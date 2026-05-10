import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import math
import random
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

# ====================== 相似度权重（题目给定） ======================
SIMILARITY_WEIGHTS = {
    'time_window': 0.066408334,   # 标准化时间宽度
    'weight': 0.475652961,        # 标准化重量
    'volume': 0.415833566,        # 标准化体积
    'distance': 0.04210514        # 标准化距离
}

# ====================== 工具函数 ======================
def get_fuel_consumption(v=35.4):
    return 0.0025 * v**2 - 0.2554 * v + 31.75

def get_electric_consumption(v=35.4):
    return 0.0014 * v**2 - 0.12 * v + 36.19

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

def compute_path_distance(path_cids, group_id, dist_file):
    try:
        dm = pd.read_excel(dist_file, sheet_name=f"区域{group_id}").set_index("Unnamed: 0")
    except:
        return 0.0
    dist = 0.0
    full = [0] + path_cids + [0]
    for i in range(len(full)-1):
        fr, to = full[i], full[i+1]
        try:
            if fr == 0:
                dist += dm.loc["配送中心", f"客户{to}"]
            elif to == 0:
                dist += dm.loc[f"客户{fr}", "配送中心"]
            else:
                dist += dm.loc[f"客户{fr}", f"客户{to}"]
        except:
            continue
    return dist

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

# ====================== 订单拆分 ======================
def do_split_orders(df_order, max_weight=3000, max_volume=15):
    print("正在汇总并拆分订单...")
    customer_total = df_order.groupby('目标客户编号').agg({'重量': 'sum', '体积': 'sum'}).reset_index()
    print(f"  原始订单：{len(df_order)}条 → 汇总客户：{len(customer_total)}个")

    new_orders = []
    split_count = 0
    for _, row in customer_total.iterrows():
        cid = int(row['目标客户编号'])
        weight = float(row['重量'])
        volume = float(row['体积'])
        if weight <= max_weight and volume <= max_volume:
            new_orders.append({
                'node_id': str(cid), 'real_cid': cid,
                'q': round(weight, 2), 'v': round(volume, 2), 'is_split': False
            })
        else:
            num_splits = max(math.ceil(weight / max_weight), math.ceil(volume / max_volume))
            split_q = weight / num_splits
            split_v = volume / num_splits
            split_count += 1
            for i in range(num_splits):
                new_orders.append({
                    'node_id': f"{cid}_{i + 1}", 'real_cid': cid,
                    'q': round(split_q, 2), 'v': round(split_v, 2), 'is_split': True
                })
    split_df = pd.DataFrame(new_orders)
    if not split_df['node_id'].is_unique:
        split_df = split_df.drop_duplicates(subset='node_id', keep='first')
    print(f"✅ 拆分完成：{len(customer_total)}个客户 → {len(split_df)}个子订单（拆分{split_count}个客户）\n")
    return split_df

# ====================== 构建节点 ======================
def build_nodes(df_coords, split_df):
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

def get_node_info(nodes_df, node_id):
    match = nodes_df[nodes_df['node_id'] == node_id]
    if match.empty:
        return {'real_cid': 0, 'q': 0, 'v': 0, 'group': 1}
    row = match.iloc[0]
    return {'real_cid': row['real_cid'], 'q': row['q'], 'v': row['v'], 'group': row['group']}

def select_vehicle_simple(q, v):
    for veh in sorted(VEHICLE_TYPES, key=lambda x: x['Q']):
        if q <= veh['Q'] and v <= veh['V']:
            return veh
    return None

