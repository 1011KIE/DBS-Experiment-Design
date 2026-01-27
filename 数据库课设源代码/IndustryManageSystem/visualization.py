import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime, timedelta
from models import db, EnergyRecord, MonitorPoint

def create_energy_trend_chart(point_code, start_date, end_date, period='day'):
    """创建能耗趋势图表"""
    from sqlalchemy import func
    
    # 根据周期聚合数据
    if period == 'hour':
        trends = db.session.query(
            func.date_trunc('hour', EnergyRecord.collection_time).label('time_period'),
            func.avg(EnergyRecord.energy_value).label('avg_energy'),
            func.max(EnergyRecord.energy_value).label('max_energy'),
            func.min(EnergyRecord.energy_value).label('min_energy'),
            func.count(EnergyRecord.id).label('count')
        ).filter(EnergyRecord.point_code == point_code)\
         .filter(EnergyRecord.collection_time >= start_date)\
         .filter(EnergyRecord.collection_time <= end_date)\
         .group_by(func.date_trunc('hour', EnergyRecord.collection_time))\
         .order_by('time_period')\
         .all()
    elif period == 'day':
        trends = db.session.query(
            func.date_trunc('day', EnergyRecord.collection_time).label('time_period'),
            func.avg(EnergyRecord.energy_value).label('avg_energy'),
            func.max(EnergyRecord.energy_value).label('max_energy'),
            func.min(EnergyRecord.energy_value).label('min_energy'),
            func.count(EnergyRecord.id).label('count')
        ).filter(EnergyRecord.point_code == point_code)\
         .filter(EnergyRecord.collection_time >= start_date)\
         .filter(EnergyRecord.collection_time <= end_date)\
         .group_by(func.date_trunc('day', EnergyRecord.collection_time))\
         .order_by('time_period')\
         .all()
    elif period == 'week':
        trends = db.session.query(
            func.date_trunc('week', EnergyRecord.collection_time).label('time_period'),
            func.avg(EnergyRecord.energy_value).label('avg_energy'),
            func.max(EnergyRecord.energy_value).label('max_energy'),
            func.min(EnergyRecord.energy_value).label('min_energy'),
            func.count(EnergyRecord.id).label('count')
        ).filter(EnergyRecord.point_code == point_code)\
         .filter(EnergyRecord.collection_time >= start_date)\
         .filter(EnergyRecord.collection_time <= end_date)\
         .group_by(func.date_trunc('week', EnergyRecord.collection_time))\
         .order_by('time_period')\
         .all()
    
    if not trends:
        return go.Figure(data=go.Scatter(x=[], y=[], mode='lines+markers')).to_html()
    
    df = pd.DataFrame([{
        'time_period': trend.time_period,
        'avg_energy': float(trend.avg_energy),
        'max_energy': float(trend.max_energy),
        'min_energy': float(trend.min_energy),
        'count': trend.count
    } for trend in trends])
    
    fig = go.Figure()
    
    # 添加平均能耗线
    fig.add_trace(go.Scatter(
        x=df['time_period'],
        y=df['avg_energy'],
        mode='lines+markers',
        name='平均能耗',
        line=dict(color='#1f77b4', width=2),
        marker=dict(size=6)
    ))
    
    # 添加最高能耗线
    fig.add_trace(go.Scatter(
        x=df['time_period'],
        y=df['max_energy'],
        mode='lines',
        name='最高能耗',
        line=dict(color='#ff7f0e', dash='dash'),
        showlegend=True
    ))
    
    # 添加最低能耗线
    fig.add_trace(go.Scatter(
        x=df['time_period'],
        y=df['min_energy'],
        mode='lines',
        name='最低能耗',
        line=dict(color='#2ca02c', dash='dash'),
        showlegend=True
    ))
    
    fig.update_layout(
        title=f'监测点 {point_code} 能耗趋势图 ({period})',
        xaxis_title='时间',
        yaxis_title='能耗值',
        hovermode='x unified',
        template='plotly_white'
    )
    
    return fig.to_html()

def create_energy_distribution_chart(group_by='workshop', start_date=None, end_date=None):
    """创建能耗分布图表"""
    from sqlalchemy import func
    
    # 构建查询
    query = db.session.query(
        getattr(MonitorPoint, group_by).label('group_field'),
        func.sum(EnergyRecord.energy_value).label('total_energy'),
        func.avg(EnergyRecord.energy_value).label('avg_energy'),
        func.count(EnergyRecord.id).label('record_count')
    ).join(EnergyRecord, MonitorPoint.point_code == EnergyRecord.point_code)
    
    # 添加时间过滤
    if start_date:
        query = query.filter(EnergyRecord.collection_time >= start_date)
    if end_date:
        query = query.filter(EnergyRecord.collection_time <= end_date)
    
    results = query.group_by(getattr(MonitorPoint, group_by)).all()
    
    if not results:
        return go.Figure(data=go.Bar(x=[], y=[])).to_html()
    
    df = pd.DataFrame([{
        'group': result.group_field,
        'total_energy': float(result.total_energy),
        'avg_energy': float(result.avg_energy),
        'record_count': result.record_count
    } for result in results])
    
    # 创建柱状图
    fig = px.bar(df, 
                 x='group', 
                 y='total_energy', 
                 title=f'按{group_by}统计的总能耗',
                 labels={'group': group_by, 'total_energy': '总能耗'},
                 color='total_energy',
                 color_continuous_scale='viridis')
    
    return fig.to_html()

