# 考古文物数据库设计方案 V3.0 Final

## 1. 报告文件结构

### 1.1 标准报告文件夹结构
```
遗址出土报告/
└─ {报告名称}/
    ├─ {uuid}_origin.pdf          # 原始PDF文件
    ├─ full.md                     # 转换后的Markdown文本（主要抽取源）
    ├─ layout.json                 # 布局信息（页面结构）
    ├─ {uuid}_content_list.json   # 内容列表（文本与图片对应关系）
    ├─ {uuid}_model.json          # 模型文件
    └─ images/                     # 图片集合（1400+张）
        ├─ {hash1}.jpg            # 图片文件（哈希命名）
        ├─ {hash2}.jpg
        └─ ...
```

### 1.2 图片与文本的关联
- `content_list.json` 包含文本块与图片的位置关系
- 每个图片通过哈希值命名，确保唯一性
- 需要建立"文物编码 → 图片哈希"的映射关系

---

## 2. 数据库表结构（完整版）

### 2.1 元数据层

#### 2.1.1 extraction_tasks (抽取任务表)
```sql
CREATE TABLE extraction_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT UNIQUE NOT NULL,
    report_name TEXT NOT NULL,
    report_folder_path TEXT NOT NULL,      -- 报告文件夹路径
    pdf_path TEXT,                         -- PDF文件路径
    markdown_path TEXT,                    -- Markdown文件路径
    layout_json_path TEXT,                 -- layout.json路径
    content_list_json_path TEXT,           -- content_list.json路径
    images_folder_path TEXT,               -- images文件夹路径
    site_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    total_pottery INTEGER DEFAULT 0,
    total_jade INTEGER DEFAULT 0,
    total_periods INTEGER DEFAULT 0,
    total_images INTEGER DEFAULT 0,        -- 图片总数
    extraction_config TEXT,
    notes TEXT,
    FOREIGN KEY (site_id) REFERENCES sites(id)
);
```

#### 2.1.2 images (图片索引表) **[新增]**
```sql
CREATE TABLE images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    
    -- 图片基本信息
    image_hash TEXT NOT NULL,              -- 图片哈希值（文件名）
    image_path TEXT NOT NULL,              -- 图片完整路径
    image_type TEXT,                       -- 图片类型：photo(照片), drawing(线图), map(地图)
    
    -- 图片元数据
    page_idx INTEGER,                      -- 所在PDF页码
    bbox TEXT,                             -- 边界框坐标 [x1,y1,x2,y2]
    caption TEXT,                          -- 图片标题/说明
    
    -- 关联信息
    related_text TEXT,                     -- 相关文本内容
    
    -- 文件信息
    file_size INTEGER,                     -- 文件大小（字节）
    width INTEGER,                         -- 图片宽度
    height INTEGER,                        -- 图片高度
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (task_id) REFERENCES extraction_tasks(task_id),
    UNIQUE(task_id, image_hash)
);

CREATE INDEX idx_images_hash ON images(image_hash);
CREATE INDEX idx_images_task ON images(task_id);
```

#### 2.1.3 artifact_images (文物图片关联表) **[新增]**
```sql
CREATE TABLE artifact_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 文物信息
    artifact_type TEXT NOT NULL,           -- 'pottery' 或 'jade'
    artifact_id INTEGER NOT NULL,          -- 文物ID
    artifact_code TEXT NOT NULL,           -- 文物编码（冗余，便于查询）
    
    -- 图片信息
    image_id INTEGER NOT NULL,             -- 关联images表
    
    -- 关系信息
    image_role TEXT NOT NULL,              -- 图片角色：
                                          -- 'main_photo'（主照片）
                                          -- 'detail_photo'（细节照片）
                                          -- 'line_drawing'（线图）
                                          -- 'context_photo'（出土情境照片）
    display_order INTEGER DEFAULT 0,       -- 显示顺序
    description TEXT,                      -- 图片描述
    
    -- 提取信息
    extraction_method TEXT,                -- 提取方式：manual(手动), auto(自动), llm(LLM识别)
    confidence REAL,                       -- 关联置信度
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (image_id) REFERENCES images(id),
    UNIQUE(artifact_type, artifact_id, image_id, image_role)
);

CREATE INDEX idx_artifact_images_artifact ON artifact_images(artifact_type, artifact_id);
CREATE INDEX idx_artifact_images_image ON artifact_images(image_id);
```

