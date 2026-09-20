import sqlite3
import os
import hashlib

DB_PATH = os.path.join(os.path.dirname(__file__), "logistics.db")

# ====================== 全局字体配置 ======================
# 中文：宋体 (SimSun) / 英文：Times New Roman
FONT_FAMILY = "'Times New Roman', 'SimSun', serif"


# ====================== 密码哈希工具 ======================
def hash_password(password):
    """使用 SHA256 对密码进行哈希处理"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def verify_password(password, hashed):
    """验证密码是否与哈希值匹配"""
    return hash_password(password) == hashed


# ====================== 获取数据库连接 ======================
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    return conn


# ====================== 注册用户 ======================
def register_user(username, password, role="dispatcher"):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        hashed_pw = hash_password(password)
        cursor.execute("""
        INSERT INTO users (username, password, role)
        VALUES (?, ?, ?)
        """, (username, hashed_pw, role))
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
    hashed_pw = hash_password(password)
    cursor.execute("""
    SELECT role FROM users
    WHERE username=? AND password=?
    """, (username, hashed_pw))
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


# ====================== 获取日志（参数化查询，防止SQL注入） ======================
def get_logs(limit=100):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT username, action, timestamp
    FROM logs
    ORDER BY id DESC
    LIMIT ?
    """, (limit,))
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


# ====================== 驾驶员相关函数 ======================

def verify_driver(driver_id, password):
    """验证驾驶员登录（支持工号或手机号）"""
    conn = get_connection()
    cursor = conn.cursor()
    hashed_pw = hash_password(password)
    # 先尝试工号匹配
    cursor.execute("""
    SELECT driver_id, name, license_plate, vehicle_type, status, current_shift
    FROM drivers
    WHERE driver_id=? AND password=?
    """, (driver_id, hashed_pw))
    result = cursor.fetchone()
    # 如果工号不匹配且看起来像手机号，尝试手机号匹配
    if not result and len(driver_id) == 11 and driver_id.isdigit():
        cursor.execute("""
        SELECT driver_id, name, license_plate, vehicle_type, status, current_shift
        FROM drivers
        WHERE phone=? AND password=?
        """, (driver_id, hashed_pw))
        result = cursor.fetchone()
    conn.close()
    if result:
        log_action(result[0], "驾驶员登录")
        return True, {
            'driver_id': result[0],
            'name': result[1],
            'license_plate': result[2],
            'vehicle_type': result[3],
            'status': result[4],
            'shift': result[5]
        }
    return False, None


def verify_driver_by_phone(phone, password):
    """使用手机号验证驾驶员登录"""
    conn = get_connection()
    cursor = conn.cursor()
    hashed_pw = hash_password(password)
    cursor.execute("""
    SELECT driver_id, name, license_plate, vehicle_type, status, current_shift
    FROM drivers
    WHERE phone=? AND password=?
    """, (phone, hashed_pw))
    result = cursor.fetchone()
    conn.close()
    if result:
        log_action(result[0], "驾驶员登录（手机号）")
        return True, {
            'driver_id': result[0],
            'name': result[1],
            'license_plate': result[2],
            'vehicle_type': result[3],
            'status': result[4],
            'shift': result[5]
        }
    return False, None


def register_driver(driver_id, password, name, phone="", license_plate="", vehicle_type="中型货车"):
    """注册新驾驶员"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        hashed_pw = hash_password(password)
        cursor.execute("""
        INSERT INTO drivers (driver_id, password, name, phone, license_plate, vehicle_type)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (driver_id, hashed_pw, name, phone, license_plate, vehicle_type))
        conn.commit()
        log_action(driver_id, "驾驶员注册")
        return True, "注册成功"
    except sqlite3.IntegrityError:
        return False, "工号已存在"
    finally:
        conn.close()


def update_driver_status(driver_id, status):
    """更新驾驶员状态（online/offline/delivering）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE drivers SET status=? WHERE driver_id=?
    """, (status, driver_id))
    conn.commit()
    conn.close()