def create_anomaly_chart(start_date, end_date):
    """创建异常记录图表"""
    from sqlalchemy import func
    
    anomalies = db.session.query(
        EnergyRecord,
        MonitorPoint
    ).join(MonitorPoint, EnergyRecord.point_code == MonitorPoint.point_code)\
     .filter(EnergyRecord.energy_value > MonitorPoint.threshold)\
     .filter(EnergyRecord.collection_time >= start_date)\
     .filter(EnergyRecord.collection_time <= end_date)\
     .all()
    
    if not anomalies:
        return go.Figure(data=go.Scatter(x=[], y=[], mode='markers')).to_html()
    
    df = pd.DataFrame([{
        'time': anomaly.EnergyRecord.collection_time,
        'energy_value': anomaly.EnergyRecord.energy_value,
        'threshold': anomaly.MonitorPoint.threshold,
        'point_code': anomaly.EnergyRecord.point_code,
        'equipment': anomaly.MonitorPoint.equipment_name
    } for anomaly in anomalies])
    
    fig = go.Figure()
    
    # 添加异常点
    fig.add_trace(go.Scatter(
        x=df['time'],
        y=df['energy_value'],
        mode='markers',
        name='异常能耗值',
        marker=dict(color='red', size=8),
        text=df['point_code'] + '<br>' + df['equipment'],
        hovertemplate='<b>%{text}</b><br>时间: %{x}<br>能耗值: %{y}<extra></extra>'
    ))
    
    fig.update_layout(
        title='异常能耗记录分布',
        xaxis_title='时间',
        yaxis_title='能耗值',
        hovermode='closest',
        template='plotly_white'
    )
    
    return fig.to_html()

def create_dashboard_charts():
    """创建仪表盘图表"""
    # 获取最近30天的数据
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # 获取能耗趋势数据
    trends = db.session.query(
        func.date_trunc('day', EnergyRecord.collection_time).label('time_period'),
        func.avg(EnergyRecord.energy_value).label('avg_energy'),
        func.count(EnergyRecord.id).label('record_count')
    ).filter(EnergyRecord.collection_time >= start_date)\
     .filter(EnergyRecord.collection_time <= end_date)\
     .group_by(func.date_trunc('day', EnergyRecord.collection_time))\
     .order_by('time_period')\
     .all()
    
    if trends:
        df = pd.DataFrame([{
            'time_period': trend.time_period,
            'avg_energy': float(trend.avg_energy),
            'record_count': trend.record_count
        } for trend in trends])
        
        # 创建趋势图
        trend_fig = go.Figure()
        trend_fig.add_trace(go.Scatter(
            x=df['time_period'],
            y=df['avg_energy'],
            mode='lines+markers',
            name='平均能耗',
            line=dict(color='#1f77b4', width=2)
        ))
        trend_fig.update_layout(
            title='最近30天能耗趋势',
            xaxis_title='日期',
            yaxis_title='平均能耗',
            template='plotly_white'
        )
        
        trend_html = trend_fig.to_html()
    else:
        trend_html = go.Figure(data=go.Scatter(x=[], y=[], mode='lines+markers')).to_html()
    
    # 获取能耗类型分布
    type_dist = db.session.query(
        MonitorPoint.energy_type,
        func.count(MonitorPoint.id).label('count')
    ).group_by(MonitorPoint.energy_type).all()
    
    if type_dist:
        df_type = pd.DataFrame([{
            'energy_type': dist.energy_type,
            'count': dist.count
        } for dist in type_dist])
        
        type_fig = px.pie(df_type, values='count', names='energy_type', title='能耗类型分布')
        type_html = type_fig.to_html()
    else:
        type_html = go.Figure(data=go.Pie(labels=[], values=[])).to_html()
    
    return trend_html, type_html


