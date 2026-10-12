"""内嵌网页的浅色菜单，以及地图脚本的加载、重试和错误显示。"""
import json
from html.parser import HTMLParser
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QMenu
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView

MENU_STYLE = """
    QMenu { background: #ffffff; color: #172033; border: 1px solid #bdc9d8;
            border-radius: 6px; padding: 6px; font: 14px 'Microsoft YaHei'; }
    QMenu::item { background: transparent; color: #172033; padding: 8px 28px 8px 12px; }
    QMenu::item:selected { background: #2563eb; color: #ffffff; border-radius: 4px; }
    QMenu::item:disabled { color: #64748b; background: transparent; }
    QMenu::separator { height: 1px; background: #e2e8f0; margin: 5px 8px; }
"""


def apply_light_palette(app):
    """防止 Windows 深色调色板与应用浅色文字样式混用。"""
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, '#f5f7fb'),
        (QPalette.ColorRole.WindowText, '#172033'),
        (QPalette.ColorRole.Base, '#ffffff'),
        (QPalette.ColorRole.AlternateBase, '#f1f5f9'),
        (QPalette.ColorRole.Text, '#172033'),
        (QPalette.ColorRole.Button, '#f1f5f9'),
        (QPalette.ColorRole.ButtonText, '#172033'),
        (QPalette.ColorRole.ToolTipBase, '#ffffff'),
        (QPalette.ColorRole.ToolTipText, '#172033'),
        (QPalette.ColorRole.Highlight, '#2563eb'),
        (QPalette.ColorRole.HighlightedText, '#ffffff'),
        (QPalette.ColorRole.PlaceholderText, '#64748b'),
    ):
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor('#64748b'))
    app.setPalette(palette)


class _ScriptParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.html = html
        self.offsets = [0]
        for line in html.splitlines(keepends=True):
            self.offsets.append(self.offsets[-1] + len(line))
        self.scripts = []
        self.current = None
        self.feed(html)

    def index(self):
        line, column = self.getpos()
        return self.offsets[line-1] + column

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            start = self.index()
            self.current = dict(start=start, content=start+len(self.get_starttag_text()), src=dict(attrs).get('src'))

    def handle_endtag(self, tag):
        if tag == 'script' and self.current:
            end = self.index()
            self.current['body'] = self.html[self.current['content']:end]
            self.current['end'] = self.html.index('>', end) + 1
            self.scripts.append(self.current)
            self.current = None


def prepare_map_html(html):
    scripts = _ScriptParser(html).scripts
    for index, sdk in enumerate(scripts[:-1]):
        if not sdk['src'] or QUrl(sdk['src']).host() != 'webapi.amap.com':
            continue
        initializer = scripts[index+1]
        if initializer['src']:
            continue
        config = json.dumps(dict(url=sdk['src'], init=initializer['body']), ensure_ascii=False).replace('<', '\\u003c')
        bootstrap = Path(__file__).with_name('map_bootstrap.js').read_text(encoding='utf-8')
        replacement = '<script>window.__logisticsMapConfig=' + config + ';\n' + bootstrap + '</script>'
        return html[:sdk['start']] + replacement + html[initializer['end']:]
    return html


class EmbeddedWebView(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._saved_html = None
        self._saved_base = QUrl()
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        self.page().setBackgroundColor(QColor('#ffffff'))

    def setHtml(self, html, baseUrl=QUrl()):
        self._saved_html = html
        self._saved_base = QUrl(baseUrl)
        super().setHtml(prepare_map_html(html), baseUrl)

    def load(self, url):
        self._saved_html = None
        super().load(url)

    def reload_content(self):
        # setHtml 的虚拟 baseUrl 并不是可刷新的网页，须重新加载保存的 HTML。
        if self._saved_html is not None:
            self.setHtml(self._saved_html, self._saved_base)
        else:
            super().reload()

    def create_readable_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        menu.setFont(QFont('Microsoft YaHei', 10))
        menu.addAction('刷新页面', self.reload_content)
        menu.addSeparator()
        copy = menu.addAction('复制', lambda: self.page().triggerAction(QWebEnginePage.WebAction.Copy))
        copy.setEnabled(self.page().action(QWebEnginePage.WebAction.Copy).isEnabled())
        menu.addAction('全选', lambda: self.page().triggerAction(QWebEnginePage.WebAction.SelectAll))
        return menu

    def contextMenuEvent(self, event):
        menu = self.create_readable_menu()
        menu.exec(event.globalPos())
        menu.deleteLater()
