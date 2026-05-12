# echarts_window.py
import json
import sqlite3
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import QTimer
from PyQt6.QtWebEngineWidgets import QWebEngineView

DB_PATH = os.path.join(os.path.dirname(__file__), "database/logistics.db")
DB_PATH = os.path.abspath(DB_PATH)

class EChartsAnalysis(QWidget):
    """集成 ECharts 数据分析窗口"""
    def __init__(self, parent=None, refresh_interval=5000):
        super().__init__(parent)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # WebEngine 显示 ECharts
        self.web_view = QWebEngineView()
        self.layout.addWidget(self.web_view)

        # 设置刷新定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.load_chart)
        self.timer.start(refresh_interval)  # 默认每 5 秒刷新一次

        # 首次加载
        self.load_chart()

    def load_chart(self):
        """从 SQLite 读取数据，生成 ECharts 图表"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1️⃣ 先读取车辆数据（因为订单统计可能需要用到）
        cursor.execute("SELECT vehicle_id, q FROM routes")
        vehicle_data = cursor.fetchall()
        vehicle_ids = [row[0] for row in vehicle_data]
        vehicle_util = [min(row[1]/3000,1)*100 for row in vehicle_data]

        # 2️⃣ 成本曲线（按时间排序）
        cursor.execute("SELECT timestamp, cost FROM routes ORDER BY timestamp")
        cost_data = cursor.fetchall()
        timestamps = [row[0] for row in cost_data]
        costs = [row[1] for row in cost_data]

        # 3️⃣ 订单统计（按状态）- 如果没有orders表或数据，使用routes表作为备选
        try:
            cursor.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
            orders = cursor.fetchall()
        except:
            orders = []
        # 如果没有订单数据，从routes生成模拟数据
        if not orders:
            orders = [('已完成', len(vehicle_ids)), ('配送中', 0), ('待处理', 0)]
        status_list = [row[0] for row in orders]
        count_list = [row[1] for row in orders]

        conn.close()

        # 构建 HTML 页面 - 使用网格布局，每个图表独立
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
                    height: calc(100vh - 20px);
                }}
                .chart-box {{
                    background: #2a2a3e;
                    border-radius: 8px;
                    padding: 10px;
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
            </style>
        </head>
        <body>
            <div class="chart-container">
                <div class="chart-box">
                    <div class="chart-title">📊 订单统计</div>
                    <div id="chart1" class="chart"></div>
                </div>
                <div class="chart-box">
                    <div class="chart-title">📈 成本曲线</div>
                    <div id="chart2" class="chart"></div>
                </div>
                <div class="chart-box">
                    <div class="chart-title">🚛 车辆利用率 (%)</div>
                    <div id="chart3" class="chart"></div>
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