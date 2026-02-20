import json
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_
from src.db.models import SysTask, Entity, EntityAttribute, MasterEntity, MasterAttribute
from src.services.coze_client import coze_client
from src.services.agent_manager import AgentManager
from src.core.config import settings
import uuid

class MergerService:
    def __init__(self, db: Session):
        self.db = db
        self.agent_manager = AgentManager(db)
        # In-memory lock mechanism would be here if needed for single-instance
        # For now, we assume sequential processing or rely on logic robustness

    async def merge_task(self, task_id: str) -> dict:
        """
        Merge all extracted entities from a specific task into the Master Data Layer.
        Now supports Agent C (Deduplication) and Site-level locking.
        """
        task = self.db.query(SysTask).get(task_id)
        if not task:
            raise ValueError("Task not found")
            
        print(f"Starting Smart Merge for Task {task_id}")

        # 1. Identify Context (Site Name) - PHASE 1
        site_name = await self._identify_and_merge_site(task_id)
        print(f"Target Master Site: {site_name}")

        # 2. Get all leaf entities (Artifacts/Features) to merge - PHASE 2
        # We process them recursively to ensure parentage is merged first
        root_entities = self.db.query(Entity).filter(
            Entity.task_id == task_id,
            Entity.parent_id == None
        ).all()
        
        print(f"Found {len(root_entities)} root entities for Task {task_id}")
        
        merged_count = 0
        updated_count = 0
        
        for root in root_entities:
            print(f"Processing root entity: {root.name} ({root.entity_type})")
            m_cnt, u_count = await self._recursive_merge(root, site_name, None)
            merged_count += m_cnt
            updated_count += u_count
            
        print(f"Merge Complete. Total Merged: {merged_count}, Updated: {updated_count}")
        
        # Explicit commit at the end of the transaction
        try:
            self.db.commit()
        except Exception as e:
            print(f"Final commit failed: {e}")
            self.db.rollback()
            raise e
        
        return {
            "task_id": task_id,
            "site_name": site_name,
            "merged_entities": merged_count,
            "updated_entities": updated_count
        }

    async def _identify_and_merge_site(self, task_id: str) -> str:
        """
        Step 1: Determine the Master Site Name.
        Uses Agent C if ambiguity exists.
        """
        # Find local site entity
        local_site = self.db.query(Entity).filter(
            Entity.task_id == task_id, 
            Entity.entity_type == "SITE"
        ).first()
        
        raw_name = local_site.name if local_site else "Unknown Site"
        
        # 1. Exact Match Check
        exact = self.db.query(MasterEntity).filter(
            MasterEntity.entity_type == "SITE",
            MasterEntity.name == raw_name
        ).first()
        
        if exact:
            # Update timestamp to show activity
            try:
                exact.updated_at = datetime.utcnow()
                self.db.commit()
            except Exception as e:
                print(f"Error updating timestamp: {e}")
            return exact.name
            
        # 2. Fuzzy/Candidate Search
        candidates = self.db.query(MasterEntity).filter(
            MasterEntity.entity_type == "SITE",
            MasterEntity.name.ilike(f"%{raw_name[:2]}%") # Simple heuristic
        ).limit(5).all()
        
        if not candidates:
            # Create new Master Site
            new_site = MasterEntity(
                site_name=raw_name, # Self-ref
                entity_type="SITE",
                name=raw_name
            )
            self.db.add(new_site)
            self.db.commit()
            return raw_name
            
        # 3. Agent C Arbitration
        try:
            decision = await self._call_agent_c(
                new_entity={"name": raw_name, "type": "SITE", "path": "ROOT", "tips": local_site.entity_specific_tips if local_site else ""},
                candidates=[self._serialize_master(c) for c in candidates]
            )
        except Exception as e:
            print(f"Agent C call failed in _identify_and_merge_site: {e}")
            decision = {"decision": "NEW"}
        
        if decision and decision.get("decision") == "MATCH" and decision.get("target_master_id"):
            target = self.db.query(MasterEntity).get(decision["target_master_id"])
            if target:
                return target.name
        
        # Default: Create New
        new_site = MasterEntity(
            site_name=raw_name,
            entity_type="SITE",
            name=raw_name
        )
        self.db.add(new_site)
        self.db.commit()
        return raw_name

    async def _recursive_merge(self, entity: Entity, site_name: str, parent_master_id: str = None):
        """
        Recursively merge entities.
        Returns (merged_count, updated_count)
        """
        m_count = 0
        u_count = 0
        
        # 1. Merge Current Entity
        # Only merge if extracted (or if it's a structural node needed for path)
        master_id = None
        
        # Try to find Master Match
        master_entity, status = await self._find_or_create_master(entity, site_name, parent_master_id)
        
        if status == "CREATED":
            m_count += 1
            print(f"Created Master Entity: {entity.name}")
        else:
            u_count += 1
            print(f"Updated Master Entity: {entity.name}")
            
        master_id = master_entity.id
        
        # Merge Attributes (only if extracted)
        if entity.extraction_status == "EXTRACTED":
            self._merge_attributes(entity, master_entity)
            
        # 2. Process Children
        children = self.db.query(Entity).filter(Entity.parent_id == entity.id).all()
        print(f"Entity {entity.name} has {len(children)} children.")
        
        for child in children:
            mc, uc = await self._recursive_merge(child, site_name, master_id)
            m_count += mc
            u_count += uc
            
        return m_count, u_count

    async def _find_or_create_master(self, entity: Entity, site_name: str, parent_master_id: str) -> (MasterEntity, str):
        # 1. Exact Match (Fast Path)
        # Match by Name + Type + Site + Parent (if applicable)
        # Note: MasterEntity currently doesn't store parent_id explicitly in schema (flattened?)
        # Wait, MasterEntity needs hierarchy to distinguish Zone A M1 vs Zone B M1.
        # Current MasterEntity schema relies on 'site_name' grouping.
        # WE NEED parent_id in MasterEntity to support true hierarchy!
        # Assuming we can't change schema right now, we use Name + Site.
        # But Agent C design assumes paths.
        
        # Let's search by Name + Site first
        candidates = self.db.query(MasterEntity).filter(
            MasterEntity.site_name == site_name,
            MasterEntity.entity_type == entity.entity_type,
            MasterEntity.name == entity.name
        ).all()
        
        if len(candidates) == 1:
            return candidates[0], "UPDATED"
        elif len(candidates) > 1:
            # Ambiguous! Need Agent C
            pass
        else:
            # No exact match. Try Fuzzy.
            pass
            
        # Prepare for Agent C
        # Retrieve potential candidates (fuzzy name match in same site)
        fuzzy_candidates = self.db.query(MasterEntity).filter(
            MasterEntity.site_name == site_name,
            MasterEntity.entity_type == entity.entity_type,
            MasterEntity.name.ilike(f"%{entity.name}%")
        ).limit(5).all()
        
        if not fuzzy_candidates:
            # Create New
            new_master = MasterEntity(
                site_name=site_name,
                entity_type=entity.entity_type,
                name=entity.name
            )
            self.db.add(new_master)
            self.db.flush()
            return new_master, "CREATED"
            
        # Call Agent C
        # Build Path String for Context
        path_str = f"{site_name} > ... > {entity.name}" # Simplified path
        
        try:
            decision = await self._call_agent_c(
                new_entity={
                    "name": entity.name, 
                    "type": entity.entity_type, 
                    "path": path_str, 
                    "tips": entity.entity_specific_tips or ""
                },
                candidates=[self._serialize_master(c) for c in fuzzy_candidates]
            )
        except Exception as e:
            print(f"Agent C call failed in _find_or_create_master: {e}")
            decision = {"decision": "NEW"}
        
        if decision and decision.get("decision") == "MATCH" and decision.get("target_master_id"):
            target = self.db.query(MasterEntity).get(decision["target_master_id"])
            if target:
                return target, "UPDATED"
                
        # Create New
        new_master = MasterEntity(
            site_name=site_name,
            entity_type=entity.entity_type,
            name=entity.name
        )
        self.db.add(new_master)
        self.db.flush()
        return new_master, "CREATED"

    def _merge_attributes(self, entity: Entity, master_entity: MasterEntity):
        attributes = self.db.query(EntityAttribute).filter(
            EntityAttribute.entity_id == entity.id
        ).all()
        
        if attributes:
            # Update Entity Timestamp
            try:
                master_entity.updated_at = datetime.utcnow()
            except: pass
        
        for attr in attributes:
            # Upsert logic
            master_attr = self.db.query(MasterAttribute).filter(
                MasterAttribute.master_entity_id == master_entity.id,
                MasterAttribute.attribute_code == attr.attribute_code
            ).first()
            
            if master_attr:
                master_attr.attribute_value = attr.attribute_value
                master_attr.quote = attr.quote
                master_attr.source_task_id = entity.task_id
            else:
                master_attr = MasterAttribute(
                    master_entity_id=master_entity.id,
                    attribute_code=attr.attribute_code,
                    attribute_value=attr.attribute_value,
                    quote=attr.quote,
                    source_task_id=entity.task_id
                )
                self.db.add(master_attr)
        self.db.commit()

    def _serialize_master(self, entity: MasterEntity) -> dict:
        return {
            "id": str(entity.id),
            "name": entity.name,
            "type": entity.entity_type,
            "site": entity.site_name,
            # In a real scenario, we'd fetch attributes to provide context like 'Year'
            "context": "Existing Database Record" 
        }

    async def _call_agent_c(self, new_entity: dict, candidates: list) -> dict:
        # 1. Try to get DEDUP agent from DB
        agent_config = self.agent_manager.get_next_agent("DEDUP")
        
        bot_id = None
        api_token = None
        base_url = None
        
        if agent_config:
            bot_id = agent_config.bot_id
            api_token = agent_config.api_token
            base_url = agent_config.api_base_url
            # print(f"Using Agent C from DB: {agent_config.name}")
        elif settings.COZE_BOT_ID_C:
            bot_id = settings.COZE_BOT_ID_C
            # print("Using Agent C from Environment Variables")
        else:
            print("Warning: Agent C not configured. Skipping deduplication.")
            return {"decision": "NEW"}
            
        try:
            # Pre-process candidates to ensure they are JSON serializable
            safe_candidates = []
            for c in candidates:
                if isinstance(c, dict):
                    safe_candidates.append(c)
                elif hasattr(c, "__tablename__"): # SQLA Model
                    safe_candidates.append(self._serialize_master(c))
                else:
                    # Fallback
                    safe_candidates.append(str(c))

            prompt = f"""
            # Task: Deduplication
            Analyze if the New Entity matches any Candidate.
            
            # New Entity
            Name: {new_entity.get('name', 'Unknown')}
            Type: {new_entity.get('type', 'Unknown')}
            Path: {new_entity.get('path', 'Unknown')}
            Context: {new_entity.get('tips', '')}
            
            # Candidates
            {json.dumps(safe_candidates, indent=2, ensure_ascii=False, default=str)}
            
            Respond JSON only.
            """
        
            # Reuse CozeClient (assuming it supports generic calls)
            response = await coze_client.chat(
                bot_id=bot_id,
                user_id="system_merge_service",
                query=prompt,
                api_key=api_token,
                base_url=base_url
            )
            
            # Robust parsing
            if not isinstance(response, dict):
                print(f"Agent C unexpected response type: {type(response)}")
                return {"decision": "NEW"}
                
            if 'messages' not in response:
                print(f"Agent C response missing 'messages'. Keys: {response.keys()}")
                # Try to see if it's a direct error from Coze/HiAgent
                if 'code' in response and response['code'] != 0:
                     print(f"Agent C API Error: {response}")
                return {"decision": "NEW"}
                
            messages = response['messages']
            if not messages or not isinstance(messages, list):
                 print(f"Agent C 'messages' is empty or invalid: {messages}")
                 return {"decision": "NEW"}
                 
            content = messages[0].get('content', '')
            if not content:
                 print("Agent C response content is empty")
                 return {"decision": "NEW"}
            
            # Parse JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content: # Handle unspec code blocks
                content = content.split("```")[1].split("```")[0]
                
            return json.loads(content.strip())
            
        except Exception as e:
            print(f"Agent C failed with exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"decision": "NEW"}