def select_best_vehicle(q, v, inventory):
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
    total_q = sum(get_node_info(nodes_df, n)['q'] for n in node_ids)
    total_v = sum(get_node_info(nodes_df, n)['v'] for n in node_ids)

    real_cids = []
    for n in node_ids:
        rc = get_node_info(nodes_df, n)['real_cid']
        if not real_cids or real_cids[-1] != rc:
            real_cids.append(rc)

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

    energy, ct, early, late = 0.0, start_time, 0.0, 0.0
    remaining = total_q
    visited = set()

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

        if to != 0 and to not in visited:
            visited.add(to)
            if to in tw_dict:
                e_win, l_win = tw_dict[to]
                if ct < e_win:
                    early += (e_win - ct) * EARLY_PENALTY_PER_HOUR
                    ct = e_win
                elif ct > l_win:
                    late += (ct - l_win) * LATE_PENALTY_PER_HOUR
                ct += SERVICE_TIME_HOURS
            remaining -= nodes_df[nodes_df['real_cid'] == to]['q'].sum()
            remaining = max(0, remaining)

    carbon = (energy / FUEL_PRICE) * FUEL_ETA * CARBON_PRICE if vehicle['type'] == 'fuel' else (energy / ELECTRIC_PRICE) * ELECTRIC_GAMMA * CARBON_PRICE
    total = vehicle['fixed_cost'] + energy + carbon + early + late

    return {'distance': round(dist, 2), 'energy': round(energy, 2), 'carbon': round(carbon, 2),
            'early': round(early, 2), 'late': round(late, 2), 'total': round(total, 2)}

def optimize_start_time(node_ids, nodes_df, group, dm, tw_dict, vehicle):
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
    if group_nodes.empty:
        return []
    node_ids = group_nodes['node_id'].tolist()
    nid_to_real = dict(zip(group_nodes['node_id'], group_nodes['real_cid']))
    q_dict = dict(zip(group_nodes['node_id'], group_nodes['q']))
    v_dict = dict(zip(group_nodes['node_id'], group_nodes['v']))

    savings = []
    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            ni, nj = node_ids[i], node_ids[j]
            ri, rj = nid_to_real[ni], nid_to_real[nj]
            if ri == rj:
                continue
            merged_q = q_dict[ni] + q_dict[nj]
            merged_v = v_dict[ni] + v_dict[nj]
            if merged_q > MAX_Q or merged_v > MAX_V:
                continue
            try:
                d0i = dm.loc['配送中心', f'客户{ri}'] if f'客户{ri}' in dm.columns else 0
                d0j = dm.loc['配送中心', f'客户{rj}'] if f'客户{rj}' in dm.columns else 0
                dij = dm.loc[f'客户{ri}', f'客户{rj}'] if (f'客户{ri}' in dm.index and f'客户{rj}' in dm.columns) else 0
                saving = d0i + d0j - dij
                if saving > 0:
                    savings.append((ni, nj, saving))
            except:
                continue
    savings.sort(key=lambda x: -x[2])

    routes = [[n] for n in node_ids]
    route_rcs = [{nid_to_real[n]} for n in node_ids]
    route_q = [[q_dict[n]] for n in node_ids]
    route_v = [[v_dict[n]] for n in node_ids]

    for ni, nj, s in savings:
        idx_i = next((idx for idx, r in enumerate(routes) if ni in r), None)
        idx_j = next((idx for idx, r in enumerate(routes) if nj in r), None)
        if idx_i is None or idx_j is None or idx_i == idx_j:
            continue
        if route_rcs[idx_i] & route_rcs[idx_j]:
            continue
        tq = sum(route_q[idx_i]) + sum(route_q[idx_j])
        tv = sum(route_v[idx_i]) + sum(route_v[idx_j])
        if tq > MAX_Q or tv > MAX_V:
            continue
        routes[idx_i].extend(routes[idx_j])
        route_rcs[idx_i].update(route_rcs[idx_j])
        route_q[idx_i].extend(route_q[idx_j])
        route_v[idx_i].extend(route_v[idx_j])
        routes.pop(idx_j)
        route_rcs.pop(idx_j)
        route_q.pop(idx_j)
        route_v.pop(idx_j)

    res = []
    for r, rcs in zip(routes, route_rcs):
        tq = sum(q_dict[n] for n in r)
        tv = sum(v_dict[n] for n in r)
        res.append({
            'group': group, 'nodes': r, 'real_cids': list(rcs),
            'q': round(tq, 2), 'v': round(tv, 2)
        })
    return res

