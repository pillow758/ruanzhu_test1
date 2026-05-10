import math

# ====================== 1. 全局配置与基础类 ======================
DEPOT = {'id': 'DC', 'x': 20, 'y': 20, 'q': 0}
VEHICLE_CAPACITY = 3000  # 车辆最大载重 (kg)
FIXED_COST = 400  # 车辆固定启动成本
COST_PER_KM = 2.5  # 每公里行驶/能耗综合成本预估


class Node:
    def __init__(self, id, x, y, q):
        self.id = str(id)
        self.x = x
        self.y = y
        self.q = q


class Route:
    def __init__(self, nodes):
        self.nodes = nodes  # 包含起终点DC, 例如 ['DC', 'C1', 'C2', 'DC']
        self.q = 0
        self.distance = 0
        self.cost = 0


def calc_dist(n1, n2):
    """计算两点之间的欧式距离"""
    return math.sqrt((n1.x - n2.x) ** 2 + (n1.y - n2.y) ** 2)


def evaluate_route(route_node_ids, node_dict):
    """计算路径的总重量、总距离和预估成本"""
    total_q = 0
    total_dist = 0

    # 累加重量 (排除配送中心)
    for nid in route_node_ids:
        if nid != 'DC':
            total_q += node_dict[nid].q

    # 累加距离
    for i in range(len(route_node_ids) - 1):
        n1 = node_dict[route_node_ids[i]]
        n2 = node_dict[route_node_ids[i + 1]]
        total_dist += calc_dist(n1, n2)

    cost = FIXED_COST + total_dist * COST_PER_KM if len(route_node_ids) > 2 else 0
    return total_q, total_dist, cost


# ====================== 2. 静态初始规划 (节约算法) ======================
def savings_algorithm(customer_nodes, node_dict):
    """标准的Clarke-Wright节约算法"""
    routes = []
    # 1. 初始状态：每个客户一辆车 [DC, i, DC]
    for c in customer_nodes:
        routes.append(['DC', c.id, 'DC'])

    # 2. 计算节约值 S(i,j) = d(DC, i) + d(DC, j) - d(i, j)
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

    # 按节约值降序排序
    savings.sort(key=lambda x: x[2], reverse=True)

    # 3. 合并路径
    for i_id, j_id, _ in savings:
        route_i_idx, route_j_idx = -1, -1
        # 寻找i和j分别在哪些路径的端点
        for idx, r in enumerate(routes):
            if r[1] == i_id and r[-2] == i_id:  # 独立点
                if route_i_idx == -1: route_i_idx = idx
            elif r[-2] == i_id:
                route_i_idx = idx

            if r[1] == j_id and r[-2] == j_id:  # 独立点
                if route_j_idx == -1: route_j_idx = idx
            elif r[1] == j_id:
                route_j_idx = idx

        if route_i_idx != -1 and route_j_idx != -1 and route_i_idx != route_j_idx:
            r_i, r_j = routes[route_i_idx], routes[route_j_idx]
            q_i, _, _ = evaluate_route(r_i, node_dict)
            q_j, _, _ = evaluate_route(r_j, node_dict)

            # 检查容量约束
            if q_i + q_j <= VEHICLE_CAPACITY:
                merged_route = r_i[:-1] + r_j[1:]
                # 移除旧路径，加入新路径
                routes.pop(max(route_i_idx, route_j_idx))
                routes.pop(min(route_i_idx, route_j_idx))
                routes.append(merged_route)

    # 封装为Route对象
    final_routes = []
    for r in routes:
        q, dist, cost = evaluate_route(r, node_dict)
        route_obj = Route(r)
        route_obj.q, route_obj.distance, route_obj.cost = q, dist, cost
        final_routes.append(route_obj)

    return final_routes


# ====================== 3. 动态调度策略 ======================
def print_summary(routes, title="当前调度状态"):
    print(f"\n[{title}]")
    total_dist, total_cost = 0, 0
    for idx, r in enumerate(routes):
        print(
            f"  车辆 {idx + 1} | 载重: {r.q:.0f}kg | 距离: {r.distance:.1f}km | 预估成本: ¥{r.cost:.1f} | 路径: {' -> '.join(r.nodes)}")
        total_dist += r.distance
        total_cost += r.cost
    print(f"▶ 总车辆数: {len(routes)} 辆 | 总距离: {total_dist:.1f} km | 总预估成本: ¥{total_cost:.1f}")


