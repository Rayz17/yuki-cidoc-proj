# GUI升级方案 - V3.0适配

## 当前GUI分析

### 现有功能（V1.0）
1. **配置管理**
   - LLM服务配置（Coze/Gemini/Anthropic）
   - 报告和模板选择

2. **数据抽取**
   - 单报告+单模板抽取
   - 调用旧版`main.py`

3. **数据库浏览**
   - 查看单表数据
   - 简单的列名映射
   - CSV导出

### 主要问题

#### 1. 架构问题 ❌
- 调用的是旧版`main.py`，不支持V3.0的多主体抽取
- 使用旧版数据库结构（单表）
- 不支持报告文件夹（只支持单个.md文件）

#### 2. 功能缺失 ❌
- ❌ 不支持多模板选择（遗址、时期、陶器、玉器）
- ❌ 不支持报告文件夹（需要full.md + images/）
- ❌ 无法查看任务列表和状态
- ❌ 无法查看抽取日志
- ❌ 无法查看图片关联
- ❌ 无法查看关系映射
- ❌ 无法查看任务报告

#### 3. 数据展示问题 ❌
- 只能查看单表，无法关联查询
- 列名映射不完整（只有7个字段）
- 无法查看文物图片
- 无法查看遗址结构树
- 无法查看时期-文物关系

---

## V3.0 GUI升级方案

### 设计目标

1. **完整支持V3.0功能**
   - 多主体抽取（遗址、时期、陶器、玉器）
   - 报告文件夹支持
   - 图片管理和展示

2. **增强用户体验**
   - 任务管理和进度跟踪
   - 日志查看
   - 数据可视化

3. **丰富数据展示**
   - 多表关联查询
   - 图片展示
   - 关系图谱

### 新架构设计

```
GUI V3.0
├── 页面1: 🏠 首页（Dashboard）
│   ├── 系统概览
│   ├── 任务统计
│   └── 快速操作
│
├── 页面2: 🚀 数据抽取
│   ├── 报告文件夹选择
│   ├── 多模板选择（遗址、时期、陶器、玉器）
│   ├── 抽取进度显示
│   └── 实时日志
│
├── 页面3: 📋 任务管理
│   ├── 任务列表
│   ├── 任务详情
│   ├── 任务日志
│   └── 任务报告
│
├── 页面4: 🏛️ 遗址浏览
│   ├── 遗址列表
│   ├── 遗址详情
│   ├── 遗址结构树
│   └── 时期信息
│
├── 页面5: 🏺 文物浏览
│   ├── 文物列表（陶器/玉器）
│   ├── 文物详情
│   ├── 文物图片展示
│   ├── 关联信息（时期、位置）
│   └── 高级筛选
│
├── 页面6: 📸 图片管理
│   ├── 图片列表
│   ├── 图片详情
│   ├── 图片-文物关联
│   └── 图片搜索
│
├── 页面7: 📊 数据分析
│   ├── 统计图表
│   ├── 关系图谱
│   └── 数据导出
│
└── 页面8: ⚙️ 系统设置
    ├── LLM配置
    ├── 数据库管理
    └── 系统信息
```

---

## 详细功能设计

### 页面1: 🏠 首页（Dashboard）

```python
def show_dashboard():
    st.title("🏠 考古文物数据抽取系统 V3.0")
    
    # 系统概览
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总任务数", task_count)
    with col2:
        st.metric("遗址数", site_count)
    with col3:
        st.metric("文物数", artifact_count)
    with col4:
        st.metric("图片数", image_count)
    
    # 最近任务
    st.subheader("最近任务")
    # 显示最近5个任务
    
    # 快速操作
    st.subheader("快速操作")
    if st.button("🚀 新建抽取任务"):
        st.switch_page("pages/2_数据抽取.py")
```

### 页面2: 🚀 数据抽取

```python
def show_extraction():
    st.title("🚀 数据抽取")
    
    # 报告文件夹选择
    report_folders = get_report_folders()
    selected_report = st.selectbox("选择报告文件夹", report_folders)
    
    # 显示报告信息
    if selected_report:
        show_report_info(selected_report)
    
    # 模板选择（多选）
    st.subheader("选择抽取模板")
    col1, col2 = st.columns(2)
    
    with col1:
        site_template = st.selectbox("遗址模板", ["不抽取"] + templates['site'])
        period_template = st.selectbox("时期模板", ["不抽取"] + templates['period'])
    
    with col2:
        pottery_template = st.selectbox("陶器模板", ["不抽取"] + templates['pottery'])
        jade_template = st.selectbox("玉器模板", ["不抽取"] + templates['jade'])
    
    # 开始抽取
    if st.button("开始抽取", type="primary"):
        # 调用workflow
        run_extraction_v3(selected_report, templates)
```

### 页面3: 📋 任务管理

