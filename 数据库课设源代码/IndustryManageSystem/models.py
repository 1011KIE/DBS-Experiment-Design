from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class MonitorPoint(db.Model):
    __tablename__ = 'monitor_point'

    id = db.Column(db.Integer, primary_key=True)
    point_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    equipment_name = db.Column(db.String(100), nullable=False)
    workshop = db.Column(db.String(100), nullable=False)
    energy_type = db.Column(db.String(50), nullable=False)  # 电力、水资源等
    unit = db.Column(db.String(20), nullable=False)  # kWh, m³等
    threshold = db.Column(db.Float, nullable=False)  # 单日能耗阈值
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联能耗记录（使用primaryjoin指定关联条件，因为外键在表创建后添加）
    energy_records = db.relationship(
        'EnergyRecord', 
        backref='monitor_point', 
        lazy=True,
        primaryjoin='MonitorPoint.point_code == EnergyRecord.point_code',
        foreign_keys='EnergyRecord.point_code'
    )

    def to_dict(self):
        return {
            'id': self.id,
            'point_code': self.point_code,
            'equipment_name': self.equipment_name,
            'workshop': self.workshop,
            'energy_type': self.energy_type,
            'unit': self.unit,
            'threshold': self.threshold,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class EnergyRecord(db.Model):
    __tablename__ = 'energy'

    # 注意：根据需求文档，record_id应该是BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
    # 但为了兼容SQLAlchemy和现有代码，这里使用id作为主键，record_id作为业务标识
    # 如果需要完全符合需求文档，需要在数据库初始化脚本中手动创建表
    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.String(50), unique=True, nullable=False)
    # 注意：psycopg3不支持在CREATE TABLE中直接使用外键，需要在表创建后通过ALTER TABLE添加
    point_code = db.Column(db.String(50), nullable=False)  # 外键将在表创建后添加
    collection_time = db.Column(db.DateTime, nullable=False, index=True)  # 用于联合索引
    energy_value = db.Column(db.Float, nullable=False)
    collection_status = db.Column(db.String(20), default='normal')  # normal, abnormal, missing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 联合索引（列存储通过DDL事件在表创建后设置）
    __table_args__ = (
        db.Index('idx_energy_point_time', 'point_code', 'collection_time'),  # 符合需求文档的索引名
    )

    def to_dict(self):
        return {
            'id': self.id,
            'record_id': self.record_id,
            'point_code': self.point_code,
            'collection_time': self.collection_time.isoformat() if self.collection_time else None,
            'energy_value': self.energy_value,
            'collection_status': self.collection_status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# 新增表：设备维护记录
class EquipmentMaintenance(db.Model):
    __tablename__ = 'equipment_maintenance'

    id = db.Column(db.Integer, primary_key=True)
    maintenance_id = db.Column(db.String(50), unique=True, nullable=False)
    # 注意：psycopg3不支持在CREATE TABLE中直接使用外键，需要在表创建后通过ALTER TABLE添加
    point_code = db.Column(db.String(50), nullable=False)  # 外键将在表创建后添加
    maintenance_type = db.Column(db.String(50), nullable=False)  # 日常维护、故障维修、定期检修
    maintenance_date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Text)
    cost = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='completed')  # planned, in_progress, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_maintenance_date_point_code', 'maintenance_date', 'point_code'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'maintenance_id': self.maintenance_id,
            'point_code': self.point_code,
            'maintenance_type': self.maintenance_type,
            'maintenance_date': self.maintenance_date.isoformat() if self.maintenance_date else None,
            'description': self.description,
            'cost': self.cost,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# 新增表：能耗成本表
class EnergyCost(db.Model):
    __tablename__ = 'energy_cost'

    id = db.Column(db.Integer, primary_key=True)
    cost_id = db.Column(db.String(50), unique=True, nullable=False)
    energy_type = db.Column(db.String(50), nullable=False)
    unit_price = db.Column(db.Float, nullable=False)  # 单价（元/单位）
    effective_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_energy_type_effective_date', 'energy_type', 'effective_date'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'cost_id': self.cost_id,
            'energy_type': self.energy_type,
            'unit_price': self.unit_price,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# 新增表：报警记录表
