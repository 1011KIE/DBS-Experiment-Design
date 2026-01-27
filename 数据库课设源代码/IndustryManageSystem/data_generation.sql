-- 工厂能源管理系统数据生成脚本
-- 生成10个监测点，2000条能耗记录，覆盖3个月数据

-- 清空现有数据
TRUNCATE TABLE energy RESTART IDENTITY CASCADE;
TRUNCATE TABLE monitor_point RESTART IDENTITY CASCADE;
TRUNCATE TABLE equipment_maintenance RESTART IDENTITY CASCADE;
TRUNCATE TABLE energy_cost RESTART IDENTITY CASCADE;
TRUNCATE TABLE alert_record RESTART IDENTITY CASCADE;
TRUNCATE TABLE prediction_result RESTART IDENTITY CASCADE;
TRUNCATE TABLE anomaly_detection RESTART IDENTITY CASCADE;

-- 插入能耗监测点数据
INSERT INTO monitor_point (point_code, equipment_name, workshop, energy_type, unit, threshold, description, created_at, updated_at) VALUES
('MP001', '设备1', '车间A', '电力', 'kWh', 150.0, '车间A主要设备电力监测', NOW(), NOW()),
('MP002', '设备2', '车间A', '水资源', 'm³', 80.0, '车间A水资源消耗监测', NOW(), NOW()),
('MP003', '设备3', '车间B', '电力', 'kWh', 120.0, '车间B设备电力监测', NOW(), NOW()),
('MP004', '设备4', '车间B', '燃气', 'm³', 60.0, '车间B燃气消耗监测', NOW(), NOW()),
('MP005', '设备5', '车间C', '电力', 'kWh', 200.0, '车间C大型设备电力监测', NOW(), NOW()),
('MP006', '设备6', '车间C', '蒸汽', 't', 15.0, '车间C蒸汽消耗监测', NOW(), NOW()),
('MP007', '设备7', '车间D', '电力', 'kWh', 90.0, '车间D设备电力监测', NOW(), NOW()),
('MP008', '设备8', '车间D', '水资源', 'm³', 50.0, '车间D水资源监测', NOW(), NOW()),
('MP009', '设备9', '车间E', '电力', 'kWh', 180.0, '车间E设备电力监测', NOW(), NOW()),
('MP010', '设备10', '车间E', '燃气', 'm³', 70.0, '车间E燃气监测', NOW(), NOW());

-- 插入能耗成本数据
INSERT INTO energy_cost (cost_id, energy_type, unit_price, effective_date, created_at) VALUES
('COST001', '电力', 0.8, '2024-01-01', NOW()),
('COST002', '水资源', 3.5, '2024-01-01', NOW()),
('COST003', '燃气', 2.8, '2024-01-01', NOW()),
('COST004', '蒸汽', 120.0, '2024-01-01', NOW());

-- 生成2000条能耗记录（每小时1条，覆盖3个月）
DO $$
DECLARE
    start_time TIMESTAMP := NOW() - INTERVAL '90 days';
    current_time TIMESTAMP := start_time;
    i INTEGER := 0;
    point_codes TEXT[] := ARRAY['MP001','MP002','MP003','MP004','MP005','MP006','MP007','MP008','MP009','MP010'];
    selected_point TEXT;
    base_value FLOAT;
    threshold_val FLOAT;
    status_val TEXT;
BEGIN
    FOR i IN 0..1999 LOOP
        -- 随机选择监测点
        selected_point := point_codes[1 + (i % 10)];

        -- 获取该监测点的阈值
        SELECT threshold INTO threshold_val FROM monitor_point WHERE point_code = selected_point;

        -- 生成基础能耗值（阈值的30%-120%）
        base_value := threshold_val * (0.3 + random() * 0.9);

        -- 5%概率生成异常值（超过阈值的120%）
        IF random() < 0.05 THEN
            base_value := threshold_val * (1.2 + random() * 1.3);
            status_val := 'abnormal';
        ELSE
            status_val := 'normal';
        END IF;

        -- 插入能耗记录
        INSERT INTO energy (record_id, point_code, collection_time, energy_value, collection_status, created_at)
        VALUES (
            'ER' || LPAD((i+1)::TEXT, 6, '0'),
            selected_point,
            current_time,
            base_value,
            status_val,
            NOW()
        );

        -- 增加1小时
        current_time := current_time + INTERVAL '1 hour';
    END LOOP;
