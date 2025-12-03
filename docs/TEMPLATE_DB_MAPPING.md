# 抽取模版与数据库映射文档 (V3.2 - 1201版)

本文档描述了 Excel 抽取模版（20241201版）中的字段如何映射到数据库 schema_v3.2 中的字段。

## 1. 遗址 (Sites)

对应模版：`数据结构3-遗址属性和类分析1201.xlsx`

| 模版字段 (抽取属性) | 数据库字段 (sites) | 说明 |
| :--- | :--- | :--- |
| 遗址名称 | `site_name` | 遗址的标准名称 |
| 遗址类型 | `site_type` | 遗址的类型 |
| 遗址当前位置 | `current_location` | 行政区划位置 |
| 遗址空间数据 | `spatial_data` | [New] 包含地理坐标、面积等空间信息 |
| 遗址描述 | `description` | 遗址的总体描述 |
| (遗址内子区域) | *Mapped to `site_structures`* | 见下表 |

### 遗址结构 (Site Structures)

遗址内的子区域信息将存储在 `site_structures` 表中。

| 模版字段 | 数据库字段 (site_structures) | 说明 |
| :--- | :--- | :--- |
| 子区域编号或名称 | `structure_name` | 子区域名称 |
| 子区域位置描述 | `relative_position` | 位置描述 |
| 子区域内具体单位 | `features` | 包含的具体遗迹单位 |
| 所属子区域 | `parent_id` (关联) | 通过逻辑解析映射到父级ID |

## 2. 时期 (Periods)

对应模版：`数据结构4-时期属性和类分析1201.xlsx`

| 模版字段 (抽取属性) | 数据库字段 (periods) | 说明 |
| :--- | :--- | :--- |
| 时期/期别 | `period_name` | 时期名称 |
| 发展阶段 | `development_stage` | 文化发展阶段 |
| 绝对年代 | `absolute_dating` | C14测年或推断年代 |
| 历史背景朝代 | `historical_era` | [New] 对应的历史朝代 |
| 细分时期划分 | `sub_period` | [New] 更细致的分期 |
| 时期顺序 | `phase_sequence` | 早晚顺序 |
| 物理地层归属 | `stratigraphic_layer` | [New] 地层信息 |

## 3. 陶器 (Pottery Artifacts)

对应模版：`数据结构1-陶器文化特征单元分析1201.xlsx`

| 模版字段 (抽取属性) | 数据库字段 (pottery_artifacts) | 类型 | 说明 |
| :--- | :--- | :--- | :--- |
| 陶土种类 | `clay_type` | 主字段 | 夹砂/泥质等 |
| 陶土纯洁程度 | `clay_purity` | 主字段 | |
| 陶土细腻程度 | `clay_fineness` | 主字段 | |
| 掺杂物 | `mixed_materials` | 主字段 | |
| 硬度 | `hardness` | 主字段 | 数值 |
| 烧成温度 | `firing_temperature` | 主字段 | 数值 |
| 基本器型 | `subtype` | 主字段 | 鼎、豆、壶等 |
| 器型部位特征 | `shape_features` | 主字段 | |
| 器物组合 | `vessel_combination` | 主字段 | |
| 基本尺寸 | `dimensions` | 主字段 | 原始描述 |
| (衍生) | `height` | 衍生字段 | 高度 |
| (衍生) | `diameter` | 衍生字段 | 口径/底径 |
| (衍生) | `thickness` | 衍生字段 | 壁厚 |
| 器物功能 | `function` | 主字段 | |
| 成型工艺 | `forming_technique` | 主字段 | |
| 修整技术 | `finishing_technique` | 主字段 | |
| 装饰手法 | `decoration_method` | 主字段 | |
| 纹饰类型 | `decoration_type` | 主字段 | |
| 人工物品编号 | `artifact_code` | 关键字段 | M1:1 |
| 制作活动 | `production_activity` | 主字段 | |
| 制作者 | `maker` | 主字段 | |
| 制作年代 | `production_date` | 主字段 | |
| 制作地点 | `production_location` | 主字段 | |
| 原始出土地点 | `excavation_location` | 主字段 | 完整描述 |
| (衍生) | `ex_region` | 衍生字段 | [New] 出土区域/墓地 |
| (衍生) | `ex_unit` | 衍生字段 | [New] 出土单位 (墓/坑) |
| (衍生) | `ex_layer` | 衍生字段 | [New] 出土层位 |
| 发掘活动 | `excavation_activity` | 主字段 | |
| 量度信息 | `measurements` | [New] | 详细量度数据 |

## 4. 玉器 (Jade Artifacts)

对应模版：`数据结构2-玉器文化特征单元分析1201.xlsx`

| 模版字段 (抽取属性) | 数据库字段 (jade_artifacts) | 类型 | 说明 |
| :--- | :--- | :--- | :--- |
| 二级类型 | `category_level2` | 主字段 | 璧环类等 |
| 三级类型 | `category_level3` | 主字段 | 玉璧等 |
| 器型单元 | `shape_unit` | 主字段 | |
| 整体形态描述 | `overall_description` | [New] | |
| 纹饰单元 | `decoration_unit` | 主字段 | 按图案题材 |
| 工艺特征单元 | `craft_unit` | 主字段 | 按制作痕迹 |
| 材质单元 | `jade_type` | 主字段 | 玉料类型 |
| 沁色单元 | `surface_condition` | 主字段 | |
| 人工物品编号 | `artifact_code` | 关键字段 | |
| 量度信息 | `measurements` | [New] | |
| (衍生) | `length`, `width`, `thickness` | 衍生字段 | |
| (衍生) | `height` | 衍生字段 | [New] 高度 |
| 原始出土地点 | `excavation_location` | 主字段 | 完整描述 |
| (衍生) | `ex_region` | 衍生字段 | [New] 出土区域/墓地 |
| (衍生) | `ex_unit` | 衍生字段 | [New] 出土单位 (墓/坑) |
| (衍生) | `ex_layer` | 衍生字段 | [New] 出土层位 |
| 制作活动 | `production_activity` | 主字段 | |
| 制作者 | `maker` | 主字段 | |
| 制作年代 | `production_date` | 主字段 | |
| 制作地点 | `production_location` | 主字段 | |
| 发掘活动 | `excavation_activity` | 主字段 | |
| 器物功能 | `function` | 主字段 | |
