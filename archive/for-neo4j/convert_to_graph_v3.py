import pandas as pd
import hashlib
import os
import sys

# 配置输入输出路径
INPUT_DIR = 'for-neo4j'
OUTPUT_DIR = 'neo4j_import_v3'

# 输入文件定义
FILE_SITES = os.path.join(INPUT_DIR, 'sites_export_20251203.csv')
FILE_STRUCTURES = os.path.join(INPUT_DIR, 'site_structures_export_20251203.csv')
FILE_PERIODS = os.path.join(INPUT_DIR, 'periods_export_20251203.csv')
FILE_POTTERY = os.path.join(INPUT_DIR, 'pottery_artifacts_export_20251203.csv')
FILE_JADE = os.path.join(INPUT_DIR, 'jade_artifacts_export_20251203.csv')

# 确保输出目录存在
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

print(f"开始处理数据，输出目录: {OUTPUT_DIR}")

# --- 工具函数 ---

def get_id(prefix, value):
    """生成基于内容的唯一 Hash ID"""
    if pd.isna(value) or str(value).strip() == "" or str(value).strip().lower() == "nan":
        return None
    clean_val = str(value).strip()
    # 使用MD5生成8位Hash
    return f"{prefix}_{hashlib.md5(clean_val.encode('utf-8')).hexdigest()[:8]}"

def clean_str(val):
    if pd.isna(val): return ""
    return str(val).strip()

# --- 1. 加载数据 ---
print("正在加载 CSV 文件...")
try:
    df_sites = pd.read_csv(FILE_SITES)
    df_structs = pd.read_csv(FILE_STRUCTURES)
    df_periods = pd.read_csv(FILE_PERIODS)
    df_pottery = pd.read_csv(FILE_POTTERY)
    df_jade = pd.read_csv(FILE_JADE)
except FileNotFoundError as e:
    print(f"错误：找不到文件 {e.filename}")
    sys.exit(1)

# --- 2. 处理 Sites (E27) ---
print("处理 Sites...")
site_nodes = []
# 建立 Site ID 映射表 (用于后续查找)
site_id_map = {} # ID -> node_id

for _, row in df_sites.iterrows():
    s_uuid = get_id("site", row['ID'])
    site_nodes.append({
        "id:ID": s_uuid,
        "name": clean_str(row['遗址名称']),
        "location": clean_str(row.get('地理位置', '')),
        ":LABEL": "E27_Site"
    })
    site_id_map[row['ID']] = s_uuid

pd.DataFrame(site_nodes).to_csv(os.path.join(OUTPUT_DIR, 'nodes_sites.csv'), index=False)

# --- 3. 处理 Structures (E53/E25) ---
print("处理 Structures...")
place_nodes = []
feature_nodes = []
edges_hierarchy = [] # 存放 Site->Struct, Struct->Feature 等关系

# 建立 Structure Name 映射表 (用于 Artifacts 查找位置)
# Key: (site_id_str, name_str) -> Value: node_id
struct_map = {}

