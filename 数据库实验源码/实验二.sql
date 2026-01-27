-- 切换到目标数据库（如 finance），若未创建请先 CREATE DATABASE finance;
-- \c finance;

-- 1. 删除已有表（如果存在）
DROP TABLE IF EXISTS property;
DROP TABLE IF EXISTS fund;
DROP TABLE IF EXISTS insurance;
DROP TABLE IF EXISTS finances_product;
DROP TABLE IF EXISTS bank_card;
DROP TABLE IF EXISTS client;

-- 2. 创建 client 表
CREATE TABLE client (
    c_id INTEGER PRIMARY KEY,
    c_name VARCHAR(100) NOT NULL,
    c_mail CHAR(30) UNIQUE,
    c_id_card CHAR(20) UNIQUE NOT NULL,
    c_phone CHAR(20) UNIQUE NOT NULL,
    c_password CHAR(20) NOT NULL
);

-- 3. 创建 bank_card 表
CREATE TABLE bank_card (
    b_number CHAR(30) PRIMARY KEY,
    b_type CHAR(20),
    b_c_id INTEGER NOT NULL
);

-- 4. 创建 finances_product 表
CREATE TABLE finances_product (
    p_name VARCHAR(100) NOT NULL,
    p_id INTEGER PRIMARY KEY,
    p_description VARCHAR(4000),
    p_amount INTEGER,
    p_year INTEGER
);

-- 5. 创建 insurance 表
CREATE TABLE insurance (
    i_name VARCHAR(100) NOT NULL,
    i_id INTEGER PRIMARY KEY,
    i_amount INTEGER,
    i_person CHAR(20),
    i_year INTEGER,
    i_project VARCHAR(200)
);

-- 6. 创建 fund 表
CREATE TABLE fund (
    f_name VARCHAR(100) NOT NULL,
    f_id INTEGER PRIMARY KEY,
    f_type CHAR(20),
    f_amount INTEGER,
    risk_level CHAR(20) NOT NULL,
    f_manager INTEGER NOT NULL
);

-- 7. 创建 property 表
CREATE TABLE property (
    pro_id INTEGER PRIMARY KEY,
    pro_c_id INTEGER NOT NULL,
    pro_pif_id INTEGER NOT NULL,
    pro_type INTEGER NOT NULL,
    pro_status CHAR(20),
    pro_quantity INTEGER,
    pro_income INTEGER,
    pro_purchase_time DATE
);

-- 8. 插入 client 数据
INSERT INTO client VALUES
(1, '张一', 'zhang1@example.com', '110101199001011234', '13800138001', 'pass123'),
(2, '李二', 'li2@example.com', '110101199102022345', '13800138002', 'pass456');

-- 查询 client
SELECT * FROM client;

-- 9. 插入 bank_card 数据
INSERT INTO bank_card VALUES
('6222081234567890001', '借记卡', 1),
('6222081234567890002', '信用卡', 1),
('6222081234567890003', '借记卡', 2);

-- 查询 bank_card
SELECT * FROM bank_card;

-- 10. 插入 finances_product 数据
INSERT INTO finances_product VALUES
('稳盈宝', 101, '低风险固定收益', 10000, 1),
('高收益理财', 102, '中高风险浮动收益', 50000, 3);

-- 查询 finances_product
SELECT * FROM finances_product;

-- 11. 插入 insurance 数据
INSERT INTO insurance VALUES
('重疾险A款', 201, 500000, '成年人', 20, '重大疾病、身故保障'),
('意外险B款', 202, 100000, '全年龄段', 1, '意外身故、医疗报销');

-- 查询 insurance
SELECT * FROM insurance;

-- 12. 插入 fund 数据
INSERT INTO fund VALUES
('沪深300指数基金', 301, '指数型', 10000, '中风险', 1001),
('科技成长混合基金', 302, '混合型', 20000, '高风险', 1002);

-- 查询 fund
SELECT * FROM fund;

-- 13. 插入 property 数据
INSERT INTO property VALUES
(1, 1, 101, 1, '持有', 1, 500, '2025-01-10'),
(2, 1, 201, 2, '生效', 1, 0, '2025-01-15'),    
(3, 2, 301, 3, '持有', 2, 300, '2025-01-20');

-- 查询 property
SELECT * FROM property;

-- 14. 单表查询
SELECT * FROM bank_card;

-- 15. 条件查询
SELECT * FROM property WHERE pro_status = '持有';

