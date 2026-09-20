import sys
import os
import sqlite3
import math
import random
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QInputDialog, QMessageBox, QStatusBar, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QUrl
from PyQt6.QtGui import QFont, QColor, QPalette
import pyqtgraph as pg
from echarts_window import EChartsAnalysis
from realtime_monitor import RealtimeMonitorWidget
from order_manage import OrderManageWidget
from cost_settings import CostSettingsDialog
from PyQt6.QtWidgets import QTabWidget, QFileDialog
from PyQt6.QtWebEngineWidgets import QWebEngineView

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
    print("警告: openpyxl 未安装，导出功能不可用。请运行: pip install openpyxl")

# 临时文件目录（用于地图HTML）
MAP_TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp_maps")
os.makedirs(MAP_TEMP_DIR, exist_ok=True)


def load_html_in_webview(web_view, html_content):
    """使用setHtml并设置baseUrl为https://localhost，使高德地图API接受合法origin"""
    web_view.setHtml(html_content, QUrl("https://localhost"))

DB_PATH = os.path.join(os.path.dirname(__file__), "database/logistics.db")
DB_PATH = os.path.abspath(DB_PATH)

# 禁用OpenGL以避免黑屏问题
pg.setConfigOptions(useOpenGL=False)
pg.setConfigOptions(antialias=True)

# ====================== 高德地图配置 ======================
# 请替换为你自己的高德地图 API Key（申请地址：https://lbs.amap.com/）
AMAP_API_KEY = "ddbc01b09151f242d386549e5f472f79"

# ====================== 参数配置 ======================
VEHICLE_CAPACITY = 3000
FIXED_COST = 400
COST_PER_KM = 2.5
COLORS = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F39C12', '#9B59B6', '#1ABC9C']

# ====================== 城市预设数据 ======================
CITIES = {
    '北京': {
        'dc_lng': 116.397, 'dc_lat': 39.908,
        'dc_name': '北京市中心配送站',
        'range': (0.15, 0.12),
        'customers': [
            ('A', 116.457, 39.888, 800,  "朝阳区建国路88号"),
            ('B', 116.357, 39.858, 600,  "丰台区南三环西路"),
            ('C', 116.427, 39.928, 700,  "东城区王府井大街"),
            ('D', 116.307, 39.968, 500,  "海淀区中关村大街"),
            ('E', 116.477, 39.828, 900,  "大兴区兴华大街"),
            ('F', 116.257, 39.908, 400,  "石景山区阜石路"),
        ],
    },
    '上海': {
        'dc_lng': 121.473, 'dc_lat': 31.230,
        'dc_name': '上海市中心配送站（人民广场）',
        'range': (0.18, 0.14),
        'customers': [
            ('A', 121.498, 31.240, 800,  "黄浦区南京东路"),
            ('B', 121.458, 31.189, 600,  "徐汇区漕溪北路"),
            ('C', 121.525, 31.228, 700,  "浦东新区陆家嘴环路"),
            ('D', 121.430, 31.260, 500,  "普陀区中山北路"),
            ('E', 121.398, 31.180, 900,  "闵行区沪闵路"),
            ('F', 121.545, 31.210, 400,  "浦东新区张杨路"),
        ],
    },
    '广州': {
        'dc_lng': 113.264, 'dc_lat': 23.129,
        'dc_name': '广州市中心配送站（越秀区）',
        'range': (0.16, 0.13),
        'customers': [
            ('A', 113.326, 23.132, 800,  "天河区天河路"),
            ('B', 113.257, 23.088, 600,  "海珠区新港中路"),
            ('C', 113.248, 23.148, 700,  "越秀区环市东路"),
            ('D', 113.188, 23.128, 500,  "荔湾区中山七路"),
            ('E', 113.360, 22.998, 900,  "番禺区大石街道"),
            ('F', 113.275, 23.188, 400,  "白云区白云大道"),
        ],
    },
    '深圳': {
        'dc_lng': 114.057, 'dc_lat': 22.543,
        'dc_name': '深圳市中心配送站（福田区）',
        'range': (0.15, 0.12),
        'customers': [
            ('A', 114.118, 22.548, 800,  "罗湖区深南东路"),
            ('B', 114.038, 22.528, 600,  "南山区科技南路"),
            ('C', 114.098, 22.568, 700,  "福田区华强北路"),
            ('D', 114.128, 22.578, 500,  "龙岗区龙翔大道"),
            ('E', 113.968, 22.548, 900,  "宝安区新安街道"),
            ('F', 114.048, 22.508, 400,  "南山区后海大道"),
        ],
    },
    '成都': {
        'dc_lng': 104.065, 'dc_lat': 30.659,
        'dc_name': '成都市中心配送站（天府广场）',
        'range': (0.16, 0.13),
        'customers': [
            ('A', 104.125, 30.648, 800,  "锦江区春熙路"),
            ('B', 104.048, 30.628, 600,  "武侯区科华北路"),
            ('C', 104.078, 30.688, 700,  "成华区建设路"),
            ('D', 103.998, 30.658, 500,  "青羊区青华路"),
            ('E', 104.118, 30.558, 900,  "高新区天府大道"),
            ('F', 104.068, 30.728, 400,  "金牛区交大路"),
        ],
    },
    '武汉': {
        'dc_lng': 114.298, 'dc_lat': 30.584,
        'dc_name': '武汉市中心配送站（江汉区）',
        'range': (0.18, 0.14),
        'customers': [
            ('A', 114.348, 30.568, 800,  "武昌区中南路"),
            ('B', 114.248, 30.548, 600,  "汉阳区龙阳大道"),
            ('C', 114.318, 30.608, 700,  "江岸区解放大道"),
            ('D', 114.358, 30.528, 500,  "洪山区珞喻路"),
            ('E', 114.218, 30.618, 900,  "硚口区武胜路"),
            ('F', 114.398, 30.498, 400,  "东湖高新区光谷大道"),
        ],
    },
}

# 当前城市（全局）
current_city = '北京'

