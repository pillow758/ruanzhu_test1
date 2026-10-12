"""地图重试、错误反馈和右键刷新保留 HTML 的回归验证。"""
import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu')
from PyQt6.QtCore import QCoreApplication, QEvent, QUrl
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from web_view import EmbeddedWebView, prepare_map_html, _ScriptParser


HARNESS = r"""
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
function scenario(failures,initializer){
  let tasks=[], id=0, requests=0, now=0;
  const elements={};
  const sandbox={console, AMap:{}, __logisticsMapConfig:{url:'https://webapi.amap.com/maps?v=2.0&key=fixture', init:initializer}};
  sandbox.window=sandbox;
  sandbox.setTimeout=(fn,delay)=>{tasks.push({id:++id,fn,at:now+delay,cancelled:false});return id;};
  sandbox.clearTimeout=(id)=>{const t=tasks.find(t=>t.id===id);if(t)t.cancelled=true;};
  sandbox.document={
    createElement(tag){return {tag,style:{},hidden:false,children:[],appendChild(c){this.children.push(c)},remove(){}};},
    getElementById(id){return elements[id]||null;},
    body:{appendChild(e){elements[e.id]=e;}},
    head:{appendChild(script){requests++;if(requests<=failures){script.onerror();}else{
      sandbox.AMap.Map=function(){this.on=(name,fn)=>{if(name==='complete')sandbox.setTimeout(fn,0);};this.destroy=()=>{};};
      script.onload();
    }}}
  };
  vm.createContext(sandbox);vm.runInContext(input.code,sandbox);
  for(let count=0;count<100;count++){
    const pending=tasks.filter(t=>!t.cancelled&&!t.done).sort((a,b)=>a.at-b.at);
    if(!pending.length)break;
    const t=pending[0];t.done=true;now=t.at;t.fn();
  }
  return {sandbox,requests,panel:elements['map-load-status']};
}
const recovered=scenario(1,'var map=new AMap.Map("map", {}); function updateDriverPosition(p){window.latest=p;}');
assert.equal(recovered.requests,2);assert.equal(recovered.sandbox.__logisticsMapStatus.stage,'complete');
assert.equal(recovered.panel.style.display,'none');
assert.equal(typeof recovered.sandbox.updateDriverPosition,'function');
recovered.sandbox.updateDriverPosition([116.4,39.9]);assert.equal(recovered.sandbox.latest[0],116.4);
const failed=scenario(99,'var map=new AMap.Map("map", {});');
assert.equal(failed.requests,3);assert.equal(failed.sandbox.__logisticsMapStatus.stage,'error');
assert.equal(failed.panel.children[1].hidden,false);assert.match(failed.panel.children[0].textContent,/脚本加载失败/);
const badConfig=scenario(0,'throw new Error("INVALID_USER_SCODE");');
assert.equal(badConfig.sandbox.__logisticsMapStatus.stage,'error');
assert.match(badConfig.panel.children[0].textContent,/安全码/);
console.log('Map retry, error feedback, global update functions: PASS');
"""


class MapLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['map-tests'])

    def test_loader_retries_and_preserves_global_updates(self):
        if not shutil.which('node'):
            self.skipTest('requires Node.js')
        code = Path('map_bootstrap.js').read_text(encoding='utf-8')
        result = subprocess.run(['node','-e',HARNESS], input=json.dumps(dict(code=code)),
                                text=True,encoding='utf-8',capture_output=True,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_bootstrap_handles_original_onerror_html_and_keeps_security_config(self):
        original = '''<div id="map"></div><script>window._AMapSecurityConfig={securityJsCode:'fixture'};</script>
        <script src="https://webapi.amap.com/maps?v=2.0&amp;key=fixture" onerror="this.innerHTML='<br>failed';"></script>
        <script>var map=new AMap.Map('map', {});</script>'''
        prepared = prepare_map_html(original)
        self.assertIn("securityJsCode:'fixture'", prepared)
        self.assertNotIn('onerror="this.innerHTML', prepared)
        scripts = _ScriptParser(prepared).scripts
        self.assertEqual(len(scripts),2)
        config = json.loads(scripts[1]['body'].split(';\n',1)[0].split('=',1)[1])
        self.assertEqual(config['url'],'https://webapi.amap.com/maps?v=2.0&key=fixture')
        self.assertIn('new AMap.Map', config['init'])

    def test_context_menu_refresh_reloads_saved_document(self):
        view = EmbeddedWebView()
        try:
            with patch.object(QWebEngineView,'setHtml') as set_html, patch.object(QWebEngineView,'reload') as reload:
                original = '<html><p>物流地图</p></html>'
                view.setHtml(original,QUrl('https://localhost'))
                menu = view.create_readable_menu()
                menu.actions()[0].trigger()
                self.assertEqual(set_html.call_count,2)
                self.assertEqual(set_html.call_args.args[0],original)
                reload.assert_not_called()
                menu.deleteLater()
        finally:
            view.deleteLater()
            QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)


if __name__ == '__main__':
    unittest.main()
