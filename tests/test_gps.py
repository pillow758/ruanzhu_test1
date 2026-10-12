"""python -m unittest discover -s tests -p test_gps.py -v（使用临时数据库）。"""
import json
import sqlite3
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from database import db_manager, init_db
from gps_receiver import LocationReceiver
from gps_store import accept_position, get_position, get_positions, is_fresh, issue_token, wgs84_to_gcj02


class GpsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / 'test.db')
        self.patches = [patch.object(db_manager, 'DB_PATH', self.db_path),
                        patch.object(init_db, 'DB_PATH', self.db_path)]
        for item in self.patches:
            item.start()
        init_db.init_database()
        self.token = issue_token('D001')
        self.receiver = LocationReceiver()

    def tearDown(self):
        self.receiver.stop()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def payload(self, **values):
        payload = dict(driver_id='D001', lng=116.397, lat=39.908, accuracy=12,
                       timestamp=time.time()-2, source='phone', coord_system='wgs84')
        payload.update(values)
        return payload

    def request(self, path='/api/location', payload=None, token=None, raw=None):
        body = raw if raw is not None else json.dumps(payload).encode()
        headers = {'Content-Type': 'application/json'}
        if token is not None:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request(self.receiver.url+path, data=body, headers=headers)
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.load(response)

    def test_report_updates_only_matching_driver(self):
        code, result = self.request(payload=self.payload(), token=self.token)
        self.assertEqual(code, 200)
        self.assertTrue(result['updated'])
        p = get_position('D001')
        self.assertEqual(p['source'], 'phone')
        self.assertAlmostEqual(p['raw_lng'], 116.397)
        self.assertTrue(is_fresh(p))
        self.assertIsNone(get_position('D002'))
        info = db_manager.get_driver_info('D001')
        self.assertEqual(info['lng'], p['lng'])

    def test_unauthorized_and_cross_driver_reports(self):
        for token in (None, 'wrong-token'):
            with self.subTest(token=token):
                self.assertEqual(self.request(payload=self.payload(), token=token)[0], 401)
        self.assertEqual(self.request(payload=self.payload(driver_id='D002'), token=self.token)[0], 401)
        self.assertEqual(get_positions(), {})

    def test_rotation_revokes_old_credential(self):
        new = issue_token('D001')
        self.assertEqual(self.request(payload=self.payload(), token=self.token)[0], 401)
        self.assertEqual(self.request(payload=self.payload(), token=new)[0], 200)

    def test_old_and_duplicate_samples_cannot_overwrite(self):
        payload = self.payload()
        self.assertTrue(accept_position(self.token, payload))
        original = get_position('D001')
        self.assertFalse(accept_position(self.token, payload))
        self.assertFalse(accept_position(self.token, dict(payload, lng=117, timestamp=payload['timestamp']-1)))
        self.assertEqual(original, get_position('D001'))

    def test_rejects_invalid_measurements(self):
        bad_values = [('lng', 181), ('lat', -91), ('accuracy', -1), ('accuracy', float('inf')),
                      ('lng', float('nan')), ('lat', True), ('timestamp', time.time()+1000),
                      ('timestamp', time.time()-600), ('source', 'simulation'), ('coord_system', 'bd09')]
        for key, value in bad_values:
            with self.subTest(key=key, value=value):
                self.assertEqual(self.request(payload=self.payload(**{key: value}), token=self.token)[0], 400)
        self.assertEqual(get_positions(), {})

    def test_protocol_errors(self):
        self.assertEqual(self.request(raw=b'{', token=self.token)[0], 400)
        self.assertEqual(self.request(payload=[], token=self.token)[0], 400)
        self.assertEqual(self.request(raw=b'x'*4097, token=self.token)[0], 413)
        self.assertEqual(self.request(path='/other', payload={}, token=self.token)[0], 404)

    def test_vehicle_gcj02_no_double_conversion(self):
        accept_position(self.token, self.payload(coord_system='gcj02', source='vehicle'))
        self.assertEqual(get_position('D001')['lng'], 116.397)
        self.assertEqual(get_position('D001')['source'], 'vehicle')

    def test_conversion_reference_and_overseas(self):
        lng, lat = wgs84_to_gcj02(116.397, 39.908)
        self.assertAlmostEqual(lng, 116.4032434, places=6)
        self.assertAlmostEqual(lat, 39.9094034, places=6)
        self.assertEqual(wgs84_to_gcj02(-.1276, 51.5072), (-.1276, 51.5072))

    def test_freshness_uses_sample_time_as_well_as_receipt(self):
        self.assertFalse(is_fresh(None))
        self.assertFalse(is_fresh({'sampled_at': 800, 'received_at': 999}, now=1000))
        self.assertTrue(is_fresh({'sampled_at': 950, 'received_at': 999}, now=1000))

    def test_schema_upgrade_preserves_existing_locations(self):
        db_manager.update_driver_location('D001', 120, 30)
        init_db.init_database()
        self.assertEqual(db_manager.get_driver_info('D001')['lng'], 120)
        self.assertEqual(get_positions(), {})  # 旧模拟数据不冒充真实上报

    def test_only_phone_page_and_health_are_public(self):
        with urllib.request.urlopen(self.receiver.url+'/mobile') as response:
            self.assertIn(b'watchPosition', response.read())
        with self.assertRaises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(self.receiver.url+'/database/logistics.db')
        self.assertEqual(exc.exception.code, 404)


if __name__ == '__main__':
    unittest.main()
