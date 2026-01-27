import random
from datetime import datetime, timedelta
from models import db, MonitorPoint, EnergyRecord, EquipmentMaintenance, EnergyCost, AlertRecord, PredictionResult, \
    AnomalyDetection
try:
    from opengauss_db4ai import get_db4ai_predictions, db4ai_detect_anomalies
except ImportError:
    from db4ai_utils import get_db4ai_predictions, db4ai_detect_anomalies
from db4ai_utils import generate_energy_cost_analysis


def generate_sample_data():
    """生成模拟数据"""
    # 能耗监测点数据
    energy_types = ['电力', '水资源', '燃气', '蒸汽']
    units = ['kWh', 'm³', 'm³', 't']
    workshops = ['车间A', '车间B', '车间C', '车间D', '车间E']
    equipments = ['设备1', '设备2', '设备3', '设备4', '设备5', '设备6', '设备7', '设备8', '设备9', '设备10']

    # 清空现有数据（使用原生SQL）
    from sqlalchemy import text
    db.session.execute(text("DELETE FROM energy"))
    db.session.execute(text("DELETE FROM monitor_point"))
    db.session.execute(text("DELETE FROM equipment_maintenance"))
    db.session.execute(text("DELETE FROM energy_cost"))
    db.session.execute(text("DELETE FROM alert_record"))
    db.session.execute(text("DELETE FROM prediction_result"))
    db.session.execute(text("DELETE FROM anomaly_detection"))
    db.session.commit()

    # 创建10个监测点
    monitor_points = []
    for i in range(10):
        point = MonitorPoint(
            point_code=f'MP{i + 1:03d}',
            equipment_name=equipments[i],
            workshop=workshops[i % len(workshops)],
            energy_type=energy_types[i % len(energy_types)],
            unit=units[i % len(units)],
            threshold=random.uniform(50, 200),  # 随机阈值
            description=f'监测点{i + 1}描述信息'
        )
        monitor_points.append(point)
        db.session.add(point)

    db.session.commit()

    # 生成能耗成本数据
    energy_costs = []
    for i, energy_type in enumerate(energy_types):
        cost = EnergyCost(
            cost_id=f'COST{i + 1:03d}',
            energy_type=energy_type,
            unit_price=random.uniform(0.5, 5.0),
            effective_date=datetime.now() - timedelta(days=30)
        )
        energy_costs.append(cost)
        db.session.add(cost)

    db.session.commit()

    # 生成2000条能耗记录，覆盖3个月数据，每小时1条
    start_date = datetime.now() - timedelta(days=90)  # 3个月前
    current_time = start_date

    for i in range(2000):
        # 随机选择一个监测点
        selected_point = random.choice(monitor_points)

        # 生成能耗值，有一定概率超过阈值（模拟异常）
        base_value = selected_point.threshold * random.uniform(0.3, 1.2)
        if random.random() < 0.05:  # 5%概率为异常值
            base_value = selected_point.threshold * random.uniform(1.2, 2.5)

        record = EnergyRecord(
            record_id=f'ER{i + 1:06d}',
            point_code=selected_point.point_code,
            collection_time=current_time,
            energy_value=base_value,
            collection_status='abnormal' if base_value > selected_point.threshold else 'normal'
        )
        db.session.add(record)

        # 每小时一条记录
        current_time += timedelta(hours=1)

    db.session.commit()

    # 生成设备维护记录
    maintenance_types = ['日常维护', '故障维修', '定期检修']
    for i in range(5):
        point = random.choice(monitor_points)
        maintenance = EquipmentMaintenance(
            maintenance_id=f'MAINT{i + 1:03d}',
            point_code=point.point_code,
            maintenance_type=random.choice(maintenance_types),
            maintenance_date=datetime.now() - timedelta(days=random.randint(1, 30)),
            description=f'{point.equipment_name}维护记录',
            cost=random.uniform(200, 2000),
            status='completed'
        )
        db.session.add(maintenance)

    db.session.commit()

    # 生成报警记录
    for i in range(3):
        point = random.choice(monitor_points)
        alert = AlertRecord(
            alert_id=f'ALERT{i + 1:03d}',
            point_code=point.point_code,
            alert_type='threshold_exceeded',
            alert_time=datetime.now() - timedelta(days=random.randint(1, 7)),
            energy_value=point.threshold * random.uniform(1.1, 1.5),
            threshold=point.threshold,
            description=f'{point.equipment_name}能耗超过阈值',
            severity=random.choice(['medium', 'high', 'critical']),
            status=random.choice(['active', 'acknowledged', 'resolved'])
        )
        db.session.add(alert)

    db.session.commit()
    print(f"生成了{len(monitor_points)}个监测点、{2000}条能耗记录和相关业务数据")


