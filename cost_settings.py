"""
成本参数配置对话框 - 支持各项成本参数填写，实时更新计算结果
方案A：浅色/蓝色主题
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QGroupBox, QGridLayout, QMessageBox
)
from PyQt6.QtCore import Qt
from database.db_manager import get_cost_params, batch_update_cost_params


# 参数字段定义：(key, label, unit, description)
COST_FIELDS = [
    ('fixed_cost',        '固定成本',     '元/车次', '每次出车的基础费用（含车辆折旧、保险分摊）'),
    ('fuel_price',        '燃油单价',     '元/L',    '当前柴油/汽油零售价格'),
    ('fuel_consumption',  '百公里油耗',   'L/100km', '车辆满载状态下每百公里平均油耗'),
    ('toll_per_km',       '过路费',       '元/km',   '高速公路及桥梁通行费均值'),
    ('maintenance_per_km','车辆维护费',   '元/km',   '保养、轮胎、维修等费用分摊'),
    ('driver_wage',       '驾驶员工资',   '元/小时', '驾驶员出勤小时工资（含社保分摊）'),
]


class CostSettingsDialog(QDialog):
    """成本参数配置对话框 - 方案A浅色主题"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ 成本参数配置")
        self.setMinimumSize(480, 420)
        self.setStyleSheet("""
            QDialog { background: #ffffff; }
            QLabel  { color: #1e293b; font: 12px "SimSun"; }
            QLineEdit {
                background: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 6px 10px;
                font: 12px "SimSun";
                color: #1e293b;
            }
            QLineEdit:focus { border: 1px solid #3b82f6; }
        """)
        self.inputs = {}
        self._init_ui()
        self._load_params()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 标题
        title = QLabel("⚙️ 运输成本参数配置")
        title.setStyleSheet("color:#1e40af;font:bold 16px SimSun;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("修改以下参数后，调度算法的成本计算将实时更新")
        subtitle.setStyleSheet("color:#64748b;font:11px SimSun;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # ── 固定成本组 ─────────────────────────────────────
        fixed_group = QGroupBox("📌 固定成本")
        fixed_group.setStyleSheet("""
            QGroupBox {
                color:#1e40af; font:bold 12px SimSun;
                border:1px solid #bfdbfe; border-radius:8px;
                margin-top:10px; padding:14px 10px 10px 10px;
                background:#eff6ff;
            }
            QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 5px; }
        """)
        fixed_grid = QGridLayout()
        fixed_grid.setSpacing(8)

        key, label, unit, desc = COST_FIELDS[0]
        fixed_grid.addWidget(QLabel(f"{label}："), 0, 0)
        inp = QLineEdit()
        inp.setPlaceholderText(f"{desc}（{unit}）")
        self.inputs[key] = inp
        fixed_grid.addWidget(inp, 0, 1)
        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet("color:#64748b;font:11px;")
        fixed_grid.addWidget(unit_lbl, 0, 2)

        fixed_group.setLayout(fixed_grid)
        layout.addWidget(fixed_group)

        # ── 变动成本组 ─────────────────────────────────────
        var_group = QGroupBox("🚛 变动成本（与里程/时间相关）")
        var_group.setStyleSheet("""
            QGroupBox {
                color:#1e40af; font:bold 12px SimSun;
                border:1px solid #bfdbfe; border-radius:8px;
                margin-top:10px; padding:14px 10px 10px 10px;
                background:#eff6ff;
            }
            QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 5px; }
        """)
        var_grid = QGridLayout()
        var_grid.setSpacing(8)

        for row, (key, label, unit, desc) in enumerate(COST_FIELDS[1:]):
            var_grid.addWidget(QLabel(f"{label}："), row, 0)
            inp = QLineEdit()
            inp.setPlaceholderText(f"{desc}")
            self.inputs[key] = inp
            var_grid.addWidget(inp, row, 1)
            unit_lbl = QLabel(unit)
            unit_lbl.setStyleSheet("color:#64748b;font:11px;")
            var_grid.addWidget(unit_lbl, row, 2)

        var_group.setLayout(var_grid)
        layout.addWidget(var_group)

        # ── 成本公式说明 ───────────────────────────────────
        formula_frame = QFrame()
        formula_frame.setStyleSheet("""
            QFrame { background:#f0f4f8; border:1px solid #e2e8f0; border-radius:8px; }
        """)
        formula_layout = QVBoxLayout(formula_frame)
        formula_title = QLabel("💡 成本计算公式")
        formula_title.setStyleSheet("color:#1e40af;font:bold 11px SimSun;")
        formula_layout.addWidget(formula_title)
        formula_text = QLabel(
            "单车成本 = 固定成本 + 配送距离 × ( 燃油单价×油耗÷100 + 过路费 + 维护费 )\n"
            "时间成本 = 配送距离 ÷ 平均速度(30km/h) × 驾驶员工资"
        )
        formula_text.setStyleSheet("color:#475569;font:11px SimSun;")
        formula_text.setWordWrap(True)
        formula_layout.addWidget(formula_text)
        layout.addWidget(formula_frame)

        # ── 按钮区 ─────────────────────────────────────────
        btn_layout = QHBoxLayout()

        reset_btn = QPushButton("恢复默认")
        reset_btn.setStyleSheet("""
            QPushButton { background:#f1f5f9;color:#475569;border:1px solid #e2e8f0;
                          border-radius:6px;padding:7px 16px;font:bold 12px SimSun;}
            QPushButton:hover { background:#e2e8f0; }
        """)
        reset_btn.clicked.connect(self._reset_defaults)
        btn_layout.addWidget(reset_btn)

        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton { background:#f1f5f9;color:#475569;border:1px solid #e2e8f0;
                          border-radius:6px;padding:7px 16px;font:bold 12px SimSun;}
            QPushButton:hover { background:#e2e8f0; }
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("💾 保存参数")
        save_btn.setStyleSheet("""
            QPushButton { background:#3b82f6;color:white;border:none;border-radius:6px;
                          padding:7px 16px;font:bold 12px SimSun;}
            QPushButton:hover { background:#2563eb; }
        """)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _load_params(self):
        """从数据库加载参数填入输入框"""
        params = get_cost_params()
        for key, inp in self.inputs.items():
            data = params.get(key, {})
            val = data.get('value', 0.0)
            inp.setText(f"{val:.2f}" if val else "0.00")

    def _reset_defaults(self):
        """恢复默认值"""
        defaults = {k: v for k, v, *_ in [
            ('fixed_cost',         400.0),
            ('fuel_price',           7.8),
            ('fuel_consumption',    12.0),
            ('toll_per_km',          0.5),
            ('maintenance_per_km',   0.3),
            ('driver_wage',         30.0),
        ]}
        for key, val in defaults.items():
            self.inputs[key].setText(f"{val:.2f}")

    def _save(self):
        """验证并保存"""
        params = {}
        for key, inp in self.inputs.items():
            text = inp.text().strip()
            try:
                val = float(text)
                if val < 0:
                    raise ValueError
                params[key] = val
            except ValueError:
                label = next(l for k, l, *_ in COST_FIELDS if k == key)
                QMessageBox.warning(self, "输入错误", f"「{label}」请输入有效的非负数字")
                inp.setFocus()
                return

        batch_update_cost_params(params)
        QMessageBox.information(self, "保存成功", "成本参数已更新，调度算法将使用新参数计算成本。")
        self.accept()

    def get_current_params(self):
        """返回当前输入框中的参数字典（供外部调用）"""
        params = {}
        for key, inp in self.inputs.items():
            try:
                params[key] = float(inp.text())
            except ValueError:
                params[key] = 0.0
        return params