class AlertRecord(db.Model):
    __tablename__ = 'alert_record'

    id = db.Column(db.Integer, primary_key=True)
    alert_id = db.Column(db.String(50), unique=True, nullable=False)
    # 注意：psycopg3不支持在CREATE TABLE中直接使用外键，需要在表创建后通过ALTER TABLE添加
    point_code = db.Column(db.String(50), nullable=False)  # 外键将在表创建后添加
    alert_type = db.Column(db.String(50), nullable=False)  # threshold_exceeded, equipment_failure, etc.
    alert_time = db.Column(db.DateTime, nullable=False)
    energy_value = db.Column(db.Float)
    threshold = db.Column(db.Float)
    description = db.Column(db.Text)
    severity = db.Column(db.String(20), default='medium')  # low, medium, high, critical
    status = db.Column(db.String(20), default='active')  # active, acknowledged, resolved
    resolved_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_alert_time_point_code', 'alert_time', 'point_code'),
        db.Index('idx_alert_status', 'status'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'alert_id': self.alert_id,
            'point_code': self.point_code,
            'alert_type': self.alert_type,
            'alert_time': self.alert_time.isoformat() if self.alert_time else None,
            'energy_value': self.energy_value,
            'threshold': self.threshold,
            'description': self.description,
            'severity': self.severity,
            'status': self.status,
            'resolved_time': self.resolved_time.isoformat() if self.resolved_time else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# 新增表：预测结果表
class PredictionResult(db.Model):
    __tablename__ = 'prediction_result'

    id = db.Column(db.Integer, primary_key=True)
    prediction_id = db.Column(db.String(50), unique=True, nullable=False)
    # 注意：psycopg3不支持在CREATE TABLE中直接使用外键，需要在表创建后通过ALTER TABLE添加
    point_code = db.Column(db.String(50), nullable=False)  # 外键将在表创建后添加
    prediction_time = db.Column(db.DateTime, nullable=False)
    predicted_value = db.Column(db.Float, nullable=False)
    confidence_interval = db.Column(db.Float)  # 置信区间
    model_type = db.Column(db.String(50), default='db4ai')  # db4ai, linear_regression, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_prediction_time_point_code', 'prediction_time', 'point_code'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'prediction_id': self.prediction_id,
            'point_code': self.point_code,
            'prediction_time': self.prediction_time.isoformat() if self.prediction_time else None,
            'predicted_value': self.predicted_value,
            'confidence_interval': self.confidence_interval,
            'model_type': self.model_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# 新增表：异常检测结果表
class AnomalyDetection(db.Model):
    __tablename__ = 'anomaly_detection'

    id = db.Column(db.Integer, primary_key=True)
    detection_id = db.Column(db.String(50), unique=True, nullable=False)
    # 注意：psycopg3不支持在CREATE TABLE中直接使用外键，需要在表创建后通过ALTER TABLE添加
    point_code = db.Column(db.String(50), nullable=False)  # 外键将在表创建后添加
    detection_time = db.Column(db.DateTime, nullable=False)
    energy_value = db.Column(db.Float, nullable=False)
    anomaly_score = db.Column(db.Float, nullable=False)  # 异常得分
    is_anomaly = db.Column(db.Boolean, default=False)
    detection_method = db.Column(db.String(50), default='db4ai')  # db4ai, threshold, statistical
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('idx_detection_time_point_code', 'detection_time', 'point_code'),
        db.Index('idx_is_anomaly', 'is_anomaly'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'detection_id': self.detection_id,
            'point_code': self.point_code,
            'detection_time': self.detection_time.isoformat() if self.detection_time else None,
            'energy_value': self.energy_value,
            'anomaly_score': self.anomaly_score,
            'is_anomaly': self.is_anomaly,
            'detection_method': self.detection_method,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }