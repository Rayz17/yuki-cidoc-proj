import pandas as pd
import hashlib
import os
import sys

"""
V5 ETL 脚本

依据：
- NEO4J_IMPLEMENTATION_V5.md
- CIDOC_FEATURE_FIELD_MAPPING_V5.md
- for-neo4j/cidoc-kg-def4.csv

输出：
- 继承 V4 的节点/关系 CSV（Site/Place/Feature/Artifact/Production/Period/Concept）
- 新增 FeatureUnit / FeatureMetric / FeatureValue 节点及其关系 CSV
- 生成 import_script_v5.cypher
"""


INPUT_DIR = "for-neo4j"
OUTPUT_DIR = "neo4j_import_v5"

FILE_SITES = os.path.join(INPUT_DIR, "sites_export_20251203.csv")
FILE_STRUCTURES = os.path.join(INPUT_DIR, "site_structures_export_20251203.csv")
FILE_PERIODS = os.path.join(INPUT_DIR, "periods_export_20251203.csv")
FILE_POTTERY = os.path.join(INPUT_DIR, "pottery_artifacts_export_20251203.csv")
FILE_JADE = os.path.join(INPUT_DIR, "jade_artifacts_export_20251203.csv")
FILE_DEF4 = os.path.join(INPUT_DIR, "cidoc-kg-def4.csv")


if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

print(f"开始处理数据 (V5 - 属性扩展版)... 输出目录: {OUTPUT_DIR}")


# --------- 工具函数 ---------

def get_id(prefix, *parts):
    """基于多个字段生成稳定的短 Hash ID"""
    valid = [str(p).strip() for p in parts if pd.notna(p) and str(p).strip() != ""]
    if not valid:
        return None
    raw = "_".join(valid)
    return f"{prefix}_{hashlib.md5(raw.encode('utf-8')).hexdigest()[:8]}"


def clean_str(val):
    if pd.isna(val):
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none") else s


def norm_domain(domain: str) -> str:
    """从 'E22 Man-Made Object' 提取 'E22'"""
    if not isinstance(domain, str):
        return ""
    return domain.strip().split()[0]


def property_code(prop: str) -> str:
    """从 'P45 consists of (由...组成)' 提取 'P45'"""
    if not isinstance(prop, str):
        return ""
    return prop.strip().split()[0]


PROPERTY_TYPE_MAP = {
    "P2": "P2_has_type",
    "P45": "P45_consists_of",
    "P43": "P43_has_dimension",
    "P103": "P103_was_intended_for",
    "P65": "P65_shows_visual_item",
    "P44": "P44_has_condition",
    "P108": "P108_was_produced_by",
    "P108i": "P108i_was_produced_by",
    "P4": "P4_has_time_span",
    "P7": "P7_took_place_at",
    "P14": "P14_carried_out_by",
    "P1": "P1_is_identified_by",
    "P53": "P53_has_former_or_current_location",
    "P106": "P106_was_found_by",
}


def map_property_to_type(prop: str) -> str:
    code = property_code(prop)
    return PROPERTY_TYPE_MAP.get(code, code)


# --------- 读取基础数据 ---------

print("加载 CSV 数据...")
try:
    df_sites = pd.read_csv(FILE_SITES)
    df_structs = pd.read_csv(FILE_STRUCTURES)
    df_periods = pd.read_csv(FILE_PERIODS)
    df_pottery = pd.read_csv(FILE_POTTERY)
    df_jade = pd.read_csv(FILE_JADE)
    df_def4 = pd.read_csv(FILE_DEF4)
except Exception as e:
    print("读取文件失败:", e)
    sys.exit(1)


# --------- V4 主干结构的节点/关系缓存（简化版） ---------

nodes_site = []
nodes_place = []
nodes_feature = []
nodes_artifact = []
nodes_period = []
nodes_production = []
nodes_concept = []  # E55/E57 等

edges_spatial = []     # P46 / P89
edges_period = []      # P7
edges_prod_link = []   # artifact -> production (P108i)
edges_prod_attr = []   # production -> technique / timespan / period
edges_obj_loc = []     # artifact -> feature (P53)
edges_obj_attr = []    # artifact -> material/type 等

