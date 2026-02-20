import pandas as pd
import hashlib
import os
import sys

# 配置
INPUT_DIR = 'for-neo4j'
OUTPUT_DIR = 'neo4j_import_v4'

# 输入文件
FILE_SITES = os.path.join(INPUT_DIR, 'sites_export_20251203.csv')
FILE_STRUCTURES = os.path.join(INPUT_DIR, 'site_structures_export_20251203.csv')
FILE_PERIODS = os.path.join(INPUT_DIR, 'periods_export_20251203.csv')
FILE_POTTERY = os.path.join(INPUT_DIR, 'pottery_artifacts_export_20251203.csv')
FILE_JADE = os.path.join(INPUT_DIR, 'jade_artifacts_export_20251203.csv')

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

print(f"开始处理数据 (V4 - 语义增强版)... 输出目录: {OUTPUT_DIR}")

# --- 工具函数 ---

def get_id(prefix, *parts):
    """生成复合键 Hash ID"""
    # 过滤空值
    valid_parts = [str(p).strip() for p in parts if pd.notna(p) and str(p).strip() != ""]
    if not valid_parts: return None
    
    raw = "_".join(valid_parts)
    return f"{prefix}_{hashlib.md5(raw.encode('utf-8')).hexdigest()[:8]}"

def clean_str(val):
    if pd.isna(val): return ""
    s = str(val).strip()
    return s if s.lower() != "nan" else ""

# --- 1. 加载数据 ---
print("正在加载 CSV 文件...")
try:
    df_sites = pd.read_csv(FILE_SITES)
    df_structs = pd.read_csv(FILE_STRUCTURES)
    df_periods = pd.read_csv(FILE_PERIODS)
    df_pottery = pd.read_csv(FILE_POTTERY)
    df_jade = pd.read_csv(FILE_JADE)
except Exception as e:
    print(f"读取文件失败: {e}")
    sys.exit(1)

# --- 全局存储 (用于生成 CSV) ---
# 节点列表: 字典列表
nodes_site = []
nodes_place = []
nodes_feature = []
nodes_artifact = []
nodes_period = []
nodes_production = [] # E12
nodes_concept = []    # E55/E57 (需去重)

# 关系列表
edges_spatial = []     # P46, P89
edges_period = []      # P7
edges_prod_link = []   # P108i (Object->Production)
edges_prod_attr = []   # P32, P4 (Production->Type/Period)
edges_obj_loc = []     # P53
edges_obj_attr = []    # P2, P45

# 辅助映射
site_id_map = {} # original_site_id -> node_id
struct_id_map = {} # original_struct_id -> {id, is_region, site_id}
struct_name_map = {} # (site_id, name) -> node_id (用于文物关联)
concept_set = set() # name -> id (去重)

def add_concept(name, label="E55_Type"):
    name = clean_str(name)
    if not name: return None
    cid = get_id("type" if label=="E55_Type" else "mat", name)
    
    if cid not in concept_set:
        nodes_concept.append({
            "id:ID": cid, "name": name, ":LABEL": label
        })
        concept_set.add(cid)
    return cid

# --- 2. 处理 Sites (E27) ---
print("构建 Sites...")
for _, row in df_sites.iterrows():
    sid = get_id("site", row['ID'])
    nodes_site.append({
        "id:ID": sid,
        "name": clean_str(row['遗址名称']),
        "location": clean_str(row.get('地理位置', '')),
        ":LABEL": "E27_Site"
    })
    site_id_map[row['ID']] = sid

# --- 3. 处理 Structures (E53/E25) & 空间层级 ---
print("构建 Spatial Hierarchy...")
# 第一次遍历：生成节点
for _, row in df_structs.iterrows():
    raw_id = row['id']
    name = clean_str(row['structure_name'])
    stype = clean_str(row['structure_type'])
    site_ref = row['site_id']
    
    if not name: continue
    
    # 区分 E53 vs E25 (GEMINI 逻辑)
    is_region = False
    if stype in ['墓地', '发掘区', '居住区', '祭祀区', '区域', '探方']:
        is_region = True
    elif '区' in name and '区' not in ['灰坑', '房址']: 
        is_region = True
        
    uid = get_id("struct", site_ref, name) # 复合ID
    
    # 记录映射
    struct_id_map[raw_id] = {'uid': uid, 'is_region': is_region, 'site_ref': site_ref}
    struct_name_map[(str(site_ref), name)] = uid
    
    if is_region:
        nodes_place.append({
            "id:ID": uid, "name": name, "type": stype, ":LABEL": "E53_Place"
        })
    else:
        nodes_feature.append({
            "id:ID": uid, "name": name, "type": stype, "code": name, ":LABEL": "E25_Man_Made_Feature"
        })
        
    # 建立 Site -> Structure (直连 P46，作为基础层级)
    # 注意：在V4中，我们主要依靠 parent_id 建立树，但为了保险（防止孤儿节点），
    # 如果没有 parent_id，则挂在 Site 下。
    if pd.isna(row.get('parent_id')) and site_ref in site_id_map:
        edges_spatial.append({
            ":START_ID": site_id_map[site_ref],
            ":END_ID": uid,
            ":TYPE": "P46_is_composed_of"
        })
        # 这里的逻辑是：顶层结构直接属于遗址。
        