```python
def show_tasks():
    st.title("📋 任务管理")
    
    # 任务列表
    tasks = get_all_tasks()
    
    # 筛选
    status_filter = st.multiselect("状态", ["pending", "running", "completed", "failed"])
    
    # 显示任务表格
    for task in tasks:
        with st.expander(f"{task['task_id']} - {task['report_name']}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"状态: {task['status']}")
            with col2:
                st.write(f"陶器: {task['total_pottery']}")
            with col3:
                st.write(f"玉器: {task['total_jade']}")
            
            # 查看详情按钮
            if st.button("查看详情", key=f"detail_{task['task_id']}"):
                show_task_detail(task['task_id'])
```

### 页面4: 🏛️ 遗址浏览

```python
def show_sites():
    st.title("🏛️ 遗址浏览")
    
    # 遗址列表
    sites = get_all_sites()
    selected_site = st.selectbox("选择遗址", sites)
    
    if selected_site:
        # 遗址详情
        site_info = get_site_info(selected_site)
        show_site_details(site_info)
        
        # 遗址结构树
        st.subheader("遗址结构")
        structures = get_site_structures(selected_site)
        show_structure_tree(structures)
        
        # 时期信息
        st.subheader("时期划分")
        periods = get_site_periods(selected_site)
        show_periods(periods)
```

### 页面5: 🏺 文物浏览

```python
def show_artifacts():
    st.title("🏺 文物浏览")
    
    # 类型选择
    artifact_type = st.radio("文物类型", ["陶器", "玉器"], horizontal=True)
    
    # 高级筛选
    with st.expander("高级筛选"):
        site_filter = st.multiselect("遗址", get_all_sites())
        period_filter = st.multiselect("时期", get_all_periods())
        has_image_filter = st.checkbox("仅显示有图片的")
    
    # 文物列表
    artifacts = get_artifacts(artifact_type, filters)
    
    # 分页显示
    page_size = 20
    page = st.number_input("页码", 1, max_pages)
    
    # 显示文物卡片
    for artifact in artifacts[start:end]:
        with st.container():
            col1, col2 = st.columns([1, 3])
            with col1:
                # 显示主图片
                if artifact['main_image_id']:
                    st.image(get_image_path(artifact['main_image_id']))
            with col2:
                st.subheader(artifact['artifact_code'])
                st.write(f"类型: {artifact['subtype']}")
                st.write(f"出土: {artifact['found_in_tomb']}")
                if st.button("查看详情", key=f"art_{artifact['id']}"):
                    show_artifact_detail(artifact['id'], artifact_type)
```

### 页面6: 📸 图片管理

```python
def show_images():
    st.title("📸 图片管理")
    
    # 搜索
    search = st.text_input("搜索图片（文物编号、说明）")
    
    # 筛选
    task_filter = st.selectbox("任务", get_all_tasks())
    role_filter = st.multiselect("角色", ["photo", "drawing", "diagram", "context"])
    
    # 图片网格显示
    images = get_images(filters)
    
    cols = st.columns(4)
    for i, img in enumerate(images):
        with cols[i % 4]:
            st.image(img['image_path'], use_column_width=True)
            st.caption(img['caption'][:50])
            if st.button("详情", key=f"img_{img['id']}"):
                show_image_detail(img['id'])
```

### 页面7: 📊 数据分析

```python
def show_analytics():
    st.title("📊 数据分析")
    
    # 统计图表
    st.subheader("文物统计")
    
    # 按类型统计
    chart_data = get_artifact_statistics()
    st.bar_chart(chart_data)
    
    # 按时期统计
    period_stats = get_period_statistics()
    st.line_chart(period_stats)
    
    # 图片关联统计
    image_stats = get_image_statistics()
    st.metric("图片关联率", f"{image_stats['rate']:.1%}")
    
    # 数据导出
    st.subheader("数据导出")
    export_type = st.selectbox("导出类型", ["全部文物", "陶器", "玉器", "遗址信息"])
    if st.button("导出Excel"):
        export_to_excel(export_type)
```

### 页面8: ⚙️ 系统设置

```python
def show_settings():
    st.title("⚙️ 系统设置")
    
    # LLM配置
    st.subheader("LLM服务配置")
    # （保留现有的LLM配置功能）
    
    # 数据库管理
    st.subheader("数据库管理")
    db_path = st.text_input("数据库路径", value=config['database']['path'])
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("初始化数据库"):
            initialize_database()
    with col2:
        if st.button("备份数据库"):
            backup_database()
    
    # 系统信息
    st.subheader("系统信息")
    st.info(f"版本: V3.0")
    st.info(f"数据库: {db_path}")
    st.info(f"Python: {sys.version}")
```

---

## 实施计划

### 阶段1: 核心功能适配（优先级：高）

**时间**: 1-2天

1. **修改数据抽取页面**
   - ✅ 支持报告文件夹选择
   - ✅ 支持多模板选择
   - ✅ 调用`workflow.py`而非`main.py`
   - ✅ 显示抽取进度和日志