def create_prediction_chart_with_history(point_code, days=7):
    """创建双曲线图：历史30天实际能耗 + 未来7天预测值，异常点红色高亮"""
    from sqlalchemy import func
    from db4ai_utils import get_db4ai_predictions
    from utils import get_anomaly_records
    
    # 获取历史30天数据
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    historical_trends = db.session.query(
        func.date_trunc('hour', EnergyRecord.collection_time).label('time_period'),
        func.avg(EnergyRecord.energy_value).label('avg_energy')
    ).filter(EnergyRecord.point_code == point_code)\
     .filter(EnergyRecord.collection_time >= start_date)\
     .filter(EnergyRecord.collection_time <= end_date)\
     .group_by(func.date_trunc('hour', EnergyRecord.collection_time))\
     .order_by('time_period')\
     .all()
    
    # 获取预测数据
    predictions = get_db4ai_predictions(point_code, days)
    
    # 获取异常点
    anomalies = get_anomaly_records(start_date, end_date + timedelta(days=days))
    anomaly_times = {anomaly['collection_time'] for anomaly in anomalies if anomaly['point_code'] == point_code}
    
    fig = go.Figure()
    
    # 添加历史实际能耗（实线）
    if historical_trends:
        hist_times = [trend.time_period for trend in historical_trends]
        hist_values = [float(trend.avg_energy) for trend in historical_trends]
        
        # 标记异常点
        normal_times = []
        normal_values = []
        anomaly_times_list = []
        anomaly_values_list = []
        
        for i, time in enumerate(hist_times):
            time_str = time.isoformat() if isinstance(time, datetime) else str(time)
            if time_str in anomaly_times or any(abs((time - datetime.fromisoformat(a_time.replace('Z', '+00:00').split('+')[0])).total_seconds()) < 3600 for a_time in anomaly_times if isinstance(a_time, str)):
                anomaly_times_list.append(time)
                anomaly_values_list.append(hist_values[i])
            else:
                normal_times.append(time)
                normal_values.append(hist_values[i])
        
        # 正常点（实线）
        if normal_times:
            fig.add_trace(go.Scatter(
                x=normal_times,
                y=normal_values,
                mode='lines+markers',
                name='历史实际能耗',
                line=dict(color='#1f77b4', width=2),
                marker=dict(size=4, color='#1f77b4')
            ))
        
        # 异常点（红色高亮）
        if anomaly_times_list:
            fig.add_trace(go.Scatter(
                x=anomaly_times_list,
                y=anomaly_values_list,
                mode='markers',
                name='异常点',
                marker=dict(color='red', size=10, symbol='x'),
                hovertemplate='<b>异常点</b><br>时间: %{x}<br>能耗值: %{y}<extra></extra>'
            ))
    
    # 添加预测值（虚线）
    if predictions:
        pred_times = [datetime.fromisoformat(pred['prediction_time'].replace('Z', '+00:00').split('+')[0]) for pred in predictions]
        pred_values = [pred['predicted_value'] for pred in predictions]
        
        fig.add_trace(go.Scatter(
            x=pred_times,
            y=pred_values,
            mode='lines+markers',
            name='未来预测值',
            line=dict(color='#ff7f0e', width=2, dash='dash'),
            marker=dict(size=6, color='#ff7f0e')
        ))
    
    # 添加阈值线
    point = MonitorPoint.query.filter_by(point_code=point_code).first()
    if point:
        all_times = []
        if historical_trends:
            all_times.extend([trend.time_period for trend in historical_trends])
        if predictions:
            all_times.extend([datetime.fromisoformat(pred['prediction_time'].replace('Z', '+00:00').split('+')[0]) for pred in predictions])
        
        if all_times:
            fig.add_trace(go.Scatter(
                x=[min(all_times), max(all_times)],
                y=[point.threshold, point.threshold],
                mode='lines',
                name=f'阈值 ({point.threshold})',
                line=dict(color='red', width=1, dash='dot'),
                hovertemplate=f'阈值: {point.threshold}<extra></extra>'
            ))
    
    fig.update_layout(
        title=f'监测点 {point_code} 能耗趋势与预测（历史30天 + 未来{days}天）',
        xaxis_title='时间',
        yaxis_title='能耗值',
        hovermode='x unified',
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    
    return fig.to_html()


def create_multi_point_compare_chart(point_codes, start_date, end_date, period='day'):
    """创建多监测点对比图表"""
    from utils import get_multi_point_trends
    
    compare_data = get_multi_point_trends(point_codes, start_date, end_date, period)
    
    fig = go.Figure()
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    for i, point_code in enumerate(point_codes):
        if point_code not in compare_data['data']:
            continue
            
        point_data = compare_data['data'][point_code]
        trends = point_data['trends']
        
        if trends:
            times = [datetime.fromisoformat(t['time_period'].replace('Z', '+00:00').split('+')[0]) for t in trends]
            values = [t['avg_energy'] for t in trends]
            
            fig.add_trace(go.Scatter(
                x=times,
                y=values,
                mode='lines+markers',
                name=f"{point_code} - {point_data['equipment_name']}",
                line=dict(color=colors[i % len(colors)], width=2),
                marker=dict(size=5),
                hovertemplate=f"<b>{point_code}</b><br>{point_data['equipment_name']}<br>时间: %{{x}}<br>能耗值: %{{y}} {point_data['unit']}<extra></extra>"
            ))
    
    fig.update_layout(
        title=f'多监测点对比图（{len(point_codes)}个监测点）',
        xaxis_title='时间',
        yaxis_title='能耗值',
        hovermode='x unified',
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )
    
    return fig.to_html()