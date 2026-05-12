# 🚚 智能物流动态调度系统

基于 PyQt6 + SQLite + 节约算法（Clarke-Wright Savings Algorithm）的智能物流动态配送调度平台。

本系统实现：

- 用户登录/注册
- SQLite数据库管理
- 用户权限控制
- 动态物流配送调度
- 实时车辆动画
- 动态订单插入
- 路径可视化
- 日志系统
- 企业级 PyQt UI

---

# 📦 项目结构

```text
logistics_system/
│
├── launch.py
├── requirements.txt
├── README.md
│
├── database/
│   ├── db_manager.py
│   ├── init_db.py
│   └── logistics.db
│
├── ui/
│   ├── login_window.py
│   ├── register_window.py
│   ├── admin_window.py
│   ├── main_window.py
│   └── styles.py
│
├── core/
│   ├── models.py
│   ├── routing.py
│   ├── scheduler.py
│   ├── animation.py
│   └── permissions.py
│
├── logs/
│   └── system.log
│
├── assets/
│   ├── icons/
│   └── backgrounds/
│
└── data/
    └── demo_orders.csv
```

---

# ✨ 功能特性

## 1. 用户系统

- 用户注册
- 用户登录
- SQLite 数据库存储
- 权限验证
- 管理员系统

---

## 2. 动态物流调度

- Clarke-Wright 节约算法
- 动态订单插入
- 地址变更
- 订单取消
- 车辆容量约束

---

## 3. 可视化系统

- PyQt6 图形界面
- PyQtGraph 高性能动画
- 实时车辆移动
- 动态路径刷新
- 深色科技风 UI

---

## 4. 日志系统

系统自动记录：

- 用户登录
- 用户注册
- 调度操作
- 订单变化
- 管理员操作

---

# 🧠 核心算法

系统采用：

## Clarke-Wright Savings Algorithm

节约值计算：

```math
S(i,j)=d(0,i)+d(0,j)-d(i,j)
```

其中：

- \(d(0,i)\)：配送中心到客户 i 的距离
- \(d(i,j)\)：客户之间距离

目标：

- 最小化车辆数量
- 最小化总运输距离
- 最小化配送成本

---

# 🖥️ 系统界面

## 登录界面

支持：

- 登录
- 注册
- 权限验证

---

## 调度主界面

包含：

- 实时路径动画
- 车辆调度表格
- 总成本统计
- 动态订单模拟

---

# ⚙️ 安装依赖

## 1. 创建虚拟环境（推荐）

```bash
conda create -n logistics python=3.11
conda activate logistics
```

---

## 2. 安装依赖

```bash
pip install -r requirements.txt
```

---

# ▶️ 启动项目

运行：

```bash
python launch.py
```

程序流程：

```text
启动系统
   ↓
登录界面
   ↓
权限验证
   ↓
进入物流调度系统
```

---

# 🗄️ SQLite 数据库

数据库文件：

```text
database/logistics.db
```

---

## 用户表

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 日志表

```sql
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    action TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

# 🔐 权限系统

| 角色 | 权限 |
|---|---|
| admin | 系统管理 |
| dispatcher | 调度操作 |
| driver | 查看路线 |
| guest | 只读 |

---

# 📊 技术栈

| 技术 | 作用 |
|---|---|
| PyQt6 | GUI框架 |
| PyQtGraph | 高性能动态图 |
| SQLite | 数据存储 |
| Python | 核心开发语言 |
| Clarke-Wright | 路径优化算法 |

---

# 🚀 后续升级方向

## 地图系统

可接入：

- OpenStreetMap
- 百度地图
- 高德地图

---

## 高级优化算法

支持升级：

- 遗传算法（GA）
- 蚁群算法（ACO）
- 粒子群算法（PSO）
- 强化学习调度

---

## 企业级功能

可扩展：

- Kafka 实时订单流
- WebSocket
- REST API
- Docker 部署
- 多用户协同调度

---

# 📜 License

MIT License

---

# 👨‍💻 作者

智能物流动态调度系统开发项目

基于：

- PyQt6
- SQLite
- 节约算法
- 动态车辆路径优化（DVRP）