def get_energy_statistics(start_date, end_date, group_by='workshop'):
    """获取能耗统计信息（支持按车间、能耗类型、监测点分组）"""
    from sqlalchemy import text

    if group_by == 'workshop':
        sql = text("""
            SELECT 
                mp.workshop,
                SUM(e.energy_value) as total_energy,
                AVG(e.energy_value) as avg_energy,
                MAX(e.energy_value) as max_energy,
                MIN(e.energy_value) as min_energy,
                COUNT(e.id) as record_count
            FROM energy e
            INNER JOIN monitor_point mp ON e.point_code = mp.point_code
            WHERE e.collection_time >= :start_date 
              AND e.collection_time <= :end_date
            GROUP BY mp.workshop
        """)
        
        result = db.session.execute(sql, {
            'start_date': start_date,
            'end_date': end_date
        })
        
        return [{'group': row.workshop, 'total_energy': float(row.total_energy),
                 'avg_energy': float(row.avg_energy), 'max_energy': float(row.max_energy),
                 'min_energy': float(row.min_energy), 'record_count': row.record_count} for row in result]

    elif group_by == 'energy_type':
        sql = text("""
            SELECT 
                mp.energy_type,
                SUM(e.energy_value) as total_energy,
                AVG(e.energy_value) as avg_energy,
                MAX(e.energy_value) as max_energy,
                MIN(e.energy_value) as min_energy,
                COUNT(e.id) as record_count
            FROM energy e
            INNER JOIN monitor_point mp ON e.point_code = mp.point_code
            WHERE e.collection_time >= :start_date 
              AND e.collection_time <= :end_date
            GROUP BY mp.energy_type
        """)
        
        result = db.session.execute(sql, {
            'start_date': start_date,
            'end_date': end_date
        })
        
        return [{'group': row.energy_type, 'total_energy': float(row.total_energy),
                 'avg_energy': float(row.avg_energy), 'max_energy': float(row.max_energy),
                 'min_energy': float(row.min_energy), 'record_count': row.record_count} for row in result]

    elif group_by == 'monitor_point' or group_by == 'point_code':
        # 按监测点分组统计（需求文档要求）
        sql = text("""
            SELECT 
                mp.point_code,
                mp.equipment_name,
                mp.workshop,
                mp.energy_type,
                SUM(e.energy_value) as total_energy,
                AVG(e.energy_value) as avg_energy,
                MAX(e.energy_value) as max_energy,
                MIN(e.energy_value) as min_energy,
                COUNT(e.id) as record_count
            FROM energy e
            INNER JOIN monitor_point mp ON e.point_code = mp.point_code
            WHERE e.collection_time >= :start_date 
              AND e.collection_time <= :end_date
            GROUP BY mp.point_code, mp.equipment_name, mp.workshop, mp.energy_type
        """)
        
        result = db.session.execute(sql, {
            'start_date': start_date,
            'end_date': end_date
        })
        
        return [{'group': f"{row.point_code} - {row.equipment_name}", 
                 'point_code': row.point_code,
                 'equipment_name': row.equipment_name,
                 'workshop': row.workshop,
                 'energy_type': row.energy_type,
                 'total_energy': float(row.total_energy),
                 'avg_energy': float(row.avg_energy), 
                 'max_energy': float(row.max_energy),
                 'min_energy': float(row.min_energy), 
                 'record_count': row.record_count} for row in result]

    return []


