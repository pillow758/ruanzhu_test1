import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import math
from collections import Counter

# ====================== 全局设置 ======================
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False
if not os.path.exists("输出"):
    os.mkdir("输出")

# ====================== 车型配置 ======================
VEHICLE_TYPES = [
    {'name': '燃油1', 'type': 'fuel', 'Q': 3000, 'V': 13.5, 'count': 60, 'fixed_cost': 400, 'load_factor': 0.4},
    {'name': '燃油2', 'type': 'fuel', 'Q': 1500, 'V': 10.8, 'count': 50, 'fixed_cost': 400, 'load_factor': 0.4},
    {'name': '燃油3', 'type': 'fuel', 'Q': 1250, 'V': 6.5, 'count': 50, 'fixed_cost': 400, 'load_factor': 0.4},
    {'name': '新能源1', 'type': 'electric', 'Q': 3000, 'V': 15, 'count': 10, 'fixed_cost': 400, 'load_factor': 0.35},
    {'name': '新能源2', 'type': 'electric', 'Q': 1250, 'V': 8.5, 'count': 15, 'fixed_cost': 400, 'load_factor': 0.35},
]

MAX_Q = max(v['Q'] for v in VEHICLE_TYPES)
MAX_V = max(v['V'] for v in VEHICLE_TYPES)

FUEL_PRICE = 7.61
ELECTRIC_PRICE = 1.64
CARBON_PRICE = 0.65
FUEL_ETA = 2.547
ELECTRIC_GAMMA = 0.501

EARLY_PENALTY_PER_HOUR = 20
LATE_PENALTY_PER_HOUR = 50
SERVICE_TIME_HOURS = 20 / 60

MAX_CUSTOMERS_PER_VEHICLE = 5


# ====================== 工具函数 ======================
def get_fuel_consumption(v=35.4):
    return 0.0025 * v ** 2 - 0.2554 * v + 31.75


def get_electric_consumption(v=35.4):
    return 0.0014 * v ** 2 - 0.12 * v + 36.19


def get_current_speed(t):
    h = t % 24
    if 8 <= h < 9 or 11.5 <= h < 13:
        return 9.8
    elif 10 <= h < 11.5 or 15 <= h < 17:
        return 35.4
    else:
        return 55.3


def get_load_factor(load, max_load, base):
    return 1.0 + base * (load / max_load) if max_load > 0 else 1.0


def time_str_to_hour(s):
    h, m = map(int, s.split(':'))
    return h + m / 60


# ====================== 读取数据 ======================
def load_all_data():
    print("正在读取 Excel 数据...")
    df_coords = pd.read_excel("客户坐标信息_处理后.xlsx")
    df_timewin = pd.read_excel("时间窗.xlsx")
    df_order = pd.read_excel("订单信息_按客户排序.xlsx")
    df_order.rename(columns={'目标客户编号': '目标客户编号', '重量': '重量', '体积': '体积'}, inplace=True)
    dist_file = pd.ExcelFile("各区域距离矩阵.xlsx")
    print("✅ 数据读取完成\n")
    return df_coords, dist_file, df_timewin, df_order


# ====================== ★ 订单拆分（先汇总再拆分） ======================
def do_split_orders(df_order, max_weight=3000, max_volume=15):
    """
    先按真实客户汇总需求，再拆分超容量客户
    确保每个node_id唯一
    """
    print("正在汇总并拆分订单...")

    # ★ 第一步：按客户汇总
    customer_total = df_order.groupby('目标客户编号').agg({
        '重量': 'sum',
        '体积': 'sum'
    }).reset_index()

    print(f"  原始订单：{len(df_order)}条 → 汇总客户：{len(customer_total)}个")

    # ★ 第二步：拆分超容量客户
    new_orders = []
    split_count = 0

    for _, row in customer_total.iterrows():
        cid = int(row['目标客户编号'])
        weight = float(row['重量'])
        volume = float(row['体积'])

        if weight <= max_weight and volume <= max_volume:
            new_orders.append({
                'node_id': str(cid),
                'real_cid': cid,
                'q': round(weight, 2),
                'v': round(volume, 2),
                'is_split': False
            })
        else:
            num_splits = max(math.ceil(weight / max_weight), math.ceil(volume / max_volume))
            split_q = weight / num_splits
            split_v = volume / num_splits
            split_count += 1

            print(f"  拆分客户{cid}: {weight:.0f}kg → {num_splits}份 × {split_q:.0f}kg")

            for i in range(num_splits):
                new_orders.append({
                    'node_id': f"{cid}_{i + 1}",
                    'real_cid': cid,
                    'q': round(split_q, 2),
                    'v': round(split_v, 2),
                    'is_split': True
                })

    split_df = pd.DataFrame(new_orders)

    # ★ 验证唯一性
    if not split_df['node_id'].is_unique:
        duplicates = split_df['node_id'][split_df['node_id'].duplicated()].tolist()
        print(f"❌ 重复的node_id: {duplicates}")
        # 手动去重
        split_df = split_df.drop_duplicates(subset='node_id', keep='first')
        print(f"  已去重，剩余{len(split_df)}条")

    print(f"✅ 拆分完成：{len(customer_total)}个客户 → {len(split_df)}个子订单（拆分{split_count}个客户）")
    print(f"   最大子订单：{split_df['q'].max():.1f}kg, {split_df['v'].max():.1f}m³\n")

    return split_df


