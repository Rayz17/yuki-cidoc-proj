-- 考古文物数据库 V3.2 Schema (CIDOC-CRM Enhanced)
-- 创建时间: 2024-12-01
-- 更新时间: 2024-12-01 (Schema Update: 1201 Template Support + Location Breakdown + Jade Height)
-- 说明: 支持遗址、时期、陶器、玉器四主体，以及元数据映射和语义事实存储

-- ============================================================
-- 0. 元数据映射层 (Meta-Model Layer)
-- ============================================================

CREATE TABLE IF NOT EXISTS sys_template_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_type TEXT NOT NULL,       -- 适用文物类型 (pottery, jade, site, period)
    field_name_cn TEXT NOT NULL,       -- 模版中的中文列名 (如 "陶土种类")
    field_name_en TEXT,                -- 对应的数据库字段名 (如 "clay_type")
    description TEXT,                  -- 字段说明
    cidoc_entity TEXT,                 -- CIDOC 主体类型 (如 "E22_Man-Made_Object")
    cidoc_property TEXT,               -- CIDOC 关系谓词 (如 "P45_consists_of")
    target_class TEXT,                 -- CIDOC 目标类型 (如 "E57_Material")
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artifact_type, field_name_cn)
);

CREATE INDEX IF NOT EXISTS idx_mappings_type ON sys_template_mappings(artifact_type);

-- ============================================================
-- 1. 语义事实层 (Semantic Fact Layer)
-- ============================================================

CREATE TABLE IF NOT EXISTS fact_artifact_triples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_type TEXT NOT NULL,       -- 文物类型 (pottery, jade, site, period)
    artifact_id INTEGER NOT NULL,      -- 关联文物ID
    mapping_id INTEGER NOT NULL,       -- 关联模版配置ID
    predicate TEXT,                    -- 关系谓词
    object_value TEXT,                 -- 抽取到的具体值
    confidence REAL DEFAULT 1.0,       -- 置信度
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mapping_id) REFERENCES sys_template_mappings(id)
);

CREATE INDEX IF NOT EXISTS idx_facts_artifact ON fact_artifact_triples(artifact_type, artifact_id);
CREATE INDEX IF NOT EXISTS idx_facts_mapping ON fact_artifact_triples(mapping_id);

-- ============================================================
-- 2. 任务管理层
-- ============================================================

CREATE TABLE IF NOT EXISTS extraction_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT UNIQUE NOT NULL,
    report_name TEXT NOT NULL,
    report_folder_path TEXT NOT NULL,
    pdf_path TEXT,
    markdown_path TEXT,
    layout_json_path TEXT,
    content_list_json_path TEXT,
    images_folder_path TEXT,
    site_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    total_pottery INTEGER DEFAULT 0,
    total_jade INTEGER DEFAULT 0,
    total_periods INTEGER DEFAULT 0,
    total_images INTEGER DEFAULT 0,
    extraction_config TEXT,
    notes TEXT,
    FOREIGN KEY (site_id) REFERENCES sites(id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_task_id ON extraction_tasks(task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON extraction_tasks(status);

CREATE TABLE IF NOT EXISTS extraction_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    log_level TEXT,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES extraction_tasks(task_id)
);

CREATE INDEX IF NOT EXISTS idx_logs_task_id ON extraction_logs(task_id);

-- ============================================================
-- 3. 图片管理层
-- ============================================================

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    image_hash TEXT NOT NULL,
    image_path TEXT NOT NULL,
    image_type TEXT,
    page_idx INTEGER,
    bbox TEXT,
    caption TEXT,
    related_text TEXT,
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES extraction_tasks(task_id),
    UNIQUE(task_id, image_hash)
);

CREATE INDEX IF NOT EXISTS idx_images_hash ON images(image_hash);
CREATE INDEX IF NOT EXISTS idx_images_task ON images(task_id);
CREATE INDEX IF NOT EXISTS idx_images_page ON images(page_idx);

CREATE TABLE IF NOT EXISTS artifact_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_type TEXT NOT NULL,
    artifact_id INTEGER NOT NULL,
    artifact_code TEXT NOT NULL,
    image_id INTEGER NOT NULL,
    image_role TEXT NOT NULL,
    display_order INTEGER DEFAULT 0,
    description TEXT,
    extraction_method TEXT,
    confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES images(id),
    UNIQUE(artifact_type, artifact_id, image_id, image_role)
);

CREATE INDEX IF NOT EXISTS idx_artifact_images_artifact ON artifact_images(artifact_type, artifact_id);
CREATE INDEX IF NOT EXISTS idx_artifact_images_image ON artifact_images(image_id);

-- ============================================================
-- 4. 主体数据层 - 遗址
-- ============================================================

