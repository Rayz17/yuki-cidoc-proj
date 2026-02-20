# V5 文化特征单元 ↔ 数据表字段映射文档

本文件整理了 V5 方案中 5 个核心数据表与 `cidoc-kg-def4.csv` 中文化特征单元的对应关系，以及每个特征单元在数据表中的**一级字段**与**二级衍生字段**。  
这些映射将直接驱动后续的 `convert_to_graph_v5.py` ETL 代码生成 `FeatureUnit / FeatureMetric / FeatureValue` 节点与关系。

> 规则来源：`for-neo4j/cidoc-kg-def4.csv`  
> 数据来源：  
> - `for-neo4j/pottery_artifacts_export_20251203.csv`  
> - `for-neo4j/jade_artifacts_export_20251203.csv`  
> - `for-neo4j/sites_export_20251203.csv`  
> - `for-neo4j/site_structures_export_20251203.csv`  
> - `for-neo4j/periods_export_20251203.csv`

---

## 1. 陶器 (pottery_artifacts_export_20251203.csv)

### 1.1 来自 `cidoc-kg-def4.csv` 的陶器文化特征单元

> 文件：`for-neo4j/cidoc-kg-def4.csv`，行 2–24  
> Domain: `E22 Man-Made Object`，文物类型：陶器 pottery

| 行号 | 文化特征单元 | CIDOC 属性路径 (简写) |
| :--- | :--- | :--- |
| 2 | 陶土种类 | E22 -P45-> E57(Material) -P1-> E55(Type) |
| 3 | 陶土纯洁程度 | E22 -P2-> E55(Type) |
| 4 | 陶土细腻程度 | E22 -P2-> E55(Type) |
| 5 | 掺杂物 | E22 -P45-> E57(Material) |
| 6 | 硬度 | E22 -P43-> E54(Dimension) |
| 7 | 烧成温度 | E22 -P108/E12 -P32-> E55(Type) |
| 8 | 基本器型 | E22 -P2-> E55(Type) |
| 9 | 器型部位特征 | E22 -P46-> E26(Physical Feature) -P2-> E55(Type) |
| 10 | 器物组合 | E22 -P46-> E19(Physical Object) -P2-> E55(Type) |
| 11 | 基本尺寸 | E22 -P43-> E54(Dimension) (通高/口径/底径/腹径) |
| 12 | 器物功能 | E22 -P103-> E55(Type) |
| 13 | 成型工艺 | E22 -P108/E12 -P32-> E55(Type) |
| 14 | 修整技术 | E22 -P108/E12 -P32-> E55(Type) |
| 15 | 装饰手法 | E22 -P108/E12 -P32-> E55(Type) |
| 16 | 纹饰类型 | E22 -P65/E36 -P2-> E55(Type) |
| 17 | 人工物品编号 | E22 -P1-> E41(Appellation) |
| 18 | 制作活动 | E22 -P108-> E12(Production) |
| 19 | 制作者 | E22 -P14-> E39(Actor) |
| 20 | 制作年代 | E22 -P4-> E52(Time-Span) |
| 21 | 制作地点 | E22 -P7-> E53(Place) |
| 22 | 原始出土地点 | E22 -P53-> E25(Feature) |
| 23 | 发掘活动 | E22 -P106-> E7(Activity) |
| 24 | 量度信息 | E22 -P43-> E54(Dimension) (长/宽/高/重) |

### 1.2 CSV 字段与特征单元映射

> 数据表：`for-neo4j/pottery_artifacts_export_20251203.csv`  
> 关键字段（首行）：  
> `文物编号, 器型, subtype_level1, subtype_level2, subtype_level3, basic_shape, 原始出土地点, 出土区域, 出土单位, 出土层位, 出土墓葬, 陶土类型, 纯洁度, 细腻度, 掺杂物, 颜色, 硬度, 烧成温度, 器型特征, 器物组合, 尺寸描述, 量度信息, 高度(cm), 口径(cm), 厚度(cm), 功能, 成型工艺, 修整技术, surface_treatment, 装饰手法, 纹饰类型, 制作活动, 制作者, 制作年代, 制作地点, excavation_activity, 保存状况, 完整程度, ...`

