/* 高德 SDK 加载重试。原页面的初始化代码仍在全局执行，保留地图更新函数。 */
(function () {
    'use strict';
    var config = window.__logisticsMapConfig;
    var state = window.__logisticsMapStatus = {stage: 'loading', attempts: 0, error: ''};
    var panel = document.createElement('div');
    panel.id = 'map-load-status';
    panel.style.cssText = 'position:fixed;z-index:10000;top:16px;left:50%;transform:translateX(-50%);max-width:85%;padding:12px 18px;background:white;color:#334155;border:1px solid #cbd5e1;border-radius:9px;font:14px/1.7 sans-serif;box-shadow:0 3px 16px #0001';
    var message = document.createElement('div');
    var retry = document.createElement('button');
    retry.textContent = '重新加载地图';
    retry.style.cssText = 'margin-top:8px;padding:7px 16px;background:#2563eb;color:white;border:0;border-radius:5px;cursor:pointer;font:inherit';
    retry.hidden = true;
    panel.appendChild(message);
    panel.appendChild(retry);
    document.body.appendChild(panel);
    var oldError = document.getElementById('map-error');
    if (oldError) oldError.style.display = 'none';
    var loadingTimer = null;
    function show(text, failed) {
        message.textContent = text;
        panel.style.display = 'block';
        retry.hidden = !failed;
        if (failed) {state.stage = 'error'; state.error = text;}
    }
    function describe(error) {
        var text = String(error && (error.info || error.message || error.type) || error || '未知错误');
        if (/INVALID_USER_SCODE/.test(text)) return '高德安全码与 Key 不匹配，请检查地图配置。';
        if (/INVALID_USER_KEY|USERKEY_PLAT_NOMATCH|INVALID_USER_DOMAIN/.test(text)) return '高德 Key、应用类型或域名配置不正确：' + text;
        return '地图初始化失败：' + text;
    }
    function initialize() {
        try {
            if (!window.AMap || typeof AMap.Map !== 'function') throw new Error('高德脚本未返回有效的地图组件');
            // 间接 eval 使用全局作用域，导航和监控页的更新函数可供 Python 调用。
            (0, eval)(config.init);
            state.stage = 'initialized';
            state.error = '';
            var map = window.map;
            if (map && typeof map.on === 'function') {
                map.on('complete', function () {
                    clearTimeout(loadingTimer);
                    state.stage = 'complete';
                    panel.style.display = 'none';
                });
                map.on('error', function (error) {show(describe(error), true);});
                show('地图组件已加载，正在获取底图…', false);
                loadingTimer = setTimeout(function () {
                    if (state.stage !== 'complete') show('底图加载时间较长，请检查网络后重新加载。', true);
                }, 20000);
            } else {
                panel.style.display = 'none';
            }
        } catch (error) {
            show(describe(error), true);
            console.error(error);
        }
    }
    function load() {
        state.attempts++;
        state.stage = 'loading';
        show('正在加载高德地图（第 ' + state.attempts + '/3 次）…', false);
        var script = document.createElement('script');
        var finished = false;
        var timeout = setTimeout(failed, 15000);
        function failed() {
            if (finished) return;
            finished = true;
            clearTimeout(timeout);
            script.remove();
            if (state.attempts < 3) setTimeout(load, 1000);
            else show('高德地图脚本加载失败，请检查网络连接或代理后重新加载。', true);
        }
        script.src = config.url;
        script.onerror = failed;
        script.onload = function () {
            if (finished) return;
            finished = true;
            clearTimeout(timeout);
            initialize();
        };
        document.head.appendChild(script);
    }
    // 避免刷新虚拟 https://localhost，保留完整页面内容后重试。
    retry.onclick = function () {
        clearTimeout(loadingTimer);
        if (!window.map || typeof window.map.destroy !== 'function') {
            state.attempts = 0;
            load();
        } else if (window.map && typeof window.map.destroy === 'function') {
            window.map.destroy();
            window.map = null;
            initialize();
        }
    };
    load();
})();
