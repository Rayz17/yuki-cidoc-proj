
import os
import pandas as pd

template_dir = '/Users/rayz/Downloads/yuki-cidoc-proj/抽取模版'
files = [f for f in os.listdir(template_dir) if f.endswith('1201.xlsx') and not f.startswith('~$')]

for file in files:
    file_path = os.path.join(template_dir, file)
    print(f"\n--- Analyzing {file} ---")
    try:
        df = pd.read_excel(file_path)
        
        # Identify the feature column
        feature_col = None
        for col in df.columns:
            if '抽取属性' in col:
                feature_col = col
                break
        
        if feature_col:
            print(f"Feature Column: {feature_col}")
            # Filter out NaNs
            features = df[feature_col].dropna().unique().tolist()
            print(f"Features: {features}")
        else:
            print("No feature column found!")
            
    except Exception as e:
        print(f"Error reading {file}: {e}")