site_id_map = {}
struct_id_map = {}
struct_name_map = {}

concept_seen = set()


def add_concept(name: str, label: str) -> str:
    """为 E55/E57 概念去重建节点"""
    name = clean_str(name)
    if not name:
        return None
    prefix = "type" if label == "E55_Type" else "mat"
    cid = get_id(prefix, name)
    if cid in concept_seen:
        return cid
    nodes_concept.append({"id:ID": cid, "name": name, ":LABEL": label})
    concept_seen.add(cid)
    return cid


# --------- FeatureUnit / Metric / Value 结构 ---------

nodes_fu = []   # FeatureUnit
nodes_fm = []   # FeatureMetric
nodes_fv = []   # FeatureValue

edges_fu_structure = []  # metric -> unit
edges_fu_links = []      # artifact -> unit/metric
edges_fu_values = []     # unit/metric -> value

fu_map = {}  # (domain, unit_name) -> fu_id
fm_map = {}  # (domain, unit_name, metric_name) -> fm_id
fv_seen = set()


def ensure_feature_unit(domain: str, unit_name: str, rule=None) -> str:
    key = (domain, unit_name)
    if key in fu_map:
        return fu_map[key]
    fu_id = get_id("fu", domain, unit_name)
    record = {
        "id:ID": fu_id,
        "name": unit_name,
        "domain": domain,
        ":LABEL": "FeatureUnit",
    }
    if rule:
        record["cidoc_domain"] = rule.get("cidoc_domain", "")
        record["cidoc_property"] = rule.get("property", "")
        record["cidoc_intermediate"] = rule.get("intermediate", "")
        record["cidoc_range"] = rule.get("range", "")
    nodes_fu.append(record)
    fu_map[key] = fu_id
    return fu_id


def ensure_feature_metric(domain: str, unit_name: str, metric_name: str, rule=None) -> str:
    if not metric_name:
        return None
    fu_id = ensure_feature_unit(domain, unit_name, rule)
    key = (domain, unit_name, metric_name)
    if key in fm_map:
        return fm_map[key]
    fm_id = get_id("fm", domain, unit_name, metric_name)
    nodes_fm.append({
        "id:ID": fm_id,
        "name": metric_name,
        ":LABEL": "FeatureMetric",
    })
    edges_fu_structure.append({
        ":START_ID": fm_id,
        ":END_ID": fu_id,
        ":TYPE": "HAS_METRIC_OF",
    })
    fm_map[key] = fm_id
    return fm_id


def ensure_feature_value(start_id: str, raw_value: str, numeric=None, unit: str = "") -> str:
    raw = clean_str(raw_value)
    vid = get_id("fv", start_id, raw)
    if vid in fv_seen:
        # 仍然需要记录边
        edges_fu_values.append({
            ":START_ID": start_id,
            ":END_ID": vid,
        })
        return vid
    nodes_fv.append({
        "id:ID": vid,
        "raw": raw,
        "numeric": numeric if numeric is not None else "",
        "unit": unit,
        ":LABEL": "FeatureValue",
    })
    edges_fu_values.append({
        ":START_ID": start_id,
        ":END_ID": vid,
    })
    fv_seen.add(vid)
    return vid


# --------- def4 规则映射 & 字段映射（根据 CIDOC_FEATURE_FIELD_MAPPING_V5） ---------

print("解析 def4 规则...")

unit_rules = {}  # (domain_short, feature_unit_name) -> rule dict

for _, row in df_def4.iterrows():
    domain_label = norm_domain(clean_str(row["核心实体（Domain）"]))
    unit = clean_str(row["抽取属性：文化特征单元"])
    if not domain_label or not unit:
        continue
    unit_rules[(domain_label, unit)] = {
        "cidoc_domain": domain_label,
        "property": clean_str(row["关系 (Property)"]),
        "intermediate": clean_str(row["中间类 (Class)"]),
        "sub_property": clean_str(row["子属性 (Sub-Property)"]),
        "range": clean_str(row["目标类 (Range Class)"]),
    }