| 文化特征单元 | 主字段 (一级 FeatureUnit) | 二级属性字段 (FeatureMetric) | 说明 |
| :--- | :--- | :--- | :--- |
| 陶土种类 | `陶土类型` | 无 | 直接存储泥质/夹砂等类型，可同时映射 E57_Material |
| 陶土纯洁程度 | `纯洁度` | 无 | 文本或枚举值，如“高”“中”等 |
| 陶土细腻程度 | `细腻度` | 无 | 文本或枚举值 |
| 掺杂物 | `掺杂物` | 无 | 描述添加的砂、云母、稻壳等 |
| 硬度 | `硬度` | *可选*：若后续有数值字段再拆出 | 目前仅文本等级，可作为 Type 或 Dimension 的 label |
| 烧成温度 | `烧成温度` | *可选*：数值字段若有 `℃` 拆为 value/unit | 映射到 E12 的工艺/温度信息 |
| 基本器型 | `器型`、`subtype_level1/2/3`、`basic_shape` | 无 | `器型` 为主；subtype 可附加到同一 FeatureUnit 下 |
| 器型部位特征 | `器型特征` | 无 | 描述口沿、肩部、腹部特征 |
| 器物组合 | `器物组合` | 无 | 如“鼎簋组合”等 |
| 基本尺寸 | `尺寸描述`、`量度信息` | `高度(cm)`、`口径(cm)`、`厚度(cm)` | 文本列为整体描述；数值列为二级 Metric，对应 E54_Dimension |
| 器物功能 | `功能` | 无 | 如“炊煮”、“盛储”等 |
| 成型工艺 | `成型工艺` | 无 | 泥条盘筑、轮制等 |
| 修整技术 | `修整技术` | 无 | 磨光、刮削等 |
| 装饰手法 | `装饰手法` | 无 | 刻划、彩绘、镂空、堆塑等 |
| 纹饰类型 | `纹饰类型` | 无 | 绳纹、几何纹、动物纹、弦纹等 |
| 人工物品编号 | `文物编号` | 无 | 直接作为 E22 的 `name/id` |
| 制作活动 | `制作活动` | 无 | 若留空，可由 LLM/规则填充 |
| 制作者 | `制作者` | 无 | 文本或人名 |
| 制作年代 | `制作年代` | *二级字段*：无（但可拆解为起止时间） | 可进一步由解析器拆分为 `start/end` 对应 E52 |
| 制作地点 | `制作地点` | 无 | 文本地点名称 |
| 原始出土地点 | `原始出土地点`、`出土区域`、`出土单位`、`出土层位`、`出土墓葬` | 无 | `出土单位/出土墓葬` 直接用于关联 E25 Feature；其余挂在 FeatureUnit 上 |
| 发掘活动 | `excavation_activity` | 无 | 对应 E7 活动名称 |
| 量度信息 | `量度信息` | 与“基本尺寸”同组的 `高度(cm), 口径(cm), 厚度(cm)` | 在属性图中可建独立 FeatureUnit“量度信息”，将各 Metric 挂在其下 |

> 备注：  
> - `颜色`、`保存状况`、`完整程度` 在 def4 中暂未声明为 CIDOC 映射，但在 V5 中仍会作为 FeatureUnit（仅走 Attribute Graph 路径）。  
> - 所有数值列（高度/口径/厚度等）都同时可映射为 `E54_Dimension`，并作为 `FeatureMetric` + `FeatureValue`。

---

## 2. 玉器 (jade_artifacts_export_20251203.csv)

### 2.1 来自 `cidoc-kg-def4.csv` 的玉器文化特征单元