# ====================== 数据结构 ======================
class Node:
    def __init__(self, id, lng, lat, q, address=""):
        """
        id: 节点ID
        lng: 经度
        lat: 纬度
        q: 需求量(kg)
        address: 地址描述
        """
        self.id = str(id)
        self.x = lng  # 兼容原代码，x=经度
        self.y = lat  # 兼容原代码，y=纬度
        self.lng = lng
        self.lat = lat
        self.q = q
        self.address = address

class Route:
    def __init__(self, nodes):
        self.nodes = nodes
        self.q = 0
        self.distance = 0
        self.cost = 0

# 全局数据（算法使用）
node_dict = {}
active_routes = []

# ====================== 核心算法 ======================
def haversine(lng1, lat1, lng2, lat2):
    """
    计算两点之间的球面距离（Haversine公式）
    返回距离（千米）
    """
    R = 6371  # 地球平均半径（千米）
    lng1_rad = math.radians(lng1)
    lat1_rad = math.radians(lat1)
    lng2_rad = math.radians(lng2)
    lat2_rad = math.radians(lat2)

    dlng = lng2_rad - lng1_rad
    dlat = lat2_rad - lat1_rad

    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2
    c = 2 * math.asin(math.sqrt(a))

    return R * c

def calc_dist(n1, n2):
    """计算两节点间的球面距离（千米）"""
    return haversine(n1.lng, n1.lat, n2.lng, n2.lat)

def evaluate_route(route_node_ids):
    total_q = 0
    total_dist = 0
    for nid in route_node_ids:
        if nid != 'DC':
            total_q += node_dict[nid].q
    for i in range(len(route_node_ids) - 1):
        n1 = node_dict[route_node_ids[i]]
        n2 = node_dict[route_node_ids[i + 1]]
        total_dist += calc_dist(n1, n2)

    if len(route_node_ids) <= 2:
        return total_q, total_dist, 0

    # 从数据库读取成本参数（支持用户自定义）
    from database.db_manager import get_cost_value
    fixed_cost    = get_cost_value('fixed_cost', FIXED_COST)
    fuel_price    = get_cost_value('fuel_price', 7.8)        # 元/L
    fuel_cons     = get_cost_value('fuel_consumption', 12.0) # L/100km
    toll_per_km   = get_cost_value('toll_per_km', 0.5)
    maint_per_km  = get_cost_value('maintenance_per_km', 0.3)

    fuel_cost_per_km  = fuel_price * fuel_cons / 100.0
    variable_per_km   = fuel_cost_per_km + toll_per_km + maint_per_km
    cost = fixed_cost + total_dist * variable_per_km
    return total_q, total_dist, cost

def savings_algorithm(customer_nodes):
    """Clark-Wright 节约算法"""
    routes = [['DC', c.id, 'DC'] for c in customer_nodes]
    savings = []
    for i in range(len(customer_nodes)):
        for j in range(i + 1, len(customer_nodes)):
            n_i, n_j = customer_nodes[i], customer_nodes[j]
            d_dc_i = calc_dist(node_dict['DC'], n_i)
            d_dc_j = calc_dist(node_dict['DC'], n_j)
            d_i_j = calc_dist(n_i, n_j)
            sav = d_dc_i + d_dc_j - d_i_j
            if sav > 0:
                savings.append((n_i.id, n_j.id, sav))
    savings.sort(key=lambda x: x[2], reverse=True)

    for i_id, j_id, _ in savings:
        route_i_idx = route_j_idx = -1
        for idx, r in enumerate(routes):
            if r[1] == i_id and r[-2] == i_id:
                route_i_idx = idx
            elif r[-2] == i_id:
                route_i_idx = idx
            if r[1] == j_id and r[-2] == j_id:
                route_j_idx = idx
            elif r[1] == j_id:
                route_j_idx = idx
        if route_i_idx != -1 and route_j_idx != -1 and route_i_idx != route_j_idx:
            r_i, r_j = routes[route_i_idx], routes[route_j_idx]
            q_i, _, _ = evaluate_route(r_i)
            q_j, _, _ = evaluate_route(r_j)
            if q_i + q_j <= VEHICLE_CAPACITY:
                merged_route = r_i[:-1] + r_j[1:]
                routes.pop(max(route_i_idx, route_j_idx))
                routes.pop(min(route_i_idx, route_j_idx))
                routes.append(merged_route)

    final_routes = []
    for r in routes:
        q, dist, cost = evaluate_route(r)
        route_obj = Route(r)
        route_obj.q, route_obj.distance, route_obj.cost = q, dist, cost
        final_routes.append(route_obj)
    return final_routes

def trigger_new_order(new_node):
    """动态插入新订单"""
    global active_routes
    node_dict[new_node.id] = new_node
    best_route_idx = best_insert_pos = -1
    min_add_cost = float('inf')
    for r_idx, r in enumerate(active_routes):
        if r.q + new_node.q > VEHICLE_CAPACITY:
            continue
        for pos in range(1, len(r.nodes)):
            trial_nodes = r.nodes[:pos] + [new_node.id] + r.nodes[pos:]
            _, _, trial_cost = evaluate_route(trial_nodes)
            add_cost = trial_cost - r.cost
            if add_cost < min_add_cost:
                min_add_cost = add_cost
                best_route_idx = r_idx
                best_insert_pos = pos
    if best_route_idx != -1:
        r = active_routes[best_route_idx]
        r.nodes.insert(best_insert_pos, new_node.id)
        r.q, r.distance, r.cost = evaluate_route(r.nodes)
    else:
        r_new = ['DC', new_node.id, 'DC']
        q, dist, cost = evaluate_route(r_new)
        route_obj = Route(r_new)
        route_obj.q, route_obj.distance, route_obj.cost = q, dist, cost
        active_routes.append(route_obj)

def trigger_cancel_order(cancel_id):
    """取消订单"""
    global active_routes
    target_r_idx = next((i for i, r in enumerate(active_routes) if cancel_id in r.nodes), -1)
    if target_r_idx == -1:
        return
    r = active_routes[target_r_idx]
    r.nodes.remove(cancel_id)
    r.q, r.distance, r.cost = evaluate_route(r.nodes)
    if len(r.nodes) <= 2:
        active_routes.pop(target_r_idx)

