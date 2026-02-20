import httpx
import json
from src.core.config import settings
from src.services.hiagent_client import HiAgentClient

class CozeClient:
    def __init__(self):
        self.default_api_key = settings.COZE_API_KEY
        self.default_base_url = settings.COZE_API_BASE
        self.hiagent_client = HiAgentClient()

    async def chat(self, bot_id: str, user_id: str, query: str, history: list = None, api_key: str = None, base_url: str = None, conversation_id: str = None):
        """
        Send message to Coze Bot and get response.
        Supports overriding api_key and base_url for specific agents.
        Automatically delegates to HiAgentClient if HiAgent URL is detected.
        """
        # Determine config to use
        token = api_key if api_key else self.default_api_key
        base = base_url if base_url else self.default_base_url
        
        # Ensure base url doesn't end with slash
        if base.endswith("/"):
            base = base[:-1]
            
        # Detect HiAgent
        is_hiagent = "hiagent" in base or "gf.com.cn" in base
        
        if is_hiagent:
            return await self.hiagent_client.chat(
                api_key=token,
                base_url=base,
                user_id=user_id,
                query=query,
                conversation_id=conversation_id
            )
        else:
            return await self._chat_standard_coze(
                bot_id=bot_id,
                user_id=user_id,
                query=query,
                history=history,
                api_key=token,
                base_url=base,
                conversation_id=conversation_id
            )

    async def get_bot_info(self, bot_id: str, user_id: str, api_key: str = None, base_url: str = None) -> dict:
        """
        Retrieves metadata about the bot, specifically the underlying model.
        """
        token = api_key if api_key else self.default_api_key
        base = base_url if base_url else self.default_base_url
        
        if base.endswith("/"):
            base = base[:-1]
            
        is_hiagent = "hiagent" in base or "gf.com.cn" in base
        
        info = {
            "model": "Unknown",
            "provider": "HiAgent" if is_hiagent else "Coze"
        }
        
        if is_hiagent:
            model_name = await self.hiagent_client.get_model_info(token, base, user_id)
            info["model"] = model_name
        else:
            # Standard Coze implementation (Placeholder)
            # We could call GET /v1/bot/get_online_info here
            info["model"] = "Coze Standard"
            
        return info

    async def _chat_standard_coze(self, bot_id, user_id, query, history, api_key, base_url, conversation_id):
        """Standard Coze API implementation with retry logic."""
        url = f"{base_url}/chat"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Connection": "keep-alive"
        }
        if "api.coze.com" in base_url:
            headers["Host"] = "api.coze.com"

        payload = {
            "conversation_id": conversation_id if conversation_id else "123",
            "bot_id": bot_id,
            "user": user_id,
            "query": query,
            "stream": False
        }
        if history:
            payload["chat_history"] = history

        print(f"Sending request to {url} (Standard Coze)")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(verify=False) as client:
                    response = await client.post(url, headers=headers, json=payload, timeout=60.0)
                    response.raise_for_status()
                    return response.json()
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                print(f"[Coze] Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt == max_retries - 1:
                    raise e
                await asyncio.sleep(2 * (attempt + 1))
            except httpx.HTTPStatusError as e:
                print(f"[Coze] HTTP Error: {e.response.status_code} - {e.response.text}")
                raise e
            except Exception as e:
                print(f"[Coze] Request Error: {e}")
                raise e

coze_client = CozeClient()
