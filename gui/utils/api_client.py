import requests
import os
from typing import Optional, Dict, Any, List

class APIClient:
    def __init__(self, base_url: str = "http://localhost:8000/api/v1"):
        self.base_url = base_url.rstrip("/")

    def _handle_response(self, response: requests.Response) -> Any:
        try:
            response.raise_for_status()
            if response.status_code == 204:
                return None
            return response.json()
        except requests.exceptions.HTTPError as e:
            try:
                error_detail = response.json().get("detail", str(e))
            except ValueError:
                error_detail = response.text or str(e)
            raise Exception(f"API Error: {error_detail}")
        except requests.exceptions.Timeout:
            raise Exception("API Error: Request timed out. Backend might be busy.")

    def list_tasks(self, status: str = None) -> List[Dict[str, Any]]:
        """List tasks."""
        url = f"{self.base_url}/tasks/"
        params = {}
        if status:
            params['status'] = status
        try:
            response = requests.get(url, params=params, timeout=10) # Increased timeout
            return self._handle_response(response)
        except requests.exceptions.Timeout:
            # Return empty list on timeout to avoid GUI crash, but warn user
            print("API Client Timeout listing tasks")
            return []
        except Exception as e:
            # Let other errors propagate
            raise e

    def create_task(self, file_paths: List[str]) -> Dict[str, Any]:
        """Upload files to create a new task."""
        url = f"{self.base_url}/tasks/"
        
        files = []
        opened_files = []
        
        try:
            for path in file_paths:
                f = open(path, "rb")
                opened_files.append(f)
                filename = os.path.basename(path)
                files.append(("files", (filename, f)))
            
            response = requests.post(url, files=files)
            return self._handle_response(response)
        finally:
            for f in opened_files:
                f.close()

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get the status of a task."""
        url = f"{self.base_url}/tasks/{task_id}"
        response = requests.get(url)
        return self._handle_response(response)

    def get_task_results(self, task_id: str) -> Dict[str, Any]:
        """Get the results of a task."""
        url = f"{self.base_url}/tasks/{task_id}/results"
        response = requests.get(url)
        return self._handle_response(response)

    def export_task_csv(self, task_id: str) -> bytes:
        """Export task details to CSV."""
        url = f"{self.base_url}/tasks/{task_id}/export"
        response = requests.get(url, stream=True)
        response.raise_for_status()
        return response.content

    def merge_task(self, task_id: str) -> Dict[str, Any]:
        """Merge task results into master data."""
        url = f"{self.base_url}/tasks/{task_id}/merge"
        response = requests.post(url)
        return self._handle_response(response)

    def pause_task(self, task_id: str) -> Dict[str, Any]:
        """Pause a running task."""
        url = f"{self.base_url}/tasks/{task_id}/pause"
        response = requests.post(url)
        return self._handle_response(response)

    def resume_task(self, task_id: str) -> Dict[str, Any]:
        """Resume a paused task."""
        url = f"{self.base_url}/tasks/{task_id}/resume"
        response = requests.post(url)
        return self._handle_response(response)

    def stop_task(self, task_id: str) -> Dict[str, Any]:
        """Stop/Cancel a running task."""
        url = f"{self.base_url}/tasks/{task_id}/stop"
        response = requests.post(url)
        return self._handle_response(response)

    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Legacy cancel."""
        return self.stop_task(task_id)

    def delete_task(self, task_id: str) -> Dict[str, Any]:
        """Delete a task."""
        url = f"{self.base_url}/tasks/{task_id}"
        response = requests.delete(url)
        return self._handle_response(response)

    def get_master_entities(self, site_name: str = None, entity_type: str = None, page: int = 1, size: int = 50) -> Dict[str, Any]:
        """List master entities with pagination."""
        url = f"{self.base_url}/master/entities"
        params = {
            "page": page,
            "size": size
        }
        if site_name:
            params['site_name'] = site_name
        if entity_type:
            params['entity_type'] = entity_type
            
        response = requests.get(url, params=params, timeout=10)
        return self._handle_response(response)

    def export_master_entities(self, site_name: str = None, entity_type: str = None) -> bytes:
        """Export master entities to CSV."""
        url = f"{self.base_url}/master/export"
        params = {}
        if site_name:
            params['site_name'] = site_name
        if entity_type:
            params['entity_type'] = entity_type
        
        response = requests.get(url, params=params, stream=True)
        response.raise_for_status()
        return response.content

    # --- Agent Management ---
    
    def list_agents(self, agent_type: str = None) -> List[Dict[str, Any]]:
        """List all agents."""
        url = f"{self.base_url}/agents/"
        params = {}
        if agent_type:
            params['type'] = agent_type
        response = requests.get(url, params=params, timeout=5)
        return self._handle_response(response)

    def create_agent(self, name: str, bot_id: str, agent_type: str, api_token: str = None, api_base_url: str = None) -> Dict[str, Any]:
        """Create a new agent."""
        url = f"{self.base_url}/agents/"
        payload = {
            "name": name,
            "bot_id": bot_id,
            "agent_type": agent_type,
            "api_token": api_token,
            "api_base_url": api_base_url
        }
        response = requests.post(url, json=payload)
        return self._handle_response(response)

    def delete_agent(self, agent_id: str):
        """Delete an agent."""
        url = f"{self.base_url}/agents/{agent_id}"
        response = requests.delete(url)
        return self._handle_response(response)

    # --- DB Tools ---

    def get_db_schema(self) -> Dict[str, List[Dict[str, str]]]:
        """Get database schema."""
        url = f"{self.base_url}/db/schema"
        response = requests.get(url)
        return self._handle_response(response)

    def get_table_preview(self, table_name: str) -> Dict[str, Any]:
        """Get preview of a table."""
        url = f"{self.base_url}/db/preview/{table_name}"
        response = requests.get(url)
        return self._handle_response(response)

    def execute_query(self, query: str) -> Dict[str, Any]:
        """Execute SQL query."""
        url = f"{self.base_url}/db/query"
        response = requests.post(url, json={"query": query})
        return self._handle_response(response)

    def reset_database(self) -> Dict[str, str]:
        """Reset database."""
        url = f"{self.base_url}/db/reset"
        response = requests.post(url)
        return self._handle_response(response)

    # --- Snapshots ---

    def list_snapshots(self) -> List[str]:
        """List available snapshots."""
        url = f"{self.base_url}/db/snapshots"
        response = requests.get(url)
        return self._handle_response(response)

    def create_snapshot(self) -> Dict[str, Any]:
        """Create a new snapshot."""
        url = f"{self.base_url}/db/snapshots"
        response = requests.post(url)
        return self._handle_response(response)

    def get_snapshot_content(self, filename: str) -> List[Dict[str, Any]]:
        """Get snapshot content."""
        url = f"{self.base_url}/db/snapshots/{filename}"
        response = requests.get(url)
        return self._handle_response(response)

    def restore_snapshot(self, filename: str) -> Dict[str, Any]:
        """Restore database from snapshot."""
        url = f"{self.base_url}/db/snapshots/restore/{filename}"
        response = requests.post(url)
        return self._handle_response(response)

    # --- Settings ---

    def get_settings(self) -> List[Dict[str, str]]:
        """Get all system settings."""
        url = f"{self.base_url}/db/settings"
        response = requests.get(url)
        return self._handle_response(response)

    def update_setting(self, key: str, value: str, description: str = None) -> Dict[str, str]:
        """Update a system setting."""
        url = f"{self.base_url}/db/settings"
        payload = {"key": key, "value": value}
        if description:
            payload["description"] = description
        response = requests.post(url, json=payload)
        return self._handle_response(response)