def get_energy_trends(point_code, start_date, end_date, period='day'):
    """获取能耗趋势数据"""
    from sqlalchemy import text
    
    try:
        if period == 'hour':
            sql = text("""
                SELECT 
                    DATE_TRUNC('hour', collection_time) as time_period,
                    AVG(energy_value) as avg_energy,
                    MAX(energy_value) as max_energy,
                    MIN(energy_value) as min_energy
                FROM energy
                WHERE point_code = :point_code
                  AND collection_time >= :start_date
                  AND collection_time <= :end_date
                GROUP BY DATE_TRUNC('hour', collection_time)
                ORDER BY time_period
            """)
        elif period == 'day':
            sql = text("""
                SELECT 
                    DATE_TRUNC('day', collection_time) as time_period,
                    AVG(energy_value) as avg_energy,
                    MAX(energy_value) as max_energy,
                    MIN(energy_value) as min_energy
                FROM energy
                WHERE point_code = :point_code
                  AND collection_time >= :start_date
                  AND collection_time <= :end_date
                GROUP BY DATE_TRUNC('day', collection_time)
                ORDER BY time_period
            """)
        elif period == 'week':
            sql = text("""
                SELECT 
                    DATE_TRUNC('week', collection_time) as time_period,
                    AVG(energy_value) as avg_energy,
                    MAX(energy_value) as max_energy,
                    MIN(energy_value) as min_energy
                FROM energy
                WHERE point_code = :point_code
                  AND collection_time >= :start_date
                  AND collection_time <= :end_date
                GROUP BY DATE_TRUNC('week', collection_time)
                ORDER BY time_period
            """)
        else:
            return []

        result = db.session.execute(sql, {
            'point_code': point_code,
            'start_date': start_date,
            'end_date': end_date
        })

        return [{'time_period': row.time_period.isoformat() if hasattr(row.time_period, 'isoformat') else str(row.time_period), 
                 'avg_energy': float(row.avg_energy) if row.avg_energy is not None else 0.0,
                 'max_energy': float(row.max_energy) if row.max_energy is not None else 0.0, 
                 'min_energy': float(row.min_energy) if row.min_energy is not None else 0.0} for row in result]
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"获取能耗趋势数据失败: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_anomaly_records(start_date, end_date):
    """获取异常能耗记录（静态阈值 + 动态异常）"""
    from sqlalchemy import text
    
    # 规则1：静态阈值异常（能耗值 > 监测点.单日阈值）
    sql = text("""
        SELECT 
            e.record_id,
            e.point_code,
            e.collection_time,
            e.energy_value,
            e.collection_status,
            mp.equipment_name,
            mp.workshop,
            mp.energy_type,
            mp.threshold
        FROM energy e
        INNER JOIN monitor_point mp ON e.point_code = mp.point_code
        WHERE e.energy_value > mp.threshold
          AND e.collection_time >= :start_date
          AND e.collection_time <= :end_date
    """)
    
    result = db.session.execute(sql, {
        'start_date': start_date,
        'end_date': end_date
    })
    
    threshold_anomalies = []
    for row in result:
        threshold_anomalies.append({
            'record_id': row.record_id,
            'point_code': row.point_code,
            'equipment_name': row.equipment_name,
            'workshop': row.workshop,
            'energy_type': row.energy_type,
            'energy_value': float(row.energy_value),
            'threshold': float(row.threshold),
            'collection_time': row.collection_time.isoformat() if hasattr(row.collection_time, 'isoformat') else str(row.collection_time),
            'collection_status': row.collection_status,
            'anomaly_type': '超阈值异常',
            'alert_message': f'{row.equipment_name}于{row.collection_time.strftime("%Y-%m-%d %H:%M") if hasattr(row.collection_time, "strftime") else row.collection_time}能耗异常，建议检查对应设备'
        })
    
    result_list = threshold_anomalies
    
    # 规则2：动态异常（通过DB4AI检测突增，如>历史同期均值2倍）
    # 获取每个监测点的历史同期均值
    point_codes_sql = text("SELECT DISTINCT point_code FROM energy")
    point_codes_result = db.session.execute(point_codes_sql)
    
    for row in point_codes_result:
        point_code = row.point_code
        
        # 获取监测点信息
        point_sql = text("SELECT point_code, equipment_name, workshop, energy_type, threshold FROM monitor_point WHERE point_code = :point_code")
        point_result = db.session.execute(point_sql, {'point_code': point_code})
        point_row = point_result.fetchone()
        if not point_row:
            continue
        
        # 计算历史同期均值（最近30天）
        historical_start = start_date - timedelta(days=30)
        avg_sql = text("""
            SELECT AVG(energy_value) as avg_value
            FROM energy
            WHERE point_code = :point_code
              AND collection_time >= :historical_start
              AND collection_time < :start_date
        """)
        avg_result = db.session.execute(avg_sql, {
            'point_code': point_code,
            'historical_start': historical_start,
            'start_date': start_date
        })
        avg_row = avg_result.fetchone()
        
        if avg_row and avg_row.avg_value:
            historical_avg = float(avg_row.avg_value)
            
            # 查找超过历史均值2倍的记录
            dynamic_sql = text("""
                SELECT record_id, point_code, collection_time, energy_value, collection_status
                FROM energy
                WHERE point_code = :point_code
                  AND energy_value > :threshold_value
                  AND collection_time >= :start_date
                  AND collection_time <= :end_date
            """)
            dynamic_result = db.session.execute(dynamic_sql, {
                'point_code': point_code,
                'threshold_value': historical_avg * 2.0,
                'start_date': start_date,
                'end_date': end_date
            })
            
            for record_row in dynamic_result:
                # 避免重复添加（如果已经在阈值异常中）
                if not any(r['record_id'] == record_row.record_id for r in result_list):
                    collection_time = record_row.collection_time
                    time_str = collection_time.strftime("%Y-%m-%d %H:%M") if hasattr(collection_time, 'strftime') else str(collection_time)
                    result_list.append({
                        'record_id': record_row.record_id,
                        'point_code': record_row.point_code,
                        'equipment_name': point_row.equipment_name,
                        'workshop': point_row.workshop,
                        'energy_type': point_row.energy_type,
                        'energy_value': float(record_row.energy_value),
                        'threshold': float(point_row.threshold),
                        'collection_time': collection_time.isoformat() if hasattr(collection_time, 'isoformat') else str(collection_time),
                        'collection_status': record_row.collection_status,
                        'anomaly_type': '行为异常',
                        'alert_message': f'{point_row.equipment_name}于{time_str}能耗异常，建议检查对应设备'
                    })

    return result_list


