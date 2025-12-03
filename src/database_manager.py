"""
一个用于管理SQLite数据库的简单工具。
"""

import sqlite3

class DatabaseManager:
    """
    用于连接和操作SQLite数据库的类。
    """
    def __init__(self, db_path='database/artifacts.db'):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """建立与数据库的连接。"""
        self.conn = sqlite3.connect(self.db_path)

    def create_table(self):
        """为文物数据创建一个表。"""
        if not self.conn:
            raise Exception('Database not connected. Call `connect()` first.')

        cursor = self.conn.cursor()
        # 简化表：为了适应多种文物类型，我们使用泛化的列
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artifact_code TEXT UNIQUE,
                artifact_type TEXT,
                subtype TEXT,
                material_type TEXT,
                process TEXT,
                found_in_tomb TEXT
            )
        ''')
        self.conn.commit()

    def insert_artifact(self, artifact_data: dict):
        """
        插入一个文物实例。

        Args:
            artifact_data (dict): 包含文物数据的字典。
        """
        cursor = self.conn.cursor()
        # 使用 INSERT OR IGNORE 来防止重复数据
        cursor.execute('''
            INSERT OR IGNORE INTO artifacts
            (artifact_code, artifact_type, subtype, material_type, process, found_in_tomb)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            artifact_data.get('单品编码'),
            artifact_data.get('文物类型'),
            artifact_data.get('子类型'),
            artifact_data.get('材料种类'),
            artifact_data.get('工艺'),
            artifact_data.get('found_in_tomb') # 这个字段需要在抽取时传入
        ))
        self.conn.commit()

    def close(self):
        """关闭数据库连接。"""
        if self.conn:
            self.conn.close()

# 示例用法
# db = DatabaseManager()
# db.connect()
# db.create_table()
# db.insert_artifact({'单品编码': 'M1:1', '文物类型': '陶器', '子类型': '陶豆', ...})
# db.close()