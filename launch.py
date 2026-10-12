import sys
import logging
from PyQt6.QtWidgets import QApplication, QMessageBox
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
from gps_access import gps_service
from web_view import apply_light_palette

# 全局窗口引用
main_window = None
login_window = None


def _start_workstation(factory, **kwargs):
    """工作台显示成功后关闭登录页；启动失败时保留登录页。"""
    global main_window
    try:
        window = factory(**kwargs)
        window.show()
    except Exception:
        logging.getLogger(__name__).exception("工作台启动失败")
        QMessageBox.critical(login_window, "工作台启动失败", "无法打开工作台，登录窗口已保留，请重试。")
        return False
    main_window = window
    if login_window is not None:
        login_window.close()
    return True


def start_admin_window(username, role):
    """启动管理员/调度员主界面"""
    return _start_workstation(LogisticsApp, username=username)


def start_driver_window(driver_info):
    """启动驾驶员工作台"""
    return _start_workstation(DriverWorkstation, driver_info=driver_info)


# ====================== 主程序 ======================
if __name__ == '__main__':
    # 初始化数据库（创建表、默认账号等）
    init_database()

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    apply_light_palette(app)
    app.aboutToQuit.connect(gps_service.stop)

    # 设置全局字体：中文宋体 / 英文 Times New Roman
    global_font = QFont("SimSun", 9)
    global_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(global_font)

    # 创建登录窗口
    login = LoginWindow()
    login_window = login

    # 连接信号
    login.admin_login_success.connect(start_admin_window)
    login.driver_login_success.connect(start_driver_window)

    login.show()

    sys.exit(app.exec())
