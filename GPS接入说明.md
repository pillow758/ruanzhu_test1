# 真实车辆 GPS 接入

本次更新将桌面电脑定位改为按司机工号接收设备位置。管理员“实时监控”和驾驶员工作台每 3 秒读取最新上报；没有上报的车辆不生成位置。超过 120 秒未获得有效新采样时，保留最后位置并标记超时。导航和取货、送达操作均不改写 GPS 坐标。

## 没有服务器、需要异地测试

1. 双击项目根目录的 `启动智能物流系统.bat`，登录管理员（admin / 123456）。
2. 点击左侧 **GPS接入**，再点击 **启动异地接入（临时 HTTPS）**。
3. 首次使用自动从 Cloudflare 官方 GitHub 下载 cloudflared 到 `.runtime/`，校验官方 SHA256 后运行。需能访问 GitHub 和 Cloudflare 网络；窗口会显示失败或超时信息。
4. 等待显示“异地 HTTPS 接入已启动”，选择司机（例如 D001），点击 **生成 / 重置该司机接入链接**。
5. 对应司机用**手机系统浏览器**扫码或打开专属链接，点击 **开始上报手机位置**，允许定位权限。
6. 电脑端切到 **实时监控** 查看车辆、定位精度、采样时间和超时状态。驾驶员工作台读取同一工号的数据；最新定位有效时才能以车辆实际位置开始导航。

司机可以使用移动网络，无需与电脑在同一 Wi-Fi。位置来自打开上报页面的设备；在电脑上打开链接仍会获取电脑位置，须由司机手机打开。

电脑、系统和隧道必须持续运行。隧道停止或程序关闭后旧网址不可用；下次启动会生成新地址，需要给司机新的链接。生成新凭证会使该司机的旧凭证失效。凭证保存在链接片段中，不写入 HTTP URL 日志；服务器只存凭证哈希。

手机网页定位需要 HTTPS 和用户授权；保持页面在前台、屏幕常亮，锁屏或后台可能停止采样。页面支持屏幕唤醒锁，浏览器不支持时需手动保持常亮。临时隧道用于联调，没有长期可用性承诺；正式运营可使用固定 HTTPS 域名的反向代理或固定隧道。连续后台定位应使用司机 App 或车载设备接入相同接口。

## 固定 HTTPS 地址

接入窗口显示本机接收端（`http://127.0.0.1:<端口>`）。配置固定 HTTPS 反向代理或隧道，将 `/mobile`、`/health`、`/api/location` 原样转发至这个接收端，并保留 Authorization 请求头。接收端仅监听本机，不需要给电脑开放公网入站端口。

有固定反向代理配置时，可单独启动接收端：

```powershell
cd logistics_system
.\.venv\Scripts\python.exe gps_receiver.py --port 8765
```

独立接收端与桌面端须使用同一个 `database/logistics.db`。接入窗口中填写固定 HTTPS 域名（不带路径），生成司机链接。独立接收端可在桌面界面关闭后继续接收；桌面界面自带的临时接入服务会随程序退出。

## 车载设备 HTTP 接口

地址：`POST https://<接入域名>/api/location`

请求头：

```text
Content-Type: application/json
Authorization: Bearer <该司机专属链接中 token 参数的值>
```

请求体示例（坐标为接口说明用示例；timestamp 须由设备填写当前采样时间）：

```json
{
  "driver_id": "D001",
  "lng": 116.397,
  "lat": 39.908,
  "accuracy": 12.0,
  "timestamp": 0,
  "coord_system": "wgs84",
  "source": "vehicle"
}
```

- `timestamp`：Unix 秒数，允许 5 分钟内的采样，最多领先服务器 60 秒；设备和电脑应同步系统时间。
- `accuracy`：设备报告的水平定位精度，单位米；不要填写虚假的精度。
- `coord_system`：`wgs84`（原始 GPS）或 `gcj02`（高德坐标）。不支持直接提交百度 BD09。
- `source`：`phone` 或 `vehicle`。
- 每个司机独立凭证，不能代替其他司机上报。凭证重置后须更新设备配置。
- 返回 `200 {"ok":true,"updated":true}` 表示更新成功；`updated:false` 表示重复或旧采样，保留较新位置。`401` 为凭证错误，`400` 为无效字段，`413` 为过大/空请求体，`503` 为暂时存储失败。

原始坐标、精度、采样时间、接收时间和来源存入 `gps_positions`；地图位置同步到 `drivers.current_lng/current_lat`。WGS84 使用离线近似 GCJ02 转换以匹配高德底图，保留原始值；高精度业务可让设备通过地图供应商官方转换后上报 GCJ02。地图 API 的网络、密钥和配额仍沿用原有项目配置。

## 验证

在 `logistics_system` 中运行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_gps*.py" -v
```

16 项测试使用临时数据库，覆盖接收接口、凭证隔离和重置、坐标转换、旧数据保护、异常输入、升级兼容和桌面界面的数据同步；地图脚本语法检查需安装 Node.js。实际手机定位还需由司机在手机端授权后联调。

可选公网联调命令：`.\.venv\Scripts\python.exe tests\check_gps_remote.py`。此检查会临时创建公网 HTTPS 通道，用示例坐标验证页面、凭证上报和落库，结束后关闭通道，不修改业务数据库。

参考：[浏览器定位要求](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation_API)、[高德坐标系说明](https://lbs.amap.com/api/javascript-api-v2/guide/abc/basetype)、[Cloudflare 临时隧道](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)。
