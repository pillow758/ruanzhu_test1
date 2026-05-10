import pandas as pd
import math
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
import os
os.environ['OMP_NUM_THREADS'] = '1'
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False
#读取文件
file_path = r'D:\数学建模\A题：城市绿色物流配送调度\附件\客户坐标信息.xlsx'
df = pd.read_excel(file_path)
# 2. 删除空白行
df = df.dropna()
#初始化列
df['绝对距离'] = None
df['绿色区域'] = None
# 只处理客户
customer_mask = df['类型'] == '客户'
#绿色区域：距离城市中心≤10
df.loc[customer_mask, '绝对距离'] = df.loc[customer_mask].apply(
    lambda row: math.sqrt(row['X (km)']**2 + row['Y (km)']**2), axis=1
)
df.loc[customer_mask, '绿色区域'] = df.loc[customer_mask, '绝对距离'].apply(
    lambda x: '是' if x <= 10 else '否'
)
#K-Means算法分为4类、绘图
customer_df = df[customer_mask].copy()
X = customer_df[['X (km)', 'Y (km)']].values
kmeans = KMeans(n_clusters=4, random_state=42)
customer_df['第几组'] = kmeans.fit_predict(X) + 1
df = pd.merge(df, customer_df[['ID', '第几组']], on='ID', how='left')
#绘图
plt.figure(figsize=(10, 10))
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
labels = ['第1类客户', '第2类客户', '第3类客户', '第4类客户']
for i in range(4):
    mask = df['第几组'] == (i+1)
    plt.scatter(df.loc[mask, 'X (km)'], df.loc[mask, 'Y (km)'],
                c=colors[i], label=labels[i], s=60, alpha=0.8)
plt.scatter(20, 20, c='black', marker='*', s=300, label='配送中心 (20,20)', zorder=5)
plt.legend(loc='upper right', fontsize=12)
plt.xlabel('X (km)', fontsize=12)
plt.ylabel('Y (km)', fontsize=12)
plt.title('客户坐标 K-Means 4类聚类分布图', fontsize=14)
plt.grid(True, alpha=0.3)
plt.axis('equal')
plt.savefig(r'D:\数学建模\A题：城市绿色物流配送调度\附件\客户聚类散点图.png', dpi=300, bbox_inches='tight')
plt.close()
# 保存文件
output_path = r'D:\数学建模\A题：城市绿色物流配送调度\附件\客户坐标信息_处理后.xlsx'
df.to_excel(output_path, index=False)
print(f"结果保存到：{output_path}")
print("聚类散点图已保存到附件目录")