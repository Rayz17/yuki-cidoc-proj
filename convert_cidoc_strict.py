import pandas as pd
import os
import hashlib
import glob

# ================= 配置区 =================
BASE_DIR = "for-neo4j"
DEFINITIONS_FILE = os.path.join(BASE_DIR, "cidoc-kg-def3.csv")
DATA_FILES = {
    "pottery": os.path.join(BASE_DIR, "pottery_artifacts_export_20251203.csv"),
    "jade": os.path.join(BASE_DIR, "jade_artifacts_export_20251203.csv"),
    "sites": os.path.join(BASE_DIR, "sites_export_20251203.csv"),
    "structures": os.path.join(BASE_DIR, "site_structures_export_20251203.csv"),
    "periods": os.path.join(BASE_DIR, "periods_export_20251203.csv")
}
OUTPUT_DIR = "neo4j_cidoc_import"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ================= 辅助函数 =================
def clean_label(text):
    """清理CIDOC类名，转为Neo4j Label格式"""
    if not isinstance(text, str): return "Unknown"
    # 处理 E22 Man-Made Object -> E22_ManMade_Object
    return text.replace(" ", "_").replace("-", "").split("(")[0].strip()

def clean_rel(text):
    """清理关系名"""
    if not isinstance(text, str): return "RELATED_TO"
    return text.split("(")[0].strip().replace(" ", "_").replace("-", "_")

def get_uid(prefix, val):
    """生成唯一ID"""
    if pd.isna(val): return f"{prefix}_unknown"
    return f"{prefix}_{hashlib.md5(str(val).encode()).hexdigest()[0:10]}"

# ================= 1. 加载并解析定义表 =================
print("正在解析 CIDOC 定义表...")
df_def = pd.read_csv(DEFINITIONS_FILE)

mapping_rules = {}

for _, row in df_def.iterrows():
    art_type = row['文物类型']
    field_cn = row['抽取属性：文化特征单元']
    
    if pd.isna(art_type) or pd.isna(field_cn):
        continue
        
    inter_class = row['中间类 (Class)']
    is_direct = pd.isna(inter_class) or inter_class == 'N/A'
    
    rule = {
        'domain': clean_label(row['核心实体（Domain）']),
        'rel1': clean_rel(row['关系 (Property)']),
        'inter_class': None if is_direct else clean_label(inter_class),
        'rel2': clean_rel(row['子属性 (Sub-Property)']) if not is_direct else None,
        'range_class': clean_label(row['目标类 (Range Class)'])
    }
    mapping_rules[(art_type, field_cn)] = rule

print(f"✅ 解析了 {len(mapping_rules)} 条映射规则")

# ================= 2. 初始化数据容器 =================
nodes_storage = {} 
rels_storage = []

def add_node(label, uid, props={}):
    if label not in nodes_storage:
        nodes_storage[label] = {}
    if uid not in nodes_storage[label]:
        nodes_storage[label][uid] = {'id': uid}
    # 更新属性，保留已有值
    nodes_storage[label][uid].update(props)

def add_rel(start_id, end_id, rel_type):
    rels_storage.append({
        ':START_ID': start_id,
        ':END_ID': end_id,
        ':TYPE': rel_type
    })

# ================= 3. 处理基础数据 =================

# --- Site ---
print("处理 Site 数据...")
if os.path.exists(DATA_FILES['sites']):
    df_sites = pd.read_csv(DATA_FILES['sites'])
    for _, row in df_sites.iterrows():
        uid = f"Site_{row['ID']}"
        add_node("E27_Site", uid, {
            'name': row['遗址名称'], 
            'type': row['遗址类型'],
            'location': row['地理位置'],
            'description': row.get('遗址描述', '')
        })

# --- Period ---
print("处理 Period 数据...")
if os.path.exists(DATA_FILES['periods']):
    df_periods = pd.read_csv(DATA_FILES['periods'])
    for _, row in df_periods.iterrows():
        uid = f"Period_{row['ID']}"
        add_node("E4_Period", uid, {
            'name': row['时期名称'],
            'date': row['绝对年代']
        })
        # 关联到 Site
        if pd.notna(row['site_id']):
            add_rel(uid, f"Site_{int(row['site_id'])}", "P7_took_place_at")
            
        # 时序关系 (简单处理：同一遗址内按 ID 或顺序字段排序)
        # 这里暂不实现复杂逻辑，重点在实体生成

# --- Structure ---
print("处理 Structure 数据...")
if os.path.exists(DATA_FILES['structures']):
    df_structs = pd.read_csv(DATA_FILES['structures'])
    for _, row in df_structs.iterrows():
        uid = f"Structure_{row['id']}"
        add_node("E25_ManMade_Feature", uid, {
            'name': row['structure_name'],
            'type': row['structure_type'],
            'description': row.get('description', '')
        })
        # 关联 Site
        if pd.notna(row['site_id']):
            add_rel(uid, f"Site_{int(row['site_id'])}", "P53_has_former_or_current_location")
        # 关联 Parent
        if pd.notna(row['parent_id']):
            add_rel(uid, f"Structure_{int(row['parent_id'])}", "P46i_forms_part_of")

# ================= 4. 处理文物数据 (核心逻辑) =================