CREATE TABLE IF NOT EXISTS sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    site_code TEXT UNIQUE,
    site_name TEXT NOT NULL,
    site_alias TEXT,
    site_type TEXT,
    current_location TEXT,
    geographic_coordinates TEXT,
    spatial_data TEXT, 
    elevation REAL,
    total_area REAL,
    excavated_area REAL,
    culture_name TEXT,
    absolute_dating TEXT,
    protection_level TEXT,
    preservation_status TEXT,
    description TEXT,
    source_text_blocks TEXT,
    raw_attributes TEXT,
    cidoc_attributes TEXT,
    extraction_confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES extraction_tasks(task_id)
);

CREATE INDEX IF NOT EXISTS idx_sites_task ON sites(task_id);
CREATE INDEX IF NOT EXISTS idx_sites_code ON sites(site_code);

CREATE TABLE IF NOT EXISTS site_structures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    parent_id INTEGER,
    structure_level INTEGER,
    structure_code TEXT,
    structure_name TEXT, 
    structure_type TEXT, 
    relative_position TEXT, 
    coordinates TEXT,
    length REAL,
    width REAL,
    depth REAL,
    area REAL,
    description TEXT,
    features TEXT, 
    source_text_blocks TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES sites(id),
    FOREIGN KEY (parent_id) REFERENCES site_structures(id)
);

CREATE INDEX IF NOT EXISTS idx_structures_site ON site_structures(site_id);
CREATE INDEX IF NOT EXISTS idx_structures_parent ON site_structures(parent_id);
CREATE INDEX IF NOT EXISTS idx_structures_code ON site_structures(structure_code);

-- ============================================================
-- 5. 主体数据层 - 时期
-- ============================================================

CREATE TABLE IF NOT EXISTS periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    site_id INTEGER NOT NULL,
    period_code TEXT,
    period_name TEXT NOT NULL, 
    period_alias TEXT,
    sub_period TEXT, 
    historical_era TEXT, 
    stratigraphic_layer TEXT, 
    time_span_start TEXT,
    time_span_end TEXT,
    absolute_dating TEXT, 
    relative_dating TEXT,
    development_stage TEXT, 
    phase_sequence INTEGER, 
    characteristics TEXT,
    representative_artifacts TEXT,
    source_text_blocks TEXT,
    raw_attributes TEXT,
    cidoc_attributes TEXT,
    extraction_confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES extraction_tasks(task_id),
    FOREIGN KEY (site_id) REFERENCES sites(id)
);

CREATE INDEX IF NOT EXISTS idx_periods_task ON periods(task_id);
CREATE INDEX IF NOT EXISTS idx_periods_site ON periods(site_id);
CREATE INDEX IF NOT EXISTS idx_periods_code ON periods(period_code);

-- ============================================================
-- 6. 主体数据层 - 陶器
-- ============================================================

CREATE TABLE IF NOT EXISTS pottery_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    site_id INTEGER,
    period_id INTEGER,
    structure_id INTEGER,
    
    -- 基础信息
    artifact_code TEXT NOT NULL, 
    subtype TEXT, 
    subtype_level1 TEXT,
    subtype_level2 TEXT,
    subtype_level3 TEXT,
    basic_shape TEXT, 
    
    -- 出土位置 (Location) - [Updated]
    excavation_location TEXT, -- 原始描述
    ex_region TEXT, -- [New] 出土区域/墓地
    ex_unit TEXT,   -- [New] 出土单位 (墓/坑)
    ex_layer TEXT,  -- [New] 出土层位
    found_in_tomb TEXT, -- 墓葬编号 (保留，作为 ex_unit 的规范化版本)
    
    -- 陶土种类
    clay_type TEXT,
    clay_purity TEXT,
    clay_fineness TEXT,
    mixed_materials TEXT,
    
    -- 物理特征
    color TEXT,
    hardness REAL,
    firing_temperature REAL,
    
    -- 形态特征
    shape_features TEXT,
    vessel_combination TEXT,
    
    -- 尺寸
    dimensions TEXT,
    measurements TEXT, 
    height REAL, 
    diameter REAL, 
    thickness REAL, 
    
    -- 功能与工艺
    function TEXT,
    forming_technique TEXT,
    finishing_technique TEXT,
    surface_treatment TEXT, 
    
    -- 装饰
    decoration_method TEXT,
    decoration_type TEXT,
    
    -- 生产相关
    production_activity TEXT,
    maker TEXT,
    production_date TEXT,
    production_location TEXT,
    
    -- 发掘与保存
    excavation_activity TEXT,
    preservation_status TEXT, 
    completeness TEXT, 
    
    -- 图片关联
    has_images BOOLEAN DEFAULT 0,
    main_image_id INTEGER,
    
    -- 元数据
    source_text_blocks TEXT,
    raw_attributes TEXT,
    cidoc_attributes TEXT,
    extraction_confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (task_id) REFERENCES extraction_tasks(task_id),
    FOREIGN KEY (site_id) REFERENCES sites(id),
    FOREIGN KEY (period_id) REFERENCES periods(id),
    FOREIGN KEY (structure_id) REFERENCES site_structures(id),
    FOREIGN KEY (main_image_id) REFERENCES images(id),
    UNIQUE(site_id, artifact_code)
);

