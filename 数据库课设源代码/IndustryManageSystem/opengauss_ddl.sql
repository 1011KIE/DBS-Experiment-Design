-- openGauss数据库DDL脚本
-- 符合需求文档的表结构定义

-- 1. 监测点信息表（行存储）
CREATE TABLE IF NOT EXISTS monitor_point (
    point_id        VARCHAR(20) PRIMARY KEY,     -- 监测点编号（如 MP001）
    equipment_name  VARCHAR(100),                -- 设备/车间名称
    energy_type     VARCHAR(20) NOT NULL,        -- '电力' / '水'
    unit            VARCHAR(10) NOT NULL,        -- 'kWh' / 'm³'
    daily_threshold NUMERIC(10,2) NOT NULL,      -- 单日能耗阈值
    workshop        VARCHAR(100),                -- 车间名称（扩展字段）
    description     TEXT,                        -- 描述信息
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 能耗记录表（列存储 - openGauss特性）
CREATE TABLE IF NOT EXISTS energy (
    record_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    point_id        VARCHAR(20) NOT NULL REFERENCES monitor_point(point_id),
    collect_time    TIMESTAMP NOT NULL,          -- 采集时间（精确到小时）
    energy_value    NUMERIC(12,3) NOT NULL,      -- 能耗值
    status          VARCHAR(10) DEFAULT 'normal'  -- normal / anomaly / missing
) WITH (ORIENTATION = COLUMN);  -- 列存储

-- 创建联合索引提升时间范围查询效率（符合需求文档）
CREATE INDEX IF NOT EXISTS idx_energy_point_time ON energy (point_id, collect_time);

-- 3. 设备维护记录表（行存储）
CREATE TABLE IF NOT EXISTS equipment_maintenance (
    id              SERIAL PRIMARY KEY,
    maintenance_id  VARCHAR(50) UNIQUE NOT NULL,
    point_id        VARCHAR(20) NOT NULL REFERENCES monitor_point(point_id),
    maintenance_type VARCHAR(50) NOT NULL,
    maintenance_date TIMESTAMP NOT NULL,
    description     TEXT,
    cost            NUMERIC(10,2) DEFAULT 0.0,
    status          VARCHAR(20) DEFAULT 'completed',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. 能耗成本表（行存储）
CREATE TABLE IF NOT EXISTS energy_cost (
    id              SERIAL PRIMARY KEY,
    cost_id         VARCHAR(50) UNIQUE NOT NULL,
    energy_type     VARCHAR(50) NOT NULL,
    unit_price      NUMERIC(10,2) NOT NULL,
    effective_date  TIMESTAMP NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. 报警记录表（行存储）
CREATE TABLE IF NOT EXISTS alert_record (
    id              SERIAL PRIMARY KEY,
    alert_id        VARCHAR(50) UNIQUE NOT NULL,
    point_id        VARCHAR(20) NOT NULL REFERENCES monitor_point(point_id),
    alert_type      VARCHAR(50) NOT NULL,
    alert_time      TIMESTAMP NOT NULL,
    energy_value    NUMERIC(12,3),
    threshold       NUMERIC(10,2),
    description     TEXT,
    severity        VARCHAR(20) DEFAULT 'medium',
    status          VARCHAR(20) DEFAULT 'active',
    resolved_time   TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. 预测结果表（行存储）
CREATE TABLE IF NOT EXISTS prediction_result (
    id              SERIAL PRIMARY KEY,
    prediction_id   VARCHAR(50) UNIQUE NOT NULL,
    point_id        VARCHAR(20) NOT NULL REFERENCES monitor_point(point_id),
    prediction_time TIMESTAMP NOT NULL,
    predicted_value NUMERIC(12,3) NOT NULL,
    confidence_interval NUMERIC(5,3),
    model_type      VARCHAR(50) DEFAULT 'db4ai',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. 异常检测结果表（行存储）
CREATE TABLE IF NOT EXISTS anomaly_detection (
    id              SERIAL PRIMARY KEY,
    detection_id   VARCHAR(50) UNIQUE NOT NULL,
    point_id        VARCHAR(20) NOT NULL REFERENCES monitor_point(point_id),
    detection_time  TIMESTAMP NOT NULL,
    energy_value    NUMERIC(12,3) NOT NULL,
    anomaly_score   NUMERIC(5,3) NOT NULL,
    is_anomaly      BOOLEAN DEFAULT FALSE,
    detection_method VARCHAR(50) DEFAULT 'db4ai',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建其他索引
CREATE INDEX IF NOT EXISTS idx_alert_time_point ON alert_record (alert_time, point_id);
CREATE INDEX IF NOT EXISTS idx_alert_status ON alert_record (status);
CREATE INDEX IF NOT EXISTS idx_prediction_time_point ON prediction_result (prediction_time, point_id);
CREATE INDEX IF NOT EXISTS idx_detection_time_point ON anomaly_detection (detection_time, point_id);
CREATE INDEX IF NOT EXISTS idx_is_anomaly ON anomaly_detection (is_anomaly);
CREATE INDEX IF NOT EXISTS idx_monitor_workshop ON monitor_point (workshop);
CREATE INDEX IF NOT EXISTS idx_monitor_energy_type ON monitor_point (energy_type);

-- 注释说明
COMMENT ON TABLE monitor_point IS '监测点信息表（行存储）';
COMMENT ON TABLE energy IS '能耗记录表（列存储，用于时序数据分析）';
COMMENT ON INDEX idx_energy_point_time IS '联合索引：提升按监测点和时间范围查询的性能';

