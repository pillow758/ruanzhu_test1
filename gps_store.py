"""真实设备定位存储；与 Qt 无关，供 HTTP 接收端和桌面端共用。"""
import hashlib
import math
import secrets
import sqlite3
import time
from contextlib import closing
from datetime import datetime

from database import db_manager

FRESH_SECONDS = 120


def ensure_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS gps_devices (
        driver_id TEXT PRIMARY KEY, token_hash TEXT NOT NULL,
        created_at REAL NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS gps_positions (
        driver_id TEXT PRIMARY KEY, lng REAL NOT NULL, lat REAL NOT NULL,
        raw_lng REAL NOT NULL, raw_lat REAL NOT NULL, coord_system TEXT NOT NULL,
        accuracy REAL NOT NULL, sampled_at REAL NOT NULL,
        received_at REAL NOT NULL, source TEXT NOT NULL)""")


def issue_token(driver_id):
    token = secrets.token_urlsafe(32)
    with closing(sqlite3.connect(db_manager.DB_PATH, timeout=10)) as conn, conn:
        if not conn.execute("SELECT 1 FROM drivers WHERE driver_id=?", (driver_id,)).fetchone():
            raise ValueError("驾驶员不存在")
        conn.execute("INSERT OR REPLACE INTO gps_devices VALUES (?, ?, ?)",
                     (driver_id, hashlib.sha256(token.encode()).hexdigest(), time.time()))
    return token


def _number(payload, key, minimum, maximum):
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} 必须是数值")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{key} 超出有效范围")
    return float(value)


def wgs84_to_gcj02(lng, lat):
    """离线近似转换到高德坐标；保留原始 WGS84，境外不偏移。"""
    if not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271):
        return lng, lat
    x, y = lng - 105, lat - 35
    dlat = -100 + 2*x + 3*y + .2*y*y + .1*x*y + .2*math.sqrt(abs(x))
    dlng = 300 + x + 2*y + .1*x*x + .1*x*y + .1*math.sqrt(abs(x))
    wave = (20*math.sin(6*x*math.pi) + 20*math.sin(2*x*math.pi))*2/3
    dlat += wave + (20*math.sin(y*math.pi) + 40*math.sin(y*math.pi/3))*2/3
    dlat += (160*math.sin(y*math.pi/12) + 320*math.sin(y*math.pi/30))*2/3
    dlng += wave + (20*math.sin(x*math.pi) + 40*math.sin(x*math.pi/3))*2/3
    dlng += (150*math.sin(x*math.pi/12) + 300*math.sin(x*math.pi/30))*2/3
    rad = math.radians(lat)
    magic = 1 - .00669342162296594323 * math.sin(rad)**2
    dlat = dlat*180 / ((6335552.717000426 / (magic*math.sqrt(magic))) * math.pi)
    dlng = dlng*180 / ((6378245 / math.sqrt(magic)) * math.cos(rad) * math.pi)
    return lng + dlng, lat + dlat


def accept_position(token, payload):
    if not isinstance(payload, dict):
        raise ValueError("请求必须是 JSON 对象")
    driver_id = payload.get("driver_id")
    if not isinstance(driver_id, str) or not isinstance(token, str) or not token:
        raise PermissionError("设备凭证无效")
    now = time.time()
    lng = _number(payload, "lng", -180, 180)
    lat = _number(payload, "lat", -90, 90)
    accuracy = _number(payload, "accuracy", 0, 100000)
    sampled_at = _number(payload, "timestamp", now - 300, now + 60)
    coord_system = payload.get("coord_system", "wgs84")
    source = payload.get("source", "phone")
    if coord_system not in ("wgs84", "gcj02") or source not in ("phone", "vehicle"):
        raise ValueError("仅支持 wgs84/gcj02 坐标和 phone/vehicle 来源")
    map_lng, map_lat = wgs84_to_gcj02(lng, lat) if coord_system == "wgs84" else (lng, lat)
    with closing(sqlite3.connect(db_manager.DB_PATH, timeout=10)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("""SELECT g.token_hash FROM gps_devices g
            JOIN drivers d ON d.driver_id=g.driver_id WHERE g.driver_id=?""", (driver_id,)).fetchone()
        if not row or not secrets.compare_digest(row[0], hashlib.sha256(token.encode()).hexdigest()):
            raise PermissionError("设备凭证无效或已重置")
        previous = conn.execute("SELECT sampled_at FROM gps_positions WHERE driver_id=?", (driver_id,)).fetchone()
        if previous and sampled_at <= previous[0]:
            return False  # 延迟到达或重复的数据不能覆盖新位置
        conn.execute("INSERT OR REPLACE INTO gps_positions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (driver_id, map_lng, map_lat, lng, lat, coord_system, accuracy, sampled_at, now, source))
        conn.execute("UPDATE drivers SET current_lng=?, current_lat=? WHERE driver_id=?",
                     (map_lng, map_lat, driver_id))
    return True


def get_positions():
    with closing(sqlite3.connect(db_manager.DB_PATH, timeout=10)) as conn:
        conn.row_factory = sqlite3.Row
        return {row["driver_id"]: dict(row) for row in conn.execute("SELECT * FROM gps_positions")}


def get_position(driver_id):
    return get_positions().get(driver_id)


def is_fresh(position, now=None):
    if not position:
        return False
    now = time.time() if now is None else now
    return now - min(position["received_at"], position["sampled_at"]) <= FRESH_SECONDS


def position_text(position):
    if not position:
        return "等待设备上报"
    source = "司机手机" if position["source"] == "phone" else "车载设备"
    state = "实时" if is_fresh(position) else "已超时 · 最后位置"
    stamp = datetime.fromtimestamp(position["sampled_at"]).strftime("%m-%d %H:%M:%S")
    return f"{source} · {state} · 精度 ±{position['accuracy']:.0f}m · {stamp}"
