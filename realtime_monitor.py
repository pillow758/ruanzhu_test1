"""
实时监控模块 - 只显示司机设备上报的位置
"""
import json
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QFrame, QScrollArea, QPushButton, QSizePolicy
)
from PyQt6.QtCore import QTimer, Qt, QUrl
from web_view import EmbeddedWebView as QWebEngineView

from database import db_manager
from gps_store import get_positions, is_fresh, position_text

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
        self._map_dc = None
        self.driver_info_cache = {}
        self._init_ui()
        self._load_data()
        self.refresh_timer.start(3000)

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

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._load_data)
        self.web_view.loadFinished.connect(lambda ok: self._push_positions() if ok else None)

    # ---------------------------------------------------------------- Data
    def _load_data(self):
        """从数据库加载驾驶员信息"""
        drivers = db_manager.get_all_drivers_with_info()
        self.driver_info_cache = {d['driver_id']: d for d in drivers}

        positions = get_positions()
        self.driver_positions = {did: p for did, p in positions.items() if did in self.driver_info_cache}
        fresh_count = sum(is_fresh(p) for p in self.driver_positions.values())
        self.stats_label.setText(
            f"实时上报 {fresh_count} 辆 · 共 {len(drivers)} 名驾驶员\n"
            f"超时 {len(self.driver_positions)-fresh_count} 辆 · 未上报 {len(drivers)-len(self.driver_positions)} 辆"
        )
        self._rebuild_driver_cards(drivers)
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

        location = QLabel(position_text(self.driver_positions.get(d['driver_id'])))
        location.setWordWrap(True)
        location.setStyleSheet("color:#64748b;font:11px SimSun;border:none;")
        card_layout.addWidget(location)
        return card

    # ----------------------------------------------------------------- Map
    def _map_data(self):
        result = []
        for did, position in self.driver_positions.items():
            driver = self.driver_info_cache[did]
            result.append({
                'id': did, 'name': driver['name'], 'plate': driver['license_plate'],
                'lng': position['lng'], 'lat': position['lat'],
                'accuracy': position['accuracy'], 'fresh': is_fresh(position),
                'location': position_text(position),
                'status': STATUS_MAP.get(driver['status'], ('未知', '#666'))[0],
            })
        return result

    def _push_positions(self):
        data = json.dumps(self._map_data(), ensure_ascii=False)
        self.web_view.page().runJavaScript(
            "if (typeof updateVehiclePositions === 'function') updateVehiclePositions(" + data + ");")

    def _update_map(self):
        dc = _get_dc()
        if self._map_dc != dc:
            self._map_dc = dc
            self.web_view.setHtml(self._build_map_html(dc), QUrl("https://localhost"))
        else:
            self._push_positions()

    def _build_map_html(self, dc):
        dc_lng, dc_lat = dc
        return f"""
        <!doctype html><html><meta charset="utf-8">
        <style>body{{margin:0;font:14px sans-serif}}#map{{height:100vh}}
        #notice{{position:absolute;top:12px;left:12px;z-index:100;background:white;padding:10px;border-radius:8px;color:#475569}}</style>
        <div id="map"></div><div id="notice">等待司机设备上报 · 灰色为超时后的最后位置</div>
        <script>window._AMapSecurityConfig={{securityJsCode:'{AMAP_SECURITY_CODE}'}};</script>
        <script src="https://webapi.amap.com/maps?v=2.0&key={AMAP_API_KEY}"
        onerror="document.getElementById('notice').textContent='地图加载失败，请检查网络和高德配置；车辆上报状态可查看右侧列表'"></script>
        <script>
        if (typeof AMap !== 'undefined') {{
            var map=new AMap.Map('map',{{zoom:12,center:[{dc_lng},{dc_lat}],viewMode:'2D'}});
            new AMap.Marker({{position:[{dc_lng},{dc_lat}],title:'配送中心',map:map}});
            var markers={{}}, circles={{}}, infos={{}};
            window.updateVehiclePositions=function(data){{
                var ids=new Set(data.map(d=>d.id)), added=false;
                Object.keys(markers).forEach(id=>{{if(!ids.has(id)){{
                    map.remove([markers[id],circles[id]]);infos[id].close();
                    delete markers[id];delete circles[id];delete infos[id];
                }}}});
                data.forEach(d=>{{
                    var color=d.fresh?'#2563eb':'#94a3b8';
                    var content=document.createElement('div');
                    content.style.cssText='background:'+color+';color:white;padding:5px 9px;border:2px solid white;border-radius:18px;white-space:nowrap;box-shadow:0 2px 6px #0003';
                    content.textContent='🚚 '+d.name;
                    if(!markers[d.id]){{
                        added=true;
                        markers[d.id]=new AMap.Marker({{position:[d.lng,d.lat],map:map,offset:new AMap.Pixel(-20,-12)}});
                        circles[d.id]=new AMap.Circle({{center:[d.lng,d.lat],map:map,strokeWeight:1,fillOpacity:.08}});
                        infos[d.id]=new AMap.InfoWindow();
                        markers[d.id].on('click',()=>infos[d.id].open(map,markers[d.id].getPosition()));
                    }}
                    markers[d.id].setPosition([d.lng,d.lat]);markers[d.id].setContent(content);
                    circles[d.id].setCenter([d.lng,d.lat]);circles[d.id].setRadius(d.accuracy);
                    circles[d.id].setOptions({{strokeColor:color,fillColor:color}});
                    var info=document.createElement('div');
                    info.style.cssText='white-space:pre-line;padding:8px;line-height:1.8';
                    info.textContent=d.name+' · '+d.plate+'\\n'+d.status+'\\n'+d.location+'\\n高德坐标 '+d.lng.toFixed(6)+', '+d.lat.toFixed(6);
                    infos[d.id].setContent(info);
                }});
                document.getElementById('notice').textContent=data.length?
                    '设备上报 '+data.length+' 辆 · 实时 '+data.filter(d=>d.fresh).length+' 辆 · 灰色为超时后的最后位置':'等待司机设备上报';
                if(added)map.setFitView(null,false,[60,60,60,60]);
            }};
        }}
        </script></html>
        """

    def stop_refresh(self):
        self.refresh_timer.stop()

    def closeEvent(self, event):
        self.stop_refresh()
        super().closeEvent(event)