def generate_initial_routes(nodes_df, dist_file, df_timewin):
    print("正在生成初始路径...")
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
    print("计算最终成本...")

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
        print(f"✅ 完成：{len(result_df)}条路径")
        print(f"   总成本：{result_df['总成本'].sum():.2f}")
        print(f"   早到惩罚：{result_df['早到惩罚'].sum():.2f}")
        print(f"   迟到惩罚：{result_df['迟到惩罚'].sum():.2f}")
        print(f"   平均装载率：{(result_df['总重量(kg)'].sum() / (len(result_df) * MAX_Q) * 100):.1f}%\n")

    return result_df, used

def make_result_row(group, real_cids, q, v, vehicle, cost, start_time):
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

# ====================== 获取车辆路径信息 ======================
def get_vehicle_route_info(final_result):
    vehicle_routes = []
    for _, row in final_result.iterrows():
        cids = [int(x) for x in str(row['路径']).replace('0 - ', '').replace(' - 0', '').split(' - ') if x.isdigit()]
        vehicle_name = row['车型']
        vehicle = None
        for v in VEHICLE_TYPES:
            if v['name'] == vehicle_name:
                vehicle = v
                break
        if vehicle:
            vehicle_routes.append({
                'vehicle': vehicle,
                'route': cids,
                'total_q': row['总重量(kg)'],
                'total_v': row['总体积(m³)'],
                'group': row['分组'],
                'cost': row['总成本'],
                'start_time': row['发车时间'] if '发车时间' in row else '8:00'
            })
    return vehicle_routes

# ====================== 相似度计算 ======================
def calculate_similarity(cid_i, cid_j, nodes_df, tw_dict, dist_file, group):
    """
    计算客户i和客户j的相似度
    指标：时间窗宽度、重量、体积、距离
    """
    # 获取客户信息
    qi = nodes_df[nodes_df['real_cid'] == cid_i]['q'].sum()
    qj = nodes_df[nodes_df['real_cid'] == cid_j]['q'].sum()
    vi = nodes_df[nodes_df['real_cid'] == cid_i]['v'].sum()
    vj = nodes_df[nodes_df['real_cid'] == cid_j]['v'].sum()
    
    # 时间窗宽度
    if cid_i in tw_dict and cid_j in tw_dict:
        twi = tw_dict[cid_i][1] - tw_dict[cid_i][0]
        twj = tw_dict[cid_j][1] - tw_dict[cid_j][0]
    else:
        twi, twj = 1, 1
    tw_diff = abs(twi - twj) / max(twi, twj, 1)
    
    # 重量差异（归一化）
    q_diff = abs(qi - qj) / max(qi, qj, 1)
    
    # 体积差异（归一化）
    v_diff = abs(vi - vj) / max(vi, vj, 1)
    
    # 距离差异（到配送中心的距离差异）
    try:
        dm = pd.read_excel(dist_file, sheet_name=f'区域{group}').set_index('Unnamed: 0')
        di = dm.loc['配送中心', f'客户{cid_i}'] if f'客户{cid_i}' in dm.columns else 50
        dj = dm.loc['配送中心', f'客户{cid_j}'] if f'客户{cid_j}' in dm.columns else 50
    except:
        di, dj = 50, 50
    d_diff = abs(di - dj) / max(di, dj, 1)
    
    # 加权相似度
    similarity = (
        SIMILARITY_WEIGHTS['time_window'] * tw_diff +
        SIMILARITY_WEIGHTS['weight'] * q_diff +
        SIMILARITY_WEIGHTS['volume'] * v_diff +
        SIMILARITY_WEIGHTS['distance'] * d_diff
    )
    
    return similarity