# 字段到特征单元的静态映射，来源：CIDOC_FEATURE_FIELD_MAPPING_V5.md

FIELD_MAP = {
    "pottery": {
        "陶土类型": ("陶土种类", None),
        "纯洁度": ("陶土纯洁程度", None),
        "细腻度": ("陶土细腻程度", None),
        "掺杂物": ("掺杂物", None),
        "硬度": ("硬度", None),
        "烧成温度": ("烧成温度", None),
        "器型": ("基本器型", None),
        "subtype_level1": ("基本器型", "subtype_level1"),
        "subtype_level2": ("基本器型", "subtype_level2"),
        "subtype_level3": ("基本器型", "subtype_level3"),
        "basic_shape": ("基本器型", "basic_shape"),
        "器型特征": ("器型部位特征", None),
        "器物组合": ("器物组合", None),
        "尺寸描述": ("基本尺寸", "尺寸描述"),
        "量度信息": ("基本尺寸", "量度信息"),
        "高度(cm)": ("量度信息", "高度(cm)"),
        "口径(cm)": ("量度信息", "口径(cm)"),
        "厚度(cm)": ("量度信息", "厚度(cm)"),
        "功能": ("器物功能", None),
        "成型工艺": ("成型工艺", None),
        "修整技术": ("修整技术", None),
        "装饰手法": ("装饰手法", None),
        "纹饰类型": ("纹饰类型", None),
        "制作活动": ("制作活动", None),
        "制作者": ("制作者", None),
        "制作年代": ("制作年代", None),
        "制作地点": ("制作地点", None),
        "excavation_activity": ("发掘活动", None),
        "原始出土地点": ("原始出土地点", "原始出土地点"),
        "出土区域": ("原始出土地点", "出土区域"),
        "出土单位": ("原始出土地点", "出土单位"),
        "出土层位": ("原始出土地点", "出土层位"),
        "出土墓葬": ("原始出土地点", "出土墓葬"),
        "颜色": ("颜色", None),
        "保存状况": ("保存状况", None),
        "完整程度": ("完整程度", None),
    },
    "jade": {
        "器型单元": ("器型单元", None),
        "一级分类": ("器型单元", "一级分类"),
        "二级分类": ("器型单元", "二级分类"),
        "三级分类": ("器型单元", "三级分类"),
        "纹饰单元": ("纹饰单元", None),
        "纹饰主题": ("纹饰单元", "纹饰主题"),
        "decoration_description": ("纹饰单元", "纹饰描述"),
        "工艺单元": ("工艺特征单元", None),
        "切割工艺": ("工艺特征单元", "切割工艺"),
        "钻孔工艺": ("工艺特征单元", "钻孔工艺"),
        "雕刻工艺": ("工艺特征单元", "雕刻工艺"),
        "decoration_craft": ("工艺特征单元", "装饰工艺"),
        "production_technique": ("工艺特征单元", "production_technique"),
        "玉料类型": ("材质单元", None),
        "玉料颜色": ("材质单元", "玉料颜色"),
        "玉料质地": ("材质单元", "玉料质地"),
        "transparency": ("材质单元", "transparency"),
        "沁色/表面": ("沁色单元", None),
        "尺寸描述": ("量度信息", "尺寸描述"),
        "量度信息": ("量度信息", "量度信息"),
        "长度(cm)": ("量度信息", "长度(cm)"),
        "宽度(cm)": ("量度信息", "宽度(cm)"),
        "厚度(cm)": ("量度信息", "厚度(cm)"),
        "高度(cm)": ("量度信息", "高度(cm)"),
        "直径(cm)": ("量度信息", "直径(cm)"),
        "孔径(cm)": ("量度信息", "孔径(cm)"),
        "重量(g)": ("量度信息", "重量(g)"),
        "原始出土地点": ("原始出土地点", "原始出土地点"),
        "出土区域": ("原始出土地点", "出土区域"),
        "出土单位": ("原始出土地点", "出土单位"),
        "出土层位": ("原始出土地点", "出土层位"),
        "出土墓葬": ("原始出土地点", "出土墓葬"),
        "制作活动": ("制作活动", None),
        "制作者": ("制作者", None),
        "制作年代": ("制作年代", None),
        "制作地点": ("制作地点", None),
        "excavation_activity": ("发掘活动", None),
        "shape_description": ("整体形态描述", "shape_description"),
        "整体形态": ("整体形态描述", "整体形态"),
        "功能": ("器物功能", "功能"),
        "使用方式": ("器物功能", "使用方式"),
        "保存状况": ("保存状况", None),
        "完整程度": ("完整程度", None),
    },
    "sites": {
        "遗址名称": ("遗址名称", None),
        "site_alias": ("遗址名称", "site_alias"),
        "遗址类型": ("遗址类型", None),
        "地理位置": ("遗址当前位置", None),
        "地理坐标": ("遗址空间数据", "地理坐标"),
        "空间数据": ("遗址空间数据", "空间数据"),
        "海拔": ("遗址空间数据", "海拔"),
        "总面积": ("遗址空间数据", "总面积"),
        "发掘面积": ("遗址空间数据", "发掘面积"),
        "遗址描述": ("遗址描述", None),
        "文化名称": ("文化名称", None),
        "绝对年代": ("遗址绝对年代", None),
        "保存状况": ("保存状况", None),
    },
    "periods": {
        "时期名称": ("时期/期别", None),
        "时期别名": ("时期/期别", "时期别名"),
        "细分时期": ("细分时期划分", None),
        "历史朝代": ("历史背景朝代", None),
        "地层归属": ("物理地层归属", None),
        "绝对年代": ("绝对年代", None),
        "起始时间": ("绝对年代", "起始时间"),
        "结束时间": ("绝对年代", "结束时间"),
        "发展阶段": ("发展阶段", None),
        "时期顺序": ("时期顺序", None),
        "时期特征": ("发展阶段", "时期特征"),
        "代表性文物": ("发展阶段", "代表性文物"),
    },
}


