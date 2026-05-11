import json
import os
import random
import sys
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QHBoxLayout, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QSize, QRect
from PyQt6.QtGui import QPainter, QBrush, QColor, QPen, QLinearGradient, QPainterPath, QFont
from PyQt6.QtMultimedia import QMediaPlayer, QMediaFormat
from PyQt6.QtMultimediaWidgets import QVideoWidget

USER_FILE = 'users.json'

# ====================== 用户数据初始化 ======================
def init_user_file():
    if not os.path.exists(USER_FILE):
        with open(USER_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)

def load_users():
    with open(USER_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(users):
    with open(USER_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

# ====================== 粒子动画组件 ======================
class ParticleWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # 让鼠标穿透
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)    # 透明背景
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
        init_user_file()
        self.success_callback = success_callback
        self.setWindowTitle("物流配送系统 - 霓虹极客版")
        self.resize(480, 600)
        self.setMinimumSize(400, 500)

        # 1. 视频背景层 (底层)
        self.video_widget = QVideoWidget(self)
        self.media_player = QMediaPlayer()
        self.media_player.setVideoOutput(self.video_widget)
        # 尝试加载背景视频，请确保目录下存在 "background.mp4" 文件，若无则显示渐变占位
        video_path = "background.mp4"
        if os.path.exists(video_path):
            self.media_player.setSource(QUrl.fromLocalFile(os.path.abspath(video_path)))
            self.media_player.setLoops(QMediaPlayer.Infinite)
            self.media_player.play()
        else:
            # 降级：显示动态霓虹渐变 (依然科技感)
            self.video_widget.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0f172a, stop:0.5 #1e1b4b, stop:1 #020617);")
            # 增加动态流光效果模拟视频
            self.gradient_timer = QTimer()
            self.gradient_timer.timeout.connect(self.update_gradient_effect)
            self.gradient_timer.start(80)
            self.gradient_offset = 0

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
                box-shadow: 0 0 20px rgba(96, 165, 250, 0.3);
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
                box-shadow: 0 0 12px #3b82f6;
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
                box-shadow: 0 0 16px #3b82f6;
            }
            QPushButton:pressed {
                background: #1e40af;
            }
            QLabel {
                color: #e2e8f0;
            }
        """)

        self.apply_neon_effects()     # 增加额外发光标签效果

    def update_gradient_effect(self):
        """视频缺失时，动态改变渐变偏移，产生流光动画"""
        self.gradient_offset = (self.gradient_offset + 5) % 100
        grad_style = f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #0f172a, stop:{self.gradient_offset/100} #1e1b4b,
            stop:0.6 #2e1065, stop:1 #020617);
        """
        self.video_widget.setStyleSheet(grad_style)

    def apply_neon_effects(self):
        # 创建标题霓虹文本效果
        self.title_label.setStyleSheet("""
            font-size: 30px;
            font-weight: bold;
            color: #60a5fa;
            background: transparent;
            qproperty-alignment: AlignCenter;
            text-shadow: 0 0 12px #3b82f6, 0 0 5px #1e3a8a;
        """)
        self.subtitle_label.setStyleSheet("""
            font-size: 15px;
            color: #b9e0ff;
            background: transparent;
            qproperty-alignment: AlignCenter;
            text-shadow: 0 0 5px #3b82f6;
        """)

    def init_panel_ui(self):
        # 面板内部布局
        panel_layout = QVBoxLayout()
        panel_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.setSpacing(20)
        panel_layout.setContentsMargins(40, 40, 40, 40)

        # 标题 + 副标题
        self.title_label = QLabel("🚚 物流星轨 · 智控系统")
        self.subtitle_label = QLabel("超维度调度平台 | 霓虹科技引擎")
        panel_layout.addWidget(self.title_label)
        panel_layout.addWidget(self.subtitle_label)
        panel_layout.addSpacing(20)

        # 输入框
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("⚡ 用户名 / 手机号")
        self.username_edit.setMinimumHeight(48)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("🔒 密码")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setMinimumHeight(48)

        panel_layout.addWidget(self.username_edit)
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
        """自适应布局：视频背景、粒子层、面板大小随窗口改变"""
        new_size = event.size()
        # 视频背景完全填充窗口
        self.video_widget.setGeometry(QRect(0, 0, new_size.width(), new_size.height()))
        # 粒子层完全填充窗口
        self.particle_widget.setGeometry(QRect(0, 0, new_size.width(), new_size.height()))
        # 控制面板居中，占据80%宽度，高度自适应但不超过窗口90%
        panel_width = int(new_size.width() * 0.78)
        panel_height = min(int(new_size.height() * 0.72), self.panel.sizeHint().height() + 80)
        panel_x = (new_size.width() - panel_width) // 2
        panel_y = (new_size.height() - panel_height) // 2
        self.panel.setGeometry(panel_x, panel_y, panel_width, panel_height)
        super().resizeEvent(event)

    def login(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        users = load_users()
        if username in users and users[username] == password:
            QMessageBox.information(self, "授权成功", "身份验证通过，正在进入智控中心...")
            self.close()
            self.success_callback()
        else:
            QMessageBox.warning(self, "接入失败", "用户名或密码错误，请重新输入")

    def register(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        if not username or not password:
            QMessageBox.warning(self, "错误", "用户名和密码不能为空！")
            return
        users = load_users()
        if username in users:
            QMessageBox.warning(self, "错误", "用户名已存在！")
            return
        users[username] = password
        save_users(users)
        QMessageBox.information(self, "成功", "注册成功，请登录！")

    def closeEvent(self, event):
        # 清理资源：停止媒体播放和粒子定时器
        self.media_player.stop()
        if hasattr(self, 'gradient_timer'):
            self.gradient_timer.stop()
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