def get_multi_point_trends(point_codes, start_date, end_date, period='day'):
    """多监测点对比功能（2-5个监测点）"""
    from sqlalchemy import text
    
    result = {
        'point_codes': point_codes,
        'period': period,
        'data': {}
    }
    
    for point_code in point_codes:
        # 获取监测点信息
        point_sql = text("SELECT point_code, equipment_name, workshop, energy_type, unit FROM monitor_point WHERE point_code = :point_code")
        point_result = db.session.execute(point_sql, {'point_code': point_code})
        point_row = point_result.fetchone()
        if not point_row:
            continue
        
        if period == 'hour':
            trends_sql = text("""
                SELECT 
                    DATE_TRUNC('hour', collection_time) as time_period,
                    AVG(energy_value) as avg_energy
                FROM energy
                WHERE point_code = :point_code
                  AND collection_time >= :start_date
                  AND collection_time <= :end_date
                GROUP BY DATE_TRUNC('hour', collection_time)
                ORDER BY time_period
            """)
        elif period == 'day':
            trends_sql = text("""
                SELECT 
                    DATE_TRUNC('day', collection_time) as time_period,
                    AVG(energy_value) as avg_energy
                FROM energy
                WHERE point_code = :point_code
                  AND collection_time >= :start_date
                  AND collection_time <= :end_date
                GROUP BY DATE_TRUNC('day', collection_time)
                ORDER BY time_period
            """)
        elif period == 'week':
            trends_sql = text("""
                SELECT 
                    DATE_TRUNC('week', collection_time) as time_period,
                    AVG(energy_value) as avg_energy
                FROM energy
                WHERE point_code = :point_code
                  AND collection_time >= :start_date
                  AND collection_time <= :end_date
                GROUP BY DATE_TRUNC('week', collection_time)
                ORDER BY time_period
            """)
        else:
            trends = []
            result['data'][point_code] = {
                'equipment_name': point_row.equipment_name,
                'workshop': point_row.workshop,
                'energy_type': point_row.energy_type,
                'unit': point_row.unit,
                'trends': []
            }
            continue
        
        trends_result = db.session.execute(trends_sql, {
            'point_code': point_code,
            'start_date': start_date,
            'end_date': end_date
        })
        
        trends = [{
            'time_period': row.time_period.isoformat() if hasattr(row.time_period, 'isoformat') else str(row.time_period),
            'avg_energy': float(row.avg_energy)
        } for row in trends_result]
        
        result['data'][point_code] = {
            'equipment_name': point_row.equipment_name,
            'workshop': point_row.workshop,
            'energy_type': point_row.energy_type,
            'unit': point_row.unit,
            'trends': trends
        }
    
    return result


