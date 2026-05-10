import pandas as pd

#读取文件
file_path = r'D:\数学建模\A题：城市绿色物流配送调度\附件\订单信息.xlsx'
df = pd.read_excel(file_path)
#删除存在空白数据的行
df = df.dropna()
#保存处理后的订单文件
output_path = r'D:\数学建模\A题：城市绿色物流配送调度\附件\订单信息_处理后.xlsx'
df.to_excel(output_path, index=False)
#提取数据
customer_summary = df.groupby('目标客户编号').agg(
    总重量=('重量', 'sum'),
    总体积=('体积', 'sum')
).reset_index()
#创建完整的 1–98 客户编号列表
full_customers = pd.DataFrame({'目标客户编号': range(1, 99)})
#汇总数据
final_summary = pd.merge(full_customers, customer_summary, on='目标客户编号', how='left').fillna(0)
#保存汇总表
summary_path = r'D:\数学建模\A题：城市绿色物流配送调度\附件\客户重量体积汇总表.xlsx'
final_summary.to_excel(summary_path, index=False)
#输出
print(f"结果保存到：{output_path}")
print(f"汇总表保存到：{summary_path}")