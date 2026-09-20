import sqlite3
import os
import hashlib

DB_PATH = os.path.join(os.path.dirname(__file__), "logistics.db")


def hash_password(password):
    """使用 SHA256 对密码进行哈希处理"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ====================== 用户表（管理员/调度员） ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'dispatcher',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ====================== 驾驶员表 ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS drivers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        driver_id TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL,
        phone TEXT,
        license_plate TEXT,
        vehicle_type TEXT DEFAULT '中型货车',
        status TEXT DEFAULT 'offline',
        current_shift TEXT DEFAULT '早班',
        current_lng REAL,
        current_lat REAL,
        total_distance REAL DEFAULT 0,
        total_deliveries INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ====================== 驾驶员任务表 ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS driver_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        driver_id TEXT,
        order_id TEXT,
        customer_name TEXT,
        address TEXT,
        lng REAL,
        lat REAL,
        demand REAL,
        status TEXT DEFAULT 'pending',
        assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        signature TEXT,
        note TEXT
    )
    """)

    # ====================== 日志表 ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        action TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ====================== 订单表 ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT,
        address TEXT,
        lng REAL,
        lat REAL,
        demand REAL,
        status TEXT DEFAULT 'pending',
        assigned_driver TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ====================== 路线表 ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id TEXT,
        nodes TEXT,
        distance REAL,
        cost REAL,
        q REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ====================== 成本参数表 ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cost_params (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        param_key TEXT UNIQUE NOT NULL,
        param_value REAL NOT NULL,
        param_desc TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ====================== 默认成本参数 ======================
    default_costs = [
        ('fixed_cost',       400.0, '固定成本（元/车次，含折旧、保险）'),
        ('fuel_price',         7.8, '燃油单价（元/L）'),
        ('fuel_consumption',  12.0, '百公里油耗（L/100km）'),
        ('toll_per_km',        0.5, '过路费（元/km）'),
        ('maintenance_per_km', 0.3, '车辆维护费（元/km）'),
        ('driver_wage',       30.0, '驾驶员工资（元/小时）'),
    ]
    for key, val, desc in default_costs:
        cursor.execute("""
        INSERT OR IGNORE INTO cost_params (param_key, param_value, param_desc)
        VALUES (?, ?, ?)
        """, (key, val, desc))

    # ====================== 订单状态日志表 ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_status_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT,
        task_id INTEGER,
        from_status TEXT,
        to_status TEXT,
        operator TEXT,
        note TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # ====================== 异常上报表 ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS exceptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        driver_id TEXT,
        task_id INTEGER,
        exception_type TEXT,
        description TEXT,
        status TEXT DEFAULT 'pending',
        reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP
    )
    """)

    # ====================== 默认管理员（密码哈希存储） ======================
    cursor.execute("SELECT * FROM users WHERE username=?", ("admin",))
    admin = cursor.fetchone()

    if not admin:
        hashed_pw = hash_password("123456")
        cursor.execute("""
        INSERT INTO users (username, password, role)
        VALUES (?, ?, ?)
        """, ("admin", hashed_pw, "admin"))
        print("默认管理员已创建: admin / 123456")

    # ====================== 默认驾驶员（测试账号） ======================
    cursor.execute("SELECT * FROM drivers WHERE driver_id=?", ("D001",))
    driver = cursor.fetchone()

    if not driver:
        hashed_pw = hash_password("123456")
        cursor.execute("""
        INSERT INTO drivers (driver_id, password, name, phone, license_plate, vehicle_type, status, current_shift)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("D001", hashed_pw, "张师傅", "13800138000", "京A12345", "中型货车", "offline", "早班"))
        print("默认驾驶员已创建: D001 / 123456")

        cursor.execute("""
        INSERT INTO drivers (driver_id, password, name, phone, license_plate, vehicle_type, status, current_shift)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("D002", hashed_pw, "李师傅", "13900139000", "京B67890", "小型货车", "offline", "中班"))
        print("默认驾驶员已创建: D002 / 123456")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_database()
    print("数据库初始化完成")