def get_rule(domain_label: str, unit_name: str):
    return unit_rules.get((domain_label, unit_name))


def emit_attribute_graph_only(domain_label: str, artifact_id: str, unit_name: str, metric_name: str, raw_value: str):
    rule = get_rule(domain_label, unit_name)
    fu_id = ensure_feature_unit(domain_label, unit_name, rule)
    # artifact -> FeatureUnit
    edges_fu_links.append({
        ":START_ID": artifact_id,
        ":END_ID": fu_id,
        ":TYPE": "HAS_FEATURE",
    })
    start_id = fu_id
    if metric_name:
        fm_id = ensure_feature_metric(domain_label, unit_name, metric_name, rule)
        edges_fu_links.append({
            ":START_ID": artifact_id,
            ":END_ID": fm_id,
            ":TYPE": "HAS_METRIC",
        })
        start_id = fm_id
    # 值节点
    try:
        num = float(str(raw_value))
    except Exception:
        num = None
    ensure_feature_value(start_id, raw_value, numeric=num)


def emit_by_rule(domain_label: str, artifact_id: str, prod_id: str, unit_name: str, metric_name: str, raw_value: str, rule: dict):
    """
    在属性图基础上，根据 def4 规则生成 CIDOC 节点与关系。
    这里只实现对 pottery/jade 中最常用的几类属性的映射：
    - P2 + E55
    - P45 + E57
    - P43 + E54
    - P108/E12 + P32/E55
    """
    # 先生成 Attribute Graph
    emit_attribute_graph_only(domain_label, artifact_id, unit_name, metric_name, raw_value)

    prop_code = property_code(rule.get("property", ""))
    rng = rule.get("range", "")
    value = clean_str(raw_value)
    if not value:
        return

    # 无中间类：直接属性 (E22 -> E55/E57)
    if not rule.get("intermediate"):
        if rng.startswith("E55"):
            cid = add_concept(value, "E55_Type")
        elif rng.startswith("E57"):
            cid = add_concept(value, "E57_Material")
        else:
            cid = None
        if not cid:
            return
        rel_type = map_property_to_type(rule.get("property", ""))
        edges_obj_attr.append({
            ":START_ID": artifact_id,
            ":END_ID": cid,
            ":TYPE": rel_type,
        })
        return

    # 有中间类：根据 intermediate class 做特别处理
    inter = rule["intermediate"]
    if inter.startswith("E12"):  # Production 相关，如烧成温度/工艺
        if not prod_id:
            return
        # 工艺类 -> E55_Type
        if rng.startswith("E55"):
            cid = add_concept(value, "E55_Type")
            rel_type = rule.get("sub_property") or "P32 used general technique"
            rel_type = map_property_to_type(rel_type)
            edges_prod_attr.append({
                ":START_ID": prod_id,
                ":END_ID": cid,
                ":TYPE": rel_type,
            })
    elif inter.startswith("E54"):  # Dimension
        # 创建 E54_Dimension
        try:
            num = float(str(raw_value))
        except Exception:
            num = None
        dim_id = get_id("dim", artifact_id, unit_name, metric_name or "")
        nodes_concept.append({
            "id:ID": dim_id,
            "name": unit_name if not metric_name else f"{unit_name}:{metric_name}",
            "value": raw_value,
            ":LABEL": "E54_Dimension",
        })
        edges_obj_attr.append({
            ":START_ID": artifact_id,
            ":END_ID": dim_id,
            ":TYPE": "P43_has_dimension",
        })
    # 其它 intermediate（如 E52/E3/E7）这里先不自动生成，后续可按需要扩展。