# ====================== 构建节点 ======================
def build_nodes(df_coords, split_df):
    """构建客户节点"""
    print("正在构建客户节点...")
    dc = df_coords[df_coords['类型'] == '配送中心'].iloc[0]
    dc_x, dc_y = dc['X (km)'], dc['Y (km)']

    cid_info = {}
    for _, row in df_coords[df_coords['类型'] == '客户'].iterrows():
        cid_info[int(row['ID'])] = {
            'group': int(row['第几组']), 'x': row['X (km)'], 'y': row['Y (km)']
        }

    nodes = []
    for _, o in split_df.iterrows():
        info = cid_info.get(o['real_cid'], {'group': 1, 'x': 0, 'y': 0})
        nodes.append({
            'node_id': o['node_id'], 'real_cid': o['real_cid'],
            'group': info['group'], 'x': info['x'], 'y': info['y'],
            'q': o['q'], 'v': o['v'], 'is_split': o['is_split']
        })

    nodes_df = pd.DataFrame(nodes)
    print(f"✅ 构建{len(nodes_df)}个节点\n")
    return dc_x, dc_y, nodes_df


# ====================== 辅助函数 ======================
def get_node_info(nodes_df, node_id):
    """获取单个节点信息"""
    match = nodes_df[nodes_df['node_id'] == node_id]
    if match.empty:
        return {'real_cid': 0, 'q': 0, 'v': 0, 'group': 1}
    row = match.iloc[0]
    return {
        'real_cid': row['real_cid'], 'q': row['q'],
        'v': row['v'], 'group': row['group']
    }


def select_vehicle_simple(q, v):
    """简化的车辆选择"""
    for veh in sorted(VEHICLE_TYPES, key=lambda x: x['Q']):
        if q <= veh['Q'] and v <= veh['V']:
            return veh
    return None


def select_best_vehicle(q, v, inventory):
    """选择最经济的车型"""
    candidates = []
    for veh in VEHICLE_TYPES:
        if q <= veh['Q'] and v <= veh['V'] and inventory.get(veh['name'], 0) > 0:
            est = veh['fixed_cost'] + q * 0.6
            candidates.append((veh, est))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[1])
    return candidates[0][0]


