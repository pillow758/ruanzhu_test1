import tkinter as tk
from tkinter import simpledialog, messagebox, ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
import matplotlib
import math
import random
from datetime import datetime

# 设置中文字体
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False

# ====================== 物流调度核心算法 ======================
DEPOT = {'id': 'DC', 'x': 20, 'y': 20, 'q': 0}
VEHICLE_CAPACITY = 3000
FIXED_COST = 400
COST_PER_KM = 2.5


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


def calc_dist(n1, n2):
    return math.sqrt((n1.x - n2.x) ** 2 + (n1.y - n2.y) ** 2)


def evaluate_route(route_node_ids, node_dict):
    total_q = sum(node_dict[nid].q for nid in route_node_ids if nid != 'DC')
    total_dist = sum(calc_dist(node_dict[route_node_ids[i]], node_dict[route_node_ids[i + 1]])
                     for i in range(len(route_node_ids) - 1))
    cost = FIXED_COST + total_dist * COST_PER_KM if len(route_node_ids) > 2 else 0
    return total_q, total_dist, cost


def savings_algorithm(customer_nodes, node_dict):
    routes = [['DC', c.id, 'DC'] for c in customer_nodes]
    savings = []
    for i in range(len(customer_nodes)):
        for j in range(i + 1, len(customer_nodes)):
            n_i, n_j = customer_nodes[i], customer_nodes[j]
            d_dc_i = calc_dist(node_dict['DC'], n_i)
            d_dc_j = calc_dist(node_dict['DC'], n_j)
            d_i_j = calc_dist(n_i, n_j)
            sav = d_dc_i + d_dc_j - d_i_j
            if sav > 0: savings.append((n_i.id, n_j.id, sav))
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
            q_i, _, _ = evaluate_route(r_i, node_dict)
            q_j, _, _ = evaluate_route(r_j, node_dict)
            if q_i + q_j <= VEHICLE_CAPACITY:
                merged_route = r_i[:-1] + r_j[1:]
                routes.pop(max(route_i_idx, route_j_idx))
                routes.pop(min(route_i_idx, route_j_idx))
                routes.append(merged_route)

    final_routes = []
    for r in routes:
        q, dist, cost = evaluate_route(r, node_dict)
        route_obj = Route(r)
        route_obj.q, route_obj.distance, route_obj.cost = q, dist, cost
        final_routes.append(route_obj)
    return final_routes


def trigger_new_order(routes, node_dict, new_node):
    print(f"新增订单 {new_node.id}")
    node_dict[new_node.id] = new_node
    best_route_idx = best_insert_pos = -1
    min_add_cost = float('inf')
    for r_idx, r in enumerate(routes):
        if r.q + new_node.q > VEHICLE_CAPACITY: continue
        for pos in range(1, len(r.nodes)):
            trial_nodes = r.nodes[:pos] + [new_node.id] + r.nodes[pos:]
            _, _, trial_cost = evaluate_route(trial_nodes, node_dict)
            add_cost = trial_cost - r.cost
            if add_cost < min_add_cost:
                min_add_cost = add_cost
                best_route_idx = r_idx
                best_insert_pos = pos
    if best_route_idx != -1:
        r = routes[best_route_idx]
        r.nodes.insert(best_insert_pos, new_node.id)
        r.q, r.distance, r.cost = evaluate_route(r.nodes, node_dict)
    else:
        r_new = ['DC', new_node.id, 'DC']
        q, dist, cost = evaluate_route(r_new, node_dict)
        route_obj = Route(r_new)
        route_obj.q, route_obj.distance, route_obj.cost = q, dist, cost
        routes.append(route_obj)


def trigger_cancel_order(routes, node_dict, cancel_id):
    print(f"取消订单 {cancel_id}")
    target_r_idx = next((i for i, r in enumerate(routes) if cancel_id in r.nodes), -1)
    if target_r_idx == -1: return
    r = routes[target_r_idx]
    r.nodes.remove(cancel_id)
    r.q, r.distance, r.cost = evaluate_route(r.nodes, node_dict)
    if len(r.nodes) <= 2:
        routes.pop(target_r_idx)


def trigger_change_address(routes, node_dict, target_id, new_x, new_y):
    target_node = node_dict[target_id]
    temp_q = target_node.q
    trigger_cancel_order(routes, node_dict, target_id)
    target_node.x, target_node.y, target_node.q = new_x, new_y, temp_q
    trigger_new_order(routes, node_dict, target_node)