def apply_cidoc_and_feature_units(table_name: str, domain_label: str, artifact_id: str, prod_id: str, row: pd.Series):
    """对单行数据应用字段到特征单元及 CIDOC 规则"""
    fmap = FIELD_MAP.get(table_name, {})
    for col_name, value in row.items():
        if pd.isna(value) or str(value).strip() == "":
            continue
        if col_name not in fmap:
            continue
        unit_name, metric_name = fmap[col_name]
        rule = get_rule(domain_label, unit_name)
        if rule:
            emit_by_rule(domain_label, artifact_id, prod_id, unit_name, metric_name, value, rule)
            else:
            emit_attribute_graph_only(domain_label, artifact_id, unit_name, metric_name, value)


# --------- 构建 Sites / Structures / Periods / Artifacts / Productions (V4 主干的简化实现) ---------

print("构建 Sites/Places/Features...")

for _, row in df_sites.iterrows():
    sid = get_id("site", row["ID"])
    nodes_site.append({
        "id:ID": sid,
        "name": clean_str(row["遗址名称"]),
        "location": clean_str(row.get("地理位置", "")),
        ":LABEL": "E27_Site",
    })
    site_id_map[row["ID"]] = sid

# structures -> E53/E25 逻辑与 V4 类似（但这里只用于空间拓扑和出土关系）
for _, row in df_structs.iterrows():
    raw_id = row["id"]
    name = clean_str(row["structure_name"])
    stype = clean_str(row["structure_type"])
    site_ref = row["site_id"]
    if not name:
                continue
    is_region = False
    if stype in ["墓地", "发掘区", "居住区", "祭祀区", "区域", "探方"]:
        is_region = True
    elif "区" in name and "区" not in ["灰坑", "房址"]:
        is_region = True
    uid = get_id("struct", site_ref, name)
    struct_id_map[raw_id] = {"uid": uid, "is_region": is_region, "site_ref": site_ref}
    struct_name_map[(str(site_ref), name)] = uid
    if is_region:
        nodes_place.append({"id:ID": uid, "name": name, "type": stype, ":LABEL": "E53_Place"})
    else:
        nodes_feature.append({"id:ID": uid, "name": name, "type": stype, "code": name, ":LABEL": "E25_Man_Made_Feature"})
    if pd.isna(row.get("parent_id")) and site_ref in site_id_map:
        edges_spatial.append({":START_ID": site_id_map[site_ref], ":END_ID": uid, ":TYPE": "P46_is_composed_of"})

