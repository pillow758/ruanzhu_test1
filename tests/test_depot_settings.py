"""配送中心的精度确认、异步结果隔离、持久化与调度原点同步。"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS','--disable-gpu')
from PyQt6.QtCore import QCoreApplication,QEvent,QSignalBlocker,QTimer
from PyQt6.QtWidgets import QApplication,QMessageBox
from PyQt6.QtWebEngineWidgets import QWebEngineView
from database import db_manager,init_db
from depot_settings import compose_address,get_depot,get_effective_depot,save_depot
from depot_dialog import DepotSettingsDialog
from driver_workstation import NavigationMap,DriverWorkstation
from gps_store import accept_position,get_position,issue_token
import main
import realtime_monitor
import echarts_window


class DepotSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication(['depot-tests'])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db_path=str(Path(self.temp.name)/'test.db')
        self.patches=[patch.object(db_manager,'DB_PATH',self.db_path),patch.object(init_db,'DB_PATH',self.db_path),
                      patch.object(main,'DB_PATH',self.db_path),patch.object(echarts_window,'DB_PATH',self.db_path),
                      patch.object(QWebEngineView,'setHtml',lambda *args:None),
                      patch.object(main,'_load_distance_matrix',lambda:{}),patch.object(main,'_build_distance_matrix',lambda:None),
                      patch.object(echarts_window,'load_html_in_webview',lambda *args:None),
                      patch.object(QTimer,'singleShot',lambda *args:None),
                      patch.object(QMessageBox,'information',return_value=QMessageBox.StandardButton.Ok)]
        for item in self.patches:item.start()
        init_db.init_database()
        self.windows=[]

    def tearDown(self):
        for window in self.windows:
            window.close()
            window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.app.processEvents()
        for item in reversed(self.patches):item.stop()
        self.temp.cleanup()

    def record(self,**values):
        record=dict(name='南京配送站',province='江苏省',city='南京市',district='玄武区',street='梅园新村街道',
                    detail='四牌楼2号',address='江苏省南京市玄武区梅园新村街道四牌楼2号',
                    lng=118.793545,lat=32.055049,source='geocode',level='门址')
        record.update(values)
        return record

    def dialog(self):
        dialog=DepotSettingsDialog()
        self.windows.append(dialog)
        for key,combo in (('province',dialog.province),('city',dialog.city),('district',dialog.district)):
            with QSignalBlocker(combo):combo.setEditText(self.record()[key])
        dialog.street.setText(self.record()['street'])
        dialog.detail.setText(self.record()['detail'])
        dialog.name.setText(self.record()['name'])
        dialog._ready=True
        return dialog

    def test_saved_center_survives_restart_and_schema_upgrade(self):
        self.assertIsNone(get_depot())
        saved=save_depot(self.record())
        init_db.init_database()
        self.assertEqual(get_depot(),saved)
        self.assertEqual(get_effective_depot()['lng'],118.793545)

    def test_coarse_or_invalid_coordinates_cannot_be_saved_as_precise(self):
        for overrides in ({'level':'街道'},{'level':'市'},{'lng':float('nan')},{'lat':91},{'province':''}):
            with self.subTest(overrides=overrides),self.assertRaises(ValueError):
                save_depot(self.record(**overrides))
        self.assertIsNone(get_depot())

    def test_municipality_address_does_not_repeat_city(self):
        self.assertEqual(compose_address('北京市','北京市','朝阳区','望京街道','阜通东大街6号'),
                         '北京市朝阳区望京街道阜通东大街6号')
        self.assertEqual(compose_address('重庆市','重庆城区','渝中区','解放碑街道'),
                         '重庆市渝中区解放碑街道')

    def test_coarse_match_needs_manual_map_point_and_explicit_confirmation(self):
        dialog=self.dialog()
        dialog._geocodes_received(json.dumps(dict(version=dialog._version,items=[self.record(level='街道')],error='')))
        dialog.confirm.setChecked(True)
        self.assertFalse(dialog.save_button.isEnabled())
        dialog._point_picked(118.79356,32.05508)
        self.assertFalse(dialog.save_button.isEnabled())
        dialog.confirm.setChecked(True)
        self.assertTrue(dialog.save_button.isEnabled())
        dialog._save()
        self.assertEqual(get_depot()['source'],'map')
        self.assertEqual(get_depot()['lng'],118.79356)

    def test_changed_address_discards_confirmation_and_late_geocode(self):
        dialog=self.dialog()
        version=dialog._version
        dialog._geocodes_received(json.dumps(dict(version=version,items=[self.record()],error='')))
        dialog.confirm.setChecked(True)
        self.assertTrue(dialog.save_button.isEnabled())
        dialog.detail.setText('四牌楼3号')
        dialog._geocodes_received(json.dumps(dict(version=version,items=[self.record()],error='')))
        self.assertIsNone(dialog.candidate)
        self.assertFalse(dialog.save_button.isEnabled())

    def test_multiple_results_can_be_selected_and_saved(self):
        dialog=self.dialog()
        second=self.record(lng=118.7936,address='江苏省南京市玄武区梅园新村街道四牌楼2号入口')
        dialog._geocodes_received(json.dumps(dict(version=dialog._version,items=[self.record(),second],error='')))
        dialog.results.setCurrentIndex(1)
        dialog.confirm.setChecked(True)
        dialog._save()
        self.assertEqual(get_depot()['lng'],118.7936)

    def test_street_dropdown_population_preserves_confirmed_location(self):
        dialog=self.dialog()
        dialog._geocodes_received(json.dumps(dict(version=dialog._version,items=[self.record()],error='')))
        dialog.confirm.setChecked(True)
        candidate=dict(dialog.candidate)
        dialog._load_region('street','320102')
        dialog._regions_received(json.dumps(dict(request_id=dialog._region_seq,items=[dict(name='梅园新村街道',code='320102',level='street')])) )
        self.assertGreaterEqual(dialog.street_combo.findText('梅园新村街道'),0)
        self.assertEqual(dialog.candidate,candidate)
        self.assertTrue(dialog.save_button.isEnabled())

    def test_cancel_does_not_overwrite_saved_depot(self):
        original=save_depot(self.record())
        dialog=self.dialog()
        dialog.detail.setText('另一个地址')
        dialog.reject()
        self.assertEqual(get_depot(),original)

    def test_municipality_dropdown_uses_virtual_city_code_for_districts(self):
        dialog=self.dialog()
        with QSignalBlocker(dialog.province):dialog.province.setEditText('北京市')
        with QSignalBlocker(dialog.city):dialog.city.setEditText('北京市')
        dialog._load_region('city','110000')
        dialog._regions_received(json.dumps(dict(request_id=dialog._region_seq,items=[dict(name='北京城区',code='110100',level='city')])))
        self.assertEqual(dialog.city.currentText(),'北京市')
        self.assertEqual(dialog.city.currentData(),'110100')
        dialog._regions_received(json.dumps(dict(request_id=dialog._region_seq,items=[dict(name='朝阳区',code='110105',level='district')])))
        self.assertGreaterEqual(dialog.district.findText('朝阳区'),0)

    def test_changing_depot_updates_all_views_and_preserves_customer_and_vehicle_positions(self):
        admin=main.LogisticsApp()
        driver=DriverWorkstation(db_manager.get_driver_info('D001'))
        self.windows.extend([admin,driver])
        import time
        accept_position(issue_token('D001'),dict(driver_id='D001',lng=118.8,lat=32.06,
                        accuracy=12,timestamp=time.time(),coord_system='gcj02',source='phone'))
        driver._tick_gps()
        vehicle=get_position('D001')
        customers={key:(node.lng,node.lat) for key,node in main.node_dict.items() if key!='DC'}
        saved=save_depot(self.record())
        admin._apply_depot_settings(saved)
        driver._tick_gps()
        self.assertEqual(main.node_dict['DC'].lng,saved['lng'])
        self.assertEqual(realtime_monitor._get_dc(),(saved['lng'],saved['lat']))
        self.assertEqual(NavigationMap._get_dc()[:2],(saved['lng'],saved['lat']))
        self.assertEqual(get_position('D001'),vehicle)
        self.assertEqual(customers,{key:(node.lng,node.lat) for key,node in main.node_dict.items() if key!='DC'})
        self.assertTrue(all(route.nodes[0]=='DC' and route.nodes[-1]=='DC' for route in main.active_routes))
        admin.reset_system_silent()
        self.assertEqual(main.node_dict['DC'].lng,saved['lng'])

    def test_reinitialization_generates_example_customers_near_saved_depot(self):
        save_depot(self.record())
        admin=main.LogisticsApp()
        self.windows.append(admin)
        self.assertEqual(main.node_dict['DC'].lng,118.793545)
        self.assertLess(abs(main.node_dict['A'].lng-118.793545),.2)
        self.assertIn('演示',main.node_dict['A'].address)

    def test_old_distance_cache_does_not_match_new_depot(self):
        main.node_dict.clear()
        main.node_dict.update(DC=main.Node('DC',118.79,32.05,0),A=main.Node('A',118.80,32.06,10))
        old={(116.397,39.908):{(118.8,32.06):1000},(118.8,32.06):{(116.397,39.908):1000}}
        self.assertFalse(main._matrix_matches_nodes(old))


if __name__=='__main__':unittest.main()