# ====================== Tkinter + 动画 ======================
class LogisticsAnimation:
    def __init__(self, ax, node_dict_ref, routes_ref):
        self.ax = ax
        self.node_dict_ref = node_dict_ref
        self.routes_ref = routes_ref
        self.vehicle_pos = []
        self.vehicle_colors = []
        self.colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8']
        self.unload_status = {}  # 记录车辆是否已卸货

    def init_animation(self):
        self.vehicle_pos = [0] * len(self.routes_ref)
        self.vehicle_colors = [self.colors[i % len(self.colors)] for i in range(len(self.routes_ref))]
        self.unload_status = {i: False for i in range(len(self.routes_ref))}

    def update_animation(self, frame):
        self.ax.clear()
        routes = self.routes_ref
        node_dict = self.node_dict_ref

        # 绘制背景网格
        self.ax.set_facecolor('#F8F9FA')

        # 绘制配送中心
        dc = node_dict['DC']
        self.ax.plot(dc.x, dc.y, 'ks', markersize=16, marker='s',
                     color='#2C3E50', markeredgecolor='#1A252F', markeredgewidth=2)
        self.ax.text(dc.x + 1.0, dc.y + 0.8, 'DC', fontsize=11, fontweight='bold')

        # 绘制客户点
        for nid, n in node_dict.items():
            if nid != 'DC':
                self.ax.plot(n.x, n.y, 'o', color='#3498DB', markersize=10,
                             markeredgecolor='white', markeredgewidth=1.5, zorder=2)
                self.ax.text(n.x + 0.3, n.y + 0.2, f'{nid}\n({n.q}kg)', fontsize=8,
                             bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.7))

        # 绘制路线和车辆
        for idx, r in enumerate(routes):
            color = self.vehicle_colors[idx] if idx < len(self.vehicle_colors) else self.colors[idx % len(self.colors)]
            xs = [node_dict[nid].x for nid in r.nodes]
            ys = [node_dict[nid].y for nid in r.nodes]

            # 绘制路线（渐变透明度）
            for i in range(len(xs) - 1):
                self.ax.plot([xs[i], xs[i + 1]], [ys[i], ys[i + 1]],
                             linestyle='-', color=color, alpha=0.4, linewidth=1.5)

            # 绘制路线上的点
            self.ax.plot(xs[1:-1], ys[1:-1], 'o', color=color, markersize=6, alpha=0.6)

            # 更新车辆位置
            if idx < len(self.vehicle_pos):
                pos = self.vehicle_pos[idx]
                if pos >= len(r.nodes) - 1:
                    # 车辆到达DC，自动卸货并重置
                    if not self.unload_status.get(idx, False):
                        self.unload_status[idx] = True
                        # 重置车辆位置循环
                        self.vehicle_pos[idx] = 0
                        pos = 0
                    else:
                        pos = len(r.nodes) - 1

                i, j = int(pos), min(int(pos) + 1, len(r.nodes) - 1)
                t = pos - i
                x = xs[i] + (xs[j] - xs[i]) * t
                y = ys[i] + (ys[j] - ys[i]) * t

                # 绘制车辆（带有光晕效果）
                self.ax.plot(x, y, marker='o', color=color, markersize=14,
                             markeredgecolor='white', markeredgewidth=2, zorder=3)
                self.ax.plot(x, y, marker='o', color=color, markersize=8,
                             alpha=0.5, zorder=2)
                self.ax.text(x - 0.8, y - 0.8, f'🚛{idx + 1}', fontsize=7, fontweight='bold')

                self.vehicle_pos[idx] += 0.03
                if self.vehicle_pos[idx] > len(r.nodes) - 1:
                    self.unload_status[idx] = True
                    self.vehicle_pos[idx] = len(r.nodes) - 1

        # 设置图表样式
        self.ax.set_title("🚚 动态物流配送模拟系统", fontsize=14, fontweight='bold', pad=15)
        self.ax.set_xlim(0, 40)
        self.ax.set_ylim(0, 40)
        self.ax.set_xlabel("X 坐标 (km)", fontsize=10)
        self.ax.set_ylabel("Y 坐标 (km)", fontsize=10)
        self.ax.grid(True, alpha=0.3, linestyle='--')
        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)


