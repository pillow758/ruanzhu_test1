"""设备接入窗口和可选的 Cloudflare 临时 HTTPS 隧道。"""
import hashlib
import html
import io
import json
import os
import platform
import re
import shutil
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QScrollArea, QWidget,
)

from database.db_manager import get_all_drivers
from gps_receiver import LocationReceiver
from gps_store import issue_token


class GpsAccessService:
    def __init__(self):
        self.receiver = None
        self.process = None
        self.public_url = ""
        self.status = "接收服务尚未启动"
        self.busy = False
        self._cancel = threading.Event()
        self._worker = None

    def ensure_receiver(self):
        if self.receiver is None:
            self.receiver = LocationReceiver()
        return self.receiver.url

    def _executable(self):
        installed = shutil.which("cloudflared")
        if installed:
            return installed
        if os.name != "nt":
            raise RuntimeError("请先安装 cloudflared 并加入 PATH")
        asset_name = "cloudflared-windows-arm64.exe" if platform.machine().lower() == "arm64" else "cloudflared-windows-amd64.exe"
        directory = Path(__file__).with_name(".runtime")
        executable = directory / "cloudflared.exe"
        if executable.exists():
            return str(executable)
        self.status = "首次接入：正在从 Cloudflare 官方 GitHub 下载隧道工具…"
        request = urllib.request.Request("https://api.github.com/repos/cloudflare/cloudflared/releases/latest",
                                         headers={"User-Agent": "Logistics-GPS", "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                release = json.load(response)
            asset = next((a for a in release["assets"] if a["name"] == asset_name), None)
            if not asset or not asset.get("digest", "").startswith("sha256:"):
                raise ValueError("发布元数据缺少 SHA256")
            download_url, expected_hash = asset["browser_download_url"], asset["digest"][7:]
        except (OSError, ValueError):
            # 共享网络的 GitHub API 可能达到匿名额度，官方发布页也提供文件哈希。
            with urllib.request.urlopen("https://github.com/cloudflare/cloudflared/releases/latest", timeout=30) as response:
                release_url = response.url
                release_html = response.read(4*1024*1024).decode("utf-8")
            clean = html.unescape(re.sub(r"<[^>]+>", " ", release_html))
            match = re.search(re.escape(asset_name) + r":\s*([a-f0-9]{64})", clean)
            if not match or "/releases/tag/" not in release_url:
                raise RuntimeError("无法获取官方 SHA256；请手动安装 cloudflared")
            expected_hash = match.group(1)
            download_url = release_url.replace("/releases/tag/", "/releases/download/") + "/" + asset_name
        directory.mkdir(exist_ok=True)
        temporary = directory / "cloudflared.download"
        digest = hashlib.sha256()
        try:
            with urllib.request.urlopen(download_url, timeout=30) as response, temporary.open("wb") as output:
                size = 0
                while True:
                    if self._cancel.is_set():
                        raise RuntimeError("已取消接入")
                    block = response.read(1024*1024)
                    if not block:
                        break
                    size += len(block)
                    if size > 200*1024*1024:
                        raise RuntimeError("隧道工具下载大小异常")
                    digest.update(block)
                    output.write(block)
            if digest.hexdigest() != expected_hash:
                raise RuntimeError("隧道工具 SHA256 校验失败")
            temporary.replace(executable)
        finally:
            temporary.unlink(missing_ok=True)
        return str(executable)

    def start_tunnel(self):
        if self.busy or (self.process and self.process.poll() is None):
            return
        self.ensure_receiver()
        self._cancel.clear()
        self.busy = True
        self.public_url = ""
        self.status = "正在启动异地 HTTPS 接入…"
        self._worker = threading.Thread(target=self._run_tunnel, daemon=True)
        self._worker.start()

    def _run_tunnel(self):
        deadline_timer = None
        process = None
        try:
            executable = self._executable()
            if self._cancel.is_set():
                return
            process = subprocess.Popen(
                [executable, "tunnel", "--no-autoupdate", "--protocol", "http2", "--url", self.receiver.url],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            self.process = process
            if self._cancel.is_set():
                process.terminate()
                return
            candidate = ""
            connected = False
            deadline_timer = threading.Timer(90, self._startup_timeout)
            deadline_timer.daemon = True
            deadline_timer.start()
            for line in process.stdout:
                match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
                if match:
                    candidate = match.group(0)
                if "Registered tunnel connection" in line:
                    connected = True
                if candidate and connected and self.busy:
                    self.public_url = candidate
                    self.status = "异地 HTTPS 接入已启动；请选择司机并生成专属链接"
                    self.busy = False
                    deadline_timer.cancel()
                if self._cancel.is_set():
                    break
            process.wait(timeout=5)
            self.public_url = ""
            if not self._cancel.is_set() and "超时" not in self.status:
                self.status = "HTTPS 隧道已断开，请检查网络后重新启动"
        except Exception as exc:
            self.public_url = ""
            self.status = f"接入失败：{exc}"
        finally:
            if deadline_timer:
                deadline_timer.cancel()
            if process:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                if process.stdout:
                    process.stdout.close()
            self.busy = False

    def _startup_timeout(self):
        if self.busy:
            self.status = "HTTPS 接入超时，请检查是否能访问 Cloudflare 网络后重试"
            if self.process and self.process.poll() is None:
                self.process.terminate()

    def stop(self):
        self._cancel.set()
        if self.process and self.process.poll() is None:
            self.process.terminate()
        if self._worker:
            self._worker.join(timeout=3)
        self.public_url = ""
        if self.receiver:
            self.receiver.stop()
            self.receiver = None
        self.status = "接入服务已停止"


gps_service = GpsAccessService()


class GpsAccessDialog(QDialog):
    def __init__(self, parent=None, driver_id=None):
        super().__init__(parent)
        self.setWindowTitle("真实 GPS · 司机设备接入")
        self.setObjectName("gpsAccessDialog")
        self.setFont(QFont("Microsoft YaHei", 10))
        # 顶层对话框使用自己的背景，避免系统深色调色板与主窗口深色文字混用。
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#f5f7fb"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#172033"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#172033"))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#64748b"))
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        self.setStyleSheet("""
            QDialog#gpsAccessDialog { background: #f5f7fb; }
            QWidget { color: #172033; font-family: 'Microsoft YaHei'; font-size: 14px; }
            QLabel { background: transparent; border: none; padding: 0; }
            QLabel#stepTitle { color: #172033; font-size: 16px; font-weight: bold; }
            QLabel#connectionState {
                background: #eaf2ff; color: #17428a; border: 1px solid #c5d8f5;
                border-radius: 8px; padding: 10px 12px;
            }
            QLabel#qrArea {
                background: #ffffff; color: #475569; border: 1px solid #cbd5e1;
                border-radius: 10px; padding: 14px;
            }
            QLabel#helperText { color: #475569; font-size: 13px; }
            QLineEdit, QComboBox {
                background: #ffffff; color: #172033; border: 1px solid #a8b7cb;
                border-radius: 7px; padding: 8px 10px; min-height: 22px;
                selection-background-color: #2563eb; selection-color: #ffffff;
            }
            QLineEdit:focus, QComboBox:focus { border: 2px solid #2563eb; }
            QLineEdit:read-only { background: #eef2f7; color: #334155; }
            QComboBox QAbstractItemView {
                background: #ffffff; color: #172033; border: 1px solid #a8b7cb;
                selection-background-color: #2563eb; selection-color: #ffffff;
                outline: none; padding: 4px;
            }
            QPushButton {
                background: #2563eb; color: #ffffff; border: 1px solid #2563eb;
                border-radius: 7px; padding: 9px 14px; min-height: 22px; font-weight: bold;
            }
            QPushButton:hover { background: #1d4ed8; border-color: #1d4ed8; }
            QPushButton:pressed { background: #1e40af; }
            QPushButton:disabled { background: #e2e8f0; color: #475569; border-color: #cbd5e1; }
            QPushButton#copyLink { background: #ffffff; color: #1d4ed8; border-color: #93b4eb; }
            QPushButton#copyLink:hover { background: #eaf2ff; }
            QPushButton#copyLink:disabled { background: #e2e8f0; color: #475569; border-color: #cbd5e1; }
            QScrollArea, QWidget#gpsContent { background: #f5f7fb; border: none; }
            QScrollBar:vertical { background: #e8edf5; width: 10px; border-radius: 5px; }
            QScrollBar::handle:vertical { background: #94a3b8; min-height: 28px; border-radius: 5px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        screen = self.screen()
        available = screen.availableGeometry()
        self.resize(min(700, available.width() - 60), min(780, available.height() - 80))
        self.link_base = ""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(8, 8, 8, 8)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("gpsContent")
        scroll.setWidget(content)
        outer_layout.addWidget(scroll)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)
        title = QLabel("1. 启动异地接入")
        title.setObjectName("stepTitle")
        layout.addWidget(title)
        hint = QLabel("手机定位来自司机手机。启动临时 HTTPS 接入后，司机可在异地上报位置。\n"
                      "电脑和程序需持续运行；重启接入后，需要重新生成链接。")
        hint.setObjectName("helperText")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.state = QLabel()
        self.state.setObjectName("connectionState")
        self.state.setWordWrap(True)
        layout.addWidget(self.state)
        self.tunnel_btn = QPushButton("启动异地接入（临时 HTTPS）")
        self.tunnel_btn.clicked.connect(self._start)
        layout.addWidget(self.tunnel_btn)
        address_hint = QLabel("接入地址（系统自动填写；已有固定 HTTPS 地址时可替换）：")
        address_hint.setWordWrap(True)
        layout.addWidget(address_hint)
        self.base = QLineEdit()
        self.base.setPlaceholderText("https://gps.example.com")
        layout.addWidget(self.base)
        self.local = QLabel()
        self.local.setObjectName("helperText")
        self.local.setWordWrap(True)
        self.local.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.local)
        driver_title = QLabel("2. 选择司机并生成链接")
        driver_title.setObjectName("stepTitle")
        layout.addWidget(driver_title)
        self.drivers = QComboBox()
        for driver in get_all_drivers():
            if driver_id is None or driver["driver_id"] == driver_id:
                self.drivers.addItem(f"{driver['driver_id']} · {driver['name']} · {driver['license_plate']}", driver["driver_id"])
        self.drivers.currentIndexChanged.connect(self._clear_link)
        layout.addWidget(self.drivers)
        generate = QPushButton("生成 / 重置司机接入链接")
        generate.setToolTip("重置后，该司机的旧设备凭证将失效。")
        generate.clicked.connect(self._generate)
        layout.addWidget(generate)
        self.link = QLineEdit()
        self.link.setReadOnly(True)
        self.link.setPlaceholderText("生成链接后，将在这里显示司机专属地址")
        layout.addWidget(self.link)
        copy = QPushButton("复制司机专属链接")
        copy.setObjectName("copyLink")
        copy.setEnabled(False)
        self.copy_btn = copy
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.link.text()))
        layout.addWidget(copy)
        self.qr = QLabel("生成链接后，用司机手机扫码或打开链接")
        self.qr.setObjectName("qrArea")
        self.qr.setWordWrap(True)
        self.qr.setMinimumHeight(280)
        self.qr.setMaximumHeight(310)
        self.qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.qr, 1)
        note = QLabel("3. 司机用手机扫码，允许定位并点击“开始上报”。\n"
                      "手机页面需保持在前台。重置链接后，旧设备凭证将失效。\n"
                      "车载设备接入和长期使用步骤，请查看 GPS接入说明.md。")
        note.setObjectName("helperText")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._refresh)
        self.poll_timer.start(1000)
        self._refresh()

    def _clear_link(self):
        self.link.clear()
        self.copy_btn.setEnabled(False)
        self.link_base = ""
        self.qr.clear()
        self.qr.setText("请生成所选司机的专属链接")

    def _start(self):
        try:
            gps_service.start_tunnel()
        except Exception as exc:
            QMessageBox.warning(self, "启动失败", str(exc))
        self._refresh()

    def _refresh(self):
        self.state.setText(gps_service.status)
        running = bool(gps_service.process and gps_service.process.poll() is None)
        self.tunnel_btn.setEnabled(not gps_service.busy and not running)
        if gps_service.public_url:
            if not self.base.text() or ".trycloudflare.com" in self.base.text():
                self.base.setText(gps_service.public_url)
        elif ".trycloudflare.com" in self.base.text():
            self.base.clear()
            self._clear_link()
        if gps_service.receiver:
            self.local.setText("本机接收端：" + gps_service.receiver.url)

    def _generate(self):
        from urllib.parse import urlsplit
        base = self.base.text().strip().rstrip("/")
        parsed = urlsplit(base)
        if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
            QMessageBox.warning(self, "接入地址", "请先启动异地接入，或填写仅包含域名和可选端口的 HTTPS 地址。")
            return
        driver_id = self.drivers.currentData()
        if not driver_id:
            return
        try:
            gps_service.ensure_receiver()
            token = issue_token(driver_id)
            link = base + "/mobile#" + urlencode({"driver_id": driver_id, "token": token})
            self.link.setText(link)
            self.copy_btn.setEnabled(True)
            self.link_base = base
            try:
                import qrcode
                buffer = io.BytesIO()
                qrcode.make(link).save(buffer, format="PNG")
                pixmap = QPixmap()
                pixmap.loadFromData(buffer.getvalue())
                self.qr.setPixmap(pixmap.scaled(260, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation))
            except ImportError:
                self.qr.setText("二维码依赖未安装；可复制链接在手机打开（pip install qrcode[pil]）。")
            self._refresh()
        except Exception as exc:
            QMessageBox.warning(self, "生成失败", str(exc))
