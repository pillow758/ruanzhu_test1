import random
import sys
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QMessageBox, QFrame,
    QStackedWidget, QComboBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QSize, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QBrush, QColor, QPen, QLinearGradient, QFont, QIcon

from database.db_manager import verify_user, register_user, verify_driver, verify_driver_by_phone


# ====================== 动态流光背景 ======================
class FlowBackground(QWidget):
    """动态渐变背景"""
    def __init__(self, parent=None, theme="admin"):
        super().__init__(parent)
        self.theme = theme  # "admin" or "driver"
        self.offset = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gradient)
        self.timer.start(50)

    def update_gradient(self):
        self.offset = (self.offset + 2) % 100
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self.theme == "admin":
            # 管理员：蓝色科技风
            gradient = QLinearGradient(0, 0, self.width(), self.height())
            pos1 = (self.offset / 100.0)
            pos2 = (self.offset + 30) / 100.0
            pos3 = (self.offset + 70) / 100.0
            gradient.setColorAt(0, QColor(15, 23, 42))
            gradient.setColorAt(pos1, QColor(30, 27, 75))
            gradient.setColorAt(pos2, QColor(46, 16, 101))
            gradient.setColorAt(pos3, QColor(2, 6, 23))
            gradient.setColorAt(1, QColor(15, 23, 42))
            painter.fillRect(self.rect(), gradient)
            # 科技感线条
            painter.setPen(QPen(QColor(96, 165, 250, 60), 2))
            for i in range(0, self.width(), 60):
                painter.drawLine(i, 0, i + self.offset, self.height())
        else:
            # 驾驶员：橙色温暖风
            gradient = QLinearGradient(0, 0, self.width(), self.height())
            pos1 = (self.offset / 100.0)
            pos2 = (self.offset + 30) / 100.0
            pos3 = (self.offset + 70) / 100.0
            gradient.setColorAt(0, QColor(45, 25, 10))
            gradient.setColorAt(pos1, QColor(80, 40, 20))
            gradient.setColorAt(pos2, QColor(60, 30, 15))
            gradient.setColorAt(pos3, QColor(30, 15, 5))
            gradient.setColorAt(1, QColor(45, 25, 10))
            painter.fillRect(self.rect(), gradient)
            # 公路感线条
            painter.setPen(QPen(QColor(255, 165, 0, 50), 2))
            for i in range(0, self.width(), 80):
                painter.drawLine(i, 0, i + self.offset * 0.5, self.height())


# ====================== 粒子动画组件 ======================
class ParticleWidget(QWidget):
    """粒子动画层"""
    def __init__(self, parent=None, theme="admin"):
        super().__init__(parent)
        self.theme = theme
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.particles = []
        self.particle_count = 60
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_particles)
        self.timer.start(40)
        self.init_particles()

    def init_particles(self):
        width = self.width() if self.width() > 0 else 800
        height = self.height() if self.height() > 0 else 600

        if self.theme == "admin":
            colors = ['#60a5fa', '#a78bfa', '#f472b6', '#2dd4bf']
        else:
            colors = ['#f59e0b', '#ef4444', '#fb923c', '#fbbf24']

        for _ in range(self.particle_count):
            self.particles.append({
                'x': random.randint(0, width),
                'y': random.randint(0, height),
                'vx': random.uniform(-0.8, 0.8),
                'vy': random.uniform(-0.6, 0.6),
                'size': random.randint(2, 5),
                'alpha': random.randint(50, 150),
                'color': random.choice(colors)
            })

    def update_particles(self):
        if not self.isVisible():
            return
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            if p['x'] < 0:
                p['x'] = 0
                p['vx'] = abs(p['vx'])
            if p['x'] > width:
                p['x'] = width
                p['vx'] = -abs(p['vx'])
            if p['y'] < 0:
                p['y'] = 0
                p['vy'] = abs(p['vy'])
            if p['y'] > height:
                p['y'] = height
                p['vy'] = -abs(p['vy'])
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for p in self.particles:
            color = QColor(p['color'])
            color.setAlpha(p['alpha'])
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(p['x'] - p['size']/2), int(p['y'] - p['size']/2), p['size'], p['size'])