def trigger_change_address(target_id, new_lng, new_lat, new_address=""):
    """变更地址（模拟先删除再插入）"""
    global active_routes
    target_node = node_dict[target_id]
    temp_q = target_node.q
    trigger_cancel_order(target_id)
    target_node.lng, target_node.lat = new_lng, new_lat
    target_node.x, target_node.y = new_lng, new_lat
    target_node.address = new_address
    target_node.q = temp_q
    trigger_new_order(target_node)

# ====================== 高德地图视图组件 ======================
class AMapViewWidget(QWidget):
    """嵌入高德地图的视图组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view, 1)

        # 初始化时加载空白地图
        self.load_map()

    def load_map(self):
        """加载高德地图HTML"""
        html_content = self._generate_map_html()
        load_html_in_webview(self.web_view, html_content)

    def update_map(self):
        """更新地图上的标记和路线"""
        # 重新加载地图以更新数据
        self.load_map()

    def _generate_map_html(self):
        """生成包含标记和路线的高德地图HTML"""
        # 准备节点数据
        nodes_data = []
        for nid, node in node_dict.items():
            nodes_data.append({
                'id': nid,
                'lng': node.lng,
                'lat': node.lat,
                'q': node.q,
                'address': node.address,
                'is_dc': nid == 'DC'
            })

        # 准备路线数据
        routes_data = []
        for idx, r in enumerate(active_routes):
            path = []
            for nid in r.nodes:
                if nid in node_dict:
                    n = node_dict[nid]
                    path.append([n.lng, n.lat])
            routes_data.append({
                'vehicle_id': f'V{idx+1}',
                'path': path,
                'color': COLORS[idx % len(COLORS)],
                'distance': round(r.distance, 2),
                'cost': round(r.cost, 2),
                'q': round(r.q, 2)
            })

        # 计算地图中心
        if node_dict:
            all_lngs = [n.lng for n in node_dict.values()]
            all_lats = [n.lat for n in node_dict.values()]
            center_lng = sum(all_lngs) / len(all_lngs)
            center_lat = sum(all_lats) / len(all_lats)
        else:
            city = CITIES.get(current_city, CITIES['北京'])
            center_lng, center_lat = city['dc_lng'], city['dc_lat']

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ margin: 0; padding: 0; }}
                #map {{ width: 100%; height: 100vh; }}
                .info-window {{
                    font-family: "SimSun", sans-serif;
                    padding: 5px;
                }}
                .info-window h4 {{ margin: 0 0 5px 0; color: #333; }}
                .info-window p {{ margin: 2px 0; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <div id="map-error" style="display:none;position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#e74c3c;font-size:16px;text-align:center;font-family:SimSun,sans-serif;"></div>
            <script>
                window._AMapSecurityConfig = {{
                    securityJsCode: '776a13f6acec470076eb03e867c7e84d'
                }};
            </script>
            <script src="https://webapi.amap.com/maps?v=2.0&key={AMAP_API_KEY}"
                onerror="document.getElementById('map').style.display='none';var e=document.getElementById('map-error');e.style.display='block';e.innerHTML='⚠️ 地图加载失败<br><span style=font-size:13px;color:#888>请检查网络连接或API Key配置</span>';">
            </script>
            <script>
                // 初始化地图
                var map = new AMap.Map('map', {{
                    zoom: 12,
                    center: [{center_lng}, {center_lat}],
                    viewMode: '2D'
                }});

                // 节点数据
                var nodesData = {json.dumps(nodes_data)};

                // 路线数据
                var routesData = {json.dumps(routes_data)};

                // 添加节点标记
                nodesData.forEach(function(node) {{
                    var marker = new AMap.Marker({{
                        position: [node.lng, node.lat],
                        title: node.id,
                        content: node.is_dc ?
                            '<div style="background:#FFD700;width:24px;height:24px;border-radius:4px;display:flex;align-items:center;justify-content:center;font-weight:bold;border:2px solid #333;">DC</div>' :
                            '<div style="background:#3498DB;width:16px;height:16px;border-radius:50%;border:2px solid white;"></div>',
                        offset: new AMap.Pixel(-12, -12)
                    }});

                    // 信息窗口
                    var infoContent = '<div class="info-window">';
                    infoContent += '<h4>' + (node.is_dc ? '配送中心 (DC)' : '客户 ' + node.id) + '</h4>';
                    if (node.address) {{
                        infoContent += '<p>地址: ' + node.address + '</p>';
                    }}
                    if (!node.is_dc) {{
                        infoContent += '<p>需求量: ' + node.q + ' kg</p>';
                    }}
                    infoContent += '<p>坐标: ' + node.lng.toFixed(4) + ', ' + node.lat.toFixed(4) + '</p>';
                    infoContent += '</div>';

                    var infoWindow = new AMap.InfoWindow({{
                        content: infoContent,
                        offset: new AMap.Pixel(0, -30)
                    }});

                    marker.on('click', function() {{
                        infoWindow.open(map, marker.getPosition());
                    }});

                    map.add(marker);
                }});

                // 添加路线
                routesData.forEach(function(route) {{
                    if (route.path.length > 1) {{
                        var polyline = new AMap.Polyline({{
                            path: route.path,
                            strokeColor: route.color,
                            strokeWeight: 4,
                            strokeOpacity: 0.8,
                            lineJoin: 'round',
                            lineCap: 'round',
                            showDir: true
                        }});

                        // 路线信息窗口
                        var routeInfo = '<div class="info-window">';
                        routeInfo += '<h4>' + route.vehicle_id + '</h4>';
                        routeInfo += '<p>距离: ' + route.distance + ' km</p>';
                        routeInfo += '<p>载重: ' + route.q + ' kg</p>';
                        routeInfo += '<p>成本: ¥' + route.cost + '</p>';
                        routeInfo += '</div>';

                        var routeInfoWindow = new AMap.InfoWindow({{
                            content: routeInfo,
                            offset: new AMap.Pixel(0, -10)
                        }});

                        polyline.on('click', function(e) {{
                            routeInfoWindow.open(map, e.lnglat);
                        }});

                        map.add(polyline);
                    }}
                }});

                // 自动调整视野以显示所有标记
                if (nodesData.length > 0) {{
                    map.setFitView(null, false, [50, 50, 50, 50]);
                }}
            </script>
        </body>
        </html>
        """


