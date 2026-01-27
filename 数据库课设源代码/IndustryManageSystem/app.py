# 在导入其他模块之前，先应用openGauss版本解析补丁
import opengauss_dialect_patch  # 修复SQLAlchemy无法解析openGauss版本字符串的问题

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from config import Config
from functools import wraps
from functools import wraps
from models import db, MonitorPoint, EnergyRecord, EquipmentMaintenance, EnergyCost, AlertRecord, PredictionResult, \
    AnomalyDetection
from utils import generate_sample_data, get_energy_statistics, get_energy_trends, get_anomaly_records
from utils import db4ai_anomaly_detection, get_energy_cost_analysis
from utils import get_maintenance_records, get_alert_records, get_predictions_history as get_predictions_history_from_utils, get_anomaly_detection_history as get_anomaly_detection_history_from_utils, \
    get_columnar_performance_stats
from visualization import create_energy_trend_chart, create_energy_distribution_chart, create_anomaly_chart, \
    create_dashboard_charts
from datetime import datetime, timedelta
from sqlalchemy import text
import json


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    # 注意：psycopg3不支持在CREATE TABLE中直接使用外键约束
    # 外键约束将在表创建后通过独立连接添加

    with app.app_context():
        # 创建所有表（不包含外键约束，因为psycopg3不支持在CREATE TABLE中使用外键）
        db.create_all()
        
        # 在表创建后，使用独立连接添加外键约束
        from sqlalchemy import text
        try:
            with db.engine.begin() as conn:  # 使用begin()自动管理事务
                # 添加外键约束
                fk_constraints = [
                    ("energy", "fk_energy_point_code", "point_code", "monitor_point"),
                    ("equipment_maintenance", "fk_maintenance_point_code", "point_code", "monitor_point"),
                    ("alert_record", "fk_alert_point_code", "point_code", "monitor_point"),
                    ("prediction_result", "fk_prediction_point_code", "point_code", "monitor_point"),
                    ("anomaly_detection", "fk_anomaly_point_code", "point_code", "monitor_point"),
                ]
                
                for table_name, constraint_name, column, ref_table in fk_constraints:
                    try:
                        # 先检查约束是否已存在
                        result = conn.execute(text(f"""
                            SELECT constraint_name 
                            FROM information_schema.table_constraints 
                            WHERE table_name = '{table_name}' 
                            AND constraint_name = '{constraint_name}'
                        """))
                        if result.fetchone() is None:
                            # 约束不存在，添加它
                            conn.execute(text(f"""
                                ALTER TABLE {table_name} 
                                ADD CONSTRAINT {constraint_name} 
                                FOREIGN KEY ({column}) REFERENCES {ref_table}(point_code)
                            """))
                            print(f"{table_name}表外键约束已添加")
                    except Exception as e:
                        # 忽略错误（约束可能已存在或其他原因）
                        pass
        except Exception as e:
            print(f"添加外键约束时出错（可能表不存在或约束已存在）: {e}")

        # 检查是否需要生成示例数据（使用原生SQL）
        count_sql = text("SELECT COUNT(*) as count FROM monitor_point")
        count_result = db.session.execute(count_sql)
        count = count_result.fetchone().count
        if count == 0:
            generate_sample_data()

    return app


app = create_app()


# 简单的用户角色管理（实际项目中应使用数据库存储用户信息）
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'
USER_USERNAME = 'user'
USER_PASSWORD = 'user123'


