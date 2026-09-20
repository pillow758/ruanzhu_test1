"""
订单管理模块 - 订单全生命周期管理，状态追踪，时间线展示
方案A：浅色/蓝色主题
"""
import json
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QPushButton, QSplitter, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from database import db_manager

# 状态中文映射
STATUS_LABEL = {
    'pending':     '待分配',
    'assigned':    '已分配',
    'picking_up':  '取货中',
    'delivering':  '配送中',
    'completed':   '已送达',
    'exception':   '异常',
    'cancelled':   '已取消',
}

STATUS_COLOR = {
    'pending':     '#f59e0b',
    'assigned':    '#3b82f6',
    'picking_up':  '#8b5cf6',
    'delivering':  '#06b6d4',
    'completed':   '#10b981',
    'exception':   '#ef4444',
    'cancelled':   '#6b7280',
}

# 状态流转规则：当前状态 → 允许的下一步状态
STATUS_TRANSITIONS = {
    'pending':    ['assigned'],
    'assigned':   ['picking_up', 'cancelled'],
    'picking_up': ['delivering'],
    'delivering': ['completed', 'exception'],
    'exception':  ['delivering', 'cancelled'],
}


class OrderManageWidget(QWidget):
    """订单管理主组件 - 方案A浅色主题"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_order_id = None
        self._init_ui()
        self._load_orders()

    # ------------------------------------------------------------------ UI
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── 顶部工具栏 ──────────────────────────────────────────
        toolbar = QFrame()
        toolbar.setStyleSheet("background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("📋 订单全生命周期管理")
        title.setStyleSheet("color:#1e40af;font:bold 15px SimSun;")
        tb_layout.addWidget(title)

        # 状态统计标签
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("color:#64748b;font:12px SimSun;")
        tb_layout.addWidget(self.summary_label)

        tb_layout.addStretch()

        # 状态筛选
        filter_lbl = QLabel("状态筛选：")
        filter_lbl.setStyleSheet("color:#475569;font:12px SimSun;")
        tb_layout.addWidget(filter_lbl)
        self.filter_combo = QComboBox()
        self.filter_combo.setStyleSheet("""
            QComboBox {
                background:#ffffff; color:#1e293b;
                border:1px solid #3b82f6; border-radius:6px; padding:4px 8px;
                font:12px SimSun;
            }
            QComboBox::drop-down { border:none; }
            QComboBox QAbstractItemView {
                background:#ffffff; color:#1e293b; selection-background-color:#dbeafe; selection-color:#1e40af;
                border:1px solid #bfdbfe;
            }
        """)
        self.filter_combo.addItem("全部", None)
        for key, label in STATUS_LABEL.items():
            self.filter_combo.addItem(label, key)
        self.filter_combo.currentIndexChanged.connect(self._load_orders)
        tb_layout.addWidget(self.filter_combo)

        # 刷新按钮
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.setStyleSheet("""
            QPushButton { background:#3b82f6;color:white;border:none;
                          border-radius:6px;padding:5px 12px;font:bold 12px SimSun;}
            QPushButton:hover { background:#2563eb; }
        """)
        refresh_btn.clicked.connect(self._load_orders)
        tb_layout.addWidget(refresh_btn)

        layout.addWidget(toolbar)

        # ── 主体：上方表格 + 下方时间线 ────────────────────────
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 订单表格
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "订单号", "客户", "地址", "需求量(kg)", "状态",
            "分配驾驶员", "创建时间", "操作"
        ])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setStyleSheet("""
            QTableWidget {
                background:#ffffff; gridline-color:#e2e8f0;
                color:#1e293b; font:9pt "SimSun";
                border:1px solid #e2e8f0; border-radius:8px;
            }
            QTableWidget::item:selected { background:#dbeafe; color:#1e40af; }
            QHeaderView::section {
                background:#3b82f6; color:white; padding:5px;
                border:none; font:bold 9pt "SimSun";
            }
        """)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.cellClicked.connect(self._on_order_selected)
        splitter.addWidget(self.table)

        # 下方时间线面板
        timeline_frame = QFrame()
        timeline_frame.setStyleSheet("background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;")
        timeline_frame.setFixedHeight(200)
        tl_layout = QVBoxLayout(timeline_frame)
        tl_layout.setContentsMargins(12, 10, 12, 10)

        # 时间线标题行
        tl_header = QHBoxLayout()
        tl_title = QLabel("🕒 状态时间线")
        tl_title.setStyleSheet("color:#1e40af;font:bold 13px SimSun;")
        tl_header.addWidget(tl_title)

        # 状态推进按钮区
        self.action_layout = QHBoxLayout()
        self.action_layout.setSpacing(6)
        tl_header.addLayout(self.action_layout)
        tl_header.addStretch()
        tl_layout.addLayout(tl_header)

        # 时间线滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border:none; background:transparent; }
            QScrollBar:vertical { width:6px; background:#f1f5f9;border-radius:3px; }
            QScrollBar::handle:vertical { background:#cbd5e1;border-radius:3px; }
        """)
        self.timeline_container = QWidget()
        self.timeline_layout = QVBoxLayout(self.timeline_container)
        self.timeline_layout.setContentsMargins(0, 0, 0, 0)
        self.timeline_layout.setSpacing(0)
        self.timeline_layout.addStretch()
        scroll.setWidget(self.timeline_container)
        tl_layout.addWidget(scroll, 1)

        splitter.addWidget(timeline_frame)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)

    # ------------------------------------------------------------- Data
    def _load_orders(self):
        """加载订单列表"""
        status_filter = self.filter_combo.currentData()
        orders = db_manager.get_all_orders(status_filter=status_filter)

        # 更新统计
        summary = db_manager.get_order_status_summary()
        parts = [f"{STATUS_LABEL.get(k, k)}: {v}" for k, v in summary.items()]
        self.summary_label.setText("  |  ".join(parts) if parts else "暂无订单数据")

        # 填充表格
        self.table.setRowCount(len(orders))
        for row, o in enumerate(orders):
            items = [
                str(o.get('id', '')),
                o.get('customer_name', ''),
                o.get('address', ''),
                f"{o.get('demand', 0):.1f}" if o.get('demand') else '',
                self._status_badge(o.get('status', 'pending')),
                o.get('assigned_driver', '') or '-',
                o.get('created_at', '') or '-',
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                if col == 4:  # 状态列用彩色文字代替白字
                    status = o.get('status', 'pending')
                    item.setForeground(QColor(STATUS_COLOR.get(status, '#666')))
                self.table.setItem(row, col, item)

            # 操作列：按钮
            self._add_action_buttons(row, o)

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(2, 300)

    def _status_badge(self, status):
        """返回带图标的状态文字"""
        icons = {
            'pending': '⏳', 'assigned': '✅', 'picking_up': '📦',
            'delivering': '🚚', 'completed': '✅', 'exception': '⚠️',
            'cancelled': '❌'
        }
        return f"{icons.get(status, '')} {STATUS_LABEL.get(status, status)}"

    def _add_action_buttons(self, row, order):
        """在操作列添加状态推进按钮"""
        widget = QWidget()
        widget.setStyleSheet("background:transparent;")
        btn_layout = QHBoxLayout(widget)
        btn_layout.setContentsMargins(4, 2, 4, 2)
        btn_layout.setSpacing(4)

        current_status = order.get('status', 'pending')
        transitions = STATUS_TRANSITIONS.get(current_status, [])

        for next_status in transitions:
            btn = QPushButton(STATUS_LABEL.get(next_status, next_status))
            color = STATUS_COLOR.get(next_status, '#888')
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{color}; color:white; border:none;
                    border-radius:4px; padding:3px 10px;
                    font:bold 10px SimSun;
                }}
                QPushButton:hover {{ background:{color}dd; }}
            """)
            btn.clicked.connect(
                lambda checked, oid=order['id'], ns=next_status, cs=current_status:
                    self._advance_status(oid, cs, ns)
            )
            btn_layout.addWidget(btn)

        # 将操作 widget 放入最后一列
        self.table.setCellWidget(row, 7, widget)

    # -------------------------------------------------------- Status
    def _advance_status(self, order_id, from_status, to_status):
        """推进订单状态"""
        # 更新数据库
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET status=? WHERE id=?", (to_status, order_id))
        conn.commit()
        conn.close()

        # 记录日志
        db_manager.log_order_status_change(
            order_id=str(order_id),
            task_id=None,
            from_status=from_status,
            to_status=to_status,
            operator='admin',
            note=''
        )

        self._load_orders()
        # 重新选中当前订单以刷新时间线
        if self.current_order_id:
            self._show_timeline(self.current_order_id)

    # --------------------------------------------------------- Click
    def _on_order_selected(self, row, col):
        """点击订单行"""
        item = self.table.item(row, 0)
        if item:
            self.current_order_id = item.text()
            self._show_timeline(self.current_order_id)

    # ------------------------------------------------------ Timeline
    def _show_timeline(self, order_id):
        """显示订单状态时间线"""
        logs = db_manager.get_order_status_log(order_id)

        # 清空现有
        while self.timeline_layout.count() > 1:
            item = self.timeline_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # 清除操作按钮
        while self.action_layout.count():
            item = self.action_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not logs:
            lbl = QLabel("暂无状态变更记录（订单刚创建时自动记录首条）")
            lbl.setStyleSheet("color:#64748b;font:12px SimSun;")
            self.timeline_layout.insertWidget(0, lbl)
            return

        # 当前状态的操作按钮
        current_order = None
        for o in db_manager.get_all_orders():
            if str(o['id']) == str(order_id):
                current_order = o
                break

        if current_order:
            transitions = STATUS_TRANSITIONS.get(current_order['status'], [])
            for next_status in transitions:
                btn = QPushButton(f"→ {STATUS_LABEL.get(next_status, next_status)}")
                color = STATUS_COLOR.get(next_status, '#888')
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background:{color}; color:white; border:none;
                        border-radius:6px; padding:4px 12px;
                        font:bold 11px SimSun;
                    }}
                    QPushButton:hover {{ background:{color}dd; }}
                """)
                btn.clicked.connect(
                    lambda checked, ns=next_status, cs=current_order['status']:
                        self._advance_status(order_id, cs, ns)
                )
                self.action_layout.addWidget(btn)

        # 构建时间线节点
        for i, log in enumerate(logs):
            node = self._make_timeline_node(log, i, len(logs))
            self.timeline_layout.insertWidget(
                self.timeline_layout.count() - 1, node
            )

    def _make_timeline_node(self, log, index, total):
        """创建单个时间线节点"""
        is_last = (index == total - 1)
        to_status = log.get('to_status', '')
        color = STATUS_COLOR.get(to_status, '#888')

        frame = QFrame()
        frame.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)

        # 左侧：圆点 + 竖线
        dot_frame = QFrame()
        dot_frame.setFixedWidth(20)
        dot_frame.setStyleSheet("background:transparent;")
        dot_layout = QVBoxLayout(dot_frame)
        dot_layout.setContentsMargins(0, 0, 0, 0)
        dot_layout.setSpacing(0)

        dot = QLabel("●")
        dot.setStyleSheet(f"color:{color};font:16px;border:none;")
        dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dot_layout.addWidget(dot)

        if not is_last:
            line = QFrame()
            line.setFixedWidth(2)
            line.setStyleSheet(f"background:{color}40;")
            line.setMinimumHeight(20)
            dot_layout.addWidget(line, 1)

        layout.addWidget(dot_frame)

        # 右侧：内容
        content = QVBoxLayout()
        content.setSpacing(2)

        status_lbl = QLabel(
            f"{STATUS_LABEL.get(log.get('from_status',''), '?')} → "
            f"{STATUS_LABEL.get(to_status, '?')}"
        )
        status_lbl.setStyleSheet(f"color:{color};font:bold 12px SimSun;border:none;")
        content.addWidget(status_lbl)

        meta_parts = []
        if log.get('operator'):
            meta_parts.append(f"操作人: {log['operator']}")
        if log.get('time'):
            meta_parts.append(log['time'])
        meta_lbl = QLabel("  ·  ".join(meta_parts))
        meta_lbl.setStyleSheet("color:#64748b;font:11px SimSun;border:none;")
        content.addWidget(meta_lbl)

        if log.get('note'):
            note_lbl = QLabel(f"备注: {log['note']}")
            note_lbl.setStyleSheet("color:#94a3b8;font:11px SimSun;border:none;")
            content.addWidget(note_lbl)

        layout.addLayout(content, 1)
        return frame