# ====================== 管理员登录面板 ======================
class AdminLoginPanel(QWidget):
    """管理员/调度员登录面板"""
    login_success = pyqtSignal(str, str)  # username, role

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        layout.setContentsMargins(60, 60, 60, 60)

        # 标题
        self.title_label = QLabel("🏢 管理员登录")
        self.title_label.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
            color: #60a5fa;
        """)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("物流调度控制中心")
        self.subtitle_label.setStyleSheet("""
            font-size: 14px;
            color: #94a3b8;
        """)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle_label)

        layout.addSpacing(30)

        # 用户名输入
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("📱 用户名 / 手机号")
        self.username_edit.setMinimumHeight(50)
        self.username_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(30, 41, 59, 0.85);
                border: 1px solid #3b82f6;
                border-radius: 16px;
                padding: 12px 16px;
                font-size: 14px;
                color: #f1f5f9;
            }
            QLineEdit:focus {
                border: 2px solid #60a5fa;
            }
        """)
        layout.addWidget(self.username_edit)

        # 密码输入
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("🔒 密码")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setMinimumHeight(50)
        self.password_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(30, 41, 59, 0.85);
                border: 1px solid #3b82f6;
                border-radius: 16px;
                padding: 12px 16px;
                font-size: 14px;
                color: #f1f5f9;
            }
            QLineEdit:focus {
                border: 2px solid #60a5fa;
            }
        """)
        layout.addWidget(self.password_edit)

        layout.addSpacing(20)

        # 按钮组
        btn_layout = QHBoxLayout()

        self.login_btn = QPushButton("🔐 登录系统")
        self.login_btn.setMinimumHeight(50)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #3b82f6);
                border: none;
                border-radius: 16px;
                padding: 14px;
                font-size: 15px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #60a5fa);
            }
            QPushButton:pressed {
                background: #1e40af;
            }
        """)
        self.login_btn.clicked.connect(self.do_login)
        btn_layout.addWidget(self.login_btn)

        self.register_btn = QPushButton("✨ 注册")
        self.register_btn.setMinimumHeight(50)
        self.register_btn.setStyleSheet("""
            QPushButton {
                background: rgba(30, 41, 59, 0.8);
                border: 1px solid #3b82f6;
                border-radius: 16px;
                padding: 14px;
                font-size: 15px;
                color: #60a5fa;
            }
            QPushButton:hover {
                background: rgba(59, 130, 246, 0.3);
            }
        """)
        self.register_btn.clicked.connect(self.do_register)
        btn_layout.addWidget(self.register_btn)

        layout.addLayout(btn_layout)

        # 装饰线
        line = QLabel("━━━━━━  Admin Portal  ━━━━━━")
        line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        line.setStyleSheet("color: #475569; font-size: 11px; margin-top: 20px;")
        layout.addWidget(line)

        self.setLayout(layout)

    def do_login(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")
            return

        success, role = verify_user(username, password)
        if success:
            QMessageBox.information(self, "成功", f"欢迎回来，{username}！\n权限：{role}")
            self.login_success.emit(username, role)
        else:
            QMessageBox.warning(self, "失败", "用户名或密码错误")

    def do_register(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "提示", "请输入用户名和密码进行注册")
            return

        success, msg = register_user(username, password)
        if success:
            QMessageBox.information(self, "成功", msg)
        else:
            QMessageBox.warning(self, "失败", msg)


# ====================== 驾驶员登录面板 ======================
class DriverLoginPanel(QWidget):
    """驾驶员登录面板 - 支持工号/手机号两种登录方式"""
    login_success = pyqtSignal(dict)  # driver_info

    def __init__(self, parent=None):
        super().__init__(parent)
        self.login_mode = "driver_id"  # "driver_id" or "phone"
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(18)
        layout.setContentsMargins(60, 60, 60, 60)

        # 标题
        self.title_label = QLabel("🚛 驾驶员登录")
        self.title_label.setStyleSheet("""
            font-size: 28px;
            font-weight: bold;
            color: #f59e0b;
        """)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("安全驾驶 使命必达")
        self.subtitle_label.setStyleSheet("""
            font-size: 14px;
            color: #d97706;
        """)
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.subtitle_label)

        layout.addSpacing(20)

        # 登录方式切换按钮
        mode_layout = QHBoxLayout()
        mode_layout.addStretch()

        self.mode_id_btn = QPushButton("🆔 工号登录")
        self.mode_id_btn.setCheckable(True)
        self.mode_id_btn.setChecked(True)
        self.mode_id_btn.setFixedSize(110, 34)
        self.mode_id_btn.clicked.connect(lambda: self._switch_mode("driver_id"))
        self._update_mode_btn(self.mode_id_btn, True)
        mode_layout.addWidget(self.mode_id_btn)

        self.mode_phone_btn = QPushButton("📱 手机号登录")
        self.mode_phone_btn.setCheckable(True)
        self.mode_phone_btn.setChecked(False)
        self.mode_phone_btn.setFixedSize(120, 34)
        self.mode_phone_btn.clicked.connect(lambda: self._switch_mode("phone"))
        self._update_mode_btn(self.mode_phone_btn, False)
        mode_layout.addWidget(self.mode_phone_btn)

        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # 账号输入（工号/手机号共用）
        self.driver_id_edit = QLineEdit()
        self.driver_id_edit.setPlaceholderText("🆔 驾驶员编号（如：D001）")
        self.driver_id_edit.setMinimumHeight(50)
        self.driver_id_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(50, 30, 15, 0.85);
                border: 1px solid #f59e0b;
                border-radius: 16px;
                padding: 12px 16px;
                font-size: 14px;
                color: #fef3c7;
            }
            QLineEdit:focus {
                border: 2px solid #fbbf24;
            }
        """)
        layout.addWidget(self.driver_id_edit)

        # 密码输入
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("🔒 密码")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setMinimumHeight(50)
        self.password_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(50, 30, 15, 0.85);
                border: 1px solid #f59e0b;
                border-radius: 16px;
                padding: 12px 16px;
                font-size: 14px;
                color: #fef3c7;
            }
            QLineEdit:focus {
                border: 2px solid #fbbf24;
            }
        """)
        layout.addWidget(self.password_edit)

        # 班次选择
        shift_layout = QHBoxLayout()
        shift_label = QLabel("🕐 班次：")
        shift_label.setStyleSheet("color: #fbbf24; font-size: 14px;")
        shift_layout.addWidget(shift_label)

        self.shift_combo = QComboBox()
        self.shift_combo.addItems(["早班 (6:00-14:00)", "中班 (14:00-22:00)", "晚班 (22:00-6:00)"])
        self.shift_combo.setMinimumHeight(45)
        self.shift_combo.setStyleSheet("""
            QComboBox {
                background: rgba(50, 30, 15, 0.85);
                border: 1px solid #f59e0b;
                border-radius: 12px;
                padding: 10px;
                font-size: 14px;
                color: #fef3c7;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox QAbstractItemView {
                background: #3d2415;
                border: 1px solid #f59e0b;
                color: #fef3c7;
                selection-background-color: #f59e0b;
            }
        """)
        shift_layout.addWidget(self.shift_combo)
        layout.addLayout(shift_layout)

        # 车牌号（可选）
        self.plate_edit = QLineEdit()
        self.plate_edit.setPlaceholderText("🚐 车牌号（可选，如：京A12345）")
        self.plate_edit.setMinimumHeight(50)
        self.plate_edit.setStyleSheet("""
            QLineEdit {
                background: rgba(50, 30, 15, 0.85);
                border: 1px solid #92400e;
                border-radius: 16px;
                padding: 12px 16px;
                font-size: 14px;
                color: #fef3c7;
            }
            QLineEdit:focus {
                border: 2px solid #fbbf24;
            }
        """)
        layout.addWidget(self.plate_edit)

        layout.addSpacing(15)

        # 登录按钮
        self.login_btn = QPushButton("🚀 开始配送")
        self.login_btn.setMinimumHeight(55)
        self.login_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #f59e0b);
                border: none;
                border-radius: 18px;
                padding: 16px;
                font-size: 16px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #fbbf24);
            }
            QPushButton:pressed {
                background: #92400e;
            }
        """)
        self.login_btn.clicked.connect(self.do_login)
        layout.addWidget(self.login_btn)

        # 装饰线
        line = QLabel("━━━━━━  Driver Portal  ━━━━━━")
        line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        line.setStyleSheet("color: #92400e; font-size: 11px; margin-top: 15px;")
        layout.addWidget(line)

        self.setLayout(layout)

    def _switch_mode(self, mode):
        """切换登录方式"""
        self.login_mode = mode
        self._update_mode_btn(self.mode_id_btn, mode == "driver_id")
        self._update_mode_btn(self.mode_phone_btn, mode == "phone")

        if mode == "driver_id":
            self.driver_id_edit.setPlaceholderText("🆔 驾驶员编号（如：D001）")
        else:
            self.driver_id_edit.setPlaceholderText("📱 手机号码（11位，如：13800138000）")
        self.driver_id_edit.clear()
        self.password_edit.clear()

    def _update_mode_btn(self, btn, active):
        """更新登录方式按钮样式"""
        if active:
            btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #f59e0b);
                    border: none; border-radius: 10px;
                    font-size: 12px; font-weight: bold; color: white;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 1px solid #92400e;
                    border-radius: 10px;
                    font-size: 12px; color: #fbbf24;
                }
                QPushButton:hover {
                    background: rgba(245, 158, 11, 0.2);
                }
            """)

    def do_login(self):
        account = self.driver_id_edit.text().strip()
        password = self.password_edit.text().strip()

        if not account or not password:
            QMessageBox.warning(self, "提示", "请输入账号和密码")
            return

        if self.login_mode == "phone":
            # 手机号登录
            if len(account) != 11 or not account.isdigit():
                QMessageBox.warning(self, "格式错误", "手机号应为11位数字")
                return
            success, driver_info = verify_driver_by_phone(account, password)
            err_msg = "手机号或密码错误，请重试"
        else:
            # 工号登录（自动兼容手机号输入）
            success, driver_info = verify_driver(account, password)
            err_msg = "工号或密码错误，请重试"

        if success:
            # 添加班次和车牌信息
            shift_text = self.shift_combo.currentText()
            plate = self.plate_edit.text().strip()
            driver_info['shift'] = shift_text
            if plate:
                driver_info['license_plate'] = plate

            QMessageBox.information(self, "登录成功",
                f"欢迎，{driver_info['name']}师傅！\n"
                f"车牌：{driver_info.get('license_plate', '未绑定')}\n"
                f"班次：{shift_text}\n\n"
                f"请注意行车安全！")
            self.login_success.emit(driver_info)
        else:
            QMessageBox.warning(self, "登录失败", err_msg)