CREATE INDEX IF NOT EXISTS idx_pottery_task ON pottery_artifacts(task_id);
CREATE INDEX IF NOT EXISTS idx_pottery_site ON pottery_artifacts(site_id);
CREATE INDEX IF NOT EXISTS idx_pottery_period ON pottery_artifacts(period_id);
CREATE INDEX IF NOT EXISTS idx_pottery_code ON pottery_artifacts(artifact_code);

-- ============================================================
-- 7. 主体数据层 - 玉器
-- ============================================================

CREATE TABLE IF NOT EXISTS jade_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    site_id INTEGER,
    period_id INTEGER,
    structure_id INTEGER,
    
    -- 基础信息
    artifact_code TEXT NOT NULL, 
    category_level1 TEXT,
    category_level2 TEXT, 
    category_level3 TEXT, 
    
    -- 出土位置 (Location) - [Updated]
    excavation_location TEXT, -- 原始描述
    ex_region TEXT, -- [New] 出土区域/墓地
    ex_unit TEXT,   -- [New] 出土单位 (墓/坑)
    ex_layer TEXT,  -- [New] 出土层位
    found_in_tomb TEXT, -- 墓葬编号
    
    -- 材质与外观
    jade_type TEXT, 
    jade_color TEXT, 
    jade_quality TEXT, 
    transparency TEXT, 
    surface_condition TEXT, -- 沁色
    
    -- 形态
    shape_unit TEXT,
    shape_description TEXT, 
    overall_description TEXT, 
    
    -- 纹饰与工艺
    decoration_unit TEXT, 
    decoration_theme TEXT, 
    decoration_description TEXT, 
    craft_unit TEXT, 
    cutting_technique TEXT, 
    drilling_technique TEXT, 
    carving_technique TEXT, 
    decoration_craft TEXT, 
    production_technique TEXT, 
    
    -- 尺寸 - [Updated]
    dimensions TEXT,
    measurements TEXT, 
    length REAL, 
    width REAL, 
    thickness REAL, 
    height REAL, -- [New] 高度 (某些玉器有高度)
    diameter REAL, 
    hole_diameter REAL, 
    weight REAL, 
    
    -- 生产相关
    production_activity TEXT,
    maker TEXT,
    production_date TEXT,
    production_location TEXT,
    
    -- 发掘与功能
    excavation_activity TEXT,
    function TEXT,
    usage TEXT, 
    preservation_status TEXT, 
    completeness TEXT, 
    
    -- 图片关联
    has_images BOOLEAN DEFAULT 0,
    main_image_id INTEGER,
    
    -- 元数据
    source_text_blocks TEXT,
    raw_attributes TEXT,
    cidoc_attributes TEXT,
    extraction_confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (task_id) REFERENCES extraction_tasks(task_id),
    FOREIGN KEY (site_id) REFERENCES sites(id),
    FOREIGN KEY (period_id) REFERENCES periods(id),
    FOREIGN KEY (structure_id) REFERENCES site_structures(id),
    FOREIGN KEY (main_image_id) REFERENCES images(id),
    UNIQUE(site_id, artifact_code)
);

CREATE INDEX IF NOT EXISTS idx_jade_task ON jade_artifacts(task_id);
CREATE INDEX IF NOT EXISTS idx_jade_site ON jade_artifacts(site_id);
CREATE INDEX IF NOT EXISTS idx_jade_period ON jade_artifacts(period_id);
CREATE INDEX IF NOT EXISTS idx_jade_code ON jade_artifacts(artifact_code);

-- ============================================================
-- 8. 关系映射层
-- ============================================================

CREATE TABLE IF NOT EXISTS artifact_period_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_type TEXT NOT NULL,
    artifact_id INTEGER NOT NULL,
    period_id INTEGER NOT NULL,
    confidence REAL,
    evidence TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (period_id) REFERENCES periods(id),
    UNIQUE(artifact_type, artifact_id, period_id)
);

CREATE INDEX IF NOT EXISTS idx_period_mapping_artifact ON artifact_period_mapping(artifact_type, artifact_id);
CREATE INDEX IF NOT EXISTS idx_period_mapping_period ON artifact_period_mapping(period_id);

CREATE TABLE IF NOT EXISTS artifact_location_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_type TEXT NOT NULL,
    artifact_id INTEGER NOT NULL,
    structure_id INTEGER NOT NULL,
    location_type TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (structure_id) REFERENCES site_structures(id),
    UNIQUE(artifact_type, artifact_id, structure_id, location_type)
);

CREATE INDEX IF NOT EXISTS idx_location_mapping_artifact ON artifact_location_mapping(artifact_type, artifact_id);
CREATE INDEX IF NOT EXISTS idx_location_mapping_structure ON artifact_location_mapping(structure_id);