---

### 2.2 主体数据层（与V3.0相同，略）

参见 `DATABASE_DESIGN_V3.md` 第3节：
- sites (遗址表)
- site_structures (遗址结构表)
- periods (时期表)
- pottery_artifacts (陶器表)
- jade_artifacts (玉器表)

**重要补充**：在 pottery_artifacts 和 jade_artifacts 表中添加：
```sql
-- 在两个文物表中添加
has_images BOOLEAN DEFAULT 0,             -- 是否有关联图片
main_image_id INTEGER,                    -- 主图片ID
FOREIGN KEY (main_image_id) REFERENCES images(id)
```

---

## 3. 图片处理流程

### 3.1 图片索引流程

```python
def index_report_images(report_folder_path, task_id):
    """索引报告中的所有图片"""
    
    images_folder = os.path.join(report_folder_path, 'images')
    content_list_path = find_content_list_json(report_folder_path)
    
    # 1. 读取content_list.json
    with open(content_list_path) as f:
        content_list = json.load(f)
    
    # 2. 提取图片信息
    image_items = [item for item in content_list if item['type'] == 'image']
    
    # 3. 索引每张图片
    for item in image_items:
        image_hash = extract_image_hash(item)
        image_path = os.path.join(images_folder, f"{image_hash}.jpg")
        
        if os.path.exists(image_path):
            # 获取图片元数据
            width, height = get_image_dimensions(image_path)
            file_size = os.path.getsize(image_path)
            
            # 提取图片说明（从周围文本）
            caption = extract_image_caption(content_list, item)
            
            # 插入数据库
            db.insert_image({
                'task_id': task_id,
                'image_hash': image_hash,
                'image_path': image_path,
                'page_idx': item.get('page_idx'),
                'bbox': json.dumps(item.get('bbox')),
                'caption': caption,
                'file_size': file_size,
                'width': width,
                'height': height
            })
```

### 3.2 文物与图片关联流程

#### 方法1：基于文本匹配（自动）
```python
def link_artifacts_to_images_auto(artifacts, images, content_list):
    """自动关联文物与图片"""
    
    for artifact in artifacts:
        artifact_code = artifact['artifact_code']  # 如 'M1:1'
        
        # 在content_list中查找包含该编码的文本块
        related_text_blocks = find_text_blocks_with_code(
            content_list, 
            artifact_code
        )
        
        # 查找这些文本块附近的图片
        nearby_images = find_nearby_images(
            content_list,
            related_text_blocks,
            distance_threshold=500  # 像素距离
        )
        
        # 建立关联
        for img in nearby_images:
            # 判断图片类型
            image_role = classify_image_role(img, artifact)
            
            db.link_artifact_to_image(
                artifact_type=artifact['type'],
                artifact_id=artifact['id'],
                artifact_code=artifact_code,
                image_id=img['id'],
                image_role=image_role,
                extraction_method='auto',
                confidence=0.8
            )
```

#### 方法2：基于LLM识别（智能）
```python
def link_artifacts_to_images_llm(artifact, candidate_images):
    """使用LLM识别文物对应的图片"""
    
    # 构建提示词
    prompt = f"""
    文物信息：
    - 编码：{artifact['artifact_code']}
    - 类型：{artifact['subtype']}
    - 描述：{artifact['description']}
    
    候选图片：
    {format_candidate_images(candidate_images)}
    
    请识别哪些图片属于该文物，并判断图片类型（照片/线图）。
    """
    
    # 调用LLM
    result = call_llm_api(prompt)
    
    # 解析结果并建立关联
    for match in result['matches']:
        db.link_artifact_to_image(
            artifact_type=artifact['type'],
            artifact_id=artifact['id'],
            artifact_code=artifact['artifact_code'],
            image_id=match['image_id'],
            image_role=match['role'],
            extraction_method='llm',
            confidence=match['confidence']
        )
```