for artifact_type_key, csv_path in [('陶器', DATA_FILES['pottery']), ('玉器', DATA_FILES['jade'])]:
    if not os.path.exists(csv_path):
        print(f"⚠️ 文件不存在: {csv_path}")
        continue
        
    print(f"处理 {artifact_type_key} 数据...")
    df = pd.read_csv(csv_path)
    
    for _, row in df.iterrows():
        # 1. 核心节点 E22
        art_uid = f"Artifact_{artifact_type_key}_{row['ID']}"
        art_label = "E22_ManMade_Object"
        
        # 尝试获取尺寸描述
        desc = row.get('尺寸描述', '')
        if pd.isna(desc): desc = ''
        
        add_node(art_label, art_uid, {
            'code': row['文物编号'],
            'category': artifact_type_key,
            'description': desc
        })
        
        # 2. 基础关联 (Site/Structure/Period)
        if pd.notna(row.get('site_id')):
            add_rel(art_uid, f"Site_{int(row['site_id'])}", "P53_has_former_or_current_location")
        if pd.notna(row.get('structure_id')):
            add_rel(art_uid, f"Structure_{int(row['structure_id'])}", "P53_has_former_or_current_location")
        if pd.notna(row.get('period_id')):
            # 文物 -> 生产事件 -> 时期
            prod_uid = f"Production_{art_uid}"
            add_node("E12_Production", prod_uid, {'label': 'Production Event'})
            add_rel(art_uid, prod_uid, "P108_was_produced_by")
            add_rel(prod_uid, f"Period_{int(row['period_id'])}", "P4_has_time_span")

        # 3. 动态属性映射
        for col_name, value in row.items():
            if pd.isna(value) or value == '': continue
            
            rule = mapping_rules.get((artifact_type_key, col_name))
            if not rule: continue
            
            range_label = rule['range_class']
            # 清理 Value (去除两端空格)
            val_str = str(value).strip()
            
            # 生成目标节点 ID
            # 逻辑：Type/Material 是共享概念节点；Dimension/Production 是私有实例节点
            if 'Type' in range_label or 'Material' in range_label:
                target_uid = get_uid(range_label, val_str)
                add_node(range_label, target_uid, {'name': val_str})
            elif 'Dimension' in range_label:
                target_uid = f"{range_label}_{art_uid}_{col_name}"
                add_node(range_label, target_uid, {'value': val_str, 'metric': col_name})
            else:
                target_uid = f"{range_label}_{art_uid}" # 默认私有
                add_node(range_label, target_uid, {'label': range_label})

            # 建立路径
            if rule['inter_class']:
                inter_label = rule['inter_class']
                
                # 中间节点 ID 策略
                if 'Production' in inter_label:
                    inter_uid = f"{inter_label}_{art_uid}" # 复用
                    add_node(inter_label, inter_uid, {'label': 'Production'})
                elif 'Material' in inter_label:
                    inter_uid = f"{inter_label}_{art_uid}"
                    add_node(inter_label, inter_uid, {'label': 'Material Constituent'})
                else:
                    inter_uid = f"{inter_label}_{art_uid}_{col_name}"
                    add_node(inter_label, inter_uid, {})
                
                add_rel(art_uid, inter_uid, rule['rel1'])
                
                # 第二跳
                rel2 = rule['rel2'] if rule['rel2'] else "P2_has_type"
                add_rel(inter_uid, target_uid, rel2)
            else:
                # 直接关联
                add_rel(art_uid, target_uid, rule['rel1'])

# ================= 5. 导出 CSV =================
print(f"正在导出 CSV 到 {OUTPUT_DIR}...")

# 导出节点
node_files = []
for label, nodes in nodes_storage.items():
    data = []
    for uid, props in nodes.items():
        row = props.copy()
        row['id:ID'] = uid
        row[':LABEL'] = label
        data.append(row)
    
    if not data: continue
    
    df_out = pd.DataFrame(data)
    # 调整列顺序
    cols = ['id:ID', ':LABEL'] + [c for c in df_out.columns if c not in ['id:ID', ':LABEL']]
    df_out = df_out[cols]
    
    filename = f"nodes_{label}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)
    df_out.to_csv(filepath, index=False)
    node_files.append(filename)

# 导出关系
if rels_storage:
    df_rels = pd.DataFrame(rels_storage)
    rel_file = "relationships.csv"
    df_rels.to_csv(os.path.join(OUTPUT_DIR, rel_file), index=False)
    print(f"✅ 关系文件生成: {rel_file} ({len(rels_storage)} 条)")
else:
    print("⚠️ 没有生成任何关系数据")

print(f"✅ 节点文件生成: {len(node_files)} 个")

# ================= 6. 生成导入命令 =================
cmd = "./bin/neo4j-admin database import full \\\n"
for nf in node_files:
    cmd += f"    --nodes=import/{nf} \\\n"
cmd += "    --relationships=import/relationships.csv \\\n"
cmd += "    --overwrite-destination neo4j"

print("\n=== Neo4j 导入命令 ===")
print(cmd)
print("======================")

# 保存命令到文件
with open(os.path.join(OUTPUT_DIR, "import_command.sh"), "w") as f:
    f.write(cmd)

