import os
import pandas as pd
import re
from typing import Dict, List, Optional, Any
from src.core.config import settings

class SchemaParser:
    def __init__(self, assets_dir: str = "src/assets"):
        self.assets_dir = assets_dir
        # Map Entity Type -> CSV Filename
        # Add Synonyms
        self.template_map = {
            "SITE": "template_site.csv",
            "SETTLEMENT": "template_site.csv",
            "CITY": "template_site.csv",
            
            "SUBAREA": "template_subarea.csv",
            "ZONE": "template_subarea.csv",
            "SECTOR": "template_subarea.csv",
            "TRENCH": "template_subarea.csv",
            
            "FEATURE": "template_feature.csv",
            "GRAVE": "template_feature.csv",
            "TOMB": "template_feature.csv",
            "ASH_PIT": "template_feature.csv",
            "HOUSE": "template_feature.csv",
            "KILN": "template_feature.csv",
            "WELL": "template_feature.csv",
            "PIT": "template_feature.csv",
            
            "POTTERY": "template_pottery.csv",
            "CERAMIC": "template_pottery.csv",
            "SHERD": "template_pottery.csv",
            
            "JADE": "template_jade.csv",
            "STONE": "template_jade.csv" # Fallback for stone tools if no specific template
        }
        self._schemas: Dict[str, List[Dict]] = {}

    def get_schema_for_type(self, entity_type: str) -> List[Dict]:
        """
        Returns the hierarchical schema tree for a specific entity type.
        Lazy loads from CSV if not already cached.
        """
        entity_type_upper = entity_type.upper()
        
        if entity_type_upper not in self.template_map:
            print(f"Warning: No template found for entity type {entity_type_upper}")
            return []

        if entity_type_upper not in self._schemas:
            self._load_schema(entity_type_upper)
            
        return self._schemas.get(entity_type_upper, [])

    def _load_schema(self, entity_type: str):
        filename = self.template_map[entity_type]
        path = os.path.join(self.assets_dir, filename)
        
        if not os.path.exists(path):
            print(f"Error: Template file not found at {path}")
            self._schemas[entity_type] = []
            return

        try:
            # Try reading with header on line 2 (index 1) which is common in these files
            try:
                df = pd.read_csv(path, header=1)
                # Verify if critical columns exist, if not try header=0
                if "CAU ID" not in df.columns and "一级指标" not in df.columns:
                     df = pd.read_csv(path, header=0)
            except:
                df = pd.read_csv(path, header=0)

            # Normalize column names to handle potential variations
            df.columns = [str(c).strip() for c in df.columns]
            
            schema_tree = []
            current_root = None
            current_l1 = None
            current_l2 = None

            for _, row in df.iterrows():
                # 1. Check for Root Node (CAU ID)
                cau_id = self._get_val(row, ["CAU ID", "FieldCode", "code", "编码"])
                
                if cau_id:
                    # New Root Node
                    node = self._create_node(row, code=cau_id, level=0)
                    schema_tree.append(node)
                    current_root = node
                    current_l1 = None
                    current_l2 = None
                    continue

                # If no CAU ID, check for sub-levels
                if not current_root:
                    continue # Skip orphan rows before first root

                # 2. Check for Level 1
                l1_text = self._get_val(row, ["一级指标", "Level 1"])
                if l1_text:
                    code, name = self._parse_code_name(l1_text)
                    node = self._create_node(row, code=code, name=name, level=1)
                    # Attach to Root
                    if current_root:
                        current_root["children"].append(node)
                        current_l1 = node
                        current_l2 = None
                    continue

                # 3. Check for Level 2
                l2_text = self._get_val(row, ["二级指标", "Level 2"])
                if l2_text:
                    code, name = self._parse_code_name(l2_text)
                    node = self._create_node(row, code=code, name=name, level=2)
                    # Attach to L1 if exists, else Root
                    parent = current_l1 if current_l1 else current_root
                    if parent:
                        parent["children"].append(node)
                        current_l2 = node
                    continue

                # 4. Check for Level 3
                l3_text = self._get_val(row, ["三级指标", "Level 3"])
                if l3_text:
                    code, name = self._parse_code_name(l3_text)
                    node = self._create_node(row, code=code, name=name, level=3)
                    # Attach to L2 if exists, else L1, else Root
                    parent = current_l2 if current_l2 else (current_l1 if current_l1 else current_root)
                    if parent:
                        parent["children"].append(node)
                    continue

            self._schemas[entity_type] = schema_tree
            print(f"Loaded hierarchical schema for {entity_type}: {len(schema_tree)} root nodes.")
            
        except Exception as e:
            print(f"Failed to load schema for {entity_type}: {e}")
            self._schemas[entity_type] = []

    def _create_node(self, row: pd.Series, code: str, name: str = None, level: int = 0) -> Dict[str, Any]:
        """Creates a standardized schema node."""
        if not name:
            # Try to find name in other columns if not provided
            if level == 0:
                name = self._get_val(row, ["FieldName", "name", "字段名", "文化特征单元定义（CAU Definition）"])
            
        desc = self._get_val(row, ["Description", "desc", "描述", "抽取值字典/定义", "文化特征单元定义（CAU Definition）"])
        
        # If name is still empty, use code
        if not name:
            name = code

        return {
            "code": code,
            "name": name,
            "description": desc or "",
            "children": []
        }

    def _get_val(self, row: pd.Series, keys: List[str]) -> Optional[str]:
        """Helper to get first non-empty value from multiple potential keys."""
        for key in keys:
            if key in row and pd.notna(row[key]):
                val = str(row[key]).strip()
                if val and val.lower() != "nan" and val != "\\":
                    return val
        return None

    def _parse_code_name(self, text: str) -> (str, str):
        """
        Extracts code and name from text like "C2：相对年代" or "PS1: Fine clay ware".
        Returns (code, name).
        """
        text = text.strip()
        # Match pattern: Code followed by colon or space
        # Regex: Start with chars, then colon/space, then rest
        match = re.match(r"^([A-Za-z0-9\-\.]+)[：:]\s*(.*)", text)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        
        # Fallback: if no colon, treat whole text as name, generate code?
        # Or treat whole text as code?
        # Usually these are codes. If it's Chinese, it's likely name.
        # If it's alphanumeric, it's code.
        if re.match(r"^[A-Za-z0-9\-\.]+$", text):
            return text, text
        
        return text, text # Fallback: use text for both

# Singleton instance
schema_parser = SchemaParser()
