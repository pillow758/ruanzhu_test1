"""省市区县地址输入、在线解析、地图确认及配送中心保存。"""
import json
from pathlib import Path
from PyQt6.QtCore import QObject, QSignalBlocker, Qt, QTimer, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QPalette
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWidgets import (
    QCheckBox,QComboBox,QDialog,QFormLayout,QHBoxLayout,QLabel,QLineEdit,
    QMessageBox,QPushButton,QScrollArea,QVBoxLayout,QWidget,
)
from web_view import EmbeddedWebView
from depot_settings import compose_address,get_depot,get_effective_depot,precise_enough,save_depot

AMAP_API_KEY='ddbc01b09151f242d386549e5f472f79'
AMAP_SECURITY_CODE='776a13f6acec470076eb03e867c7e84d'


class DepotBridge(QObject):
    ready=pyqtSignal()
    regions=pyqtSignal(str)
    geocodes=pyqtSignal(str)
    picked=pyqtSignal(float,float)
    reverse=pyqtSignal(str)

    @pyqtSlot()
    def mapReady(self): self.ready.emit()
    @pyqtSlot(str)
    def regionsResult(self,data): self.regions.emit(data)
    @pyqtSlot(str)
    def geocodeResult(self,data): self.geocodes.emit(data)
    @pyqtSlot(float,float)
    def pointPicked(self,lng,lat): self.picked.emit(lng,lat)
    @pyqtSlot(str)
    def reverseResult(self,data): self.reverse.emit(data)


class DepotSettingsDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('配送中心位置设置')
        self.setObjectName('depotSettingsDialog')
        self.setFont(QFont('Microsoft YaHei',10))
        palette=self.palette()
        for role,color in ((QPalette.ColorRole.Window,'#f5f7fb'),(QPalette.ColorRole.Base,'#ffffff'),
                           (QPalette.ColorRole.Text,'#172033'),(QPalette.ColorRole.WindowText,'#172033')):
            palette.setColor(role,QColor(color))
        self.setPalette(palette)
        self.setStyleSheet('''
            QDialog#depotSettingsDialog,QWidget#addressForm {background:#f5f7fb;}
            QLabel {color:#172033;background:transparent;border:none;font:14px 'Microsoft YaHei';}
            QLineEdit,QComboBox {background:white;color:#172033;border:1px solid #a8b7cb;border-radius:6px;padding:7px;min-height:22px;font:14px 'Microsoft YaHei';selection-background-color:#2563eb;selection-color:white;}
            QComboBox QAbstractItemView {background:white;color:#172033;selection-background-color:#2563eb;selection-color:white;}
            QPushButton {background:#2563eb;color:white;border:none;border-radius:6px;padding:10px 14px;font:14px 'Microsoft YaHei';}
            QPushButton:hover {background:#1d4ed8;}
            QPushButton:disabled {background:#e2e8f0;color:#475569;}
            QPushButton#cancelButton {background:white;color:#334155;border:1px solid #cbd5e1;}
            QCheckBox {color:#172033;font:14px 'Microsoft YaHei';spacing:7px;}
            QCheckBox::indicator {width:18px;height:18px;border:1px solid #94a3b8;background:white;border-radius:3px;}
            QCheckBox::indicator:checked {background:#2563eb;border-color:#2563eb;}
            QScrollArea {border:none;background:#f5f7fb;}
        ''')
        area=self.screen().availableGeometry()
        self.resize(min(1080,area.width()-60),min(760,area.height()-80))
        self.saved_depot=None
        saved=get_depot()
        self.candidate=dict(saved) if saved else None
        self._ready=False
        self._version=0
        self._region_seq=0
        self._region_requests={}
        self._pending_region=None
        outer=QVBoxLayout(self)
        outer.setContentsMargins(16,16,16,16)
        explanation=QLabel('填写省、市、区县、街道/乡镇和门牌号，再定位地址。请在地图上确认配送中心实际入口；街道级结果需要补充地址或重新选点。')
        explanation.setWordWrap(True)
        outer.addWidget(explanation)
        body=QHBoxLayout()
        outer.addLayout(body,1)
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(310)
        scroll.setMaximumWidth(360)
        form_widget=QWidget()
        form_widget.setObjectName('addressForm')
        scroll.setWidget(form_widget)
        form=QFormLayout(form_widget)
        form.setContentsMargins(0,8,14,8)
        form.setVerticalSpacing(12)
        self.name=QLineEdit((saved or {}).get('name','配送中心'))
        self.name.setMaxLength(80)
        form.addRow('名称',self.name)
        self.province,self.city,self.district=(QComboBox() for _ in range(3))
        for label,key,combo in (('省 / 直辖市','province',self.province),('市','city',self.city),('区 / 县','district',self.district)):
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            combo.lineEdit().setMaxLength(80)
            combo.setEditText((saved or {}).get(key,''))
            form.addRow(label,combo)
        self.street_combo=QComboBox()
        self.street_combo.setEditable(True)
        self.street_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.street=self.street_combo.lineEdit()
        self.street.setText((saved or {}).get('street',''))
        self.street.setPlaceholderText('例如：望京街道 / 城关镇')
        self.detail=QLineEdit((saved or {}).get('detail',''))
        self.detail.setPlaceholderText('道路、门牌号、园区或仓库名称')
        self.street.setMaxLength(100)
        self.detail.setMaxLength(200)
        form.addRow('街道 / 乡镇',self.street_combo)
        form.addRow('详细地址',self.detail)
        self.query=QPushButton('定位地址')
        self.query.setEnabled(False)
        self.query.clicked.connect(self._search)
        form.addRow(self.query)
        self.results=QComboBox()
        self.results.setMinimumContentsLength(10)
        self.results.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.results.addItem('定位后选择匹配结果')
        self.results.currentIndexChanged.connect(self._select_result)
        form.addRow('匹配结果',self.results)
        self.status=QLabel('正在加载地图和地址服务…')
        self.status.setWordWrap(True)
        form.addRow(self.status)
        self.coordinates=QLabel('尚未确认位置')
        self.coordinates.setWordWrap(True)
        self.coordinates.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow(self.coordinates)
        self.confirm=QCheckBox('已确认标记位于配送中心入口')
        self.confirm.toggled.connect(self._update_save)
        form.addRow(self.confirm)
        body.addWidget(scroll)
        self.map_view=EmbeddedWebView(self)
        body.addWidget(self.map_view,1)
        buttons=QHBoxLayout()
        buttons.addStretch()
        cancel=QPushButton('取消')
        cancel.setObjectName('cancelButton')
        cancel.clicked.connect(self.reject)
        self.save_button=QPushButton('保存并应用配送中心')
        self.save_button.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(self.save_button)
        outer.addLayout(buttons)
        self.bridge=DepotBridge(self)
        self.channel=QWebChannel(self.map_view.page())
        self.channel.registerObject('depotBridge',self.bridge)
        self.map_view.page().setWebChannel(self.channel)
        self.bridge.ready.connect(self._map_ready)
        self.bridge.regions.connect(self._regions_received)
        self.bridge.geocodes.connect(self._geocodes_received)
        self.bridge.picked.connect(self._point_picked)
        self.bridge.reverse.connect(self._reverse_received)
        self.region_timer=QTimer(self)
        self.region_timer.setSingleShot(True)
        self.region_timer.timeout.connect(self._load_pending_region)
        self.query_timer=QTimer(self)
        self.query_timer.setSingleShot(True)
        self.query_timer.timeout.connect(self._search_timeout)
        self.province.currentTextChanged.connect(lambda:self._region_changed('province'))
        self.city.currentTextChanged.connect(lambda:self._region_changed('city'))
        self.district.currentTextChanged.connect(lambda:self._region_changed('district'))
        self.street.textChanged.connect(self._invalidate)
        self.detail.textChanged.connect(self._invalidate)
        self.name.textChanged.connect(self._update_save)
        center=get_effective_depot()
        html=Path(__file__).with_name('depot_map.html').read_text(encoding='utf-8')
        html=html.replace('__SECURITY_CODE__',json.dumps(AMAP_SECURITY_CODE)).replace('__API_KEY__',AMAP_API_KEY)
        html=html.replace('__CENTER__',json.dumps([center['lng'],center['lat']]))
        self.map_view.setHtml(html,QUrl('https://localhost'))
        self._display_candidate()

    def _js(self,function,*args):
        self.map_view.page().runJavaScript('if(typeof '+function+"==='function') "+function+'('+','.join(json.dumps(a,ensure_ascii=False) for a in args)+');')

    def _form_values(self):
        province=self.province.currentText().strip()
        city=self.city.currentText().strip()
        if province.removesuffix('市') in {'北京','上海','天津','重庆'} and city.endswith(('城区','郊县')):
            city=province
        return dict(name=self.name.text().strip(),province=province,
                    city=city,district=self.district.currentText().strip(),
                    street=self.street.text().strip(),detail=self.detail.text().strip())

    def _invalidate(self,*args):
        self._version+=1
        self.query_timer.stop()
        self.candidate=None
        self.confirm.setChecked(False)
        self.query.setEnabled(self._ready)
        self.status.setText('地址已修改，请重新定位，或点击地图选择入口。')
        with QSignalBlocker(self.results):
            self.results.clear()
            self.results.addItem('定位后选择匹配结果')
        self._js('depotClearCandidate')
        self._display_candidate()

    def _region_changed(self,level):
        self._invalidate()
        affected={'province':(self.city,self.district,self.street_combo),'city':(self.district,self.street_combo),'district':(self.street_combo,)}[level]
        for combo in affected:
            with QSignalBlocker(combo),QSignalBlocker(combo.lineEdit()): combo.clear()
        self._pending_region={'province':'city','city':'district','district':'street'}[level]
        self.region_timer.start(350)

    def _set_items(self,combo,items,text=None):
        preserve=combo.currentText() if text is None else text
        with QSignalBlocker(combo),QSignalBlocker(combo.lineEdit()):
            combo.clear()
            for item in items: combo.addItem(item['name'],str(item.get('code') or ''))
            index=combo.findText(preserve)
            combo.setCurrentIndex(index)
            if index<0: combo.setEditText(preserve)

    def _map_ready(self):
        self._ready=True
        self.query.setEnabled(True)
        self.status.setText('可选择或直接填写省、市、区县，再定位详细地址。')
        self._load_region('province','中国')
        if self.candidate:
            self._js('depotShowPoint',self.candidate['lng'],self.candidate['lat'])
            self._display_candidate()

    def _load_pending_region(self):
        if not self._ready or not self._pending_region: return
        level=self._pending_region
        self._pending_region=None
        combo={'city':self.province,'district':self.city,'street':self.district}[level]
        keyword=self._region_key(combo)
        if keyword: self._load_region(level,str(keyword))

    def _region_key(self,combo):
        if combo.currentIndex()>=0 and combo.itemText(combo.currentIndex())==combo.currentText():
            return combo.currentData() or combo.currentText()
        return combo.currentText().strip()

    def _load_region(self,level,keyword):
        self._region_seq+=1
        parents=(self.province.currentText(),self.city.currentText(),self.district.currentText())
        self._region_requests[self._region_seq]=(level,parents)
        self._js('depotLoadRegions',self._region_seq,level,keyword)

    def _regions_received(self,raw):
        data=json.loads(raw)
        request=self._region_requests.pop(data['request_id'],None)
        if not request: return
        level,parents=request
        if level=='city' and parents[0]!=self.province.currentText(): return
        if level=='district' and parents[:2]!=(self.province.currentText(),self.city.currentText()): return
        if level=='street' and parents!=(self.province.currentText(),self.city.currentText(),self.district.currentText()): return
        items=data.get('items',[])
        if not items:
            if not self.candidate: self.status.setText('地区列表暂不可用，可直接填写省、市、区县后定位。')
            return
        if level=='province':
            self._set_items(self.province,items)
            if self.province.currentText(): self._load_region('city',str(self._region_key(self.province)))
        elif level=='city' and all(item.get('level')=='district' for item in items):
            self._set_items(self.city,[dict(name=self.province.currentText(),code=self.province.currentData())],self.province.currentText())
            self._set_items(self.district,items)
        elif level=='city':
            if len(items)==1 and self.province.currentText().removesuffix('市') in {'北京','上海','天津','重庆'}:
                self._set_items(self.city,[dict(items[0],name=self.province.currentText())],self.province.currentText())
            else: self._set_items(self.city,items)
            if self.city.currentText(): self._load_region('district',str(self._region_key(self.city)))
        elif level=='district':
            self._set_items(self.district,items)
            if self.district.currentText(): self._load_region('street',str(self._region_key(self.district)))
        else: self._set_items(self.street_combo,items)

    def _search(self):
        values=self._form_values()
        if not all(values[k] for k in ('province','city','district','street')):
            QMessageBox.warning(self,'地址不完整','请填写省、市、区县、街道或乡镇。')
            return
        self._invalidate()
        self.query.setEnabled(False)
        self.status.setText('正在解析详细地址…')
        self.query_timer.start(25000)
        address=compose_address(*(values[k] for k in ('province','city','district','street','detail')))
        self._js('depotGeocode',self._version,address,values['city'])

    def _search_timeout(self):
        self._version+=1
        self.query.setEnabled(self._ready)
        self.status.setText('地址解析超时，可重新定位，或直接在地图上选择配送中心入口。')

    def _geocodes_received(self,raw):
        data=json.loads(raw)
        if data['version']!=self._version: return
        self.query_timer.stop()
        self.query.setEnabled(self._ready)
        items=data.get('items',[])
        with QSignalBlocker(self.results):
            self.results.clear()
            for item in items:
                item=dict(item,source='geocode')
                self.results.addItem(item['address']+' · '+item['level'],item)
        if not items:
            self.status.setText('未找到该地址，请补充门牌号或直接在地图上选点。'+data.get('error',''))
            return
        self.results.setCurrentIndex(0)
        self._select_result(0)

    def _select_result(self,index):
        value=self.results.itemData(index) if index>=0 else None
        if not value: return
        self.candidate=dict(value)
        for key,combo in (('province',self.province),('city',self.city),('district',self.district)):
            if value.get(key):
                with QSignalBlocker(combo):
                    combo.setCurrentIndex(combo.findText(value[key]))
                    combo.setEditText(value[key])
        self.confirm.setChecked(False)
        self._js('depotShowPoint',value['lng'],value['lat'])
        self._display_candidate()

    def _point_picked(self,lng,lat):
        self._version+=1
        self.query_timer.stop()
        self.query.setEnabled(self._ready)
        values=self._form_values()
        self.candidate=dict(lng=lng,lat=lat,level='地图选点',source='map',
                            address=compose_address(*(values[k] for k in ('province','city','district','street','detail'))))
        self.confirm.setChecked(False)
        self._display_candidate()
        self._js('depotShowPoint',lng,lat)
        self._js('depotReversePoint',self._version,lng,lat)

    def _reverse_received(self,raw):
        data=json.loads(raw)
        if data['version']!=self._version or not self.candidate or self.candidate['source']!='map': return
        if data.get('address'):
            self.candidate['address']=data['address']
            for key,widget in (('province',self.province),('city',self.city),('district',self.district),('street',self.street),('detail',self.detail)):
                if data.get(key):
                    with QSignalBlocker(widget):
                        if isinstance(widget,QComboBox):
                            widget.setCurrentIndex(widget.findText(data[key]))
                            widget.setEditText(data[key])
                        else: widget.setText(data[key])
        self._display_candidate()

    def _display_candidate(self):
        if self.candidate:
            point=self.candidate
            self.coordinates.setText(f"经度 {point['lng']:.6f}\n纬度 {point['lat']:.6f}\n匹配级别：{point['level']}")
            if precise_enough(point): self.status.setText(point['address']+'\n请确认标记位于配送中心入口，再勾选确认并保存。')
            else: self.status.setText(point['address']+'\n仅匹配到区域或街道，不能确定仓库入口。请补充门牌号，或点击地图重新选点。')
        else: self.coordinates.setText('尚未确认配送中心经纬度')
        self._update_save()

    def _update_save(self,*args):
        values=self._form_values()
        self.save_button.setEnabled(precise_enough(self.candidate) and self.confirm.isChecked()
                                    and all(values[k] for k in ('name','province','city','district','street')))

    def _save(self):
        if not self.save_button.isEnabled(): return
        record=dict(self._form_values(),**{k:self.candidate[k] for k in ('lng','lat','address','level','source')})
        try: self.saved_depot=save_depot(record)
        except Exception as exc:
            QMessageBox.warning(self,'保存失败',str(exc))
            return
        self.accept()

    def done(self,result):
        self.region_timer.stop()
        self.query_timer.stop()
        super().done(result)