# ====================== 主界面 ======================
class LogisticsApp(QMainWindow):
    def __init__(self, username="admin"):
        super().__init__()
        self.username = username
        self.setWindowTitle("🚚 动态物流调度模拟系统 by pillow")
        self.setGeometry(100, 100, 1400, 800)
        self.setup_ui()
        self.apply_dark_theme()

        # 动画状态
        self.vehicle_pos = []
        self.vehicle_colors = []
        self.unload_status = {}
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)

        # 初始化数据并开始动画
        self.init_data()
        self.start_animation()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ---------- 左侧控制面板 ----------
        left_panel = QFrame()
        left_panel.setFixedWidth(360)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        # 标题
        title = QLabel("📋 调度控制系统")
        title.setFont(QFont("SimSun", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title)

        # 城市选择器
        city_frame = QFrame()
        city_frame.setStyleSheet("background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;")
        city_layout = QHBoxLayout(city_frame)
        city_layout.setContentsMargins(8, 6, 8, 6)
        city_lbl = QLabel("🌆 城市：")
        city_lbl.setStyleSheet("color:#1e40af;font:bold 12px SimSun;border:none;")
        city_layout.addWidget(city_lbl)
        self.city_combo = QComboBox()
        self.city_combo.addItems(list(CITIES.keys()))
        self.city_combo.setCurrentText(current_city)
        self.city_combo.setStyleSheet("""
            QComboBox {
                background:#ffffff;color:#1e293b;border:1px solid #3b82f6;
                border-radius:6px;padding:4px 8px;font:bold 12px SimSun;
            }
            QComboBox::drop-down{border:none;}
            QComboBox QAbstractItemView{background:#ffffff;color:#1e293b;selection-background-color:#dbeafe;selection-color:#1e40af;border:1px solid #bfdbfe;}
        """)
        self.city_combo.currentTextChanged.connect(self.on_city_changed)
        city_layout.addWidget(self.city_combo, 1)
        left_layout.addWidget(city_frame)

        # 按钮组
        btn_data = [
            ("🎯 静态规划", self.init_routes, "#27AE60"),
            ("➕ 新增订单", self.add_order, "#3498DB"),
            ("❌ 取消订单", self.cancel_order, "#E74C3C"),
            ("📍 地址变更", self.change_address, "#F39C12"),
            ("🎲 批量随机模拟", self.batch_simulation, "#9B59B6"),
            ("🚛 分配任务", self.assign_tasks_to_drivers, "#E67E22"),
            ("📥 导出调度方案", self.export_routes, "#16A085"),
            ("⚙️ 成本设置", self.open_cost_settings, "#8E44AD"),
            ("🗺️ 刷新地图", self.refresh_map, "#1ABC9C"),
            ("🔄 重置系统", self.reset_system, "#95A5A6"),
        ]
        for text, slot, color in btn_data:
            btn = QPushButton(text)
            btn.setFont(QFont("SimSun", 10))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    border-radius: 8px;
                    padding: 10px;
                }}
                QPushButton:hover {{
                    background-color: {self.lighten_color(color)};
                }}
                QPushButton:pressed {{
                    background-color: {self.darken_color(color)};
                }}
            """)
            btn.clicked.connect(slot)
            left_layout.addWidget(btn)

        # 统计信息
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 10px; padding: 10px;")
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setSpacing(5)

        stats_title = QLabel("📊 运营统计")
        stats_title.setFont(QFont("SimSun", 11, QFont.Weight.Bold))
        stats_title.setStyleSheet("color: #1e40af; border: none;")
        stats_layout.addWidget(stats_title)

        self.lbl_vehicle = QLabel("🚛 使用车辆: 0")
        self.lbl_load = QLabel("📦 总载重: 0 kg")
        self.lbl_dist = QLabel("📏 总距离: 0 km")
        self.lbl_cost = QLabel("💰 总成本: ¥ 0")
        for lbl in (self.lbl_vehicle, self.lbl_load, self.lbl_dist, self.lbl_cost):
            lbl.setFont(QFont("SimSun", 9))
            lbl.setStyleSheet("color: #334155; border: none;")
            stats_layout.addWidget(lbl)
        left_layout.addWidget(stats_frame)

        # 车辆详情表格
        table_label = QLabel("🚚 车辆配送详情")
        table_label.setFont(QFont("SimSun", 11, QFont.Weight.Bold))
        left_layout.addWidget(table_label)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["车辆", "载重(kg)", "距离(km)", "成本(¥)", "路径"])
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e2e8f0;
                color: #1e293b;
                font: 9pt "SimSun";
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #3b82f6;
                color: white;
                padding: 5px;
                border: none;
                font-weight: bold;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #1e40af;
            }
        """)
        left_layout.addWidget(self.table, 1)

        main_layout.addWidget(left_panel)

        # ---------- 右侧显示面板 ----------
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 新建 Tab
        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs)

        # Tab 1: 调度动画页（pyqtgraph）
        self.dispatch_container = QWidget()
        dispatch_layout = QVBoxLayout(self.dispatch_container)
        dispatch_layout.setContentsMargins(0, 0, 0, 0)
        dispatch_layout.setSpacing(0)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#f0f4f8')
        self.plot_widget.setLabel('left', '纬度 (°)')
        self.plot_widget.setLabel('bottom', '经度 (°)')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setMinimumSize(400, 300)
        dispatch_layout.addWidget(self.plot_widget, 1)

        self.tabs.addTab(self.dispatch_container, "调度动画")

        # Tab 2: 高德地图页
        self.map_widget = AMapViewWidget()
        self.tabs.addTab(self.map_widget, "地图视图")

        # Tab 3: 实时监控页
        self.realtime_widget = RealtimeMonitorWidget()
        self.tabs.addTab(self.realtime_widget, "实时监控")

        # Tab 4: 订单管理页
        self.order_widget = OrderManageWidget()
        self.tabs.addTab(self.order_widget, "订单管理")

        # Tab 5: 数据分析页
        self.analysis_widget = EChartsAnalysis()
        self.tabs.addTab(self.analysis_widget, "数据分析")

        # Tab切换时强制重绘
        self.tabs.currentChanged.connect(self.on_tab_changed)
        main_layout.addWidget(right_panel, 1)

        # ---------- 状态栏 ----------
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("background-color: #ffffff; color: #64748b; border-top: 1px solid #e2e8f0;")
        self.status_msg = QLabel("✅ 系统就绪")
        self.status_msg.setFont(QFont("SimSun", 9))
        self.status_bar.addWidget(self.status_msg)
        self.setStatusBar(self.status_bar)

    def on_tab_changed(self, index):
        """Tab切换时处理"""
        if index == 0:  # 调度动画页
            self.plot_widget.update()
        elif index == 1:  # 地图页
            self.refresh_map()
        elif index == 2:  # 实时监控页
            if hasattr(self, 'realtime_widget'):
                self.realtime_widget._load_data()
        elif index == 3:  # 订单管理页
            if hasattr(self, 'order_widget'):
                self.order_widget._load_orders()

    def apply_dark_theme(self):
        """全局方案A简洁卡片风（浅色/蓝色主题）"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f4f8;
            }
            QWidget {
                background-color: transparent;
                color: #1e293b;
                font-family: "SimSun";
            }
            QFrame {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
            QLabel {
                background-color: transparent;
                color: #1e293b;
            }
            QTabWidget::pane {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #f1f5f9;
                color: #64748b;
                border: none;
                padding: 8px 18px;
                font-size: 13px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #3b82f6;
                color: white;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background: #dbeafe;
                color: #1e40af;
            }
            QMessageBox {
                background: #ffffff;
            }
            QMessageBox QLabel {
                color: #1e293b;
            }
            QMessageBox QPushButton {
                background: #3b82f6;
                border-radius: 8px;
                padding: 8px 20px;
                color: white;
                font-weight: bold;
            }
            QMessageBox QPushButton:hover {
                background: #2563eb;
            }
        """)

    def lighten_color(self, hex_color):
        """简易颜色变亮"""
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        r = min(255, r + 30); g = min(255, g + 30); b = min(255, b + 30)
        return f"#{r:02x}{g:02x}{b:02x}"

    def darken_color(self, hex_color):
        r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
        r = max(0, r - 30); g = max(0, g - 30); b = max(0, b - 30)
        return f"#{r:02x}{g:02x}{b:02x}"

    def init_data(self):
        """初始化示例数据（根据 current_city 加载对应城市节点）"""
        global node_dict, active_routes, current_city
        node_dict.clear()
        active_routes.clear()

        city = CITIES.get(current_city, CITIES['北京'])
        dc_lng, dc_lat, dc_name = city['dc_lng'], city['dc_lat'], city['dc_name']
        rng_lng, rng_lat = city['range']

        # 配送中心
        node_dict['DC'] = Node('DC', dc_lng, dc_lat, 0, dc_name)

        # 客户节点
        for nid, lng, lat, q, addr in city['customers']:
            node_dict[nid] = Node(nid, lng, lat, q, addr)

        # 设置pyqtgraph坐标范围
        self.plot_widget.setRange(
            xRange=[dc_lng - rng_lng * 2, dc_lng + rng_lng * 2],
            yRange=[dc_lat - rng_lat * 2, dc_lat + rng_lat * 2]
        )

        self.init_routes()

    def init_routes(self):
        """静态优化路线"""
        global active_routes
        customers = [node_dict[nid] for nid in node_dict if nid != 'DC']
        active_routes = savings_algorithm(customers)
        self.save_routes_to_db()
        self.reset_animation()
        self.update_stats()
        self.refresh_map()
        self.status_msg.setText("✅ 静态规划完成，路线已优化")
        QTimer.singleShot(100, lambda: QMessageBox.information(self, "完成",
            f"静态规划完成！\n使用车辆: {len(active_routes)} 辆\n总成本: ¥{sum(r.cost for r in active_routes):.1f}"))

    def save_routes_to_db(self):
        """把 active_routes 写入 routes 表供 ECharts 使用"""
        global active_routes
        if not active_routes:
            return
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM routes")
            for idx, r in enumerate(active_routes):
                nodes_str = ",".join(r.nodes)
                cursor.execute("""
                INSERT INTO routes (vehicle_id, nodes, distance, cost, q)
                VALUES (?, ?, ?, ?, ?)
                """, (f"V{idx+1}", nodes_str, r.distance, r.cost, r.q))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"保存路线到数据库失败: {e}")

    def reset_animation(self):
        """重置动画状态"""
        self.vehicle_pos = [0.0] * len(active_routes)
        self.vehicle_colors = [COLORS[i % len(COLORS)] for i in range(len(active_routes))]
        self.unload_status = {i: False for i in range(len(active_routes))}

    def start_animation(self):
        self.update_plot()
        self.timer.start(50)  # 20帧/秒

    def update_plot(self):
        """每帧重绘全部内容（高性能）"""
        self.plot_widget.clear()

        # 绘制配送中心
        dc = node_dict['DC']
        dc_item = pg.ScatterPlotItem(
            [dc.lng], [dc.lat], symbol='s', size=20,
            pen=pg.mkPen(color='#FFD700', width=3), brush=pg.mkBrush('#2C3E50')
        )
        self.plot_widget.addItem(dc_item)
        dc_text = pg.TextItem('DC', color='#FFD700', anchor=(0.5, -0.5))
        dc_text.setFont(QFont('SimSun', 10, QFont.Weight.Bold))
        dc_text.setPos(dc.lng, dc.lat + 0.005)
        self.plot_widget.addItem(dc_text)

        # 绘制所有客户点
        client_x, client_y, client_labels = [], [], []
        for nid, n in node_dict.items():
            if nid == 'DC':
                continue
            client_x.append(n.lng)
            client_y.append(n.lat)
            client_labels.append((n.lng, n.lat, f'{nid}\n({n.q}kg)'))
        clients = pg.ScatterPlotItem(
            client_x, client_y, symbol='o', size=12,
            pen=pg.mkPen(color='white', width=1.5), brush=pg.mkBrush('#3498DB')
        )
        self.plot_widget.addItem(clients)
        for lng, lat, text in client_labels:
            label = pg.TextItem(text, color='#b0b0b0', anchor=(0.5, -0.5))
            label.setFont(QFont('SimSun', 8))
            label.setPos(lng, lat + 0.003)
            self.plot_widget.addItem(label)

        # 绘制路线与车辆动画
        for idx, r in enumerate(active_routes):
            xs = [node_dict[nid].lng for nid in r.nodes]
            ys = [node_dict[nid].lat for nid in r.nodes]
            color = self.vehicle_colors[idx]

            # 路线（半透明虚线）
            line = pg.PlotDataItem(xs, ys, pen=pg.mkPen(color, width=2, style=Qt.PenStyle.DashLine), symbol=None)
            self.plot_widget.addItem(line)

            # 车辆动画位置
            if idx < len(self.vehicle_pos):
                pos = self.vehicle_pos[idx]
                if pos >= len(r.nodes) - 1:
                    self.vehicle_pos[idx] = 0.0
                    pos = 0.0
                i = int(pos)
                j = min(i + 1, len(r.nodes) - 1)
                t = pos - i
                x = xs[i] + (xs[j] - xs[i]) * t
                y = ys[i] + (ys[j] - ys[i]) * t

                # 光晕效果
                glow = pg.ScatterPlotItem(
                    [x], [y], symbol='o', size=20,
                    pen=None, brush=pg.mkBrush(color + '60')
                )
                self.plot_widget.addItem(glow)
                vehicle = pg.ScatterPlotItem(
                    [x], [y], symbol='o', size=14,
                    pen=pg.mkPen('white', width=2), brush=pg.mkBrush(color)
                )
                self.plot_widget.addItem(vehicle)
                label = pg.TextItem(f'V{idx+1}', color=color, anchor=(0.5, 0.5))
                label.setFont(QFont('SimSun', 7, QFont.Weight.Bold))
                label.setPos(x, y)
                self.plot_widget.addItem(label)

                self.vehicle_pos[idx] += 0.03

    def update_stats(self):
        """刷新统计信息与表格"""
        total_dist = sum(r.distance for r in active_routes)
        total_cost = sum(r.cost for r in active_routes)
        total_q = sum(r.q for r in active_routes)
        self.lbl_vehicle.setText(f"🚛 使用车辆: {len(active_routes)}")
        self.lbl_load.setText(f"📦 总载重: {total_q:.0f} kg")
        self.lbl_dist.setText(f"📏 总距离: {total_dist:.2f} km")
        self.lbl_cost.setText(f"💰 总成本: ¥ {total_cost:.1f}")

        # 更新表格
        self.table.setRowCount(len(active_routes))
        for idx, r in enumerate(active_routes):
            path_str = " → ".join(r.nodes[:3])
            if len(r.nodes) > 4:
                path_str += " …"
            items = [
                QTableWidgetItem(f"车辆{idx+1}"),
                QTableWidgetItem(f"{r.q:.0f}"),
                QTableWidgetItem(f"{r.distance:.2f}"),
                QTableWidgetItem(f"¥{r.cost:.1f}"),
                QTableWidgetItem(path_str),
            ]
            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(idx, col, item)

        self.status_msg.setText(
            f"📅 最后更新 | 📊 车辆: {len(active_routes)} | 成本: ¥{total_cost:.0f}"
        )

    def open_cost_settings(self):
        """打开成本参数配置对话框"""
        dialog = CostSettingsDialog(self)
        if dialog.exec():
            # 参数已保存，重新计算所有路线成本
            for r in active_routes:
                r.q, r.distance, r.cost = evaluate_route(r.nodes)
            self.update_stats()
            self.refresh_map()
            self.status_msg.setText("✅ 成本参数已更新，路线成本已重新计算")

    def refresh_map(self):
        """刷新高德地图视图"""
        if hasattr(self, 'map_widget'):
            self.map_widget.update_map()

    def assign_tasks_to_drivers(self):
        """分配任务给驾驶员"""
        from database.db_manager import get_all_drivers, generate_random_orders, batch_assign_tasks, get_driver_tasks

        # 获取所有驾驶员
        drivers = get_all_drivers()
        if not drivers:
            QMessageBox.warning(self, "提示", "没有可用的驾驶员！请先添加驾驶员账号。")
            return

        # 选择驾驶员
        driver_names = [f"{d['driver_id']} - {d['name']} ({d['license_plate']})" for d in drivers]
        driver_choice, ok = QInputDialog.getItem(
            self, "选择驾驶员", "请选择要分配任务的驾驶员:",
            driver_names, 0, False
        )
        if not ok:
            return

        # 解析驾驶员ID
        selected_driver_id = driver_choice.split(" - ")[0]

        # 询问生成任务数量
        count, ok = QInputDialog.getInt(
            self, "任务数量", "要生成多少个配送任务？",
            5, 1, 20, 1
        )
        if not ok:
            return

        # 生成随机订单并分配
        orders = generate_random_orders(count)
        task_ids = batch_assign_tasks(selected_driver_id, orders)

        # 记录状态变更日志
        from database.db_manager import log_order_status_change
        for order, tid in zip(orders, task_ids):
            log_order_status_change(
                order_id=order['order_id'],
                task_id=tid,
                from_status='',
                to_status='pending',
                operator=self.username if hasattr(self, 'username') else 'admin',
                note=f'管理员分配任务给 {selected_driver_id}'
            )

        # 显示结果
        driver_name = next(d['name'] for d in drivers if d['driver_id'] == selected_driver_id)
        QMessageBox.information(
            self, "分配成功",
            f"已将 {count} 个配送任务分配给：\n"
            f"👨‍✈️ {driver_name} ({selected_driver_id})\n\n"
            f"任务已添加到驾驶员工作台。\n"
            f"驾驶员可在工作台进行取货、导航、送达等操作。"
        )

        self.status_msg.setText(f"✅ 已分配 {count} 个任务给 {driver_name}")

    def export_routes(self):
        """导出调度方案到Excel文件"""
        if not OPENPYXL_AVAILABLE:
            QMessageBox.warning(self, "错误", "导出功能需要安装 openpyxl 库。\n请运行: pip install openpyxl")
            return

        if not active_routes:
            QMessageBox.warning(self, "警告", "没有可导出的调度方案！请先进行路线规划。")
            return

        # 选择保存路径
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出调度方案",
            "物流调度方案.xlsx",
            "Excel文件 (*.xlsx)"
        )

        if not file_path:
            return

        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "调度方案总览"

            # 样式定义
            header_font = Font(bold=True, size=12, color="FFFFFF")
            header_fill = PatternFill(start_color="3498DB", end_color="3498DB", fill_type="solid")
            header_alignment = Alignment(horizontal="center", vertical="center")
            border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )

            # 标题
            ws.merge_cells('A1:G1')
            title_cell = ws['A1']
            title_cell.value = "动态物流调度方案报告"
            title_cell.font = Font(bold=True, size=16)
            title_cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[1].height = 30

            # 统计信息
            ws['A3'] = "统计项目"
            ws['B3'] = "数值"
            ws['A3'].font = Font(bold=True, size=11)
            ws['B3'].font = Font(bold=True, size=11)
            ws['A3'].fill = PatternFill(start_color="E8E8E8", end_color="E8E8E8", fill_type="solid")
            ws['B3'].fill = PatternFill(start_color="E8E8E8", end_color="E8E8E8", fill_type="solid")

            total_dist = sum(r.distance for r in active_routes)
            total_cost = sum(r.cost for r in active_routes)
            total_q = sum(r.q for r in active_routes)

            stats = [
                ("使用车辆数", f"{len(active_routes)} 辆"),
                ("总载重量", f"{total_q:.0f} kg"),
                ("总配送距离", f"{total_dist:.2f} km"),
                ("总配送成本", f"¥ {total_cost:.2f}"),
                ("平均单车距离", f"{total_dist/len(active_routes):.2f} km"),
                ("平均单车成本", f"¥ {total_cost/len(active_routes):.2f}"),
            ]

            for i, (item, value) in enumerate(stats, start=4):
                ws[f'A{i}'] = item
                ws[f'B{i}'] = value

            # 车辆路线详情表头
            detail_start_row = 12
            ws.merge_cells(f'A{detail_start_row}:G{detail_start_row}')
            ws[f'A{detail_start_row}'] = "车辆路线详情"
            ws[f'A{detail_start_row}'].font = Font(bold=True, size=14)
            ws[f'A{detail_start_row}'].alignment = Alignment(horizontal="center")

            headers = ["车辆编号", "配送节点", "载重(kg)", "距离(km)", "成本(¥)", "节点数", "备注"]
            header_row = detail_start_row + 1

            for col, header in enumerate(headers, start=1):
                cell = ws.cell(row=header_row, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
                cell.border = border

            # 车辆路线数据
            for idx, r in enumerate(active_routes):
                row = header_row + 1 + idx
                path_str = " → ".join(r.nodes)

                # 构建备注：包含各节点地址
                notes = []
                for nid in r.nodes:
                    if nid != 'DC' and nid in node_dict:
                        node = node_dict[nid]
                        if node.address:
                            notes.append(f"{nid}: {node.address}")
                note_str = "; ".join(notes) if notes else "无"

                data = [
                    f"车辆{idx+1}",
                    path_str,
                    round(r.q, 2),
                    round(r.distance, 2),
                    round(r.cost, 2),
                    len([n for n in r.nodes if n != 'DC']),
                    note_str
                ]

                for col, value in enumerate(data, start=1):
                    cell = ws.cell(row=row, column=col, value=value)
                    cell.border = border
                    cell.alignment = Alignment(horizontal="center" if col != 2 and col != 7 else "left")

            # 设置列宽
            ws.column_dimensions['A'].width = 15
            ws.column_dimensions['B'].width = 35
            ws.column_dimensions['C'].width = 12
            ws.column_dimensions['D'].width = 12
            ws.column_dimensions['E'].width = 12
            ws.column_dimensions['F'].width = 10
            ws.column_dimensions['G'].width = 40

            # 第二个Sheet：节点详细信息
            ws2 = wb.create_sheet("节点信息")
            ws2['A1'] = "节点详细信息"
            ws2.merge_cells('A1:F1')
            ws2['A1'].font = Font(bold=True, size=14)
            ws2['A1'].alignment = Alignment(horizontal="center")

            node_headers = ["节点ID", "经度", "纬度", "地址", "需求量(kg)", "类型"]
            for col, header in enumerate(node_headers, start=1):
                cell = ws2.cell(row=3, column=col, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
                cell.border = border

            row = 4
            for nid, node in node_dict.items():
                data = [
                    nid,
                    round(node.lng, 6),
                    round(node.lat, 6),
                    node.address if node.address else "无",
                    node.q if nid != 'DC' else "-",
                    "配送中心" if nid == 'DC' else "客户"
                ]
                for col, value in enumerate(data, start=1):
                    cell = ws2.cell(row=row, column=col, value=value)
                    cell.border = border
                    cell.alignment = Alignment(horizontal="center")
                row += 1

            # 设置列宽
            ws2.column_dimensions['A'].width = 12
            ws2.column_dimensions['B'].width = 15
            ws2.column_dimensions['C'].width = 15
            ws2.column_dimensions['D'].width = 35
            ws2.column_dimensions['E'].width = 15
            ws2.column_dimensions['F'].width = 12

            # 保存文件
            wb.save(file_path)

            self.status_msg.setText(f"✅ 调度方案已导出: {os.path.basename(file_path)}")
            QMessageBox.information(self, "导出成功", f"调度方案已成功导出到:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出过程中发生错误:\n{str(e)}")

    # ---------- 按钮槽函数 ----------
    def add_order(self):
        nid, ok = QInputDialog.getText(self, "新增订单", "请输入订单ID:")
        if not ok or not nid.strip():
            return
        nid = nid.strip()
        if nid in node_dict:
            QMessageBox.warning(self, "错误", "订单ID已存在！")
            return
        # 根据当前城市设置坐标范围
        city = CITIES.get(current_city, CITIES['北京'])
        base_lng, base_lat = city['dc_lng'], city['dc_lat']
        rng_lng, rng_lat = city['range']
        lng_min, lng_max = base_lng - rng_lng * 2, base_lng + rng_lng * 2
        lat_min, lat_max = base_lat - rng_lat * 2, base_lat + rng_lat * 2
        # 输入经度
        lng, ok = QInputDialog.getDouble(
            self, "新增订单", f"经度 ({lng_min:.3f}-{lng_max:.3f}):",
            base_lng, lng_min, lng_max, 4)
        if not ok: return
        # 输入纬度
        lat, ok = QInputDialog.getDouble(
            self, "新增订单", f"纬度 ({lat_min:.3f}-{lat_max:.3f}):",
            base_lat, lat_min, lat_max, 4)
        if not ok: return
        # 输入地址
        address, ok = QInputDialog.getText(self, "新增订单", "地址描述:")
        if not ok: address = ""
        # 输入重量
        q, ok = QInputDialog.getDouble(self, "新增订单", "重量 (kg):", 500, 1, 3000, 1)
        if not ok: return

        new_node = Node(nid, lng, lat, q, address)
        global active_routes
        trigger_new_order(new_node)
        self.save_routes_to_db()
        self.reset_animation()
        self.update_stats()
        self.refresh_map()
        self.status_msg.setText(f"✅ 已新增订单 {nid}")

    def cancel_order(self):
        customers = [nid for nid in node_dict if nid != 'DC']
        if not customers:
            QMessageBox.warning(self, "警告", "没有可取消的订单！")
            return
        nid, ok = QInputDialog.getItem(self, "取消订单", "选择订单ID:", customers, 0, False)
        if ok and nid:
            global active_routes
            trigger_cancel_order(nid)
            self.save_routes_to_db()
            self.reset_animation()
            self.update_stats()
            self.refresh_map()
            self.status_msg.setText(f"✅ 已取消订单 {nid}")

    def change_address(self):
        customers = [nid for nid in node_dict if nid != 'DC']
        if not customers:
            QMessageBox.warning(self, "警告", "没有可修改的订单！")
            return
        nid, ok = QInputDialog.getItem(self, "地址变更", "选择订单:", customers, 0, False)
        if not ok: return
        lng, ok = QInputDialog.getDouble(self, "地址变更", "新经度 (116.0-117.0):", 116.4, 116.0, 117.0, 4)
        if not ok: return
        lat, ok = QInputDialog.getDouble(self, "地址变更", "新纬度 (39.5-40.5):", 39.9, 39.5, 40.5, 4)
        if not ok: return
        address, ok = QInputDialog.getText(self, "地址变更", "新地址描述:")
        if not ok: address = ""
        global active_routes
        trigger_change_address(nid, lng, lat, address)
        self.save_routes_to_db()
        self.reset_animation()
        self.update_stats()
        self.refresh_map()
        self.status_msg.setText(f"✅ 已更新订单 {nid} 地址")

    def batch_simulation(self):
        num, ok = QInputDialog.getInt(self, "批量随机模拟", "生成订单数量:", 5, 1, 20, 1)
        if not ok: return
        self.reset_system_silent()  # 先清空（不弹确认框）
        global active_routes, current_city
        new_ids = []
        # 根据当前城市设置坐标范围
        city = CITIES.get(current_city, CITIES['北京'])
        base_lng, base_lat = city['dc_lng'], city['dc_lat']
        rng_lng, rng_lat = city['range']
        for _ in range(num):
            nid = f"R{random.randint(100, 999)}"
            while nid in node_dict:
                nid = f"R{random.randint(100, 999)}"
            lng = base_lng + random.uniform(-rng_lng, rng_lng)
            lat = base_lat + random.uniform(-rng_lat, rng_lat)
            q = random.randint(200, 1500)
            address = f"模拟地址{random.randint(1,999)}号"
            new_node = Node(nid, lng, lat, q, address)
            trigger_new_order(new_node)
            new_ids.append(nid)
        self.reset_animation()
        self.save_routes_to_db()
        self.update_stats()
        self.refresh_map()
        self.status_msg.setText(f"✅ 批量模拟完成，新增 {num} 个随机订单")
        QMessageBox.information(self, "完成", f"已生成 {num} 个随机订单！\nID示例: {', '.join(new_ids[:5])}" +
                                ("…" if num > 5 else ""))

    def on_city_changed(self, city_name):
        """切换城市"""
        global current_city
        if city_name not in CITIES:
            return
        current_city = city_name
        reply = QMessageBox.question(
            self, "切换城市",
            f"切换到「{city_name}」将重新加载城市节点数据，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.init_data()
            self.status_msg.setText(f"🌆 已切换至：{city_name}")

    def reset_system_silent(self):
        """静默重置系统（不弹确认框）"""
        global node_dict, active_routes, current_city
        node_dict.clear()
        active_routes.clear()
        city = CITIES.get(current_city, CITIES['北京'])
        node_dict['DC'] = Node('DC', city['dc_lng'], city['dc_lat'], 0, city['dc_name'])

    def reset_system(self):
        reply = QMessageBox.question(self, "确认", "重置将清除所有订单数据，确定吗？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.init_data()

# ====================== 程序入口 ======================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("SimSun", 10))
    window = LogisticsApp()
    window.show()
    sys.exit(app.exec())
