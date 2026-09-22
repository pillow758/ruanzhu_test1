import sys
import os
import json
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QListWidget, QListWidgetItem,
    QMessageBox, QInputDialog, QStackedWidget, QScrollArea,
    QSizePolicy, QDialog, QTextEdit, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtWebEngineWidgets import QWebEngineView

from database.db_manager import (
    get_driver_tasks, update_task_status, report_exception,
    update_driver_status, get_driver_info, log_order_status_change,
    update_driver_location
)

# 高德地图 API Key
AMAP_API_KEY = "ddbc01b09151f242d386549e5f472f79"

# 临时文件目录（用于地图HTML）
MAP_TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp_driver_maps")
os.makedirs(MAP_TEMP_DIR, exist_ok=True)


def load_html_in_webview(web_view, html_content):
    """使用setHtml并设置baseUrl为https://localhost，使高德地图API接受合法origin"""
    web_view.setHtml(html_content, QUrl("https://localhost"))


# ====================== 任务卡片组件 ======================
class TaskCard(QFrame):
    """单个任务卡片 - 方案A：白色卡片 + 蓝色主题"""
    task_action = pyqtSignal(str, int)  # action, task_id

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.task_id = task['id']
        self.init_ui()

    def init_ui(self):
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            TaskCard {
                background: #ffffff;
                border-radius: 12px;
                border: 1px solid #e2e8f0;
                margin: 5px;
            }
            TaskCard:hover {
                border: 1px solid #3b82f6;
            }
        """)
        self.setMinimumHeight(140)

        layout = QVBoxLayout()
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(8)

        # 顶部：订单号 + 状态
        top_layout = QHBoxLayout()

        order_label = QLabel(f"📦 {self.task['order_id']}")
        order_label.setStyleSheet("color: #1e40af; font-size: 16px; font-weight: bold;")
        top_layout.addWidget(order_label)

        top_layout.addStretch()

        status = self.task['status']
        status_colors = {
            'pending': ('#f59e0b', '待取货'),
            'in_progress': ('#3b82f6', '配送中'),
            'completed': ('#10b981', '已完成'),
            'exception': ('#ef4444', '异常')
        }
        color, text = status_colors.get(status, ('#6b7280', '未知'))
        status_label = QLabel(f"● {text}")
        status_label.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")
        top_layout.addWidget(status_label)

        layout.addLayout(top_layout)

        # 客户信息
        customer_label = QLabel(f"👤 {self.task['customer_name']}")
        customer_label.setStyleSheet("color: #1e293b; font-size: 14px;")
        layout.addWidget(customer_label)

        # 地址
        address_label = QLabel(f"📍 {self.task['address']}")
        address_label.setStyleSheet("color: #64748b; font-size: 12px;")
        address_label.setWordWrap(True)
        layout.addWidget(address_label)

        # 底部：重量 + 操作按钮
        bottom_layout = QHBoxLayout()

        demand_label = QLabel(f"📦 {self.task['demand']:.1f} kg")
        demand_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        bottom_layout.addWidget(demand_label)

        bottom_layout.addStretch()

        # 根据状态显示不同按钮
        if status == 'pending':
            pickup_btn = QPushButton("📥 取货")
            pickup_btn.setStyleSheet(self.get_button_style('#3b82f6'))
            pickup_btn.clicked.connect(lambda: self.task_action.emit('pickup', self.task_id))
            bottom_layout.addWidget(pickup_btn)

        elif status == 'in_progress':
            nav_btn = QPushButton("🗺️ 导航")
            nav_btn.setStyleSheet(self.get_button_style('#3b82f6'))
            nav_btn.clicked.connect(lambda: self.task_action.emit('navigate', self.task_id))
            bottom_layout.addWidget(nav_btn)

            complete_btn = QPushButton("✅ 送达")
            complete_btn.setStyleSheet(self.get_button_style('#10b981'))
            complete_btn.clicked.connect(lambda: self.task_action.emit('complete', self.task_id))
            bottom_layout.addWidget(complete_btn)

            exception_btn = QPushButton("⚠️ 异常")
            exception_btn.setStyleSheet(self.get_button_style('#ef4444'))
            exception_btn.clicked.connect(lambda: self.task_action.emit('exception', self.task_id))
            bottom_layout.addWidget(exception_btn)

        layout.addLayout(bottom_layout)
        self.setLayout(layout)

    def get_button_style(self, color):
        return f"""
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {color}dd;
            }}
            QPushButton:pressed {{
                background: {color}99;
            }}
        """


# ====================== 异常上报对话框 ======================
class ExceptionDialog(QDialog):
    """异常上报对话框 - 方案A：白色主题"""
    def __init__(self, task_id, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.exception_type = None
        self.description = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("上报异常")
        self.resize(400, 350)
        self.setStyleSheet("""
            QDialog {
                background: #ffffff;
            }
            QLabel {
                color: #1e293b;
                font-size: 14px;
            }
            QComboBox, QTextEdit {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 10px;
                color: #1e293b;
                font-size: 14px;
            }
            QComboBox:focus, QTextEdit:focus {
                border: 1px solid #3b82f6;
            }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #1e293b;
                selection-background-color: #dbeafe;
                selection-color: #1e40af;
                border: 1px solid #e2e8f0;
                outline: none;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #64748b;
                margin-right: 6px;
            }
            QTextEdit {
                min-height: 100px;
            }
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2563eb;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 异常类型
        type_label = QLabel("异常类型：")
        type_label.setStyleSheet("font-weight: bold; color: #1e293b;")
        layout.addWidget(type_label)

        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "交通拥堵",
            "车辆故障",
            "客户不在",
            "地址错误",
            "货物损坏",
            "其他"
        ])
        self.type_combo.setMinimumHeight(45)
        layout.addWidget(self.type_combo)

        # 详细描述
        desc_label = QLabel("详细描述：")
        desc_label.setStyleSheet("font-weight: bold; color: #1e293b;")
        layout.addWidget(desc_label)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("请描述具体情况...")
        self.desc_edit.setMinimumHeight(100)
        layout.addWidget(self.desc_edit)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #e2e8f0;
                color: #64748b;
            }
            QPushButton:hover {
                background: #cbd5e1;
                color: #475569;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        submit_btn = QPushButton("提交上报")
        submit_btn.clicked.connect(self.accept)
        btn_layout.addWidget(submit_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def get_data(self):
        return self.type_combo.currentText(), self.desc_edit.toPlainText()


# ====================== 导航地图组件 ======================
class NavigationMap(QWidget):
    """导航地图组件 - 方案A：浅色UI"""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view, 1)

        self.current_destination = None
        self.show_empty_map()

    @staticmethod
    def _get_dc():
        """获取当前城市配送中心坐标"""
        try:
            from main import CITIES, current_city
            city = CITIES.get(current_city, CITIES['北京'])
            return city['dc_lng'], city['dc_lat'], city.get('dc_name', '配送中心')
        except Exception:
            return 116.397, 39.908, '配送中心'

    def show_empty_map(self):
        """显示空白地图（以当前城市配送中心为圆心）"""
        dc_lng, dc_lat, dc_name = self._get_dc()
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ margin: 0; padding: 0; background: #f0f4f8; }}
                #map {{ width: 100%; height: 100vh; }}
                .placeholder {{
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    color: #94a3b8;
                    font-size: 18px;
                    text-align: center;
                    font-family: "SimSun";
                    pointer-events: none;
                }}
                .dc-label {{
                    position: absolute;
                    bottom: 20px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: rgba(255,255,255,0.95);
                    padding: 8px 20px;
                    border-radius: 20px;
                    font-family: "SimSun";
                    font-size: 13px;
                    color: #1e40af;
                    box-shadow: 0 2px 12px rgba(0,0,0,0.12);
                    border: 1px solid #bfdbfe;
                    z-index: 100;
                }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <div class="placeholder" id="placeholder">
                🗺️<br>
                选择一个任务开始导航
            </div>
            <div class="dc-label">📍 {dc_name}（{dc_lng:.3f}, {dc_lat:.3f}）</div>
            <div id="map-error" style="display:none;position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#ef4444;font-size:16px;text-align:center;font-family:SimSun,sans-serif;"></div>
            <script>
                window._AMapSecurityConfig = {{
                    securityJsCode: '776a13f6acec470076eb03e867c7e84d'
                }};
            </script>
            <script src="https://webapi.amap.com/maps?v=2.0&key={AMAP_API_KEY}"
                onerror="document.getElementById('map').style.display='none';document.getElementById('placeholder').style.display='none';var e=document.getElementById('map-error');e.style.display='block';e.innerHTML='⚠️ 地图加载失败<br><span style=font-size:13px;color:#64748b>请检查网络连接</span>';">
            </script>
            <script>
                var map = new AMap.Map('map', {{
                    zoom: 12,
                    center: [{dc_lng}, {dc_lat}],
                    viewMode: '2D'
                }});

                // 配送中心标记
                new AMap.Marker({{
                    position: [{dc_lng}, {dc_lat}],
                    content: '<div style="background:#fbbf24;width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:10px;border:2px solid #1e40af;color:#1e40af;font-family:SimSun;">DC</div>',
                    offset: new AMap.Pixel(-14, -14),
                    map: map
                }});
            </script>
        </body>
        </html>
        """
        load_html_in_webview(self.web_view, html)

    def navigate_to(self, dest_lng, dest_lat, dest_name, driver_lng=None, driver_lat=None):
        """导航到目的地（driver_lng/lat 默认使用当前城市DC坐标）"""
        if driver_lng is None or driver_lat is None:
            dc_lng, dc_lat, _ = self._get_dc()
            driver_lng = driver_lng or dc_lng
            driver_lat = driver_lat or dc_lat
        self.current_destination = (dest_lng, dest_lat, dest_name)

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ margin: 0; padding: 0; }}
                #map {{ width: 100%; height: 100vh; }}
                .info {{
                    position: absolute;
                    top: 10px;
                    left: 10px;
                    background: rgba(255, 255, 255, 0.95);
                    padding: 15px;
                    border-radius: 10px;
                    color: #1e293b;
                    font-family: "SimSun";
                    border: 1px solid #e2e8f0;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                    z-index: 100;
                }}
                .info h3 {{ margin: 0 0 10px 0; color: #1e40af; }}
                .info p {{ margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <div id="map-error" style="display:none;position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#ef4444;font-size:16px;text-align:center;font-family:SimSun,sans-serif;"></div>
            <div class="info">
                <h3>🚛 导航中</h3>
                <p><b>目的地：</b>{dest_name}</p>
                <p><b>坐标：</b>{dest_lng:.4f}, {dest_lat:.4f}</p>
            </div>
            <script>
                window._AMapSecurityConfig = {{
                    securityJsCode: '776a13f6acec470076eb03e867c7e84d'
                }};
            </script>
            <script src="https://webapi.amap.com/maps?v=2.0&key={AMAP_API_KEY}"
                onerror="document.getElementById('map').style.display='none';var e=document.getElementById('map-error');if(e){{e.style.display='block';e.innerHTML='⚠️ 地图加载失败';}}">
            </script>
            <script>
                var map = new AMap.Map('map', {{
                    zoom: 13,
                    center: [{dest_lng}, {dest_lat}],
                    viewMode: '2D'
                }});

                // 起点标记（驾驶员位置）
                var startMarker = new AMap.Marker({{
                    position: [{driver_lng}, {driver_lat}],
                    content: '<div style="background:#10b981;width:20px;height:20px;border-radius:50%;border:3px solid white;"></div>',
                    offset: new AMap.Pixel(-10, -10)
                }});
                map.add(startMarker);

                // 终点标记
                var endMarker = new AMap.Marker({{
                    position: [{dest_lng}, {dest_lat}],
                    content: '<div style="background:#ef4444;width:24px;height:24px;border-radius:4px;border:3px solid white;display:flex;align-items:center;justify-content:center;font-size:14px;">📍</div>',
                    offset: new AMap.Pixel(-12, -12)
                }});
                map.add(endMarker);

                // 使用 AMap.Driving 展示真实道路导航路径
                AMap.plugin('AMap.Driving', function() {{
                    var driving = new AMap.Driving({{
                        map: map,
                        policy: AMap.DrivingPolicy.LEAST_DISTANCE,
                        hideMarkers: true,
                        autoFitView: false
                    }});
                    driving.search(
                        new AMap.LngLat({driver_lng}, {driver_lat}),
                        new AMap.LngLat({dest_lng}, {dest_lat}),
                        {{}},
                        function(status, result) {{
                            if (status === 'complete' && result.routes && result.routes.length) {{
                                var pathCoords = [];
                                result.routes[0].steps.forEach(function(step) {{
                                    pathCoords = pathCoords.concat(step.path);
                                }});
                                var roadLine = new AMap.Polyline({{
                                    path: pathCoords,
                                    strokeColor: '#3b82f6',
                                    strokeWeight: 6,
                                    strokeOpacity: 0.9,
                                    lineJoin: 'round',
                                    lineCap: 'round',
                                    showDir: true
                                }});
                                map.add(roadLine);
                                map.setFitView(null, false, [80, 80, 80, 80]);
                            }}
                        }}
                    );
                }});

                // 自动调整视野
                map.setFitView(null, false, [80, 80, 80, 80]);
            </script>
        </body>
        </html>
        """
        load_html_in_webview(self.web_view, html)

    def show_driver_marker(self, driver_lng, driver_lat):
        """在空白地图上显示驾驶员位置标记（向后兼容）"""
        dc_lng, dc_lat, dc_name = self._get_dc()
        self.show_driver_at_dc(driver_lng, driver_lat, dc_lng, dc_lat, dc_name)

    def show_driver_at_dc(self, driver_lng, driver_lat, dc_lng, dc_lat, dc_name):
        """在地图上同时显示配送中心和驾驶员位置"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ margin: 0; padding: 0; }}
                #map {{ width: 100%; height: 100vh; }}
                .gps-info {{
                    position: absolute;
                    bottom: 20px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: rgba(255,255,255,0.95);
                    padding: 10px 20px;
                    border-radius: 20px;
                    font-family: "SimSun";
                    font-size: 13px;
                    color: #1e293b;
                    box-shadow: 0 2px 12px rgba(0,0,0,0.15);
                    border: 1px solid #e2e8f0;
                    z-index: 100;
                    white-space: nowrap;
                }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <div class="gps-info">📍 {dc_name} &nbsp;|&nbsp; 驾驶员：{driver_lng:.4f}, {driver_lat:.4f}</div>
            <script>
                window._AMapSecurityConfig = {{
                    securityJsCode: '776a13f6acec470076eb03e867c7e84d'
                }};
            </script>
            <script src="https://webapi.amap.com/maps?v=2.0&key={AMAP_API_KEY}"></script>
            <script>
                var map = new AMap.Map('map', {{
                    zoom: 14,
                    center: [{dc_lng}, {dc_lat}],
                    viewMode: '2D'
                }});

                // 配送中心标记（金色）
                new AMap.Marker({{
                    position: [{dc_lng}, {dc_lat}],
                    content: '<div style="background:#fbbf24;width:30px;height:30px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:11px;border:2px solid #1e40af;color:#1e40af;font-family:SimSun;">DC</div>',
                    offset: new AMap.Pixel(-15, -15),
                    map: map
                }});

                // 驾驶员位置标记（蓝色，带精度圈）
                new AMap.Marker({{
                    position: [{driver_lng}, {driver_lat}],
                    content: '<div style="position:relative;">' +
                        '<div style="background:#3b82f6;width:18px;height:18px;border-radius:50%;border:3px solid white;box-shadow:0 2px 8px rgba(59,130,246,0.6);"></div>' +
                        '<div style="position:absolute;top:-20px;left:50%;transform:translateX(-50%);background:#3b82f6;color:white;padding:1px 6px;border-radius:4px;font-size:10px;white-space:nowrap;font-family:SimSun;">🚛 驾驶员</div>' +
                        '</div>',
                    offset: new AMap.Pixel(-9, -9),
                    map: map
                }});

                // 精度圈
                new AMap.Circle({{
                    center: [{driver_lng}, {driver_lat}],
                    radius: 50,
                    strokeColor: '#3b82f6',
                    strokeWeight: 1,
                    strokeOpacity: 0.5,
                    fillColor: '#3b82f6',
                    fillOpacity: 0.12,
                    map: map
                }});

                // 自动调整视野以包含两个标记
                map.setFitView(null, false, [60, 60, 60, 60]);
            </script>
        </body>
        </html>
        """
        load_html_in_webview(self.web_view, html)


# ====================== 驾驶员工作台主界面 ======================
class DriverWorkstation(QMainWindow):
    """驾驶员工作台 - 方案A：简洁卡片风（浅色/蓝色主题）"""
    def __init__(self, driver_info):
        super().__init__()
        self.driver_info = driver_info
        self.driver_id = driver_info['driver_id']
        self.current_task_id = None

        self.setWindowTitle(f"🚛 驾驶员工作台 - {driver_info['name']}师傅")
        self.setGeometry(100, 100, 1200, 800)

        self.init_ui()
        self.apply_theme()
        self.load_tasks()

        # 更新驾驶员状态为在线
        update_driver_status(self.driver_id, 'online')

        # 状态刷新定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_tasks)
        self.timer.start(30000)  # 30秒刷新一次

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # ==================== 左侧：任务面板 ====================
        left_panel = QFrame()
        left_panel.setFixedWidth(400)
        left_panel.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border-radius: 16px;
                border: 1px solid #e2e8f0;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(15, 15, 15, 15)
        left_layout.setSpacing(12)

        # 驾驶员信息卡 - 蓝色渐变条
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3b82f6, stop:1 #1d4ed8);
                border-radius: 12px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(15, 12, 15, 12)

        name_label = QLabel(f"👨‍✈️ {self.driver_info['name']}")
        name_label.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: bold; border: none;")
        info_layout.addWidget(name_label)

        plate = self.driver_info.get('license_plate', '未绑定')
        vehicle = self.driver_info.get('vehicle_type', '未知')
        detail_label = QLabel(f"🚐 {plate} | {vehicle}")
        detail_label.setStyleSheet("color: #bfdbfe; font-size: 13px; border: none;")
        info_layout.addWidget(detail_label)

        shift = self.driver_info.get('shift', '未知')
        shift_label = QLabel(f"🕐 {shift}")
        shift_label.setStyleSheet("color: #93c5fd; font-size: 12px; border: none;")
        info_layout.addWidget(shift_label)

        left_layout.addWidget(info_frame)

        # ── GPS 定位状态栏 ──────────────────────────────────
        gps_frame = QFrame()
        gps_frame.setStyleSheet("""
            QFrame {
                background: #eff6ff;
                border: 1px solid #bfdbfe;
                border-radius: 10px;
            }
        """)
        gps_layout = QHBoxLayout(gps_frame)
        gps_layout.setContentsMargins(12, 8, 12, 8)

        self.gps_status_dot = QLabel("●")
        self.gps_status_dot.setStyleSheet("color: #94a3b8; font-size: 16px; border: none;")
        gps_layout.addWidget(self.gps_status_dot)

        self.gps_info_label = QLabel("GPS 未定位")
        self.gps_info_label.setStyleSheet("color: #64748b; font-size: 12px; border: none;")
        gps_layout.addWidget(self.gps_info_label, 1)

        self.gps_btn = QPushButton("📍 获取定位")
        self.gps_btn.setFixedHeight(32)
        self.gps_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #2563eb; }
            QPushButton:pressed { background: #1d4ed8; }
        """)
        self.gps_btn.clicked.connect(self._do_gps_locate)
        gps_layout.addWidget(self.gps_btn)

        left_layout.addWidget(gps_frame)

        # GPS 模拟定时器（每 8 秒微调一次位置）
        self.gps_timer = QTimer()
        self.gps_timer.timeout.connect(self._tick_gps)
        self.driver_lng = None
        self.driver_lat = None

        # 任务标题
        task_header = QHBoxLayout()
        task_title = QLabel("📋 我的任务")
        task_title.setStyleSheet("color: #1e293b; font-size: 16px; font-weight: bold;")
        task_header.addWidget(task_title)

        task_header.addStretch()

        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(36, 36)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #e2e8f0;
                color: #475569;
                border-radius: 18px;
            }
            QPushButton:hover {
                background: #3b82f6;
                color: white;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_tasks)
        task_header.addWidget(refresh_btn)

        left_layout.addLayout(task_header)

        # 任务统计
        self.stats_label = QLabel("待取货: 0 | 配送中: 0 | 已完成: 0")
        self.stats_label.setStyleSheet("color: #64748b; font-size: 12px;")
        left_layout.addWidget(self.stats_label)

        # 任务列表（滚动区域）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #f1f5f9;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
        """)

        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(8)
        self.task_layout.addStretch()

        scroll.setWidget(self.task_container)
        left_layout.addWidget(scroll, 1)

        # 底部按钮
        bottom_btns = QHBoxLayout()

        status_btn = QPushButton("🔴 下线")
        status_btn.setMinimumHeight(50)
        status_btn.setStyleSheet("""
            QPushButton {
                background: #fee2e2;
                color: #dc2626;
                border: 1px solid #fca5a5;
                border-radius: 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #fecaca;
            }
        """)
        status_btn.clicked.connect(self.toggle_status)
        bottom_btns.addWidget(status_btn)

        logout_btn = QPushButton("🚪 交班")
        logout_btn.setMinimumHeight(50)
        logout_btn.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                color: #475569;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #e2e8f0;
            }
        """)
        logout_btn.clicked.connect(self.close)
        bottom_btns.addWidget(logout_btn)

        left_layout.addLayout(bottom_btns)
        main_layout.addWidget(left_panel)

        # ==================== 右侧：地图面板 ====================
        right_panel = QFrame()
        right_panel.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border-radius: 16px;
                border: 1px solid #e2e8f0;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)

        # 地图标题
        map_header = QLabel("🗺️ 配送导航")
        map_header.setStyleSheet("color: #1e293b; font-size: 16px; font-weight: bold; padding: 5px;")
        right_layout.addWidget(map_header)

        # 地图组件
        self.nav_map = NavigationMap()
        right_layout.addWidget(self.nav_map, 1)

        main_layout.addWidget(right_panel, 1)

    def apply_theme(self):
        """应用方案A浅色蓝色主题"""
        self.setStyleSheet("""
            QMainWindow {
                background: #f0f4f8;
            }
            QWidget {
                background: transparent;
                color: #1e293b;
                font-family: "SimSun";
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
                padding: 10px 20px;
                color: white;
                font-weight: bold;
            }
            QMessageBox QPushButton:hover {
                background: #2563eb;
            }
        """)

    def load_tasks(self):
        """加载任务列表"""
        # 清空现有任务
        while self.task_layout.count() > 1:
            item = self.task_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 从数据库获取任务
        tasks = get_driver_tasks(self.driver_id)

        # 统计
        pending = sum(1 for t in tasks if t['status'] == 'pending')
        in_progress = sum(1 for t in tasks if t['status'] == 'in_progress')
        completed = sum(1 for t in tasks if t['status'] == 'completed')
        self.stats_label.setText(f"待取货: {pending} | 配送中: {in_progress} | 已完成: {completed}")

        if not tasks:
            # 显示空状态和演示按钮
            empty_widget = QWidget()
            empty_widget.setStyleSheet("background: transparent;")
            empty_layout = QVBoxLayout(empty_widget)
            empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            empty_label = QLabel("📭\n暂无任务")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet("""
                color: #64748b;
                font-size: 16px;
                padding: 20px;
            """)
            empty_layout.addWidget(empty_label)

            hint_label = QLabel("请联系调度中心分配任务，或点击下方按钮生成演示数据")
            hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint_label.setStyleSheet("""
                color: #94a3b8;
                font-size: 12px;
                padding: 10px;
            """)
            hint_label.setWordWrap(True)
            empty_layout.addWidget(hint_label)

            demo_btn = QPushButton("🎲 生成演示任务")
            demo_btn.setMinimumHeight(50)
            demo_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #1d4ed8);
                    color: white;
                    border: none;
                    border-radius: 12px;
                    padding: 14px;
                    font-size: 14px;
                    font-weight: bold;
                    margin: 20px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #1e40af);
                }
            """)
            demo_btn.clicked.connect(self.generate_demo_tasks)
            empty_layout.addWidget(demo_btn)

            self.task_layout.insertWidget(0, empty_widget)
            return

        # 创建任务卡片
        for task in tasks:
            card = TaskCard(task)
            card.task_action.connect(self.handle_task_action)
            self.task_layout.insertWidget(self.task_layout.count() - 1, card)

    def generate_demo_tasks(self):
        """生成演示任务"""
        from database.db_manager import generate_random_orders, batch_assign_tasks

        orders = generate_random_orders(5)
        batch_assign_tasks(self.driver_id, orders)
        self.refresh_tasks()
        QMessageBox.information(self, "演示数据", "已生成5个演示任务！\n现在可以体验取货、导航、送达等功能。")

    def handle_task_action(self, action, task_id):
        """处理任务操作"""
        tasks = get_driver_tasks(self.driver_id)
        task = next((t for t in tasks if t['id'] == task_id), None)
        if not task:
            return

        if action == 'pickup':
            # 取货
            reply = QMessageBox.question(
                self, "确认取货",
                f"确认已取货？\n\n客户：{task['customer_name']}\n重量：{task['demand']}kg",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                update_task_status(task_id, 'in_progress')
                # 记录状态变更日志
                log_order_status_change(
                    order_id=task.get('order_id', ''),
                    task_id=task_id,
                    from_status='assigned',
                    to_status='picking_up',
                    operator=self.driver_id,
                    note='驾驶员确认取货'
                )
                self.current_task_id = task_id
                self.refresh_tasks()
                QMessageBox.information(self, "成功", "已取货，请开始配送")

        elif action == 'navigate':
            # 导航
            if task['lng'] and task['lat']:
                # 使用实时GPS位置（若有），否则使用默认DC坐标
                drv_lng = self.driver_lng if self.driver_lng else 116.397
                drv_lat = self.driver_lat if self.driver_lat else 39.908
                self.nav_map.navigate_to(
                    task['lng'], task['lat'],
                    f"{task['customer_name']} - {task['address']}",
                    driver_lng=drv_lng,
                    driver_lat=drv_lat
                )
                # 更新驾驶员位置
                update_driver_location(self.driver_id, task['lng'], task['lat'])
                # 记录状态变更
                log_order_status_change(
                    order_id=task.get('order_id', ''),
                    task_id=task_id,
                    from_status='picking_up',
                    to_status='delivering',
                    operator=self.driver_id,
                    note=f'开始导航至: {task["address"]}'
                )
            else:
                QMessageBox.warning(self, "提示", "该任务没有坐标信息")

        elif action == 'complete':
            # 送达确认
            reply = QMessageBox.question(
                self, "确认送达",
                f"确认已送达？\n\n客户：{task['customer_name']}\n地址：{task['address']}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                update_task_status(task_id, 'completed', note="已送达")
                # 记录状态变更日志
                log_order_status_change(
                    order_id=task.get('order_id', ''),
                    task_id=task_id,
                    from_status='delivering',
                    to_status='completed',
                    operator=self.driver_id,
                    note='驾驶员确认送达'
                )
                self.refresh_tasks()
                QMessageBox.information(self, "完成", "配送完成！辛苦了")

        elif action == 'exception':
            # 异常上报
            dialog = ExceptionDialog(task_id, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                exc_type, desc = dialog.get_data()
                report_exception(self.driver_id, task_id, exc_type, desc)
                update_task_status(task_id, 'exception', note=f"{exc_type}: {desc}")
                # 记录状态变更日志
                log_order_status_change(
                    order_id=task.get('order_id', ''),
                    task_id=task_id,
                    from_status='delivering',
                    to_status='exception',
                    operator=self.driver_id,
                    note=f'异常上报: {exc_type} - {desc}'
                )
                self.refresh_tasks()
                QMessageBox.information(self, "已上报", "异常已上报，请等待处理")

    def refresh_tasks(self):
        """刷新任务列表"""
        self.load_tasks()

    def toggle_status(self):
        """切换在线/离线状态"""
        current_status = self.driver_info.get('status', 'offline')
        if current_status == 'online':
            update_driver_status(self.driver_id, 'offline')
            self.driver_info['status'] = 'offline'
            QMessageBox.information(self, "状态", "已切换为离线状态")
        else:
            update_driver_status(self.driver_id, 'online')
            self.driver_info['status'] = 'online'
            QMessageBox.information(self, "状态", "已切换为在线状态")

    def closeEvent(self, event):
        """关闭时更新状态"""
        if self.gps_timer.isActive():
            self.gps_timer.stop()
        update_driver_status(self.driver_id, 'offline')
        event.accept()

    # ── GPS 定位方法 ─────────────────────────────────────
    def _do_gps_locate(self):
        """触发 GPS 定位：将驾驶员定位到当前城市配送中心"""
        import random
        try:
            from main import CITIES, current_city
            city = CITIES.get(current_city, CITIES['北京'])
            dc_lng, dc_lat = city['dc_lng'], city['dc_lat']
            dc_name = city.get('dc_name', '配送中心')
        except Exception:
            dc_lng, dc_lat = 116.397, 39.908
            dc_name = '配送中心'

        # 驾驶员位于配送中心附近（约 200m 范围内随机偏移）
        self.driver_lng = dc_lng + random.uniform(-0.002, 0.002)
        self.driver_lat = dc_lat + random.uniform(-0.0015, 0.0015)

        # 更新 UI
        self.gps_status_dot.setStyleSheet("color: #10b981; font-size: 16px; border: none;")
        self._update_gps_label()

        # 写入数据库
        update_driver_location(self.driver_id, self.driver_lng, self.driver_lat)

        # 启动 GPS 持续更新
        if not self.gps_timer.isActive():
            self.gps_timer.start(8000)

        # 在导航地图上显示驾驶员位置 + 配送中心标记
        if self.nav_map.current_destination:
            dest_lng, dest_lat, dest_name = self.nav_map.current_destination
            self.nav_map.navigate_to(dest_lng, dest_lat, dest_name,
                                     self.driver_lng, self.driver_lat)
        else:
            self.nav_map.show_driver_at_dc(self.driver_lng, self.driver_lat,
                                           dc_lng, dc_lat, dc_name)

        QMessageBox.information(self, "GPS 定位成功",
            f"已定位到：{dc_name}\n\n"
            f"配送中心坐标：{dc_lng:.5f}, {dc_lat:.5f}\n"
            f"驾驶员位置：{self.driver_lng:.5f}, {self.driver_lat:.5f}\n"
            f"精度：±{random.randint(5, 20)}m")

    def _tick_gps(self):
        """模拟 GPS 持续漂移（每次约 50-150m 随机移动）"""
        import random
        if self.driver_lng is None or self.driver_lat is None:
            return
        # 随机小步移动
        self.driver_lng += random.uniform(-0.0008, 0.0008)
        self.driver_lat += random.uniform(-0.0006, 0.0006)
        update_driver_location(self.driver_id, self.driver_lng, self.driver_lat)
        self._update_gps_label()

    def _update_gps_label(self):
        if self.driver_lng is not None:
            self.gps_info_label.setText(
                f"已定位  {self.driver_lng:.4f}, {self.driver_lat:.4f}")


# ====================== 测试入口 ======================
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # 模拟驾驶员信息
    test_driver = {
        'driver_id': 'D001',
        'name': '张师傅',
        'license_plate': '京A12345',
        'vehicle_type': '中型货车',
        'status': 'online',
        'shift': '早班 (6:00-14:00)'
    }

    window = DriverWorkstation(test_driver)
    window.show()
    sys.exit(app.exec())
