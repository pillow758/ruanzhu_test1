import sys
import math
import random
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QInputDialog, QMessageBox, QStatusBar
)
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QFont, QColor, QPalette
import pyqtgraph as pg

# 尝试启用GPU加速（若系统支持则使用OpenGL渲染）
try:
    pg.setConfigOptions(useOpenGL=True)
    pg.setConfigOptions(antialias=True)
except Exception:
    pass

# ====================== 参数配置 ======================
VEHICLE_CAPACITY = 3000
FIXED_COST = 400
COST_PER_KM = 2.5
COLORS = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F39C12', '#9B59B6', '#1ABC9C']

# ====================== 数据结构 ======================
class Node:
    def __init__(self, id, x, y, q):
        self.id = str(id)
        self.x = x
        self.y = y
        self.q = q

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
def calc_dist(n1, n2):
    return math.sqrt((n1.x - n2.x) ** 2 + (n1.y - n2.y) ** 2)

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
    cost = FIXED_COST + total_dist * COST_PER_KM if len(route_node_ids) > 2 else 0
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

def trigger_change_address(target_id, new_x, new_y):
    """变更地址（模拟先删除再插入）"""
    global active_routes
    target_node = node_dict[target_id]
    temp_q = target_node.q
    trigger_cancel_order(target_id)
    target_node.x, target_node.y, target_node.q = new_x, new_y, temp_q
    trigger_new_order(target_node)

