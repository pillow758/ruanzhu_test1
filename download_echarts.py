"""
下载 ECharts 到本地 - 只需运行一次
"""
import urllib.request
import os

LIB_DIR = os.path.join(os.path.dirname(__file__), "lib")
os.makedirs(LIB_DIR, exist_ok=True)

ECHARTS_URL = "https://cdnjs.cloudflare.com/ajax/libs/echarts/5.5.0/echarts.min.js"
ECHARTS_LOCAL = os.path.join(LIB_DIR, "echarts.min.js")

if os.path.exists(ECHARTS_LOCAL):
    print(f"ECharts 已存在: {ECHARTS_LOCAL}")
else:
    print("正在下载 ECharts...")
    try:
        urllib.request.urlretrieve(ECHARTS_URL, ECHARTS_LOCAL)
        print(f"下载完成: {ECHARTS_LOCAL}")
    except Exception as e:
        print(f"下载失败: {e}")
        print("请手动下载 echarts.min.js 放到 lib 目录下")
        print(f"下载地址: {ECHARTS_URL}")
