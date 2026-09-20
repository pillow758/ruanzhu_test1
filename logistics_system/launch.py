import sys
from PyQt6.QtWidgets import QApplication

from login_window import LoginWindow
from main import LogisticsApp
from driver_window import DriverWindow


main_window = None  # 必须加这句！


def start_main_window(username, role):
    global main_window

    print("登录成功，角色：", role)

    if role == "admin":
        main_window = LogisticsApp()
        main_window.show()
    else:
        main_window = DriverWindow(username)
        main_window.show()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    login = LoginWindow(start_main_window)
    login.show()

    sys.exit(app.exec())