> 文件：`for-neo4j/cidoc-kg-def4.csv`，行 25–40  
> Domain: `E22 Man-Made Object`，文物类型：玉器 jade

| 行号 | 文化特征单元 | CIDOC 属性路径 (简写) |
| :--- | :--- | :--- |
| 25 | 器型单元 | E22 -P2-> E55(Type) |
| 27 | 纹饰单元 | E22 -P65/E36 -P2-> E55(Type) |
| 28 | 工艺特征单元 | E22 -P108i/E12 -P32-> E55(Type) |
| 29 | 材质单元 | E22 -P45-> E57(Material) |
| 30 | 沁色单元 | E22 -P44/E3 -P2-> E55(Type) |
| 31 | 人工物品编号 | E22 -P1-> E41 |
| 32 | 量度信息 | E22 -P43-> E54(Dimension) |
| 33 | 原始出土地点 | E22 -P53-> E25(Feature) |
| 34 | 制作活动 | E22 -P108-> E12(Production) |
| 35 | 制作者 | E22 -P14-> E39(Actor) |
| 36 | 制作年代 | E22 -P4-> E52(Time-Span) |
| 37 | 制作地点 | E22 -P7-> E53(Place) |
| 38 | 发掘活动 | E22 -P106-> E7(Activity) |
| 39 | 整体形态描述 | E22 -P46/E26 -P2-> E55(Type) |
| 40 | 器物功能 | E22 -P103-> E55(Type) |

### 2.2 CSV 字段与特征单元映射

> 数据表：`for-neo4j/jade_artifacts_export_20251203.csv`  
> 关键字段（首行）：  
> `文物编号, 一级分类, 二级分类, 三级分类, 原始出土地点, 出土区域, 出土单位, 出土层位, 出土墓葬, 玉料类型, 玉料颜色, 玉料质地, transparency, 沁色/表面, 器型单元, shape_description, 整体形态, 纹饰单元, 纹饰主题, decoration_description, 工艺单元, 切割工艺, 钻孔工艺, 雕刻工艺, decoration_craft, production_technique, 尺寸描述, 量度信息, 长度(cm), 宽度(cm), 厚度(cm), 高度(cm), 直径(cm), 孔径(cm), 重量(g), 制作活动, 制作者, 制作年代, 制作地点, excavation_activity, 功能, 使用方式, 保存状况, 完整程度, ...`

| 文化特征单元 | 主字段 | 二级属性字段 | 说明 |
| :--- | :--- | :--- | :--- |
| 器型单元 | `器型单元`, `一级分类`, `二级分类`, `三级分类` | 无 | 器型层级可统一挂在同一 FeatureUnit 下 |
| 纹饰单元 | `纹饰单元` | `纹饰主题`, `decoration_description` | 主题与具体描述作为二级属性 |
| 工艺特征单元 | `工艺单元` | `切割工艺`, `钻孔工艺`, `雕刻工艺`, `decoration_craft`, `production_technique` | 多个二级字段描述不同工艺子单元 |
| 材质单元 | `玉料类型` | `玉料颜色`, `玉料质地`, `transparency` | 颜色/质地/透明度作为二级属性 |
| 沁色单元 | `沁色/表面` | 无 | 若后续细分可拆二级字段 |
| 人工物品编号 | `文物编号` | 无 | 直接作为 E22 的 `id/name` |
| 量度信息 | `尺寸描述`, `量度信息` | `长度(cm)`, `宽度(cm)`, `厚度(cm)`, `高度(cm)`, `直径(cm)`, `孔径(cm)`, `重量(g)` | 同时映射为 E54_Dimension 与 Metric+Value |
| 原始出土地点 | `原始出土地点`, `出土区域`, `出土单位`, `出土层位`, `出土墓葬` | 无 | 与陶器相同 |
| 制作活动 | `制作活动` | 无 | 文本活动名 |
| 制作者 | `制作者` | 无 | 文本人名 |
| 制作年代 | `制作年代` | 无（二级可以由解析拆分） | 可按需要解析为起止年 |
| 制作地点 | `制作地点` | 无 | 文本地点 |
| 发掘活动 | `excavation_activity` | 无 | 文本 |
| 整体形态描述 | `shape_description`, `整体形态` | 无 | 文字描述为特征单元自身的属性 |
| 器物功能 | `功能`, `使用方式` | 无 | 可在 FeatureUnit “器物功能” 下建两个二级属性 |

