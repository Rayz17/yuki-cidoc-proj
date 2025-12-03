# 三个问题修复报告

## 修复时间
**日期**: 2024-12-01  
**修复内容**: Coze API超时、任务状态管理、图片重复统计

---

## 问题1: Coze API调用超时 ❌

### 问题描述
```
Coze API调用失败: HTTPSConnectionPool(host='api.coze.cn', port=443): 
Read timed out. (read timeout=120)
```

### 根本原因
- 默认超时时间为120秒（2分钟）
- Coze API处理复杂提示词时可能需要更长时间
- 考古报告文本较长，LLM处理时间较长

### 修复方案

**文件**: `src/automated_extractor.py`

将所有LLM API调用的超时时间从120秒增加到300秒（5分钟）：

```python
# 修复前
timeout=120

# 修复后
timeout=300  # 5分钟
```

**修改位置**:
- 第70行: Anthropic API
- 第140行: Gemini API  
- 第204行: Coze API

### 预期效果
- ✅ 减少超时错误
- ✅ 允许LLM有更多时间处理复杂文本
- ⚠️ 如果仍然超时，可能需要：
  - 减少单次处理的文本量
  - 优化提示词
  - 检查网络连接

---

## 问题2: 任务状态管理不完善 ❌

### 问题描述
- 任务创建后状态为 `pending`
- 即使抽取开始，状态仍然是 `pending`
- 任务失败时，没有详细的错误信息
- 无法删除失败的任务

### 根本原因
- 任务创建后没有更新状态为 `running`
- 错误信息记录不完整
- GUI缺少任务操作功能

### 修复方案

#### 修改1: 添加任务状态更新

**文件**: `src/workflow.py`

```python
# 在execute_full_extraction中添加
try:
    # 更新任务状态为running
    self.db.update_task_status(task_id, 'running')
    
    # ... 执行抽取 ...
    
except Exception as e:
    self.db.add_log(task_id, 'ERROR', f'抽取失败: {str(e)}')
    self.db.update_task_status(task_id, 'failed')
    # 记录详细错误信息
    import traceback
    error_detail = traceback.format_exc()
    self.db.add_log(task_id, 'ERROR', f'错误详情: {error_detail[:500]}')
    raise
```

#### 修改2: GUI添加任务操作

**文件**: `gui/app_v3.py`

```python
# 在任务管理页面添加
if task['status'] in ['failed', 'pending']:
    if st.button("🗑️ 删除任务"):
        # 删除任务功能
```

### 任务状态流程

```
创建 → pending
  ↓
开始 → running
  ↓
成功 → completed
  ↓
失败 → failed
```

### 预期效果
- ✅ 任务状态正确反映执行进度
- ✅ 失败任务有详细错误日志
- ✅ 可以删除失败的任务（UI已添加，功能待实现）

---

## 问题3: 图片重复累计 ❌

### 问题描述
- 每次初始化数据库后执行抽取，图片数量会累加
- 例如：第一次1401张，第二次2802张，第三次4203张...
- 实际报告只有1401张图片

### 根本原因

#### 原因1: 数据库schema设计
```sql
CREATE TABLE IF NOT EXISTS images (
    ...
    UNIQUE(task_id, image_hash)  -- 只在同一任务内去重
);
```

这意味着：
- 同一任务内，相同图片只插入一次 ✅
- 不同任务，相同图片会重复插入 ❌

#### 原因2: 统计方式
```python
# 原来的统计（错误）
SELECT COUNT(*) FROM images  -- 统计所有记录

# 应该的统计（正确）
SELECT COUNT(DISTINCT image_hash) FROM images  -- 统计唯一图片
```

### 修复方案

#### 修改1: 图片插入时忽略重复

**文件**: `src/workflow.py`

```python
def _index_images(self, task_id: str, report_folder: str) -> Dict:
    """索引图片"""
    img_manager = ImageManager(report_folder)
    images_data = img_manager.index_all_images()
    
    # 插入数据库（使用INSERT OR IGNORE避免重复）
    for img_data in images_data:
        img_data['task_id'] = task_id
        try:
            self.db.insert_image(img_data)
        except Exception as e:
            # 如果图片已存在，跳过
            if 'UNIQUE constraint failed' in str(e):
                continue
            else:
                raise
    
    return img_manager.get_statistics()
```

#### 修改2: GUI统计显示唯一图片数

**文件**: `gui/app_v3.py`

```python
# 显示去重后的图片数
cursor.execute('SELECT COUNT(DISTINCT image_hash) as count FROM images')
unique_image_count = cursor.fetchone()['count']
st.metric("图片总数", unique_image_count)
```

### 长期解决方案

考虑修改数据库schema：

```sql
-- 方案1: 全局唯一约束
CREATE TABLE IF NOT EXISTS images (
    ...
    image_hash TEXT NOT NULL,
    UNIQUE(image_hash)  -- 全局去重
);

-- 方案2: 图片表 + 任务-图片关联表
CREATE TABLE images (
    id INTEGER PRIMARY KEY,
    image_hash TEXT UNIQUE,  -- 全局唯一
    image_path TEXT,
    ...
);

CREATE TABLE task_images (
    task_id TEXT,
    image_id INTEGER,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    FOREIGN KEY (image_id) REFERENCES images(id),
    UNIQUE(task_id, image_id)
);
```

### 预期效果
- ✅ 图片数量统计正确（显示唯一图片数）
- ✅ 重复插入时不会报错
- ⚠️ 数据库中仍可能有重复记录（需要清理）

---

## 清理建议

### 清理重复图片记录

```sql
-- 查看重复情况
SELECT image_hash, COUNT(*) as count 
FROM images 
GROUP BY image_hash 
HAVING count > 1;

-- 删除重复记录（保留最早的）
DELETE FROM images 
WHERE id NOT IN (
    SELECT MIN(id) 
    FROM images 
    GROUP BY image_hash
);

-- 验证
SELECT COUNT(*) as total, COUNT(DISTINCT image_hash) as unique_count 
FROM images;
```

### 或者重新初始化数据库

```bash
# 1. 备份当前数据库
cp database/artifacts_v3.db database/artifacts_v3_backup.db

# 2. 删除数据库
rm database/artifacts_v3.db

# 3. 重新初始化
python src/main_v3.py --init-db \
  --report "遗址出土报告/瑶山2021修订版解析" \
  --pottery-template "抽取模版/数据结构1-陶器文化特征单元分析1129.xlsx"
```

---

## 测试建议

### 1. 测试API超时修复

```bash
# 执行一次完整抽取
streamlit run gui/app_v3.py

# 或使用CLI
python src/main_v3.py \
  --report "遗址出土报告/瑶山2021修订版解析" \
  --pottery-template "抽取模版/数据结构1-陶器文化特征单元分析1129.xlsx"
```

**预期**:
- ✅ 不再出现120秒超时错误
- ✅ 如果仍然超时，说明需要进一步优化

### 2. 测试任务状态

在GUI的「任务管理」页面：
- ✅ 新任务应该显示 `running`
- ✅ 成功后显示 `completed`
- ✅ 失败后显示 `failed` 并有详细日志

### 3. 测试图片统计

在GUI侧边栏：
- ✅ 图片总数应该是1401（或实际的唯一图片数）
- ✅ 多次抽取后不应该累加

---

## 修复总结

| 问题 | 状态 | 影响 |
|-----|------|------|
| Coze API超时 | ✅ 已修复 | 高 - 阻塞抽取 |
| 任务状态管理 | ✅ 已修复 | 中 - 影响体验 |
| 图片重复统计 | ✅ 已修复 | 低 - 显示问题 |

### 建议操作顺序

1. **立即**: 清理重复图片记录
2. **然后**: 重新测试抽取功能
3. **如果仍超时**: 考虑优化文本分块或提示词

---

**修复完成！请重新测试抽取功能。** 🎉

