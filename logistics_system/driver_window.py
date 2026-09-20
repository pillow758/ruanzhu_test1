import os
# 获取当前脚本所在目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 构建数据库绝对路径
DB_PATH = os.path.join(BASE_DIR, "database", "logistics.db")
import sys
import sqlite3
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QFrame, QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
import pyqtgraph as pg

from database.db_manager import get_all_routes, get_all_customers_nodes

COLORS = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F39C12', '#9B59B6', '#1ABC9C']

class DriverWindow(QMainWindow):
    def __init__(self, username):
        super().__init__()
        self.username = username
        self.setWindowTitle(f"驾驶员工作台 - {username}")
        self.setGeometry(100, 100, 1400, 800)
        self.init_ui()
        self.apply_dark_theme()

        # 动画状态
        self.vehicle_pos = 0.0
        self.vehicle_color = COLORS[0]
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)

        # 初始化数据
        self.load_all_data()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 左侧控制面板
        left_panel = QFrame()
        left_panel.setFixedWidth(360)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        # ========== 司机信息卡片 ==========
        driver_card = QFrame()
        driver_card.setStyleSheet("""
            QFrame {
                background-color: #2a2a3e;
                border-radius: 12px;
                border: 1px solid #3b82f6;
                padding: 5px;
            }
        """)
        driver_layout = QVBoxLayout(driver_card)
        driver_layout.setSpacing(10)
        driver_layout.setContentsMargins(15, 15, 15, 15)
        
        # 司机标题
        driver_title = QLabel("👤 司机信息")
        driver_title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        driver_title.setStyleSheet("color: #3b82f6;")
        driver_layout.addWidget(driver_title)
        
        # 司机信息网格
        info_grid = QVBoxLayout()
        info_grid.setSpacing(8)
        
        # 姓名
        name_layout = QHBoxLayout()
        name_icon = QLabel("👤")
        name_icon.setFont(QFont("Microsoft YaHei", 14))
        name_layout.addWidget(name_icon)
        name_label = QLabel("姓名：")
        name_label.setFont(QFont("Microsoft YaHei", 11))
        name_label.setStyleSheet("color: #aaa;")
        name_layout.addWidget(name_label)
        self.driver_name = QLabel("张三")
        self.driver_name.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        self.driver_name.setStyleSheet("color: #cdd6f4;")
        name_layout.addWidget(self.driver_name)
        name_layout.addStretch()
        info_grid.addLayout(name_layout)
        
        # 电话
        phone_layout = QHBoxLayout()
        phone_icon = QLabel("📞")
        phone_icon.setFont(QFont("Microsoft YaHei", 14))
        phone_layout.addWidget(phone_icon)
        phone_label = QLabel("电话：")
        phone_label.setFont(QFont("Microsoft YaHei", 11))
        phone_label.setStyleSheet("color: #aaa;")
        phone_layout.addWidget(phone_label)
        self.driver_phone = QLabel("13800000000")
        self.driver_phone.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        self.driver_phone.setStyleSheet("color: #cdd6f4;")
        phone_layout.addWidget(self.driver_phone)
        phone_layout.addStretch()
        info_grid.addLayout(phone_layout)
        
        # 状态
        status_layout = QHBoxLayout()
        status_icon = QLabel("🟢")
        status_icon.setFont(QFont("Microsoft YaHei", 14))
        status_layout.addWidget(status_icon)
        status_label = QLabel("状态：")
        status_label.setFont(QFont("Microsoft YaHei", 11))
        status_label.setStyleSheet("color: #aaa;")
        status_layout.addWidget(status_label)
        self.driver_status = QLabel("在线")
        self.driver_status.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        self.driver_status.setStyleSheet("color: #27AE60;")
        status_layout.addWidget(self.driver_status)
        status_layout.addStretch()
        info_grid.addLayout(status_layout)
        
        # 配送次数
        delivery_layout = QHBoxLayout()
        delivery_icon = QLabel("📦")
        delivery_icon.setFont(QFont("Microsoft YaHei", 14))
        delivery_layout.addWidget(delivery_icon)
        delivery_label = QLabel("配送次数：")
        delivery_label.setFont(QFont("Microsoft YaHei", 11))
        delivery_label.setStyleSheet("color: #aaa;")
        delivery_layout.addWidget(delivery_label)
        self.delivery_count = QLabel("15")
        self.delivery_count.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        self.delivery_count.setStyleSheet("color: #3b82f6;")
        delivery_layout.addWidget(self.delivery_count)
        delivery_layout.addStretch()
        info_grid.addLayout(delivery_layout)
        
        # 今日任务
        task_layout = QHBoxLayout()
        task_icon = QLabel("🚚")
        task_icon.setFont(QFont("Microsoft YaHei", 14))
        task_layout.addWidget(task_icon)
        task_label = QLabel("今日任务：")
        task_label.setFont(QFont("Microsoft YaHei", 11))
        task_label.setStyleSheet("color: #aaa;")
        task_layout.addWidget(task_label)
        self.today_tasks = QLabel("3")
        self.today_tasks.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        self.today_tasks.setStyleSheet("color: #F39C12;")
        task_layout.addWidget(self.today_tasks)
        task_layout.addStretch()
        info_grid.addLayout(task_layout)
        
        driver_layout.addLayout(info_grid)
        left_layout.addWidget(driver_card)
        
        # 分隔线
        left_layout.addSpacing(10)

        # 标题
        title = QLabel("🚚 我的配送任务")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title)

        # 车辆选择下拉框
        self.vehicle_select = QComboBox()
        self.vehicle_select.setFont(QFont("Microsoft YaHei", 10))
        self.vehicle_select.setStyleSheet("""
            QComboBox {
                background-color: #2a2a3e;
                color: white;
                border-radius: 8px;
                padding: 10px;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 8px solid #60a5fa;
                width: 0;
                height: 0;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background: #2a2a3e;
                border: 1px solid #3b82f6;
                border-radius: 8px;
                color: white;
                selection-background-color: #3b82f6;
                outline: none;
                margin: 0;
                padding: 0;
            }
            QComboBox QAbstractItemView::item {
                background: #2a2a3e;
                color: white;
                padding: 8px 16px;
                min-height: 32px;
            }
            QComboBox QAbstractItemView::item:hover {
                background: #3b82f6;
                color: white;
            }
            QComboBox QAbstractItemView::item:selected {
                background: #3b82f6;
                color: white;
            }
        """)
        self.vehicle_select.currentIndexChanged.connect(self.on_vehicle_changed)
        left_layout.addWidget(self.vehicle_select)

        # 统计信息
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background-color: #2a2a3e; border-radius: 8px; padding: 10px;")
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setSpacing(5)

        stats_title = QLabel("📊 任务详情")
        stats_title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        stats_layout.addWidget(stats_title)

        self.lbl_load = QLabel("📦 载重: 0 kg")
        self.lbl_dist = QLabel("📏 距离: 0 km")
        self.lbl_cost = QLabel("💰 成本: ¥ 0")
        for lbl in (self.lbl_load, self.lbl_dist, self.lbl_cost):
            lbl.setFont(QFont("Microsoft YaHei", 9))
            stats_layout.addWidget(lbl)
        left_layout.addWidget(stats_frame)

        # 车辆详情表格
        table_label = QLabel("🚚 路线详情")
        table_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        left_layout.addWidget(table_label)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["车辆", "载重(kg)", "距离(km)", "成本(¥)", "路径"])
        self.table.horizontalHeader().setSectionResizeMode(4, pg.QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #2a2a3e;
                gridline-color: #444;
                color: #e0e0e0;
                font: 9pt "Microsoft YaHei";
            }
            QHeaderView::section {
                background-color: #1e1e2e;
                color: #ccc;
                padding: 4px;
                border: 1px solid #444;
            }
        """)
        left_layout.addWidget(self.table, 1)

        layout.addWidget(left_panel)

        # 右侧动画面板
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#1e1e2e')
        self.plot_widget.setLabel('left', 'Y 坐标 (km)', color='#ccc')
        self.plot_widget.setLabel('bottom', 'X 坐标 (km)', color='#ccc')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setRange(xRange=[-2, 42], yRange=[-2, 42])
        right_layout.addWidget(self.plot_widget, 1)

        layout.addWidget(right_panel, 1)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #12121a;
            }
            QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: "Microsoft YaHei";
            }
            QFrame {
                background-color: #1e1e2e;
                border: 1px solid #333;
                border-radius: 10px;
            }
            QLabel {
                background-color: transparent;
            }
        """)

    def load_all_data(self):
        # 1. 读取所有节点（包括DC）
        self.nodes = {'DC': (20, 20)}
        for nid, x, y, q in get_all_customers_nodes():
            self.nodes[nid] = (x, y)

        # 2. 读取所有路线
        self.routes = get_all_routes()
        self.vehicle_select.clear()
        for idx, (vid, *_ ) in enumerate(self.routes):
            self.vehicle_select.addItem(vid)

        # 默认显示第一条路线
        if self.routes:
            self.on_vehicle_changed(0)

    def on_vehicle_changed(self, index):
        if not self.routes:
            return

        # 重置动画状态
        self.vehicle_pos = 0.0
        self.vehicle_color = COLORS[index % len(COLORS)]

        # 更新统计信息
        vid, q, dis, cost, nodes_str = self.routes[index]
        self.lbl_load.setText(f"📦 载重: {q:.0f} kg")
        self.lbl_dist.setText(f"📏 距离: {dis:.1f} km")
        self.lbl_cost.setText(f"💰 成本: ¥ {cost:.1f}")

        # 更新表格
        self.table.setRowCount(1)
        path_str = nodes_str[:30] + ("…" if len(nodes_str) > 30 else "")
        items = [
            QTableWidgetItem(vid),
            QTableWidgetItem(f"{q:.0f}"),
            QTableWidgetItem(f"{dis:.1f}"),
            QTableWidgetItem(f"¥{cost:.1f}"),
            QTableWidgetItem(path_str),
        ]
        for col, item in enumerate(items):
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(0, col, item)

        # 开始动画
        self.timer.start(50)
        # 记录配送开始时间
        self.start_delivery()

    def update_plot(self):
        if not self.routes:
            return

        # 获取当前车辆路线
        current_index = self.vehicle_select.currentIndex()
        vid, q, dis, cost, nodes_str = self.routes[current_index]
        node_list = nodes_str.split(" → ")

        # 清空并重绘
        self.plot_widget.clear()

        # 1. 绘制配送中心
        dc = self.nodes['DC']
        dc_item = pg.ScatterPlotItem(
            [dc[0]], [dc[1]], symbol='s', size=20,
            pen=pg.mkPen(color='#FFD700', width=3), brush=pg.mkBrush('#2C3E50')
        )
        self.plot_widget.addItem(dc_item)
        dc_text = pg.TextItem('DC', color='#FFD700', anchor=(0.5, -0.5))
        dc_text.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        dc_text.setPos(dc[0], dc[1] + 0.8)
        self.plot_widget.addItem(dc_text)

        # 2. 绘制所有客户点
        client_x, client_y, client_labels = [], [], []
        for name, (x, y) in self.nodes.items():
            if name == 'DC':
                continue
            client_x.append(x)
            client_y.append(y)
            client_labels.append((x, y, f'{name}'))
        clients = pg.ScatterPlotItem(
            client_x, client_y, symbol='o', size=12,
            pen=pg.mkPen(color='white', width=1.5), brush=pg.mkBrush('#3498DB')
        )
        self.plot_widget.addItem(clients)
        for x, y, text in client_labels:
            label = pg.TextItem(text, color='#b0b0b0', anchor=(0.5, -0.5))
            label.setFont(QFont('Microsoft YaHei', 8))
            label.setPos(x, y + 0.5)
            self.plot_widget.addItem(label)

        # 3. 绘制路线与车辆动画
        xs = [self.nodes[nid][0] for nid in node_list]
        ys = [self.nodes[nid][1] for nid in node_list]
        color = self.vehicle_color

        # 路线（半透明虚线）
        line = pg.PlotDataItem(xs, ys, pen=pg.mkPen(color, width=2, style=Qt.PenStyle.DashLine), symbol=None)
        self.plot_widget.addItem(line)

        # 沿途节点小点
        if len(xs) > 2:
            mid_points = pg.ScatterPlotItem(
                xs[1:-1], ys[1:-1], symbol='o', size=8,
                pen=None, brush=pg.mkBrush(color + '80')
            )
            self.plot_widget.addItem(mid_points)

        # 车辆动画位置
        if self.vehicle_pos >= len(node_list) - 1:
            # 到达DC，完成一圈配送
            self.finish_delivery()
            self.vehicle_pos = 0.0
            # 配送次数 +1
            self.increment_delivery_count()
        pos = self.vehicle_pos
        i = int(pos)
        j = min(i + 1, len(node_list) - 1)
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
        label = pg.TextItem(f'🚛', color=color, anchor=(0.5, 0.5))
        label.setFont(QFont('Microsoft YaHei', 7, QFont.Weight.Bold))
        label.setPos(x, y)
        self.plot_widget.addItem(label)

        self.vehicle_pos += 0.03  # 移动步长

    def increment_delivery_count(self):
        """配送次数 +1"""
        try:
            # 从当前显示文本中提取数字
            current_text = self.delivery_count.text()
            current_count = int(current_text)
            new_count = current_count + 1
            
            # 更新显示
            self.delivery_count.setText(str(new_count))
            
            # 可选：添加视觉反馈（闪烁效果）
            self.delivery_count.setStyleSheet("color: #27AE60; font-weight: bold;")
            QTimer.singleShot(500, lambda: self.delivery_count.setStyleSheet("color: #3b82f6; font-weight: bold;"))
            
        except Exception as e:
            print(f"更新配送次数失败: {e}")

    def start_delivery(self):
        """开始配送，记录配送时间"""
        current_index = self.vehicle_select.currentIndex()
        if current_index < 0:
            return
        
        vehicle_id = self.routes[current_index][0]
        delivery_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn = conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE routes
            SET delivery_time=?
            WHERE vehicle_id=?
        """, (delivery_time, vehicle_id))
        
        conn.commit()
        conn.close()
        print(f"车辆 {vehicle_id} 开始配送，时间: {delivery_time}")

    def finish_delivery(self):
        """完成配送，记录完成时间和计算效率"""
        current_index = self.vehicle_select.currentIndex()
        if current_index < 0:
            return
        
        vehicle_id = self.routes[current_index][0]
        finish_time = datetime.now()
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT delivery_time, distance
            FROM routes
            WHERE vehicle_id=?
        """, (vehicle_id,))
        
        result = cursor.fetchone()
        
        if result and result[0]:
            delivery_time_str, distance = result
            delivery_time = datetime.strptime(
                delivery_time_str,
                "%Y-%m-%d %H:%M:%S"
            )
            
            # 计算配送时长（分钟）
            duration = (finish_time - delivery_time).total_seconds() / 60
            
            # 配送效率 = 距离 / 时长
            efficiency = distance / duration if duration > 0 else 0
            
            cursor.execute("""
                UPDATE routes
                SET finish_time=?,
                    duration=?,
                    efficiency=?
                WHERE vehicle_id=?
            """, (
                finish_time.strftime("%Y-%m-%d %H:%M:%S"),
                round(duration, 2),
                round(efficiency, 2),
                vehicle_id
            ))
            
            conn.commit()
            print(f"车辆 {vehicle_id} 完成配送，时长: {duration:.2f}分钟，效率: {efficiency:.2f}")
        
        conn.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = DriverWindow("测试驾驶员")
    win.show()
    sys.exit(app.exec())