def update_driver_location(driver_id, lng, lat):
    """更新驾驶员位置"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE drivers SET current_lng=?, current_lat=? WHERE driver_id=?
    """, (lng, lat, driver_id))
    conn.commit()
    conn.close()


def get_driver_info(driver_id):
    """获取驾驶员信息"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT driver_id, name, phone, license_plate, vehicle_type, status, current_shift,
           current_lng, current_lat, total_distance, total_deliveries
    FROM drivers WHERE driver_id=?
    """, (driver_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {
            'driver_id': result[0],
            'name': result[1],
            'phone': result[2],
            'license_plate': result[3],
            'vehicle_type': result[4],
            'status': result[5],
            'shift': result[6],
            'lng': result[7],
            'lat': result[8],
            'total_distance': result[9],
            'total_deliveries': result[10]
        }
    return None


def get_driver_tasks(driver_id, status=None):
    """获取驾驶员的任务列表"""
    conn = get_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("""
        SELECT id, order_id, customer_name, address, lng, lat, demand, status, assigned_at
        FROM driver_tasks
        WHERE driver_id=? AND status=?
        ORDER BY assigned_at
        """, (driver_id, status))
    else:
        cursor.execute("""
        SELECT id, order_id, customer_name, address, lng, lat, demand, status, assigned_at
        FROM driver_tasks
        WHERE driver_id=?
        ORDER BY
            CASE status
                WHEN 'pending' THEN 1
                WHEN 'in_progress' THEN 2
                WHEN 'completed' THEN 3
                ELSE 4
            END,
            assigned_at
        """, (driver_id,))
    tasks = cursor.fetchall()
    conn.close()
    return [{
        'id': t[0],
        'order_id': t[1],
        'customer_name': t[2],
        'address': t[3],
        'lng': t[4],
        'lat': t[5],
        'demand': t[6],
        'status': t[7],
        'assigned_at': t[8]
    } for t in tasks]


def assign_task_to_driver(driver_id, order_id, customer_name, address, lng, lat, demand):
    """分配任务给驾驶员"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO driver_tasks (driver_id, order_id, customer_name, address, lng, lat, demand)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (driver_id, order_id, customer_name, address, lng, lat, demand))
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    return task_id


def update_task_status(task_id, status, note=""):
    """更新任务状态"""
    conn = get_connection()
    cursor = conn.cursor()
    if status == 'completed':
        cursor.execute("""
        UPDATE driver_tasks SET status=?, completed_at=CURRENT_TIMESTAMP, note=?
        WHERE id=?
        """, (status, note, task_id))
    else:
        cursor.execute("""
        UPDATE driver_tasks SET status=?, note=? WHERE id=?
        """, (status, note, task_id))
    conn.commit()
    conn.close()


def report_exception(driver_id, task_id, exception_type, description):
    """上报异常"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO exceptions (driver_id, task_id, exception_type, description)
    VALUES (?, ?, ?, ?)
    """, (driver_id, task_id, exception_type, description))
    conn.commit()
    conn.close()
    log_action(driver_id, f"上报异常: {exception_type}")


def get_all_drivers():
    """获取所有驾驶员列表"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT driver_id, name, phone, license_plate, vehicle_type, status, current_shift
    FROM drivers
    ORDER BY driver_id
    """)
    drivers = cursor.fetchall()
    conn.close()
    return [{
        'driver_id': d[0],
        'name': d[1],
        'phone': d[2],
        'license_plate': d[3],
        'vehicle_type': d[4],
        'status': d[5],
        'shift': d[6]
    } for d in drivers]


# ====================== 生成随机订单并分配任务 ======================

def generate_random_orders(count=6):
    """生成随机订单数据"""
    import random

    # 北京市真实地址和坐标
    locations = [
        ("朝阳区建国路88号", 116.467, 39.908),
        ("海淀区中关村大街1号", 116.317, 39.978),
        ("丰台区南三环西路10号", 116.357, 39.858),
        ("东城区王府井大街218号", 116.417, 39.918),
        ("西城区西单北大街10号", 116.377, 39.918),
        ("朝阳区望京街10号", 116.487, 39.998),
        ("大兴区兴华大街段", 116.347, 39.728),
        ("通州区新华大街", 116.657, 39.908),
        ("昌平区回龙观东大街", 116.337, 40.078),
        ("石景山区阜石路", 116.227, 39.918),
        ("顺义区天竺镇", 116.567, 40.058),
        ("房山区良乡", 116.147, 39.748),
    ]

    customers = [
        "张三", "李四", "王五", "赵六", "钱七", "孙八",
        "周九", "吴十", "郑先生", "冯女士", "陈先生", "林小姐"
    ]

    orders = []
    for i in range(count):
        loc = random.choice(locations)
        order = {
            'order_id': f"ORD{random.randint(10000, 99999)}",
            'customer_name': random.choice(customers),
            'address': loc[0],
            'lng': loc[1],
            'lat': loc[2],
            'demand': round(random.uniform(50, 500), 1)
        }
        orders.append(order)

    return orders


def create_order_and_assign(driver_id, order_id, customer_name, address, lng, lat, demand):
    """创建订单并分配给驾驶员"""
    conn = get_connection()
    cursor = conn.cursor()

    # 创建订单
    cursor.execute("""
    INSERT INTO orders (customer_name, address, lng, lat, demand, status, assigned_driver)
    VALUES (?, ?, ?, ?, ?, 'assigned', ?)
    """, (customer_name, address, lng, lat, demand, driver_id))
    order_db_id = cursor.lastrowid

    # 创建驾驶员任务
    cursor.execute("""
    INSERT INTO driver_tasks (driver_id, order_id, customer_name, address, lng, lat, demand, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
    """, (driver_id, order_id, customer_name, address, lng, lat, demand))
    task_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return task_id


def batch_assign_tasks(driver_id, orders):
    """批量分配任务给驾驶员"""
    task_ids = []
    for order in orders:
        task_id = create_order_and_assign(
            driver_id,
            order['order_id'],
            order['customer_name'],
            order['address'],
            order['lng'],
            order['lat'],
            order['demand']
        )
        task_ids.append(task_id)
    return task_ids


def get_unassigned_orders():
    """获取未分配的订单"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, customer_name, address, lng, lat, demand
    FROM orders
    WHERE assigned_driver IS NULL OR assigned_driver = ''
    """)
    orders = cursor.fetchall()
    conn.close()
    return [{
        'id': o[0],
        'customer_name': o[1],
        'address': o[2],
        'lng': o[3],
        'lat': o[4],
        'demand': o[5]
    } for o in orders]


# ====================== 订单状态日志 ======================

def log_order_status_change(order_id, task_id, from_status, to_status, operator, note=""):
    """记录订单状态变更"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO order_status_log (order_id, task_id, from_status, to_status, operator, note)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (order_id, task_id, from_status, to_status, operator, note))
    conn.commit()
    conn.close()


def get_order_status_log(order_id):
    """获取订单的完整状态变更历史"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT from_status, to_status, operator, note, created_at
    FROM order_status_log
    WHERE order_id=?
    ORDER BY created_at ASC
    """, (order_id,))
    logs = cursor.fetchall()
    conn.close()
    return [{
        'from_status': l[0],
        'to_status': l[1],
        'operator': l[2],
        'note': l[3],
        'time': l[4]
    } for l in logs]


def get_all_orders(status_filter=None):
    """获取所有订单，可按状态过滤"""
    conn = get_connection()
    cursor = conn.cursor()
    if status_filter:
        cursor.execute("""
        SELECT id, customer_name, address, lng, lat, demand, status, assigned_driver, created_at
        FROM orders WHERE status=?
        ORDER BY created_at DESC
        """, (status_filter,))
    else:
        cursor.execute("""
        SELECT id, customer_name, address, lng, lat, demand, status, assigned_driver, created_at
        FROM orders
        ORDER BY created_at DESC
        """)
    orders = cursor.fetchall()
    conn.close()
    return [{
        'id': o[0],
        'customer_name': o[1],
        'address': o[2],
        'lng': o[3],
        'lat': o[4],
        'demand': o[5],
        'status': o[6],
        'assigned_driver': o[7],
        'created_at': o[8]
    } for o in orders]


def get_order_status_summary():
    """获取各状态订单数量"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT status, COUNT(*) FROM orders GROUP BY status
    """)
    result = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in result}


