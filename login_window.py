import json
import os
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QPushButton,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
)
from PyQt6.QtCore import Qt

USER_FILE = 'users.json'

# ====================== 用户数据初始化 ======================
def init_user_file():
    if not os.path.exists(USER_FILE):
        with open(USER_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)

# ====================== 读取用户 ======================
def load_users():
    with open(USER_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# ====================== 保存用户 ======================
def save_users(users):
    with open(USER_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

# ====================== 登录窗口 ======================
class LoginWindow(QWidget):

    def __init__(self, success_callback):
        super().__init__()

        init_user_file()

        self.success_callback = success_callback

        self.setWindowTitle('物流配送系统 - 登录')
        self.resize(420, 520)

        self.setStyleSheet(
            '''
            QWidget {
                background:#0f172a;
                color:white;
                font-family:微软雅黑;
            }
            QLineEdit {
                background:#1e293b;
                border:2px solid #334155;
                border-radius:10px;
                padding:12px;
                font-size:15px;
                color:white;
            }
            QPushButton {
                background:#3b82f6;
                border:none;
                border-radius:10px;
                padding:12px;
                color:white;
                font-size:16px;
                font-weight:bold;
            }
            QPushButton:hover {
                background:#2563eb;
            }
            '''
        )

        self.init_ui()

# ====================== UI ======================
    def init_ui(self):

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(18)

        title = QLabel('🚚 智能物流配送系统')
        title.setStyleSheet(
            '''
            font-size:28px;
            font-weight:bold;
            color:#60a5fa;
            '''
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel('物流动态调度平台')
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet('font-size:16px;color:#cbd5e1;')

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText('请输入用户名')

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText('请输入密码')
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        login_btn = QPushButton('登录系统')
        login_btn.clicked.connect(self.login)

        register_btn = QPushButton('注册账号')
        register_btn.clicked.connect(self.register)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(login_btn)
        btn_layout.addWidget(register_btn)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(25)
        layout.addWidget(self.username_edit)
        layout.addWidget(self.password_edit)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
# ====================== 登录 ======================
    def login(self):

        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()

        users = load_users()

        if username in users and users[username] == password:
            QMessageBox.information(self, '成功', '登录成功！')

            self.close()

            self.success_callback()

        else:
            QMessageBox.warning(self, '失败', '用户名或密码错误！')

    # ====================== 注册 ======================
    def register(self):

        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()

        if not username or not password:
            QMessageBox.warning(self, '错误', '用户名和密码不能为空！')
            return

        users = load_users()

        if username in users:
            QMessageBox.warning(self, '错误', '用户名已存在！')
            return

        users[username] = password

        save_users(users)

        QMessageBox.information(self, '成功', '注册成功，请登录！')