#### 方法3：手动标注（GUI）
```python
# 在GUI中提供图片选择界面
def manual_link_artifact_to_image(artifact_id, artifact_type):
    """手动关联文物与图片"""
    
    # 显示文物信息
    display_artifact_info(artifact_id, artifact_type)
    
    # 显示候选图片（缩略图网格）
    candidate_images = get_candidate_images_for_artifact(
        artifact_id, 
        artifact_type
    )
    
    # 用户选择图片并标注类型
    selected_images = user_select_images(candidate_images)
    
    # 保存关联
    for img, role in selected_images:
        db.link_artifact_to_image(
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            image_id=img['id'],
            image_role=role,
            extraction_method='manual',
            confidence=1.0
        )
```

---

## 4. GUI 界面设计（图片功能）

### 4.1 文物详情页面（带图片）

```
┌─────────────────────────────────────────────────────────────┐
│ 文物详情: M1:1 玉琮                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ┌─────────────────┐  ┌─────────────────────────────────┐  │
│ │                 │  │ 基本信息                        │  │
│ │   主照片        │  │ - 编码: M1:1                    │  │
│ │                 │  │ - 类型: 玉器 > 琮筒类 > 玉琮   │  │
│ │  [大图显示]    │  │ - 尺寸: 高8.8、外径6.5厘米      │  │
│ │                 │  │ - 材质: 青玉                    │  │
│ └─────────────────┘  │ - 工艺: 切割、钻孔、雕刻        │  │
│                      │ - 纹饰: 神人神兽纹              │  │
│ 相关图片:            │ - 出土: M1墓葬                  │  │
│ ┌────┐┌────┐┌────┐  │ - 时期: 第一期                  │  │
│ │细节││线图││情境│  └─────────────────────────────────┘  │
│ │照片││    ││照片│                                      │  │
│ └────┘└────┘└────┘  [编辑信息] [关联图片] [导出数据]   │  │
│                                                             │
│ 图片管理:                                                   │
│ ┌─────────────────────────────────────────────────────┐    │
│ │ 图片1: 主照片 (line_drawing)                        │    │
│ │ 来源: images/abc123.jpg | 页码: 45 | 尺寸: 800x600 │    │
│ │ [查看大图] [设为主图] [删除关联]                    │    │
│ ├─────────────────────────────────────────────────────┤    │
│ │ 图片2: 细节照片 (detail_photo)                      │    │
│ │ 来源: images/def456.jpg | 页码: 46 | 尺寸: 600x800 │    │
│ │ [查看大图] [设为主图] [删除关联]                    │    │
│ └─────────────────────────────────────────────────────┘    │
│                                                             │
│ [+ 添加图片关联]                                            │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 图片关联界面

```
┌─────────────────────────────────────────────────────────────┐
│ 为文物 M1:1 关联图片                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 搜索范围: ○ 全部图片  ● 附近图片  ○ 同页图片              │
│                                                             │
│ 候选图片 (共156张):                                         │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐                │ │
│ │ │ □  ││ □  ││ ☑  ││ □  ││ ☑  ││ □  │                │ │
│ │ │图1 ││图2 ││图3 ││图4 ││图5 ││图6 │                │ │
│ │ │P45 ││P45 ││P46 ││P46 ││P47 ││P47 │                │ │
│ │ └────┘└────┘└────┘└────┘└────┘└────┘                │ │
│ │ ┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐                │ │
│ │ │ □  ││ □  ││ □  ││ □  ││ □  ││ □  │                │ │
│ │ │图7 ││图8 ││图9 ││图10││图11││图12│                │ │
│ │ │P48 ││P48 ││P49 ││P49 ││P50 ││P50 │                │ │
│ │ └────┘└────┘└────┘└────┘└────┘└────┘                │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                             │
│ 已选择: 2张图片                                             │
│ - 图3 (P46): 类型 [主照片▼]  顺序 [1]                     │
│ - 图5 (P47): 类型 [线图▼]    顺序 [2]                     │
│                                                             │
│ [智能推荐] [取消] [确认关联]                                │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 图片浏览器

