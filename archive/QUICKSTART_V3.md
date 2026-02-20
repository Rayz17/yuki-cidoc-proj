# V3.0 快速开始指南

## 5分钟快速上手

### 步骤1: 安装依赖 (1分钟)

```bash
cd /Users/rayz/Downloads/yuki-cidoc-proj

# 激活虚拟环境
source venv/bin/activate

# 确认依赖已安装
pip list | grep -E "pandas|openpyxl|requests|streamlit|Pillow"
```

### 步骤2: 配置LLM (1分钟)

确认 `config.json` 配置正确：

```bash
cat config.json
```

应该看到：
```json
{
  "provider": "coze",
  "api_url": "https://api.coze.cn",
  "bot_id": "7563628511874203694",
  "api_key": "pat_GBm4NGk0oClLti2G87VL7JieYVEhOyNzg91ri3BqsQQFCdAG3CxATu3tqleELyQJ",
  ...
}
```

### 步骤3: 初始化数据库 (30秒)

```bash
python src/main_v3.py \
  --init-db \
  --report "遗址出土报告/瑶山2021修订版解析" \
  --jade-template "抽取模版/数据结构2-玉器文化特征单元分析1129.xlsx"
```

### 步骤4: 执行抽取 (2-5分钟，取决于LLM速度)

```bash
python src/main_v3.py \
  --report "遗址出土报告/瑶山2021修订版解析" \
  --jade-template "抽取模版/数据结构2-玉器文化特征单元分析1129.xlsx"
```

### 步骤5: 查看结果 (1分钟)

#### 方式1: 命令行查看

```bash
sqlite3 database/artifacts_v3.db << EOF
SELECT COUNT(*) as jade_count FROM jade_artifacts;
SELECT artifact_code, subtype, jade_type FROM jade_artifacts LIMIT 5;
EOF
```

#### 方式2: GUI查看

```bash
streamlit run gui/app.py
```

然后在浏览器中访问 `http://localhost:8501`

---

## 完整示例：抽取所有主体

```bash
python src/main_v3.py \
  --report "遗址出土报告/瑶山2021修订版解析" \
  --site-template "抽取模版/数据结构3-遗址属性和类分析1129.xlsx" \
  --period-template "抽取模版/数据结构4-时期属性和类分析1129.xlsx" \
  --pottery-template "抽取模版/数据结构1-陶器文化特征单元分析1129.xlsx" \
  --jade-template "抽取模版/数据结构2-玉器文化特征单元分析1129.xlsx"
```

---

## 常见问题

**Q: 报错 "ModuleNotFoundError"**  
A: 确保激活了虚拟环境: `source venv/bin/activate`

**Q: 报错 "FileNotFoundError"**  
A: 检查报告路径和模板路径是否正确

**Q: LLM调用失败**  
A: 检查 `config.json` 中的API密钥是否有效

**Q: 抽取结果为空**  
A: 查看日志: `sqlite3 database/artifacts_v3.db "SELECT * FROM extraction_logs WHERE log_level='ERROR'"`

---

## 下一步

- 阅读完整手册: `MANUAL_V3.md`
- 运行测试: `TEST_V3.md`
- 查看设计文档: `DESIGN_V2.md`, `DATABASE_DESIGN_V3_FINAL.md`

---

**版本**: V3.0  
**更新**: 2024-12-01

