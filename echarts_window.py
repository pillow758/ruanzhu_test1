import json
import sqlite3
import os
import tempfile
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFrame, QStackedWidget
)
from PyQt6.QtCore import QTimer, Qt, pyqtSlot, QObject, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel

DB_PATH = os.path.join(os.path.dirname(__file__), "database/logistics.db")
DB_PATH = os.path.abspath(DB_PATH)

# 临时文件目录
TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp_charts")
os.makedirs(TEMP_DIR, exist_ok=True)


def load_html_in_webview(web_view, html_content):
    """
    将HTML写入临时文件并通过QUrl.fromLocalFile()加载，
    解决setHtml()在QWebEngineView中的沙箱限制问题
    """
    temp_path = os.path.join(TEMP_DIR, f"chart_{id(web_view)}.html")
    with open(temp_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    web_view.load(QUrl.fromLocalFile(temp_path))


class PyBridge(QObject):
    """用于 JavaScript 和 Python 通信的桥梁"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent = parent

    @pyqtSlot()
    def openCostDetail(self):
        if self._parent:
            self._parent.show_cost_detail()

    @pyqtSlot()
    def openUtilDetail(self):
        if self._parent:
            self._parent.show_utilization_detail()


class ChartDetailBridge(QObject):
    """用于 ChartDetailWindow 中 JS 和 Python 通信的桥梁"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent = parent

    @pyqtSlot(str)
    def openSingleChart(self, chart_type):
        """打开单个大图表窗口"""
        if self._parent:
            self._parent.show_single_chart(chart_type)


class SingleChartWindow(QWidget):
    """单个大图表详情窗口"""
    def __init__(self, chart_subtype, vehicle_ids, vehicle_util, distances, costs, parent=None):
        super().__init__(parent)
        self.chart_subtype = chart_subtype  # 'utilization', 'distance', 'cost'
        self.vehicle_ids = vehicle_ids
        self.vehicle_util = vehicle_util
        self.distances = distances
        self.costs = costs
        
        titles = {
            'utilization': '🚛 车辆利用率详情',
            'distance': '📏 配送距离详情',
            'cost': '💰 车辆成本详情'
        }
        self.setWindowTitle(titles.get(chart_subtype, '📊 图表详情'))
        self.resize(1400, 900)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        self.setLayout(layout)
        
        # 顶部按钮栏
        btn_frame = QFrame()
        btn_frame.setStyleSheet("""
            QFrame {
                background-color: #2a2a3e;
                border-radius: 6px;
                padding: 5px;
            }
        """)
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(10, 5, 10, 5)
        
        # 标题
        title_label = QLabel(titles.get(chart_subtype, '📊 图表详情'))
        title_label.setStyleSheet("color: #cdd6f4; font-size: 14px; font-weight: bold;")
        btn_layout.addWidget(title_label)
        
        btn_layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("✕ 关闭")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #E74C3C;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #C0392B;
            }
            QPushButton:pressed {
                background-color: #A93226;
            }
        """)
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        layout.addWidget(btn_frame)
        
        # WebEngine 显示 ECharts
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view, 1)
        
        self.load_chart()
    
    def load_chart(self):
        """加载单个大图表"""
        # 格式化数据保留两位小数
        vehicle_util_formatted = [round(x, 2) for x in self.vehicle_util]
        distances_formatted = [round(x, 2) for x in self.distances]
        costs_formatted = [round(x, 2) for x in self.costs]
        
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F39C12', '#9B59B6', '#1ABC9C']
        
        if self.chart_subtype == 'utilization':
            html_content = self._generate_single_chart_html(
                '🚛 车辆利用率 (%)', vehicle_util_formatted, '%', colors, 100
            )
        elif self.chart_subtype == 'distance':
            html_content = self._generate_single_chart_html(
                '📏 配送距离 (km)', distances_formatted, ' km', ['#3498DB'], None
            )
        else:  # cost
            html_content = self._generate_single_chart_html(
                '💰 车辆成本 (¥)', costs_formatted, '¥', colors, None
            )
        
        load_html_in_webview(self.web_view, html_content)
    
    def _generate_single_chart_html(self, title, data, unit, colors, max_val):
        if not max_val:
            max_val = max(data) * 1.3 if data else 100
        color_list = json.dumps(colors)

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    background: #1e1e2e;
                    font-family: "SimSun", sans-serif;
                    padding: 20px;
                }}
                .title {{
                    color: #cdd6f4;
                    font-size: 22px;
                    font-weight: bold;
                    text-align: center;
                    margin-bottom: 15px;
                }}
                canvas {{
                    width: 100%;
                    height: calc(100vh - 80px);
                }}
            </style>
        </head>
        <body>
            <div class="title">{title}</div>
            <canvas id="chart"></canvas>
            <script>
                var labels = {json.dumps(self.vehicle_ids)};
                var data = {json.dumps(data)};
                var unit = '{unit}';
                var colors = {color_list};
                var maxVal = {max_val};

                function draw() {{
                    var c = document.getElementById('chart');
                    var ctx = c.getContext('2d');
                    c.width = c.clientWidth;
                    c.height = c.clientHeight;
                    var w = c.width, h = c.height;
                    var pad = {{top:30, right:30, bottom:50, left:60}};
                    var cw = w - pad.left - pad.right;
                    var ch = h - pad.top - pad.bottom;

                    ctx.clearRect(0,0,w,h);

                    // Y轴网格
                    ctx.strokeStyle = '#333';
                    ctx.lineWidth = 1;
                    ctx.fillStyle = '#888';
                    ctx.font = '13px SimSun';
                    ctx.textAlign = 'right';
                    for (var i=0; i<=5; i++) {{
                        var y = pad.top + ch * (1 - i/5);
                        ctx.beginPath();
                        ctx.moveTo(pad.left, y);
                        ctx.lineTo(w - pad.right, y);
                        ctx.stroke();
                        ctx.fillText((maxVal * i / 5).toFixed(1), pad.left - 8, y + 4);
                    }}

                    // 柱子
                    var gap = cw / data.length;
                    var barW = gap * 0.55;
                    var avg = data.reduce(function(a,b){{return a+b}},0) / data.length;

                    data.forEach(function(val, idx) {{
                        var x = pad.left + gap * idx + (gap - barW) / 2;
                        var barH = (val / maxVal) * ch;
                        var y = pad.top + ch - barH;
                        var color = colors[idx % colors.length];

                        var grad = ctx.createLinearGradient(x, y, x, pad.top + ch);
                        grad.addColorStop(0, color);
                        grad.addColorStop(1, color + '40');
                        ctx.fillStyle = grad;
                        ctx.beginPath();
                        ctx.roundRect(x, y, barW, barH, [6,6,0,0]);
                        ctx.fill();

                        // 数值
                        ctx.fillStyle = '#cdd6f4';
                        ctx.font = 'bold 13px SimSun';
                        ctx.textAlign = 'center';
                        ctx.fillText(val.toFixed(2) + unit, x + barW/2, y - 8);

                        // X标签
                        ctx.fillStyle = '#aaa';
                        ctx.font = '13px SimSun';
                        ctx.fillText(labels[idx] || '', x + barW/2, pad.top + ch + 25);
                    }});

                    // 平均线
                    var avgY = pad.top + ch - (avg / maxVal) * ch;
                    ctx.setLineDash([8, 4]);
                    ctx.strokeStyle = '#FFEAA7';
                    ctx.lineWidth = 2;
                    ctx.beginPath();
                    ctx.moveTo(pad.left, avgY);
                    ctx.lineTo(w - pad.right, avgY);
                    ctx.stroke();
                    ctx.setLineDash([]);
                    ctx.fillStyle = '#FFEAA7';
                    ctx.font = 'bold 12px SimSun';
                    ctx.textAlign = 'left';
                    ctx.fillText('平均: ' + avg.toFixed(2), w - pad.right + 5, avgY + 4);
                }}

                window.onload = function() {{ setTimeout(draw, 50); }};
                window.onresize = draw;
            </script>
        </body>
        </html>
        """