def get_all_drivers_with_info():
    """获取所有驾驶员及其任务统计信息"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT d.driver_id, d.name, d.license_plate, d.vehicle_type, d.status,
           d.current_lng, d.current_lat, d.total_distance, d.total_deliveries,
           d.current_shift, d.phone,
           (SELECT COUNT(*) FROM driver_tasks dt WHERE dt.driver_id=d.driver_id AND dt.status='pending') as pending_count,
           (SELECT COUNT(*) FROM driver_tasks dt WHERE dt.driver_id=d.driver_id AND dt.status='completed') as completed_count
    FROM drivers d
    ORDER BY d.driver_id
    """)
    drivers = cursor.fetchall()
    conn.close()
    return [{
        'driver_id': d[0],
        'name': d[1],
        'license_plate': d[2],
        'vehicle_type': d[3],
        'status': d[4],
        'lng': d[5],
        'lat': d[6],
        'total_distance': d[7],
        'total_deliveries': d[8],
        'shift': d[9],
        'phone': d[10],
        'pending_count': d[11],
        'completed_count': d[12]
    } for d in drivers]


def update_order_status(order_id, status):
    """更新订单状态"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE orders SET status=? WHERE customer_name=? OR id=?
    """, (status, order_id, order_id))
    # 也尝试用 order_id 字段匹配
    cursor.execute("""
    UPDATE orders SET status=? WHERE id IN (
        SELECT id FROM orders WHERE id=? OR CAST(id AS TEXT)=?
    )
    """, (status, order_id, str(order_id)))
    conn.commit()
    conn.close()


