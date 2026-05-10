import pandas as pd
import numpy as np

def entropy_weight_method(file_path):
    # 1. 读取归一化矩阵（已按0-1标准化的4列指标）
    df = pd.read_excel(file_path)
    print("=== 输入数据概览 ===")
    print(df.head())
    print(f"订单数：{len(df)}，指标数：{len(df.columns)}")

    # 2. 计算指标比重 P_pq = z_pq / Σ z_pq
    # 按列求和，然后每行除以该列和
    col_sum = df.sum(axis=0)
    p = df / col_sum
    # 防止除零或P=0的情况（公式规定P_pq=0时该项为0）
    p = p.fillna(0)

    # 3. 计算信息熵 e_q = -1/ln(n) * Σ(P_pq * ln(P_pq))
    n = len(df)
    ln_p = np.log(p)
    ln_p[p == 0] = 0  # 规定P=0时该项为0
    e = -1 / np.log(n) * (p * ln_p).sum(axis=0)

    # 4. 计算差异系数 g_q = 1 - e_q
    g = 1 - e

    # 5. 计算权重 γ_q = g_q / Σ g_q
    gamma = g / g.sum()

    # 整理结果为DataFrame
    result = pd.DataFrame({
        "指标名称": df.columns,
        "信息熵e_q": e.values,
        "差异系数g_q": g.values,
        "权重γ_q": gamma.values
    })

    print("\n=== 熵权法计算结果 ===")
    print(result.round(4))
    print(f"\n权重和：{gamma.sum():.4f}")

    return result

if __name__ == "__main__":
    # 调用你上一步生成的归一化矩阵文件
    file_path = "输出/四指标归一化矩阵.xlsx"
    weight_result = entropy_weight_method(file_path)

    # 保存结果到Excel
    weight_result.to_excel("输出/熵权法权重结果.xlsx", index=False)
    print("\n✅ 权重结果已保存到：输出/熵权法权重结果.xlsx")