# structures second pass: parent-child
for _, row in df_structs.iterrows():
    child_raw_id = row["id"]
    parent_raw_id = row.get("parent_id")
    if pd.isna(parent_raw_id):
                continue
    if parent_raw_id not in struct_id_map:
                continue
    child_info = struct_id_map[child_raw_id]
    parent_info = struct_id_map[parent_raw_id]
    if parent_info["is_region"] and not child_info["is_region"]:
        edges_spatial.append({
        ":START_ID": child_info["uid"],
        ":END_ID": parent_info["uid"],
        ":TYPE": "P89_falls_within",
    })
            else:
        edges_spatial.append({
        ":START_ID": parent_info["uid"],
        ":END_ID": child_info["uid"],
        ":TYPE": "P46_is_composed_of",
    })

for s_info in struct_id_map.values():
    if not s_info["is_region"] and s_info["site_ref"] in site_id_map:
        edges_spatial.append({
        ":START_ID": s_info["uid"],
        ":END_ID": site_id_map[s_info["site_ref"]],
        ":TYPE": "P89_falls_within",
    })

print("构建 Periods...")

period_id_map = {}
for _, row in df_periods.iterrows():
    name = clean_str(row["时期名称"])
        if not name:
            continue
    pid = get_id("period", name)
    if pid not in period_id_map:
        nodes_period.append({
            "id:ID": pid,
            "name": name,
            "start_date": clean_str(row.get("起始时间", "")),
            "end_date": clean_str(row.get("结束时间", "")),
            ":LABEL": "E4_Period",
        })
        period_id_map[name] = pid
    if row["site_id"] in site_id_map:
        edges_period.append({
            ":START_ID": pid,
            ":END_ID": site_id_map[row["site_id"]],
            ":TYPE": "P7_took_place_at",
        })


# --------- Artifacts + Production + FeatureUnits 映射 ---------

print("构建 Pottery Artifacts ...")

artifact_prod_map = {}  # artifact_id -> production_id


def process_artifact_row(row: pd.Series, table_name: str, category_label: str):
    site_ref = str(row["site_id"]) if pd.notna(row.get("site_id")) else "unknown"
    code = clean_str(row["文物编号"])
    if not code:
        return
    aid = get_id("obj", site_ref, code)
    nodes_artifact.append({
        "id:ID": aid,
        "name": code,
        "category": category_label,
        "height:float": row.get("高度(cm)", ""),
        ":LABEL": "E22_Man_Made_Object",
    })
    # 出土位置
    loc_name = clean_str(row.get("出土单位")) or clean_str(row.get("出土墓葬")) or clean_str(row.get("原始出土地点"))
    if loc_name and site_ref:
        key = (site_ref, loc_name)
        if key in struct_name_map:
            edges_obj_loc.append({
                ":START_ID": aid,
                ":END_ID": struct_name_map[key],
                ":TYPE": "P53_has_former_or_current_location",
            })
    # 生产事件
    prod_id = get_id("prod", aid)
    nodes_production.append({
        "id:ID": prod_id,
        "note": f"Production of {code}",
        ":LABEL": "E12_Production",
    })
    edges_prod_link.append({
        ":START_ID": aid,
        ":END_ID": prod_id,
        ":TYPE": "P108i_was_produced_by",
    })
    artifact_prod_map[aid] = prod_id
    # 基本材质/器型（直接用已有列）
    if table_name == "pottery":
        mat = clean_str(row.get("陶土类型"))
            else:
        mat = clean_str(row.get("玉料类型"))
    if mat:
        mid = add_concept(mat, "E57_Material")
        edges_obj_attr.append({":START_ID": aid, ":END_ID": mid, ":TYPE": "P45_consists_of"})
    if table_name == "pottery":
        tval = clean_str(row.get("器型"))
    else:
        tval = clean_str(row.get("器型单元"))
    if tval:
        tid = add_concept(tval, "E55_Type")
        edges_obj_attr.append({":START_ID": aid, ":END_ID": tid, ":TYPE": "P2_has_type"})
    # 应用文化特征单元映射
    domain_label = "E22"
    apply_cidoc_and_feature_units(table_name, domain_label, aid, prod_id, row)