def trigger_new_order(routes, node_dict, new_node):
    """事件：新增订单 (贪婪插入法)"""
    print(f"\n>>> 事件触发：新增订单 {new_node.id} ({new_node.q}kg, 坐标:{new_node.x},{new_node.y})")
    node_dict[new_node.id] = new_node

    best_route_idx = -1
    best_insert_pos = -1
    min_add_cost = float('inf')

    # 遍历所有路径寻找最佳插入点
    for r_idx, r in enumerate(routes):
        if r.q + new_node.q > VEHICLE_CAPACITY:
            continue  # 容量不足

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
        print(
            f"✓ 策略执行：插入到车辆 {best_route_idx + 1} 的第 {best_insert_pos} 个访问位置。边际成本增加: ¥{min_add_cost:.1f}")
    else:
        # 无车可插，派新车
        new_r = ['DC', new_node.id, 'DC']
        q, dist, cost = evaluate_route(new_r, node_dict)
        route_obj = Route(new_r)
        route_obj.q, route_obj.distance, route_obj.cost = q, dist, cost
        routes.append(route_obj)
        print("✓ 策略执行：现有车辆容量不足，派发新车进行专门配送。")


def trigger_cancel_order(routes, node_dict, cancel_id):
    """事件：取消订单 (装载率评估法)"""
    print(f"\n>>> 事件触发：取消订单 {cancel_id}")
    target_r_idx = -1
    for idx, r in enumerate(routes):
        if cancel_id in r.nodes:
            target_r_idx = idx
            break

    if target_r_idx == -1:
        print("未找到该订单。")
        return

    r = routes[target_r_idx]
    original_q = r.q
    r.nodes.remove(cancel_id)
    r.q, r.distance, r.cost = evaluate_route(r.nodes, node_dict)

    # 策略判断：如果剩余载重 <= 原载重的一半，且不仅包含起点终点
    if r.q <= original_q / 2 and len(r.nodes) > 2:
        print(f"✓ 策略执行：车辆 {target_r_idx + 1} 剩余载重({r.q}kg)偏低，取消原车，尝试将剩余客户重新分配...")
        remaining_cids = r.nodes[1:-1]
        routes.pop(target_r_idx)  # 移除原车
        for cid in remaining_cids:
            # 复用新增订单逻辑进行重新分配
            trigger_new_order(routes, node_dict, node_dict[cid])
    elif len(r.nodes) <= 2:
        print(f"✓ 策略执行：车辆 {target_r_idx + 1} 已空载，回收车辆。")
        routes.pop(target_r_idx)
    else:
        print(f"✓ 策略执行：车辆 {target_r_idx + 1} 剩余装载率尚可，继续原计划配送（跳过 {cancel_id}）。成本已重新计算。")


def trigger_change_address(routes, node_dict, target_id, new_x, new_y):
    """事件：地址变更 (先删后加)"""
    print(f"\n>>> 事件触发：客户 {target_id} 地址变更至 ({new_x}, {new_y})")
    target_node = node_dict[target_id]
    temp_q = target_node.q  # 保存原有需求

    # 1. 视为取消旧订单
    trigger_cancel_order(routes, node_dict, target_id)

    # 2. 视为在不同地点的新增订单
    target_node.x = new_x
    target_node.y = new_y
    target_node.q = temp_q
    trigger_new_order(routes, node_dict, target_node)


# ====================== 4. 主程序模拟 ======================
if __name__ == "__main__":
    # 导入测试数据 (模拟您的客户坐标和订单汇总)
    node_dict = {'DC': Node('DC', 20, 20, 0)}
    raw_customers = [
        Node('C1', 15, 28, 800),
        Node('C2', 25, 28, 700),
        Node('C3', 12, 12, 1200),
        Node('C4', 28, 10, 1000),
        Node('C5', 22, 15, 1400)
    ]
    for c in raw_customers:
        node_dict[c.id] = c

    print("==================================================")
    print(" 🚀 智能物流动态调度模拟器 (节约算法内核)")
    print("==================================================")

    # 1. 静态全局规划
    active_routes = savings_algorithm(raw_customers, node_dict)
    print_summary(active_routes, "阶段1：初始静态规划完成")

    # 2. 突发事件 A: 配送途中新增订单 C6
    new_customer = Node('C6', 18, 8, 500)
    trigger_new_order(active_routes, node_dict, new_customer)
    print_summary(active_routes, "阶段2：新增订单后状态")

    # 3. 突发事件 B: C1 突然取消订单
    trigger_cancel_order(active_routes, node_dict, 'C1')
    print_summary(active_routes, "阶段3：C1取消订单后状态")

    # 4. 突发事件 C: C3 变更送货地址
    trigger_change_address(active_routes, node_dict, 'C3', 25, 20)
    print_summary(active_routes, "阶段4：C3地址变更后最终状态")