class ChartDetailWindow(QWidget):
    """详细图表窗口（成本曲线或车辆利用率）"""
    def __init__(self, chart_type, parent=None):
        super().__init__(parent)
        self.chart_type = chart_type  # 'cost' 或 'utilization'
        self.single_windows = []  # 保持单图表窗口引用
        self.setWindowTitle("📊 成本曲线详情" if chart_type == 'cost' else "📊 车辆利用率详情")
        self.resize(1200, 800)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        self.setLayout(layout)
        
        # 顶部按钮栏
        btn_frame = QFrame()
        btn_frame.setStyleSheet("""
            QFrame {
                background-color: #2a2a3e;
                border-radius: 6px;
                padding: 5px;
            }
        """)
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(10, 5, 10, 5)
        
        # 标题
        title = "📈 成本曲线详情" if chart_type == 'cost' else "🚛 车辆利用率详情"
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #cdd6f4; font-size: 14px; font-weight: bold;")
        btn_layout.addWidget(title_label)
        
        btn_layout.addStretch()
        
        # 关闭按钮
        close_btn = QPushButton("✕ 关闭")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #E74C3C;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #C0392B;
            }
            QPushButton:pressed {
                background-color: #A93226;
            }
        """)
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)
        
        layout.addWidget(btn_frame)
        
        # WebEngine 显示 ECharts
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view, 1)
        
        # 设置 WebChannel 用于 JS 和 Python 通信
        if chart_type == 'utilization':
            self.channel = QWebChannel()
            self.py_bridge = ChartDetailBridge(self)
            self.channel.registerObject("chartBridge", self.py_bridge)
            self.web_view.page().setWebChannel(self.channel)
        
        self.load_chart()
    
    def load_chart(self):
        """加载详细图表"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if self.chart_type == 'cost':
            # 成本曲线详细数据
            cursor.execute("SELECT timestamp, cost FROM routes ORDER BY timestamp")
            cost_data = cursor.fetchall()
            timestamps = [row[0] for row in cost_data]
            costs = [row[1] for row in cost_data]

            # 如果没有数据，使用演示数据
            if not timestamps:
                timestamps = ['2024-01-01 08:00', '2024-01-01 10:00', '2024-01-01 12:00',
                             '2024-01-01 14:00', '2024-01-01 16:00']
                costs = [450.0, 520.5, 480.3, 560.8, 510.2]

            html_content = self._generate_cost_chart_html(timestamps, costs)
        else:  # utilization
            # 车辆利用率详细数据
            cursor.execute("SELECT vehicle_id, q, distance, cost FROM routes")
            vehicle_data = cursor.fetchall()
            self.vehicle_ids = [row[0] for row in vehicle_data]
            self.vehicle_util = [min(row[1]/3000,1)*100 for row in vehicle_data]
            self.distances = [row[2] for row in vehicle_data]
            self.costs = [row[3] for row in vehicle_data]

            # 如果没有数据，使用演示数据
            if not self.vehicle_ids:
                self.vehicle_ids = ['V1', 'V2', 'V3', 'V4']
                self.vehicle_util = [75.5, 60.2, 85.8, 45.3]
                self.distances = [25.6, 18.3, 32.1, 15.8]
                self.costs = [464.0, 445.75, 480.25, 439.5]

            html_content = self._generate_utilization_chart_html(
                self.vehicle_ids, self.vehicle_util, self.distances, self.costs
            )

        conn.close()
        load_html_in_webview(self.web_view, html_content)
    
    def show_single_chart(self, chart_type):
        """显示单个大图表窗口"""
        single_window = SingleChartWindow(
            chart_type, 
            self.vehicle_ids, 
            self.vehicle_util, 
            self.distances, 
            self.costs, 
            self
        )
        single_window.show()
        self.single_windows.append(single_window)
        # 清理已关闭的窗口引用
        self.single_windows = [w for w in self.single_windows if w.isVisible()]
    
    def _generate_cost_chart_html(self, timestamps, costs):
        """生成成本曲线详细图表（纯Canvas）"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    background: #1e1e2e;
                    font-family: "SimSun", sans-serif;
                    padding: 20px;
                }}
                .title {{
                    color: #cdd6f4;
                    font-size: 20px;
                    font-weight: bold;
                    text-align: center;
                    margin-bottom: 15px;
                }}
                canvas {{
                    width: 100%;
                    height: calc(100vh - 80px);
                }}
            </style>
        </head>
        <body>
            <div class="title">📈 成本曲线详情</div>
            <canvas id="chart"></canvas>
            <script>
                var labels = {json.dumps(timestamps)};
                var data = {json.dumps(costs)};

                function draw() {{
                    var c = document.getElementById('chart');
                    var ctx = c.getContext('2d');
                    c.width = c.clientWidth;
                    c.height = c.clientHeight;
                    var w = c.width, h = c.height;
                    var pad = {{top:30, right:30, bottom:55, left:65}};
                    var cw = w - pad.left - pad.right;
                    var ch = h - pad.top - pad.bottom;
                    var maxVal = Math.max(...data) * 1.2 || 100;
                    var minVal = Math.min(...data) * 0.8;
                    var range = maxVal - minVal || 1;
                    var avg = data.reduce(function(a,b){{return a+b}},0) / data.length;

                    ctx.clearRect(0,0,w,h);

                    // 网格
                    ctx.strokeStyle = '#333';
                    ctx.lineWidth = 1;
                    ctx.fillStyle = '#888';
                    ctx.font = '12px SimSun';
                    ctx.textAlign = 'right';
                    for (var i=0; i<=5; i++) {{
                        var y = pad.top + ch * (1 - i/5);
                        ctx.beginPath();
                        ctx.moveTo(pad.left, y);
                        ctx.lineTo(w - pad.right, y);
                        ctx.stroke();
                        var val = minVal + range * i / 5;
                        ctx.fillText('¥' + val.toFixed(0), pad.left - 8, y + 4);
                    }}

                    // 面积
                    ctx.beginPath();
                    data.forEach(function(val, idx) {{
                        var x = pad.left + (cw / (data.length - 1)) * idx;
                        var y = pad.top + ch - ((val - minVal) / range) * ch;
                        if (idx === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                    }});
                    ctx.lineTo(pad.left + cw, pad.top + ch);
                    ctx.lineTo(pad.left, pad.top + ch);
                    ctx.closePath();
                    var grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + ch);
                    grad.addColorStop(0, 'rgba(39,174,96,0.4)');
                    grad.addColorStop(1, 'rgba(39,174,96,0.02)');
                    ctx.fillStyle = grad;
                    ctx.fill();

                    // 线
                    ctx.beginPath();
                    data.forEach(function(val, idx) {{
                        var x = pad.left + (cw / (data.length - 1)) * idx;
                        var y = pad.top + ch - ((val - minVal) / range) * ch;
                        if (idx === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
                    }});
                    ctx.strokeStyle = '#27AE60';
                    ctx.lineWidth = 3;
                    ctx.stroke();

                    // 点 + X标签
                    data.forEach(function(val, idx) {{
                        var x = pad.left + (cw / (data.length - 1)) * idx;
                        var y = pad.top + ch - ((val - minVal) / range) * ch;
                        ctx.beginPath();
                        ctx.arc(x, y, 6, 0, Math.PI*2);
                        ctx.fillStyle = '#27AE60';
                        ctx.fill();
                        ctx.strokeStyle = '#fff';
                        ctx.lineWidth = 2;
                        ctx.stroke();

                        // 数值
                        ctx.fillStyle = '#cdd6f4';
                        ctx.font = 'bold 11px SimSun';
                        ctx.textAlign = 'center';
                        ctx.fillText('¥' + val.toFixed(1), x, y - 12);

                        // X标签
                        ctx.fillStyle = '#aaa';
                        ctx.font = '10px SimSun';
                        var lbl = labels[idx] ? labels[idx].substring(5, 16) : '';
                        ctx.fillText(lbl, x, pad.top + ch + 20);
                    }});

                    // 平均线
                    var avgY = pad.top + ch - ((avg - minVal) / range) * ch;
                    ctx.setLineDash([8,4]);
                    ctx.strokeStyle = '#FFEAA7';
                    ctx.lineWidth = 2;
                    ctx.beginPath();
                    ctx.moveTo(pad.left, avgY);
                    ctx.lineTo(w - pad.right, avgY);
                    ctx.stroke();
                    ctx.setLineDash([]);
                    ctx.fillStyle = '#FFEAA7';
                    ctx.font = 'bold 12px SimSun';
                    ctx.textAlign = 'right';
                    ctx.fillText('平均: ¥' + avg.toFixed(1), w - pad.right, avgY - 8);
                }}

                window.onload = function() {{ setTimeout(draw, 50); }};
                window.onresize = draw;
            </script>
        </body>
        </html>
        """
    
    def _generate_utilization_chart_html(self, vehicle_ids, vehicle_util, distances, costs):
        """生成车辆利用率详细图表（纯Canvas）"""
        # 格式化数据保留两位小数
        vehicle_util_formatted = [round(x, 2) for x in vehicle_util]
        distances_formatted = [round(x, 2) for x in distances]
        costs_formatted = [round(x, 2) for x in costs]
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    background: #1e1e2e;
                    font-family: "SimSun", sans-serif;
                    padding: 15px;
                }}
                .container {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    grid-template-rows: 1fr 1fr;
                    gap: 15px;
                    height: calc(100vh - 30px);
                }}
                .chart-box {{
                    background: #2a2a3e;
                    border-radius: 8px;
                    padding: 12px;
                    display: flex;
                    flex-direction: column;
                    min-height: 0;
                }}
                .chart-title {{
                    color: #cdd6f4;
                    font-size: 15px;
                    font-weight: bold;
                    text-align: center;
                    margin-bottom: 8px;
                    flex-shrink: 0;
                }}
                canvas {{
                    flex: 1;
                    width: 100%;
                    min-height: 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="chart-box">
                    <div class="chart-title">🚛 车辆利用率 (%)</div>
                    <canvas id="c1"></canvas>
                </div>
                <div class="chart-box">
                    <div class="chart-title">📏 配送距离 (km)</div>
                    <canvas id="c2"></canvas>
                </div>
                <div class="chart-box">
                    <div class="chart-title">💰 车辆成本 (¥)</div>
                    <canvas id="c3"></canvas>
                </div>
                <div class="chart-box">
                    <div class="chart-title">📊 综合对比</div>
                    <canvas id="c4"></canvas>
                </div>
            </div>
            <script>
                var COLORS = ['#FF6B6B','#4ECDC4','#45B7D1','#96CEB4','#FFEAA7','#DDA0DD','#98D8C8','#F39C12','#9B59B6','#1ABC9C'];
                var vehicleIds = {json.dumps(vehicle_ids)};
                var vehicleUtil = {json.dumps(vehicle_util_formatted)};
                var distancesArr = {json.dumps(distances_formatted)};
                var costsArr = {json.dumps(costs_formatted)};

                function sizeCanvas(id) {{
                    var c = document.getElementById(id);
                    c.width = c.clientWidth;
                    c.height = c.clientHeight;
                    return c.getContext('2d');
                }}

                function drawBarChart(id, labels, data, maxVal, suffix, color) {{
                    var c = document.getElementById(id);
                    var ctx = c.getContext('2d');
                    c.width = c.clientWidth;
                    c.height = c.clientHeight;
                    var w = c.width, h = c.height;
                    var pad = {{top:20, right:15, bottom:40, left:55}};
                    var cw = w - pad.left - pad.right;
                    var ch = h - pad.top - pad.bottom;
                    var n = data.length;
                    var maxV = maxVal || Math.max.apply(null, data) * 1.2 || 100;

                    ctx.clearRect(0,0,w,h);

                    // Y轴网格
                    ctx.strokeStyle = '#333';
                    ctx.lineWidth = 1;
                    ctx.textAlign = 'right';
                    ctx.fillStyle = '#888';
                    ctx.font = '11px SimSun';
                    for (var i=0; i<=4; i++) {{
                        var y = pad.top + ch * (1 - i/4);
                        ctx.beginPath();
                        ctx.moveTo(pad.left, y);
                        ctx.lineTo(w - pad.right, y);
                        ctx.stroke();
                        ctx.fillText((maxV * i / 4).toFixed(1) + suffix, pad.left - 5, y + 4);
                    }}

                    if (n === 0) return;
                    var barW = Math.min(50, cw / n * 0.65);
                    var gap = cw / n;

                    for (var j=0; j<n; j++) {{
                        var x = pad.left + gap * j + gap/2 - barW/2;
                        var barH = (data[j] / maxV) * ch;
                        var by = pad.top + ch - barH;

                        // 柱体渐变
                        var grad = ctx.createLinearGradient(x, by, x, pad.top + ch);
                        grad.addColorStop(0, color);
                        grad.addColorStop(1, color + '60');
                        ctx.fillStyle = grad;
                        ctx.beginPath();
                        var r = Math.min(5, barW/3);
                        ctx.moveTo(x + r, by);
                        ctx.lineTo(x + barW - r, by);
                        ctx.quadraticCurveTo(x + barW, by, x + barW, by + r);
                        ctx.lineTo(x + barW, pad.top + ch);
                        ctx.lineTo(x, pad.top + ch);
                        ctx.lineTo(x, by + r);
                        ctx.quadraticCurveTo(x, by, x + r, by);
                        ctx.fill();

                        // 数值标签
                        ctx.fillStyle = '#cdd6f4';
                        ctx.font = 'bold 11px SimSun';
                        ctx.textAlign = 'center';
                        ctx.fillText(data[j].toFixed(2) + suffix, x + barW/2, by - 5);

                        // X标签
                        ctx.fillStyle = '#aaa';
                        ctx.font = '10px SimSun';
                        ctx.fillText(labels[j], pad.left + gap * j + gap/2, pad.top + ch + 18);
                    }}
                }}

                function drawRadar() {{
                    var c = document.getElementById('c4');
                    var ctx = c.getContext('2d');
                    c.width = c.clientWidth;
                    c.height = c.clientHeight;
                    var w = c.width, h = c.height;
                    var cx = w/2, cy = h/2 - 10;
                    var R = Math.min(cx, cy) - 40;
                    var axes = 3;
                    var labels = ['利用率','距离占比','成本占比'];
                    var angles = [];
                    for (var a=0; a<axes; a++) angles.push(-Math.PI/2 + (Math.PI*2/axes)*a);

                    var maxU = Math.max.apply(null, vehicleUtil) || 1;
                    var maxD = Math.max.apply(null, distancesArr) || 1;
                    var maxC = Math.max.apply(null, costsArr) || 1;

                    ctx.clearRect(0,0,w,h);

                    // 网格圆 + 轴线
                    ctx.strokeStyle = '#444';
                    ctx.lineWidth = 1;
                    for (var ring=1; ring<=5; ring++) {{
                        var rr = R * ring / 5;
                        ctx.beginPath();
                        ctx.arc(cx, cy, rr, 0, Math.PI*2);
                        ctx.stroke();
                    }}
                    for (var a=0; a<axes; a++) {{
                        ctx.beginPath();
                        ctx.moveTo(cx, cy);
                        ctx.lineTo(cx + R*Math.cos(angles[a]), cy + R*Math.sin(angles[a]));
                        ctx.stroke();
                    }}

                    // 轴标签
                    ctx.fillStyle = '#aaa';
                    ctx.font = '11px SimSun';
                    ctx.textAlign = 'center';
                    for (var a=0; a<axes; a++) {{
                        var lx = cx + (R+18)*Math.cos(angles[a]);
                        var ly = cy + (R+18)*Math.sin(angles[a]);
                        ctx.fillText(labels[a], lx, ly + 4);
                    }}

                    // 绘制各车辆数据
                    var n = vehicleIds.length;
                    for (var v=0; v<n; v++) {{
                        var utilN = vehicleUtil[v] / maxU * 100;
                        var distN = distancesArr[v] / maxD * 100;
                        var costN = costsArr[v] / maxC * 100;
                        var vals = [utilN, distN, costN];
                        var col = COLORS[v % COLORS.length];

                        // 填充区域
                        ctx.beginPath();
                        for (var a=0; a<axes; a++) {{
                            var px = cx + R*(vals[a]/100)*Math.cos(angles[a]);
                            var py = cy + R*(vals[a]/100)*Math.sin(angles[a]);
                            if (a===0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
                        }}
                        ctx.closePath();
                        ctx.fillStyle = col + '40';
                        ctx.fill();
                        ctx.strokeStyle = col;
                        ctx.lineWidth = 2;
                        ctx.stroke();

                        // 数据点
                        for (var a=0; a<axes; a++) {{
                            var px = cx + R*(vals[a]/100)*Math.cos(angles[a]);
                            var py = cy + R*(vals[a]/100)*Math.sin(angles[a]);
                            ctx.beginPath();
                            ctx.arc(px, py, 4, 0, Math.PI*2);
                            ctx.fillStyle = col;
                            ctx.fill();
                            ctx.strokeStyle = '#fff';
                            ctx.lineWidth = 1.5;
                            ctx.stroke();
                        }}
                    }}

                    // 图例
                    var legendY = h - 22;
                    var totalW = 0;
                    var itemWidths = vehicleIds.map(function(id) {{ return id.length * 8 + 25; }});
                    totalW = itemWidths.reduce(function(a,b){{return a+b}}, 0) + (n-1)*8;
                    var sx = (w - totalW) / 2;
                    ctx.font = '11px SimSun';
                    for (var v=0; v<n; v++) {{
                        var col = COLORS[v % COLORS.length];
                        ctx.fillStyle = col;
                        ctx.fillRect(sx, legendY - 6, 14, 10);
                        ctx.fillStyle = '#aaa';
                        ctx.textAlign = 'left';
                        ctx.fillText(vehicleIds[v], sx + 18, legendY + 4);
                        sx += itemWidths[v] + 8;
                    }}
                }}

                function drawAll() {{
                    var maxU = Math.max(100, Math.max.apply(null, vehicleUtil) * 1.2);
                    var maxD = Math.max(1, Math.max.apply(null, distancesArr) * 1.2);
                    var maxC = Math.max(1, Math.max.apply(null, costsArr) * 1.2);
                    drawBarChart('c1', vehicleIds, vehicleUtil, maxU, '%', '#4ECDC4');
                    drawBarChart('c2', vehicleIds, distancesArr, maxD, 'km', '#3498DB');
                    drawBarChart('c3', vehicleIds, costsArr, maxC, '¥', '#E74C3C');
                    drawRadar();
                }}

                window.onload = function() {{ setTimeout(drawAll, 50); }};
                window.onresize = drawAll;
            </script>
        </body>
        </html>
        """


class EChartsAnalysis(QWidget):
    """集成 ECharts 数据分析窗口 - 带按钮导航"""
    def __init__(self, parent=None, refresh_interval=5000):
        super().__init__(parent)
        self.detail_windows = []  # 保持引用防止被垃圾回收
        
        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        self.setLayout(main_layout)
        
        # 按钮区域
        btn_frame = QFrame()
        btn_frame.setStyleSheet("""
            QFrame {
                background-color: #2a2a3e;
                border-radius: 8px;
                padding: 5px;
            }
        """)
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setSpacing(15)
        
        # 标题
        title_label = QLabel("📊 数据分析中心")
        title_label.setStyleSheet("color: #cdd6f4; font-size: 16px; font-weight: bold;")
        btn_layout.addWidget(title_label)
        
        btn_layout.addStretch()
        
        # 成本曲线按钮
        self.cost_btn = QPushButton("📈 成本曲线详情")
        self.cost_btn.setStyleSheet("""
            QPushButton {
                background-color: #27AE60;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2ECC71;
            }
            QPushButton:pressed {
                background-color: #1E8449;
            }
        """)
        self.cost_btn.clicked.connect(self.show_cost_detail)
        btn_layout.addWidget(self.cost_btn)
        
        # 车辆利用率按钮
        self.util_btn = QPushButton("🚛 车辆利用率详情")
        self.util_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498DB;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5DADE2;
            }
            QPushButton:pressed {
                background-color: #2874A6;
            }
        """)
        self.util_btn.clicked.connect(self.show_utilization_detail)
        btn_layout.addWidget(self.util_btn)
        
        main_layout.addWidget(btn_frame)
        
        # WebEngine 显示概览图表
        self.web_view = QWebEngineView()
        main_layout.addWidget(self.web_view, 1)
        
        # 设置 WebChannel 用于 JS 和 Python 通信
        self.channel = QWebChannel()
        self.py_bridge = PyBridge(self)
        self.channel.registerObject("pybridge", self.py_bridge)
        self.web_view.page().setWebChannel(self.channel)
        
        # 设置刷新定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.load_chart)
        self.timer.start(refresh_interval)
        
        # 首次加载
        self.load_chart()
    
    def show_cost_detail(self):
        """显示成本曲线详细窗口"""
        detail_window = ChartDetailWindow('cost', self)
        detail_window.show()
        self.detail_windows.append(detail_window)
        # 清理已关闭的窗口引用
        self.detail_windows = [w for w in self.detail_windows if w.isVisible()]
    
    def show_utilization_detail(self):
        """显示车辆利用率详细窗口"""
        detail_window = ChartDetailWindow('utilization', self)
        detail_window.show()
        self.detail_windows.append(detail_window)
        # 清理已关闭的窗口引用
        self.detail_windows = [w for w in self.detail_windows if w.isVisible()]
    
    def load_chart(self):
        """从 SQLite 读取数据，生成概览图表"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1️⃣ 先读取车辆数据
        cursor.execute("SELECT vehicle_id, q FROM routes")
        vehicle_data = cursor.fetchall()
        vehicle_ids = [row[0] for row in vehicle_data]
        vehicle_util = [min(row[1]/3000,1)*100 for row in vehicle_data]

        # 2️⃣ 成本曲线
        cursor.execute("SELECT timestamp, cost FROM routes ORDER BY timestamp")
        cost_data = cursor.fetchall()
        timestamps = [row[0] for row in cost_data]
        costs = [row[1] for row in cost_data]

        # 3️⃣ 订单统计
        try:
            cursor.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
            orders = cursor.fetchall()
        except:
            orders = []
        if not orders:
            orders = [('已完成', len(vehicle_ids) if vehicle_ids else 5), ('配送中', 0), ('待处理', 0)]
        status_list = [row[0] for row in orders]
        count_list = [row[1] for row in orders]

        conn.close()

        # 如果没有数据，生成演示数据
        if not vehicle_ids:
            vehicle_ids = ['V1', 'V2', 'V3', 'V4']
            vehicle_util = [75.5, 60.2, 85.8, 45.3]
            timestamps = ['2024-01-01 08:00', '2024-01-01 10:00', '2024-01-01 12:00', '2024-01-01 14:00']
            costs = [450.0, 520.5, 480.3, 560.8]
            status_list = ['已完成', '配送中', '待处理']
            count_list = [12, 5, 3]
        
        # 构建概览页面 HTML（纯Canvas实现，无需外部库）
        avgUtil = sum(vehicle_util) / len(vehicle_util) if vehicle_util else 0
        totalOrders = sum(count_list) if count_list else 0
        totalCost = sum(costs) if costs else 0

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script type="text/javascript">
                new QWebChannel(qt.webChannelTransport, function(channel) {{
                    window.pybridge = channel.objects.pybridge;
                }});
            </script>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    background-color: #1e1e2e;
                    font-family: "SimSun", sans-serif;
                    padding: 10px;
                }}
                .grid {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    grid-template-rows: 1fr 1fr;
                    gap: 12px;
                    height: calc(100vh - 20px);
                }}
                .box {{
                    background: #2a2a3e;
                    border-radius: 10px;
                    padding: 12px;
                    display: flex;
                    flex-direction: column;
                }}
                .box.clickable {{ cursor: pointer; }}
                .box.clickable:hover {{ background: #333350; }}
                .title {{
                    color: #cdd6f4;
                    font-size: 14px;
                    font-weight: bold;
                    text-align: center;
                    margin-bottom: 8px;
                }}
                .hint {{
                    color: #666;
                    font-size: 11px;
                    text-align: center;
                    margin-top: 4px;
                }}
                canvas {{ flex: 1; width: 100%; }}
            </style>
        </head>
        <body>
            <div class="grid">
                <div class="box">
                    <div class="title">📊 订单统计</div>
                    <canvas id="c1"></canvas>
                </div>
                <div class="box clickable" onclick="window.pybridge && window.pybridge.openCostDetail()">
                    <div class="title">📈 成本曲线</div>
                    <canvas id="c2"></canvas>
                    <div class="hint">点击查看详情</div>
                </div>
                <div class="box clickable" onclick="window.pybridge && window.pybridge.openUtilDetail()">
                    <div class="title">🚛 车辆利用率 (%)</div>
                    <canvas id="c3"></canvas>
                    <div class="hint">点击查看详情</div>
                </div>
                <div class="box">
                    <div class="title">📊 综合仪表盘</div>
                    <canvas id="c4"></canvas>
                </div>
            </div>
            <script>
                var colors = ['#FF6B6B','#4ECDC4','#45B7D1','#96CEB4','#FFEAA7','#DDA0DD','#98D8C8','#F39C12'];

                function drawBar(canvasId, labels, data, unit, maxVal) {{
                    var c = document.getElementById(canvasId);
                    var ctx = c.getContext('2d');
                    var rect = c.parentElement.getBoundingClientRect();
                    c.width = rect.width - 24;
                    c.height = rect.height - 60;
                    var w = c.width, h = c.height;
                    var pad = {{top:20, right:20, bottom:40, left:50}};
                    var chartW = w - pad.left - pad.right;
                    var chartH = h - pad.top - pad.bottom;
                    if (!maxVal) maxVal = Math.max(...data) * 1.2 || 100;

                    ctx.clearRect(0,0,w,h);

                    // Y轴网格
                    ctx.strokeStyle = '#333';
                    ctx.lineWidth = 1;
                    ctx.fillStyle = '#888';
                    ctx.font = '11px SimSun';
                    ctx.textAlign = 'right';
                    for (var i=0; i<=4; i++) {{
                        var y = pad.top + chartH * (1 - i/4);
                        ctx.beginPath();
                        ctx.moveTo(pad.left, y);
                        ctx.lineTo(w - pad.right, y);
                        ctx.stroke();
                        ctx.fillText((maxVal * i / 4).toFixed(0), pad.left - 5, y + 4);
                    }}

                    // 柱子
                    var barW = chartW / data.length * 0.6;
                    var gap = chartW / data.length;
                    data.forEach(function(val, idx) {{
                        var x = pad.left + gap * idx + (gap - barW) / 2;
                        var barH = (val / maxVal) * chartH;
                        var y = pad.top + chartH - barH;
                        var color = colors[idx % colors.length];

                        // 渐变
                        var grad = ctx.createLinearGradient(x, y, x, pad.top + chartH);
                        grad.addColorStop(0, color);
                        grad.addColorStop(1, color + '40');
                        ctx.fillStyle = grad;
                        ctx.beginPath();
                        ctx.roundRect(x, y, barW, barH, [4,4,0,0]);
                        ctx.fill();

                        // 数值
                        ctx.fillStyle = '#cdd6f4';
                        ctx.font = 'bold 11px SimSun';
                        ctx.textAlign = 'center';
                        ctx.fillText(val.toFixed(1) + unit, x + barW/2, y - 5);

                        // 标签
                        ctx.fillStyle = '#aaa';
                        ctx.font = '11px SimSun';
                        ctx.fillText(labels[idx], x + barW/2, pad.top + chartH + 18);
                    }});
                }}

                function drawLine(canvasId, labels, data) {{
                    var c = document.getElementById(canvasId);
                    var ctx = c.getContext('2d');
                    var rect = c.parentElement.getBoundingClientRect();
                    c.width = rect.width - 24;
                    c.height = rect.height - 60;
                    var w = c.width, h = c.height;
                    var pad = {{top:20, right:20, bottom:40, left:55}};
                    var chartW = w - pad.left - pad.right;
                    var chartH = h - pad.top - pad.bottom;
                    var maxVal = Math.max(...data) * 1.2 || 100;
                    var minVal = Math.min(...data) * 0.8;

                    ctx.clearRect(0,0,w,h);

                    // 网格
                    ctx.strokeStyle = '#333';
                    ctx.lineWidth = 1;
                    ctx.fillStyle = '#888';
                    ctx.font = '11px SimSun';
                    ctx.textAlign = 'right';
                    for (var i=0; i<=4; i++) {{
                        var y = pad.top + chartH * (1 - i/4);
                        ctx.beginPath();
                        ctx.moveTo(pad.left, y);
                        ctx.lineTo(w - pad.right, y);
                        ctx.stroke();
                        var val = minVal + (maxVal - minVal) * i / 4;
                        ctx.fillText('¥' + val.toFixed(0), pad.left - 5, y + 4);
                    }}

                    // 面积
                    ctx.beginPath();
                    data.forEach(function(val, idx) {{
                        var x = pad.left + (chartW / (data.length - 1)) * idx;
                        var y = pad.top + chartH - ((val - minVal) / (maxVal - minVal)) * chartH;
                        if (idx === 0) ctx.moveTo(x, y);
                        else ctx.lineTo(x, y);
                    }});
                    var lastX = pad.left + chartW;
                    ctx.lineTo(lastX, pad.top + chartH);
                    ctx.lineTo(pad.left, pad.top + chartH);
                    ctx.closePath();
                    var grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + chartH);
                    grad.addColorStop(0, 'rgba(39,174,96,0.4)');
                    grad.addColorStop(1, 'rgba(39,174,96,0.02)');
                    ctx.fillStyle = grad;
                    ctx.fill();

                    // 线
                    ctx.beginPath();
                    data.forEach(function(val, idx) {{
                        var x = pad.left + (chartW / (data.length - 1)) * idx;
                        var y = pad.top + chartH - ((val - minVal) / (maxVal - minVal)) * chartH;
                        if (idx === 0) ctx.moveTo(x, y);
                        else ctx.lineTo(x, y);
                    }});
                    ctx.strokeStyle = '#27AE60';
                    ctx.lineWidth = 3;
                    ctx.stroke();

                    // 点+标签
                    data.forEach(function(val, idx) {{
                        var x = pad.left + (chartW / (data.length - 1)) * idx;
                        var y = pad.top + chartH - ((val - minVal) / (maxVal - minVal)) * chartH;
                        ctx.beginPath();
                        ctx.arc(x, y, 5, 0, Math.PI*2);
                        ctx.fillStyle = '#27AE60';
                        ctx.fill();
                        ctx.strokeStyle = '#fff';
                        ctx.lineWidth = 2;
                        ctx.stroke();

                        // X标签
                        ctx.fillStyle = '#aaa';
                        ctx.font = '10px SimSun';
                        ctx.textAlign = 'center';
                        var lbl = labels[idx] ? labels[idx].substring(5, 16) : '';
                        ctx.fillText(lbl, x, pad.top + chartH + 18);
                    }});
                }}

                function drawGauge(canvasId, value) {{
                    var c = document.getElementById(canvasId);
                    var ctx = c.getContext('2d');
                    var rect = c.parentElement.getBoundingClientRect();
                    c.width = rect.width - 24;
                    c.height = rect.height - 60;
                    var w = c.width, h = c.height;
                    var cx = w/2, cy = h * 0.65;
                    var r = Math.min(w, h) * 0.38;

                    ctx.clearRect(0,0,w,h);

                    // 背景弧
                    ctx.beginPath();
                    ctx.arc(cx, cy, r, Math.PI, 0);
                    ctx.lineWidth = r * 0.18;
                    ctx.strokeStyle = '#333';
                    ctx.lineCap = 'round';
                    ctx.stroke();

                    // 彩色弧
                    var angle = Math.PI + (value / 100) * Math.PI;
                    var grad = ctx.createLinearGradient(cx - r, cy, cx + r, cy);
                    grad.addColorStop(0, '#FF6B6B');
                    grad.addColorStop(0.5, '#FFEAA7');
                    grad.addColorStop(1, '#27AE60');
                    ctx.beginPath();
                    ctx.arc(cx, cy, r, Math.PI, angle);
                    ctx.lineWidth = r * 0.18;
                    ctx.strokeStyle = grad;
                    ctx.lineCap = 'round';
                    ctx.stroke();

                    // 指针
                    var pAngle = Math.PI + (value / 100) * Math.PI;
                    var px = cx + Math.cos(pAngle) * r * 0.75;
                    var py = cy + Math.sin(pAngle) * r * 0.75;
                    ctx.beginPath();
                    ctx.moveTo(cx, cy);
                    ctx.lineTo(px, py);
                    ctx.strokeStyle = '#cdd6f4';
                    ctx.lineWidth = 3;
                    ctx.lineCap = 'round';
                    ctx.stroke();

                    // 中心圆
                    ctx.beginPath();
                    ctx.arc(cx, cy, 6, 0, Math.PI*2);
                    ctx.fillStyle = '#cdd6f4';
                    ctx.fill();

                    // 数值
                    ctx.fillStyle = '#cdd6f4';
                    ctx.font = 'bold 28px SimSun';
                    ctx.textAlign = 'center';
                    ctx.fillText(Math.round(value) + '%', cx, cy + r * 0.35);

                    ctx.fillStyle = '#888';
                    ctx.font = '13px SimSun';
                    ctx.fillText('平均利用率', cx, cy + r * 0.55);

                    // 刻度
                    ctx.fillStyle = '#aaa';
                    ctx.font = '11px SimSun';
                    ctx.fillText('低', cx - r - 5, cy + 18);
                    ctx.fillText('高', cx + r + 5, cy + 18);
                }}

                // 绘制所有图表
                window.onload = function() {{
                    setTimeout(function() {{
                        drawBar('c1', {json.dumps(status_list)}, {json.dumps(count_list)}, '', {max(count_list)*1.3 if count_list else 20});
                        drawLine('c2', {json.dumps(timestamps)}, {json.dumps(costs)});
                        drawBar('c3', {json.dumps(vehicle_ids)}, {json.dumps(vehicle_util)}, '%', 100);
                        drawGauge('c4', {avgUtil:.1f});
                    }}, 100);
                }};

                window.onresize = function() {{
                    drawBar('c1', {json.dumps(status_list)}, {json.dumps(count_list)}, '', {max(count_list)*1.3 if count_list else 20});
                    drawLine('c2', {json.dumps(timestamps)}, {json.dumps(costs)});
                    drawBar('c3', {json.dumps(vehicle_ids)}, {json.dumps(vehicle_util)}, '%', 100);
                    drawGauge('c4', {avgUtil:.1f});
                }};
            </script>
        </body>
        </html>
        """
        load_html_in_webview(self.web_view, html_content)