for _, row in df_pottery.iterrows():
    process_artifact_row(row, "pottery", "Pottery")

print("构建 Jade Artifacts ...")

for _, row in df_jade.iterrows():
    process_artifact_row(row, "jade", "Jade")


# --------- 导出 CSV ---------

print("写入 CSV 文件...")


def write_csv(data, filename):
    if not data:
        return
    df = pd.DataFrame(data)

    def _norm_col(c: str) -> str:
        if c.startswith(":"):
            return c[1:]
        parts = c.split(":")
        return parts[0] if parts[0] else c

    df = df.rename(columns={c: _norm_col(c) for c in df.columns})
    path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(path, index=False)
    return list(df.columns)


write_csv(nodes_site, "nodes_site.csv")
write_csv(nodes_place, "nodes_place.csv")
write_csv(nodes_feature, "nodes_feature.csv")
write_csv(nodes_period, "nodes_period.csv")
write_csv(nodes_artifact, "nodes_artifact.csv")
write_csv(nodes_production, "nodes_production.csv")
write_csv(nodes_concept, "nodes_concept.csv")

write_csv(edges_spatial, "edges_spatial.csv")
write_csv(edges_period, "edges_period.csv")
write_csv(edges_obj_loc, "edges_obj_loc.csv")
write_csv(edges_obj_attr, "edges_obj_attr.csv")
write_csv(edges_prod_link, "edges_prod_link.csv")
write_csv(edges_prod_attr, "edges_prod_attr.csv")

write_csv(nodes_fu, "nodes_feature_units.csv")
write_csv(nodes_fm, "nodes_feature_metrics.csv")
write_csv(nodes_fv, "nodes_feature_values.csv")
write_csv(edges_fu_structure, "edges_feature_structure.csv")
write_csv(edges_fu_links, "edges_feature_links.csv")
write_csv(edges_fu_values, "edges_feature_values.csv")


# --------- 生成 Cypher 导入脚本 ---------

print("生成 import_script_v5.cypher ...")

base_url = "https://raw.githubusercontent.com/Rayz17/yuki-cidoc-proj/main/neo4j_import_v5"

