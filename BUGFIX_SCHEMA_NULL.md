# 数据库 Schema 修复 (NOT NULL Constraint Fix)

## 问题描述
任务失败，报错信息：`sqlite3.IntegrityError: NOT NULL constraint failed: pottery_artifacts.site_id`。

## 原因分析
1.  用户在抽取时未选择“遗址模板”，导致 `site_id` 为空 (`None`)。
2.  数据库 Schema 中，`pottery_artifacts` 和 `jade_artifacts` 表的 `site_id` 字段被定义为 `NOT NULL`，导致插入失败。

## 修复方案
修改了 `database/schema_v3.sql`，移除了 `site_id` 的 `NOT NULL` 约束。

```sql
-- 修改前
site_id INTEGER NOT NULL,

-- 修改后
site_id INTEGER,
```

## 必须执行的操作
**请务必在 GUI 中点击“初始化数据库”按钮！**
因为 SQLite 不会自动应用 Schema 更改到已存在的表，必须重新初始化数据库以重建表结构。

---

**重新初始化数据库后，请再次运行抽取任务。** 🚀