def modify_order_demo(final_result, nodes_df, dist_file, df_timewin):
    """
    修改订单演示：先删除旧订单，再增加新订单
    修改 = 取消原有配送 + 新增配送需求
    """
    print("\n" + "="*60)
    print("📦 订单修改演示（先删除再增加）")
    print("="*60)
    
    df_timewin_copy = df_timewin.copy()
    df_timewin_copy['客户编号'] = df_timewin_copy['客户编号'].astype(int)
    df_timewin_copy['e'] = df_timewin_copy['开始时间'].apply(time_str_to_hour)
    df_timewin_copy['l'] = df_timewin_copy['结束时间'].apply(time_str_to_hour)
    tw_dict = dict(zip(df_timewin_copy['客户编号'], zip(df_timewin_copy['e'], df_timewin_copy['l'])))
    
    vehicle_routes = get_vehicle_route_info(final_result)
    original_total_cost = sum(vr['cost'] for vr in vehicle_routes)
    
    # ★ 第一步：选择要修改的订单（随机选一个多客户路径中的客户）
    multi_customer_routes = []
    for v_idx, vr in enumerate(vehicle_routes):
        if len(vr['route']) >= 2:
            multi_customer_routes.append((v_idx, vr))
    
    if not multi_customer_routes:
        print("❌ 没有多客户路径可供演示")
        return
    
    v_idx, vr = random.choice(multi_customer_routes)
    old_route = [int(x) for x in vr['route']]
    old_q = float(vr['total_q'])
    old_v = float(vr['total_v'])
    old_cost = float(vr['cost'])
    vehicle_name = vr['vehicle']['name']
    group = vr['group']
    
    # 随机选择要修改的客户
    modify_cid = random.choice(old_route)
    
    # 获取该客户信息
    modify_q_old = nodes_df[nodes_df['real_cid'] == modify_cid]['q'].sum()
    modify_v_old = nodes_df[nodes_df['real_cid'] == modify_cid]['v'].sum()
    
    # ★ 第二阶段：生成新的订单需求
    # 新需求在旧需求的50%-150%之间
    new_q = round(modify_q_old * random.uniform(0.5, 1.5), 2)
    new_v = round(modify_v_old * random.uniform(0.5, 1.5), 2)
    new_q = min(new_q, MAX_Q - 100)
    new_v = min(new_v, MAX_V - 2)
    
    # 时间窗也稍微调整
    if modify_cid in tw_dict:
        tw_start_old, tw_end_old = tw_dict[modify_cid]
        tw_shift = random.uniform(-5, 5)
        tw_start_new = max(6.0, tw_start_old + tw_shift)
        tw_end_new = max(tw_start_new + 1, tw_end_old + tw_shift)
    else:
        tw_start_new, tw_end_new = 8.0, 16.0
    
    print(f"\n🔄 订单修改事件：")
    print(f"   客户ID：{modify_cid}")
    print(f"   目标车辆：{vehicle_name}")
    print(f"   原路径：{old_route}")
    print(f"   旧需求：{modify_q_old:.2f}kg, {modify_v_old:.2f}m³")
    print(f"   新需求：{new_q:.2f}kg, {new_v:.2f}m³")
    print(f"   新时间窗：{tw_start_new:.1f}h - {tw_end_new:.1f}h")
    
    # ====== 先删除旧订单 ======
    print(f"\n📋 第一步：删除旧订单")
    
    # 从路径中移除
    new_route_after_del = [c for c in old_route if c != modify_cid]
    remaining_q = old_q - modify_q_old
    remaining_v = old_v - modify_v_old
    
    # 确保不为负
    remaining_q = max(0, remaining_q)
    remaining_v = max(0, remaining_v)
    
    half_q = old_q / 2
    
    # 判断保留还是取消原车
    if remaining_q > half_q and remaining_q > 0 and len(new_route_after_del) > 0:
        print(f"   剩余重量({remaining_q:.2f}kg) > 原重量的一半({half_q:.2f}kg)")
        print(f"   → 原车继续配送剩余订单")
        
        vr['route'] = new_route_after_del
        vr['total_q'] = remaining_q
        vr['total_v'] = remaining_v
        
        # 重新计算原车成本
        node_ids = []
        for cid in new_route_after_del:
            matched = nodes_df[nodes_df['real_cid'] == cid]
            if not matched.empty:
                node_ids.extend(matched['node_id'].tolist())
        
        if node_ids:
            try:
                dm = pd.read_excel(dist_file, sheet_name=f'区域{group}').set_index('Unnamed: 0')
            except:
                dm = None
            
            if dm:
                new_veh = select_vehicle_simple(remaining_q, remaining_v)
                if new_veh and new_veh['Q'] < vr['vehicle']['Q']:
                    vr['vehicle'] = new_veh
                best_start, cost = optimize_start_time(node_ids, nodes_df, group, dm, tw_dict, vr['vehicle'])
                if cost:
                    vr['cost'] = cost['total']
    else:
        print(f"   剩余重量({remaining_q:.2f}kg) ≤ 原重量的一半({half_q:.2f}kg)")
        print(f"   → 原车取消，剩余客户重新分配")
        
        # 将剩余客户分配到其他车辆（简化处理）
        remaining_cids = new_route_after_del
        for move_cid in remaining_cids:
            move_q = nodes_df[nodes_df['real_cid']==move_cid]['q'].sum()
            move_v = nodes_df[nodes_df['real_cid']==move_cid]['v'].sum()
            
            best_other = None
            for other_idx, other_vr in enumerate(vehicle_routes):
                if other_idx == v_idx:
                    continue
                if other_vr['group'] != group:
                    continue
                if other_vr['total_q'] + move_q <= other_vr['vehicle']['Q']:
                    if other_vr['total_v'] + move_v <= other_vr['vehicle']['V']:
                        if move_cid not in other_vr['route']:
                            best_other = other_vr
                            break
            
            if best_other:
                best_other['route'] = [move_cid] + best_other['route']
                best_other['total_q'] += move_q
                best_other['total_v'] += move_v
                best_other['cost'] += move_q * 0.3
        
        # 原车取消
        vr['route'] = []
        vr['total_q'] = 0
        vr['total_v'] = 0
        vr['cost'] = 0
    
    # ====== 再增加新订单 ======
    print(f"\n📋 第二步：增加新订单")
    print(f"   新需求：{new_q:.2f}kg, {new_v:.2f}m³")
    print(f"   时间窗：{tw_start_new:.1f}h - {tw_end_new:.1f}h")
    
    # 贪婪插入新订单
    best_idx = None
    best_pos = None
    best_add = float('inf')
    temp_tw = tw_dict.copy()
    temp_tw[modify_cid] = (tw_start_new, tw_end_new)
    
    for v_idx2, vr2 in enumerate(vehicle_routes):
        if not vr2['route']:
            continue
        if vr2['group'] != group:
            continue
        if vr2['total_q'] + new_q > vr2['vehicle']['Q']:
            continue
        if vr2['total_v'] + new_v > vr2['vehicle']['V']:
            continue
        if modify_cid in [int(x) for x in vr2['route']]:
            continue
        
        route = [int(x) for x in vr2['route']]
        for pos in range(len(route) + 1):
            trial_route = route[:pos] + [modify_cid] + route[pos:]
            node_ids = []
            for cid in trial_route:
                matched = nodes_df[nodes_df['real_cid'] == cid]
                if not matched.empty:
                    node_ids.extend(matched['node_id'].tolist())
                else:
                    node_ids.append(f"new_{cid}")
            
            if not node_ids:
                continue
            
            temp_nodes = nodes_df.copy()
            new_node = pd.DataFrame([{
                'node_id': f"new_{modify_cid}",
                'real_cid': modify_cid,
                'group': group,
                'x': 0, 'y': 0,
                'q': new_q, 'v': new_v,
                'is_split': False
            }])
            temp_nodes = pd.concat([temp_nodes, new_node], ignore_index=True)
            
            try:
                dm = pd.read_excel(dist_file, sheet_name=f'区域{group}').set_index('Unnamed: 0')
            except:
                continue
            
            best_start, cost = optimize_start_time(node_ids, temp_nodes, group, dm, temp_tw, vr2['vehicle'])
            
            if cost:
                add = cost['total'] - float(vr2['cost'])
                if add < best_add:
                    best_add = add
                    best_idx = v_idx2
                    best_pos = pos
    
    if best_idx is not None:
        vr2 = vehicle_routes[best_idx]
        old_route2 = [int(x) for x in vr2['route']]
        vr2['route'] = old_route2[:best_pos] + [modify_cid] + old_route2[best_pos:]
        vr2['total_q'] += new_q
        vr2['total_v'] += new_v
        vr2['cost'] += best_add
        
        print(f"✅ 插入到车辆{best_idx+1}（{vr2['vehicle']['name']}）")
        print(f"   新路径：{vr2['route']}")
        print(f"   成本增加：{best_add:.2f}元")
    else:
        print(f"⚠️ 无法插入，新增车辆")
        new_veh = select_vehicle_simple(new_q, new_v)
        if new_veh:
            vehicle_routes.append({
                'vehicle': new_veh,
                'route': [modify_cid],
                'total_q': new_q,
                'total_v': new_v,
                'group': group,
                'cost': new_veh['fixed_cost'] + new_q * 0.6
            })
            print(f"   新增车型：{new_veh['name']}")
    
    # ====== 汇总结果 ======
    new_total_cost = sum(vr['cost'] for vr in vehicle_routes)
    
    print(f"\n{'='*60}")
    print(f"📊 修改订单汇总")
    print(f"{'='*60}")
    print(f"   客户：{modify_cid}")
    print(f"   旧需求：{modify_q_old:.2f}kg → 新需求：{new_q:.2f}kg")
    print(f"   原总成本：{original_total_cost:.2f}元")
    print(f"   现总成本：{new_total_cost:.2f}元")
    print(f"   成本变化：{new_total_cost - original_total_cost:.2f}元")
    print(f"   车辆数：{len(vehicle_routes)}辆")
    print(f"\n{'='*60}")
    print(f"✅ 演示完成")



