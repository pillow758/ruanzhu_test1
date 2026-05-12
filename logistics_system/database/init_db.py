import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "logistics.db")


def init_database():

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    # ====================== 用户表 ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'dispatcher',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        x REAL,
        y REAL,
        demand REAL,
        status TEXT DEFAULT 'pending'
    )
    """)
    # ====================== 路线表 ======================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id TEXT,
        nodes TEXT,         -- 用逗号分隔存储节点ID
        distance REAL,
        cost REAL,
        q REAL,             -- 载重
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # ====================== 默认管理员 ======================
    cursor.execute("""
    SELECT * FROM users WHERE username=?
    """, ("admin",))

    admin = cursor.fetchone()

    if not admin:

        cursor.execute("""
        INSERT INTO users (username, password, role)
        VALUES (?, ?, ?)
        """, ("admin", "123456", "admin"))

        print("默认管理员已创建")
        print("账号：admin")
        print("密码：123456")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_database()
    print("数据库初始化完成")