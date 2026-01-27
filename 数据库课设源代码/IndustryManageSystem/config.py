import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard to guess string'
    # openGauss数据库连接格式（兼容PostgreSQL协议）
    # 格式：postgresql+psycopg://用户名:密码@主机:端口/数据库名（使用psycopg3）
    # 或：postgresql+psycopg2://用户名:密码@主机:端口/数据库名（使用psycopg2）
    # openGauss常用端口：5432（默认）或 26000（常见配置）
    # 注意：端口号可以根据实际部署情况自定义
    # 注意：psycopg3对openGauss的SASL认证支持更好
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql+psycopg://username:password@localhost:5432/industry_energy'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,  # 连接前检查连接是否有效
        'pool_recycle': 300,     # 连接回收时间（秒）
        'connect_args': {
            'connect_timeout': 10,  # 连接超时时间
            'application_name': 'IndustryEnergySystem',  # 应用名称
            'sslmode': 'disable'  # 禁用SSL（openGauss可能需要）
            # 注意：psycopg3不需要gssencmode参数
        }
    }