```
┌─────────────────────────────────────────────────────────────┐
│ 图片浏览器 - 瑶山遗址报告                                   │
├─────────────────────────────────────────────────────────────┤
│ 筛选: [全部▼] [已关联] [未关联]  类型: [全部▼]            │
│ 页码: [___] - [___]  搜索: [_____________] [搜索]          │
│                                                             │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ 缩略图网格 (每行6张)                                    │ │
│ │ ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐  │ │
│ │ │        ││        ││        ││        ││        │  │ │
│ │ │ 图1    ││ 图2    ││ 图3    ││ 图4    ││ 图5    │  │ │
│ │ │ P1     ││ P1     ││ P2     ││ P2     ││ P3     │  │ │
│ │ │ 未关联 ││ 已关联 ││ 已关联 ││ 未关联 ││ 已关联 │  │ │
│ │ └────────┘└────────┘└────────┘└────────┘└────────┘  │ │
│ │ ... (更多图片)                                          │ │
│ └────────────────────────────────────────────────────────┘ │
│                                                             │
│ 共1402张图片 | 已关联: 245 | 未关联: 1157                  │
│                                                             │
│ [批量关联] [导出图片列表] [刷新]                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 完整抽取流程（含图片）

```python
def extract_complete_report(report_folder_path, templates):
    """完整的报告抽取流程"""
    
    # ========== 阶段1: 初始化 ==========
    task_id = create_extraction_task(report_folder_path)
    
    # ========== 阶段2: 图片索引 ==========
    print("[1/8] 索引图片...")
    total_images = index_report_images(report_folder_path, task_id)
    print(f"  ✅ 已索引 {total_images} 张图片")
    
    # ========== 阶段3: 抽取遗址信息 ==========
    print("[2/8] 抽取遗址信息...")
    markdown_path = os.path.join(report_folder_path, 'full.md')
    site_id = extract_site_info(markdown_path, templates['site'], task_id)
    
    # ========== 阶段4: 抽取遗址结构 ==========
    print("[3/8] 抽取遗址结构...")
    structures = extract_site_structures(markdown_path, site_id, task_id)
    
    # ========== 阶段5: 抽取时期信息 ==========
    print("[4/8] 抽取时期信息...")
    periods = extract_periods(markdown_path, templates['period'], site_id, task_id)
    
    # ========== 阶段6: 抽取陶器 ==========
    print("[5/8] 抽取陶器信息...")
    pottery_list = extract_pottery_artifacts(
        markdown_path, 
        templates['pottery'],
        site_id,
        task_id
    )
    
    # ========== 阶段7: 抽取玉器 ==========
    print("[6/8] 抽取玉器信息...")
    jade_list = extract_jade_artifacts(
        markdown_path,
        templates['jade'],
        site_id,
        task_id
    )
    
    # ========== 阶段8: 关联图片 ==========
    print("[7/8] 关联文物与图片...")
    
    # 读取content_list用于图片定位
    content_list = load_content_list(report_folder_path)
    images = get_all_images(task_id)
    
    # 自动关联陶器图片
    link_artifacts_to_images_auto(pottery_list, images, content_list)
    
    # 自动关联玉器图片
    link_artifacts_to_images_auto(jade_list, images, content_list)
    
    # ========== 阶段9: 建立其他关联 ==========
    print("[8/8] 建立关联关系...")
    link_artifacts_to_periods(pottery_list, periods)
    link_artifacts_to_periods(jade_list, periods)
    link_artifacts_to_locations(pottery_list, structures)
    link_artifacts_to_locations(jade_list, structures)
    
    # ========== 完成 ==========
    update_task_statistics(task_id)
    print(f"\n✅ 抽取完成！")
    print(f"  - 遗址: 1个")
    print(f"  - 时期: {len(periods)}个")
    print(f"  - 陶器: {len(pottery_list)}件")
    print(f"  - 玉器: {len(jade_list)}件")
    print(f"  - 图片: {total_images}张")
```

---

## 6. 查询示例（含图片）

### 6.1 查询文物及其图片

```sql
-- 查询单个文物的所有图片
SELECT 
    p.artifact_code,
    p.subtype,
    i.image_path,
    ai.image_role,
    ai.display_order,
    i.caption
