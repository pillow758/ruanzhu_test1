import json
import sqlite3
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QFrame, QStackedWidget
)
from PyQt6.QtCore import QTimer, Qt, pyqtSlot, QObject
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel

DB_PATH = os.path.join(os.path.dirname(__file__), "database/logistics.db")
DB_PATH = os.path.abspath(DB_PATH)


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
        
        self.web_view.setHtml(html_content)
    
    def _generate_single_chart_html(self, title, data, unit, colors, max_val):
        max_val_str = f"max: {max_val}," if max_val else ""
        unit_formatter = f"formatter: '{{value}}{unit}'," if not unit.startswith('¥') else "formatter: (val) => '¥' + val,"
        label_formatter = f"formatter: (params) => params.value.toFixed(2) + '{unit}',"
        tooltip_formatter = f"formatter: (params) => params[0].name + ': ' + params[0].value.toFixed(2) + '{unit}',"
        
        if unit.startswith('¥'):
            label_formatter = "formatter: (params) => '¥' + params.value.toFixed(2),"
            tooltip_formatter = "formatter: (params) => params[0].name + ': ¥' + params[0].value.toFixed(2),"
        
        color_func = ""
        if len(colors) > 1:
            color_func = """
                            color: function(params) {
                                var colorList = %s;
                                var color = colorList[params.dataIndex %% colorList.length];
                                return {
                                    type: 'linear',
                                    x: 0, y: 0, x2: 0, y2: 1,
                                    colorStops: [
                                        { offset: 0, color: color },
                                        { offset: 1, color: color + '80' }
                                    ]
                                };
                            },
            """ % json.dumps(colors)
        else:
            color_func = """
                            color: {
                                type: 'linear',
                                x: 0, y: 0, x2: 0, y2: 1,
                                colorStops: [
                                    { offset: 0, color: '%s' },
                                    { offset: 1, color: '%s80' }
                                ]
                            },
            """ % (colors[0], colors[0])
        
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
                        text: '{title}',
                        left: 'center',
                        textStyle: {{ color: '#cdd6f4', fontSize: 24, fontWeight: 'bold' }}
                    }},
                    tooltip: {{
                        trigger: 'axis',
                        backgroundColor: '#2a2a3e',
                        borderColor: '#444',
                        textStyle: {{ color: '#cdd6f4' }},
                        {tooltip_formatter}
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
                        data: {json.dumps(self.vehicle_ids)},
                        axisLabel: {{ 
                            color: '#aaa', 
                            interval: 0, 
                            rotate: 45,
                            fontSize: 14
                        }},
                        axisLine: {{ lineStyle: {{ color: '#444', width: 2 }} }}
                    }},
                    yAxis: {{
                        type: 'value',
                        {max_val_str}
                        axisLabel: {{ 
                            color: '#aaa', 
                            fontSize: 14,
                            {unit_formatter}
                        }},
                        axisLine: {{ lineStyle: {{ color: '#444', width: 2 }} }},
                        splitLine: {{ lineStyle: {{ color: '#333' }} }}
                    }},
                    series: [{{
                        type: 'bar',
                        data: {json.dumps(data)},
                        barWidth: '50%',
                        itemStyle: {{
                            {color_func}
                            borderRadius: [8, 8, 0, 0]
                        }},
                        label: {{
                            show: true,
                            position: 'top',
                            {label_formatter}
                            color: '#cdd6f4',
                            fontSize: 14,
                            fontWeight: 'bold'
                        }},
                        markPoint: {{
                            data: [
                                {{ type: 'max', name: '最大值' }},
                                {{ type: 'min', name: '最小值' }}
                            ],
                            label: {{ color: '#fff', fontSize: 12 }}
                        }},
                        markLine: {{
                            data: [{{ type: 'average', name: '平均值' }}],
                            lineStyle: {{ color: '#FFEAA7', width: 2 }},
                            label: {{ color: '#FFEAA7', fontSize: 12 }}
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
            
            html_content = self._generate_cost_chart_html(timestamps, costs)
        else:  # utilization
            # 车辆利用率详细数据
            cursor.execute("SELECT vehicle_id, q, distance, cost FROM routes")
            vehicle_data = cursor.fetchall()
            self.vehicle_ids = [row[0] for row in vehicle_data]
            self.vehicle_util = [min(row[1]/3000,1)*100 for row in vehicle_data]
            self.distances = [row[2] for row in vehicle_data]
            self.costs = [row[3] for row in vehicle_data]
            
            html_content = self._generate_utilization_chart_html(
                self.vehicle_ids, self.vehicle_util, self.distances, self.costs
            )
        
        conn.close()
        self.web_view.setHtml(html_content)
    
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
        # 格式化数据保留两位小数
        vehicle_util_formatted = [round(x, 2) for x in vehicle_util]
        distances_formatted = [round(x, 2) for x in distances]
        costs_formatted = [round(x, 2) for x in costs]
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
                    grid-template-rows: 1fr 1fr;
                    gap: 20px;
                    height: calc(100vh - 40px);
                }}
                .chart-box {{
                    background: #2a2a3e;
                    border-radius: 8px;
                    padding: 15px;
                    display: flex;
                    flex-direction: column;
                    min-height: 0;
                }}
                .chart {{
                    width: 100%;
                    flex: 1;
                    min-height: 0;
                }}
                .chart-title {{
                    color: #cdd6f4;
                    font-size: 16px;
                    font-weight: bold;
                    text-align: center;
                    margin-bottom: 10px;
                    flex-shrink: 0;
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
                        formatter: function(params) {{
                            return params[0].name + ': ' + params[0].value.toFixed(2) + '%';
                        }},
                        backgroundColor: '#2a2a3e',
                        borderColor: '#444',
                        textStyle: {{ color: '#cdd6f4' }}
                    }},
                    grid: {{ left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true }},
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
                        data: {json.dumps(vehicle_util_formatted)},
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
                            formatter: function(params) {{
                                return params.value.toFixed(2) + '%';
                            }},
                            color: '#cdd6f4',
                            fontSize: 12
                        }}
                    }}]
                }});

                // 图表2: 配送距离
                var chart2 = echarts.init(document.getElementById('chart2'));
                chart2.setOption({{
                    tooltip: {{
                        trigger: 'axis',
                        formatter: function(params) {{
                            return params[0].name + ': ' + params[0].value.toFixed(2) + ' km';
                        }},
                        backgroundColor: '#2a2a3e',
                        borderColor: '#444',
                        textStyle: {{ color: '#cdd6f4' }}
                    }},
                    grid: {{ left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true }},
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
                        data: {json.dumps(distances_formatted)},
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
                            formatter: function(params) {{
                                return params.value.toFixed(2) + ' km';
                            }},
                            color: '#cdd6f4',
                            fontSize: 12
                        }}
                    }}]
                }});

                // 图表3: 车辆成本
                var chart3 = echarts.init(document.getElementById('chart3'));
                chart3.setOption({{
                    tooltip: {{
                        trigger: 'axis',
                        formatter: function(params) {{
                            return params[0].name + ': ¥' + params[0].value.toFixed(2);
                        }},
                        backgroundColor: '#2a2a3e',
                        borderColor: '#444',
                        textStyle: {{ color: '#cdd6f4' }}
                    }},
                    grid: {{ left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true }},
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
                        data: {json.dumps(costs_formatted)},
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
                            formatter: function(params) {{
                                return '¥' + params.value.toFixed(2);
                            }},
                            color: '#cdd6f4',
                            fontSize: 12
                        }}
                    }}]
                }});

                // 图表4: 综合对比（雷达图）
                var chart4 = echarts.init(document.getElementById('chart4'));
                var maxUtil = Math.max(...{json.dumps(vehicle_util_formatted)});
                var maxDist = Math.max(...{json.dumps(distances_formatted)});
                var maxCost = Math.max(...{json.dumps(costs_formatted)});
                var radarData = {json.dumps(vehicle_ids)}.map((id, idx) => {{
                    var utilVal = {json.dumps(vehicle_util_formatted)}[idx];
                    var distVal = maxDist > 0 ? ({json.dumps(distances_formatted)}[idx] / maxDist * 100) : 0;
                    var costVal = maxCost > 0 ? ({json.dumps(costs_formatted)}[idx] / maxCost * 100) : 0;
                    return {{
                        value: [
                            parseFloat(utilVal.toFixed(2)),
                            parseFloat(distVal.toFixed(2)),
                            parseFloat(costVal.toFixed(2))
                        ],
                        name: id
                    }};
                }});
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
                        type: 'scroll',
                        itemWidth: 15,
                        itemHeight: 10
                    }},
                    radar: {{
                        indicator: [
                            {{ name: '利用率', max: 100 }},
                            {{ name: '距离占比', max: 100 }},
                            {{ name: '成本占比', max: 100 }}
                        ],
                        axisName: {{ color: '#aaa', fontSize: 12 }},
                        splitArea: {{ areaStyle: {{ color: ['#2a2a3e', '#1e1e2e'] }} }},
                        axisLine: {{ lineStyle: {{ color: '#444' }} }},
                        splitLine: {{ lineStyle: {{ color: '#444' }} }},
                        radius: '68%',
                        center: ['50%', '45%']
                    }},
                    series: [{{
                        type: 'radar',
                        data: radarData,
                        areaStyle: {{ opacity: 0.3 }},
                        label: {{
                            show: false
                        }}
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
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script type="text/javascript">
                // 初始化 QWebChannel
                new QWebChannel(qt.webChannelTransport, function(channel) {{
                    window.pybridge = channel.objects.pybridge;
                }});
            </script>
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
