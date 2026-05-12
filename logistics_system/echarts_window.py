import json
import sqlite3
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QFrame, QStackedWidget
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWebEngineWidgets import QWebEngineView

DB_PATH = os.path.join(os.path.dirname(__file__), "database/logistics.db")
DB_PATH = os.path.abspath(DB_PATH)


class ChartDetailWindow(QWidget):
    """详细图表窗口（成本曲线或车辆利用率）"""
    def __init__(self, chart_type, parent=None):
        super().__init__(parent)
        self.chart_type = chart_type  # 'cost' 或 'utilization'
        self.setWindowTitle("📊 成本曲线详情" if chart_type == 'cost' else "📊 车辆利用率详情")
        self.resize(1000, 600)
        
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
            
            html_content = self._generate_cost_chart_html(timestamps, costs)
        else:  # utilization
            # 车辆利用率详细数据
            cursor.execute("SELECT vehicle_id, q, distance, cost FROM routes")
            vehicle_data = cursor.fetchall()
            vehicle_ids = [row[0] for row in vehicle_data]
            vehicle_util = [min(row[1]/3000,1)*100 for row in vehicle_data]
            distances = [row[2] for row in vehicle_data]
            costs = [row[3] for row in vehicle_data]
            
            html_content = self._generate_utilization_chart_html(
                vehicle_ids, vehicle_util, distances, costs
            )
        
        conn.close()
        self.web_view.setHtml(html_content)
    
    def _generate_cost_chart_html(self, timestamps, costs):
        """生成成本曲线详细图表"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
            <style>
                body {{
                    margin: 0;
                    padding: 20px;
                    background-color: #1e1e2e;
                    font-family: "Microsoft YaHei", sans-serif;
                }}
                #main {{
                    width: 100%;
                    height: calc(100vh - 40px);
                }}
            </style>
        </head>
        <body>
            <div id="main"></div>
            <script type="text/javascript">
                var chart = echarts.init(document.getElementById('main'));
                chart.setOption({{
                    title: {{
                        text: '📈 成本曲线详情',
                        left: 'center',
                        textStyle: {{ color: '#cdd6f4', fontSize: 20 }}
                    }},
                    tooltip: {{
                        trigger: 'axis',
                        backgroundColor: '#2a2a3e',
                        borderColor: '#444',
                        textStyle: {{ color: '#cdd6f4' }},
                        formatter: function(params) {{
                            return '时间: ' + params[0].name + '<br/>成本: ¥' + params[0].value.toFixed(2);
                        }}
                    }},
                    grid: {{
                        left: '5%',
                        right: '5%',
                        bottom: '15%',
                        top: '15%',
                        containLabel: true
                    }},
                    xAxis: {{
                        type: 'category',
                        data: {json.dumps(timestamps)},
                        axisLabel: {{
                            color: '#aaa',
                            rotate: 45,
                            formatter: function(value) {{
                                if (!value) return '';
                                var parts = value.split(' ');
                                if (parts.length >= 2) {{
                                    return parts[0].substring(5) + '\\n' + parts[1].substring(0, 5);
                                }}
                                return value;
                            }}
                        }},
                        axisLine: {{ lineStyle: {{ color: '#444' }} }}
                    }},
                    yAxis: {{
                        type: 'value',
                        name: '成本 (¥)',
                        nameTextStyle: {{ color: '#cdd6f4' }},
                        axisLabel: {{
                            color: '#aaa',
                            formatter: '¥{{value}}'
                        }},
                        axisLine: {{ lineStyle: {{ color: '#444' }} }},
                        splitLine: {{ lineStyle: {{ color: '#333' }} }}
                    }},
                    series: [{{
                        name: '成本',
                        type: 'line',
                        data: {json.dumps(costs)},
                        smooth: true,
                        symbol: 'circle',
                        symbolSize: 10,
                        lineStyle: {{
                            color: '#27AE60',
                            width: 3
                        }},
                        itemStyle: {{
                            color: '#27AE60',
                            borderColor: '#fff',
                            borderWidth: 2
                        }},
                        areaStyle: {{
                            color: {{
                                type: 'linear',
                                x: 0, y: 0, x2: 0, y2: 1,
                                colorStops: [
                                    {{ offset: 0, color: 'rgba(39, 174, 96, 0.5)' }},
                                    {{ offset: 1, color: 'rgba(39, 174, 96, 0.05)' }}
                                ]
                            }}
                        }},
                        markPoint: {{
                            data: [
                                {{ type: 'max', name: '最大值' }},
                                {{ type: 'min', name: '最小值' }}
                            ],
                            label: {{ color: '#fff' }}
                        }},
                        markLine: {{
                            data: [{{ type: 'average', name: '平均值' }}],
                            lineStyle: {{ color: '#FFEAA7' }},
                            label: {{ color: '#FFEAA7' }}
                        }}
                    }}]
                }});
                window.addEventListener('resize', function() {{
                    chart.resize();
                }});
            </script>
        </body>
        </html>
        """
    
    def _generate_utilization_chart_html(self, vehicle_ids, vehicle_util, distances, costs):
        """生成车辆利用率详细图表"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
            <style>
                body {{
                    margin: 0;
                    padding: 20px;
                    background-color: #1e1e2e;
                    font-family: "Microsoft YaHei", sans-serif;
                }}
                .container {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 20px;
                    height: calc(100vh - 40px);
                }}
                .chart-box {{
                    background: #2a2a3e;
                    border-radius: 8px;
                    padding: 15px;
                }}
                .chart {{
                    width: 100%;
                    height: calc(100% - 30px);
                }}
                .chart-title {{
                    color: #cdd6f4;
                    font-size: 16px;
                    font-weight: bold;
                    text-align: center;
                    margin-bottom: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="chart-box">
                    <div class="chart-title">🚛 车辆利用率 (%)</div>
                    <div id="chart1" class="chart"></div>
                </div>
                <div class="chart-box">
                    <div class="chart-title">📏 配送距离 (km)</div>
                    <div id="chart2" class="chart"></div>
                </div>
                <div class="chart-box">
                    <div class="chart-title">💰 车辆成本 (¥)</div>
                    <div id="chart3" class="chart"></div>
                </div>
                <div class="chart-box">
                    <div class="chart-title">📊 综合对比</div>
                    <div id="chart4" class="chart"></div>
                </div>
            </div>
            <script type="text/javascript">
                var colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F39C12', '#9B59B6', '#1ABC9C'];
                
                // 图表1: 车辆利用率
                var chart1 = echarts.init(document.getElementById('chart1'));
                chart1.setOption({{
                    tooltip: {{
                        trigger: 'axis',
                        formatter: '{{b}}: {{c}}%',
                        backgroundColor: '#2a2a3e',
                        borderColor: '#444',
                        textStyle: {{ color: '#cdd6f4' }}
                    }},
                    grid: {{ left: '3%', right: '4%', bottom: '3%', containLabel: true }},
                    xAxis: {{
                        type: 'category',
                        data: {json.dumps(vehicle_ids)},
                        axisLabel: {{ color: '#aaa', interval: 0, rotate: 30 }},
                        axisLine: {{ lineStyle: {{ color: '#444' }} }}
                    }},
                    yAxis: {{
                        type: 'value',
                        max: 100,
                        axisLabel: {{ color: '#aaa', formatter: '{{value}}%' }},
                        axisLine: {{ lineStyle: {{ color: '#444' }} }},
                        splitLine: {{ lineStyle: {{ color: '#333' }} }}
                    }},
                    series: [{{
                        type: 'bar',
                        data: {json.dumps(vehicle_util)},
                        itemStyle: {{
                            color: function(params) {{
                                var color = colors[params.dataIndex % colors.length];
                                return {{
                                    type: 'linear',
                                    x: 0, y: 0, x2: 0, y2: 1,
                                    colorStops: [
                                        {{ offset: 0, color: color }},
                                        {{ offset: 1, color: color + '80' }}
                                    ]
                                }};
                            }},
                            borderRadius: [5, 5, 0, 0]
                        }},
                        label: {{
                            show: true,
                            position: 'top',
                            formatter: '{{c}}%',
                            color: '#cdd6f4'
                        }}
                    }}]
                }});
                
                // 图表2: 配送距离
                var chart2 = echarts.init(document.getElementById('chart2'));
                chart2.setOption({{
                    tooltip: {{
                        trigger: 'axis',
                        backgroundColor: '#2a2a3e',
                        borderColor: '#444',
                        textStyle: {{ color: '#cdd6f4' }}
                    }},
                    grid: {{ left: '3%', right: '4%', bottom: '3%', containLabel: true }},
                    xAxis: {{
                        type: 'category',
                        data: {json.dumps(vehicle_ids)},
                        axisLabel: {{ color: '#aaa', interval: 0, rotate: 30 }},
                        axisLine: {{ lineStyle: {{ color: '#444' }} }}
                    }},
                    yAxis: {{
                        type: 'value',
                        name: 'km',
                        nameTextStyle: {{ color: '#aaa' }},
                        axisLabel: {{ color: '#aaa' }},
                        axisLine: {{ lineStyle: {{ color: '#444' }} }},
                        splitLine: {{ lineStyle: {{ color: '#333' }} }}
                    }},
                    series: [{{
                        type: 'bar',
                        data: {json.dumps(distances)},
                        itemStyle: {{
                            color: {{
                                type: 'linear',
                                x: 0, y: 0, x2: 0, y2: 1,
                                colorStops: [
                                    {{ offset: 0, color: '#3498DB' }},
                                    {{ offset: 1, color: '#3498DB80' }}
                                ]
                            }},
                            borderRadius: [5, 5, 0, 0]
                        }},
                        label: {{
                            show: true,
                            position: 'top',
                            formatter: '{{c}} km',
                            color: '#cdd6f4'
                        }}
                    }}]
                }});
                
                // 图表3: 车辆成本
                var chart3 = echarts.init(document.getElementById('chart3'));
                chart3.setOption({{
                    tooltip: {{
                        trigger: 'axis',
                        backgroundColor: '#2a2a3e',
                        borderColor: '#444',
                        textStyle: {{ color: '#cdd6f4' }}
                    }},
                    grid: {{ left: '3%', right: '4%', bottom: '3%', containLabel: true }},
                    xAxis: {{
                        type: 'category',
                        data: {json.dumps(vehicle_ids)},
                        axisLabel: {{ color: '#aaa', interval: 0, rotate: 30 }},
                        axisLine: {{ lineStyle: {{ color: '#444' }} }}
                    }},
                    yAxis: {{
                        type: 'value',
                        name: '¥',
                        nameTextStyle: {{ color: '#aaa' }},
                        axisLabel: {{ color: '#aaa', formatter: '¥{{value}}' }},
                        axisLine: {{ lineStyle: {{ color: '#444' }} }},
                        splitLine: {{ lineStyle: {{ color: '#333' }} }}
                    }},
                    series: [{{
                        type: 'bar',
                        data: {json.dumps(costs)},
                        itemStyle: {{
                            color: function(params) {{
                                var color = colors[params.dataIndex % colors.length];
                                return {{
                                    type: 'linear',
                                    x: 0, y: 0, x2: 0, y2: 1,
                                    colorStops: [
                                        {{ offset: 0, color: color }},
                                        {{ offset: 1, color: color + '80' }}
                                    ]
                                }};
                            }},
                            borderRadius: [5, 5, 0, 0]
                        }},
                        label: {{
                            show: true,
                            position: 'top',
                            formatter: '¥{{c}}',
                            color: '#cdd6f4'
                        }}
                    }}]
                }});
                
                // 图表4: 综合对比（雷达图）
                var chart4 = echarts.init(document.getElementById('chart4'));
                var maxUtil = Math.max(...{json.dumps(vehicle_util)});
                var maxDist = Math.max(...{json.dumps(distances)});
                var maxCost = Math.max(...{json.dumps(costs)});
                var radarData = {json.dumps(vehicle_ids)}.map((id, idx) => ({{
                    value: [
                        {json.dumps(vehicle_util)}[idx],
                        maxDist > 0 ? ({json.dumps(distances)}[idx] / maxDist * 100) : 0,
                        maxCost > 0 ? ({json.dumps(costs)}[idx] / maxCost * 100) : 0
                    ],
                    name: id
                }}));
                chart4.setOption({{
                    tooltip: {{
                        backgroundColor: '#2a2a3e',
                        borderColor: '#444',
                        textStyle: {{ color: '#cdd6f4' }}
                    }},
                    legend: {{
                        data: {json.dumps(vehicle_ids)},
                        textStyle: {{ color: '#aaa' }},
                        bottom: 0,
                        type: 'scroll'
                    }},
                    radar: {{
                        indicator: [
                            {{ name: '利用率', max: 100 }},
                            {{ name: '距离占比', max: 100 }},
                            {{ name: '成本占比', max: 100 }}
                        ],
                        axisName: {{ color: '#aaa' }},
                        splitArea: {{ areaStyle: {{ color: ['#2a2a3e', '#1e1e2e'] }} }},
                        axisLine: {{ lineStyle: {{ color: '#444' }} }},
                        splitLine: {{ lineStyle: {{ color: '#444' }} }}
                    }},
                    series: [{{
                        type: 'radar',
                        data: radarData,
                        areaStyle: {{ opacity: 0.3 }}
                    }}]
                }});
                
                window.addEventListener('resize', function() {{
                    chart1.resize();
                    chart2.resize();
                    chart3.resize();
                    chart4.resize();
                }});
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
            orders = [('已完成', len(vehicle_ids)), ('配送中', 0), ('待处理', 0)]
        status_list = [row[0] for row in orders]
        count_list = [row[1] for row in orders]
        
        conn.close()
        
        # 构建概览页面 HTML
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
            <style>
                body {{
                    margin: 0;
                    padding: 10px;
                    background-color: #1e1e2e;
                    font-family: "Microsoft YaHei", sans-serif;
                }}
                .chart-container {{
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    grid-template-rows: 1fr 1fr;
                    gap: 15px;
                    height: calc(100vh - 100px);
                }}
                .chart-box {{
                    background: #2a2a3e;
                    border-radius: 8px;
                    padding: 10px;
                    cursor: pointer;
                    transition: transform 0.2s;
                }}
                .chart-box:hover {{
                    transform: scale(1.02);
                }}
                .chart-title {{
                    color: #cdd6f4;
                    font-size: 14px;
                    font-weight: bold;
                    margin-bottom: 10px;
                    text-align: center;
                }}
                .chart {{
                    width: 100%;
                    height: calc(100% - 40px);
                }}
                .hint {{
                    color: #888;
                    font-size: 11px;
                    text-align: center;
                    margin-top: 5px;
                }}
            </style>
        </head>
        <body>
            <div class="chart-container">
                <div class="chart-box">
                    <div class="chart-title">📊 订单统计</div>
                    <div id="chart1" class="chart"></div>
                </div>
                <div class="chart-box" onclick="window.pybridge && window.pybridge.openCostDetail()">
                    <div class="chart-title">📈 成本曲线</div>
                    <div id="chart2" class="chart"></div>
                    <div class="hint">点击查看详情</div>
                </div>
                <div class="chart-box" onclick="window.pybridge && window.pybridge.openUtilDetail()">
                    <div class="chart-title">🚛 车辆利用率 (%)</div>
                    <div id="chart3" class="chart"></div>
                    <div class="hint">点击查看详情</div>
                </div>
                <div class="chart-box">
                    <div class="chart-title">📋 数据概览</div>
                    <div id="chart4" class="chart"></div>
                </div>
            </div>
            <script type="text/javascript">
                // 图表1: 订单统计
                var chart1 = echarts.init(document.getElementById('chart1'));
                chart1.setOption({{
                    tooltip: {{ trigger: 'axis' }},
                    grid: {{ left: '3%', right: '4%', bottom: '3%', containLabel: true }},
                    xAxis: {{ 
                        type: 'category', 
                        data: {json.dumps(status_list)},
                        axisLabel: {{ color: '#aaa', rotate: 30 }}
                    }},
                    yAxis: {{ 
                        type: 'value',
                        axisLabel: {{ color: '#aaa' }}
                    }},
                    series: [{{
                        name: '订单数',
                        type: 'bar',
                        data: {json.dumps(count_list)},
                        itemStyle: {{ color: '#3498DB' }}
                    }}]
                }});

                // 图表2: 成本曲线
                var chart2 = echarts.init(document.getElementById('chart2'));
                chart2.setOption({{
                    tooltip: {{ trigger: 'axis' }},
                    grid: {{ left: '3%', right: '4%', bottom: '15%', containLabel: true }},
                    xAxis: {{ 
                        type: 'category', 
                        data: {json.dumps(timestamps)},
                        axisLabel: {{ 
                            color: '#aaa',
                            rotate: 45,
                            formatter: function(value) {{
                                if (!value) return '';
                                var parts = value.split(' ');
                                if (parts.length >= 2) {{
                                    return parts[0].substring(5) + '\\n' + parts[1].substring(0, 5);
                                }}
                                return value;
                            }}
                        }}
                    }},
                    yAxis: {{ 
                        type: 'value',
                        axisLabel: {{ color: '#aaa' }}
                    }},
                    series: [{{
                        name: '成本',
                        type: 'line',
                        data: {json.dumps(costs)},
                        smooth: true,
                        itemStyle: {{ color: '#27AE60' }},
                        areaStyle: {{ opacity: 0.3 }}
                    }}]
                }});

                // 图表3: 车辆利用率
                var chart3 = echarts.init(document.getElementById('chart3'));
                chart3.setOption({{
                    tooltip: {{ 
                        trigger: 'axis',
                        formatter: '{{b}}: {{c}}%'
                    }},
                    grid: {{ left: '3%', right: '4%', bottom: '3%', containLabel: true }},
                    xAxis: {{ 
                        type: 'category', 
                        data: {json.dumps(vehicle_ids)},
                        axisLabel: {{ color: '#aaa' }}
                    }},
                    yAxis: {{ 
                        type: 'value',
                        max: 100,
                        axisLabel: {{ 
                            color: '#aaa',
                            formatter: '{{value}}%'
                        }}
                    }},
                    series: [{{
                        name: '利用率',
                        type: 'bar',
                        data: {json.dumps(vehicle_util)},
                        itemStyle: {{ 
                            color: function(params) {{
                                var colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F39C12'];
                                return colors[params.dataIndex % colors.length];
                            }}
                        }}
                    }}]
                }});

                // 图表4: 综合数据表格
                var chart4 = echarts.init(document.getElementById('chart4'));
                var totalOrders = {sum(count_list) if count_list else 0};
                var totalCost = {sum(costs) if costs else 0};
                var avgUtil = {sum(vehicle_util)/len(vehicle_util) if vehicle_util else 0};
                chart4.setOption({{
                    tooltip: {{ trigger: 'item' }},
                    series: [{{
                        type: 'gauge',
                        startAngle: 180,
                        endAngle: 0,
                        min: 0,
                        max: 100,
                        splitNumber: 5,
                        axisLine: {{
                            lineStyle: {{
                                width: 6,
                                color: [
                                    [0.3, '#FF6B6B'],
                                    [0.7, '#FFEAA7'],
                                    [1, '#27AE60']
                                ]
                            }}
                        }},
                        pointer: {{
                            icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
                            length: '12%',
                            width: 10,
                            offsetCenter: [0, '-60%'],
                            itemStyle: {{ color: 'auto' }}
                        }},
                        axisTick: {{ length: 12, lineStyle: {{ color: 'auto', width: 2 }} }},
                        splitLine: {{ length: 20, lineStyle: {{ color: 'auto', width: 5 }} }},
                        axisLabel: {{
                            color: '#aaa',
                            fontSize: 12,
                            distance: -50,
                            formatter: function(value) {{
                                if (value === 0) return '低';
                                if (value === 50) return '中';
                                if (value === 100) return '高';
                                return '';
                            }}
                        }},
                        title: {{
                            offsetCenter: [0, '-35%'],
                            fontSize: 14,
                            color: '#cdd6f4'
                        }},
                        detail: {{
                            fontSize: 18,
                            offsetCenter: [0, '10%'],
                            valueAnimation: true,
                            formatter: function(value) {{
                                return '平均利用率\\n' + Math.round(value) + '%';
                            }},
                            color: '#cdd6f4'
                        }},
                        data: [{{ value: avgUtil, name: '车辆效率' }}]
                    }}]
                }});

                // 响应窗口大小变化
                window.addEventListener('resize', function() {{
                    chart1.resize();
                    chart2.resize();
                    chart3.resize();
                    chart4.resize();
                }});
            </script>
        </body>
        </html>
        """
        self.web_view.setHtml(html_content)
