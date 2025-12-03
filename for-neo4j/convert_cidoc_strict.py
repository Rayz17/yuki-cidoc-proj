"""
严格遵循 cidoc-kg-def3.csv 的 CIDOC-CRM 映射规则，
将项目导出的 CSV 数据转换为 Neo4j 可导入的节点 / 关系 CSV。

输出目录：neo4j_cidoc_import/
"""

import os
import re
import hashlib
from typing import Dict, Any, Tuple

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOR_NEO4J_DIR = os.path.join(BASE_DIR, "for-neo4j")

DEFINITIONS_FILE = os.path.join(FOR_NEO4J_DIR, "cidoc-kg-def3.csv")

DATA_FILES = {
    "陶器": os.path.join(FOR_NEO4J_DIR, "pottery_artifacts_export_20251203.csv"),
    "玉器": os.path.join(FOR_NEO4J_DIR, "jade_artifacts_export_20251203.csv"),
    "遗址": os.path.join(FOR_NEO4J_DIR, "sites_export_20251203.csv"),
    "时期": os.path.join(FOR_NEO4J_DIR, "periods_export_20251203.csv"),
}

STRUCTURES_FILE = os.path.join(FOR_NEO4J_DIR, "site_structures_export_20251203.csv")

OUTPUT_DIR = os.path.join(BASE_DIR, "neo4j_cidoc_import")


# ========= 工具函数 =========

def clean_label(text: Any) -> str:
    """清理 CIDOC 类名，如 'E22 Man-Made Object' -> 'E22_ManMade_Object'"""
    if not isinstance(text, str):
        return "Unknown"
    s = text.strip()
    # 去掉括号中的中文说明
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("-", "")
    parts = s.split()
    if not parts:
        return "Unknown"
    code = parts[0]
    rest = "".join(parts[1:])
    return f"{code}_{rest}" if rest else code


def clean_rel(text: Any) -> str:
    """清理关系名，如 'P45 consists of (由...组成)' -> 'P45_consists_of'"""
    if not isinstance(text, str):
        return ""
    s = text.strip()
    # 去掉 LaTeX / $ / \text{ }
    s = s.replace("\\text", "")
    s = s.replace("{", "").replace("}", "").replace("$", "")
    # 只取中文括号前面的英文部分
    s = s.split("（")[0].split("(")[0].strip()
    m = re.match(r"(P\d+)\s*(.*)", s)
    if not m:
        return s.replace(" ", "_")
    pid, rest = m.groups()
    rest = rest.strip()
    if not rest:
        return pid
    rest = rest.replace(" ", "_")
    return f"{pid}_{rest}"


