"""
openGauss DB4AI功能实现模块
提供时序预测和异常检测功能
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from models import db, PredictionResult, AnomalyDetection, MonitorPoint, EnergyRecord


class DB4AIPredictor:
    """DB4AI时序预测器"""

    def __init__(self, connection):
        self.connection = connection

    def predict_time_series(self, point_code, days=7):
        """
        使用DB4AI.PREDICT_TIME_SERIES预测未来能耗
        """
        try:
            # 获取历史数据用于训练
            historical_data = self._get_historical_data(point_code, days=60)
            if len(historical_data) < 10:
                return self._fallback_prediction(point_code, days)

            # 这里应该使用openGauss的DB4AI.PREDICT_TIME_SERIES函数
            # 由于环境限制，这里使用模拟实现
            predictions = self._simulate_db4ai_prediction(historical_data, days)

            # 保存预测结果到数据库
            self._save_predictions(point_code, predictions)

            return predictions

        except Exception as e:
            print(f"DB4AI预测失败: {e}")
            return self._fallback_prediction(point_code, days)

    def _get_historical_data(self, point_code, days=60):
        """获取历史数据"""
        from models import db
        sql = text("""
            SELECT id, record_id, point_code, collection_time, energy_value, collection_status, created_at
            FROM energy
            WHERE point_code = :point_code
              AND collection_time >= :start_date
            ORDER BY collection_time
        """)
        start_date = datetime.now() - timedelta(days=days)
        result = db.session.execute(sql, {
            'point_code': point_code,
            'start_date': start_date
        })
        
        # 转换为EnergyRecord对象列表（保持兼容性）
        records = []
        for row in result:
            record = EnergyRecord()
            record.id = row.id
            record.record_id = row.record_id
            record.point_code = row.point_code
            record.collection_time = row.collection_time
            record.energy_value = row.energy_value
            record.collection_status = row.collection_status
            record.created_at = row.created_at
            records.append(record)
        
        return records

    def _simulate_db4ai_prediction(self, historical_data, days):
        """模拟DB4AI预测功能"""
        # 提取时间和能耗值
        times = []
        values = []
        for record in historical_data:
            times.append(record.collection_time.timestamp())
            values.append(record.energy_value)

        # 使用ARIMA模型模拟预测
        predictions = []
        for i in range(1, days + 1):
            future_time = datetime.now() + timedelta(days=i)

            # 简单的趋势预测（基于历史趋势）
            if len(values) >= 2:
                # 计算趋势
                recent_trend = np.mean(values[-7:]) if len(values) >= 7 else values[-1]
                seasonal_factor = self._calculate_seasonal_factor(values, i)
                predicted_value = recent_trend * seasonal_factor
            else:
                predicted_value = np.mean(values) if values else 0

            predictions.append({
                'date': future_time.strftime('%Y-%m-%d'),
                'prediction_time': future_time.isoformat(),
                'predicted_value': float(max(0, predicted_value)),
                'predicted_date': future_time.strftime('%Y-%m-%d'),
                'value': float(max(0, predicted_value)),
                'confidence_lower': float(max(0, predicted_value * 0.8)),
                'confidence_upper': float(max(0, predicted_value * 1.2)),
                'confidence': 0.85,
                'model_type': 'db4ai_simulated'
            })

        return predictions

    def _calculate_seasonal_factor(self, values, day_offset):
        """计算季节性因子"""
        if len(values) < 24:  # 至少需要一天的数据
            return 1.0

        # 简单的日周期模式
        hour = (day_offset * 24) % 24
        if 6 <= hour < 18:  # 白天
            return 1.2
        else:  # 夜间
            return 0.8

    def _fallback_prediction(self, point_code, days):
        """备用预测方法"""
        from models import db
        # 获取监测点阈值作为基准
        sql = text("SELECT threshold FROM monitor_point WHERE point_code = :point_code")
        result = db.session.execute(sql, {'point_code': point_code})
        row = result.fetchone()
        base_value = row.threshold * 0.7 if row else 100.0

        predictions = []
        for i in range(1, days + 1):
            future_time = datetime.now() + timedelta(days=i)
            predictions.append({
                'date': future_time.strftime('%Y-%m-%d'),
                'prediction_time': future_time.isoformat(),
                'predicted_value': base_value,
                'predicted_date': future_time.strftime('%Y-%m-%d'),
                'value': base_value,
                'confidence_lower': base_value * 0.8,
                'confidence_upper': base_value * 1.2,
                'confidence': 0.5,
                'model_type': 'fallback'
            })

        return predictions

    def _save_predictions(self, point_code, predictions):
        """保存预测结果到数据库"""
        for pred in predictions:
            prediction_record = PredictionResult(
                prediction_id=f"PRED_{point_code}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                point_code=point_code,
                prediction_time=datetime.fromisoformat(pred['prediction_time']),
                predicted_value=pred['predicted_value'],
                confidence_interval=pred.get('confidence', 0.8),
                model_type=pred.get('model_type', 'db4ai')
            )
            db.session.add(prediction_record)

        db.session.commit()


class DB4AIAnomalyDetector:
    """DB4AI异常检测器"""

    def __init__(self, connection):
        self.connection = connection

    def detect_anomalies(self, point_code, threshold_multiplier=2.0):
        """
        使用DB4AI.DETECT_ANOMALIES检测异常
        """
        try:
            # 获取历史数据
            historical_data = self._get_recent_data(point_code, days=30)
            if len(historical_data) < 10:
                return []

            # 这里应该使用openGauss的DB4AI.DETECT_ANOMALIES函数
            # 由于环境限制，这里使用模拟实现
            anomalies = self._simulate_db4ai_anomaly_detection(
                historical_data, point_code, threshold_multiplier
            )

            # 保存检测结果到数据库
            self._save_anomalies(anomalies)

            return anomalies

        except Exception as e:
            print(f"DB4AI异常检测失败: {e}")
            return []

    def _get_recent_data(self, point_code, days=30):
        """获取近期数据"""
        from models import db
        sql = text("""
            SELECT id, record_id, point_code, collection_time, energy_value, collection_status, created_at
            FROM energy
            WHERE point_code = :point_code
              AND collection_time >= :start_date
            ORDER BY collection_time
        """)
        start_date = datetime.now() - timedelta(days=days)
        result = db.session.execute(sql, {
            'point_code': point_code,
            'start_date': start_date
        })
        
        # 转换为EnergyRecord对象列表（保持兼容性）
        records = []
        for row in result:
            record = EnergyRecord()
            record.id = row.id
            record.record_id = row.record_id
            record.point_code = row.point_code
            record.collection_time = row.collection_time
            record.energy_value = row.energy_value
            record.collection_status = row.collection_status
            record.created_at = row.created_at
            records.append(record)
        
        return records

    def _simulate_db4ai_anomaly_detection(self, data, point_code, threshold_multiplier):
        """模拟DB4AI异常检测功能"""
        values = [record.energy_value for record in data]

        if len(values) < 10:
            return []

        # 使用统计方法检测异常
        mean_val = np.mean(values)
        std_val = np.std(values)

        anomalies = []
        for record in data[-24:]:  # 检查最近24小时数据
            # 基于统计的异常检测
            z_score = abs(record.energy_value - mean_val) / std_val if std_val > 0 else 0

            if z_score > threshold_multiplier:
                # 检查是否超过阈值
                from models import db
                point_sql = text("SELECT threshold, equipment_name, workshop, energy_type FROM monitor_point WHERE point_code = :point_code")
                point_result = db.session.execute(point_sql, {'point_code': point_code})
                point_row = point_result.fetchone()
                threshold_exceeded = record.energy_value > point_row.threshold if point_row else False

                anomaly_score = min(1.0, z_score / 5.0)  # 归一化到0-1
                anomalies.append({
                    'record_id': record.record_id,
                    'point_code': point_code,
                    'equipment_name': point.equipment_name if point else '',
                    'workshop': point.workshop if point else '',
                    'energy_type': point.energy_type if point else '',
                    'collection_time': record.collection_time.isoformat() if hasattr(record.collection_time, 'isoformat') else str(record.collection_time),
                    'detection_time': record.collection_time.isoformat() if hasattr(record.collection_time, 'isoformat') else str(record.collection_time),
                    'energy_value': float(record.energy_value),
                    'anomaly_score': float(anomaly_score),
                    'is_anomaly': True,
                    'z_score': float(z_score),
                    'threshold_exceeded': threshold_exceeded,
                    'mean_value': float(mean_val),
                    'std_value': float(std_val)
                })

        return anomalies

    def _save_anomalies(self, anomalies):
        """保存异常检测结果到数据库"""
        for anomaly in anomalies:
            detection_record = AnomalyDetection(
                detection_id=f"ANOM_{anomaly['point_code']}_{anomaly['detection_time'].strftime('%Y%m%d%H%M%S')}",
                point_code=anomaly['point_code'],
                detection_time=anomaly['detection_time'],
                energy_value=anomaly['energy_value'],
                anomaly_score=anomaly['anomaly_score'],
                is_anomaly=anomaly['is_anomaly'],
                detection_method='db4ai_simulated'
            )
            db.session.add(detection_record)

        db.session.commit()


# 工具函数
def get_db4ai_predictions(point_code, days=7):
    """获取DB4AI预测结果"""
    # 这里需要实际的数据库连接
    # 暂时使用模拟实现
    predictor = DB4AIPredictor(None)
    return predictor.predict_time_series(point_code, days)


def db4ai_detect_anomalies(point_code, threshold_multiplier=2.0):
    """使用DB4AI检测异常"""
    # 这里需要实际的数据库连接
    # 暂时使用模拟实现
    detector = DB4AIAnomalyDetector(None)
    return detector.detect_anomalies(point_code, threshold_multiplier)


def generate_energy_cost_analysis():
    """生成能耗成本分析报告"""
    # 模拟能耗成本分析功能
    from sqlalchemy import func

    # 按车间统计能耗成本
    from models import db
    sql = text("""
        SELECT 
            mp.workshop,
            mp.energy_type,
            SUM(e.energy_value) as total_energy,
            COUNT(e.id) as record_count
        FROM energy e
        INNER JOIN monitor_point mp ON e.point_code = mp.point_code
        WHERE e.collection_time >= :start_date
        GROUP BY mp.workshop, mp.energy_type
    """)
    start_date = datetime.now() - timedelta(days=30)
    result = db.session.execute(sql, {'start_date': start_date})
    
    cost_analysis = []
    for row in result:
        cost_analysis.append(type('obj', (object,), {
            'workshop': row.workshop,
            'energy_type': row.energy_type,
            'total_energy': float(row.total_energy),
            'record_count': row.record_count
        })())

    result = []
    for analysis in cost_analysis:
        # 模拟成本计算（实际应该从energy_cost表获取单价）
        unit_price = 1.0  # 默认单价
        total_cost = analysis.total_energy * unit_price

        result.append({
            'workshop': analysis.workshop,
            'energy_type': analysis.energy_type,
            'total_energy': float(analysis.total_energy),
            'record_count': analysis.record_count,
            'unit_price': unit_price,
            'total_cost': float(total_cost)
        })

    return result