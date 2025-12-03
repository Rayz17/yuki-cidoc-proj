# V3.0 系统测试指南

## 测试准备

### 1. 环境检查

```bash
# 激活虚拟环境
source venv/bin/activate

# 检查依赖
pip list | grep -E "pandas|openpyxl|requests|streamlit|Pillow"
```

### 2. 数据准备

确保以下文件存在：

- 报告：`遗址出土报告/瑶山2021修订版解析/`
  - `full.md`
  - `images/` 文件夹
  - `*_content_list.json`

- 模板：`抽取模版/`
  - `数据结构1-陶器文化特征单元分析1129.xlsx`
  - `数据结构2-玉器文化特征单元分析1129.xlsx`
  - `数据结构3-遗址属性和类分析1129.xlsx`
  - `数据结构4-时期属性和类分析1129.xlsx`

## 单元测试

### 测试1: 数据库管理器

```bash
python src/database_manager_v3.py
```

预期输出：
```
✅ 数据库初始化完成: database/test_v3.db
✅ 创建任务: task_20241201_xxx
任务信息: 测试报告, 状态: pending
✅ 数据库管理器测试完成
```

### 测试2: 图片管理器

```bash
python src/image_manager.py
```

预期输出：
```
✅ 已加载 content_list.json，共 xxxx 项
图片统计:
  总数: xxxx
  总大小: xx.xx MB
  有content_list: True
✅ 图片管理器测试完成
```

### 测试3: 模板分析器

```bash
python src/template_analyzer.py
```

预期输出：
```
模板分析完成
  字段数: xx
  文物类型: ['陶器']
  数据库字段: {...}
✅ 模板分析器测试完成
```

### 测试4: 提示词生成器

```bash
python src/prompt_generator.py
```

预期输出：
```
============================================================
测试陶器提示词生成
============================================================
# 陶器文物信息抽取任务
...
✅ 陶器提示词生成成功
```

### 测试5: 文物合并器

```bash
python src/artifact_merger.py
```

预期输出：
```
============================================================
原始数据:
============================================================
...
合并统计:
原始数量: 4
合并后数量: 2
减少数量: 2
减少比例: 50.0%
✅ 文物合并器测试完成
```

## 集成测试

### 测试6: 完整工作流（仅玉器）

```bash
python src/main_v3.py \
  --init-db \
  --report "遗址出土报告/瑶山2021修订版解析" \
  --jade-template "抽取模版/数据结构2-玉器文化特征单元分析1129.xlsx" \
  --db "database/test_jade_only.db"
```

预期输出：
```
============================================================
考古文物数据抽取系统 V3.0
============================================================

📦 初始化数据库...
✅ 数据库初始化完成

📋 抽取配置:
  报告: 遗址出土报告/瑶山2021修订版解析
  数据库: database/test_jade_only.db
  模板:
    - 玉器: 数据结构2-玉器文化特征单元分析1129.xlsx

🚀 开始抽取...
------------------------------------------------------------
[日志输出...]
------------------------------------------------------------

✅ 抽取完成！
   任务ID: task_20241201_xxx

📊 抽取报告:
  陶器: 0件
  玉器: xx件 (含图片: xx件)
  图片: xxxx张

💾 数据已保存到: database/test_jade_only.db
   可使用GUI查看: streamlit run gui/app.py
```

### 测试7: 完整工作流（全部主体）

```bash
python src/main_v3.py \
  --report "遗址出土报告/瑶山2021修订版解析" \
  --site-template "抽取模版/数据结构3-遗址属性和类分析1129.xlsx" \
  --period-template "抽取模版/数据结构4-时期属性和类分析1129.xlsx" \
  --pottery-template "抽取模版/数据结构1-陶器文化特征单元分析1129.xlsx" \
  --jade-template "抽取模版/数据结构2-玉器文化特征单元分析1129.xlsx" \
  --db "database/test_full.db"
```

### 测试8: GUI界面

```bash
streamlit run gui/app.py
```

测试步骤：
1. 打开浏览器访问 `http://localhost:8501`
2. 查看配置页面
3. 浏览数据库（选择 `database/test_full.db`）
4. 检查数据显示是否正常
5. 尝试导出CSV

## 数据验证

### 验证1: 数据库完整性

```bash
sqlite3 database/test_full.db << EOF
-- 检查表结构
.tables

-- 检查任务
SELECT task_id, report_name, status, total_pottery, total_jade FROM extraction_tasks;

-- 检查遗址
SELECT site_name, culture_name FROM sites;

-- 检查时期
SELECT period_name, time_span_start, time_span_end FROM periods;

-- 检查陶器
SELECT COUNT(*) as pottery_count FROM pottery_artifacts;

-- 检查玉器
SELECT COUNT(*) as jade_count FROM jade_artifacts;

-- 检查图片
SELECT COUNT(*) as image_count FROM images;

-- 检查图片关联
SELECT 
  artifact_type,
  COUNT(*) as link_count
FROM artifact_images
GROUP BY artifact_type;

EOF
```

### 验证2: 数据质量

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('database/test_full.db')

# 检查玉器数据完整性
df = pd.read_sql('SELECT * FROM jade_artifacts', conn)
print("玉器数据:")
print(f"  总数: {len(df)}")
print(f"  有artifact_code: {df['artifact_code'].notna().sum()}")
print(f"  有图片: {df['has_images'].sum()}")
print(f"  字段填充率:")
for col in ['subtype', 'jade_type', 'jade_color', 'dimensions']:
    rate = df[col].notna().sum() / len(df) * 100
    print(f"    {col}: {rate:.1f}%")

# 检查图片关联
df_links = pd.read_sql('''
  SELECT 
    ai.artifact_code,
    COUNT(*) as image_count,
    AVG(ai.confidence) as avg_confidence
  FROM artifact_images ai
  GROUP BY ai.artifact_code
''', conn)
print(f"\n图片关联:")
print(f"  关联文物数: {len(df_links)}")
print(f"  平均图片数: {df_links['image_count'].mean():.1f}")
print(f"  平均置信度: {df_links['avg_confidence'].mean():.2f}")

conn.close()
```

## 性能测试

### 测试9: 处理时间

```bash
time python src/main_v3.py \
  --report "遗址出土报告/瑶山2021修订版解析" \
  --jade-template "抽取模版/数据结构2-玉器文化特征单元分析1129.xlsx" \
  --db "database/test_perf.db"
```

记录：
- 总时间
- 图片索引时间
- LLM调用次数
- 平均每次LLM调用时间

### 测试10: 内存使用

```bash
/usr/bin/time -l python src/main_v3.py \
  --report "遗址出土报告/瑶山2021修订版解析" \
  --jade-template "抽取模版/数据结构2-玉器文化特征单元分析1129.xlsx" \
  --db "database/test_mem.db"
```

## 错误处理测试

### 测试11: 缺失文件

```bash
# 测试缺失报告
python src/main_v3.py \
  --report "不存在的路径" \
  --jade-template "抽取模版/数据结构2-玉器文化特征单元分析1129.xlsx"

# 预期：显示错误信息并退出
```

### 测试12: 无效模板

```bash
# 测试无效模板
python src/main_v3.py \
  --report "遗址出土报告/瑶山2021修订版解析" \
  --jade-template "不存在的模板.xlsx"

# 预期：显示错误信息并退出
```

### 测试13: LLM错误

```bash
# 临时修改config.json使用无效的API密钥
# 然后运行抽取

# 预期：记录错误日志，任务状态为failed
```

## 回归测试

### 测试14: 与V2.0对比

如果有V2.0的数据：

```sql
-- 比较抽取结果数量
SELECT 
  'V2.0' as version,
  COUNT(*) as count
FROM v2_artifacts
UNION ALL
SELECT 
  'V3.0' as version,
  COUNT(*) as count
FROM jade_artifacts;

-- 比较字段完整性
-- ...
```

## 测试检查清单

- [ ] 所有单元测试通过
- [ ] 玉器单独抽取成功
- [ ] 完整抽取（四主体）成功
- [ ] GUI正常显示数据
- [ ] 数据库结构正确
- [ ] 图片索引正常
- [ ] 图片关联有效
- [ ] 信息合并正确
- [ ] 错误处理正常
- [ ] 日志记录完整
- [ ] 性能可接受
- [ ] 文档完整准确

## 测试报告模板

```markdown
# V3.0 测试报告

**测试日期**: 2024-12-01
**测试人员**: [姓名]
**测试环境**: macOS / Python 3.x

## 测试结果

| 测试项 | 状态 | 备注 |
|-------|------|------|
| 数据库管理器 | ✅ | |
| 图片管理器 | ✅ | |
| 模板分析器 | ✅ | |
| 提示词生成器 | ✅ | |
| 文物合并器 | ✅ | |
| 玉器抽取 | ✅ | 抽取xx件 |
| 完整抽取 | ✅ | 遗址1个，时期x个，陶器xx件，玉器xx件 |
| GUI | ✅ | |
| 图片关联 | ✅ | 关联率xx% |

## 性能数据

- 总处理时间: xx分钟
- 图片索引: xx秒
- LLM调用: xx次
- 内存使用: xxMB

## 发现的问题

1. [问题描述]
2. ...

## 建议

1. [改进建议]
2. ...
```

---

**测试版本**: V3.0  
**更新时间**: 2024-12-01

