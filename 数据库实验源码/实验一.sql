-- 创建 department 表（院系）
CREATE TABLE department (
    dno CHAR(6) PRIMARY KEY,
    dept_name CHAR(20) NOT NULL,
    header CHAR(8)
);

-- 创建 speciality 表（专业）
CREATE TABLE speciality (
    spno CHAR(8) PRIMARY KEY,
    dno CHAR(6) NOT NULL,
    spname CHAR(20) NOT NULL
);

-- 创建 class 表（班级）
CREATE TABLE class (
    spno CHAR(8),
    class_no CHAR(4),
    header CHAR(8),
    PRIMARY KEY (spno, class_no)
);

-- 创建 teacher 表（教师）
CREATE TABLE teacher (
    t_no CHAR(8) PRIMARY KEY,
    t_name CHAR(8) NOT NULL,
    t_sex CHAR(2),
    t_birthday SMALLDATETIME,
    dno CHAR(6),
    tech_title CHAR(10)
);

-- 创建 course 表（课程）
CREATE TABLE course (
    cno CHAR(10) PRIMARY KEY,
    cname CHAR(20) NOT NULL,
    spno CHAR(8),
    ctno TINYINT,
    lecture TINYINT,
    experiment TINYINT,
    semester TINYINT,
    credit TINYINT
);

-- 创建 teacher_course 表（教师授课安排）
CREATE TABLE teacher_course (
    tcid SMALLINT PRIMARY KEY,
    t_no CHAR(8),
    spno CHAR(8),
    class_no CHAR(4),
    cno CHAR(10) NOT NULL,
    semester CHAR(6),
    schoolyear CHAR(10)
);

-- 创建 student 表（学生）
CREATE TABLE student (
    s_no CHAR(8) PRIMARY KEY,
    sname CHAR(8) NOT NULL,
    sex CHAR(2),
    sbirthday SMALLDATETIME,
    dno CHAR(6),
    spno CHAR(8),
    class_no CHAR(4)
);

-- 创建 student_course 表（学生成绩/选课记录）
CREATE TABLE student_course (
    s_no CHAR(8),
    tcid SMALLINT,
    score TINYINT,
    PRIMARY KEY (s_no, tcid)
);