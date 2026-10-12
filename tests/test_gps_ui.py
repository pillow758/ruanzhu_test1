"""离线界面回归：禁用外部地图加载，使用临时数据库。"""
import json
import os
import re
from html.parser import HTMLParser
import shutil
import subprocess
import gc
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu')
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QTimer, QCoreApplication, QEvent

from database import db_manager, init_db
from gps_store import issue_token, accept_position, get_position, get_positions
from gps_access import GpsAccessDialog, gps_service
from driver_workstation import DriverWorkstation
import main
import echarts_window


class GpsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['gps-tests'])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name)/'test.db')
        self.html = []
        def capture(view, html, *args):
            self.html.append(html)
        self.patches = [patch.object(db_manager, 'DB_PATH', self.path),
                        patch.object(init_db, 'DB_PATH', self.path),
                        patch.object(main, 'DB_PATH', self.path),
                        patch.object(echarts_window, 'DB_PATH', self.path),
                        patch.object(QWebEngineView, 'setHtml', capture),
                        patch.object(echarts_window, 'load_html_in_webview', lambda *args: None),
                        patch.object(main, '_load_distance_matrix', lambda: {}),
                        patch.object(main, '_build_distance_matrix', lambda: None),
                        patch.object(QTimer, 'singleShot', lambda *args: None),
                        patch.object(QMessageBox, 'information', return_value=QMessageBox.StandardButton.Ok)]
        for item in self.patches:
            item.start()
        init_db.init_database()
        self.windows = []

    def tearDown(self):
        for window in self.windows:
            window.close()
            window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        gc.collect()
        gps_service.stop()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def report(self):
        accept_position(issue_token('D001'), dict(driver_id='D001', lng=116.397, lat=39.908,
                        accuracy=16, timestamp=time.time()-1, source='phone', coord_system='wgs84'))

    def test_admin_and_driver_read_real_position_without_writing(self):
        admin = main.LogisticsApp()
        driver = DriverWorkstation(db_manager.get_driver_info('D001'))
        self.windows += [admin, driver]
        self.assertEqual(get_positions(), {})
        self.assertIsNone(driver.driver_lng)
        self.assertEqual(admin.realtime_widget.driver_positions, {})
        self.report()
        snapshot = get_position('D001')
        admin.realtime_widget._load_data()
        driver._tick_gps()
        admin._update_gps_label()
        self.assertEqual(driver.driver_lng, snapshot['lng'])
        self.assertEqual(admin.realtime_widget.driver_positions['D001'], snapshot)
        self.assertIn('实时 1', admin.gps_info_label.text())
        for _ in range(3):
            admin.realtime_widget._load_data()
            driver._tick_gps()
        self.assertEqual(get_position('D001'), snapshot)

    def test_navigation_does_not_move_vehicle_to_destination(self):
        self.report()
        driver = DriverWorkstation(db_manager.get_driver_info('D001'))
        self.windows.append(driver)
        task = dict(id=10, lng=117.0, lat=40.0, customer_name='客户', address='地址', order_id='T1')
        snapshot = get_position('D001')
        with patch('driver_workstation.get_driver_tasks', return_value=[task]), patch('driver_workstation.log_order_status_change'):
            driver.handle_task_action('navigate', 10)
        self.assertEqual(get_position('D001'), snapshot)
        self.assertEqual(db_manager.get_driver_info('D001')['lng'], snapshot['lng'])
        self.assertEqual(driver.nav_map.current_destination[:2], (117.0, 40.0))

    def test_missing_or_stale_location_blocks_actual_vehicle_navigation(self):
        driver = DriverWorkstation(db_manager.get_driver_info('D001'))
        self.windows.append(driver)
        task = dict(id=10, lng=117.0, lat=40.0, customer_name='客户', address='地址')
        with patch('driver_workstation.get_driver_tasks', return_value=[task]), patch.object(QMessageBox, 'warning') as warning:
            driver.handle_task_action('navigate', 10)
            warning.assert_called_once()
        self.assertIsNone(driver.nav_map.current_destination)
        accept_position(issue_token('D001'), dict(driver_id='D001', lng=116.4, lat=39.9,
                        accuracy=12, timestamp=time.time()-200, source='phone', coord_system='gcj02'))
        with patch('driver_workstation.get_driver_tasks', return_value=[task]), patch.object(QMessageBox, 'warning') as warning:
            driver.handle_task_action('navigate', 10)
            warning.assert_called_once()
        self.assertIsNone(driver.nav_map.current_destination)
        self.assertIn('超时', driver.gps_info_label.text())

    def test_access_dialog_can_generate_link_and_qr(self):
        dialog = GpsAccessDialog(driver_id='D001')
        self.windows.append(dialog)
        dialog.base.setText('https://gps.example.com')
        dialog._generate()
        self.assertIn('/mobile#driver_id=D001&token=', dialog.link.text())
        self.assertFalse(dialog.qr.pixmap().isNull())

    def test_map_and_mobile_javascript_compile(self):
        from realtime_monitor import RealtimeMonitorWidget
        monitor = RealtimeMonitorWidget()
        driver = DriverWorkstation(db_manager.get_driver_info('D001'))
        self.windows += [monitor, driver]
        driver.nav_map.show_driver_at_dc(116.4, 39.9, 116.397, 39.908, '配送中心', 16)
        driver.nav_map.navigate_to(116.5, 39.8, '客户', 116.4, 39.9)
        html = self.html + [Path('mobile_gps.html').read_text(encoding='utf-8')]
        class ScriptParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.inline = False
                self.parts = []
                self.scripts = []

            def handle_starttag(self, tag, attrs):
                if tag == 'script':
                    self.inline = 'src' not in dict(attrs)
                    self.parts = []

            def handle_data(self, data):
                if self.inline:
                    self.parts.append(data)

            def handle_endtag(self, tag):
                if tag == 'script' and self.inline:
                    self.scripts.append(''.join(self.parts))
                    self.inline = False

        parser = ScriptParser()
        for page in html:
            parser.feed(page)
        scripts = parser.scripts
        if not shutil.which('node'):
            self.skipTest('JavaScript syntax check requires Node.js')
        result = subprocess.run(['node', '-e',
            "const fs=require('fs');const scripts=JSON.parse(fs.readFileSync(0,'utf8'));scripts.forEach((s,i)=>{try{new Function(s)}catch(e){console.error('Script '+i+': '+e+'\\n'+s);process.exit(1)}});console.log('OK '+scripts.length);"],
            input=json.dumps(scripts), text=True, encoding='utf-8', capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith('OK'))


if __name__ == '__main__':
    unittest.main()
