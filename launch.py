import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

# 导入登录窗口
from login_window import LoginWindow

# 导入物流调度主界面（管理员）
from main import LogisticsApp

# 导入驾驶员工作台
from driver_workstation import DriverWorkstation

# 初始化数据库
from database.init_db import init_database
from database.db_manager import FONT_FAMILY

# 全局窗口引用
main_window = None


def start_admin_window(username, role):
    """启动管理员/调度员主界面"""
    global main_window
    main_window = LogisticsApp(username=username)
    main_window.show()


def start_driver_window(driver_info):
    """启动驾驶员工作台"""
    global main_window
    main_window = DriverWorkstation(driver_info)
    main_window.show()


# ====================== 主程序 ======================
if __name__ == '__main__':
    # 初始化数据库（创建表、默认账号等）
    init_database()

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # 设置全局字体：中文宋体 / 英文 Times New Roman
    global_font = QFont("SimSun", 9)
    global_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(global_font)

    # 创建登录窗口
    login = LoginWindow()

    # 连接信号
    login.admin_login_success.connect(start_admin_window)
    login.driver_login_success.connect(start_driver_window)

    login.show()

    sys.exit(app.exec())
