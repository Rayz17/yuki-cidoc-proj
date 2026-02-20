# 数据库约束修复 (Database Constraint Fix)

## 问题描述
用户报告 `sqlite3.IntegrityError: NOT NULL constraint failed: pottery_artifacts.site_id`。
这表明数据库表结构强制 `site_id` 不能为空，但当用户选择“不抽取遗址”时，该字段为 None，导致插入失败。

## 原因分析
虽然最新的 `schema_v3.sql` 中 `site_id` 允许为空，但由于 `CREATE TABLE IF NOT EXISTS` 机制，**现有的数据库文件保留了旧版本的表结构**（旧版本可能设置了 NOT NULL）。
代码更新不会自动修改已存在的 SQLite 表结构。

## 修复方案
1.  **备份并移除了旧数据库**：`database/artifacts_v3.db` 已重命名备份。
2.  **重新初始化了数据库**：使用最新的 Schema 重新创建了数据库文件。现在 `pottery_artifacts` 表允许 `site_id` 为空。

## 综合修复效果
结合之前的“自动字段过滤”修复：
1.  **字段名不匹配**（如 `additives`）：会被自动忽略，不再报错。
2.  **遗址ID为空**：会被允许（存储为 NULL），不再报错。

---

**请重启 GUI 并重新运行抽取任务。这次应该畅通无阻！** 🚀

