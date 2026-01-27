from app import app

if __name__ == '__main__':
    print("启动工业能耗监测数据管理系统...")
    print("访问 http://localhost:5000 查看系统")
    app.run(debug=True, host='0.0.0.0', port=5000)