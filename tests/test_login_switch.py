"""真实绘图回调、反复切换、工号/手机号登录以及工作台启动失败回归。"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu')
from PyQt6.QtCore import QCoreApplication, QEvent, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget
from PyQt6.QtWebEngineWidgets import QWebEngineView
from database import db_manager, init_db
from login_window import LoginWindow
import launch


class LoginSwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['login-tests'])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        path = str(Path(self.directory.name)/'test.db')
        self.errors = []
        self.windows = []
        self.patches = [patch.object(db_manager,'DB_PATH',path), patch.object(init_db,'DB_PATH',path),
                        patch.object(launch,'login_window',None), patch.object(launch,'main_window',None),
                        patch.object(QWebEngineView,'setHtml',lambda *args:None),
                        patch.object(QMessageBox,'information',return_value=QMessageBox.StandardButton.Ok),
                        patch.object(sys,'excepthook',lambda kind,error,tb:self.errors.append((kind,error)))]
        for item in self.patches:
            item.start()
        init_db.init_database()

    def tearDown(self):
        for window in self.windows:
            window.close()
            window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.app.processEvents()
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    def login_window(self):
        login = LoginWindow()
        self.windows.append(login)
        login.show()
        self.app.processEvents()
        return login

    def test_repeated_tab_switching_paints_without_exceptions_or_particle_growth(self):
        login = self.login_window()
        for i in range(50):
            button = login.driver_btn if i%2==0 else login.admin_btn
            QTest.mouseClick(button,Qt.MouseButton.LeftButton)
            login.bg_widget.offset = 98
            login.bg_widget.repaint()
            login.particle_widget.repaint()
            self.app.processEvents()
            self.assertEqual(len(login.particle_widget.particles),60)
        QTest.qWait(120)
        self.assertEqual(self.errors,[])

    def test_animation_timers_stop_when_login_is_hidden_and_resume_when_shown(self):
        login = self.login_window()
        self.assertTrue(login.bg_widget.timer.isActive())
        self.assertTrue(login.particle_widget.timer.isActive())
        login.hide()
        self.assertFalse(login.bg_widget.timer.isActive())
        self.assertFalse(login.particle_widget.timer.isActive())
        login.show()
        self.assertTrue(login.bg_widget.timer.isActive())
        login.close()
        self.assertFalse(login.bg_widget.timer.isActive())

    def test_real_driver_login_by_id_and_phone_shows_workstation_before_closing_login(self):
        for mode, account in [('driver_id','D001'),('phone','13800138000')]:
            with self.subTest(mode=mode):
                login = self.login_window()
                launch.login_window = login
                login.driver_login_success.connect(launch.start_driver_window)
                login.switch_tab(1)
                login.driver_panel._switch_mode(mode)
                login.driver_panel.driver_id_edit.setText(account)
                login.driver_panel.password_edit.setText('123456')
                QTest.mouseClick(login.driver_panel.login_btn,Qt.MouseButton.LeftButton)
                self.app.processEvents()
                self.assertIsNotNone(launch.main_window)
                driver = launch.main_window
                self.windows.append(driver)
                self.assertTrue(driver.isVisible())
                self.assertFalse(login.isVisible())
                self.assertEqual(driver.driver_id,'D001')
                self.assertFalse(login.bg_widget.timer.isActive())
                driver.close()
        self.assertEqual(self.errors,[])

    def test_failed_workstation_start_keeps_login_visible(self):
        login = self.login_window()
        launch.login_window = login
        login.driver_login_success.connect(launch.start_driver_window)
        with patch.object(launch,'DriverWorkstation',side_effect=RuntimeError('fixture startup error')), \
             patch.object(QMessageBox,'critical') as error_dialog, patch.object(launch.logging,'getLogger'):
            login.on_driver_login({'driver_id':'D001','name':'测试司机'})
        self.assertTrue(login.isVisible())
        self.assertIsNone(launch.main_window)
        error_dialog.assert_called_once()
        self.assertEqual(self.errors,[])

    def test_admin_login_handoff_still_opens_new_window(self):
        login = self.login_window()
        launch.login_window = login
        login.admin_login_success.connect(launch.start_admin_window)
        with patch.object(launch,'LogisticsApp',side_effect=lambda **kwargs:QWidget()):
            login.on_admin_login('admin','admin')
        self.windows.append(launch.main_window)
        self.assertTrue(launch.main_window.isVisible())
        self.assertFalse(login.isVisible())


if __name__ == '__main__':
    unittest.main()