# 第二次遍历：建立父子关系 (Strict Hierarchy)
for _, row in df_structs.iterrows():
    child_raw_id = row['id']
    parent_raw_id = row.get('parent_id')
    
    if pd.notna(parent_raw_id) and parent_raw_id in struct_id_map:
        child_info = struct_id_map.get(child_raw_id)
        parent_info = struct_id_map.get(parent_raw_id)
        
        if not child_info: continue
        
        # 逻辑：
        # 1. Place -> Place (P46)
        # 2. Place -> Feature (P46? P89?) -> CIDOC 推荐 P89 falls within (空间包含) 或 P46 composed of
        #    方案 V4 采用：若父为 Region 子为 Feature，用 P89。
        
        rel_type = "P46_is_composed_of" # 默认
        if parent_info['is_region'] and not child_info['is_region']:
            rel_type = "P89_falls_within" # 空间包含
            
        # 注意方向：CIDOC P89 是 Feature falls within Place (子 -> 父)
        # P46 是 Place composed of Place (父 -> 子)
        
        if rel_type == "P89_falls_within":
            edges_spatial.append({
                ":START_ID": child_info['uid'], # 子
                ":END_ID": parent_info['uid'],   # 父
                ":TYPE": "P89_falls_within"
            })
        else:
            edges_spatial.append({
                ":START_ID": parent_info['uid'], # 父
                ":END_ID": child_info['uid'],   # 子
                ":TYPE": "P46_is_composed_of"
            })

# 补充：Feature -> Site 的快捷路径 (P89)
for s_info in struct_id_map.values():
    if not s_info['is_region'] and s_info['site_ref'] in site_id_map:
        # 每一个 Feature 都位于其 Site 内
        edges_spatial.append({
            ":START_ID": s_info['uid'],
            ":END_ID": site_id_map[s_info['site_ref']],
            ":TYPE": "P89_falls_within"
        })

# --- 4. 处理 Periods (E4) ---
print("构建 Periods...")
for _, row in df_periods.iterrows():
    p_name = clean_str(row['时期名称'])
    if not p_name: continue
    
    # ID策略：Period是全库通用的概念，还是遗址特有的？
    # 通常"良渚文化"是通用的，但这里为了数据对应，还是带上 site_id 防止歧义，
    # 或者我们做一个全局 Period 映射？
    # V4 策略：基于 Name 做全局去重，如果不同遗址对同一时期的定义不同（如时间段不同），则保留独立节点。
    # 这里暂时按 (Name) 去重，忽略 site_id 差异，合并同名时期。
    
    pid = get_id("period", p_name) 
    # 检查是否已添加 (简单去重)
    exists = False
    for p in nodes_period:
        if p['id:ID'] == pid: exists = True; break
    
    if not exists:
        nodes_period.append({
            "id:ID": pid, "name": p_name, 
            "start_date": clean_str(row.get('起始时间', '')),
            "end_date": clean_str(row.get('结束时间', '')),
            ":LABEL": "E4_Period"
        })
    
    # 建立 Period -> Site (P7)
    if row['site_id'] in site_id_map:
        edges_period.append({
            ":START_ID": pid,
            ":END_ID": site_id_map[row['site_id']],
            ":TYPE": "P7_took_place_at"
        })

# --- 5. 处理 Artifacts & Events ---
print("构建 Artifacts & Production Events...")