def get_energy_predictions(point_code, days=7):
    """使用DB4AI进行能耗预测"""
    # 使用真正的DB4AI功能
    return get_db4ai_predictions(point_code, days)


def db4ai_anomaly_detection(point_code, threshold_multiplier=1.5, start_date=None, end_date=None, days=30):
    """使用DB4AI进行异常检测
    
    Args:
        point_code: 监测点代码
        threshold_multiplier: 阈值倍数
        start_date: 开始日期（可选）
        end_date: 结束日期（可选）
        days: 天数（当start_date和end_date为None时使用）
    """
    # 使用真正的DB4AI功能
    return db4ai_detect_anomalies(point_code, threshold_multiplier, 'isolation_forest', 
                                  start_date, end_date, days)


def get_energy_cost_analysis():
    """获取能耗成本分析"""
    return generate_energy_cost_analysis()


def get_maintenance_records():
    """获取设备维护记录（使用原生SQL）"""
    from sqlalchemy import text
    
    sql = text("""
        SELECT id, maintenance_id, point_code, maintenance_type, maintenance_date, 
               description, cost, status, created_at
        FROM equipment_maintenance
        ORDER BY maintenance_date DESC
    """)
    
    result = db.session.execute(sql)
    records = []
    for row in result:
        records.append({
            'id': row.id,
            'maintenance_id': row.maintenance_id,
            'point_code': row.point_code,
            'maintenance_type': row.maintenance_type,
            'maintenance_date': row.maintenance_date.isoformat() if row.maintenance_date else None,
            'description': row.description,
            'cost': float(row.cost) if row.cost else 0.0,
            'status': row.status,
            'created_at': row.created_at.isoformat() if row.created_at else None
        })
    
    return records


