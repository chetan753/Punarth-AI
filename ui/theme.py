"""Colours and Qt stylesheets. The Marketplace uses a bright green-and-white
premium look; the AI Scanner uses a dark 'lab' look so the two feel distinct."""

GREEN = "#16a34a"
GREEN_DARK = "#15803d"
GREEN_DEEP = "#0f5132"
GREEN_50 = "#f0fdf4"
GREEN_100 = "#dcfce7"
GREEN_200 = "#bbf7d0"
INK = "#0f2e1d"
MUTED = "#5b7466"
BORDER = "#e2eee6"
BG = "#f5faf7"
WHITE = "#ffffff"
AMBER = "#d97706"
RED = "#dc2626"
BLUE = "#0284c7"

SCAN_BG = "#0b1512"
SCAN_PANEL = "#12211c"
SCAN_ACCENT = "#34d399"

CONDITION_COLORS = {
    "Like New": ("#065f46", "#d1fae5"), "Excellent": ("#166534", "#dcfce7"), "Good": ("#1e40af", "#dbeafe"),
    "Fair": ("#92400e", "#fef3c7"), "For Parts / Repair": ("#991b1b", "#fee2e2"),
}

ORDER_STATUS_COLORS = {
    "Pending Payment": ("#92400e", "#fef3c7"), "Paid": ("#166534", "#dcfce7"), "Confirmed": ("#1e40af", "#dbeafe"),
    "Shipped": ("#6d28d9", "#ede9fe"), "Out for Delivery": ("#6d28d9", "#ede9fe"),
    "Ready for Pickup": ("#0369a1", "#e0f2fe"), "Delivered": ("#065f46", "#d1fae5"), "Picked Up": ("#065f46", "#d1fae5"),
    "Cancelled": ("#475569", "#f1f5f9"), "Payment Failed": ("#991b1b", "#fee2e2"), "Refund Required": ("#991b1b", "#fee2e2"),
}

APP_QSS = f"""
* {{ font-size: 14px; color: {INK}; }}
QMainWindow, #AppRoot {{ background: {BG}; }}
QToolTip {{ background: {INK}; color: white; border: 0; padding: 6px 8px; border-radius: 6px; }}

/* Sidebar */
#Sidebar {{ background: {GREEN_DEEP}; }}
#Sidebar QLabel {{ color: #d1fae5; }}
#SidebarBrand {{ color: white; font-size: 20px; font-weight: 800; }}
#SidebarRole {{ color: #86efac; font-size: 12px; font-weight: 600; }}
QPushButton[nav="true"] {{ background: transparent; color: #d1fae5; text-align: left; padding: 11px 16px;
    border: 0; border-radius: 10px; font-size: 14px; font-weight: 600; }}
QPushButton[nav="true"]:hover {{ background: rgba(255,255,255,0.08); color: white; }}
QPushButton[nav="true"]:checked {{ background: white; color: {GREEN_DEEP}; }}

/* Buttons */
QPushButton {{ border-radius: 10px; padding: 9px 16px; font-weight: 600; border: 1px solid {BORDER}; background: white; }}
QPushButton:hover {{ border-color: {GREEN}; color: {GREEN_DARK}; }}
QPushButton:disabled {{ color: #9db3a6; background: #f1f5f2; border-color: #e6eee9; }}
QPushButton[kind="primary"] {{ background: {GREEN}; color: white; border: 0; }}
QPushButton[kind="primary"]:hover {{ background: {GREEN_DARK}; color: white; }}
QPushButton[kind="primary"]:disabled {{ background: #9fd3b2; color: white; }}
QPushButton[kind="dark"] {{ background: {INK}; color: white; border: 0; }}
QPushButton[kind="dark"]:hover {{ background: #1c4a31; color: white; }}
QPushButton[kind="soft"] {{ background: {GREEN_50}; color: {GREEN_DARK}; border: 1px solid {GREEN_200}; }}
QPushButton[kind="danger"] {{ background: #fff1f2; color: {RED}; border: 1px solid #fecdd3; }}
QPushButton[kind="danger"]:hover {{ background: #ffe4e6; }}
QPushButton[kind="link"] {{ background: transparent; border: 0; color: {GREEN_DARK}; padding: 4px; }}
QPushButton[kind="link"]:hover {{ color: {GREEN}; }}
QPushButton[kind="chip"] {{ background: white; border: 1px solid {BORDER}; border-radius: 16px; padding: 6px 14px; font-weight: 600; }}
QPushButton[kind="chip"]:checked {{ background: {GREEN}; color: white; border-color: {GREEN}; }}

/* Inputs */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {{ background: white; border: 1px solid {BORDER};
    border-radius: 10px; padding: 8px 10px; selection-background-color: {GREEN_200}; selection-color: {INK}; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1.5px solid {GREEN}; }}
QComboBox::drop-down {{ border: 0; width: 24px; }}
QComboBox QAbstractItemView {{ background: white; border: 1px solid {BORDER}; selection-background-color: {GREEN_100}; selection-color: {INK}; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 18px; height: 18px; }}
QSlider::groove:horizontal {{ height: 6px; background: {GREEN_100}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {GREEN}; width: 18px; margin: -6px 0; border-radius: 9px; }}

QScrollArea {{ border: 0; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #c7dccf; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #c7dccf; border-radius: 4px; min-width: 30px; }}

QTabWidget::pane {{ border: 0; }}
QTabBar::tab {{ background: transparent; padding: 10px 18px; margin-right: 4px; font-weight: 600; color: {MUTED};
    border-bottom: 3px solid transparent; }}
QTabBar::tab:selected {{ color: {GREEN_DARK}; border-bottom: 3px solid {GREEN}; }}
QTabBar::tab:hover {{ color: {INK}; }}

QTableWidget {{ background: white; border: 1px solid {BORDER}; border-radius: 12px; gridline-color: {BORDER};
    selection-background-color: {GREEN_100}; selection-color: {INK}; }}
QHeaderView::section {{ background: {GREEN_50}; border: 0; border-bottom: 1px solid {BORDER}; padding: 8px; font-weight: 700; }}

/* Cards */
QFrame[card="true"] {{ background: white; border: 1px solid {BORDER}; border-radius: 16px; }}
QFrame[card="soft"] {{ background: {GREEN_50}; border: 1px solid {GREEN_100}; border-radius: 16px; }}
QFrame[card="warn"] {{ background: #fffbeb; border: 1px solid #fde68a; border-radius: 14px; }}
QFrame[card="danger"] {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 14px; }}
QFrame[card="ai"] {{ background: #f5f3ff; border: 1px solid #ddd6fe; border-radius: 14px; }}
QLabel[role="h1"] {{ font-size: 28px; font-weight: 800; }}
QLabel[role="h2"] {{ font-size: 20px; font-weight: 800; }}
QLabel[role="h3"] {{ font-size: 16px; font-weight: 700; }}
QLabel[role="muted"] {{ color: {MUTED}; }}
QLabel[role="small"] {{ color: {MUTED}; font-size: 12px; }}
QLabel[role="price"] {{ font-size: 20px; font-weight: 800; color: {INK}; }}
QLabel[role="bigprice"] {{ font-size: 32px; font-weight: 800; color: {INK}; }}

/* Marketplace header */
#MarketHeader {{ background: white; border-bottom: 1px solid {BORDER}; }}
#MarketBrand {{ font-size: 20px; font-weight: 800; color: {GREEN_DEEP}; }}
#MarketSearch {{ border-radius: 20px; padding: 10px 16px; background: {GREEN_50}; border: 1px solid {GREEN_100}; font-size: 14px; }}
QPushButton[kind="mnav"] {{ background: transparent; border: 0; border-radius: 0; padding: 10px 12px;
    color: {MUTED}; font-weight: 700; border-bottom: 3px solid transparent; }}
QPushButton[kind="mnav"]:hover {{ color: {INK}; }}
QPushButton[kind="mnav"]:checked {{ color: {GREEN_DARK}; border-bottom: 3px solid {GREEN}; }}
QPushButton[kind="icon"] {{ background: {GREEN_50}; border: 1px solid {GREEN_100}; border-radius: 20px; padding: 8px 14px; font-size: 15px; }}
QPushButton[kind="icon"]:hover {{ background: {GREEN_100}; }}

/* Scanner (dark lab look) */
#ScannerRoot {{ background: {SCAN_BG}; }}
#ScannerRoot QLabel {{ color: #d6f5e7; }}
#ScannerRoot QLabel[role="muted"], #ScannerRoot QLabel[role="small"] {{ color: #8fb5a4; }}
#ScannerRoot QFrame[card="true"] {{ background: {SCAN_PANEL}; border: 1px solid #1f3a31; }}
#ScannerRoot QFrame[card="ai"] {{ background: #1a1833; border: 1px solid #3b3570; }}
#ScannerRoot QFrame[card="danger"] {{ background: #2a1215; border: 1px solid #7f1d1d; }}
#ScannerRoot QFrame[card="warn"] {{ background: #2a2210; border: 1px solid #78590f; }}
#ScannerRoot QLineEdit, #ScannerRoot QComboBox, #ScannerRoot QSpinBox {{ background: #0f1b17; color: #e6fff4;
    border: 1px solid #24443a; }}
#ScannerRoot QComboBox QAbstractItemView {{ background: #0f1b17; color: #e6fff4; }}
#ScannerRoot QPushButton {{ background: #16302a; color: #d6f5e7; border: 1px solid #24443a; }}
#ScannerRoot QPushButton:hover {{ border-color: {SCAN_ACCENT}; color: white; }}
#ScannerRoot QPushButton[kind="primary"] {{ background: {SCAN_ACCENT}; color: #04120c; border: 0; }}
#ScannerRoot QPushButton[kind="primary"]:hover {{ background: #6ee7b7; }}
#ScannerRoot QPushButton[kind="chip"] {{ background: #0f1b17; color: #d6f5e7; border: 1px solid #24443a; }}
#ScannerRoot QPushButton[kind="chip"]:checked {{ background: {SCAN_ACCENT}; color: #04120c; }}
#ScannerRoot QRadioButton, #ScannerRoot QCheckBox {{ color: #d6f5e7; }}
#ScannerRoot QScrollArea {{ background: transparent; }}

#Toast {{ background: {INK}; color: white; border-radius: 12px; padding: 12px 18px; font-weight: 600; }}
"""