def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in') or session.get('role') != 'admin':
            return jsonify({'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated_function


def login_required(f):
    """登录权限装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': '需要登录'}), 401
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/login', methods=['POST'])
def login():
    """登录接口"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session['logged_in'] = True
        session['role'] = 'admin'
        session['username'] = username
        return jsonify({'success': True, 'role': 'admin', 'username': username})
    elif username == USER_USERNAME and password == USER_PASSWORD:
        session['logged_in'] = True
        session['role'] = 'user'
        session['username'] = username
        return jsonify({'success': True, 'role': 'user', 'username': username})
    else:
        return jsonify({'error': '用户名或密码错误'}), 401


@app.route('/api/logout', methods=['POST'])
def logout():
    """登出接口"""
    session.clear()
    return jsonify({'success': True})


@app.route('/api/current_user', methods=['GET'])
def get_current_user():
    """获取当前用户信息"""
    if session.get('logged_in'):
        return jsonify({
            'logged_in': True,
            'role': session.get('role'),
            'username': session.get('username')
        })
    return jsonify({'logged_in': False})


@app.route('/api/monitor_points')
def get_monitor_points():
    """获取监测点列表，支持按编号和能耗类型筛选（使用原生SQL）"""
    point_code = request.args.get('point_code', '')
    energy_type = request.args.get('energy_type', '')
    
    # 使用原生SQL查询
    sql = "SELECT id, point_code, equipment_name, workshop, energy_type, unit, threshold, description, created_at, updated_at FROM monitor_point WHERE 1=1"
    params = {}
    
    if point_code:
        sql += " AND point_code ILIKE :point_code"
        params['point_code'] = f'%{point_code}%'
    
    if energy_type:
        sql += " AND energy_type = :energy_type"
        params['energy_type'] = energy_type
    
    sql += " ORDER BY id"
    
    result = db.session.execute(text(sql), params)
    points = []
    for row in result:
        points.append({
            'id': row.id,
            'point_code': row.point_code,
            'equipment_name': row.equipment_name,
            'workshop': row.workshop,
            'energy_type': row.energy_type,
            'unit': row.unit,
            'threshold': float(row.threshold),
            'description': row.description,
            'created_at': row.created_at.isoformat() if row.created_at else None,
            'updated_at': row.updated_at.isoformat() if row.updated_at else None
        })
    
    return jsonify(points)


@app.route('/api/monitor_points', methods=['POST'])
@admin_required
def add_monitor_point():
    """添加监测点（使用原生SQL）"""
    data = request.get_json()
    
    # 使用原生SQL INSERT
    sql = text("""
        INSERT INTO monitor_point 
        (point_code, equipment_name, workshop, energy_type, unit, threshold, description, created_at, updated_at)
        VALUES 
        (:point_code, :equipment_name, :workshop, :energy_type, :unit, :threshold, :description, NOW(), NOW())
        RETURNING id, point_code, equipment_name, workshop, energy_type, unit, threshold, description, created_at, updated_at
    """)
    
    result = db.session.execute(sql, {
        'point_code': data['point_code'],
        'equipment_name': data['equipment_name'],
        'workshop': data['workshop'],
        'energy_type': data['energy_type'],
        'unit': data['unit'],
        'threshold': data['threshold'],
        'description': data.get('description', '')
    })
    
    db.session.commit()
    row = result.fetchone()
    
    return jsonify({
        'id': row.id,
        'point_code': row.point_code,
        'equipment_name': row.equipment_name,
        'workshop': row.workshop,
        'energy_type': row.energy_type,
        'unit': row.unit,
        'threshold': float(row.threshold),
        'description': row.description,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None
    })


@app.route('/api/monitor_points/<int:point_id>', methods=['PUT'])
@admin_required
def update_monitor_point(point_id):
    """更新监测点（使用原生SQL）"""
    data = request.get_json()
    
    # 先检查记录是否存在
    check_sql = text("SELECT id FROM monitor_point WHERE id = :point_id")
    check_result = db.session.execute(check_sql, {'point_id': point_id})
    if not check_result.fetchone():
        return jsonify({'error': '监测点不存在'}), 404
    
    # 使用原生SQL UPDATE
    sql = text("""
        UPDATE monitor_point 
        SET equipment_name = :equipment_name,
            workshop = :workshop,
            energy_type = :energy_type,
            unit = :unit,
            threshold = :threshold,
            description = :description,
            updated_at = NOW()
        WHERE id = :point_id
        RETURNING id, point_code, equipment_name, workshop, energy_type, unit, threshold, description, created_at, updated_at
    """)
    
    result = db.session.execute(sql, {
        'point_id': point_id,
        'equipment_name': data['equipment_name'],
        'workshop': data['workshop'],
        'energy_type': data['energy_type'],
        'unit': data['unit'],
        'threshold': data['threshold'],
        'description': data.get('description', '')
    })
    
    db.session.commit()
    row = result.fetchone()
    
    return jsonify({
        'id': row.id,
        'point_code': row.point_code,
        'equipment_name': row.equipment_name,
        'workshop': row.workshop,
        'energy_type': row.energy_type,
        'unit': row.unit,
        'threshold': float(row.threshold),
        'description': row.description,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None
    })


@app.route('/api/monitor_points/<int:point_id>', methods=['DELETE'])
@admin_required
def delete_monitor_point(point_id):
    """删除监测点（使用原生SQL）"""
    # 先获取监测点编号
    get_sql = text("SELECT point_code FROM monitor_point WHERE id = :point_id")
    result = db.session.execute(get_sql, {'point_id': point_id})
    point_row = result.fetchone()
    
    if not point_row:
        return jsonify({'error': '监测点不存在'}), 404
    
    point_code = point_row.point_code
    
    # 检查是否有能耗记录（使用原生SQL）
    check_sql = text("SELECT COUNT(*) as count FROM energy WHERE point_code = :point_code")
    check_result = db.session.execute(check_sql, {'point_code': point_code})
    count = check_result.fetchone().count
    
    if count > 0:
        return jsonify({'error': '该监测点已有能耗记录，无法删除'}), 400
    
    # 使用原生SQL DELETE
    delete_sql = text("DELETE FROM monitor_point WHERE id = :point_id")
    db.session.execute(delete_sql, {'point_id': point_id})
    db.session.commit()
    
    return jsonify({'message': '监测点删除成功'})


@app.route('/api/energy_records')
def get_energy_records():
    """获取能耗记录列表（使用原生SQL，支持分页）"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    point_code = request.args.get('point_code', '')

    # 计算偏移量
    offset = (page - 1) * per_page
    
    # 构建WHERE条件
    where_clause = "WHERE 1=1"
    params = {}
    
    if point_code:
        where_clause += " AND point_code = :point_code"
        params['point_code'] = point_code
    
    # 先查询总数（使用原生SQL）
    count_sql = text(f"SELECT COUNT(*) as total FROM energy {where_clause}")
    count_result = db.session.execute(count_sql, params)
    total = count_result.fetchone().total
    
    # 查询分页数据（使用原生SQL）
    sql = text(f"""
        SELECT id, record_id, point_code, collection_time, energy_value, collection_status, created_at
        FROM energy 
        {where_clause}
        ORDER BY collection_time DESC
        LIMIT :limit OFFSET :offset
    """)
    
    params['limit'] = per_page
    params['offset'] = offset
    
    result = db.session.execute(sql, params)
    records = []
    for row in result:
        records.append({
            'id': row.id,
            'record_id': row.record_id,
            'point_code': row.point_code,
            'collection_time': row.collection_time.isoformat() if row.collection_time else None,
            'energy_value': float(row.energy_value),
            'collection_status': row.collection_status,
            'created_at': row.created_at.isoformat() if row.created_at else None
        })
    
    # 计算总页数
    pages = (total + per_page - 1) // per_page
    
    return jsonify({
        'records': records,
        'total': total,
        'pages': pages,
        'current_page': page
    })


@app.route('/api/energy_records', methods=['POST'])
@admin_required
def add_energy_record():
    """添加能耗记录（使用原生SQL）"""
    data = request.get_json()
    
    # 根据"能耗值>阈值"自动判断采集状态
    point_code = data['point_code']
    energy_value = float(data['energy_value'])
    
    # 获取监测点信息以获取阈值（使用原生SQL）
    threshold_sql = text("SELECT threshold FROM monitor_point WHERE point_code = :point_code")
    threshold_result = db.session.execute(threshold_sql, {'point_code': point_code})
    threshold_row = threshold_result.fetchone()
    
    if threshold_row:
        # 如果能耗值大于阈值，标记为异常，否则为正常
        collection_status = 'abnormal' if energy_value > float(threshold_row.threshold) else 'normal'
    else:
        # 如果监测点不存在，默认使用normal
        collection_status = 'normal'
    
    # 使用原生SQL INSERT
    sql = text("""
        INSERT INTO energy 
        (record_id, point_code, collection_time, energy_value, collection_status, created_at)
        VALUES 
        (:record_id, :point_code, :collection_time, :energy_value, :collection_status, NOW())
        RETURNING id, record_id, point_code, collection_time, energy_value, collection_status, created_at
    """)
    
    result = db.session.execute(sql, {
        'record_id': data['record_id'],
        'point_code': point_code,
        'collection_time': datetime.fromisoformat(data['collection_time']),
        'energy_value': energy_value,
        'collection_status': collection_status
    })
    
    db.session.commit()
    row = result.fetchone()
    
    return jsonify({
        'id': row.id,
        'record_id': row.record_id,
        'point_code': row.point_code,
        'collection_time': row.collection_time.isoformat() if row.collection_time else None,
        'energy_value': float(row.energy_value),
        'collection_status': row.collection_status,
        'created_at': row.created_at.isoformat() if row.created_at else None
    })


@app.route('/api/energy_records/<int:record_id>', methods=['DELETE'])
@admin_required
def delete_energy_record(record_id):
    """删除能耗记录（仅允许删除24小时内的记录，使用原生SQL）"""
    try:
        # 先获取记录信息（使用原生SQL）
        get_sql = text("""
            SELECT id, collection_time 
            FROM energy 
            WHERE id = :record_id
        """)
        result = db.session.execute(get_sql, {'record_id': record_id})
        record_row = result.fetchone()
        
        if not record_row:
            return jsonify({'error': '记录不存在'}), 404
        
        # 检查记录是否在24小时内（使用SQL计算时间差）
        check_sql = text("""
            SELECT 
                id,
                EXTRACT(EPOCH FROM (NOW() - collection_time)) / 3600 as hours_diff
            FROM energy 
            WHERE id = :record_id
        """)
        check_result = db.session.execute(check_sql, {'record_id': record_id})
        time_row = check_result.fetchone()
        
        hours_diff = float(time_row.hours_diff)
        
        if hours_diff > 24:
            return jsonify({'error': f'只能删除24小时内的记录，该记录已超过{int(hours_diff)}小时'}), 400
        
        # 使用原生SQL DELETE
        delete_sql = text("DELETE FROM energy WHERE id = :record_id")
        db.session.execute(delete_sql, {'record_id': record_id})
        db.session.commit()
        
        return jsonify({'message': '能耗记录删除成功'})
    except Exception as e:
        import traceback
        print(f"删除能耗记录失败: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'删除失败: {str(e)}'}), 500


@app.route('/api/energy_statistics')
def energy_statistics():
    """能耗统计分析（支持按车间、能耗类型、监测点分组）"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    group_by = request.args.get('group_by', 'workshop')  # workshop, energy_type, monitor_point

    start_date = datetime.fromisoformat(start_date_str) if start_date_str else datetime.now() - timedelta(days=30)
    end_date = datetime.fromisoformat(end_date_str) if end_date_str else datetime.now()

    stats = get_energy_statistics(start_date, end_date, group_by)
    return jsonify(stats)


@app.route('/api/energy_trends')
def energy_trends():
    try:
        point_code = request.args.get('point_code')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        period = request.args.get('period', 'day')

        if not point_code:
            return jsonify({'error': 'Missing point_code parameter'}), 400

        # 处理日期格式：支持 YYYY-MM-DD 和完整的 ISO 格式
        if start_date_str:
            try:
                if len(start_date_str) == 10:  # YYYY-MM-DD 格式
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                else:
                    start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                start_date = datetime.now() - timedelta(days=30)
        else:
            start_date = datetime.now() - timedelta(days=30)
            
        if end_date_str:
            try:
                if len(end_date_str) == 10:  # YYYY-MM-DD 格式
                    # 结束日期需要包含当天的结束时间
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
                else:
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                end_date = datetime.now()
        else:
            end_date = datetime.now()

        trends = get_energy_trends(point_code, start_date, end_date, period)
        return jsonify(trends)
    except Exception as e:
        import traceback
        print(f"能耗趋势分析错误: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@app.route('/api/energy_compare')
def energy_compare():
    """多监测点对比功能（2-5个监测点）"""
    point_codes_str = request.args.get('point_codes', '')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    period = request.args.get('period', 'day')

    if not point_codes_str:
        return jsonify({'error': 'Missing point_codes parameter'}), 400

    point_codes = [code.strip() for code in point_codes_str.split(',')]
    
    # 限制2-5个监测点
    if len(point_codes) < 2 or len(point_codes) > 5:
        return jsonify({'error': '请选择2-5个监测点进行对比'}), 400

    start_date = datetime.fromisoformat(start_date_str) if start_date_str else datetime.now() - timedelta(days=30)
    end_date = datetime.fromisoformat(end_date_str) if end_date_str else datetime.now()

    from utils import get_multi_point_trends
    compare_data = get_multi_point_trends(point_codes, start_date, end_date, period)
    return jsonify(compare_data)


@app.route('/api/anomaly_records')
def anomaly_records():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # 处理日期格式：支持 YYYY-MM-DD 和完整的 ISO 格式
    if start_date_str:
        try:
            if len(start_date_str) == 10:  # YYYY-MM-DD 格式
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            else:
                start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            start_date = datetime.now() - timedelta(days=30)
    else:
        start_date = datetime.now() - timedelta(days=30)
        
    if end_date_str:
        try:
            if len(end_date_str) == 10:  # YYYY-MM-DD 格式
                # 结束日期需要包含当天的结束时间
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            else:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            end_date = datetime.now()
    else:
        end_date = datetime.now()

    anomalies = get_anomaly_records(start_date, end_date)
    return jsonify(anomalies)


@app.route('/api/generate_sample_data', methods=['POST'])
def api_generate_sample_data():
    generate_sample_data()
    return jsonify({'message': '示例数据生成成功'})


@app.route('/api/charts/trend')
def get_trend_chart():
    point_code = request.args.get('point_code')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    period = request.args.get('period', 'day')

    start_date = datetime.fromisoformat(start_date_str) if start_date_str else datetime.now() - timedelta(days=30)
    end_date = datetime.fromisoformat(end_date_str) if end_date_str else datetime.now()

    chart_html = create_energy_trend_chart(point_code, start_date, end_date, period)
    return jsonify({'chart_html': chart_html})


@app.route('/api/charts/distribution')
def get_distribution_chart():
    group_by = request.args.get('group_by', 'workshop')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    start_date = datetime.fromisoformat(start_date_str) if start_date_str else None
    end_date = datetime.fromisoformat(end_date_str) if end_date_str else None

    chart_html = create_energy_distribution_chart(group_by, start_date, end_date)
    return jsonify({'chart_html': chart_html})


@app.route('/api/charts/anomaly')
def get_anomaly_chart():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    start_date = datetime.fromisoformat(start_date_str) if start_date_str else datetime.now() - timedelta(days=30)
    end_date = datetime.fromisoformat(end_date_str) if end_date_str else datetime.now()

    chart_html = create_anomaly_chart(start_date, end_date)
    return jsonify({'chart_html': chart_html})


@app.route('/api/charts/dashboard')
def get_dashboard_charts():
    trend_html, type_html = create_dashboard_charts()
    return jsonify({
        'trend_chart_html': trend_html,
        'type_chart_html': type_html
    })


@app.route('/api/charts/prediction_with_history')
def get_prediction_with_history_chart():
    """获取预测与历史对比图表（双曲线图）"""
    point_code = request.args.get('point_code')
    days = int(request.args.get('days', 7))
    
    if not point_code:
        return jsonify({'error': 'Missing point_code parameter'}), 400
    
    from visualization import create_prediction_chart_with_history
    chart_html = create_prediction_chart_with_history(point_code, days)
    return jsonify({'chart_html': chart_html})


@app.route('/api/charts/multi_point_compare')
def get_multi_point_compare_chart():
    """获取多监测点对比图表"""
    point_codes_str = request.args.get('point_codes', '')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    period = request.args.get('period', 'day')
    
    if not point_codes_str:
        return jsonify({'error': 'Missing point_codes parameter'}), 400
    
    point_codes = [code.strip() for code in point_codes_str.split(',')]
    
    if len(point_codes) < 2 or len(point_codes) > 5:
        return jsonify({'error': '请选择2-5个监测点进行对比'}), 400
    
    start_date = datetime.fromisoformat(start_date_str) if start_date_str else datetime.now() - timedelta(days=30)
    end_date = datetime.fromisoformat(end_date_str) if end_date_str else datetime.now()
    
    from visualization import create_multi_point_compare_chart
    chart_html = create_multi_point_compare_chart(point_codes, start_date, end_date, period)
    return jsonify({'chart_html': chart_html})


@app.route('/api/predictions')
def api_get_energy_predictions():
    """获取能耗预测数据，包含预警逻辑"""
    try:
        point_code = request.args.get('point_code')
        days = int(request.args.get('days', 7))

        if not point_code:
            return jsonify({'error': 'Missing point_code parameter'}), 400

        from utils import get_energy_predictions as get_pred
        predictions = get_pred(point_code, days)
        
        # 确保predictions是列表格式
        if predictions is None:
            predictions = []
        if not isinstance(predictions, list):
            predictions = list(predictions) if predictions else []
        
        # 格式化预测数据，确保有正确的字段
        formatted_predictions = []
        for pred in predictions:
            if isinstance(pred, dict):
                # 处理日期字段
                date_val = pred.get('date') or pred.get('prediction_time', '')
                if isinstance(date_val, datetime):
                    date_val = date_val.isoformat()
                elif date_val and not isinstance(date_val, str):
                    date_val = str(date_val)
                
                formatted_predictions.append({
                    'date': date_val or '',
                    'predicted_value': float(pred.get('predicted_value', pred.get('value', 0))),
                    'confidence_lower': float(pred.get('confidence_lower', 0)) if pred.get('confidence_lower') is not None else None,
                    'confidence_upper': float(pred.get('confidence_upper', 0)) if pred.get('confidence_upper') is not None else None
                })
        
        # 检查预警逻辑：连续3天预测值 > 阈值 → 触发"能耗超标风险"预警（使用原生SQL）
        threshold_sql = text("SELECT threshold, equipment_name FROM monitor_point WHERE point_code = :point_code")
        threshold_result = db.session.execute(threshold_sql, {'point_code': point_code})
        point_row = threshold_result.fetchone()
        
        if point_row and formatted_predictions:
            point_threshold = float(point_row.threshold)
            point_equipment_name = point_row.equipment_name
            consecutive_days = 0
            max_consecutive = 0
            for pred in formatted_predictions:
                if pred.get('predicted_value', 0) > point_threshold:
                    consecutive_days += 1
                    max_consecutive = max(max_consecutive, consecutive_days)
                else:
                    consecutive_days = 0
            
            if max_consecutive >= 3:
                # 触发预警
                alert_message = f'监测点{point_code}({point_equipment_name})未来预测连续{max_consecutive}天超过阈值，触发"能耗超标风险"预警'
                return jsonify({
                    'predictions': formatted_predictions,
                    'warning': {
                        'triggered': True,
                        'message': alert_message,
                        'consecutive_days': max_consecutive,
                        'threshold': point_threshold
                    }
                })

        return jsonify({'predictions': formatted_predictions, 'warning': {'triggered': False}})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'预测失败: {str(e)}'}), 500


@app.route('/api/anomaly_alerts')
def get_anomaly_alerts():
    """获取异常预警信息（用于弹窗提示）"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    # 处理日期格式：支持 YYYY-MM-DD 和完整的 ISO 格式
    if start_date_str:
        try:
            if len(start_date_str) == 10:  # YYYY-MM-DD 格式
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            else:
                start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            start_date = datetime.now() - timedelta(days=1)
    else:
        start_date = datetime.now() - timedelta(days=1)
        
    if end_date_str:
        try:
            if len(end_date_str) == 10:  # YYYY-MM-DD 格式
                # 结束日期需要包含当天的结束时间
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
            else:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            end_date = datetime.now()
    else:
        end_date = datetime.now()
    
    anomalies = get_anomaly_records(start_date, end_date)
    
    # 返回需要弹窗提示的异常记录
    alerts = []
    for anomaly in anomalies:
        alerts.append({
            'point_code': anomaly['point_code'],
            'equipment_name': anomaly['equipment_name'],
            'collection_time': anomaly['collection_time'],
            'energy_value': anomaly['energy_value'],
            'anomaly_type': anomaly.get('anomaly_type', '异常'),
            'alert_message': anomaly.get('alert_message', f"{anomaly['equipment_name']}于{anomaly['collection_time']}能耗异常，建议检查对应设备")
        })
    
    return jsonify({'alerts': alerts, 'count': len(alerts)})


@app.route('/api/db4ai_anomalies')
def get_db4ai_anomalies():
    """获取DB4AI异常检测结果"""
    try:
        point_code = request.args.get('point_code')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        threshold_multiplier_str = request.args.get('threshold_multiplier', '1.5')
        
        if not point_code:
            return jsonify({'error': 'Missing point_code parameter'}), 400

        # 验证并转换阈值倍数
        try:
            threshold_multiplier = float(threshold_multiplier_str)
            # 确保阈值在合理范围内（0.1 到 10）
            if threshold_multiplier < 0.1:
                threshold_multiplier = 0.1
            elif threshold_multiplier > 10:
                threshold_multiplier = 10
        except (ValueError, TypeError):
            threshold_multiplier = 1.5

        from utils import db4ai_anomaly_detection
        # 解析日期范围（如果提供）
        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str)
            except (ValueError, AttributeError):
                pass
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str)
            except (ValueError, AttributeError):
                pass
        
        # 调用异常检测，传递日期范围参数（如果提供）
        anomalies = db4ai_anomaly_detection(
            point_code, 
            threshold_multiplier,
            start_date=start_date,
            end_date=end_date,
            days=30  # 默认30天，如果提供了日期范围则使用日期范围
        )
        
        # 如果提供了日期范围，进行过滤
        if start_date_str and end_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str)
                end_date = datetime.fromisoformat(end_date_str)
                filtered_anomalies = []
                for anomaly in anomalies:
                    if 'detection_time' in anomaly:
                        anomaly_time = anomaly['detection_time']
                        if isinstance(anomaly_time, str):
                            anomaly_time = datetime.fromisoformat(anomaly_time.replace('Z', '+00:00'))
                        if start_date <= anomaly_time <= end_date:
                            filtered_anomalies.append(anomaly)
                    elif 'collection_time' in anomaly:
                        anomaly_time = anomaly['collection_time']
                        if isinstance(anomaly_time, str):
                            anomaly_time = datetime.fromisoformat(anomaly_time.replace('Z', '+00:00'))
                        if start_date <= anomaly_time <= end_date:
                            filtered_anomalies.append(anomaly)
                anomalies = filtered_anomalies
            except Exception as e:
                pass  # 如果日期解析失败，返回所有异常

        return jsonify({'anomalies': anomalies})
    except Exception as e:
        import traceback
        print(f"DB4AI异常检测错误: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


@app.route('/api/energy_cost_analysis')
def get_energy_cost_analysis():
    """获取能耗成本分析"""
    analysis = get_energy_cost_analysis()
    return jsonify(analysis)


@app.route('/api/maintenance_records')
def get_maintenance_records():
    """获取设备维护记录"""
    records = get_maintenance_records()
    return jsonify(records)


# 设备维护记录管理API（管理员）
@app.route('/api/equipment_maintenance', methods=['GET'])
def get_equipment_maintenance():
    """获取设备维护记录列表（使用原生SQL）"""
    # 使用原生SQL查询
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
    
    return jsonify(records)


@app.route('/api/equipment_maintenance', methods=['POST'])
@admin_required
def add_equipment_maintenance():
    """添加设备维护记录（使用原生SQL）"""
    data = request.get_json()
    
    # 使用原生SQL INSERT
    sql = text("""
        INSERT INTO equipment_maintenance 
        (maintenance_id, point_code, maintenance_type, maintenance_date, description, cost, status, created_at)
        VALUES 
        (:maintenance_id, :point_code, :maintenance_type, :maintenance_date, :description, :cost, :status, NOW())
        RETURNING id, maintenance_id, point_code, maintenance_type, maintenance_date, description, cost, status, created_at
    """)
    
    result = db.session.execute(sql, {
        'maintenance_id': data['maintenance_id'],
        'point_code': data['point_code'],
        'maintenance_type': data['maintenance_type'],
        'maintenance_date': datetime.fromisoformat(data['maintenance_date']),
        'description': data.get('description', ''),
        'cost': float(data.get('cost', 0.0)),
        'status': data.get('status', 'completed')
    })
    
    db.session.commit()
    row = result.fetchone()
    
    return jsonify({
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


@app.route('/api/equipment_maintenance/<int:record_id>', methods=['PUT'])
@admin_required
def update_equipment_maintenance(record_id):
    """更新设备维护记录（使用原生SQL）"""
    data = request.get_json()
    
    # 先检查记录是否存在
    check_sql = text("SELECT id FROM equipment_maintenance WHERE id = :record_id")
    check_result = db.session.execute(check_sql, {'record_id': record_id})
    if not check_result.fetchone():
        return jsonify({'error': '维护记录不存在'}), 404
    
    # 使用原生SQL UPDATE
    sql = text("""
        UPDATE equipment_maintenance 
        SET maintenance_type = :maintenance_type,
            maintenance_date = :maintenance_date,
            description = :description,
            cost = :cost,
            status = :status
        WHERE id = :record_id
        RETURNING id, maintenance_id, point_code, maintenance_type, maintenance_date, description, cost, status, created_at
    """)
    
    result = db.session.execute(sql, {
        'record_id': record_id,
        'maintenance_type': data.get('maintenance_type'),
        'maintenance_date': datetime.fromisoformat(data['maintenance_date']) if 'maintenance_date' in data else None,
        'description': data.get('description', ''),
        'cost': float(data.get('cost', 0.0)),
        'status': data.get('status', 'completed')
    })
    
    db.session.commit()
    row = result.fetchone()
    
    return jsonify({
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


@app.route('/api/equipment_maintenance/<int:record_id>', methods=['DELETE'])
@admin_required
def delete_equipment_maintenance(record_id):
    """删除设备维护记录（使用原生SQL）"""
    # 先检查记录是否存在
    check_sql = text("SELECT id FROM equipment_maintenance WHERE id = :record_id")
    check_result = db.session.execute(check_sql, {'record_id': record_id})
    if not check_result.fetchone():
        return jsonify({'error': '维护记录不存在'}), 404
    
    # 使用原生SQL DELETE
    delete_sql = text("DELETE FROM equipment_maintenance WHERE id = :record_id")
    db.session.execute(delete_sql, {'record_id': record_id})
    db.session.commit()
    
    return jsonify({'message': '设备维护记录删除成功'})


@app.route('/api/alert_records')
def get_alert_records():
    """获取报警记录"""
    records = get_alert_records()
    return jsonify(records)


# 报警记录管理API（管理员）
@app.route('/api/alert_record', methods=['GET'])
def get_alert_record():
    """获取报警记录列表（使用原生SQL）"""
    # 使用原生SQL查询
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
    
    return jsonify(records)


@app.route('/api/alert_record/<int:record_id>', methods=['PUT'])
@admin_required
def update_alert_record(record_id):
    """更新报警记录（主要用于标记已处理，使用原生SQL）"""
    data = request.get_json()
    
    # 先检查记录是否存在
    check_sql = text("SELECT id FROM alert_record WHERE id = :record_id")
    check_result = db.session.execute(check_sql, {'record_id': record_id})
    if not check_result.fetchone():
        return jsonify({'error': '报警记录不存在'}), 404
    
    # 确定resolved_time的值
    status = data.get('status')
    resolved_time = None
    if status == 'resolved':
        if 'resolved_time' in data:
            resolved_time = datetime.fromisoformat(data['resolved_time'])
        else:
            resolved_time = datetime.now()
    elif 'resolved_time' in data:
        resolved_time = datetime.fromisoformat(data['resolved_time'])
    
    # 使用原生SQL UPDATE
    if resolved_time:
        sql = text("""
            UPDATE alert_record 
            SET status = :status,
                resolved_time = :resolved_time
            WHERE id = :record_id
            RETURNING id, alert_id, point_code, alert_type, alert_time, energy_value, threshold,
                     description, severity, status, resolved_time, created_at
        """)
        result = db.session.execute(sql, {
            'record_id': record_id,
            'status': status,
            'resolved_time': resolved_time
        })
    else:
        sql = text("""
            UPDATE alert_record 
            SET status = :status
            WHERE id = :record_id
            RETURNING id, alert_id, point_code, alert_type, alert_time, energy_value, threshold,
                     description, severity, status, resolved_time, created_at
        """)
        result = db.session.execute(sql, {
            'record_id': record_id,
            'status': status
        })
    
    db.session.commit()
    row = result.fetchone()
    
    return jsonify({
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


@app.route('/api/alert_record/<int:record_id>', methods=['DELETE'])
@admin_required
def delete_alert_record(record_id):
    """删除报警记录（使用原生SQL）"""
    # 先检查记录是否存在
    check_sql = text("SELECT id FROM alert_record WHERE id = :record_id")
    check_result = db.session.execute(check_sql, {'record_id': record_id})
    if not check_result.fetchone():
        return jsonify({'error': '报警记录不存在'}), 404
    
    # 使用原生SQL DELETE
    delete_sql = text("DELETE FROM alert_record WHERE id = :record_id")
    db.session.execute(delete_sql, {'record_id': record_id})
    db.session.commit()
    
    return jsonify({'message': '报警记录删除成功'})


# 能耗成本管理API（管理员）
@app.route('/api/energy_cost', methods=['GET'])
def get_energy_cost():
    """获取能耗成本列表（使用原生SQL）"""
    # 使用原生SQL查询
    sql = text("""
        SELECT id, cost_id, energy_type, unit_price, effective_date, created_at
        FROM energy_cost
        ORDER BY effective_date DESC
    """)
    
    result = db.session.execute(sql)
    records = []
    for row in result:
        records.append({
            'id': row.id,
            'cost_id': row.cost_id,
            'energy_type': row.energy_type,
            'unit_price': float(row.unit_price),
            'effective_date': row.effective_date.isoformat() if row.effective_date else None,
            'created_at': row.created_at.isoformat() if row.created_at else None
        })
    
    return jsonify(records)


@app.route('/api/energy_cost', methods=['POST'])
@admin_required
def add_energy_cost():
    """添加能耗成本记录（使用原生SQL）"""
    data = request.get_json()
    
    # 使用原生SQL INSERT
    sql = text("""
        INSERT INTO energy_cost 
        (cost_id, energy_type, unit_price, effective_date, created_at)
        VALUES 
        (:cost_id, :energy_type, :unit_price, :effective_date, NOW())
        RETURNING id, cost_id, energy_type, unit_price, effective_date, created_at
    """)
    
    result = db.session.execute(sql, {
        'cost_id': data['cost_id'],
        'energy_type': data['energy_type'],
        'unit_price': float(data['unit_price']),
        'effective_date': datetime.fromisoformat(data['effective_date'])
    })
    
    db.session.commit()
    row = result.fetchone()
    
    return jsonify({
        'id': row.id,
        'cost_id': row.cost_id,
        'energy_type': row.energy_type,
        'unit_price': float(row.unit_price),
        'effective_date': row.effective_date.isoformat() if row.effective_date else None,
        'created_at': row.created_at.isoformat() if row.created_at else None
    })


@app.route('/api/energy_cost/<int:record_id>', methods=['PUT'])
@admin_required
def update_energy_cost(record_id):
    """更新能耗成本记录（使用原生SQL）"""
    data = request.get_json()
    
    # 先检查记录是否存在
    check_sql = text("SELECT id FROM energy_cost WHERE id = :record_id")
    check_result = db.session.execute(check_sql, {'record_id': record_id})
    if not check_result.fetchone():
        return jsonify({'error': '成本记录不存在'}), 404
    
    # 使用原生SQL UPDATE
    sql = text("""
        UPDATE energy_cost 
        SET energy_type = :energy_type,
            unit_price = :unit_price,
            effective_date = :effective_date
        WHERE id = :record_id
        RETURNING id, cost_id, energy_type, unit_price, effective_date, created_at
    """)
    
    result = db.session.execute(sql, {
        'record_id': record_id,
        'energy_type': data.get('energy_type'),
        'unit_price': float(data.get('unit_price')),
        'effective_date': datetime.fromisoformat(data['effective_date']) if 'effective_date' in data else None
    })
    
    db.session.commit()
    row = result.fetchone()
    
    return jsonify({
        'id': row.id,
        'cost_id': row.cost_id,
        'energy_type': row.energy_type,
        'unit_price': float(row.unit_price),
        'effective_date': row.effective_date.isoformat() if row.effective_date else None,
        'created_at': row.created_at.isoformat() if row.created_at else None
    })


@app.route('/api/energy_cost/<int:record_id>', methods=['DELETE'])
@admin_required
def delete_energy_cost(record_id):
    """删除能耗成本记录（使用原生SQL）"""
    # 先检查记录是否存在
    check_sql = text("SELECT id FROM energy_cost WHERE id = :record_id")
    check_result = db.session.execute(check_sql, {'record_id': record_id})
    if not check_result.fetchone():
        return jsonify({'error': '成本记录不存在'}), 404
    
    # 使用原生SQL DELETE
    delete_sql = text("DELETE FROM energy_cost WHERE id = :record_id")
    db.session.execute(delete_sql, {'record_id': record_id})
    db.session.commit()
    
    return jsonify({'message': '能耗成本记录删除成功'})


# ========== 批量操作API ==========

@app.route('/api/monitor_points/batch_delete', methods=['POST'])
@admin_required
def batch_delete_monitor_points():
    """批量删除监测点"""
    data = request.get_json()
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'error': '请提供要删除的ID列表'}), 400
    
    deleted_count = 0
    errors = []
    
    for point_id in ids:
        try:
            # 检查监测点是否存在
            get_sql = text("SELECT point_code FROM monitor_point WHERE id = :point_id")
            result = db.session.execute(get_sql, {'point_id': point_id})
            point_row = result.fetchone()
            
            if not point_row:
                errors.append(f'ID {point_id}: 监测点不存在')
                continue
            
            point_code = point_row.point_code
            
            # 检查是否有能耗记录
            check_sql = text("SELECT COUNT(*) as count FROM energy WHERE point_code = :point_code")
            check_result = db.session.execute(check_sql, {'point_code': point_code})
            count = check_result.fetchone().count
            
            if count > 0:
                errors.append(f'ID {point_id}: 该监测点已有能耗记录，无法删除')
                continue
            
            # 删除监测点
            delete_sql = text("DELETE FROM monitor_point WHERE id = :point_id")
            db.session.execute(delete_sql, {'point_id': point_id})
            deleted_count += 1
        except Exception as e:
            errors.append(f'ID {point_id}: {str(e)}')
    
    db.session.commit()
    
    return jsonify({
        'deleted_count': deleted_count,
        'errors': errors if errors else None
    })


@app.route('/api/energy_records/batch_delete', methods=['POST'])
@admin_required
def batch_delete_energy_records():
    """批量删除能耗记录（仅允许删除24小时内的记录）"""
    data = request.get_json()
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'error': '请提供要删除的ID列表'}), 400
    
    deleted_count = 0
    errors = []
    
    for record_id in ids:
        try:
            # 检查记录是否在24小时内
            check_sql = text("""
                SELECT id, collection_time,
                       EXTRACT(EPOCH FROM (NOW() - collection_time)) / 3600 as hours_diff
                FROM energy 
                WHERE id = :record_id
            """)
            result = db.session.execute(check_sql, {'record_id': record_id})
            record_row = result.fetchone()
            
            if not record_row:
                errors.append(f'ID {record_id}: 记录不存在')
                continue
            
            if record_row.hours_diff > 24:
                errors.append(f'ID {record_id}: 只能删除24小时内的记录')
                continue
            
            # 删除记录
            delete_sql = text("DELETE FROM energy WHERE id = :record_id")
            db.session.execute(delete_sql, {'record_id': record_id})
            deleted_count += 1
        except Exception as e:
            errors.append(f'ID {record_id}: {str(e)}')
    
    db.session.commit()
    
    return jsonify({
        'deleted_count': deleted_count,
        'errors': errors if errors else None
    })


@app.route('/api/equipment_maintenance/batch_delete', methods=['POST'])
@admin_required
def batch_delete_maintenance():
    """批量删除设备维护记录"""
    data = request.get_json()
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'error': '请提供要删除的ID列表'}), 400
    
    deleted_count = 0
    errors = []
    
    for record_id in ids:
        try:
            # 检查记录是否存在
            check_sql = text("SELECT id FROM equipment_maintenance WHERE id = :record_id")
            check_result = db.session.execute(check_sql, {'record_id': record_id})
            if not check_result.fetchone():
                errors.append(f'ID {record_id}: 记录不存在')
                continue
            
            # 删除记录
            delete_sql = text("DELETE FROM equipment_maintenance WHERE id = :record_id")
            db.session.execute(delete_sql, {'record_id': record_id})
            deleted_count += 1
        except Exception as e:
            errors.append(f'ID {record_id}: {str(e)}')
    
    db.session.commit()
    
    return jsonify({
        'deleted_count': deleted_count,
        'errors': errors if errors else None
    })


@app.route('/api/energy_cost/batch_delete', methods=['POST'])
@admin_required
def batch_delete_energy_cost():
    """批量删除能耗成本记录"""
    data = request.get_json()
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'error': '请提供要删除的ID列表'}), 400
    
    deleted_count = 0
    errors = []
    
    for record_id in ids:
        try:
            # 检查记录是否存在
            check_sql = text("SELECT id FROM energy_cost WHERE id = :record_id")
            check_result = db.session.execute(check_sql, {'record_id': record_id})
            if not check_result.fetchone():
                errors.append(f'ID {record_id}: 记录不存在')
                continue
            
            # 删除记录
            delete_sql = text("DELETE FROM energy_cost WHERE id = :record_id")
            db.session.execute(delete_sql, {'record_id': record_id})
            deleted_count += 1
        except Exception as e:
            errors.append(f'ID {record_id}: {str(e)}')
    
    db.session.commit()
    
    return jsonify({
        'deleted_count': deleted_count,
        'errors': errors if errors else None
    })


@app.route('/api/monitor_points/batch_insert', methods=['POST'])
@admin_required
def batch_insert_monitor_points():
    """批量插入监测点"""
    try:
        data = request.get_json()
        if data is None:
            return jsonify({'error': '请求体必须是有效的JSON格式'}), 400
        
        records = data.get('records', [])
        
        if not records:
            return jsonify({'error': '请提供要插入的记录列表'}), 400
        
        inserted_count = 0
        errors = []
        
        for record in records:
            try:
                # 检查监测点编号是否已存在
                check_sql = text("SELECT id FROM monitor_point WHERE point_code = :point_code")
                check_result = db.session.execute(check_sql, {'point_code': record['point_code']})
                if check_result.fetchone():
                    errors.append(f"监测点编号 {record['point_code']}: 已存在")
                    continue
                
                # 插入记录
                insert_sql = text("""
                    INSERT INTO monitor_point 
                    (point_code, equipment_name, workshop, energy_type, unit, threshold, description, created_at, updated_at)
                    VALUES 
                    (:point_code, :equipment_name, :workshop, :energy_type, :unit, :threshold, :description, NOW(), NOW())
                """)
                db.session.execute(insert_sql, {
                    'point_code': record['point_code'],
                    'equipment_name': record['equipment_name'],
                    'workshop': record['workshop'],
                    'energy_type': record['energy_type'],
                    'unit': record['unit'],
                    'threshold': record['threshold'],
                    'description': record.get('description', '')
                })
                inserted_count += 1
            except Exception as e:
                errors.append(f"监测点编号 {record.get('point_code', '未知')}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'inserted_count': inserted_count,
            'errors': errors if errors else None
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'批量插入失败: {str(e)}'}), 500


@app.route('/api/energy_records/batch_insert', methods=['POST'])
@admin_required
def batch_insert_energy_records():
    """批量插入能耗记录"""
    try:
        data = request.get_json()
        if data is None:
            return jsonify({'error': '请求体必须是有效的JSON格式'}), 400
        
        records = data.get('records', [])
        
        if not records:
            return jsonify({'error': '请提供要插入的记录列表'}), 400
        
        inserted_count = 0
        errors = []
        
        for record in records:
            try:
                # 检查记录ID是否已存在
                check_sql = text("SELECT id FROM energy WHERE record_id = :record_id")
                check_result = db.session.execute(check_sql, {'record_id': record['record_id']})
                if check_result.fetchone():
                    errors.append(f"记录ID {record['record_id']}: 已存在")
                    continue
                
                # 检查监测点是否存在并获取阈值
                point_sql = text("SELECT threshold FROM monitor_point WHERE point_code = :point_code")
                point_result = db.session.execute(point_sql, {'point_code': record['point_code']})
                point_row = point_result.fetchone()
                
                if not point_row:
                    errors.append(f"记录ID {record['record_id']}: 监测点 {record['point_code']} 不存在")
                    continue
                
                threshold = point_row.threshold
                energy_value = record['energy_value']
                collection_status = 'normal' if energy_value <= threshold else 'abnormal'
                
                # 插入记录
                insert_sql = text("""
                    INSERT INTO energy 
                    (record_id, point_code, collection_time, energy_value, collection_status, created_at)
                    VALUES 
                    (:record_id, :point_code, :collection_time, :energy_value, :collection_status, NOW())
                """)
                db.session.execute(insert_sql, {
                    'record_id': record['record_id'],
                    'point_code': record['point_code'],
                    'collection_time': record['collection_time'],
                    'energy_value': energy_value,
                    'collection_status': collection_status
                })
                inserted_count += 1
            except Exception as e:
                errors.append(f"记录ID {record.get('record_id', '未知')}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'inserted_count': inserted_count,
            'errors': errors if errors else None
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'批量插入失败: {str(e)}'}), 500


@app.route('/api/equipment_maintenance/batch_insert', methods=['POST'])
@admin_required
def batch_insert_maintenance():
    """批量插入设备维护记录"""
    try:
        data = request.get_json()
        if data is None:
            return jsonify({'error': '请求体必须是有效的JSON格式'}), 400
        
        records = data.get('records', [])
        
        if not records:
            return jsonify({'error': '请提供要插入的记录列表'}), 400
        
        inserted_count = 0
        errors = []
        
        for record in records:
            try:
                # 检查维护ID是否已存在
                check_sql = text("SELECT id FROM equipment_maintenance WHERE maintenance_id = :maintenance_id")
                check_result = db.session.execute(check_sql, {'maintenance_id': record['maintenance_id']})
                if check_result.fetchone():
                    errors.append(f"维护ID {record['maintenance_id']}: 已存在")
                    continue
                
                # 检查监测点是否存在
                point_sql = text("SELECT id FROM monitor_point WHERE point_code = :point_code")
                point_result = db.session.execute(point_sql, {'point_code': record['point_code']})
                if not point_result.fetchone():
                    errors.append(f"维护ID {record['maintenance_id']}: 监测点 {record['point_code']} 不存在")
                    continue
                
                # 插入记录
                insert_sql = text("""
                    INSERT INTO equipment_maintenance 
                    (maintenance_id, point_code, maintenance_type, maintenance_date, description, cost, status, created_at)
                    VALUES 
                    (:maintenance_id, :point_code, :maintenance_type, :maintenance_date, :description, :cost, :status, NOW())
                """)
                db.session.execute(insert_sql, {
                    'maintenance_id': record['maintenance_id'],
                    'point_code': record['point_code'],
                    'maintenance_type': record['maintenance_type'],
                    'maintenance_date': record['maintenance_date'],
                    'description': record.get('description', ''),
                    'cost': record.get('cost', 0),
                    'status': record.get('status', 'completed')
                })
                inserted_count += 1
            except Exception as e:
                errors.append(f"维护ID {record.get('maintenance_id', '未知')}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'inserted_count': inserted_count,
            'errors': errors if errors else None
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'批量插入失败: {str(e)}'}), 500


@app.route('/api/energy_cost/batch_insert', methods=['POST'])
@admin_required
def batch_insert_energy_cost():
    """批量插入能耗成本记录"""
    try:
        data = request.get_json()
        if data is None:
            return jsonify({'error': '请求体必须是有效的JSON格式'}), 400
        
        records = data.get('records', [])
        
        if not records:
            return jsonify({'error': '请提供要插入的记录列表'}), 400
        
        inserted_count = 0
        errors = []
        
        for record in records:
            try:
                # 检查成本ID是否已存在
                check_sql = text("SELECT id FROM energy_cost WHERE cost_id = :cost_id")
                check_result = db.session.execute(check_sql, {'cost_id': record['cost_id']})
                if check_result.fetchone():
                    errors.append(f"成本ID {record['cost_id']}: 已存在")
                    continue
                
                # 插入记录
                insert_sql = text("""
                    INSERT INTO energy_cost 
                    (cost_id, energy_type, unit_price, effective_date, created_at)
                    VALUES 
                    (:cost_id, :energy_type, :unit_price, :effective_date, NOW())
                """)
                db.session.execute(insert_sql, {
                    'cost_id': record['cost_id'],
                    'energy_type': record['energy_type'],
                    'unit_price': record['unit_price'],
                    'effective_date': record['effective_date']
                })
                inserted_count += 1
            except Exception as e:
                errors.append(f"成本ID {record.get('cost_id', '未知')}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'inserted_count': inserted_count,
            'errors': errors if errors else None
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'批量插入失败: {str(e)}'}), 500


@app.route('/api/alert_record/batch_insert', methods=['POST'])
@admin_required
def batch_insert_alert_records():
    """批量插入报警记录"""
    try:
        data = request.get_json()
        if data is None:
            return jsonify({'error': '请求体必须是有效的JSON格式'}), 400
        
        records = data.get('records', [])
        
        if not records:
            return jsonify({'error': '请提供要插入的记录列表'}), 400
        
        inserted_count = 0
        errors = []
        
        for record in records:
            try:
                # 检查报警ID是否已存在
                check_sql = text("SELECT id FROM alert_record WHERE alert_id = :alert_id")
                check_result = db.session.execute(check_sql, {'alert_id': record['alert_id']})
                if check_result.fetchone():
                    errors.append(f"报警ID {record['alert_id']}: 已存在")
                    continue
                
                # 检查监测点是否存在
                point_sql = text("SELECT id FROM monitor_point WHERE point_code = :point_code")
                point_result = db.session.execute(point_sql, {'point_code': record['point_code']})
                if not point_result.fetchone():
                    errors.append(f"报警ID {record['alert_id']}: 监测点 {record['point_code']} 不存在")
                    continue
                
                # 插入记录
                insert_sql = text("""
                    INSERT INTO alert_record 
                    (alert_id, point_code, alert_type, alert_time, energy_value, threshold, description, severity, status, created_at)
                    VALUES 
                    (:alert_id, :point_code, :alert_type, :alert_time, :energy_value, :threshold, :description, :severity, :status, NOW())
                """)
                db.session.execute(insert_sql, {
                    'alert_id': record['alert_id'],
                    'point_code': record['point_code'],
                    'alert_type': record['alert_type'],
                    'alert_time': record['alert_time'],
                    'energy_value': record.get('energy_value'),
                    'threshold': record.get('threshold'),
                    'description': record.get('description', ''),
                    'severity': record.get('severity', 'medium'),
                    'status': record.get('status', 'active')
                })
                inserted_count += 1
            except Exception as e:
                errors.append(f"报警ID {record.get('alert_id', '未知')}: {str(e)}")
        
        db.session.commit()
        
        return jsonify({
            'inserted_count': inserted_count,
            'errors': errors if errors else None
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'批量插入失败: {str(e)}'}), 500


@app.route('/api/alert_record/batch_delete', methods=['POST'])
@admin_required
def batch_delete_alert_records():
    """批量删除报警记录"""
    data = request.get_json()
    ids = data.get('ids', [])
    
    if not ids:
        return jsonify({'error': '请提供要删除的ID列表'}), 400
    
    deleted_count = 0
    errors = []
    
    for record_id in ids:
        try:
            # 检查记录是否存在
            check_sql = text("SELECT id FROM alert_record WHERE id = :record_id")
            check_result = db.session.execute(check_sql, {'record_id': record_id})
            if not check_result.fetchone():
                errors.append(f'ID {record_id}: 记录不存在')
                continue
            
            # 删除记录
            delete_sql = text("DELETE FROM alert_record WHERE id = :record_id")
            db.session.execute(delete_sql, {'record_id': record_id})
            deleted_count += 1
        except Exception as e:
            errors.append(f'ID {record_id}: {str(e)}')
    
    db.session.commit()
    
    return jsonify({
        'deleted_count': deleted_count,
        'errors': errors if errors else None
    })


@app.route('/api/predictions_history')
def get_predictions_history():
    """获取预测历史记录"""
    try:
        point_code = request.args.get('point_code')
        records = get_predictions_history_from_utils(point_code)
        return jsonify(records)
    except Exception as e:
        import traceback
        print(f"获取预测历史记录失败: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'获取预测历史记录失败: {str(e)}'}), 500


@app.route('/api/anomaly_detection_history')
def get_anomaly_detection_history():
    """获取异常检测历史记录"""
    try:
        point_code = request.args.get('point_code')
        records = get_anomaly_detection_history_from_utils(point_code)
        return jsonify(records)
    except Exception as e:
        import traceback
        print(f"获取异常检测历史记录失败: {e}")
        print(traceback.format_exc())
        return jsonify({'error': f'获取异常检测历史记录失败: {str(e)}'}), 500


@app.route('/api/performance_stats')
def get_performance_stats():
    """获取列存储性能统计"""
    stats = get_columnar_performance_stats()
    return jsonify(stats)


@app.route('/api/health')
def health_check():
    """系统健康检查（使用原生SQL）"""
    try:
        # 检查数据库连接（使用原生SQL）
        db.session.execute(text('SELECT 1'))

        # 检查各表数据量（使用原生SQL）
        monitor_points_sql = text("SELECT COUNT(*) as count FROM monitor_point")
        energy_records_sql = text("SELECT COUNT(*) as count FROM energy")
        maintenance_records_sql = text("SELECT COUNT(*) as count FROM equipment_maintenance")
        alert_records_sql = text("SELECT COUNT(*) as count FROM alert_record")
        
        monitor_points = db.session.execute(monitor_points_sql).fetchone().count
        energy_records = db.session.execute(energy_records_sql).fetchone().count
        maintenance_records = db.session.execute(maintenance_records_sql).fetchone().count
        alert_records = db.session.execute(alert_records_sql).fetchone().count

        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'monitor_points': monitor_points,
            'energy_records': energy_records,
            'maintenance_records': maintenance_records,
            'alert_records': alert_records,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


if __name__ == '__main__':
    app.run(debug=True)