def get_uid(prefix: str, value: Any) -> str:
    """根据前缀和原始值生成稳定的字符串 ID"""
    h = hashlib.md5(str(value).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{h}"


# ========= 映射规则解析 =========

def load_mapping_rules() -> Dict[Tuple[str, str], Dict[str, Any]]:
    """
    加载 cidoc-kg-def3.csv，生成：
    (文物类型, 字段中文名) -> { domain, rel1, inter_class, rel2, range_class }
    """
    if not os.path.exists(DEFINITIONS_FILE):
        raise FileNotFoundError(f"缺少定义文件: {DEFINITIONS_FILE}")

    df_def = pd.read_csv(DEFINITIONS_FILE)
    rules: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for _, row in df_def.iterrows():
        art_type = str(row.get("文物类型", "")).strip()
        field_cn = str(row.get("抽取属性：文化特征单元", "")).strip()
        if not art_type or not field_cn or field_cn == "nan":
            continue

        domain_raw = row.get("核心实体（Domain）", "")
        prop_raw = row.get("关系 (Property)", "")
        inter_raw = row.get("中间类 (Class)", "")
        subprop_raw = row.get("子属性 (Sub-Property)", "")
        range_raw = row.get("目标类 (Range Class)", "")

        domain = clean_label(domain_raw)
        rel1 = clean_rel(prop_raw)
        inter_class = None
        rel2 = None
        if isinstance(inter_raw, str) and inter_raw.strip() and inter_raw.strip() != "N/A":
            inter_class = clean_label(inter_raw)
            rel2 = clean_rel(subprop_raw) if isinstance(subprop_raw, str) else ""
        range_class = clean_label(range_raw)

        rules[(art_type, field_cn)] = {
            "domain": domain,
            "rel1": rel1,
            "inter_class": inter_class,
            "rel2": rel2,
            "range_class": range_class,
        }

    print(f"✅ 已解析映射规则 {len(rules)} 条")
    return rules


# ========= 节点 / 关系 存储结构 =========

class GraphBuilder:
    def __init__(self) -> None:
        # label -> id -> props
        self.nodes: Dict[str, Dict[str, Dict[str, Any]]] = {}
        # list of relations
        self.rels: list[Dict[str, str]] = []

    def add_node(self, label: str, uid: str, props: Dict[str, Any] | None = None) -> None:
        if label not in self.nodes:
            self.nodes[label] = {}
        if uid not in self.nodes[label]:
            self.nodes[label][uid] = {"id": uid}
        if props:
            # 不覆盖已有键
            for k, v in props.items():
                if v is None or v == "" or v != v:  # NaN
                    continue
                if k not in self.nodes[label][uid]:
                    self.nodes[label][uid][k] = v

    def add_rel(self, start_id: str, end_id: str, rel_type: str) -> None:
        if not start_id or not end_id or not rel_type:
            return
        self.rels.append(
            {
                ":START_ID": start_id,
                ":END_ID": end_id,
                ":TYPE": rel_type,
            }
        )

    # ===== 导出 =====
    def export(self, output_dir: str) -> None:
        os.makedirs(output_dir, exist_ok=True)

        # 节点
        for label, table in self.nodes.items():
            if not table:
                continue
            # 汇总所有字段
            keys = set()
            for props in table.values():
                keys.update(props.keys())
            keys.discard("id")
            cols = ["id:ID", ":LABEL"] + sorted(keys)
            rows = []
            for uid, props in table.items():
                row = {"id:ID": uid, ":LABEL": label}
                for k in keys:
                    if k in props:
                        row[k] = props[k]
                rows.append(row)
            df = pd.DataFrame(rows, columns=cols)
            path = os.path.join(output_dir, f"nodes_{label}.csv")
            df.to_csv(path, index=False, encoding="utf-8-sig")

        # 关系
        if self.rels:
            df_rels = pd.DataFrame(self.rels, columns=[":START_ID", ":END_ID", ":TYPE"])
            df_rels.to_csv(os.path.join(output_dir, "relationships.csv"), index=False, encoding="utf-8-sig")


# ========= 主处理流程 =========

def build_graph() -> None:
    print("📥 加载 CIDOC 定义表...")
    rules = load_mapping_rules()
    g = GraphBuilder()

    # ------- 遗址 (E27_Site) -------
    print("📦 处理遗址数据 (E27_Site)...")
    sites_path = DATA_FILES.get("遗址")
    if sites_path and os.path.exists(sites_path):
        df_sites = pd.read_csv(sites_path)
        for _, row in df_sites.iterrows():
            site_uid = f"Site_{int(row['ID'])}"
            g.add_node("E27_Site", site_uid, {
                "name": row.get("遗址名称"),
                "type": row.get("遗址类型"),
                "location": row.get("地理位置"),
            })

    # ------- 遗址结构 (E25_ManMade_Feature) -------
    if os.path.exists(STRUCTURES_FILE):
        print("📦 处理遗址结构 (E25_ManMade_Feature)...")
        df_struct = pd.read_csv(STRUCTURES_FILE)
        for _, row in df_struct.iterrows():
            sid = int(row["id"])
            struct_uid = f"Structure_{sid}"
            g.add_node("E25_ManMade_Feature", struct_uid, {
                "name": row.get("structure_name"),
                "type": row.get("structure_type"),
                "description": row.get("description"),
            })
            # 结构 -> 遗址 : P53_has_former_or_current_location
            if "site_id" in row and not pd.isna(row["site_id"]):
                site_uid = f"Site_{int(row['site_id'])}"
                g.add_rel(struct_uid, site_uid, "P53_has_former_or_current_location")
            # 结构层级：子结构 -> 父结构
            if "parent_id" in row and not pd.isna(row["parent_id"]):
                parent_uid = f"Structure_{int(row['parent_id'])}"
                g.add_rel(struct_uid, parent_uid, "P46i_forms_part_of")

    # ------- 时期 (E4_Period) -------
    print("📦 处理时期数据 (E4_Period)...")
    periods_path = DATA_FILES.get("时期")
    if periods_path and os.path.exists(periods_path):
        df_periods = pd.read_csv(periods_path)
        for _, row in df_periods.iterrows():
            pid = int(row["ID"])
            period_uid = f"Period_{pid}"
            g.add_node("E4_Period", period_uid, {
                "name": row.get("时期名称"),
                "absolute_date": row.get("绝对年代"),
                "development_stage": row.get("发展阶段"),
            })
            # P7_took_place_at -> Site
            if "site_id" in row and not pd.isna(row["site_id"]):
                site_uid = f"Site_{int(row['site_id'])}"
                g.add_rel(period_uid, site_uid, "P7_took_place_at")

        # 按 site_id + 时序 建立 P120_occurs_before
        if "site_id" in df_periods.columns and "时期顺序" in df_periods.columns:
            for site_id, grp in df_periods.groupby("site_id"):
                try:
                    grp_sorted = grp.sort_values("时期顺序")
                except KeyError:
                    continue
                ids = [int(x) for x in grp_sorted["ID"].tolist()]
                for a, b in zip(ids, ids[1:]):
                    g.add_rel(f"Period_{a}", f"Period_{b}", "P120_occurs_before")

    # ------- 文物（陶器 / 玉器） E22_ManMade_Object -------
    def process_artifacts(art_type_key: str, csv_path: str) -> None:
        if not os.path.exists(csv_path):
            return
        print(f"📦 处理 {art_type_key} 文物 (E22_ManMade_Object)...")
        df = pd.read_csv(csv_path)

        for _, row in df.iterrows():
            rid = row.get("ID")
            if pd.isna(rid):
                continue
            art_uid = f"Artifact_{art_type_key}_{int(rid)}"
            code = row.get("文物编号") or row.get("artifact_code")
            g.add_node("E22_ManMade_Object", art_uid, {
                "code": code,
                "category": art_type_key,
                "description": row.get("尺寸描述") or row.get("description"),
            })

            # 出土结构 / 遗址 基础拓扑（非 CIDOC 定义表，利于导航）
            if "structure_id" in row and not pd.isna(row["structure_id"]):
                struct_uid = f"Structure_{int(row['structure_id'])}"
                g.add_rel(art_uid, struct_uid, "P53_has_former_or_current_location")
            elif "出土墓葬" in row and isinstance(row["出土墓葬"], str):
                # 如果结构表中的名称与“出土墓葬”一致，可在后续单独补充映射逻辑
                pass

            # === 根据 cidoc-kg-def3 规则生成语义路径 ===
            for col_name, value in row.items():
                if value is None or value == "" or value != value:
                    continue
                key = (art_type_key, str(col_name).strip())
                rule = rules.get(key)
                if not rule:
                    continue

                range_label = rule["range_class"]

                # 目标节点 ID 策略
                if "E55" in range_label:
                    # 类型概念：全球共享
                    target_uid = get_uid(range_label, value)
                    g.add_node(range_label, target_uid, {"name": value})
                elif "E57" in range_label:
                    # 材质对象：每件文物一个
                    target_uid = f"{range_label}_{art_uid}_{col_name}"
                    g.add_node(range_label, target_uid, {"name": value})
                elif "E54" in range_label:
                    # 量度：每件文物 + 指标 唯一
                    target_uid = f"{range_label}_{art_uid}_{col_name}"
                    g.add_node(range_label, target_uid, {
                        "value": value,
                        "metric": col_name,
                    })
                elif "E12" in range_label:
                    # 某些规则可能直接指向 E12 事件
                    target_uid = f"{range_label}_{art_uid}"
                    g.add_node(range_label, target_uid, {"name": "Production"})
                else:
                    target_uid = f"{range_label}_{art_uid}_{col_name}"
                    g.add_node(range_label, target_uid, {"value": value})

                inter_class = rule["inter_class"]
                rel1 = rule["rel1"]
                rel2 = rule["rel2"]

                if inter_class:
                    # 中间类节点
                    if "E12" in inter_class:
                        inter_uid = f"{inter_class}_{art_uid}"
                        g.add_node(inter_class, inter_uid, {"name": "Production"})
                    elif "E57" in inter_class:
                        inter_uid = f"{inter_class}_{art_uid}"
                        g.add_node(inter_class, inter_uid, {"name": "Material"})
                    else:
                        inter_uid = f"{inter_class}_{art_uid}_{col_name}"
                        g.add_node(inter_class, inter_uid, {})

                    # E22 -> 中间类
                    g.add_rel(art_uid, inter_uid, rel1)
                    # 中间类 -> 目标类
                    if rel2:
                        g.add_rel(inter_uid, target_uid, rel2)
                    else:
                        g.add_rel(inter_uid, target_uid, "P2_has_type")
                else:
                    # 直接关系
                    g.add_rel(art_uid, target_uid, rel1)

    # 分别处理陶器、玉器
    for art_type, path in [("陶器", DATA_FILES["陶器"]), ("玉器", DATA_FILES["玉器"])]:
        process_artifacts(art_type, path)

    # TODO: 遗址 / 时期字段也可以通过 rules 进行进一步丰富，这里先实现文物部分的完整路径。

    # 导出
    print("📤 正在导出 CSV 文件...")
    g.export(OUTPUT_DIR)
    print(f"✅ 完成，结果已写入: {OUTPUT_DIR}")


if __name__ == "__main__":
    build_graph()


