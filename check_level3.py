import os
import pandas as pd

assets_dir = "src/assets"
files = [f for f in os.listdir(assets_dir) if f.endswith(".csv")]

print(f"Checking {len(files)} CSV files for '三级指标' content...")

for file in files:
    path = os.path.join(assets_dir, file)
    try:
        # Try reading with header on line 2 (index 1)
        df = pd.read_csv(path, header=1)
        
        # Check if "三级指标" column exists
        col_name = None
        for col in df.columns:
            if "三级指标" in str(col):
                col_name = col
                break
        
        if not col_name:
            # Try header=0 just in case
            df = pd.read_csv(path, header=0)
            for col in df.columns:
                if "三级指标" in str(col):
                    col_name = col
                    break
        
        if not col_name:
            print(f"[{file}] Column '三级指标' NOT FOUND.")
            continue
            
        # Print unique values to debug
        unique_vals = df[col_name].dropna().unique()
        print(f"[{file}] Unique values in Level 3: {unique_vals}")

            
    except Exception as e:
        print(f"[{file}] Error reading: {e}")