2. **修改数据库浏览页面**
   - ✅ 支持V3.0数据库结构（10个表）
   - ✅ 完整的列名映射
   - ✅ 基本的关联查询

3. **添加任务管理页面**
   - ✅ 任务列表
   - ✅ 任务详情
   - ✅ 任务日志查看

### 阶段2: 增强功能（优先级：中）

**时间**: 2-3天

4. **添加遗址浏览页面**
   - 遗址列表和详情
   - 遗址结构树展示
   - 时期信息展示

5. **添加文物浏览页面**
   - 文物列表（陶器/玉器）
   - 文物详情
   - 图片展示
   - 高级筛选

6. **添加图片管理页面**
   - 图片列表
   - 图片详情
   - 图片-文物关联展示

### 阶段3: 高级功能（优先级：低）

**时间**: 2-3天

7. **添加首页Dashboard**
   - 系统概览
   - 统计数据
   - 快速操作

8. **添加数据分析页面**
   - 统计图表
   - 数据可视化
   - 批量导出

9. **优化用户体验**
   - 响应式设计
   - 加载优化
   - 错误提示优化

---

## 技术实现要点

### 1. 数据库访问层

创建`gui/db_helper.py`:

```python
import sqlite3
from typing import List, Dict, Optional

class DatabaseHelper:
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        pass
    
    def get_task_detail(self, task_id: str) -> Dict:
        """获取任务详情"""
        pass
    
    def get_all_sites(self) -> List[Dict]:
        """获取所有遗址"""
        pass
    
    def get_artifacts(self, artifact_type: str, filters: Dict) -> List[Dict]:
        """获取文物列表"""
        pass
    
    def get_artifact_images(self, artifact_id: int, artifact_type: str) -> List[Dict]:
        """获取文物图片"""
        pass
    
    # ... 更多查询方法
```

### 2. 工作流集成

修改抽取调用:

```python
from src.workflow import ExtractionWorkflow

def run_extraction_v3(report_folder, templates):
    workflow = ExtractionWorkflow()
    try:
        task_id = workflow.execute_full_extraction(
            report_folder,
            templates
        )
        return task_id
    finally:
        workflow.close()
```

### 3. 多页面架构

使用Streamlit的多页面功能:

```
gui/
├── app.py                    # 主入口（首页）
├── pages/
│   ├── 1_🏠_首页.py
│   ├── 2_🚀_数据抽取.py
│   ├── 3_📋_任务管理.py
│   ├── 4_🏛️_遗址浏览.py
│   ├── 5_🏺_文物浏览.py
│   ├── 6_📸_图片管理.py
│   ├── 7_📊_数据分析.py
│   └── 8_⚙️_系统设置.py
├── db_helper.py              # 数据库辅助类
└── utils.py                  # 工具函数
```

### 4. 列名映射

创建完整的列名映射:

```python
COLUMN_MAPPINGS = {
    'pottery_artifacts': {
        'id': 'ID',
        'artifact_code': '文物编号',
        'subtype': '器型',
        'clay_type': '陶土类型',
        'color': '颜色',
        'height': '高度',
        'diameter': '口径',
        # ... 所有字段
    },
    'jade_artifacts': {
        'id': 'ID',
        'artifact_code': '文物编号',
        'category_level1': '一级分类',
        'jade_type': '玉料类型',
        # ... 所有字段
    },
    # ... 其他表
}
```

---

## 预期效果

### 功能完整性
- ✅ 100%支持V3.0功能
- ✅ 多主体抽取
- ✅ 图片管理
- ✅ 关系展示

### 用户体验
- ✅ 清晰的导航
- ✅ 丰富的数据展示
- ✅ 直观的操作流程

### 性能
- ✅ 快速加载
- ✅ 分页显示
- ✅ 缓存优化

---

## 风险和挑战

1. **数据量大时的性能**
   - 解决方案: 分页、缓存、索引优化

2. **图片加载慢**
   - 解决方案: 缩略图、懒加载

3. **复杂查询的实现**
   - 解决方案: 预定义常用查询、SQL优化

4. **多页面状态管理**
   - 解决方案: 使用st.session_state

---

## 总结

当前GUI需要进行**重大升级**以适配V3.0：

### 必须修改（阶段1）
1. ❌ 数据抽取功能（调用workflow.py）
2. ❌ 数据库浏览（支持10个表）
3. ❌ 任务管理功能

### 建议添加（阶段2-3）
4. 遗址浏览
5. 文物浏览（含图片）
6. 图片管理
7. 数据分析
8. 首页Dashboard

**建议**: 先完成阶段1的核心功能适配，确保系统可用，然后逐步添加增强功能。

---

**文档版本**: V1.0  
**创建时间**: 2024-12-01  
**预计完成时间**: 5-7天（分3个阶段）