同样，`保存状况`、`完整程度` 虽然不在 def4 中定义为 CIDOC 特征，但在 V5 中也会作为独立的 FeatureUnit（仅属性图）。

---

## 3. 遗址 (sites_export_20251203.csv)

### 3.1 来自 def4 的遗址类特征单元

> 文件：`for-neo4j/cidoc-kg-def4.csv`，行 41–46  
> Domain: `E27 Site`

| 行号 | 文化特征单元 | CIDOC 属性路径 |
| :--- | :--- | :--- |
| 41 | 遗址名称 | E27 -P1-> E41(Appellation) |
| 42 | 遗址类型 | E27 -P2-> E55(Type) |
| 43 | 遗址当前位置 | E27 -P53-> E53(Place) |
| 44 | 遗址空间数据 | E27 -P53/E53 -P168-> E94(Space Primitive) |
| 45 | 遗址描述 | E27 -P3-> E62(String) |
| 46 | 遗址内子区域 | E27 -P46-> E53(Place) |

### 3.2 CSV 字段与特征单元映射

> 数据表：`for-neo4j/sites_export_20251203.csv`  
> 关键字段：`遗址名称, site_alias, 遗址类型, 地理位置, 地理坐标, 空间数据, 海拔, 总面积, 发掘面积, 文化名称, 绝对年代, 保护级别, 保存状况, 遗址描述, ...`

| 文化特征单元 | 主字段 | 二级属性字段 | 说明 |
| :--- | :--- | :--- | :--- |
| 遗址名称 | `遗址名称` | `site_alias` | 标准名称与别名 |
| 遗址类型 | `遗址类型` | 无 | 墓地/聚落等 |
| 遗址当前位置 | `地理位置` | 无 | 行政区位文字 |
| 遗址空间数据 | `地理坐标`, `空间数据` | `海拔`, `总面积`, `发掘面积` | 坐标/矢量数据 + 若干数值属性 |
| 遗址描述 | `遗址描述` | 无 | 长文本 |
| 遗址内子区域 | 不直接在此表中出现 | 来自 `raw_attributes` 中的 `site_sub_zone/sub_zone_name` 等 | 实际子区域与结构对应由 `site_structures` 表和 raw JSON 提供 |

此外，`文化名称`、`绝对年代` 可视为与 Period 相连的特征单元，将在 Periods 映射中体现。

---

## 4. 遗址结构 / 单位 (site_structures_export_20251203.csv)

### 4.1 相关特征单元

`cidoc-kg-def4.csv` 中与结构/单位直接相关的是：

- 行 49：  
  - Domain: `E53 Place`  
  - Property: `P89 falls within`  
  - Range: `E25 Man-Made Feature`  
  - 特征单元：子区域内具体单位
- 行 56：  
  - Domain: `E25 Man-Made Feature`  
  - Property: `P108i was produced by` + `E12 Production` + `P10 falls within` + `E4 Period`  
  - 特征单元：物理地层归属。

### 4.2 CSV 字段与特征单元映射

> 数据表：`for-neo4j/site_structures_export_20251203.csv`  
> 关键字段：`id, site_id, parent_id, structure_level, structure_code, structure_name, structure_type, relative_position, coordinates, length, width, depth, area, description, features, ...`

