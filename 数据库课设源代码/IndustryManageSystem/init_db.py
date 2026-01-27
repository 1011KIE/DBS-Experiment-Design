"""
数据库初始化脚本
创建表结构和索引（符合openGauss规范）
"""

# 在导入其他模块之前，先应用openGauss版本解析补丁
import opengauss_dialect_patch  # 修复SQLAlchemy无法解析openGauss版本字符串的问题

from app import create_app
from models import db
from sqlalchemy import text
import os


def init_database():
    """初始化数据库（openGauss兼容）"""
    app = create_app()

    with app.app_context():
        # 创建所有表
        db.create_all()
        print("数据库表创建完成")

        # 确保energy表使用列存储（openGauss特性）
        try:
            with db.engine.connect() as conn:
                # 检查表是否已存在且不是列存储
                result = conn.execute(text("""
                    SELECT tablename, tableoptions 
                    FROM pg_tables 
                    WHERE schemaname = 'public' AND tablename = 'energy'
                """))
                
                # 尝试转换为列存储（如果支持）
                try:
                    conn.execute(text("ALTER TABLE energy SET (ORIENTATION = COLUMN)"))
                    conn.commit()
                    print("energy表已设置为列存储（openGauss）")
                except Exception as e:
                    print(f"设置列存储失败（可能已设置或不支持）: {e}")
        except Exception as e:
            print(f"检查列存储状态失败: {e}")

        # 创建联合索引（符合需求文档）
        try:
            with db.engine.connect() as conn:
                # 创建符合需求文档的联合索引：idx_energy_point_time
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_energy_point_time 
                    ON energy (point_id, collect_time)
                """))
                conn.commit()
                print("联合索引创建完成")
        except Exception as e:
            # 如果point_id不存在，使用point_code（兼容现有结构）
            try:
                with db.engine.connect() as conn:
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_energy_point_time 
                        ON energy (point_code, collection_time)
                    """))
                    conn.commit()
                    print("联合索引创建完成（使用point_code）")
            except Exception as e2:
                print(f"创建联合索引失败: {e2}")

        # 检查表数量
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"创建的数据库表: {tables}")

        # 检查索引
        for table_name in tables:
            indexes = inspector.get_indexes(table_name)
            print(f"表 {table_name} 的索引: {indexes}")


if __name__ == '__main__':
    init_database()