def process_artifact(row, cat_label):
    code = clean_str(row['文物编号'])
    site_ref = str(row['site_id']) if pd.notna(row.get('site_id')) else "unknown"
    if not code: return

    # 1. Artifact Node
    aid = get_id("obj", site_ref, code) # 复合ID确保唯一
    nodes_artifact.append({
        "id:ID": aid, "name": code, "category": cat_label,
        "height:float": row.get('高度(cm)', ''),
        ":LABEL": "E22_Man_Made_Object"
    })
    
    # 2. Location (P53)
    loc_name = clean_str(row.get('出土单位')) or clean_str(row.get('出土墓葬'))
    if loc_name:
        # 查找 Structure ID
        key = (site_ref, loc_name)
        if key in struct_name_map:
            edges_obj_loc.append({
                ":START_ID": aid, ":END_ID": struct_name_map[key], ":TYPE": "P53_has_former_or_current_location"
            })
            
    # 3. Concepts (Type/Material) -> 直接属性关联 P2, P45
    # Type
    type_list = [row.get('器型'), row.get('一级分类'), row.get('纹饰类型'), row.get('纹饰主题')]
    for t in type_list:
        tid = add_concept(t, "E55_Type")
        if tid:
            edges_obj_attr.append({":START_ID": aid, ":END_ID": tid, ":TYPE": "P2_has_type"})
            
    # Material
    mat = row.get('陶土类型') or row.get('玉料类型')
    mid = add_concept(mat, "E57_Material")
    if mid:
        edges_obj_attr.append({":START_ID": aid, ":END_ID": mid, ":TYPE": "P45_consists_of"})
        
    # 4. Production Event (E12) - 语义增强核心
    # 每一个文物都对应一个生产事件
    prod_id = get_id("prod", aid)
    nodes_production.append({
        "id:ID": prod_id,
        "note": "Production of " + code,
        ":LABEL": "E12_Production"
    })
    # 关联 Object -> Production
    edges_prod_link.append({
        ":START_ID": aid, ":END_ID": prod_id, ":TYPE": "P108i_was_produced_by"
    })
    
    # 关联 Production -> Technique (P32)
    tech = row.get('成型工艺') or row.get('工艺单元')
    tech_id = add_concept(tech, "E55_Type")
    if tech_id:
        edges_prod_attr.append({
            ":START_ID": prod_id, ":END_ID": tech_id, ":TYPE": "P32_used_general_technique"
        })
        
    # 关联 Production -> Period (P4)
    # 如果文物表里没有直接的 Period 字段，通常通过 Site 或 Location 推断。
    # 但如果 CSV 里有 '制作年代' 或类似字段，可以利用。
    # 这里暂且略过，因为 Period 通常挂在 Site 上。如果需要，可以查找最近的 Period 节点。

# 运行处理
for _, row in df_pottery.iterrows(): process_artifact(row, "Pottery")
for _, row in df_jade.iterrows(): process_artifact(row, "Jade")

# --- 6. 导出 CSV (用于 neo4j-admin import 或 LOAD CSV) ---
print("写入 CSV 文件...")

# 为了方便 Cypher LOAD CSV，我们生成带Header的简单CSV
def write_csv(data, filename):
    if not data: return
    df = pd.DataFrame(data)
    # 确保列名符合 neo4j-admin import 规范 (id:ID, :LABEL 等)
    # 这里为了通用性，我们生成标准CSV，不带 neo4j-admin 的 type 标记，
    # 而是生成一个 import_script.cypher 来控制加载。
    
    # 清洗列名：
    # - 节点： "id:ID" -> "id"
    # - 关系： ":START_ID" -> "START_ID", ":END_ID" -> "END_ID", ":TYPE" -> "TYPE"
    def _norm_col(c: str) -> str:
        if c.startswith(':'):
            return c[1:]  # 去掉开头的冒号
        # 处理类似 "id:ID" 这种形式
        parts = c.split(':')
        return parts[0] if parts[0] else c

    clean_cols = {c: _norm_col(c) for c in df.columns}
    df = df.rename(columns=clean_cols)
    
    path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(path, index=False)
    return list(df.columns)

cols_site = write_csv(nodes_site, 'nodes_site.csv')
cols_place = write_csv(nodes_place, 'nodes_place.csv')
cols_feat = write_csv(nodes_feature, 'nodes_feature.csv')
cols_period = write_csv(nodes_period, 'nodes_period.csv')
cols_art = write_csv(nodes_artifact, 'nodes_artifact.csv')
cols_prod = write_csv(nodes_production, 'nodes_production.csv')
cols_concept = write_csv(nodes_concept, 'nodes_concept.csv')

write_csv(edges_spatial, 'edges_spatial.csv')
write_csv(edges_period, 'edges_period.csv')
write_csv(edges_obj_loc, 'edges_obj_loc.csv')
write_csv(edges_obj_attr, 'edges_obj_attr.csv')
write_csv(edges_prod_link, 'edges_prod_link.csv')
write_csv(edges_prod_attr, 'edges_prod_attr.csv')

