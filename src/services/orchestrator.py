import json
import re
import asyncio
import httpx
import os
from datetime import datetime
from sqlalchemy.orm import Session
from src.db.models import SysTask, Entity, TextSegment, EntityAttribute, SystemSetting
from src.services.coze_client import coze_client
from src.core.config import settings
from src.services.parser_service import schema_parser
from src.services.agent_manager import AgentManager
from src.services.merger_service import MergerService

class Orchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.agent_manager = AgentManager(db)
        self.chunk_size = 4000  # Characters per chunk (Reduced from 6000 to avoid context limits)
        self.chunk_overlap = 500 # Overlap to maintain context

    async def process_task(self, task_id: str, raw_text: str, bot_structure_id: str = None, bot_extraction_id: str = None):
        # 1. Retrieve Task
        task = self.db.query(SysTask).filter(SysTask.id == task_id).first()
        if not task:
            raise ValueError("Task not found")
            
        # Handle Resume from SUSPENDED
        if task.status == "SUSPENDED":
            print(f"Resuming task {task_id} from SUSPENDED state...")
            if task.is_paused: # Should be unpaused by API before calling this
                task.is_paused = False
        else:
            # Smart Resume: If passed as EXTRACTING (from resume_task), keep it.
            # Only reset to STRUCTURING if it's PENDING (new or full restart).
            if task.status != "EXTRACTING":
                task.status = "STRUCTURING" # Phase 1
            
            task.start_time = datetime.utcnow()
            task.bot_structure_id = bot_structure_id
            task.bot_extraction_id = bot_extraction_id
            
            # Save Model Info (Basic info for now)
            model_info = {
                "structure_bot": {"id": bot_structure_id, "name": "Unknown", "model": "Unknown"},
                "extraction_bot": {"id": bot_extraction_id, "name": "Unknown", "model": "Unknown"}
            }
            
            # Fetch Structure Bot Info
            if bot_structure_id:
                agent = self.agent_manager.get_agent(bot_structure_id)
                if agent:
                    model_info["structure_bot"]["name"] = agent.name
                    try:
                        print(f"Querying model info for Structure Bot {agent.name}...")
                        info = await coze_client.get_bot_info(
                            bot_id=agent.bot_id,
                            user_id="system_probe",
                            api_key=agent.api_token,
                            base_url=agent.api_base_url
                        )
                        model_info["structure_bot"]["model"] = info.get("model", "Unknown")
                    except Exception as e:
                        print(f"Failed to get model info for Structure Bot: {e}")
                
            # Fetch Extraction Bot Info
            if bot_extraction_id:
                agent = self.agent_manager.get_agent(bot_extraction_id)
                if agent:
                    model_info["extraction_bot"]["name"] = agent.name
                    try:
                        print(f"Querying model info for Extraction Bot {agent.name}...")
                        info = await coze_client.get_bot_info(
                            bot_id=agent.bot_id,
                            user_id="system_probe",
                            api_key=agent.api_token,
                            base_url=agent.api_base_url
                        )
                        model_info["extraction_bot"]["model"] = info.get("model", "Unknown")
                    except Exception as e:
                        print(f"Failed to get model info for Extraction Bot: {e}")
                
            task.llm_model_info = json.dumps(model_info, ensure_ascii=False)
        
        self.db.commit()

        try:
            # Check Cancellation / Pause
            if await self._is_stopped_or_cancelled(task_id): return
            await self._check_pause(task_id)

            # 2. Chunking & Agent A (Structure)
            # Only run if not already past this stage
            # Double check: if status is EXTRACTING, we should skip this block entirely
            if task.status == "STRUCTURING" or task.status == "PENDING":
                chunks = self._chunk_text(raw_text)
                print(f"Split text into {len(chunks)} chunks.")
                
                # Check Resume Progress
                start_index = 0
                if task.progress:
                    try:
                        prog = json.loads(task.progress)
                        if prog.get("phase") == "STRUCTURE":
                            start_index = prog.get("chunk_index", -1) + 1
                            if start_index > 0:
                                print(f"Resuming Structure phase from chunk index {start_index}")
                    except: pass
                else:
                    # Fresh start: Clear global tips to avoid duplication if retrying
                    task.global_context_tips = ""

                for i, chunk in enumerate(chunks):
                    if i < start_index:
                        continue # Skip processed chunks

                    # Check Pause inside loop
                    await self._check_pause(task_id)
                    if await self._is_stopped_or_cancelled(task_id): return
                    
                    print(f"Processing Chunk {i+1}/{len(chunks)}...")
                    try:
                        chunk_result = await self._call_agent_a(chunk, bot_structure_id)
                    except httpx.RequestError as e:
                        print(f"Network error in Structure phase: {e}")
                        self._suspend_task(task, f"Network error during structuring: {str(e)}")
                        return

                    # Save entities immediately (Incremental Saving)
                    entities = chunk_result.get("entities", []) or [] # Ensure it's a list even if None
                    if not isinstance(entities, list):
                        print(f"Warning: 'entities' from Agent A is not a list ({type(entities)}). Setting to empty.")
                        entities = []
                        
                    for entity_data in entities:
                        self._save_entity_recursive(entity_data, parent_id=None, task_id=task.id)
                    
                    # Save tips immediately
                    tips = chunk_result.get("global_tips", "")
                    if tips:
                        current_tips = task.global_context_tips or ""
                        task.global_context_tips = f"{current_tips}\n{tips}".strip()

                    # Update Progress
                    task.progress = json.dumps({"phase": "STRUCTURE", "chunk_index": i}, ensure_ascii=False)
                    self.db.commit()

                # Loop ends
                task.status = "EXTRACTING"
                # Clear progress for next phase
                task.progress = json.dumps({"phase": "EXTRACTING", "chunk_index": 0}, ensure_ascii=False)
                self.db.commit()

            # Check Cancellation / Pause
            if await self._is_stopped_or_cancelled(task_id): return
            await self._check_pause(task_id)

            # 4. Trigger Extraction (Agent B)
            if task.status == "EXTRACTING":
                await self._run_extraction_phase(task.id, bot_extraction_id)
            
            # Final Check
            self.db.refresh(task)
            if task.status == "STOPPED":
                print(f"Task {task_id} finished via STOP command.")
                task.end_time = datetime.utcnow()
                self.db.commit()
                # Check Auto-Merge for STOPPED tasks
                await self._check_auto_merge(task.id)
                return

            if await self._is_cancelled(task_id): return
            
            # Don't overwrite SUSPENDED status if set during extraction
            if task.status == "SUSPENDED":
                print(f"Task {task_id} ended in SUSPENDED state.")
                return

            task.status = "COMPLETED"
            task.end_time = datetime.utcnow()
            self.db.commit()

            # 5. Auto-Merge Check
            await self._check_auto_merge(task.id)

        except Exception as e:
            # If it was already marked SUSPENDED inside, don't mark FAILED
            # Refresh to get latest status
            self.db.rollback() # Rollback transaction to ensure session is clean
            try:
                self.db.refresh(task)
            except: pass
            
            if task.status != "SUSPENDED" and task.status != "STOPPED":
                print(f"Task {task_id} FAILED with exception: {e}")
                import traceback
                traceback.print_exc()
                
                task.status = "FAILED"
                task.end_time = datetime.utcnow()
                # Append error to global tips for visibility
                current_tips = task.global_context_tips or ""
                task.global_context_tips = f"{current_tips}\n[SYSTEM ERROR] {str(e)}"
                self.db.commit()
            raise e
        except BaseException as e:
            # Catch cancellation or system exit
            print(f"Task {task_id} interrupted by BaseException: {e}")
            try:
                self.db.refresh(task)
                if task.status != "SUSPENDED" and task.status != "STOPPED":
                    task.status = "FAILED"
                    task.global_context_tips = f"{task.global_context_tips or ''}\n[SYSTEM CRASH] Interrupted by {type(e).__name__}"
                    self.db.commit()
            except: pass
            raise e
        finally:
            # Release Bots
            print(f"Releasing bots for task {task_id}")
            self.agent_manager.release_bot_pair(task_id)

    def _suspend_task(self, task, reason):
        """Sets task to SUSPENDED state."""
        task.status = "SUSPENDED"
        # Append reason to global tips for visibility
        current_tips = task.global_context_tips or ""
        task.global_context_tips = f"{current_tips}\n[SYSTEM LOG] Task suspended due to: {reason}"
        self.db.commit()
        print(f"Task {task.id} suspended: {reason}")

    async def _check_auto_merge(self, task_id):
        """Checks system settings and performs auto-merge if enabled."""
        setting = self.db.query(SystemSetting).filter(SystemSetting.key == "auto_merge_enabled").first()
        if setting and setting.value == "true":
            print(f"Auto-merge enabled. Merging task {task_id}...")
            try:
                merger = MergerService(self.db)
                result = await merger.merge_task(task_id)
                print(f"Auto-merge success: {result}")
            except Exception as e:
                print(f"Auto-merge failed: {e}")

    async def _check_pause(self, task_id):
        """Checks if task is paused and sleeps until resumed."""
        while True:
            # Re-fetch task to check current status
            self.db.expire_all()
            task = self.db.query(SysTask).get(task_id)
            if not task: return
            
            if task.status == "CANCELLED" or task.status == "STOPPED": return
            
            if task.is_paused:
                print(f"Task {task_id} is paused. Waiting...")
                await asyncio.sleep(2)
            else:
                break

    def _chunk_text(self, text: str) -> list[str]:
        """Splits text into chunks with overlap."""
        if len(text) <= self.chunk_size:
            return [text]
            
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += (self.chunk_size - self.chunk_overlap)
        return chunks

    async def _is_cancelled(self, task_id):
        # Re-fetch task to check current status
        self.db.expire_all()
        task = self.db.query(SysTask).get(task_id)
        if task and task.status == "CANCELLED":
            print(f"Task {task_id} was cancelled by user.")
            return True
        return False
        
    async def _is_stopped_or_cancelled(self, task_id):
        # Re-fetch task
        self.db.expire_all()
        task = self.db.query(SysTask).get(task_id)
        if not task: return False
        
        if task.status == "CANCELLED":
            print(f"Task {task_id} was cancelled by user.")
            return True
        
        if task.status == "STOPPED":
            print(f"Task {task_id} was manually stopped by user.")
            # Trigger auto-merge for partial results
            await self._check_auto_merge(task_id)
            return True
            
        return False

    def _get_bot_config(self, agent_type: str, assigned_bot_id: str = None):
        """
        Get full AgentConfig object.
        """
        if assigned_bot_id:
            agent = self.agent_manager.get_agent(assigned_bot_id)
            if agent:
                print(f"Using Assigned Agent: {agent.name} ({agent.bot_id})")
                return agent
            else:
                print(f"Assigned agent {assigned_bot_id} not found in DB!")

        # Fallback (Legacy)
        agent = self.agent_manager.get_next_agent(agent_type)
        if agent:
            print(f"Selected Agent: {agent.name} ({agent.bot_id})")
            return agent
        
        # Fallback to env vars
        bot_id = None
        if agent_type == "STRUCTURE":
            bot_id = settings.COZE_BOT_ID_A
        elif agent_type == "EXTRACTION":
            bot_id = settings.COZE_BOT_ID_B
            
        if bot_id:
            class EnvAgent:
                bot_id = None
                api_token = None
                api_base_url = None
            
            env_agent = EnvAgent()
            env_agent.bot_id = bot_id
            env_agent.api_token = settings.COZE_API_KEY
            env_agent.api_base_url = settings.COZE_API_BASE
            return env_agent
            
        return None

    async def _call_agent_a(self, text: str, bot_id: str = None) -> dict:
        print("Calling Agent A (Structure)...")
        agent_config = self._get_bot_config("STRUCTURE", bot_id)
        
        if not agent_config:
            raise ValueError("No Structure Bot configured!")

        # Retry loop for JSON parsing errors
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Load prompt template (optional, but good practice)
                # For now, sticking to simple query as Structure prompt is usually fixed in Bot
                response = await coze_client.chat(
                    bot_id=agent_config.bot_id,
                    user_id="system_user",
                    query=f"Analyze this text:\n{text}",
                    api_key=agent_config.api_token,
                    base_url=agent_config.api_base_url
                )
                
                content = response['messages'][0]['content']
                if not content:
                    print(f"Agent A returned empty content (Attempt {attempt+1}/{max_retries}).")
                    if attempt == max_retries - 1:
                        return {"entities": []}
                    await asyncio.sleep(1)
                    continue
                return self._clean_and_parse_json(content)
            except httpx.RequestError as e:
                # Re-raise network errors to allow suspension
                raise e
            except ValueError as ve: # JSON parse error
                print(f"Attempt {attempt+1}/{max_retries} failed to parse JSON from Agent A: {ve}")
                if attempt == max_retries - 1:
                    print(f"Final failure parsing Agent A response.")
                    return {"entities": []}
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Error calling Agent A: {e}")
                return {"entities": []}
        
        return {"entities": []}

    def _clean_and_parse_json(self, content: str) -> dict:
        """
        Robustly attempts to extract and parse JSON from a string.
        """
        if not content:
            return {}
            
        content = content.strip()
        
        # 1. Try standard markdown extraction
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
            
        # 2. Try regex to find the first JSON object or array
        try:
            return json.loads(content, strict=False)
        except json.JSONDecodeError:
            pass

        # Regex to find the outermost JSON object/array
        start_brace = content.find('{')
        start_bracket = content.find('[')
        
        start_index = -1
        end_index = -1
        
        if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
            # Probably an object
            start_index = start_brace
            end_index = content.rfind('}') + 1
        elif start_bracket != -1:
            # Probably an array
            start_index = start_bracket
            end_index = content.rfind(']') + 1
            
        if start_index != -1 and end_index != -1:
            potential_json = content[start_index:end_index]
            try:
                return json.loads(potential_json, strict=False)
            except json.JSONDecodeError as e:
                print(f"JSON Parse Error: {e}")
                # Try fixing trailing commas
                fixed = re.sub(r',\s*([\]}])', r'\1', potential_json)
                try:
                    return json.loads(fixed, strict=False)
                except: pass
                
        print("Failed to parse JSON from content.")
        raise ValueError("Could not parse JSON content")

    def _save_entity_recursive(self, data: dict, parent_id, task_id):
        # Check if entity already exists to avoid duplicates (Unique Constraint: parent_id, entity_type, name, task_id)
        existing_entity = self.db.query(Entity).filter(
            Entity.task_id == task_id,
            Entity.parent_id == parent_id,
            Entity.entity_type == data.get("type", "UNKNOWN").upper(),
            Entity.name == data.get("name", "Unnamed")
        ).first()

        if existing_entity:
            entity = existing_entity
            # Optional: Update tips if new tips are more detailed? For now, we keep the first one or append?
            # Let's append if different
            new_tips = data.get("entity_tips", "")
            if new_tips and new_tips not in (entity.entity_specific_tips or ""):
                entity.entity_specific_tips = f"{entity.entity_specific_tips or ''}\n{new_tips}".strip()
        else:
            # Create Entity
            entity = Entity(
                parent_id=parent_id,
                task_id=task_id,
                entity_type=data.get("type", "UNKNOWN").upper(),
                name=data.get("name", "Unnamed"),
                entity_specific_tips=data.get("entity_tips", "")
            )
            self.db.add(entity)
            self.db.flush() # Get ID
        
        # Save Text Segment (Always append new evidence)
        if data.get("related_text"):
            segment = TextSegment(
                entity_id=entity.id,
                content=data.get("related_text")
            )
            self.db.add(segment)
        else:
            # Only warn if it's a new entity without text. If existing, maybe it's fine.
            if not existing_entity:
                print(f"Warning: Entity {data.get('name')} has no related_text from Agent A.")

        # Recurse
        for child in data.get("children", []):
            self._save_entity_recursive(child, entity.id, task_id)

    def _flatten_attributes(self, data: dict, prefix: str = "") -> list:
        """
        Flattens nested JSON into (code, value, quote) tuples.
        """
        results = []
        
        if not isinstance(data, dict):
            return results

        # Check if this is a leaf node (has 'value' and 'quote')
        # Note: Some agents might miss 'quote' or 'value', so be lenient but prefer both
        if "value" in data:
            # It's a leaf!
            code = prefix
            val = data["value"]
            quote = data.get("quote") # Optional but requested
            
            # If value is complex (list/dict), it's not a leaf in the strict sense, 
            # but Agent B V3 should return primitives in 'value'.
            # If 'value' is a list/dict, we might need to recurse or serialize?
            # V3 prompt asks for "value: extracted value".
            if isinstance(val, (dict, list)):
                 # If value is complex, maybe it's not a leaf node but a container?
                 # But if key is "value", it's likely the value.
                 # Let's stringify it if complex.
                 val = str(val)
            
            results.append((code, val, quote))
            
            # Continue to check siblings/children just in case (e.g. ProductionDate.type + ProductionDate.C2)
        
        for key, val in data.items():
            if key in ["value", "quote", "confidence"]: 
                continue # Already handled or metadata
            
            new_prefix = f"{prefix}.{key}" if prefix else key
            
            if isinstance(val, dict):
                # Recurse
                results.extend(self._flatten_attributes(val, new_prefix))
            elif isinstance(val, list):
                # Handle list of objects (e.g. multiple items)
                for i, item in enumerate(val):
                    if isinstance(item, dict):
                        # Use index in code: FoundItems.0.Name
                        results.extend(self._flatten_attributes(item, f"{new_prefix}.{i}"))
                    else:
                        # List of primitives?
                        results.append((f"{new_prefix}.{i}", str(item), None))
            else:
                # Primitive value at this level (should be wrapped in object but if not...)
                results.append((new_prefix, str(val), None))
                
        return results

    async def _run_extraction_phase(self, task_id, bot_id: str = None):
        print("Starting Extraction Phase (Agent B)...")
        # Get all entities for this task that are not yet extracted
        all_entities = self.db.query(Entity).filter(
            Entity.task_id == task_id
        ).all()
        
        task = self.db.query(SysTask).get(task_id)
        
        for entity in all_entities:
            # Check Cancellation / Pause in loop
            if await self._is_stopped_or_cancelled(task_id): return
            await self._check_pause(task_id)

            # Skip if already extracted (Idempotency)
            if entity.extraction_status == "EXTRACTED":
                continue

            # Check if we have a schema for this entity type
            schema = schema_parser.get_schema_for_type(entity.entity_type)
            if not schema:
                print(f"Skipping extraction for {entity.name}: No schema found for type {entity.entity_type}")
                continue
                
            # Gather text context
            segments = self.db.query(TextSegment).filter(TextSegment.entity_id == entity.id).all()
            text = "\n".join([s.content for s in segments])
            
            if not text.strip():
                print(f"Skipping {entity.name}: No text content found (related_text is empty).")
                # Fallback: Use entity tips if available
                if entity.entity_specific_tips:
                    print(f"Fallback: Using entity_specific_tips for {entity.name}")
                    text = f"Context: {entity.entity_specific_tips}"
                else:
                    continue

            # Construct Tips
            tips = f"Global Context: {task.global_context_tips or 'None'}\n"
            tips += f"Entity Context: {entity.entity_specific_tips or 'None'}"
            
            # Add Hierarchy Context
            if entity.parent_id:
                parent = self.db.query(Entity).get(entity.parent_id)
                if parent:
                    tips += f"\nHierarchical Context: This entity belongs to {parent.name} ({parent.entity_type})."
                    if parent.entity_specific_tips:
                        tips += f" Parent Context: {parent.entity_specific_tips}"

            # Call Agent B
            print(f"Extracting attributes for {entity.name}...")
            try:
                extraction_result = await self._call_agent_b(text, tips, schema, text, bot_id) # Pass related_text as related_text arg
            except httpx.RequestError as e:
                print(f"Network error in Extraction phase: {e}")
                self._suspend_task(task, f"Network error during extraction of {entity.name}: {str(e)}")
                return
            
            # Flatten and Save Attributes
            flattened_attrs = self._flatten_attributes(extraction_result)
            
            for code, val, quote in flattened_attrs:
                attr = EntityAttribute(
                    entity_id=entity.id,
                    attribute_code=code,
                    attribute_value=val,
                    quote=quote
                )
                self.db.add(attr)
            
            # [Fix] Always save the full source text as a special attribute
            # This ensures we have the context even if extraction failed or was partial
            # Update SourceText generation to use full text as value (Goal 1.1)
            source_attr = EntityAttribute(
                entity_id=entity.id,
                attribute_code="SourceText",
                attribute_value=text, # Use full text as value
                quote=text,
                confidence="HIGH"
            )
            self.db.add(source_attr)
            
            entity.extraction_status = "EXTRACTED"
            self.db.commit()

    async def _call_agent_b(self, text: str, tips: str, schema: list, related_text: str, bot_id: str = None) -> dict:
        agent_config = self._get_bot_config("EXTRACTION", bot_id)
        
        if not agent_config:
            raise ValueError("No Extraction Bot configured!")

        # Prepare Schema JSON - Compact format to save tokens
        schema_json = json.dumps(schema, ensure_ascii=False)
        
        # Construct Data-Only Prompt (User Query)
        # Assuming System Prompt is already configured in the Bot
        prompt = f"""
[DATA START]
Target Text:
{text}

Related Context:
{related_text}

Global & Entity Tips:
{tips}

Extraction Schema:
{schema_json}
[DATA END]

Please extract the attributes defined in the Schema from the Target Text, referencing the Context. Return the JSON object.
"""
        
        # Retry loop for JSON parsing errors
        max_retries = 3
        for attempt in range(max_retries):
            response = await coze_client.chat(
                bot_id=agent_config.bot_id,
                user_id="system_user",
                query=prompt,
                api_key=agent_config.api_token,
                base_url=agent_config.api_base_url
            )
            
            try:
                content = response['messages'][0]['content']
                if not content:
                    print(f"Agent B returned empty content (Attempt {attempt+1}/{max_retries}).")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                    return {}
                return self._clean_and_parse_json(content)
            except Exception as e:
                print(f"Error parsing Agent B response (Attempt {attempt+1}/{max_retries}): {e}")
                try:
                    raw_content = response.get('messages', [{}])[0].get('content', 'N/A')
                    print(f"Raw content: {raw_content}")
                    
                    # Self-Correction: Append error to prompt for next retry
                    if attempt < max_retries - 1:
                        prompt += f"\n\n[SYSTEM ERROR] Your previous response was invalid JSON. Error: {str(e)}. Please correct it and return ONLY valid JSON."
                        await asyncio.sleep(1)
                        continue
                except: pass
                
                if attempt == max_retries - 1:
                    return {}
        return {}
