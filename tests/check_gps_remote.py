"""可选网络联调：创建临时 HTTPS 隧道，使用临时数据库和示例坐标，结束后关闭。"""
import json
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import db_manager, init_db
from gps_access import GpsAccessService
from gps_store import get_position, issue_token


def main():
    service = GpsAccessService()
    with tempfile.TemporaryDirectory() as directory, patch.object(db_manager, 'DB_PATH', str(Path(directory)/'test.db')), patch.object(init_db, 'DB_PATH', str(Path(directory)/'test.db')):
        init_db.init_database()
        try:
            service.start_tunnel()
            deadline = time.monotonic()+180
            previous = ''
            while service.busy and time.monotonic()<deadline:
                if service.status != previous:
                    print(service.status, flush=True)
                    previous = service.status
                time.sleep(.5)
            if not service.public_url:
                raise RuntimeError(service.status)
            token = issue_token('D001')
            # 隧道注册后 DNS/路由可能需要短暂生效。
            for attempt in range(12):
                try:
                    with urllib.request.urlopen(service.public_url+'/health', timeout=10) as response:
                        assert json.load(response)['status']=='ok'
                    break
                except Exception:
                    if attempt == 11:
                        raise
                    time.sleep(2)
            with urllib.request.urlopen(service.public_url+'/mobile', timeout=15) as response:
                assert b'watchPosition' in response.read()
            payload = dict(driver_id='D001', lng=116.397, lat=39.908, accuracy=12,
                           timestamp=time.time(), source='vehicle', coord_system='gcj02')
            request = urllib.request.Request(service.public_url+'/api/location',
                data=json.dumps(payload).encode(), headers={'Content-Type':'application/json', 'Authorization':'Bearer '+token})
            with urllib.request.urlopen(request, timeout=15) as response:
                assert json.load(response)['updated']
            assert get_position('D001')['lng']==payload['lng']
            print('HTTPS page + authenticated report + SQLite persistence: PASS (fixture coordinates only)', flush=True)
        finally:
            service.stop()


if __name__ == '__main__':
    main()
