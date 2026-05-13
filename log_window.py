import sqlite3
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QLabel
)

DB_PATH = "database/logistics.db"


class LogWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("系统日志")
        self.resize(900, 600)

        layout = QVBoxLayout()
        self.setLayout(layout)

        title = QLabel("📋 系统操作日志")
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(4)

        self.table.setHorizontalHeaderLabels([
            "时间",
            "用户",
            "操作",
            "详情"
        ])

        layout.addWidget(self.table)

        self.load_logs()

    def load_logs(self):

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT create_time,
                   username,
                   action,
                   detail
            FROM logs
            ORDER BY id DESC
        """)

        rows = cursor.fetchall()

        conn.close()

        self.table.setRowCount(len(rows))

        for row_index, row_data in enumerate(rows):

            for col_index, value in enumerate(row_data):

                item = QTableWidgetItem(str(value))

                self.table.setItem(
                    row_index,
                    col_index,
                    item
                )