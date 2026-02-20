from src.services.parser_service import schema_parser
import json

types = ["SITE", "SUBAREA", "FEATURE", "POTTERY", "JADE"]

print("Testing Schema Parser...")

for t in types:
    print(f"\n--- Testing {t} ---")
    schema = schema_parser.get_schema_for_type(t)
    if schema:
        json_str = json.dumps(schema, ensure_ascii=False)
        print(f"Success! Loaded {len(schema)} root nodes. JSON Length: {len(json_str)} chars.")
        # Print first node to verify structure
        print(f"First Node: {json.dumps(schema[0], ensure_ascii=False, indent=2)}")
        
        # Check for children
        if schema[0].get("children"):
             print(f"First Node has {len(schema[0]['children'])} children.")
    else:
        print(f"FAILED: No schema loaded for {t}")