class LogisticsUI:
    def __init__(self, master):
        self.master = master
        master.title("🚚 动态物流调度模拟器")
        master.geometry("1400x800")
        master.configure(bg='#F0F2F5')

        # 设置样式
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Title.TLabel', font=('微软雅黑', 16, 'bold'), foreground='#2C3E50')
        style.configure('Info.TLabel', font=('微软雅黑', 10), foreground='#34495E')
        style.configure('Header.TLabel', font=('微软雅黑', 11, 'bold'), foreground='#2C3E50')
        style.configure('Success.TButton', font=('微软雅黑', 9), background='#27AE60')
        style.configure('Warning.TButton', font=('微软雅黑', 9), background='#E74C3C')

        # 创建主框架
        self.main_frame = tk.Frame(master, bg='#F0F2F5')
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # 左侧控制面板
        self.create_control_panel()

        # 右侧动画区域
        self.create_animation_panel()

        # 底部状态栏
        self.create_status_bar()

        # 初始化数据
        self.init_data()

        # 动画对象
        self.ani = None

    def create_control_panel(self):
        """创建控制面板"""
        left_frame = tk.Frame(self.main_frame, bg='white', relief=tk.RAISED, bd=1)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15), pady=0)

        # 标题
        title_frame = tk.Frame(left_frame, bg='#2C3E50', height=60)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        tk.Label(title_frame, text="📋 调度控制系统", font=('微软雅黑', 14, 'bold'),
                 bg='#2C3E50', fg='white').pack(expand=True)

        # 按钮区域
        btn_frame = tk.Frame(left_frame, bg='white', padx=15, pady=15)
        btn_frame.pack(fill=tk.X)

        buttons = [
            ("🎯 静态规划", self.init_routes, '#27AE60'),
            ("➕ 新增订单", self.add_order, '#3498DB'),
            ("❌ 取消订单", self.cancel_order, '#E74C3C'),
            ("📍 地址变更", self.change_address, '#F39C12'),
            ("🎲 批量随机模拟", self.batch_simulation, '#9B59B6'),
            ("🔄 重置系统", self.reset_system, '#95A5A6'),
        ]

        for text, cmd, color in buttons:
            btn = tk.Button(btn_frame, text=text, command=cmd, font=('微软雅黑', 10),
                            bg=color, fg='white', relief=tk.FLAT, padx=15, pady=8,
                            activebackground=self.darken_color(color), activeforeground='white',
                            cursor='hand2')
            btn.pack(fill=tk.X, pady=5)

        # 统计信息区域
        stats_frame = tk.Frame(left_frame, bg='#ECF0F1', padx=15, pady=15)
        stats_frame.pack(fill=tk.X, pady=15)

        tk.Label(stats_frame, text="📊 运营统计", font=('微软雅黑', 12, 'bold'),
                 bg='#ECF0F1', fg='#2C3E50').pack(anchor='w', pady=(0, 10))

        self.stats_labels = {}
        stats_items = [
            ("🚛 使用车辆:", "0"),
            ("📦 总载重:", "0 kg"),
            ("📏 总距离:", "0 km"),
            ("💰 总成本:", "¥ 0"),
        ]

        for label, initial in stats_items:
            frame = tk.Frame(stats_frame, bg='#ECF0F1')
            frame.pack(fill=tk.X, pady=3)
            tk.Label(frame, text=label, font=('微软雅黑', 9), bg='#ECF0F1',
                     fg='#7F8C8D').pack(side=tk.LEFT)
            lbl_val = tk.Label(frame, text=initial, font=('微软雅黑', 9, 'bold'),
                               bg='#ECF0F1', fg='#2C3E50')
            lbl_val.pack(side=tk.RIGHT)
            self.stats_labels[label] = lbl_val

        # 车辆信息表格
        table_frame = tk.Frame(left_frame, bg='white', padx=15, pady=15)
        table_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(table_frame, text="🚚 车辆配送详情", font=('微软雅黑', 12, 'bold'),
                 bg='white', fg='#2C3E50').pack(anchor='w', pady=(0, 10))

        # 创建Treeview
        columns = ("车辆", "载重(kg)", "距离(km)", "成本(¥)", "路径")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)

        for col in columns:
            self.tree.heading(col, text=col)
            width = 80 if col == "车辆" else 100 if col != "路径" else 200
            self.tree.column(col, width=width, anchor='center')

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_animation_panel(self):
        """创建动画面板"""
        right_frame = tk.Frame(self.main_frame, bg='white', relief=tk.RAISED, bd=1)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 图表
        self.fig, self.ax = plt.subplots(figsize=(8, 7), facecolor='white')
        self.fig.patch.set_facecolor('white')
        self.canvas = FigureCanvasTkAgg(self.fig, right_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = tk.Frame(self.master, bg='#2C3E50', height=30)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = tk.Label(self.status_bar, text="✅ 系统就绪",
                                     font=('微软雅黑', 9), bg='#2C3E50', fg='white')
        self.status_label.pack(side=tk.LEFT, padx=15)

        self.time_label = tk.Label(self.status_bar, text="", font=('微软雅黑', 9),
                                   bg='#2C3E50', fg='white')
        self.time_label.pack(side=tk.RIGHT, padx=15)
        self.update_time()

    def init_data(self):
        """初始化数据"""
        global node_dict, active_routes, raw_customers
        node_dict = {'DC': Node('DC', 20, 20, 0)}

        # 初始客户数据
        raw_customers = [
            Node('A', 25, 15, 800), Node('B', 15, 10, 600), Node('C', 30, 25, 700),
            Node('D', 10, 30, 500), Node('E', 28, 8, 900), Node('F', 5, 20, 400),
        ]
        for c in raw_customers:
            node_dict[c.id] = c

        active_routes = []
        self.anim_ctrl = None

        # 默认运行静态规划
        self.init_routes()

    def darken_color(self, color):
        """颜色变暗效果"""
        return '#1E8449' if color == '#27AE60' else '#2980B9' if color == '#3498DB' else '#C0392B'

    def update_time(self):
        """更新时间显示"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.config(text=now)
        self.master.after(1000, self.update_time)

    def update_stats(self):
        """更新统计信息"""
        if not active_routes:
            return
        total_dist = sum(r.distance for r in active_routes)
        total_cost = sum(r.cost for r in active_routes)
        total_q = sum(r.q for r in active_routes)

        self.stats_labels["🚛 使用车辆:"].config(text=str(len(active_routes)))
        self.stats_labels["📦 总载重:"].config(text=f"{total_q:.0f} kg")
        self.stats_labels["📏 总距离:"].config(text=f"{total_dist:.1f} km")
        self.stats_labels["💰 总成本:"].config(text=f"¥ {total_cost:.1f}")

        # 更新表格
        for item in self.tree.get_children():
            self.tree.delete(item)

        for idx, r in enumerate(active_routes):
            path_str = " → ".join(r.nodes[:3]) + ("..." if len(r.nodes) > 4 else "")
            self.tree.insert("", tk.END, values=(
                f"车辆{idx + 1}", f"{r.q:.0f}", f"{r.distance:.1f}", f"¥{r.cost:.1f}", path_str
            ))

        self.status_label.config(
            text=f"📅 最后更新: {datetime.now().strftime('%H:%M:%S')} | 📊 车辆: {len(active_routes)} | 成本: ¥{total_cost:.0f}")

    def init_routes(self):
        """初始化/重新规划路线"""
        global active_routes
        customers = [node_dict[nid] for nid in node_dict if nid != 'DC']
        active_routes = savings_algorithm(customers, node_dict)

        if self.anim_ctrl:
            self.ani.event_source.stop()

        self.anim_ctrl = LogisticsAnimation(self.ax, node_dict, active_routes)
        self.anim_ctrl.init_animation()
        self.ani = FuncAnimation(self.fig, self.anim_ctrl.update_animation, interval=50, cache_frame_data=False)
        self.canvas.draw()

        self.update_stats()
        self.status_label.config(text="✅ 静态规划完成，路线已优化")
        messagebox.showinfo("完成",
                            f"静态规划完成！\n使用车辆: {len(active_routes)} 辆\n总成本: ¥{sum(r.cost for r in active_routes):.1f}")

    def add_order(self):
        """新增订单"""
        dialog = tk.Toplevel(self.master)
        dialog.title("新增订单")
        dialog.geometry("300x280")
        dialog.configure(bg='white')
        dialog.transient(self.master)
        dialog.grab_set()

        tk.Label(dialog, text="📦 新增订单", font=('微软雅黑', 14, 'bold'),
                 bg='white', fg='#2C3E50').pack(pady=15)

        fields = [
            ("订单ID:", tk.StringVar()),
            ("X坐标 (0-40):", tk.DoubleVar()),
            ("Y坐标 (0-40):", tk.DoubleVar()),
            ("重量 (kg):", tk.DoubleVar()),
        ]

        entries = []
        for label, var in fields:
            frame = tk.Frame(dialog, bg='white')
            frame.pack(fill=tk.X, padx=20, pady=5)
            tk.Label(frame, text=label, width=12, anchor='w', bg='white').pack(side=tk.LEFT)
            entry = tk.Entry(frame, textvariable=var, font=('微软雅黑', 10))
            entry.pack(side=tk.RIGHT, expand=True, fill=tk.X)
            entries.append((var, entry))

        def submit():
            nid = fields[0][1].get()
            x = fields[1][1].get()
            y = fields[2][1].get()
            q = fields[3][1].get()

            if nid and 0 <= x <= 40 and 0 <= y <= 40 and q > 0:
                if nid in node_dict:
                    messagebox.showerror("错误", "订单ID已存在！")
                    return
                new_node = Node(nid, x, y, q)
                trigger_new_order(active_routes, node_dict, new_node)
                self.anim_ctrl.init_animation()
                self.update_stats()
                self.status_label.config(text=f"✅ 已新增订单 {nid}")
                dialog.destroy()
            else:
                messagebox.showerror("错误", "请输入有效数据！")

        btn_frame = tk.Frame(dialog, bg='white')
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="确认", command=submit, bg='#27AE60', fg='white',
                  font=('微软雅黑', 10), padx=20, relief=tk.FLAT, cursor='hand2').pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="取消", command=dialog.destroy, bg='#95A5A6', fg='white',
                  font=('微软雅黑', 10), padx=20, relief=tk.FLAT, cursor='hand2').pack(side=tk.LEFT)

    def cancel_order(self):
        """取消订单"""
        customers = [nid for nid in node_dict if nid != 'DC']
        if not customers:
            messagebox.showwarning("警告", "没有可取消的订单！")
            return

        dialog = tk.Toplevel(self.master)
        dialog.title("取消订单")
        dialog.geometry("300x200")
        dialog.configure(bg='white')
        dialog.transient(self.master)
        dialog.grab_set()

        tk.Label(dialog, text="❌ 取消订单", font=('微软雅黑', 14, 'bold'),
                 bg='white', fg='#2C3E50').pack(pady=15)

        tk.Label(dialog, text="选择订单ID:", bg='white').pack(pady=5)
        var = tk.StringVar(dialog)
        var.set(customers[0])
        dropdown = ttk.Combobox(dialog, textvariable=var, values=customers, state='readonly')
        dropdown.pack(pady=5)

        def submit():
            nid = var.get()
            if nid in node_dict:
                trigger_cancel_order(active_routes, node_dict, nid)
                self.anim_ctrl.init_animation()
                self.update_stats()
                self.status_label.config(text=f"✅ 已取消订单 {nid}")
                dialog.destroy()
            else:
                messagebox.showerror("错误", "订单不存在！")

        tk.Button(dialog, text="确认取消", command=submit, bg='#E74C3C', fg='white',
                  font=('微软雅黑', 10), padx=20, pady=5, relief=tk.FLAT, cursor='hand2').pack(pady=15)

    def change_address(self):
        """地址变更"""
        customers = [nid for nid in node_dict if nid != 'DC']
        if not customers:
            messagebox.showwarning("警告", "没有可修改的订单！")
            return

        dialog = tk.Toplevel(self.master)
        dialog.title("地址变更")
        dialog.geometry("300x300")
        dialog.configure(bg='white')
        dialog.transient(self.master)
        dialog.grab_set()

        tk.Label(dialog, text="📍 地址变更", font=('微软雅黑', 14, 'bold'),
                 bg='white', fg='#2C3E50').pack(pady=15)

        tk.Label(dialog, text="选择订单:", bg='white').pack()
        var_id = tk.StringVar(dialog)
        var_id.set(customers[0])
        ttk.Combobox(dialog, textvariable=var_id, values=customers, state='readonly').pack(pady=5)

        tk.Label(dialog, text="新X坐标 (0-40):", bg='white').pack(pady=(10, 0))
        var_x = tk.DoubleVar(dialog)
        tk.Entry(dialog, textvariable=var_x).pack(pady=5)

        tk.Label(dialog, text="新Y坐标 (0-40):", bg='white').pack()
        var_y = tk.DoubleVar(dialog)
        tk.Entry(dialog, textvariable=var_y).pack(pady=5)

        def submit():
            nid = var_id.get()
            x = var_x.get()
            y = var_y.get()
            if 0 <= x <= 40 and 0 <= y <= 40:
                trigger_change_address(active_routes, node_dict, nid, x, y)
                self.anim_ctrl.init_animation()
                self.update_stats()
                self.status_label.config(text=f"✅ 已更新订单 {nid} 地址")
                dialog.destroy()
            else:
                messagebox.showerror("错误", "坐标范围需在0-40之间！")

        tk.Button(dialog, text="确认修改", command=submit, bg='#F39C12', fg='white',
                  font=('微软雅黑', 10), padx=20, pady=5, relief=tk.FLAT, cursor='hand2').pack(pady=20)

    def batch_simulation(self):
        """批量随机订单模拟"""
        dialog = tk.Toplevel(self.master)
        dialog.title("批量随机模拟")
        dialog.geometry("350x250")
        dialog.configure(bg='white')
        dialog.transient(self.master)
        dialog.grab_set()

        tk.Label(dialog, text="🎲 批量随机模拟", font=('微软雅黑', 14, 'bold'),
                 bg='white', fg='#2C3E50').pack(pady=15)

        tk.Label(dialog, text="生成订单数量:", bg='white').pack()
        var_num = tk.IntVar(dialog)
        var_num.set(5)
        spinbox = tk.Spinbox(dialog, from_=1, to=20, textvariable=var_num, width=10)
        spinbox.pack(pady=5)

        def simulate():
            num = var_num.get()
            self.reset_system()

            # 生成随机订单
            new_ids = []
            for i in range(num):
                nid = f"R{random.randint(100, 999)}"
                while nid in node_dict:
                    nid = f"R{random.randint(100, 999)}"
                x = random.uniform(2, 38)
                y = random.uniform(2, 38)
                q = random.randint(200, 1500)
                new_node = Node(nid, x, y, q)
                trigger_new_order(active_routes, node_dict, new_node)
                new_ids.append(nid)

            self.anim_ctrl.init_animation()
            self.update_stats()
            self.status_label.config(text=f"✅ 批量模拟完成，新增 {num} 个随机订单")
            messagebox.showinfo("完成", f"已生成 {num} 个随机订单！\n\n订单ID: {', '.join(new_ids[:5])}" +
                                ("..." if num > 5 else ""))
            dialog.destroy()

        btn_frame = tk.Frame(dialog, bg='white')
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="开始模拟", command=simulate, bg='#9B59B6', fg='white',
                  font=('微软雅黑', 10), padx=20, relief=tk.FLAT, cursor='hand2').pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="取消", command=dialog.destroy, bg='#95A5A6', fg='white',
                  font=('微软雅黑', 10), padx=20, relief=tk.FLAT, cursor='hand2').pack(side=tk.LEFT)

    def reset_system(self):
        """重置系统"""
        if messagebox.askyesno("确认", "重置将清除所有订单数据，确定吗？"):
            self.init_data()


def print_summary(routes, title="状态"):
    """打印摘要信息（控制台输出）"""
    print(f"\n{'=' * 50}")
    print(f"[{title}]")
    print(f"{'=' * 50}")
    total_dist = total_cost = 0
    for idx, r in enumerate(routes):
        print(f"车辆{idx + 1}: 载重{r.q}kg, 距离{r.distance:.1f}km, 成本¥{r.cost:.1f}")
        print(f"        路径: {' → '.join(r.nodes)}")
        total_dist += r.distance
        total_cost += r.cost
    print(f"{'-' * 50}")
    print(f"总车辆: {len(routes)}, 总距离: {total_dist:.1f}km, 总成本: ¥{total_cost:.1f}")
    print(f"{'=' * 50}\n")


# ====================== 全局变量 ======================
node_dict = {}
active_routes = []
raw_customers = []

# ====================== 主循环 ======================
if __name__ == "__main__":
    root = tk.Tk()
    app = LogisticsUI(root)
    root.mainloop()