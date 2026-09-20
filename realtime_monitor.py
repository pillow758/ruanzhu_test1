"""
实时监控模块 - 显示所有在线驾驶员位置及模拟配送动画
"""
import json
import math
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QFrame, QScrollArea, QPushButton, QSizePolicy
)
from PyQt6.QtCore import QTimer, Qt, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView

from database import db_manager

AMAP_API_KEY = "ddbc01b09151f242d386549e5f472f79"
AMAP_SECURITY_CODE = "776a13f6acec470076eb03e867c7e84d"


def _get_dc():
    """获取当前城市的配送中心坐标"""
    try:
        from main import CITIES, current_city
        city = CITIES.get(current_city, CITIES['北京'])
        return city['dc_lng'], city['dc_lat']
    except Exception:
        return 116.397, 39.908  # 北京默认

STATUS_MAP = {
    'online':   ('🟢 在线',  '#10b981'),
    'offline':  ('⚪ 离线',  '#6b7280'),
    'delivering': ('🔵 配送中', '#3b82f6'),
    'rest':     ('🟡 休息',  '#f59e0b'),
}


class RealtimeMonitorWidget(QWidget):
    """实时监控主组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.driver_positions = {}   # driver_id → {lng, lat}
        self.driver_targets = {}     # driver_id → {lng, lat}
        self.driver_info_cache = {}
        self._init_ui()
        self._load_data()
        self._start_simulation()

    # ------------------------------------------------------------------ UI
    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 左侧地图
        self.web_view = QWebEngineView()
        self.web_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.web_view, 3)

        # 右侧面板
        right = QFrame()
        right.setFixedWidth(280)
        right.setStyleSheet("background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)

        # 标题
        title = QLabel("📡 实时监控")
        title.setStyleSheet("color:#1e40af;font-size:16px;font-weight:bold;")
        right_layout.addWidget(title)

        # 在线统计
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color:#64748b;font-size:12px;")
        right_layout.addWidget(self.stats_label)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color:#e2e8f0;")
        right_layout.addWidget(line)

        # 驾驶员滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width:6px; background:#f1f5f9; border-radius:3px; }
            QScrollBar::handle:vertical { background:#cbd5e1; border-radius:3px; }
        """)
        self.driver_container = QWidget()
        self.driver_container_layout = QVBoxLayout(self.driver_container)
        self.driver_container_layout.setContentsMargins(0, 0, 0, 0)
        self.driver_container_layout.setSpacing(6)
        self.driver_container_layout.addStretch()
        scroll.setWidget(self.driver_container)
        right_layout.addWidget(scroll, 1)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新数据")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background:#3b82f6; color:white; border:none;
                border-radius:6px; padding:8px; font:bold 12px SimSun;
            }
            QPushButton:hover { background:#2563eb; }
        """)
        refresh_btn.clicked.connect(self._load_data)
        right_layout.addWidget(refresh_btn)

        layout.addWidget(right, 1)

        # 模拟定时器（每2秒）
        self.sim_timer = QTimer(self)
        self.sim_timer.timeout.connect(self._tick_simulation)

    # ---------------------------------------------------------------- Data
    def _load_data(self):
        """从数据库加载驾驶员信息"""
        drivers = db_manager.get_all_drivers_with_info()
        self.driver_info_cache = {d['driver_id']: d for d in drivers}

        online_count = sum(1 for d in drivers if d['status'] != 'offline')

        for d in drivers:
            did = d['driver_id']
            # 初始化位置：有位置用实际位置，否则用DC附近随机偏移
            if d['lng'] and d['lat']:
                self.driver_positions[did] = {'lng': d['lng'], 'lat': d['lat']}
            else:
                import random
                dc_lng, dc_lat = _get_dc()
                self.driver_positions[did] = {
                    'lng': dc_lng + random.uniform(-0.03, 0.03),
                    'lat': dc_lat + random.uniform(-0.02, 0.02)
                }

            # 为在线驾驶员设置目标位置（有任务则向目的地移动，否则随机漂移）
            if d['status'] != 'offline':
                self._assign_random_target(did)

        self.stats_label.setText(
            f"在线 {online_count} 人 · 共 {len(drivers)} 名驾驶员"
        )

        self._rebuild_driver_cards(drivers)
        self._update_map()

    def _assign_random_target(self, driver_id):
        """为驾驶员分配一个随机目标位置（模拟城区目的地）"""
        import random
        dc_lng, dc_lat = _get_dc()
        # 当前城市城区范围
        target_lng = dc_lng + random.uniform(-0.08, 0.08)
        target_lat = dc_lat + random.uniform(-0.06, 0.06)
        self.driver_targets[driver_id] = {'lng': target_lng, 'lat': target_lat}

    # ------------------------------------------------------------ Simulation
    def _start_simulation(self):
        self.sim_timer.start(2000)

    def _tick_simulation(self):
        """每次定时器触发，移动驾驶员向目标位置靠近"""
        moved = False
        for did, pos in list(self.driver_positions.items()):
            info = self.driver_info_cache.get(did, {})
            if info.get('status') == 'offline':
                continue

            target = self.driver_targets.get(did)
            if not target:
                self._assign_random_target(did)
                target = self.driver_targets[did]

            # 每次移动约 0.002 度（约 200 米）
            step = 0.002
            dlng = target['lng'] - pos['lng']
            dlat = target['lat'] - pos['lat']
            dist = math.sqrt(dlng**2 + dlat**2)

            if dist < step:
                # 到达目标，分配新目标
                pos['lng'] = target['lng']
                pos['lat'] = target['lat']
                self._assign_random_target(did)
                # 更新数据库
                db_manager.update_driver_location(did, pos['lng'], pos['lat'])
            else:
                ratio = step / dist
                pos['lng'] += dlng * ratio
                pos['lat'] += dlat * ratio
                db_manager.update_driver_location(did, pos['lng'], pos['lat'])

            moved = True

        if moved:
            self._update_map()

    # --------------------------------------------------------------- Sidebar
    def _rebuild_driver_cards(self, drivers):
        """重建右侧驾驶员卡片列表"""
        # 清空现有卡片
        while self.driver_container_layout.count() > 1:
            item = self.driver_container_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for d in drivers:
            card = self._make_driver_card(d)
            self.driver_container_layout.insertWidget(
                self.driver_container_layout.count() - 1, card
            )

    def _make_driver_card(self, d):
        """创建单个驾驶员卡片"""
        did = d['driver_id']
        status_text, status_color = STATUS_MAP.get(d['status'], ('未知', '#666'))

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: #ffffff;
                border-radius: 8px;
                border: 1px solid #e2e8f0;
                border-left: 4px solid {status_color};
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(4)

        # 第一行：姓名 + 状态
        row1 = QHBoxLayout()
        name_lbl = QLabel(f"🚛 {d['name']}")
        name_lbl.setStyleSheet(f"color:#1e293b;font:bold 13px SimSun;border:none;")
        row1.addWidget(name_lbl)
        row1.addStretch()
        status_lbl = QLabel(status_text)
        status_lbl.setStyleSheet(f"color:{status_color};font:11px SimSun;border:none;")
        row1.addWidget(status_lbl)
        card_layout.addLayout(row1)

        # 第二行：车牌 + 班次
        row2 = QLabel(f"🚗 {d['license_plate']}  ·  {d['shift']}")
        row2.setStyleSheet("color:#64748b;font:11px SimSun;border:none;")
        card_layout.addWidget(row2)

        # 第三行：统计
        stats_row = QLabel(
            f"✅ 完成 {d['completed_count']} 单"
            f"   📦 待配送 {d['pending_count']} 单"
        )
        stats_row.setStyleSheet("color:#64748b;font:11px SimSun;border:none;")
        card_layout.addWidget(stats_row)

        return card

    # ----------------------------------------------------------------- Map
    def _update_map(self):
        """更新地图HTML（所有驾驶员标记 + DC标记）"""
        drivers_data = []
        for d in self.driver_info_cache.values():
            did = d['driver_id']
            pos = self.driver_positions.get(did, {'lng': _get_dc()[0], 'lat': _get_dc()[1]})
            status_text, status_color = STATUS_MAP.get(d['status'], ('未知', '#666'))
            drivers_data.append({
                'id': did,
                'name': d['name'],
                'plate': d['license_plate'],
                'status': status_text,
                'color': status_color,
                'lng': pos['lng'],
                'lat': pos['lat'],
                'pending': d['pending_count'],
                'completed': d['completed_count'],
                'online': d['status'] != 'offline'
            })

        # 计算地图中心（所有驾驶员位置的平均值）
        online_drivers = [d for d in drivers_data if d['online']]
        if online_drivers:
            center_lng = sum(d['lng'] for d in online_drivers) / len(online_drivers)
            center_lat = sum(d['lat'] for d in online_drivers) / len(online_drivers)
        else:
            center_lng, center_lat = _get_dc()

        html = self._build_map_html(drivers_data, center_lng, center_lat)
        self.web_view.setHtml(html, QUrl("https://localhost"))

    def _build_map_html(self, drivers_data, center_lng, center_lat):
        dc_lng, dc_lat = _get_dc()
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                * {{ margin:0; padding:0; box-sizing:border-box; }}
                body {{ background:#f0f4f8; }}
                #map {{ width:100vw; height:100vh; }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <script>
                window._AMapSecurityConfig = {{
                    securityJsCode: '{AMAP_SECURITY_CODE}'
                }};
            </script>
            <script src="https://webapi.amap.com/maps?v=2.0&key={AMAP_API_KEY}"
                onerror="document.getElementById('map').innerHTML=
                    '<div style=&quot;display:flex;align-items:center;justify-content:center;height:100vh;color:#e74c3c;font-size:16px;font-family:SimSun;&quot;>⚠️ 地图加载失败，请检查网络</div>';">
            </script>
            <script>
                var map = new AMap.Map('map', {{
                    zoom: 11,
                    center: [{center_lng}, {center_lat}],
                    viewMode: '2D'
                }});

                // 配送中心标记
                new AMap.Marker({{
                    position: [{dc_lng}, {dc_lat}],
                    content: '<div style="background:#FFD700;width:28px;height:28px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:11px;border:2px solid #333;color:#333;">DC</div>',
                    offset: new AMap.Pixel(-14, -14),
                    map: map
                }});

                // 驾驶员标记
                var driversData = {json.dumps(drivers_data)};
                driversData.forEach(function(d) {{
                    if (!d.online) return;
                    var color = d.color === '#10b981' ? '#10b981' :
                                d.color === '#3b82f6' ? '#3b82f6' :
                                d.color === '#f59e0b' ? '#f59e0b' : '#6b7280';
                    var html = '<div style="position:relative;">' +
                        '<div style="background:' + color + ';width:22px;height:22px;border-radius:50%;border:3px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.4);"></div>' +
                        '<div style="position:absolute;top:-22px;left:50%;transform:translateX(-50%);white-space:nowrap;background:rgba(0,0,0,0.75);color:white;padding:2px 6px;border-radius:4px;font-size:11px;font-family:SimSun;">' + d.name + '</div>' +
                        '</div>';
                    var marker = new AMap.Marker({{
                        position: [d.lng, d.lat],
                        content: html,
                        offset: new AMap.Pixel(-11, -11),
                        map: map
                    }});

                    var infoHtml = '<div style="font-family:SimSun;padding:4px;min-width:160px;">' +
                        '<div style="font-weight:bold;font-size:14px;color:#333;">🚛 ' + d.name + '</div>' +
                        '<div style="color:#666;font-size:12px;margin:3px 0;">车牌：' + d.plate + '</div>' +
                        '<div style="color:#666;font-size:12px;">状态：' + d.status + '</div>' +
                        '<div style="color:#666;font-size:12px;">已完成：' + d.completed + ' 单</div>' +
                        '<div style="color:#666;font-size:12px;">待配送：' + d.pending + ' 单</div>' +
                        '</div>';
                    var infoWindow = new AMap.InfoWindow({{
                        content: infoHtml,
                        offset: new AMap.Pixel(0, -24)
                    }});
                    marker.on('click', function() {{
                        infoWindow.open(map, marker.getPosition());
                    }});
                }});
            </script>
        </body>
        </html>
        """

    def stop_simulation(self):
        self.sim_timer.stop()