# ====================== 主函数 ======================
def main():
    print("\n" + "=" * 60)
    print("🚀 绿色物流配送优化系统（问题3：动态事件演示）")
    print("=" * 60 + "\n")

    df_coords, dist_file, df_tw, df_order = load_all_data()
    split_df = do_split_orders(df_order, MAX_Q, MAX_V)
    dc_x, dc_y, nodes_df = build_nodes(df_coords, split_df)

    routes_df = generate_initial_routes(nodes_df, dist_file, df_tw)
    if routes_df is None or routes_df.empty:
        print("❌ 路径生成失败")
        return

    final_result, used_vehicles = calculate_final_cost(routes_df, nodes_df, dist_file, df_tw)
    if final_result.empty:
        print("❌ 成本计算失败")
        return

    print("=" * 60)
    print("📊 静态方案统计")
    print("=" * 60)
    total = final_result['总成本'].sum()
    print(f"\n💰 总成本：{total:,.2f} 元")
    print(f"   固定成本：{final_result['固定成本'].sum():,.2f}（{final_result['固定成本'].sum()/total*100:.1f}%）")
    print(f"   能耗成本：{final_result['能耗成本'].sum():,.2f}（{final_result['能耗成本'].sum()/total*100:.1f}%）")
    print(f"   碳成本：{final_result['碳成本'].sum():,.2f}（{final_result['碳成本'].sum()/total*100:.1f}%）")
    print(f"   早到惩罚：{final_result['早到惩罚'].sum():,.2f}（{final_result['早到惩罚'].sum()/total*100:.1f}%）")
    print(f"   迟到惩罚：{final_result['迟到惩罚'].sum():,.2f}（{final_result['迟到惩罚'].sum()/total*100:.1f}%）")
    print(f"\n📊 路径数：{len(final_result)}条")
    print(f"🚗 车辆使用：")
    for v in VEHICLE_TYPES:
        n = used_vehicles.get(v['name'], 0)
        if n > 0:
            print(f"   {v['name']}：{n}/{v['count']}辆")

    
    # 演示2：取消订单
    modify_order_demo(final_result, nodes_df, dist_file, df_tw)

    print("\n✅ 全部运行完成！")

if __name__ == "__main__":
    random.seed(40)
    np.random.seed(40)
    main()