END $$;

-- 插入设备维护记录
INSERT INTO equipment_maintenance (maintenance_id, point_code, maintenance_type, maintenance_date, description, cost, status, created_at) VALUES
('MAINT001', 'MP001', '日常维护', NOW() - INTERVAL '15 days', '设备1日常保养', 500.0, 'completed', NOW()),
('MAINT002', 'MP003', '故障维修', NOW() - INTERVAL '5 days', '设备3电机故障维修', 2000.0, 'completed', NOW()),
('MAINT003', 'MP005', '定期检修', NOW() - INTERVAL '30 days', '设备5季度检修', 1500.0, 'completed', NOW()),
('MAINT004', 'MP007', '日常维护', NOW() - INTERVAL '10 days', '设备7日常保养', 400.0, 'completed', NOW()),
('MAINT005', 'MP009', '定期检修', NOW() - INTERVAL '25 days', '设备9月度检修', 800.0, 'completed', NOW());

-- 插入报警记录
INSERT INTO alert_record (alert_id, point_code, alert_type, alert_time, energy_value, threshold, description, severity, status, created_at) VALUES
('ALERT001', 'MP001', 'threshold_exceeded', NOW() - INTERVAL '2 days', 180.5, 150.0, '电力消耗超过阈值', 'high', 'resolved', NOW()),
('ALERT002', 'MP002', 'threshold_exceeded', NOW() - INTERVAL '1 day', 95.2, 80.0, '水资源消耗异常', 'medium', 'acknowledged', NOW()),
('ALERT003', 'MP005', 'equipment_failure', NOW() - INTERVAL '3 days', 250.8, 200.0, '设备5能耗异常升高', 'critical', 'resolved', NOW());

-- 生成预测结果数据
INSERT INTO prediction_result (prediction_id, point_code, prediction_time, predicted_value, confidence_interval, model_type, created_at) VALUES
('PRED_MP001_20241201', 'MP001', NOW() + INTERVAL '1 day', 145.2, 0.85, 'db4ai', NOW()),
('PRED_MP001_20241202', 'MP001', NOW() + INTERVAL '2 days', 148.7, 0.82, 'db4ai', NOW()),
('PRED_MP003_20241201', 'MP003', NOW() + INTERVAL '1 day', 118.5, 0.88, 'db4ai', NOW());

-- 生成异常检测结果
INSERT INTO anomaly_detection (detection_id, point_code, detection_time, energy_value, anomaly_score, is_anomaly, detection_method, created_at) VALUES
('ANOM_MP001_20241130', 'MP001', NOW() - INTERVAL '1 day', 180.5, 0.92, true, 'db4ai', NOW()),
('ANOM_MP002_20241129', 'MP002', NOW() - INTERVAL '2 days', 95.2, 0.78, true, 'db4ai', NOW());

-- 创建索引优化查询性能
CREATE INDEX IF NOT EXISTS idx_energy_composite ON energy (collection_time, point_code);
CREATE INDEX IF NOT EXISTS idx_energy_status ON energy (collection_status);
CREATE INDEX IF NOT EXISTS idx_monitor_workshop ON monitor_point (workshop);
CREATE INDEX IF NOT EXISTS idx_monitor_energy_type ON monitor_point (energy_type);

-- 统计信息
SELECT
    '数据生成完成' as status,
    (SELECT COUNT(*) FROM monitor_point) as monitor_points,
    (SELECT COUNT(*) FROM energy) as energy_records,
    (SELECT COUNT(*) FROM equipment_maintenance) as maintenance_records,
    (SELECT COUNT(*) FROM alert_record) as alert_records,
    (SELECT COUNT(*) FROM prediction_result) as prediction_results,
    (SELECT COUNT(*) FROM anomaly_detection) as anomaly_detections;