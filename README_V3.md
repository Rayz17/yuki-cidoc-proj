# 考古文物数据抽取系统 V3.0

## 项目简介

基于大语言模型（LLM）的考古文物信息自动抽取系统，支持从考古报告中抽取遗址、时期、陶器、玉器四大主体的详细信息，并自动关联图片。

## 主要特性

- 🏛️ **多主体抽取**: 遗址、时期、陶器、玉器
- 🔗 **关系管理**: 自动建立主体间的关联
- 📸 **图片索引**: 智能关联文物与图片
- 🔄 **信息合并**: 跨文本块信息整合
- 📋 **模板驱动**: Excel模板定义抽取字段
- 🤖 **LLM支持**: Coze/Gemini/Anthropic

## 快速开始

```bash
# 1. 安装依赖
source venv/bin/activate
pip install -r requirements.txt

# 2. 初始化数据库
python src/main_v3.py --init-db \
  --report "遗址出土报告/瑶山2021修订版解析" \
  --jade-template "抽取模版/数据结构2-玉器文化特征单元分析1129.xlsx"

# 3. 执行抽取
python src/main_v3.py \
  --report "遗址出土报告/瑶山2021修订版解析" \
  --jade-template "抽取模版/数据结构2-玉器文化特征单元分析1129.xlsx"

# 4. 查看结果
streamlit run gui/app.py
```

详见: [快速开始指南](QUICKSTART_V3.md)

## 项目结构

```
yuki-cidoc-proj/
├── src/                          # 源代码
│   ├── main_v3.py               # 主程序V3
│   ├── workflow.py              # 工作流编排器
│   ├── database_manager_v3.py   # 数据库管理器V3
│   ├── image_manager.py         # 图片管理器
│   ├── image_linker.py          # 图片关联器
│   ├── template_analyzer.py     # 模板分析器
│   ├── prompt_generator.py      # 提示词生成器
│   ├── artifact_merger.py       # 信息合并器
│   ├── content_extractor.py     # 文本分块器
│   └── automated_extractor.py   # LLM调用器
│
├── database/                     # 数据库
│   ├── schema_v3.sql            # 数据库结构V3
│   └── artifacts_v3.db          # SQLite数据库
│
├── gui/                          # 图形界面
│   └── app.py                   # Streamlit应用
│
├── 抽取模版/                     # Excel模板
│   ├── 数据结构1-陶器文化特征单元分析1129.xlsx
│   ├── 数据结构2-玉器文化特征单元分析1129.xlsx
│   ├── 数据结构3-遗址属性和类分析1129.xlsx
│   └── 数据结构4-时期属性和类分析1129.xlsx
│
├── 遗址出土报告/                 # 考古报告
│   └── 瑶山2021修订版解析/
│       ├── full.md              # 报告正文
│       ├── *_content_list.json  # 内容索引
│       └── images/              # 图片文件夹
│
├── config.json                   # LLM配置
├── requirements.txt              # Python依赖
│
├── MANUAL_V3.md                 # 使用手册
├── TEST_V3.md                   # 测试指南
├── QUICKSTART_V3.md             # 快速开始
├── DEVELOPMENT_SUMMARY_V3.md    # 开发总结
├── DESIGN_V2.md                 # 设计文档
├── DATABASE_DESIGN_V3_FINAL.md  # 数据库设计
└── IMPLEMENTATION_PLAN.md       # 实施计划
```

## 文档导航

### 用户文档
- [快速开始](QUICKSTART_V3.md) - 5分钟上手
- [使用手册](MANUAL_V3.md) - 完整功能说明
- [测试指南](TEST_V3.md) - 测试方法

### 开发文档
- [开发总结](DEVELOPMENT_SUMMARY_V3.md) - V3.0开发情况
- [设计文档](DESIGN_V2.md) - 系统设计
- [数据库设计](DATABASE_DESIGN_V3_FINAL.md) - 数据库结构
- [实施计划](IMPLEMENTATION_PLAN.md) - 开发计划

## 系统架构

