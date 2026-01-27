-- 3. 创建数据库
CREATE DATABASE edu_manage ENCODING 'UTF8' TEMPLATE = template0;

-- 连接到新数据库
\connect edu_manage

-- 创建 schema 并设置 search_path
CREATE SCHEMA edu;
SET search_path TO edu;

-- 4. 创建基本表

-- (1) 教师表
CREATE TABLE teacher (
    t_id CHAR(8) PRIMARY KEY,
    t_name VARCHAR(50) NOT NULL,
    t_dept VARCHAR(50),
    t_title VARCHAR(20)
);

-- (2) 课程表
CREATE TABLE course (
    c_id CHAR(8) PRIMARY KEY,
    c_name VARCHAR(100) NOT NULL,
    c_credit INTEGER,
    c_hours INTEGER,
    t_id CHAR(8)
    -- 外键逻辑引用 teacher(t_id)，此处未显式声明以简化（可根据需要添加）
);

-- (3) 选课表
CREATE TABLE enrollment (
    e_id SERIAL PRIMARY KEY,
    s_id CHAR(10) NOT NULL,
    c_id CHAR(8) NOT NULL,
    grade NUMERIC(5,2),
    semester VARCHAR(20)
    -- 外键逻辑引用 student(s_id) 和 course(c_id)
);

-- (4) 学生表
CREATE TABLE student (
    s_id CHAR(10) PRIMARY KEY,
    s_name VARCHAR(50) NOT NULL,
    s_gender CHAR(2),
    s_major VARCHAR(100),
    s_enroll_year INTEGER
);

-- 添加检查约束：入学年份在 2000–2026 之间
ALTER TABLE student 
ADD CONSTRAINT chk_enroll_year 
CHECK (s_enroll_year BETWEEN 2000 AND 2026);

-- 6. 插入基本表数据

-- (1) 教师表
INSERT INTO teacher VALUES 
('T001', '张教授', '计算机学院', '教授'),
('T002', '李讲师', '数学学院', '讲师');

-- (2) 学生表
INSERT INTO student VALUES 
('S2023001', '王小明', '男', '计算机科学', 2023),
('S2023002', '赵小红', '女', '软件工程', 2023);

-- (3) 课程表
INSERT INTO course VALUES 
('C001', '数据库原理', 3, 48, 'T001'),
('C002', '高等数学', 4, 64, 'T002');

-- (4) 选课表
INSERT INTO enrollment (s_id, c_id, grade, semester) VALUES 
('S2023001', 'C001', 88.5, '2023-秋'),
('S2023002', 'C001', 92.0, '2023-秋');

-- 7. 修改基本表数据

-- (1) 修正王小明的成绩
UPDATE enrollment 
SET grade = 90.0 
WHERE s_id = 'S2023001' AND c_id = 'C001';

-- (2) 更新李讲师的职称
UPDATE teacher 
SET t_title = '副教授' 
WHERE t_id = 'T002';

-- 8. 删除基本表数据

-- (1) 删除未录入成绩的选课记录（当前无 NULL，仅为示例）
DELETE FROM enrollment WHERE grade IS NULL;

-- (2) 删除已停开的课程（先删选课，再删课程）
DELETE FROM enrollment WHERE c_id = 'C002';
DELETE FROM course WHERE c_id = 'C002';

-- 9. 查询基本表数据（单表查询）

-- (1) 查询全部信息
SELECT * FROM student;

-- (2) 查询部分属性
SELECT s_id, s_name, s_major FROM student;

-- (3) 查询部分元组（2023级学生）
SELECT * FROM student WHERE s_enroll_year = 2023;

-- (4) 含虚拟列（显示“年级”）
SELECT s_name, 2026 - s_enroll_year AS 年级 FROM student;

-- (5) 含 IN 谓词
SELECT * FROM student WHERE s_major IN ('计算机科学', '人工智能');

-- (6) 含通配符（姓名含“小”）
SELECT * FROM student WHERE s_name LIKE '%小%';

-- (7) 含 ORDER BY
SELECT * FROM student ORDER BY s_enroll_year DESC;

-- (8) 含聚集函数
SELECT COUNT(*) AS 学生总数 FROM student;

-- (9) 含 GROUP BY（按专业统计人数）
SELECT s_major, COUNT(*) FROM student GROUP BY s_major;

-- 10. 多表查询

-- (1) 两表连接：学生+选课
SELECT s.s_name, e.grade 
FROM student s JOIN enrollment e ON s.s_id = e.s_id;

-- (2) 三表连接：学生+课程+教师
SELECT s.s_name, c.c_name, t.t_name 
FROM student s 
JOIN enrollment e ON s.s_id = e.s_id
JOIN course c ON e.c_id = c.c_id
JOIN teacher t ON c.t_id = t.t_id;

-- (3) 自身连接（同院系不同教师）
SELECT t1.t_name, t2.t_name 
FROM teacher t1, teacher t2 
WHERE t1.t_dept = t2.t_dept AND t1.t_id != t2.t_id;

-- (4) 外连接：所有学生及其选课（包括未选课的）
SELECT s.s_name, e.c_id 
FROM student s LEFT JOIN enrollment e ON s.s_id = e.s_id;

-- (5) 不相关子查询：选了“数据库原理”的学生
SELECT s_name FROM student 
WHERE s_id IN (SELECT s_id FROM enrollment WHERE c_id = 'C001');

-- (6) 相关子查询：每门课高于平均分的成绩
SELECT e1.s_id, e1.c_id, e1.grade 
FROM enrollment e1 
WHERE e1.grade > (
    SELECT AVG(e2.grade) 
    FROM enrollment e2 
    WHERE e2.c_id = e1.c_id
);

-- (7) EXISTS 查询：有选课记录的学生
SELECT s_name FROM student s 
WHERE EXISTS (SELECT 1 FROM enrollment e WHERE e.s_id = s.s_id);

-- (8) 派生表：各课程平均分
SELECT c_name, avg_grade 
FROM course c 
JOIN (SELECT c_id, AVG(grade) AS avg_grade FROM enrollment GROUP BY c_id) t 
ON c.c_id = t.c_id;

-- 11. 视图与触发器

-- (1) 行列子集视图：学生基本信息
CREATE VIEW v_student_basic AS
SELECT s_id, s_name, s_major FROM student;

-- (2) 基于视图的视图：计算机专业学生
CREATE VIEW v_cs_student AS
SELECT * FROM v_student_basic WHERE s_major = '计算机科学';

-- (3) 基于视图的查询
SELECT * FROM v_cs_student;

-- (4) 触发器：禁止成绩超过100分或低于0分
CREATE OR REPLACE FUNCTION check_grade() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.grade > 100 OR NEW.grade < 0 THEN
        RAISE EXCEPTION '成绩必须在0-100之间！';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_check_grade
BEFORE INSERT OR UPDATE ON enrollment
FOR EACH ROW EXECUTE PROCEDURE check_grade();

-- 12. 创建新用户并授权

-- (1) 创建教务员用户
CREATE USER jiaowu IDENTIFIED BY 'Jw@2026';

-- (2) 授予权限（在 edu schema 下）
GRANT USAGE ON SCHEMA edu TO jiaowu;
GRANT SELECT, INSERT, UPDATE ON TABLE edu.student, edu.enrollment TO jiaowu;
GRANT SELECT ON TABLE edu.course, edu.teacher TO jiaowu;

-- 可选：授予序列权限（因 enrollment.e_id 是 SERIAL）
GRANT USAGE, SELECT ON SEQUENCE enrollment_e_id_seq TO jiaowu;

-- 结束