| 文化特征单元 | 主字段 | 二级属性字段 | 说明 |
| :--- | :--- | :--- | :--- |
| 子区域编号或名称 | `structure_name`, `structure_code` | 无 | 对应 def4 行 47（E44 Place Appellation） |
| 子区域位置描述 | `relative_position` | `coordinates`, `length`, `width`, `depth`, `area` | 位置/尺寸作为二级属性 |
| 子区域内具体单位 | `structure_type`（墓地/灰坑/房址/码头等） | `features`, `description` | 与空间拓扑(P46/P89) 共同描述结构类型 |
| 物理地层归属 | 暂无直接字段，在 Periods 表中通过 `地层归属` 引用结构 ID | 无 | 由 Periods→Feature 的交叉映射体现 |

在 V5 中，site_structures 表更多用于拓扑建模（E53/E25）与基本说明；若后续需要，也可以为 `structure_type/description/features` 各自建 FeatureUnit。

---

## 5. 时期 (periods_export_20251203.csv)

### 5.1 来自 def4 的 Period 特征单元

> 文件：`for-neo4j/cidoc-kg-def4.csv`，行 50–56  
> Domain: `E4 Period`

| 行号 | 文化特征单元 | CIDOC 路径 |
| :--- | :--- | :--- |
| 50 | 时期/期别 | E4 -P1-> E41(Appellation) |
| 51 | 发展阶段 | E4 -P7-> E27 Site |
| 52 | 绝对年代 | E4 -P4-> E52(Time-Span) |
| 53 | 历史背景朝代 | E4 -P10-> E4(朝代 Period) |
| 54 | 细分时期划分 | E4 -P9-> E4(子时期) |
| 55 | 时期顺序 | E4 -P120-> E4(后期) |
| 56 | 物理地层归属 | E25 Feature -P108i/E12 -P10-> E4 Period |

### 5.2 CSV 字段与特征单元映射

> 数据表：`for-neo4j/periods_export_20251203.csv`  
> 关键字段：`时期名称, 时期别名, 细分时期, 历史朝代, 地层归属, 起始时间, 结束时间, 绝对年代, 相对年代, 发展阶段, 时期顺序, 时期特征, 代表性文物, ...`

| 文化特征单元 | 主字段 | 二级属性字段 | 说明 |
| :--- | :--- | :--- | :--- |
| 时期/期别 | `时期名称` | `时期别名` | 名称与别名 |
| 发展阶段 | `发展阶段` | `时期特征`, `代表性文物` | 阶段说明与代表性描述 |
| 绝对年代 | `绝对年代` | `起始时间`, `结束时间` | 可解析为 E52 的 start/end |
| 历史背景朝代 | `历史朝代` | 无 | 文本，如“夏朝” |
| 细分时期划分 | `细分时期` | 无 | 如“盘龙城一期早段” |
| 时期顺序 | `时期顺序` | 无 | 数值/序列号，用于排序 |
| 物理地层归属 | `地层归属` | 无 | 指向结构/地层编码，可用于 Period–Feature 关联 |

---

## 6. 小结与后续步骤

1. 本文档已经为 **陶器、玉器、遗址、遗址结构、时期** 五大类，逐一给出了：
   - def4 中的文化特征单元；
   - 它们在各自 CSV 中的主字段与二级衍生字段；
   - 以及在 V5 模型中应对应的 `FeatureUnit / FeatureMetric` 设计。
2. 后续在编写 `convert_to_graph_v5.py` 时，可直接据此：
   - 生成 `field_to_unit[(table, column)] -> (feature_unit, sub_metric)` 映射；
   - 为每个 `(Domain, feature_unit)` 查找 def4 中的 CIDOC 路径（若存在），补充 CIDOC 语义；
   - 同时统一生成 Attribute Graph：`HAS_FEATURE / HAS_METRIC / HAS_VALUE`。
3. 若今后 def4 或字段结构更新，只需同步维护本映射文档与对应的配置表，即可保证 ETL 与图谱语义的一致性。 