# ====================== 成本计算 ======================
def calc_route_cost_detail(node_ids, nodes_df, group, dm, tw_dict, vehicle, start_time=8.0):
    """计算单条路径成本"""
    total_q = 0
    total_v = 0
    for n in node_ids:
        info = get_node_info(nodes_df, n)
        total_q += info['q']
        total_v += info['v']

    # 获取真实客户ID并去重连续
    real_cids = []
    for n in node_ids:
        rc = get_node_info(nodes_df, n)['real_cid']
        if not real_cids or real_cids[-1] != rc:
            real_cids.append(rc)

    # 计算距离
    dist = 0
    path = [0] + real_cids + [0]
    for i in range(len(path) - 1):
        try:
            if path[i] == 0:
                dist += dm.loc['配送中心', f'客户{path[i + 1]}']
            elif path[i + 1] == 0:
                dist += dm.loc[f'客户{path[i]}', '配送中心']
            else:
                dist += dm.loc[f'客户{path[i]}', f'客户{path[i + 1]}']
        except:
            dist += 20

    # 能耗和时间窗
    energy, ct, early, late = 0.0, start_time, 0.0, 0.0
    remaining = total_q

    for i in range(len(path) - 1):
        fr, to = path[i], path[i + 1]
        try:
            if fr == 0:
                d = dm.loc['配送中心', f'客户{to}']
            elif to == 0:
                d = dm.loc[f'客户{fr}', '配送中心']
            else:
                d = dm.loc[f'客户{fr}', f'客户{to}']
            d = float(d)
        except:
            d = 20

        sp = get_current_speed(ct)
        ct += d / sp

        lf = get_load_factor(remaining, vehicle['Q'], vehicle['load_factor'])
        if vehicle['type'] == 'fuel':
            cons = get_fuel_consumption(sp)
            energy += (cons / 100) * lf * d * FUEL_PRICE
        else:
            cons = get_electric_consumption(sp)
            energy += (cons / 100) * lf * d * ELECTRIC_PRICE

        if to != 0 and to in tw_dict:
            e_win, l_win = tw_dict[to]
            if ct < e_win:
                early += (e_win - ct) * EARLY_PENALTY_PER_HOUR
                ct = e_win
            elif ct > l_win:
                late += (ct - l_win) * LATE_PENALTY_PER_HOUR
            ct += SERVICE_TIME_HOURS

            # 减去该真实客户的总需求
            c_q = 0
            for n in node_ids:
                if get_node_info(nodes_df, n)['real_cid'] == to:
                    c_q += get_node_info(nodes_df, n)['q']
            remaining -= c_q
            remaining = max(0, remaining)

    if vehicle['type'] == 'fuel':
        carbon = (energy / FUEL_PRICE) * FUEL_ETA * CARBON_PRICE
    else:
        carbon = (energy / ELECTRIC_PRICE) * ELECTRIC_GAMMA * CARBON_PRICE

    total = vehicle['fixed_cost'] + energy + carbon + early + late

    return {
        'distance': round(dist, 2),
        'energy': round(energy, 2),
        'carbon': round(carbon, 2),
        'early': round(early, 2),
        'late': round(late, 2),
        'total': round(total, 2),
        'end_time': round(ct, 2)
    }


def optimize_start_time(node_ids, nodes_df, group, dm, tw_dict, vehicle):
    """搜索最优出发时间（6:00-12:00，步长15分钟）"""
    best_cost = float('inf')
    best_start = 8.0
    best_result = None

    for start in np.arange(6.0, 12.25, 0.25):
        result = calc_route_cost_detail(node_ids, nodes_df, group, dm, tw_dict, vehicle, start)
        if result and result['total'] < best_cost:
            best_cost = result['total']
            best_start = start
            best_result = result

    return best_start, best_result


# ====================== 节约算法 ======================
def savings_algorithm(group, group_nodes, dm, tw_dict):
    """节约算法（使用成本节约）"""
    if group_nodes.empty:
        return []

    node_ids = group_nodes['node_id'].tolist()
    nid_to_real = dict(zip(group_nodes['node_id'], group_nodes['real_cid']))
    q_dict = dict(zip(group_nodes['node_id'], group_nodes['q']))
    v_dict = dict(zip(group_nodes['node_id'], group_nodes['v']))

    # 计算成本节约值
    savings = []
    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            ni, nj = node_ids[i], node_ids[j]
            ri, rj = nid_to_real[ni], nid_to_real[nj]

            if ri == rj:
                continue

            try:
                veh_i = select_vehicle_simple(q_dict[ni], v_dict[ni])
                veh_j = select_vehicle_simple(q_dict[nj], v_dict[nj])

                if veh_i and veh_j:
                    cost_i = calc_route_cost_detail([ni], group_nodes, group, dm, tw_dict, veh_i)
                    cost_j = calc_route_cost_detail([nj], group_nodes, group, dm, tw_dict, veh_j)

                    merged_q = q_dict[ni] + q_dict[nj]
                    merged_v = v_dict[ni] + v_dict[nj]
                    merged_veh = select_vehicle_simple(merged_q, merged_v)

                    if merged_veh and merged_q <= MAX_Q and merged_v <= MAX_V:
                        cost_merged = calc_route_cost_detail([ni, nj], group_nodes, group, dm, tw_dict, merged_veh)

                        if cost_i and cost_j and cost_merged:
                            cost_saving = (cost_i['total'] + cost_j['total']) - cost_merged['total']
                            if cost_saving > 0:
                                savings.append((ni, nj, cost_saving))
            except:
                continue

    savings.sort(key=lambda x: -x[2])

    # 初始化
    routes = [[n] for n in node_ids]
    route_rcs = [{nid_to_real[n]} for n in node_ids]

    # 合并
    for ni, nj, s in savings:
        idx_i = next((idx for idx, r in enumerate(routes) if ni in r), None)
        idx_j = next((idx for idx, r in enumerate(routes) if nj in r), None)

        if idx_i is None or idx_j is None or idx_i == idx_j:
            continue
        if route_rcs[idx_i] & route_rcs[idx_j]:
            continue

        tq = sum(q_dict[n] for n in routes[idx_i] + routes[idx_j])
        tv = sum(v_dict[n] for n in routes[idx_i] + routes[idx_j])

        if tq > MAX_Q or tv > MAX_V:
            continue

        merged = routes[idx_i] + routes[idx_j]
        merged_rcs = route_rcs[idx_i] | route_rcs[idx_j]

        routes.pop(max(idx_i, idx_j))
        routes.pop(min(idx_i, idx_j))
        route_rcs.pop(max(idx_i, idx_j))
        route_rcs.pop(min(idx_i, idx_j))

        routes.append(merged)
        route_rcs.append(merged_rcs)

    res = []
    for r, rcs in zip(routes, route_rcs):
        tq = sum(q_dict[n] for n in r)
        tv = sum(v_dict[n] for n in r)
        res.append({
            'group': group,
            'nodes': r,
            'real_cids': list(rcs),
            'q': round(tq, 2),
            'v': round(tv, 2),
            'n_customers': len(rcs)
        })

    return res


def generate_initial_routes(nodes_df, dist_file, df_timewin):
    """生成初始路径"""
    print("正在生成初始路径（使用成本节约）...")

    df_timewin['客户编号'] = df_timewin['客户编号'].astype(int)
    df_timewin['e'] = df_timewin['开始时间'].apply(time_str_to_hour)
    df_timewin['l'] = df_timewin['结束时间'].apply(time_str_to_hour)
    tw_dict = dict(zip(df_timewin['客户编号'], zip(df_timewin['e'], df_timewin['l'])))

    sheets = ['区域1', '区域2', '区域3', '区域4']
    groups = sorted(nodes_df['group'].unique())

    all_routes = []
    for g in groups:
        sheet = sheets[min(g - 1, len(sheets) - 1)]
        try:
            dm = pd.read_excel(dist_file, sheet_name=sheet).set_index('Unnamed: 0')
            group_data = nodes_df[nodes_df['group'] == g]
            routes = savings_algorithm(g, group_data, dm, tw_dict)
            all_routes.extend(routes)
        except Exception as e:
            print(f"  区域{g}失败: {e}")

    routes_df = pd.DataFrame(all_routes)

    if routes_df.empty:
        print("❌ 未生成任何路径")
        return None

    # 验证唯一性
    all_nodes_list = []
    for nodes in routes_df['nodes']:
        all_nodes_list.extend(nodes)

    duplicates = {k: v for k, v in Counter(all_nodes_list).items() if v > 1}
    if duplicates:
        print(f"❌ 节点重复: {len(duplicates)}个")
        return None

    print(f"✅ 初始路径：{len(routes_df)}条\n")
    return routes_df


# ====================== 最终成本计算 ======================
def calculate_final_cost(routes_df, nodes_df, dist_file, df_timewin):
    """计算最终成本（最优出发时间 + 装载率优先）"""
    print("=" * 50)
    print("计算最终成本（最优出发时间 + 装载率优先）")
    print("=" * 50)

    df_timewin['客户编号'] = df_timewin['客户编号'].astype(int)
    df_timewin['e'] = df_timewin['开始时间'].apply(time_str_to_hour)
    df_timewin['l'] = df_timewin['结束时间'].apply(time_str_to_hour)
    tw_dict = dict(zip(df_timewin['客户编号'], zip(df_timewin['e'], df_timewin['l'])))

    dm_dict = {}
    for g in range(1, 5):
        try:
            dm = pd.read_excel(dist_file, sheet_name=f'区域{g}').set_index('Unnamed: 0')
            dm_dict[g] = dm
        except:
            continue

    inventory = {v['name']: v['count'] for v in VEHICLE_TYPES}
    used = {v['name']: 0 for v in VEHICLE_TYPES}

    # 按装载率降序
    sorted_df = routes_df.copy()
    sorted_df['load_rate'] = sorted_df['q'] / MAX_Q
    sorted_df = sorted_df.sort_values('load_rate', ascending=False)

    results = []

    for _, route in sorted_df.iterrows():
        node_ids = route['nodes']
        group = route['group']
        total_q = route['q']
        total_v = route['v']

        if group not in dm_dict:
            continue

        dm = dm_dict[group]
        vehicle = select_best_vehicle(total_q, total_v, inventory)

        if vehicle is None:
            # 拆分处理
            for nid in node_ids:
                info = get_node_info(nodes_df, nid)
                nq, nv = info['q'], info['v']
                v2 = select_best_vehicle(nq, nv, inventory)
                if v2:
                    inventory[v2['name']] -= 1
                    used[v2['name']] += 1
                    best_start, cost = optimize_start_time([nid], nodes_df, group, dm, tw_dict, v2)
                    if cost:
                        rc = info['real_cid']
                        results.append(make_result_row(group, [rc], nq, nv, v2, cost, best_start))
                else:
                    print(f"  警告：节点{nid}无法分配车辆")
        else:
            inventory[vehicle['name']] -= 1
            used[vehicle['name']] += 1
            best_start, cost = optimize_start_time(node_ids, nodes_df, group, dm, tw_dict, vehicle)
            if cost:
                real_cids = []
                for nid in node_ids:
                    rc = get_node_info(nodes_df, nid)['real_cid']
                    if not real_cids or real_cids[-1] != rc:
                        real_cids.append(rc)
                results.append(make_result_row(group, real_cids, total_q, total_v, vehicle, cost, best_start))

    result_df = pd.DataFrame(results)

    if not result_df.empty:
        print(f"\n✅ 完成：{len(result_df)}条路径")
        print(f"   总成本：{result_df['总成本'].sum():.2f}")
        print(f"   早到惩罚：{result_df['早到惩罚'].sum():.2f}")
        print(f"   迟到惩罚：{result_df['迟到惩罚'].sum():.2f}")
        print(f"   平均装载率：{(result_df['总重量(kg)'].sum() / (len(result_df) * MAX_Q) * 100):.1f}%\n")

    return result_df, used


def make_result_row(group, real_cids, q, v, vehicle, cost, start_time):
    """构建结果行"""
    return {
        '分组': group,
        '路径': f"0 - {' - '.join(map(str, real_cids))} - 0",
        '总重量(kg)': round(q, 2),
        '总体积(m³)': round(v, 2),
        '车型': vehicle['name'],
        '客户数': len(real_cids),
        '固定成本': vehicle['fixed_cost'],
        '发车时间': f"{int(start_time):02d}:{int((start_time % 1) * 60):02d}",
        '行驶距离(km)': cost['distance'],
        '能耗成本': cost['energy'],
        '碳成本': cost['carbon'],
        '早到惩罚': cost['early'],
        '迟到惩罚': cost['late'],
        '总成本': cost['total'],
        '装载率': round(q / vehicle['Q'] * 100, 1)
    }