FROM pottery_artifacts p
LEFT JOIN artifact_images ai ON ai.artifact_id = p.id AND ai.artifact_type = 'pottery'
LEFT JOIN images i ON i.id = ai.image_id
WHERE p.artifact_code = 'M1:1'
ORDER BY ai.display_order;
```

### 6.2 查询有图片的文物

```sql
SELECT 
    artifact_code,
    subtype,
    COUNT(ai.id) as image_count
FROM pottery_artifacts p
LEFT JOIN artifact_images ai ON ai.artifact_id = p.id AND ai.artifact_type = 'pottery'
WHERE p.has_images = 1
GROUP BY p.id
HAVING image_count > 0;
```

### 6.3 查询未关联的图片

```sql
SELECT 
    i.id,
    i.image_hash,
    i.page_idx,
    i.caption
FROM images i
WHERE i.task_id = 'yaoshan_001'
AND i.id NOT IN (
    SELECT DISTINCT image_id FROM artifact_images
);
```

---

## 7. 数据导出（含图片）

### 7.1 导出文物数据包

```python
def export_artifact_package(artifact_id, artifact_type, output_dir):
    """导出文物完整数据包（含图片）"""
    
    # 1. 查询文物信息
    artifact = db.get_artifact(artifact_id, artifact_type)
    
    # 2. 查询关联图片
    images = db.get_artifact_images(artifact_id, artifact_type)
    
    # 3. 创建导出目录
    package_dir = os.path.join(output_dir, artifact['artifact_code'])
    os.makedirs(package_dir, exist_ok=True)
    
    # 4. 导出JSON数据
    with open(os.path.join(package_dir, 'data.json'), 'w') as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2)
    
    # 5. 复制图片文件
    images_dir = os.path.join(package_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    for img in images:
        src_path = img['image_path']
        dst_filename = f"{img['image_role']}_{img['display_order']}.jpg"
        dst_path = os.path.join(images_dir, dst_filename)
        shutil.copy2(src_path, dst_path)
    
    # 6. 生成README
    generate_readme(package_dir, artifact, images)
    
    print(f"✅ 已导出到: {package_dir}")
```

### 7.2 导出HTML报告

```python
def export_html_report(task_id, output_path):
    """导出带图片的HTML报告"""
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>考古文物数据报告</title>
        <style>
            .artifact {{ margin: 20px; border: 1px solid #ccc; padding: 10px; }}
            .artifact-images {{ display: flex; gap: 10px; }}
            .artifact-images img {{ max-width: 200px; height: auto; }}
        </style>
    </head>
    <body>
        <h1>瑶山遗址考古报告</h1>
    """
    
    # 遍历所有文物
    artifacts = db.get_all_artifacts(task_id)
    for artifact in artifacts:
        images = db.get_artifact_images(artifact['id'], artifact['type'])
        
        html += f"""
        <div class="artifact">
            <h2>{artifact['artifact_code']} - {artifact['subtype']}</h2>
            <p>材质: {artifact.get('material_type', 'N/A')}</p>
            <p>尺寸: {artifact.get('dimensions', 'N/A')}</p>
            
            <div class="artifact-images">
        """
        
        for img in images:
            html += f'<img src="{img["image_path"]}" alt="{img["image_role"]}">'
        
        html += """
            </div>
        </div>
        """
    
    html += """
    </body>
    </html>
    """
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
```

---

## 8. 实施优先级

### Phase 1: 核心功能（必需）
- [x] 基础数据库表结构
- [ ] 图片索引功能
- [ ] 文物与图片自动关联（基于文本匹配）
- [ ] GUI图片显示

### Phase 2: 增强功能（重要）
- [ ] 手动图片关联界面
- [ ] 图片浏览器
- [ ] 数据导出（含图片）

### Phase 3: 高级功能（可选）
- [ ] LLM智能图片识别
- [ ] 图片OCR文字提取
- [ ] 图片相似度匹配
- [ ] 3D模型支持

---

*文档版本：V3.0 Final*  
*更新时间：2024-12-01*  
*作者：AI Assistant*