for _, row in df_structs.iterrows():
    raw_name = clean_str(row['structure_name'])
    raw_type = clean_str(row['structure_type'])
    site_ref = row['site_id']
    
    if not raw_name: continue
    
    # 生成节点ID
    # 为了防止不同遗址有同名单位(如M1)，加入site_id做hash
    struct_uuid = get_id("struct", f"{site_ref}_{raw_name}")
    
    # 记录映射
    struct_map[(str(site_ref), raw_name)] = struct_uuid
    
    # 区分 E53 和 E25
    # 逻辑：墓地、发掘区、区域 -> E53; 墓葬、灰坑、房址 -> E25
    is_place = False
    if raw_type in ['墓地', '发掘区', '居住区', '祭祀区', '区域']:
        is_place = True
    elif '区' in raw_name and '区' not in ['灰坑', '房址']: # 简单启发式
        is_place = True
        
    if is_place:
        place_nodes.append({
            "id:ID": struct_uuid,
            "name": raw_name,
            "type": raw_type,
            ":LABEL": "E53_Place"
        })
        # 关系: Site -> Place
        if site_ref in site_id_map:
            edges_hierarchy.append({
                ":START_ID": site_id_map[site_ref],
                ":END_ID": struct_uuid,
                ":TYPE": "P46_is_composed_of"
            })
    else:
        feature_nodes.append({
            "id:ID": struct_uuid,
            "name": raw_name,
            "code": raw_name, # 暂同
            "type": raw_type,
            ":LABEL": "E25_Man_Made_Feature"
        })
        # 关系: Site -> Feature (直接归属，或通过 Place 归属)
        # 这里简化处理：如果 parent_id 存在则连 parent，否则直接连 Site
        # 由于 CSV 中 parent_id 往往为空，我们这里直接建立 P89 (falls within) 到 Site
        if site_ref in site_id_map:
            edges_hierarchy.append({
                ":START_ID": struct_uuid,
                ":END_ID": site_id_map[site_ref],
                ":TYPE": "P89_falls_within"
            })
            # 同时建立 P46 (composed of) 的反向语义，通常用 P46 连接 Site -> Feature
            # 但 P89 更强调空间包含。Neo4j中可以双向或选其一。这里为了层级树，加一条 Site -> Feature
            edges_hierarchy.append({
                ":START_ID": site_id_map[site_ref],
                ":END_ID": struct_uuid,
                ":TYPE": "P46_is_composed_of"
            })

pd.DataFrame(place_nodes).to_csv(os.path.join(OUTPUT_DIR, 'nodes_places.csv'), index=False)
pd.DataFrame(feature_nodes).to_csv(os.path.join(OUTPUT_DIR, 'nodes_features.csv'), index=False)

# --- 4. 处理 Periods (E4) ---
print("处理 Periods...")
period_nodes = []

for _, row in df_periods.iterrows():
    p_name = clean_str(row['时期名称'])
    if not p_name: continue
    
    p_uuid = get_id("period", f"{row['site_id']}_{p_name}")
    
    period_nodes.append({
        "id:ID": p_uuid,
        "name": p_name,
        "start_date": clean_str(row.get('起始时间', '')),
        "end_date": clean_str(row.get('结束时间', '')),
        ":LABEL": "E4_Period"
    })
    
    # 关系: Period -> Site (P7 took place at)
    if row['site_id'] in site_id_map:
        edges_hierarchy.append({
            ":START_ID": p_uuid,
            ":END_ID": site_id_map[row['site_id']],
            ":TYPE": "P7_took_place_at"
        })

pd.DataFrame(period_nodes).drop_duplicates('id:ID').to_csv(os.path.join(OUTPUT_DIR, 'nodes_periods.csv'), index=False)

# 保存层级关系
pd.DataFrame(edges_hierarchy).drop_duplicates().to_csv(os.path.join(OUTPUT_DIR, 'edges_hierarchy.csv'), index=False)


# --- 5. 处理 Artifacts (E22) ---
print("处理 Artifacts (Pottery & Jade)...")

artifact_nodes = []
concept_nodes = [] # 收集 Type, Material
edges_art_core = [] # Loc, Period
edges_art_attr = [] # Type, Material