# --- 7. 生成 Cypher Import Script ---
print("生成 import_script.cypher ...")

base_url = "https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v4"

cypher_script = f"""
// Neo4j V4 Import Script
// 建议使用 cypher-shell 运行: cat import_script.cypher | cypher-shell -u neo4j -p password
// 或者在 Neo4j Browser 中直接运行。注意：需确保 neo4j 配置了 dbms.security.allow_csv_import_from_file_urls=true

// 1. Indices (Added generic Entity index for performance)
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E27_Site) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E53_Place) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E25_Man_Made_Feature) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E22_Man_Made_Object) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E4_Period) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E12_Production) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E55_Type) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E57_Material) REQUIRE n.id IS UNIQUE;
// 全局索引，用于关系导入加速
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.id IS UNIQUE;

// 2. Nodes (Adding :Entity label to all nodes)
// 请逐条运行
LOAD CSV WITH HEADERS FROM '{{base_url}}/nodes_site.csv' AS row MERGE (n:E27_Site {{id: row.id}}) SET n:Entity, n.name=row.name, n.location=row.location;
LOAD CSV WITH HEADERS FROM '{{base_url}}/nodes_place.csv' AS row MERGE (n:E53_Place {{id: row.id}}) SET n:Entity, n.name=row.name, n.type=row.type;
LOAD CSV WITH HEADERS FROM '{{base_url}}/nodes_feature.csv' AS row MERGE (n:E25_Man_Made_Feature {{id: row.id}}) SET n:Entity, n.name=row.name, n.code=row.code, n.type=row.type;
LOAD CSV WITH HEADERS FROM '{{base_url}}/nodes_period.csv' AS row MERGE (n:E4_Period {{id: row.id}}) SET n:Entity, n.name=row.name, n.start_date=row.start_date;
LOAD CSV WITH HEADERS FROM '{{base_url}}/nodes_artifact.csv' AS row MERGE (n:E22_Man_Made_Object {{id: row.id}}) SET n:Entity, n.name=row.name, n.category=row.category, n.height=toFloat(row.height);
LOAD CSV WITH HEADERS FROM '{{base_url}}/nodes_production.csv' AS row MERGE (n:E12_Production {{id: row.id}}) SET n:Entity, n.note=row.note;
LOAD CSV WITH HEADERS FROM '{{base_url}}/nodes_concept.csv' AS row CALL apoc.create.node([row.LABEL, 'Entity'], {{id: row.id, name: row.name}}) YIELD node RETURN count(node);

// 3. Edges (Using :Entity index for matching)
LOAD CSV WITH HEADERS FROM '{{base_url}}/edges_spatial.csv' AS row MATCH (s:Entity {{id: row.START_ID}}) MATCH (e:Entity {{id: row.END_ID}}) CALL apoc.create.relationship(s, row.TYPE, {{}}, e) YIELD rel RETURN count(rel);
LOAD CSV WITH HEADERS FROM '{{base_url}}/edges_period.csv' AS row MATCH (s:Entity {{id: row.START_ID}}) MATCH (e:Entity {{id: row.END_ID}}) MERGE (s)-[:P7_took_place_at]->(e);
LOAD CSV WITH HEADERS FROM '{{base_url}}/edges_obj_loc.csv' AS row MATCH (s:Entity {{id: row.START_ID}}) MATCH (e:Entity {{id: row.END_ID}}) MERGE (s)-[:P53_has_former_or_current_location]->(e);
LOAD CSV WITH HEADERS FROM '{{base_url}}/edges_obj_attr.csv' AS row MATCH (s:Entity {{id: row.START_ID}}) MATCH (e:Entity {{id: row.END_ID}}) CALL apoc.create.relationship(s, row.TYPE, {{}}, e) YIELD rel RETURN count(rel);
LOAD CSV WITH HEADERS FROM '{{base_url}}/edges_prod_link.csv' AS row MATCH (s:Entity {{id: row.START_ID}}) MATCH (e:Entity {{id: row.END_ID}}) MERGE (s)-[:P108i_was_produced_by]->(e);
LOAD CSV WITH HEADERS FROM '{{base_url}}/edges_prod_attr.csv' AS row MATCH (s:Entity {{id: row.START_ID}}) MATCH (e:Entity {{id: row.END_ID}}) CALL apoc.create.relationship(s, row.TYPE, {{}}, e) YIELD rel RETURN count(rel);

"""

with open(os.path.join(OUTPUT_DIR, 'import_script.cypher'), 'w') as f:
    f.write(cypher_script)

print("完成！")
