import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "logistics.db")


# ====================== 获取数据库连接 ======================
def get_connection():

    conn = sqlite3.connect(DB_PATH)

    return conn


# ====================== 注册用户 ======================
def register_user(username, password, role="dispatcher"):

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


# ====================== 判断管理员 ======================
def is_admin(username):

    role = get_user_role(username)

    return role == "admin"