# ====================== 绘图 ======================
def plot_routes(df, nodes_df, dc_x, dc_y, title):
    print(f"正在绘图: {title}...")
    plt.figure(figsize=(14, 12))
    colors = plt.cm.tab20(np.linspace(0, 1, 20))

    for i, g in enumerate(sorted(df['分组'].unique())):
        gr = df[df['分组'] == g]
        gn = nodes_df[nodes_df['group'] == g]

        for cid in gn['real_cid'].unique():
            sub = gn[gn['real_cid'] == cid]
            plt.scatter(sub['x'].mean(), sub['y'].mean(), c=[colors[i % 20]], s=40, zorder=3)
            plt.text(sub['x'].mean() + 0.2, sub['y'].mean() + 0.2, str(cid), fontsize=6)

        for _, r in gr.iterrows():
            cs = [int(x) for x in str(r['路径']).replace('0 - ', '').replace(' - 0', '').split(' - ') if x.isdigit()]
            xs, ys = [dc_x], [dc_y]
            for c in cs:
                sub = gn[gn['real_cid'] == c]
                if not sub.empty:
                    xs.append(sub['x'].mean())
                    ys.append(sub['y'].mean())
            xs.append(dc_x);
            ys.append(dc_y)
            plt.plot(xs, ys, c=colors[i % 20], lw=1, alpha=0.6)

    plt.scatter(dc_x, dc_y, c='red', marker='s', s=300, label='配送中心', zorder=5)
    plt.title(title, fontsize=14)
    plt.xlabel('X (km)');
    plt.ylabel('Y (km)')
    plt.legend();
    plt.grid(alpha=0.3);
    plt.axis('equal')
    plt.tight_layout()
    plt.savefig(f'输出/{title}.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ 已保存: 输出/{title}.png\n")


# ====================== 主函数 ======================
def main():
    print("\n" + "=" * 60)
    print("🚀 绿色物流配送优化系统 v2.0")
    print("   优化特性：最优发车时间 + 成本节约 + 装载率优先")
    print("=" * 60 + "\n")

    # 1. 读取数据
    df_coords, dist_file, df_tw, df_order = load_all_data()

    # 2. 拆分订单（先汇总再拆分）
    split_df = do_split_orders(df_order, MAX_Q, MAX_V)

    # 3. 构建节点
    dc_x, dc_y, nodes_df = build_nodes(df_coords, split_df)

    # 4. 生成初始路径
    routes_df = generate_initial_routes(nodes_df, dist_file, df_tw)

    if routes_df is None or routes_df.empty:
        print("❌ 路径生成失败")
        return

    # 5. 计算最终成本
    final_result, used_vehicles = calculate_final_cost(routes_df, nodes_df, dist_file, df_tw)

    if final_result.empty:
        print("❌ 成本计算失败")
        return

    # 6. 保存
    final_result.to_excel('输出/配送方案_优化版.xlsx', index=False)
    print("✅ 已保存: 输出/配送方案_优化版.xlsx\n")

    # 7. 绘图
    plot_routes(final_result, nodes_df, dc_x, dc_y, "优化配送方案")

    # 8. 统计
    print("=" * 60)
    print("📊 最终统计")
    print("=" * 60)

    total = final_result['总成本'].sum()
    print(f"\n💰 总成本：{total:,.2f} 元")
    print(f"   固定成本：{final_result['固定成本'].sum():,.2f}（{final_result['固定成本'].sum() / total * 100:.1f}%）")
    print(f"   能耗成本：{final_result['能耗成本'].sum():,.2f}（{final_result['能耗成本'].sum() / total * 100:.1f}%）")
    print(f"   碳成本：{final_result['碳成本'].sum():,.2f}（{final_result['碳成本'].sum() / total * 100:.1f}%）")
    print(f"   早到惩罚：{final_result['早到惩罚'].sum():,.2f}（{final_result['早到惩罚'].sum() / total * 100:.1f}%）")
    print(f"   迟到惩罚：{final_result['迟到惩罚'].sum():,.2f}（{final_result['迟到惩罚'].sum() / total * 100:.1f}%）")

    print(f"\n🚗 配送效率：")
    print(f"   路径数：{len(final_result)}")
    print(f"   总距离：{final_result['行驶距离(km)'].sum():,.2f} km")
    print(f"   平均装载率：{final_result['装载率'].mean():.1f}%")

    low_load = final_result[final_result['装载率'] < 50]
    if len(low_load) > 0:
        print(f"   装载率<50%：{len(low_load)}条（最低{low_load['装载率'].min():.1f}%）")

    print(f"\n🚙 车辆使用：")
    for v in VEHICLE_TYPES:
        n = used_vehicles.get(v['name'], 0)
        if n > 0:
            print(f"   {v['name']}（{v['Q']}kg）：{n}/{v['count']}辆")

    if '发车时间' in final_result.columns:
        print(f"\n⏰ 发车时间分布：")
        hours = final_result['发车时间'].apply(lambda x: int(x.split(':')[0]))
        for h in range(6, 13):
            cnt = len(hours[hours == h])
            if cnt > 0:
                print(f"   {h}:00-{h}:59：{cnt}辆车")

    print("\n✅ 程序运行完成！")


if __name__ == "__main__":
    main()