def get_active_tasks_with_routes():
    """获取所有进行中的任务及其路线信息，用于实时模拟"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT dt.id, dt.driver_id, dt.order_id, dt.customer_name, dt.address,
           dt.lng, dt.lat, dt.status,
           d.name as driver_name, d.current_lng, d.current_lat, d.license_plate
    FROM driver_tasks dt
    JOIN drivers d ON dt.driver_id = d.driver_id
    WHERE dt.status IN ('pending', 'in_progress')
    AND d.status = 'online'
    """)
    tasks = cursor.fetchall()
    conn.close()
    return [{
        'task_id': t[0],
        'driver_id': t[1],
        'order_id': t[2],
        'customer_name': t[3],
        'address': t[4],
        'dest_lng': t[5],
        'dest_lat': t[6],
        'status': t[7],
        'driver_name': t[8],
        'current_lng': t[9],
        'current_lat': t[10],
        'license_plate': t[11]
    } for t in tasks]


# ====================== 成本参数 ======================

def get_cost_params():
    """获取所有成本参数，返回字典"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT param_key, param_value, param_desc FROM cost_params")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: {'value': row[1], 'desc': row[2]} for row in rows}


def get_cost_value(key, default=0.0):
    """获取单个成本参数值"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT param_value FROM cost_params WHERE param_key=?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default


def update_cost_param(key, value):
    """更新单个成本参数"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE cost_params SET param_value=?, updated_at=CURRENT_TIMESTAMP
    WHERE param_key=?
    """, (value, key))
    conn.commit()
    conn.close()


def batch_update_cost_params(params_dict):
    """批量更新成本参数 {key: value}"""
    conn = get_connection()
    cursor = conn.cursor()
    for key, value in params_dict.items():
        cursor.execute("""
        UPDATE cost_params SET param_value=?, updated_at=CURRENT_TIMESTAMP
        WHERE param_key=?
        """, (value, key))
    conn.commit()
    conn.close()

