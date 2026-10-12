"""配送中心设置持久化；高德地图坐标（GCJ02）是统一调度原点。"""
import json
import math
import sqlite3
from contextlib import closing
from database import db_manager

DEFAULT_DEPOT = dict(name='北京市中心配送站', address='北京市中心配送站',
                     lng=116.397, lat=39.908, province='', city='', district='',
                     street='', detail='', level='默认示例', source='default')
COARSE_LEVELS = {'国家', '省', '市', '区县', '区', '县', '乡镇', '村庄', '街道', '道路', '区域', '开发区', '未知', ''}


def ensure_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS depot_settings (
        id INTEGER PRIMARY KEY CHECK (id=1), payload TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")


def compose_address(province, city, district, street, detail=''):
    parts = [str(value).strip() for value in (province, city, district, street, detail)]
    municipality=parts[0].removesuffix('市')
    if parts[0] == parts[1] or (municipality in {'北京','上海','天津','重庆'} and parts[1] in {municipality,municipality+'市',municipality+'城区',municipality+'郊县'}):
        parts[1] = ''  # 直辖市省市字段相同，只拼接一次
    return ''.join(parts)


def precise_enough(point):
    return bool(point) and (point.get('source') == 'map' or point.get('level', '') not in COARSE_LEVELS)


def validate_depot(record):
    result = {}
    for key in ('name','province','city','district','street','detail','address','level','source'):
        value = record.get(key, '')
        if not isinstance(value, str) or len(value) > 500:
            raise ValueError('配送中心地址字段无效')
        result[key] = value.strip()
    if not all(result[k] for k in ('name','province','city','district','street','address')):
        raise ValueError('请填写配送中心名称、省、市、区县和街道/乡镇')
    if result['source'] not in ('map','geocode') or not precise_enough(result):
        raise ValueError('地址只匹配到行政区域或街道，请补充详细地址或在地图上选点')
    for key, maximum in (('lng',180),('lat',90)):
        value = record.get(key)
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or not -maximum <= value <= maximum:
            raise ValueError('配送中心经纬度无效')
        result[key] = float(value)
    return result


def save_depot(record):
    value = validate_depot(record)
    with closing(sqlite3.connect(db_manager.DB_PATH,timeout=10)) as conn, conn:
        ensure_schema(conn)
        conn.execute("INSERT OR REPLACE INTO depot_settings (id,payload,updated_at) VALUES (1,?,CURRENT_TIMESTAMP)",
                     (json.dumps(value,ensure_ascii=False),))
    return value


def get_depot():
    with closing(sqlite3.connect(db_manager.DB_PATH,timeout=10)) as conn:
        try:
            row = conn.execute('SELECT payload FROM depot_settings WHERE id=1').fetchone()
        except sqlite3.OperationalError as exc:
            if 'no such table' in str(exc):
                return None
            raise
    return validate_depot(json.loads(row[0])) if row else None


def get_effective_depot(fallback=None):
    return get_depot() or dict(DEFAULT_DEPOT, **(fallback or {}))
