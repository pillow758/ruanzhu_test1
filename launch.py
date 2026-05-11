import sys
from PyQt6.QtWidgets import QApplication

# 导入登录窗口
from login_window import LoginWindow

# 导入物流主界面
from main import LogisticsApp


# ====================== 启动物流系统 ======================
def start_main_window():
    global main_window

    main_window = LogisticsApp()
    main_window.show()


# ====================== 主程序 ======================
if __name__ == '__main__':

    app = QApplication(sys.argv)

    app.setStyle('Fusion')

    # 创建登录窗口
    login = LoginWindow(start_main_window)

    login.show()

    sys.exit(app.exec())