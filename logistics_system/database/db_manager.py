import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "logistics.db")


# ====================== 获取数据库连接 ======================
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    return conn


# ====================== 【自动创建所有表】初始化数据库 ======================
def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    # 用户表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # 日志表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        action TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ✅【新增】配送路线表（管理员保存，驾驶员读取）
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS routes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id TEXT,
        q REAL,
        distance REAL,
        cost REAL,
        nodes TEXT,
        create_time TEXT,
        delivery_time TEXT,
        finish_time TEXT,
        duration REAL,
        efficiency REAL
    )
    """)
    
    # 检查并添加新列（兼容旧数据库）
    cursor.execute("PRAGMA table_info(routes)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    if 'create_time' not in existing_columns:
        cursor.execute("ALTER TABLE routes ADD COLUMN create_time TEXT")
    if 'delivery_time' not in existing_columns:
        cursor.execute("ALTER TABLE routes ADD COLUMN delivery_time TEXT")
    if 'finish_time' not in existing_columns:
        cursor.execute("ALTER TABLE routes ADD COLUMN finish_time TEXT")
    if 'duration' not in existing_columns:
        cursor.execute("ALTER TABLE routes ADD COLUMN duration REAL")
    if 'efficiency' not in existing_columns:
        cursor.execute("ALTER TABLE routes ADD COLUMN efficiency REAL")

    # ✅客户节点表（解决 no such table: customers）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS customers (
        id TEXT PRIMARY KEY NOT NULL,
        x REAL NOT NULL,
        y REAL NOT NULL,
        q REAL NOT NULL
    )''')

    # ✅订单表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_name TEXT NOT NULL,
        x REAL NOT NULL,
        y REAL NOT NULL,
        demand REAL NOT NULL,
        status TEXT DEFAULT 'pending',
        create_time TEXT,
        delivery_time TEXT,
        finish_time TEXT,
        duration REAL,
        efficiency REAL
    )''')
    
    # 检查并添加新列（兼容旧数据库）
    cursor.execute("PRAGMA table_info(orders)")
    existing_columns = [col[1] for col in cursor.fetchall()]
    
    if 'create_time' not in existing_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN create_time TEXT")
    if 'delivery_time' not in existing_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN delivery_time TEXT")
    if 'finish_time' not in existing_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN finish_time TEXT")
    if 'duration' not in existing_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN duration REAL")
    if 'efficiency' not in existing_columns:
        cursor.execute("ALTER TABLE orders ADD COLUMN efficiency REAL")

    # 插入示例订单数据（如果表为空）
    cursor.execute("SELECT COUNT(*) FROM orders")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO orders
        (customer_name, x, y, demand, status)
        VALUES
        ('张三', 10.5, 20.3, 500, 'pending'),
        ('李四', 15.2, 8.7, 300, 'pending'),
        ('王五', 25.0, 30.1, 800, 'completed')
        """)

    conn.commit()
    conn.close()


# ====================== 注册用户（支持选择角色：admin / driver）======================
def register_user(username, password, role):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
        INSERT INTO users (username, password, role)
        VALUES (?, ?, ?)
        """, (username, password, role))

        conn.commit()
        log_action(username, "用户注册")
        return True, "注册成功"

    except sqlite3.IntegrityError:
        return False, "用户名已存在"

    finally:
        conn.close()


# ====================== 登录验证 ======================
def verify_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT role FROM users
    WHERE username=? AND password=?
    """, (username, password))

    result = cursor.fetchone()
    conn.close()

    if result:
        role = result[0]
        log_action(username, "用户登录")
        return True, role
    else:
        return False, None


# ====================== 获取用户角色 ======================
def get_user_role(username):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT role FROM users
    WHERE username=?
    """, (username,))

    result = cursor.fetchone()
    conn.close()

    if result:
        return result[0]
    return None


# ====================== 写入日志 ======================
def log_action(username, action):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO logs (username, action)
    VALUES (?, ?)
    """, (username, action))

    conn.commit()
    conn.close()


# ====================== 获取日志 ======================
def get_logs(limit=100):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(f"""
    SELECT username, action, timestamp
    FROM logs
    ORDER BY id DESC
    LIMIT {limit}
    """)

    logs = cursor.fetchall()
    conn.close()
    return logs


# ====================== 获取所有用户 ======================
def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, username, role, created_at
    FROM users
    """)

    users = cursor.fetchall()
    conn.close()
    return users


# ====================== 删除用户 ======================
def delete_user(username):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    DELETE FROM users
    WHERE username=?
    """, (username,))

    conn.commit()
    conn.close()
    log_action(username, "用户被删除")


# ====================== 判断是否为管理员 ======================
def is_admin(username):
    role = get_user_role(username)
    return role == "admin"


# ==============================================
# ✅【新增】管理员：保存配送路线到数据库
# ==============================================
def save_routes(routes_list):
    conn = get_connection()
    cursor = conn.cursor()

    # 先清空旧路线
    cursor.execute("DELETE FROM routes")

    # 插入新路线
    for (
        vehicle_id,
        q,
        distance,
        cost,
        nodes,
        create_time,
        delivery_time,
        finish_time,
        duration,
        efficiency
    ) in routes_list:
        cursor.execute("""
            INSERT INTO routes(
                vehicle_id,
                q,
                distance,
                cost,
                nodes,
                create_time,
                delivery_time,
                finish_time,
                duration,
                efficiency
            )
            VALUES(?,?,?,?,?,?,?,?,?,?)
        """, (
            vehicle_id,
            q,
            distance,
            cost,
            nodes,
            create_time,
            delivery_time,
            finish_time,
            duration,
            efficiency
        ))

    conn.commit()
    conn.close()

# ====================== 保存节点坐标 =========================
def save_customers_nodes(nodes_dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM customers")
    for nid, node in nodes_dict.items():
        if nid != "DC":
            cursor.execute('''
                INSERT INTO customers (id, x, y, q) VALUES (?, ?, ?, ?)
            ''', (nid, node.x, node.y, node.q))
    conn.commit()
    conn.close()

# ====================== 读取所有节点 ======================
def get_all_customers_nodes():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, x, y, q FROM customers")
    rows = cursor.fetchall()
    conn.close()
    return rows
# ==============================================

# ✅【新增】驾驶员：读取所有车辆路线
# ==============================================
def get_all_routes():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT vehicle_id, q, distance, cost, nodes FROM routes")
    routes = cursor.fetchall()
    conn.close()
    return routes

def save_customers_nodes(nodes_dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM customers")
    for nid, node in nodes_dict.items():
        if nid != "DC":
            cursor.execute('''
                INSERT INTO customers (id, x, y, q) VALUES (?, ?, ?, ?)
            ''', (nid, node.x, node.y, node.q))
    conn.commit()
    conn.close()

def save_customers_nodes(nodes_dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM customers")
    for nid, node in nodes_dict.items():
        if nid != "DC":
            cursor.execute('''
                INSERT INTO customers (id, x, y, q)
                VALUES (?, ?, ?, ?)
            ''', (nid, node.x, node.y, node.q))
    conn.commit()
    conn.close()
    
# 程序启动时自动初始化表
init_database()