# ====================== 主登录窗口 ======================
class LoginWindow(QWidget):
    """主登录窗口 - 双入口设计"""
    admin_login_success = pyqtSignal(str, str)  # username, role
    driver_login_success = pyqtSignal(dict)  # driver_info

    def __init__(self):
        super().__init__()
        self.setWindowTitle("物流调度系统 - 登录")
        self.resize(500, 650)
        self.setMinimumSize(450, 600)

        # 当前主题
        self.current_theme = "admin"

        # 背景层
        self.bg_widget = FlowBackground(self, self.current_theme)

        # 粒子层
        self.particle_widget = ParticleWidget(self, self.current_theme)

        # 主面板（磨砂玻璃效果）
        self.panel = QFrame(self)
        self.panel.setObjectName("mainPanel")
        self.update_panel_style()

        # 顶部切换栏
        self.setup_switcher()

        # 堆叠面板（管理员/驾驶员）
        self.stack = QStackedWidget()

        # 管理员面板
        self.admin_panel = AdminLoginPanel()
        self.admin_panel.login_success.connect(self.on_admin_login)
        self.stack.addWidget(self.admin_panel)

        # 驾驶员面板
        self.driver_panel = DriverLoginPanel()
        self.driver_panel.login_success.connect(self.on_driver_login)
        self.stack.addWidget(self.driver_panel)

        # 布局
        main_layout = QVBoxLayout(self.panel)
        main_layout.setContentsMargins(0, 70, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.stack)

        # 默认显示管理员登录
        self.stack.setCurrentIndex(0)

    def setup_switcher(self):
        """设置顶部切换栏"""
        switcher = QFrame(self.panel)
        switcher.setGeometry(0, 0, self.width(), 70)
        switcher.setStyleSheet("""
            QFrame {
                background: rgba(0, 0, 0, 0.3);
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }
        """)

        layout = QHBoxLayout(switcher)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(10)

        # 管理员按钮
        self.admin_btn = QPushButton("🏢 管理员")
        self.admin_btn.setCheckable(True)
        self.admin_btn.setChecked(True)
        self.admin_btn.setMinimumHeight(45)
        self.admin_btn.clicked.connect(lambda: self.switch_tab(0))
        self.update_button_style(self.admin_btn, True, "admin")

        # 驾驶员按钮
        self.driver_btn = QPushButton("🚛 驾驶员")
        self.driver_btn.setCheckable(True)
        self.driver_btn.setChecked(False)
        self.driver_btn.setMinimumHeight(45)
        self.driver_btn.clicked.connect(lambda: self.switch_tab(1))
        self.update_button_style(self.driver_btn, False, "driver")

        layout.addWidget(self.admin_btn)
        layout.addWidget(self.driver_btn)

    def update_button_style(self, btn, active, theme):
        """更新按钮样式"""
        if theme == "admin":
            if active:
                btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #3b82f6);
                        border: none;
                        border-radius: 12px;
                        font-size: 14px;
                        font-weight: bold;
                        color: white;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        border: 1px solid #3b82f6;
                        border-radius: 12px;
                        font-size: 14px;
                        color: #60a5fa;
                    }
                    QPushButton:hover {
                        background: rgba(59, 130, 246, 0.2);
                    }
                """)
        else:  # driver
            if active:
                btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #f59e0b);
                        border: none;
                        border-radius: 12px;
                        font-size: 14px;
                        font-weight: bold;
                        color: white;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        border: 1px solid #f59e0b;
                        border-radius: 12px;
                        font-size: 14px;
                        color: #fbbf24;
                    }
                    QPushButton:hover {
                        background: rgba(245, 158, 11, 0.2);
                    }
                """)

    def switch_tab(self, index):
        """切换登录标签"""
        self.stack.setCurrentIndex(index)

        if index == 0:
            self.current_theme = "admin"
            self.admin_btn.setChecked(True)
            self.driver_btn.setChecked(False)
            self.update_button_style(self.admin_btn, True, "admin")
            self.update_button_style(self.driver_btn, False, "driver")
        else:
            self.current_theme = "driver"
            self.admin_btn.setChecked(False)
            self.driver_btn.setChecked(True)
            self.update_button_style(self.admin_btn, False, "admin")
            self.update_button_style(self.driver_btn, True, "driver")

        # 更新背景和粒子主题
        self.bg_widget.theme = self.current_theme
        self.particle_widget.theme = self.current_theme
        self.particle_widget.init_particles()
        self.update_panel_style()

    def update_panel_style(self):
        """根据主题更新面板样式"""
        if self.current_theme == "admin":
            self.panel.setStyleSheet("""
                QFrame#mainPanel {
                    background: rgba(15, 25, 45, 0.75);
                    border-radius: 24px;
                    border: 1px solid rgba(96, 165, 250, 0.3);
                }
            """)
        else:
            self.panel.setStyleSheet("""
                QFrame#mainPanel {
                    background: rgba(45, 25, 15, 0.75);
                    border-radius: 24px;
                    border: 1px solid rgba(245, 158, 11, 0.3);
                }
            """)

    def on_admin_login(self, username, role):
        """管理员登录成功回调"""
        self.close()
        self.admin_login_success.emit(username, role)

    def on_driver_login(self, driver_info):
        """驾驶员登录成功回调"""
        self.close()
        self.driver_login_success.emit(driver_info)

    def resizeEvent(self, event):
        """自适应布局"""
        new_size = event.size()
        margin = 20
        panel_width = new_size.width() - margin * 2
        panel_height = new_size.height() - margin * 2

        self.bg_widget.setGeometry(QRect(0, 0, new_size.width(), new_size.height()))
        self.particle_widget.setGeometry(QRect(0, 0, new_size.width(), new_size.height()))
        self.panel.setGeometry(margin, margin, panel_width, panel_height)

        # 更新switcher宽度
        switcher = self.panel.findChild(QFrame)
        if switcher:
            switcher.setGeometry(0, 0, panel_width, 70)

        super().resizeEvent(event)

    def closeEvent(self, event):
        if hasattr(self, 'bg_widget') and self.bg_widget.timer:
            self.bg_widget.timer.stop()
        if hasattr(self, 'particle_widget') and self.particle_widget.timer:
            self.particle_widget.timer.stop()
        event.accept()


# ====================== 测试入口 ======================
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())
