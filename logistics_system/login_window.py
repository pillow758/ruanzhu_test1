from PyQt6.QtWidgets import QComboBox
from database.db_manager import verify_user
from database.db_manager import register_user
import random
import sys
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QMessageBox, QFrame,QComboBox
)
from PyQt6.QtCore import Qt, QTimer, QSize, QRect
from PyQt6.QtGui import QPainter, QBrush, QColor, QPen, QLinearGradient, QPainterPath, QFont
from PyQt6.QtMultimedia import QMediaPlayer, QMediaFormat
from PyQt6.QtMultimediaWidgets import QVideoWidget

# ====================== 动态流光背景 ======================
class FlowBackground(QWidget):
    """用于绘制动态渐变背景，替换视频层，避免黑屏"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.offset = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gradient)
        self.timer.start(50)  # 20fps 流光效果

    def update_gradient(self):
        self.offset = (self.offset + 2) % 100
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # 创建动态渐变
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        # 随偏移变化的颜色
        pos1 = (self.offset / 100.0)
        pos2 = (self.offset + 30) / 100.0
        pos3 = (self.offset + 70) / 100.0
        gradient.setColorAt(0, QColor(15, 23, 42))      # #0f172a
        gradient.setColorAt(pos1, QColor(30, 27, 75))   # #1e1b4b
        gradient.setColorAt(pos2, QColor(46, 16, 101))  # #2e1065
        gradient.setColorAt(pos3, QColor(2, 6, 23))     # #020617
        gradient.setColorAt(1, QColor(15, 23, 42))
        painter.fillRect(self.rect(), gradient)
        # 绘制一些光晕线条（科技感）
        painter.setPen(QPen(QColor(96, 165, 250, 80), 2))
        for i in range(0, self.width(), 60):
            painter.drawLine(i, 0, i + self.offset, self.height())
            
# ====================== 粒子动画组件 ======================
class ParticleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # 让鼠标穿透
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)    # 透明背景
        self.setAutoFillBackground(False)
        self.particles = []
        self.particle_count = 80
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_particles)
        self.timer.start(40)  # 约25fps
        self.init_particles()

    def init_particles(self):
        """生成随机粒子"""
        self.particles = []
        width = self.width() if self.width() > 0 else 800
        height = self.height() if self.height() > 0 else 600
        for _ in range(self.particle_count):
            self.particles.append({
                'x': random.randint(0, width),
                'y': random.randint(0, height),
                'vx': random.uniform(-1.2, 1.2),
                'vy': random.uniform(-0.8, 0.8),
                'size': random.randint(2, 6),
                'alpha': random.randint(60, 200),
                'color': random.choice(['#60a5fa', '#a78bfa', '#f472b6', '#2dd4bf'])
            })

    def update_particles(self):
        """更新粒子位置，边界回弹"""
        if not self.isVisible():
            return
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            # 边界回弹并略微随机变化速度
            if p['x'] < 0:
                p['x'] = 0
                p['vx'] = abs(p['vx'])
                p['vy'] += random.uniform(-0.2, 0.2)
            if p['x'] > width:
                p['x'] = width
                p['vx'] = -abs(p['vx'])
                p['vy'] += random.uniform(-0.2, 0.2)
            if p['y'] < 0:
                p['y'] = 0
                p['vy'] = abs(p['vy'])
                p['vx'] += random.uniform(-0.2, 0.2)
            if p['y'] > height:
                p['y'] = height
                p['vy'] = -abs(p['vy'])
                p['vx'] += random.uniform(-0.2, 0.2)
            # 速度限制，避免飞出过快
            p['vx'] = max(-2.5, min(2.5, p['vx']))
            p['vy'] = max(-2.0, min(2.0, p['vy']))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for p in self.particles:
            color = QColor(p['color'])
            color.setAlpha(p['alpha'])
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            # 绘制光晕效果：小圆加外发光感 (两层)
            painter.drawEllipse(int(p['x'] - p['size']/2), int(p['y'] - p['size']/2), p['size'], p['size'])
            # 增加中心亮点
            highlight = QColor(255, 255, 255, 100)
            painter.setBrush(highlight)
            painter.drawEllipse(int(p['x'] - p['size']/3), int(p['y'] - p['size']/3), p['size']//2+1, p['size']//2+1)

    def resizeEvent(self, event):
        # 窗口大小变化时重新初始化粒子位置，保证布满窗口
        self.init_particles()
        super().resizeEvent(event)

# ====================== 霓虹科技风登录窗口 ======================
class LoginWindow(QWidget):
    def __init__(self, success_callback):
        super().__init__()
        self.success_callback = success_callback
        self.setWindowTitle("物流配送系统by pillow")
        self.resize(480, 600)
        self.setMinimumSize(400, 500)

         # 1. 底层：动态流光背景
        self.bg_widget = FlowBackground(self)

        # 2. 粒子动画层 (中层，浮于视频之上)
        self.particle_widget = ParticleWidget(self)

        # 3. 控件主面板 (上层，半透明磨砂玻璃效果)
        self.panel = QFrame(self)
        self.panel.setObjectName("neonPanel")
        self.panel.setStyleSheet("""
            QFrame#neonPanel {
                background: rgba(15, 25, 45, 0.65);
                border-radius: 28px;
                border: 1px solid rgba(96, 165, 250, 0.4);
            }
        """)
        self.init_panel_ui()          # 构建登录控件

        # 设置整体样式与霓虹科技风细节
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', 'Microsoft YaHei', 'PingFang SC', 'Helvetica Neue', sans-serif;
            }
            QLineEdit {
                background: rgba(30, 41, 59, 0.85);
                border: 1px solid #3b82f6;
                border-radius: 16px;
                padding: 12px 16px;
                font-size: 14px;
                color: #f1f5f9;
                selection-background-color: #3b82f6;
            }
            QLineEdit:focus {
                border: 2px solid #60a5fa;
                background: rgba(30, 41, 59, 0.95);
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563eb, stop:1 #3b82f6);
                border: none;
                border-radius: 20px;
                padding: 12px;
                font-size: 15px;
                font-weight: bold;
                color: white;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3b82f6, stop:1 #60a5fa);
            }
            QPushButton:pressed {
                background: #1e40af;
            }
            QLabel {
                color: #e2e8f0;
            }
            QMessageBox {
                background-color: #1e293b;
            }
            QMessageBox QLabel {
                color: #f1f5f9;
            }
            QMessageBox QPushButton {
                background: #3b82f6;
                border-radius: 8px;
                padding: 8px 20px;
                min-width: 80px;
            }
        """)

        # 调整层级顺序：背景在最下，粒子中间，面板最上
        self.bg_widget.lower()
        self.particle_widget.raise_()
        self.panel.raise_()

        # 安装事件过滤器，确保窗口缩放时控件自适应
        self.resize(self.size())  # 触发一次 resizeEvent

    def apply_neon_effects(self):
        # 创建标题霓虹文本效果
        self.title_label.setStyleSheet("""
            font-size: 30px;
            font-weight: bold;
            color: #60a5fa;
            background: transparent;
            qproperty-alignment: AlignCenter;
        """)
        self.subtitle_label.setStyleSheet("""
            font-size: 15px;
            color: #b9e0ff;
            background: transparent;
            qproperty-alignment: AlignCenter;
        """)

    def init_panel_ui(self):
        # 面板内部布局
        panel_layout = QVBoxLayout()
        panel_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.setSpacing(20)
        panel_layout.setContentsMargins(60, 60, 60, 60)

        # 标题 + 副标题
        self.title_label = QLabel("🚚 物流系统")
        self.subtitle_label = QLabel("超维度调度平台 ")
        panel_layout.addWidget(self.title_label)
        panel_layout.addWidget(self.subtitle_label)
        panel_layout.addSpacing(20)

        # 输入框
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("⚡ 用户名 / 手机号")
        self.username_edit.setMinimumHeight(48)
        self.username_edit.setMaximumWidth(500)

        # ========== 角色选择下拉框 ==========
        self.role_combo = QComboBox()
        self.role_combo.addItems(["管理员", "驾驶员"])
        self.role_combo.setMinimumHeight(48)
        self.role_combo.setMaximumWidth(500)
        self.role_combo.setStyleSheet("""
            QComboBox {
                background: rgba(30, 41, 59, 0.85);
                border: 1px solid #3b82f6;
                border-radius: 16px;
                padding: 12px 16px;
                font-size: 14px;
                color: #f1f5f9;
            }
            QComboBox:focus {
                border: 2px solid #60a5fa;
                background: rgba(30, 41, 59, 0.95);
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 8px solid #60a5fa;
                width: 0;
                height: 0;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background: rgba(30, 41, 59, 0.95);
                border: 1px solid #3b82f6;
                border-radius: 8px;
                color: #f1f5f9;
                selection-background-color: #3b82f6;
                outline: none;
                margin: 0;
                padding: 0;
            }
            QComboBox QAbstractItemView::item {
                background: rgba(30, 41, 59, 0.95);
                color: #f1f5f9;
                padding: 8px 16px;
                min-height: 32px;
            }
            QComboBox QAbstractItemView::item:hover {
                background: #3b82f6;
                color: #ffffff;
            }
            QComboBox QAbstractItemView::item:selected {
                background: #3b82f6;
                color: #ffffff;
            }
        """)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("🔒 密码")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setMinimumHeight(48)
        self.password_edit.setMaximumWidth(500)

        panel_layout.addWidget(self.username_edit)
        panel_layout.addWidget(self.role_combo)
        panel_layout.addWidget(self.password_edit)
        panel_layout.addSpacing(10)

        # 按钮布局
        btn_layout = QHBoxLayout()
        self.login_btn = QPushButton("⟳ 登录系统")
        self.register_btn = QPushButton("✨ 注册账号")
        self.login_btn.clicked.connect(self.login)
        self.register_btn.clicked.connect(self.register)

        btn_layout.addWidget(self.login_btn)
        btn_layout.addWidget(self.register_btn)
        panel_layout.addLayout(btn_layout)

        # 增加科技感装饰线
        line = QLabel("━━━━━━  Neural Network  ━━━━━━")
        line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        line.setStyleSheet("color: #5b8cbf; font-size: 11px; margin-top: 15px;")
        panel_layout.addWidget(line)

        self.panel.setLayout(panel_layout)

    def resizeEvent(self, event):
        """自适应布局：背景、粒子层、面板大小随窗口改变"""
        new_size = event.size()
        # 动态流光背景完全填充窗口
        self.bg_widget.setGeometry(QRect(0, 0, new_size.width(), new_size.height()))
        # 粒子层完全填充窗口
        self.particle_widget.setGeometry(QRect(0, 0, new_size.width(), new_size.height()))
        # 控制面板铺满整个窗口
        self.panel.setGeometry(0, 0, new_size.width(), new_size.height())
        super().resizeEvent(event)

    def login(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        success, real_role = verify_user(username, password)

        if success:
            role_text = "管理员" if real_role == "admin" else "驾驶员"
            QMessageBox.information(self, "成功", f"登录成功！权限：{role_text}")
            self.close()
            self.success_callback(username, real_role)
        else:
            QMessageBox.warning(self, "失败", "用户名或密码错误")

    def register(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "错误", "用户名密码不能为空")
            return

        role_text = self.role_combo.currentText()
        role = "admin" if role_text == "管理员" else "driver"

        success, msg = register_user(username, password, role)
        if success:
            QMessageBox.information(self, "成功", msg)
        else:
            QMessageBox.warning(self, "失败", msg)

    def closeEvent(self, event):
        # 清理资源：停止定时器
        if hasattr(self, 'bg_widget') and self.bg_widget.timer:
            self.bg_widget.timer.stop()
        if hasattr(self, 'particle_widget') and self.particle_widget.timer:
            self.particle_widget.timer.stop()
        event.accept()


# ====================== 调用示例 (保留原有登录回调结构) ======================
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QUrl

    app = QApplication(sys.argv)

    def on_login_success():
        print("登录成功，跳转主界面")
        # 此处可调用真正的主窗口
        msg = QMessageBox()
        msg.setWindowTitle("Welcome")
        msg.setText("登录成功！即将进入物流调度主界面 (演示跳转)")
        msg.exec()

    window = LoginWindow(on_login_success)
    window.show()
    sys.exit(app.exec())