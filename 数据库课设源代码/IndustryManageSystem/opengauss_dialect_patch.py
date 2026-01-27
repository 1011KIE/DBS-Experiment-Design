# -*- coding: utf-8 -*-
"""
openGauss版本字符串解析补丁
修复SQLAlchemy无法解析openGauss版本字符串的问题
"""

from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy import text
import re


def _get_server_version_info_opengauss(self, connection):
    """
    自定义的openGauss版本解析函数
    修复SQLAlchemy无法解析openGauss版本字符串的问题
    """
    try:
        # 获取版本字符串
        if hasattr(connection, 'execute'):
            result = connection.execute(text("SELECT version()"))
            version_string = result.scalar()
        else:
            # 如果connection是原始连接对象
            cursor = connection.cursor()
            cursor.execute("SELECT version()")
            version_string = cursor.fetchone()[0]
            cursor.close()
        
        # openGauss版本字符串格式示例：
        # " (openGauss 1.0.0 build Obd0ce80) compiled at 2020-06-30 18:19:27 commit 0 last mr on x86_64-unknown-linux-gnu, compiled by g++ (GCC) 8.2.0, 64-bit"
        # 或
        # "openGauss 5.0.0 build 12345f8c compiled at 2024-01-01 12:00:00 commit 12345 last mr on x86_64-unknown-linux-gnu, compiled by g++ (GCC) 8.2.0, 64-bit"
        
        # 尝试提取版本号
        match = re.search(r'openGauss\s+(\d+)\.(\d+)\.(\d+)', version_string, re.IGNORECASE)
        if match:
            major, minor, patch = map(int, match.groups())
            return (major, minor, patch)
        
        # 如果无法解析，返回一个兼容的版本号（假设是PostgreSQL 12兼容）
        # 这样可以避免AssertionError，但某些功能可能不可用
        # openGauss通常兼容PostgreSQL 12+
        return (12, 0, 0)
    except Exception as e:
        # 如果出现任何错误，返回默认版本号
        print(f"警告：无法解析openGauss版本，使用默认版本号: {e}")
        return (12, 0, 0)


# 应用补丁
PGDialect._get_server_version_info = _get_server_version_info_opengauss

