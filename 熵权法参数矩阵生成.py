import pandas as pd
import numpy as np
import os

# ================== 工具函数 ==================
def time_to_hour(time_str):
    h, m = map(int, time_str.split(":"))
    return h + m / 60

def distance(x, y, cx=20, cy=20):
    return np.sqrt((x - cx)**2 + (y - cy)**2)

def norm_pos(data):
    # 正向指标归一化（时间、重量、体积）
    dmin = data.min()
    dmax = data.max()
    return (data - dmin) / (dmax - dmin) if dmax != dmin else np.ones_like(data)

def norm_neg(data):
    # 负向指标归一化（距离）
    dmin = data.min()
    dmax = data.max()
    return (dmax - data) / (dmax - dmin) if dmax != dmin else np.ones_like(data)

# ================== 主程序 ==================
def main():
    # 读取三个文件
    df_order = pd.read_excel("订单信息_按客户排序.xlsx")
    df_coord = pd.read_excel("客户坐标信息.xlsx")
    df_tw    = pd.read_excel("时间窗.xlsx")

    # 统一客户编号
    df_order["客户编号"] = df_order["目标客户编号"].astype(int)
    df_coord["客户编号"] = df_coord["ID"].astype(int)
    df_tw["客户编号"]    = df_tw["客户编号"].astype(int)

    # 1. 计算客户到配送中心(20,20)距离
    cus = df_coord[df_coord["类型"] == "客户"].copy()
    cus["距离"] = cus.apply(lambda r: distance(r["X (km)"], r["Y (km)"]), axis=1)

    # 2. 计算时间窗宽度
    df_tw["时间宽度"] = df_tw["结束时间"].apply(time_to_hour) - df_tw["开始时间"].apply(time_to_hour)

    # 3. 合并到订单表（保持订单行数）
    df = df_order.merge(cus[["客户编号", "距离"]], on="客户编号", how="left")
    df = df.merge(df_tw[["客户编号", "时间宽度"]], on="客户编号", how="left")

    # 填充缺失
    df = df.fillna(0)

    # ================== 全部指标归一化 ==================
    df["标准化时间宽度"] = norm_pos(df["时间宽度"])
    df["标准化重量"]      = norm_pos(df["重量"])
    df["标准化体积"]      = norm_pos(df["体积"])
    df["标准化距离"]      = norm_neg(df["距离"])

    # ================== 最终输出：4列 ==================
    out = df[[
        "标准化时间宽度",
        "标准化重量",
        "标准化体积",
        "标准化距离"
    ]].copy()

    # 保存
    os.makedirs("输出", exist_ok=True)
    out.to_excel("输出/四指标归一化矩阵.xlsx", index=False)

    print("✅ 全部完成！")
    print(f"订单总行数：{len(out)}")
    print("输出 4 列（全部 0~1 归一化）：")
    print("1. 标准化时间宽度")
    print("2. 标准化重量")
    print("3. 标准化体积")
    print("4. 标准化距离")

if __name__ == "__main__":
    main()