-- 16. 聚合查询
SELECT COUNT(*) AS user_count FROM client;

SELECT b_type, COUNT(*) AS card_count 
FROM bank_card 
GROUP BY b_type;

SELECT AVG(i_amount) AS avg_insurance_amount FROM insurance;

-- 最大值和最小值保险
SELECT i_name, i_amount 
FROM insurance 
WHERE i_amount = (SELECT MAX(i_amount) FROM insurance)

UNION ALL

SELECT i_name, i_amount 
FROM insurance 
WHERE i_amount = (SELECT MIN(i_amount) FROM insurance);

-- 17. 半连接（IN 子查询）
SELECT c_id, c_name, c_id_card 
FROM client 
WHERE c_id IN (SELECT b_c_id FROM bank_card);

-- 18. 反连接（NOT IN）
SELECT c_id, c_name, c_id_card 
FROM client 
WHERE c_id NOT IN (
    SELECT b_c_id 
    FROM bank_card 
    WHERE b_number LIKE '622202130202000001%'
);

-- 19. 子查询（保额高于平均）
SELECT i_name, i_person 
FROM insurance 
WHERE i_amount > (SELECT AVG(i_amount) FROM insurance);

-- 20. ORDER BY
SELECT i_name, i_amount, i_person 
FROM insurance 
WHERE i_id > 2 
ORDER BY i_amount DESC;

-- 21. GROUP BY
SELECT p_year, COUNT(*) AS product_count 
FROM finances_product 
GROUP BY p_year;

-- 22. HAVING
SELECT i_person, COUNT(*) AS insurance_count 
FROM insurance 
GROUP BY i_person 
HAVING COUNT(*) = 2;

-- 23. WITH AS
WITH fund_summary AS (
    SELECT f_name, f_type, risk_level, f_amount
    FROM fund
)
SELECT * FROM fund_summary;

-- 24. 创建视图
CREATE VIEW v_client AS
SELECT c.c_id, c.c_name, c.c_id_card
FROM client c
WHERE c.c_id IN (SELECT b_c_id FROM bank_card);

-- 查询视图
SELECT * FROM v_client;

-- 25. 修改视图（使用 CREATE OR REPLACE）
CREATE OR REPLACE VIEW v_client AS
SELECT c.c_id, c.c_name, c.c_id_card
FROM client c
JOIN bank_card b ON c.c_id = b.b_c_id
WHERE b.b_type = '信用卡';

-- 查询修改后的视图
SELECT * FROM v_client;

-- 26. 重命名视图
ALTER VIEW v_client RENAME TO v_credit_card_client;

-- 27. 删除视图
DROP VIEW IF EXISTS v_credit_card_client;

-- 28. 创建索引
CREATE INDEX idx_property_client ON property(pro_c_id);

-- 29. 重建并重命名索引
DROP INDEX IF EXISTS idx_property_client;
CREATE INDEX idx_property_temp ON property(pro_c_id);
ALTER INDEX idx_property_temp RENAME TO idx_property_new;

-- 30. 删除索引（示例，实际已重命名）
DROP INDEX IF EXISTS idx_property_temp;

-- 31. 数据更新
-- 查看更新前
SELECT * FROM bank_card WHERE b_c_id < 10;

-- 执行更新
UPDATE bank_card
SET b_type = '储蓄卡'
WHERE b_c_id < 10
  AND b_c_id IN (SELECT c_id FROM client);

-- 32. 数据删除
-- 删除前查询
SELECT * FROM fund WHERE f_id < 3;

-- 执行删除
DELETE FROM fund WHERE f_id < 3;

-- 删除后查询
SELECT * FROM fund;

-- 33. 创建用户（需 superuser 权限，如 omm）
-- 注意：以下语句需在具有管理员权限的用户下执行
CREATE USER dbuser IDENTIFIED BY 'Gauss#3demo';

-- 34. 授予权限（假设表在 finance schema 下）
-- 若当前 schema 是 public，请将 finance 替换为 public
GRANT USAGE ON SCHEMA finance TO dbuser;
GRANT SELECT, INSERT ON TABLE finance.bank_card TO dbuser;
GRANT ALL PRIVILEGES ON SCHEMA finance TO dbuser;

-- 注意：openGauss 中 GRANT ALL ON SCHEMA 不自动包含表权限，
-- 需单独授权表，或使用默认权限：
-- ALTER DEFAULT PRIVILEGES IN SCHEMA finance GRANT SELECT, INSERT ON TABLES TO dbuser;

-- 结束