# ====================== 主界面 ======================
class LogisticsApp(QMainWindow):
    def __init__(self):
        super().__init__()
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
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title)

        # 按钮组
        btn_data = [
            ("🎯 静态规划", self.init_routes, "#27AE60"),
            ("➕ 新增订单", self.add_order, "#3498DB"),
            ("❌ 取消订单", self.cancel_order, "#E74C3C"),
            ("📍 地址变更", self.change_address, "#F39C12"),
            ("🎲 批量随机模拟", self.batch_simulation, "#9B59B6"),
            ("🔄 重置系统", self.reset_system, "#95A5A6"),
        ]
        for text, slot, color in btn_data:
            btn = QPushButton(text)
            btn.setFont(QFont("Microsoft YaHei", 10))
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
        stats_frame.setStyleSheet("background-color: #2a2a3e; border-radius: 8px; padding: 10px;")
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setSpacing(5)

        stats_title = QLabel("📊 运营统计")
        stats_title.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        stats_layout.addWidget(stats_title)

        self.lbl_vehicle = QLabel("🚛 使用车辆: 0")
        self.lbl_load = QLabel("📦 总载重: 0 kg")
        self.lbl_dist = QLabel("📏 总距离: 0 km")
        self.lbl_cost = QLabel("💰 总成本: ¥ 0")
        for lbl in (self.lbl_vehicle, self.lbl_load, self.lbl_dist, self.lbl_cost):
            lbl.setFont(QFont("Microsoft YaHei", 9))
            stats_layout.addWidget(lbl)
        left_layout.addWidget(stats_frame)

        # 车辆详情表格
        table_label = QLabel("🚚 车辆配送详情")
        table_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        left_layout.addWidget(table_label)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["车辆", "载重(kg)", "距离(km)", "成本(¥)", "路径"])
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
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

        main_layout.addWidget(left_panel)

        # ---------- 右侧动画面板 ----------
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#1e1e2e')
        self.plot_widget.setLabel('left', 'Y 坐标 (km)', color='#ccc')
        self.plot_widget.setLabel('bottom', 'X 坐标 (km)', color='#ccc')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setRange(xRange=[-2, 42], yRange=[-2, 42])
        right_layout.addWidget(self.plot_widget)
        main_layout.addWidget(right_panel, 1)

        # ---------- 状态栏 ----------
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("background-color: #1e1e2e; color: #aaa;")
        self.status_msg = QLabel("✅ 系统就绪")
        self.status_msg.setFont(QFont("Microsoft YaHei", 9))
        self.status_bar.addWidget(self.status_msg)
        self.setStatusBar(self.status_bar)

    def apply_dark_theme(self):
        """全局深色科技风样式"""
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
        """初始化示例数据"""
        global node_dict, active_routes
        node_dict.clear()
        active_routes.clear()
        node_dict['DC'] = Node('DC', 20, 20, 0)
        raw_customers = [
            Node('A', 25, 15, 800), Node('B', 15, 10, 600), Node('C', 30, 25, 700),
            Node('D', 10, 30, 500), Node('E', 28, 8, 900), Node('F', 5, 20, 400),
        ]
        for c in raw_customers:
            node_dict[c.id] = c
        self.init_routes()

    def init_routes(self):
        """静态优化路线"""
        global active_routes
        customers = [node_dict[nid] for nid in node_dict if nid != 'DC']
        active_routes = savings_algorithm(customers)
        self.reset_animation()
        self.update_stats()
        self.status_msg.setText("✅ 静态规划完成，路线已优化")
        QMessageBox.information(self, "完成",
            f"静态规划完成！\n使用车辆: {len(active_routes)} 辆\n总成本: ¥{sum(r.cost for r in active_routes):.1f}")

    def reset_animation(self):
        """重置动画状态"""
        self.vehicle_pos = [0.0] * len(active_routes)
        self.vehicle_colors = [COLORS[i % len(COLORS)] for i in range(len(active_routes))]
        self.unload_status = {i: False for i in range(len(active_routes))}

    def start_animation(self):
        self.timer.start(50)  # 20帧/秒

    def update_plot(self):
        """每帧重绘全部内容（高性能）"""
        self.plot_widget.clear()
        # 绘制配送中心
        dc = node_dict['DC']
        dc_item = pg.ScatterPlotItem(
            [dc.x], [dc.y], symbol='s', size=20,
            pen=pg.mkPen(color='#FFD700', width=3), brush=pg.mkBrush('#2C3E50')
        )
        self.plot_widget.addItem(dc_item)
        dc_text = pg.TextItem('DC', color='#FFD700', anchor=(0.5, -0.5))
        dc_text.setFont(QFont('Microsoft YaHei', 10, QFont.Weight.Bold))
        dc_text.setPos(dc.x, dc.y + 0.8)
        self.plot_widget.addItem(dc_text)

        # 绘制所有客户点
        client_x, client_y, client_labels = [], [], []
        for nid, n in node_dict.items():
            if nid == 'DC':
                continue
            client_x.append(n.x)
            client_y.append(n.y)
            client_labels.append((n.x, n.y, f'{nid}\n({n.q}kg)'))
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

        # 绘制路线与车辆动画
        for idx, r in enumerate(active_routes):
            xs = [node_dict[nid].x for nid in r.nodes]
            ys = [node_dict[nid].y for nid in r.nodes]
            color = self.vehicle_colors[idx]

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
            if idx < len(self.vehicle_pos):
                pos = self.vehicle_pos[idx]
                if pos >= len(r.nodes) - 1:
                    # 到达DC，重置（循环配送）
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
                label = pg.TextItem(f'🚛{idx+1}', color=color, anchor=(0.5, 0.5))
                label.setFont(QFont('Microsoft YaHei', 7, QFont.Weight.Bold))
                label.setPos(x, y)
                self.plot_widget.addItem(label)

                self.vehicle_pos[idx] += 0.03  # 移动步长

    def update_stats(self):
        """刷新统计信息与表格"""
        total_dist = sum(r.distance for r in active_routes)
        total_cost = sum(r.cost for r in active_routes)
        total_q = sum(r.q for r in active_routes)
        self.lbl_vehicle.setText(f"🚛 使用车辆: {len(active_routes)}")
        self.lbl_load.setText(f"📦 总载重: {total_q:.0f} kg")
        self.lbl_dist.setText(f"📏 总距离: {total_dist:.1f} km")
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
                QTableWidgetItem(f"{r.distance:.1f}"),
                QTableWidgetItem(f"¥{r.cost:.1f}"),
                QTableWidgetItem(path_str),
            ]
            for col, item in enumerate(items):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(idx, col, item)

        self.status_msg.setText(
            f"📅 最后更新 | 📊 车辆: {len(active_routes)} | 成本: ¥{total_cost:.0f}"
        )

    # ---------- 按钮槽函数 ----------
    def add_order(self):
        nid, ok = QInputDialog.getText(self, "新增订单", "请输入订单ID:")
        if not ok or not nid.strip():
            return
        nid = nid.strip()
        if nid in node_dict:
            QMessageBox.warning(self, "错误", "订单ID已存在！")
            return
        x, ok = QInputDialog.getDouble(self, "新增订单", "X坐标 (0-40):", 20, 0, 40, 1)
        if not ok: return
        y, ok = QInputDialog.getDouble(self, "新增订单", "Y坐标 (0-40):", 20, 0, 40, 1)
        if not ok: return
        q, ok = QInputDialog.getDouble(self, "新增订单", "重量 (kg):", 500, 1, 3000, 1)
        if not ok: return

        new_node = Node(nid, x, y, q)
        global active_routes
        trigger_new_order(new_node)
        self.reset_animation()
        self.update_stats()
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
            self.reset_animation()
            self.update_stats()
            self.status_msg.setText(f"✅ 已取消订单 {nid}")

    def change_address(self):
        customers = [nid for nid in node_dict if nid != 'DC']
        if not customers:
            QMessageBox.warning(self, "警告", "没有可修改的订单！")
            return
        nid, ok = QInputDialog.getItem(self, "地址变更", "选择订单:", customers, 0, False)
        if not ok: return
        x, ok = QInputDialog.getDouble(self, "地址变更", "新X坐标 (0-40):", 20, 0, 40, 1)
        if not ok: return
        y, ok = QInputDialog.getDouble(self, "地址变更", "新Y坐标 (0-40):", 20, 0, 40, 1)
        if not ok: return
        global active_routes
        trigger_change_address(nid, x, y)
        self.reset_animation()
        self.update_stats()
        self.status_msg.setText(f"✅ 已更新订单 {nid} 地址")

    def batch_simulation(self):
        num, ok = QInputDialog.getInt(self, "批量随机模拟", "生成订单数量:", 5, 1, 20, 1)
        if not ok: return
        self.reset_system()  # 先清空
        global active_routes
        new_ids = []
        for _ in range(num):
            nid = f"R{random.randint(100, 999)}"
            while nid in node_dict:
                nid = f"R{random.randint(100, 999)}"
            x = random.uniform(2, 38)
            y = random.uniform(2, 38)
            q = random.randint(200, 1500)
            new_node = Node(nid, x, y, q)
            trigger_new_order(new_node)
            new_ids.append(nid)
        self.reset_animation()
        self.update_stats()
        self.status_msg.setText(f"✅ 批量模拟完成，新增 {num} 个随机订单")
        QMessageBox.information(self, "完成", f"已生成 {num} 个随机订单！\nID示例: {', '.join(new_ids[:5])}" +
                                ("…" if num > 5 else ""))

    def reset_system(self):
        reply = QMessageBox.question(self, "确认", "重置将清除所有订单数据，确定吗？",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.init_data()

# ====================== 程序入口 ======================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    window = LogisticsApp()
    window.show()
    sys.exit(app.exec())