cypher = f"""
// V5 Import Script (CIDOC + Feature Units)

// 1. 约束
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E27_Site) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E53_Place) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E25_Man_Made_Feature) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E22_Man_Made_Object) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E4_Period) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E12_Production) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E55_Type) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:E57_Material) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:FeatureUnit) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:FeatureMetric) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:FeatureValue) REQUIRE n.id IS UNIQUE;

// 2. 节点
LOAD CSV WITH HEADERS FROM '{base_url}/nodes_site.csv' AS row
MERGE (n:E27_Site {{id: row.id}})
SET n.name = row.name, n.location = row.location;

LOAD CSV WITH HEADERS FROM '{base_url}/nodes_place.csv' AS row
MERGE (n:E53_Place {{id: row.id}})
SET n.name = row.name, n.type = row.type;

LOAD CSV WITH HEADERS FROM '{base_url}/nodes_feature.csv' AS row
MERGE (n:E25_Man_Made_Feature {{id: row.id}})
SET n.name = row.name, n.code = row.code, n.type = row.type;

LOAD CSV WITH HEADERS FROM '{base_url}/nodes_period.csv' AS row
MERGE (n:E4_Period {{id: row.id}})
SET n.name = row.name, n.start_date = row.start_date, n.end_date = row.end_date;

LOAD CSV WITH HEADERS FROM '{base_url}/nodes_artifact.csv' AS row
MERGE (n:E22_Man_Made_Object {{id: row.id}})
SET n.name = row.name, n.category = row.category, n.height = toFloat(row.height);

LOAD CSV WITH HEADERS FROM '{base_url}/nodes_production.csv' AS row
MERGE (n:E12_Production {{id: row.id}})
SET n.note = row.note;

LOAD CSV WITH HEADERS FROM '{base_url}/nodes_concept.csv' AS row
CALL apoc.create.node([row.LABEL], {{id: row.id, name: row.name}}) YIELD node
RETURN count(node);

LOAD CSV WITH HEADERS FROM '{base_url}/nodes_feature_units.csv' AS row
MERGE (u:FeatureUnit {{id: row.id}})
SET u.name = row.name,
    u.domain = row.domain,
    u.cidoc_domain = row.cidoc_domain,
    u.cidoc_property = row.cidoc_property,
    u.cidoc_intermediate = row.cidoc_intermediate,
    u.cidoc_range = row.cidoc_range;

LOAD CSV WITH HEADERS FROM '{base_url}/nodes_feature_metrics.csv' AS row
MERGE (m:FeatureMetric {{id: row.id}})
SET m.name = row.name;

LOAD CSV WITH HEADERS FROM '{base_url}/nodes_feature_values.csv' AS row
MERGE (v:FeatureValue {{id: row.id}})
SET v.raw = row.raw,
    v.numeric = toFloat(row.numeric),
    v.unit = row.unit;

// 3. 关系
LOAD CSV WITH HEADERS FROM '{base_url}/edges_spatial.csv' AS row
MATCH (s {{id: row.START_ID}}) MATCH (e {{id: row.END_ID}})
CALL apoc.create.relationship(s, row.TYPE, {{}}, e) YIELD rel RETURN count(rel);

LOAD CSV WITH HEADERS FROM '{base_url}/edges_period.csv' AS row
MATCH (s:E4_Period {{id: row.START_ID}}) MATCH (e:E27_Site {{id: row.END_ID}})
MERGE (s)-[:P7_took_place_at]->(e);

LOAD CSV WITH HEADERS FROM '{base_url}/edges_obj_loc.csv' AS row
MATCH (s:E22_Man_Made_Object {{id: row.START_ID}}) MATCH (e:E25_Man_Made_Feature {{id: row.END_ID}})
MERGE (s)-[:P53_has_former_or_current_location]->(e);

LOAD CSV WITH HEADERS FROM '{base_url}/edges_obj_attr.csv' AS row
MATCH (s:E22_Man_Made_Object {{id: row.START_ID}}) MATCH (e {{id: row.END_ID}})
CALL apoc.create.relationship(s, row.TYPE, {{}}, e) YIELD rel RETURN count(rel);

LOAD CSV WITH HEADERS FROM '{base_url}/edges_prod_link.csv' AS row
MATCH (s:E22_Man_Made_Object {{id: row.START_ID}}) MATCH (e:E12_Production {{id: row.END_ID}})
MERGE (s)-[:P108i_was_produced_by]->(e);

LOAD CSV WITH HEADERS FROM '{base_url}/edges_prod_attr.csv' AS row
MATCH (s:E12_Production {{id: row.START_ID}}) MATCH (e {{id: row.END_ID}})
CALL apoc.create.relationship(s, row.TYPE, {{}}, e) YIELD rel RETURN count(rel);

LOAD CSV WITH HEADERS FROM '{base_url}/edges_feature_structure.csv' AS row
MATCH (m:FeatureMetric {{id: row.START_ID}}) MATCH (u:FeatureUnit {{id: row.END_ID}})
MERGE (m)-[:HAS_METRIC_OF]->(u);

LOAD CSV WITH HEADERS FROM '{base_url}/edges_feature_links.csv' AS row
MATCH (s:E22_Man_Made_Object {{id: row.START_ID}}) MATCH (t {{id: row.END_ID}})
CALL apoc.create.relationship(s, row.TYPE, {{}}, t) YIELD rel RETURN count(rel);

LOAD CSV WITH HEADERS FROM '{base_url}/edges_feature_values.csv' AS row
MATCH (s {{id: row.START_ID}}) MATCH (v:FeatureValue {{id: row.END_ID}})
MERGE (s)-[:HAS_VALUE]->(v);
"""

with open(os.path.join(OUTPUT_DIR, "import_script_v5.cypher"), "w", encoding="utf-8") as f:
    f.write(cypher)

print("V5 转换完成。")