```
┌─────────────────────────────────────────┐
│          应用层 (Application)            │
│  main_v3.py  │  gui/app.py              │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────┴───────────────────────┐
│        工作流层 (Workflow)               │
│  workflow.py - 流程编排                  │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────┴───────────────────────┐
│        处理层 (Processing)               │
│  prompt_generator.py - 提示词生成        │
│  artifact_merger.py  - 信息合并          │
│  image_linker.py     - 图片关联          │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────┴───────────────────────┐
│        管理层 (Management)               │
│  image_manager.py    - 图片管理          │
│  template_analyzer.py - 模板分析         │
│  content_extractor.py - 文本分块         │
│  automated_extractor.py - LLM调用        │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────┴───────────────────────┐
│        数据层 (Data)                     │
│  database_manager_v3.py - 数据库管理     │
│  schema_v3.sql - 数据库结构              │
└─────────────────────────────────────────┘
```

## 数据库结构

### 核心表

- `extraction_tasks` - 抽取任务
- `sites` - 遗址信息
- `site_structures` - 遗址结构
- `periods` - 时期信息
- `pottery_artifacts` - 陶器文物
- `jade_artifacts` - 玉器文物
- `images` - 图片索引
- `artifact_images` - 文物-图片关联
- `artifact_period_mapping` - 文物-时期关联
- `artifact_location_mapping` - 文物-位置关联

详见: [数据库设计文档](DATABASE_DESIGN_V3_FINAL.md)

## 工作流程

```
1. 创建任务
   ↓
2. 索引图片 (扫描images文件夹)
   ↓
3. 抽取遗址信息 (报告前5000字)
   ↓
4. 抽取时期信息 (报告中部)
   ↓
5. 按墓葬分块
   ↓
6. 逐块抽取陶器/玉器
   ↓
7. 合并同一文物信息
   ↓
8. 关联图片
   ↓
9. 保存到数据库
   ↓
10. 生成报告
```

## 技术栈

- **语言**: Python 3.8+
- **数据库**: SQLite
- **数据处理**: Pandas, OpenPyXL
- **图片处理**: Pillow
- **Web界面**: Streamlit
- **LLM**: Coze/Gemini/Anthropic API

## 开发状态

| 模块 | 状态 | 测试 |
|-----|------|------|
| 数据库层 | ✅ 完成 | ✅ 通过 |
| 图片处理层 | ✅ 完成 | ✅ 通过 |
| 模板处理层 | ✅ 完成 | ✅ 通过 |
| 信息处理层 | ✅ 完成 | ✅ 通过 |
| 工作流层 | ✅ 完成 | ⏳ 待测试 |
| 应用层 | ✅ 完成 | ⏳ 待测试 |
| 文档 | ✅ 完成 | - |

## 版本历史

### V3.0 (2024-12-01) - 当前版本
- ✅ 支持多主体（遗址、时期、陶器、玉器）
- ✅ 图片索引和关联
- ✅ 信息合并
- ✅ 模板驱动
- ✅ 完整工作流

### V2.0 (2024-11-XX)
- 支持陶器单主体抽取
- 基础数据库结构
- CLI和GUI界面

### V1.0 (2024-11-XX)
- 基础抽取功能
- Mock实现

## 下一步计划

### 短期（1周内）
- [ ] 完成集成测试
- [ ] 修复发现的bug
- [ ] 性能优化
- [ ] GUI适配V3数据库

### 中期（1月内）
- [ ] 支持更多文物类型
- [ ] 优化图片关联算法
- [ ] 增加数据导出功能
- [ ] 开发数据可视化

### 长期（3月内）
- [ ] 支持批量处理
- [ ] 开发Web API
- [ ] 集成更多LLM服务
- [ ] 机器学习辅助抽取

## 贡献指南

欢迎贡献代码、报告问题或提出建议！

## 许可证

[待定]

## 联系方式

[待定]

---

**版本**: V3.0  
**状态**: 开发完成，待集成测试  
**更新**: 2024-12-01