def get_alert_records():
    """获取报警记录（使用原生SQL）"""
    from sqlalchemy import text
    
    sql = text("""
        SELECT id, alert_id, point_code, alert_type, alert_time, energy_value, threshold,
               description, severity, status, resolved_time, created_at
        FROM alert_record
        ORDER BY alert_time DESC
    """)
    
    result = db.session.execute(sql)
    records = []
    for row in result:
        records.append({
            'id': row.id,
            'alert_id': row.alert_id,
            'point_code': row.point_code,
            'alert_type': row.alert_type,
            'alert_time': row.alert_time.isoformat() if row.alert_time else None,
            'energy_value': float(row.energy_value) if row.energy_value else None,
            'threshold': float(row.threshold) if row.threshold else None,
            'description': row.description,
            'severity': row.severity,
            'status': row.status,
            'resolved_time': row.resolved_time.isoformat() if row.resolved_time else None,
            'created_at': row.created_at.isoformat() if row.created_at else None
        })
    
    return records


def get_predictions_history(point_code=None):
    """获取预测历史记录（使用原生SQL）"""
    from sqlalchemy import text
    
    # 构建SQL查询
    sql = """
        SELECT id, prediction_id, point_code, prediction_time, predicted_value, 
               confidence_interval, model_type, created_at
        FROM prediction_result
        WHERE 1=1
    """
    params = {}
    
    if point_code:
        sql += " AND point_code = :point_code"
        params['point_code'] = point_code
    
    sql += " ORDER BY prediction_time DESC"
    
    result = db.session.execute(text(sql), params)
    records = []
    for row in result:
        records.append({
            'id': row.id,
            'prediction_id': row.prediction_id,
            'point_code': row.point_code,
            'prediction_time': row.prediction_time.isoformat() if row.prediction_time else None,
            'predicted_value': float(row.predicted_value),
            'confidence_interval': float(row.confidence_interval) if row.confidence_interval else None,
            'model_type': row.model_type,
            'created_at': row.created_at.isoformat() if row.created_at else None
        })
    
    return records


def get_anomaly_detection_history(point_code=None):
    """获取异常检测历史记录（使用原生SQL）"""
    from sqlalchemy import text
    
    # 构建SQL查询
    sql = """
        SELECT id, detection_id, point_code, detection_time, energy_value, 
               anomaly_score, is_anomaly, detection_method, created_at
        FROM anomaly_detection
        WHERE 1=1
    """
    params = {}
    
    if point_code:
        sql += " AND point_code = :point_code"
        params['point_code'] = point_code
    
    sql += " ORDER BY detection_time DESC"
    
    result = db.session.execute(text(sql), params)
    records = []
    for row in result:
        records.append({
            'id': row.id,
            'detection_id': row.detection_id,
            'point_code': row.point_code,
            'detection_time': row.detection_time.isoformat() if row.detection_time else None,
            'energy_value': float(row.energy_value),
            'anomaly_score': float(row.anomaly_score),
            'is_anomaly': bool(row.is_anomaly),
            'detection_method': row.detection_method,
            'created_at': row.created_at.isoformat() if row.created_at else None
        })
    
    return records


def get_columnar_performance_stats():
    """获取列存储性能统计"""
    from sqlalchemy import text
    from datetime import datetime, timedelta

    # 模拟列存储性能优势
    start_date = datetime.now() - timedelta(days=30)

    # 统计查询性能数据
    sql = text("""
        SELECT 
            COUNT(id) as total_records,
            AVG(energy_value) as avg_energy,
            MAX(energy_value) as max_energy
        FROM energy
        WHERE collection_time >= :start_date
    """)
    
    result = db.session.execute(sql, {'start_date': start_date})
    stats = result.fetchone()

    return {
        'total_records': stats.total_records if stats else 0,
        'avg_energy': float(stats.avg_energy) if stats and stats.avg_energy else 0,
        'max_energy': float(stats.max_energy) if stats and stats.max_energy else 0,
        'query_performance': '列存储查询速度比行存储快3-5倍',
        'storage_efficiency': '列存储仅读取所需列，减少数据传输',
        'compression_ratio': '列存储压缩比可达5:1以上'
    }