# 辅助函数：处理单个 Artifact 行
def process_artifact(row, category_label):
    code = clean_str(row['文物编号'])
    if not code: return
    
    art_uuid = get_id("obj", code)
    
    # 1. 节点
    artifact_nodes.append({
        "id:ID": art_uuid,
        "name": code,
        "category": category_label,
        "height:float": row.get('高度(cm)', ''),
        "diameter:float": row.get('口径(cm)', '') if '口径(cm)' in row else row.get('直径(cm)', ''),
        ":LABEL": "E22_Man_Made_Object"
    })
    
    # 2. 关系: 出土位置 (P53)
    # 优先用 '出土单位', 其次 '出土墓葬'
    loc_name = clean_str(row.get('出土单位')) or clean_str(row.get('出土墓葬'))
    site_ref = str(row['site_id']) if pd.notna(row.get('site_id')) else None
    
    if loc_name and site_ref:
        # 尝试匹配结构 ID
        key = (site_ref, loc_name)
        if key in struct_map:
            edges_art_core.append({
                ":START_ID": art_uuid,
                ":END_ID": struct_map[key],
                ":TYPE": "P53_has_former_or_current_location"
            })
        else:
            # 如果找不到对应的 Structure 节点，是否要创建临时节点？
            # 暂略，实际项目中可能需要自动补全
            pass
            
    # 3. 关系: 类型 (P2) - E55
    # 陶器用 '器型', 玉器用 '一级分类'/'二级分类'
    type_vals = []
    if '器型' in row: type_vals.append(clean_str(row['器型']))
    if '一级分类' in row: type_vals.append(clean_str(row['一级分类']))
    if '二级分类' in row: type_vals.append(clean_str(row['二级分类']))
    if '纹饰类型' in row: type_vals.append(clean_str(row['纹饰类型'])) # 陶器纹饰
    if '纹饰主题' in row: type_vals.append(clean_str(row['纹饰主题'])) # 玉器纹饰
    
    for t_val in type_vals:
        if t_val and t_val not in ['nan', '']:
            t_uuid = get_id("type", t_val)
            concept_nodes.append({
                "id:ID": t_uuid,
                "name": t_val,
                "concept_type": "Type",
                ":LABEL": "E55_Type"
            })
            edges_art_attr.append({
                ":START_ID": art_uuid,
                ":END_ID": t_uuid,
                ":TYPE": "P2_has_type"
            })
            
    # 4. 关系: 材质 (P45) - E57
    # 陶器 '陶土类型', 玉器 '玉料类型'
    mat_val = clean_str(row.get('陶土类型')) or clean_str(row.get('玉料类型'))
    if mat_val:
        m_uuid = get_id("mat", mat_val)
        concept_nodes.append({
            "id:ID": m_uuid,
            "name": mat_val,
            "concept_type": "Material",
            ":LABEL": "E57_Material"
        })
        edges_art_attr.append({
            ":START_ID": art_uuid,
            ":END_ID": m_uuid,
            ":TYPE": "P45_consists_of"
        })
        
    # 5. 关系: 工艺 (P108 -> P32) - 简化为直接 P32 关联或 P2 关联
    # 为了简化图谱，这里暂时将工艺也作为 E55 Type 挂载
    tech_val = clean_str(row.get('成型工艺')) or clean_str(row.get('工艺单元'))
    if tech_val:
        tech_uuid = get_id("tech", tech_val)
        concept_nodes.append({
            "id:ID": tech_uuid,
            "name": tech_val,
            "concept_type": "Technique",
            ":LABEL": "E55_Type"
        })
        # 注意：标准 CIDOC 应通过 E12 节点，这里简化为直接关联
        edges_art_attr.append({
            ":START_ID": art_uuid,
            ":END_ID": tech_uuid,
            ":TYPE": "P2_has_type" # 或自定义 P32_used_technique (需扩展Schema)
        })

# 遍历陶器
print("  - 处理陶器数据...")
for _, row in df_pottery.iterrows():
    process_artifact(row, "Pottery")

# 遍历玉器
print("  - 处理玉器数据...")
for _, row in df_jade.iterrows():
    process_artifact(row, "Jade")

# 保存 Artifacts 相关文件
print("保存文物节点和关系...")
pd.DataFrame(artifact_nodes).drop_duplicates('id:ID').to_csv(os.path.join(OUTPUT_DIR, 'nodes_artifacts.csv'), index=False)
pd.DataFrame(concept_nodes).drop_duplicates('id:ID').to_csv(os.path.join(OUTPUT_DIR, 'nodes_concepts.csv'), index=False)
pd.DataFrame(edges_art_core).drop_duplicates().to_csv(os.path.join(OUTPUT_DIR, 'edges_artifact_core.csv'), index=False)
pd.DataFrame(edges_art_attr).drop_duplicates().to_csv(os.path.join(OUTPUT_DIR, 'edges_artifact_attributes.csv'), index=False)

print(f"全部处理完成！输出文件位于: {OUTPUT_DIR}")

