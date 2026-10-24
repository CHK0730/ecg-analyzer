#!/usr/bin/env python3
from __future__ import annotations
"""
ECG Analyzer V5 — Main Application
====================================
Mac App 主程式，使用 PyQt6 + pyqtgraph 建立原生視窗介面
功能：
  - 拖放或選擇 .abf / .edf 檔案
  - 互動式波形瀏覽（縮放、平移）
  - 時間測量工具
  - 時間戳記管理與儲存 (JSON + CSV)
  - R-peak 自動偵測
  - 截圖匯出
"""

import sys
import os
import json
import csv
import struct
import datetime
import traceback
import time
import tempfile
import subprocess

# ── 依賴確認 ──────────────────────────────────────────────────────────────────
def check_deps():
    missing = []
    for pkg in ['PyQt6', 'pyqtgraph', 'numpy', 'scipy', 'openpyxl']:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    return missing

missing = check_deps()
if missing:
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "缺少套件",
            f"請先執行 install.command 安裝以下套件：\n\n" +
            "\n".join(missing))
        sys.exit(1)
    except Exception:
        print(f"[ERROR] 缺少套件：{missing}")
        print("請執行 install.command")
        sys.exit(1)

# ── 正式 import ───────────────────────────────────────────────────────────────
import numpy as np
try:
    import pyabf
    _PYABF_OK = True
except ImportError:
    _PYABF_OK = False
try:
    import bioread
    _BIOREAD_OK = True
except ImportError:
    _BIOREAD_OK = False
from scipy.signal import (find_peaks, butter, filtfilt, iirnotch,
                          sosfiltfilt, sosfreqz)
from scipy.ndimage import uniform_filter1d

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QToolBar, QStatusBar, QFileDialog, QDialog,
    QLabel, QPushButton, QLineEdit, QTextEdit, QGroupBox,
    QListWidget, QListWidgetItem, QMessageBox, QInputDialog,
    QFrame, QScrollArea, QSizePolicy, QComboBox, QCheckBox,
    QProgressBar, QSlider, QSpinBox, QDoubleSpinBox,
    QRadioButton, QButtonGroup, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QGridLayout, QProgressDialog,
    QMenu, QStyle, QStyleOptionGroupBox, QAbstractSpinBox,
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QRect, QRectF, QPoint, QPointF,
    QSettings, QEvent,
)
from PyQt6.QtGui import (
    QAction, QIcon, QFont, QFontMetrics, QColor, QPalette, QDragEnterEvent,
    QDropEvent, QKeySequence, QPixmap, QPainter, QLinearGradient,
    QShortcut,
)

import pyqtgraph as pg
from pyqtgraph import PlotWidget, InfiniteLine, LinearRegionItem

# ── pyqtgraph 全局設定 ────────────────────────────────────────────────────────
pg.setConfigOptions(antialias=True, background='#0d1117', foreground='#e6edf3')

APP_VERSION = 'V5 (+SKNA)'


def build_stamp() -> str:
    """這份程式碼最後修改的時間。

    改完程式要重新啟動才會生效，但從畫面上看不出跑的是哪一版，
    很容易誤以為修正沒有生效。把檔案時間顯示出來就能當場確認。
    """
    try:
        t = os.path.getmtime(os.path.abspath(__file__))
        return datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return '—'

# ══════════════════════════════════════════════════════════════════════════════
# 顏色主題
# ══════════════════════════════════════════════════════════════════════════════
C = {
    'bg':       '#0d1117',
    'panel':    '#161b22',
    'border':   '#30363d',
    'text':     '#e6edf3',
    'dim':      '#8b949e',
    'accent':   '#58a6ff',
    'green':    '#3fb950',
    'yellow':   '#d29922',
    'red':      '#f85149',
    'orange':   '#ffa657',
    'purple':   '#bc8cff',
    'wave':     '#388bfd',
    'wave_alt': '#56d364',
    'ts_color': '#ffa657',
    'meas_a':   '#ff7b72',
    'meas_b':   '#79c0ff',
}

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {C['bg']};
    color: {C['text']};
    font-family: 'SF Mono', 'Menlo', 'Consolas', 'Cascadia Mono', monospace;
    font-size: 12px;
}}
QToolBar {{
    background: {C['panel']};
    border-bottom: 1px solid {C['border']};
    spacing: 4px;
    padding: 4px 8px;
}}
QToolBar QToolButton {{
    background: {C['panel']};
    color: {C['accent']};
    border: 1px solid {C['border']};
    border-radius: 5px;
    padding: 5px 10px;
    font-size: 12px;
}}
QToolBar QToolButton:hover {{
    background: {C['border']};
    color: {C['text']};
}}
QToolBar QToolButton:pressed {{
    background: {C['accent']};
    color: {C['bg']};
}}
QToolBar QToolButton:checked {{
    background: {C['yellow']};
    color: {C['bg']};
    border-color: {C['yellow']};
    font-weight: bold;
}}
QToolBar QToolButton:checked:hover {{
    background: #e6b030;
    color: {C['bg']};
}}
QPushButton {{
    background: {C['panel']};
    color: {C['accent']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
}}
QPushButton:hover {{ background: {C['border']}; color: {C['text']}; }}
QPushButton:pressed {{ background: {C['accent']}; color: {C['bg']}; }}
QPushButton#btn_danger {{
    color: {C['red']};
    border-color: {C['red']};
}}
QPushButton#btn_success {{
    color: {C['green']};
    border-color: {C['green']};
}}
QGroupBox {{
    border: 1px solid {C['border']};
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
    color: {C['dim']};
    font-size: 11px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    top: -2px;
}}
QListWidget {{
    background: {C['panel']};
    border: 1px solid {C['border']};
    border-radius: 6px;
    color: {C['text']};
    font-size: 11px;
}}
QListWidget::item:selected {{
    background: {C['accent']};
    color: {C['bg']};
}}
QListWidget::item:hover {{
    background: {C['border']};
}}
QLabel {{
    color: {C['text']};
}}
QLabel#label_dim {{
    color: {C['dim']};
    font-size: 11px;
}}
QLabel#label_value {{
    color: {C['accent']};
    font-size: 13px;
    font-weight: bold;
}}
QLineEdit, QTextEdit {{
    background: {C['panel']};
    border: 1px solid {C['border']};
    border-radius: 5px;
    color: {C['text']};
    padding: 4px 8px;
    font-size: 12px;
}}
QLineEdit:focus, QTextEdit:focus {{
    border-color: {C['accent']};
}}
QStatusBar {{
    background: {C['panel']};
    color: {C['dim']};
    border-top: 1px solid {C['border']};
    font-size: 11px;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {C['border']};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {C['accent']};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: {C['accent']};
    border-radius: 2px;
}}
QComboBox {{
    background: {C['panel']};
    border: 1px solid {C['border']};
    border-radius: 5px;
    color: {C['text']};
    padding: 4px 8px;
    min-width: 80px;
}}
QComboBox::drop-down {{ border: none; }}
QScrollBar:vertical {{
    background: {C['panel']};
    width: 8px;
}}
QScrollBar::handle:vertical {{
    background: {C['border']};
    border-radius: 4px;
    min-height: 20px;
}}
QSplitter::handle {{
    background: {C['border']};
}}
QFrame#divider {{
    color: {C['border']};
}}
"""

# ══════════════════════════════════════════════════════════════════════════════
# 工具函數
# ══════════════════════════════════════════════════════════════════════════════
def fmt_hms(sec: float) -> str:
    if sec is None or sec < 0:
        return '--:--'
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    if h > 0:
        return f'{h:02d}:{m:02d}:{s:06.3f}'
    return f'{m:02d}:{s:06.3f}'


def fmt_ms(sec: float) -> str:
    return f'{sec * 1000:.2f} ms'


# 開檔對話框要停在哪個資料夾。優先用「目前開著的檔案」所在位置，
# 沒有開檔（起始畫面）時用上一次成功開檔的位置，跨程式重啟也記得。
# 設定儲存名稱沿用舊名，升級到 V5 後仍保留原本記住的資料夾等偏好設定
_SETTINGS_ORG, _SETTINGS_APP = 'ECGAnalyzer', 'ECG Analyzer V4'


def remember_dir(path: str):
    """記下這個檔案所在的資料夾，供下次開檔對話框使用。"""
    try:
        d = os.path.dirname(os.path.abspath(path))
        if d and os.path.isdir(d):
            QSettings(_SETTINGS_ORG, _SETTINGS_APP).setValue('last_dir', d)
    except Exception:
        pass


def last_open_dir(current_path: str | None = None) -> str:
    """開檔對話框的起始資料夾。

    current_path — 目前開著的檔案；有的話就直接用它所在的資料夾，
                   這樣接著開下一個檔不必再從頭找路徑。
    都沒有就回空字串，交給系統決定（維持原生對話框的預設行為）。
    """
    if current_path:
        try:
            d = os.path.dirname(os.path.abspath(current_path))
            if d and os.path.isdir(d):
                return d
        except Exception:
            pass
    try:
        d = QSettings(_SETTINGS_ORG, _SETTINGS_APP).value('last_dir', '')
        if isinstance(d, str) and d and os.path.isdir(d):
            return d
    except Exception:
        pass
    return ''


class WrapLabel(QLabel):
    """會自動換行、而且不會被版面壓扁的說明文字。

    QLabel 開了 wordWrap 之後，minimumSizeHint 只保證得到很小的高度。
    對話框內容一旦比可用高度長，版面就會把這種標籤壓到只剩一兩行：
    文字被切掉，還會跟下一個元件疊在一起。這裡讓它依目前寬度回報真正
    需要的高度（heightForWidth），版面就不會再壓它。
    """

    def __init__(self, text: str = '', parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        sp = self.sizePolicy()
        sp.setHeightForWidth(True)
        sp.setVerticalPolicy(QSizePolicy.Policy.MinimumExpanding)
        self.setSizePolicy(sp)

    def _needed(self, w: int) -> int:
        w = max(1, int(w) - 2)
        flags = int(self.alignment()) | int(Qt.TextFlag.TextWordWrap)
        h = self.fontMetrics().boundingRect(QRect(0, 0, w, 10_000),
                                            flags, self.text()).height()
        m = self.contentsMargins()
        return h + m.top() + m.bottom() + 2

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        return self._needed(w)

    def minimumSizeHint(self) -> QSize:
        w = self.width() or self.minimumWidth() or 320
        return QSize(0, self._needed(w))

    def sizeHint(self) -> QSize:
        w = self.width() or self.minimumWidth() or 400
        return QSize(w, self._needed(w))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.updateGeometry()


class HelpPopup(QFrame):
    """問號圖示旁邊彈出來的說明框。"""

    def __init__(self, text: str):
        super().__init__(None, Qt.WindowType.ToolTip |
                         Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setStyleSheet(
            f'QFrame{{background:{C["panel"]};border:1px solid {C["accent"]};'
            f'border-radius:6px;}}'
            f'QLabel{{color:{C["text"]};font-size:11px;background:transparent;'
            f'border:none;}}')
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 8)
        self.lbl = QLabel(text)
        self.lbl.setWordWrap(True)
        self.lbl.setMinimumWidth(300)
        self.lbl.setMaximumWidth(420)
        v.addWidget(self.lbl)

    def set_text(self, text: str):
        self.lbl.setText(text)
        self.adjustSize()


class HelpBadge(QLabel):
    """標題旁邊的「?」：游標移上去顯示說明，點一下固定，再點一下收起來。

    說明文字不佔版面，需要的時候才叫出來；固定模式是為了讓人可以一邊看
    說明一邊調參數，不會因為滑鼠移開就消失。
    """

    _open: list = []          # 目前開著的說明框，關對話框時要一起收掉

    def __init__(self, text: str, parent=None, size: int = 0):
        super().__init__('?', parent)
        self._text = text
        self._pinned = False
        self._pop: HelpPopup | None = None
        self.set_badge_size(size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip('點一下固定說明')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_badge_size(self, size: int = 0):
        """圓圈大小跟著字體走，才不會在小字時比標題還高、大字時變得很小。"""
        if size <= 0:
            size = max(13, min(20, self.fontMetrics().height()))
        if size % 2 == 0:              # 取奇數，中心才在整數像素上
            size -= 1                  # 往下取，圓圈才不會比標題還高
        self._size = size
        self.setFixedSize(size, size)
        self.update()

    def _paint(self, active: bool):
        self.update()

    def paintEvent(self, ev):
        """自己畫圓圈與問號。

        交給樣式表的 border-radius 畫的話，在不同平台／縮放下會變成方角，
        而且父層的 QLabel 樣式可能蓋掉設定。自己畫最穩，也能做抗鋸齒。
        """
        d = getattr(self, '_size', 15)
        pn = QPainter(self)
        pn.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        col = QColor(C['accent'])
        r = QRectF(0.5, 0.5, d - 1.0, d - 1.0)
        if self._pinned:
            pn.setBrush(col)
            pn.setPen(col)
            pn.drawEllipse(r)
            pn.setPen(QColor(C['bg']))
        else:
            pn.setBrush(Qt.BrushStyle.NoBrush)
            pn.setPen(col)
            pn.drawEllipse(r)
        f = QFont(self.font())
        f.setBold(True)
        f.setPixelSize(max(8, int(d * 0.62)))
        pn.setFont(f)
        pn.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), '?')
        pn.end()

    def set_text(self, text: str):
        self._text = text
        if self._pop is not None:
            self._pop.set_text(text)

    # ── 顯示／隱藏 ──
    def _place(self):
        if self._pop is None:
            self._pop = HelpPopup(self._text)
        self._pop.set_text(self._text)
        g = self.mapToGlobal(QPoint(0, self.height() + 4))
        scr = self.screen().availableGeometry() if self.screen() else None
        x, y = g.x(), g.y()
        if scr is not None:
            x = min(x, scr.right() - self._pop.width() - 8)
            x = max(x, scr.left() + 8)
            if y + self._pop.height() > scr.bottom():
                y = self.mapToGlobal(QPoint(0, 0)).y() - self._pop.height() - 4
        self._pop.move(x, y)

    def _show(self):
        self._place()
        self._pop.show()
        if self not in HelpBadge._open:
            HelpBadge._open.append(self)

    def _hide(self):
        if self._pop is not None:
            self._pop.hide()
        if self in HelpBadge._open:
            HelpBadge._open.remove(self)

    def close_popup(self):
        self._pinned = False
        self._paint(False)
        self._hide()

    @staticmethod
    def close_all():
        for b in list(HelpBadge._open):
            b.close_popup()

    # ── 事件 ──
    def enterEvent(self, ev):
        super().enterEvent(ev)
        if not self._pinned:
            self._show()

    def leaveEvent(self, ev):
        super().leaveEvent(ev)
        if not self._pinned:
            self._hide()

    def mousePressEvent(self, ev):
        self._pinned = not self._pinned
        self._paint(self._pinned)
        if self._pinned:
            self._show()
            self.setToolTip('點一下收起說明')
        else:
            self._hide()
            self.setToolTip('點一下固定說明')
        ev.accept()

    def moveEvent(self, ev):          # 捲動時跟著走
        super().moveEvent(ev)
        if self._pop is not None and self._pop.isVisible():
            self._place()

    def hideEvent(self, ev):
        super().hideEvent(ev)
        self.close_popup()


class HelpGroupBox(QGroupBox):
    """標題旁邊帶一個「?」的群組框。

    說明文字改成隨選顯示，版面就不會被一大段灰字撐開，
    也不會在螢幕不夠高時被擠壓。
    """

    def __init__(self, title: str, help_text: str = '', parent=None):
        super().__init__(title, parent)
        self.badge = HelpBadge(help_text, self) if help_text else None
        if self.badge is not None:
            self.badge.show()
            self._place_badge()

    def _place_badge(self):
        if self.badge is None:
            return
        # 直接跟樣式問「標題實際被畫在哪」。自己用 fontMetrics 估字寬會失準：
        # 標題是粗體、樣式表還有 left/padding，中文粗體的字寬跟一般體差更多，
        # 估出來的位置會偏、垂直也對不準。
        r = None
        self.badge.set_badge_size(
            max(13, min(20, self.fontMetrics().height())))
        try:
            opt = QStyleOptionGroupBox()
            self.initStyleOption(opt)
            r = self.style().subControlRect(
                QStyle.ComplexControl.CC_GroupBox, opt,
                QStyle.SubControl.SC_GroupBoxLabel, self)
        except Exception:
            r = None
        # 標題是粗體，樣式回報的矩形有些平台是用一般體算的，會比實際畫出來
        # 的窄 —— 直接用它就會壓到標題。所以另外用粗體量一次字寬，兩者取大。
        bf = QFont(self.font())
        bf.setBold(True)
        fmb = QFontMetrics(bf)
        # 樣式表：QGroupBox::title{left:10px; padding:0 4px;}
        x_font = 10 + 4 + fmb.horizontalAdvance(self.title()) + 4 + 6
        if r is None or r.width() <= 0:
            x = x_font
            y = (fmb.height() - self.badge.height()) // 2
        else:
            x = max(r.right() + 6, x_font)
            y = r.center().y() - self.badge.height() // 2
        # 標題很長、視窗很窄時不要跑出框外
        x = min(int(x), max(0, self.width() - self.badge.width() - 6))
        self.badge.move(int(x), max(0, int(y)))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._place_badge()

    def setTitle(self, t: str):
        super().setTitle(t)
        self._place_badge()


def unique_path(path: str) -> str:
    """若檔案已存在就加序號：foo.xlsx → foo(2).xlsx → foo(3).xlsx …

    不覆蓋舊結果，也避免舊檔正開在 Excel 裡導致寫入失敗。
    """
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    for i in range(2, 1000):
        cand = f'{stem}({i}){ext}'
        if not os.path.exists(cand):
            return cand
    return f'{stem}({datetime.datetime.now():%H%M%S}){ext}'


def open_in_default_app(path: str):
    """用系統預設程式開啟檔案（.xlsx → Excel）。回傳 (成功, 錯誤訊息)。"""
    try:
        if sys.platform == 'darwin':
            subprocess.Popen(['open', path],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        elif os.name == 'nt':
            os.startfile(path)          # type: ignore[attr-defined]
        else:
            subprocess.Popen(['xdg-open', path],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        return True, ''
    except Exception as ex:
        return False, str(ex)


# ══════════════════════════════════════════════════════════════════════════════
# 資料載入
# ══════════════════════════════════════════════════════════════════════════════
# ── ABF v1 備援解析器 ────────────────────────────────────────────────────────
# pyabf 2.x 對 ABF v1「浮點資料」(nDataFormat = 1) 直接丟出
#   ValueError: Support for float data is not implemented
# 但這種檔案其實最單純：資料區就是一段 float32，不需要任何增益換算。
# 以下自行解析 6144 bytes 的 v1 標頭，讓這類檔案也能開啟。
# （int16 格式也一併支援，換算公式與 pyabf 相同。）
_ABF_V1_OFF = {           # 欄位: (byte offset, struct 格式)
    'fFileVersionNumber':     (4,    '<f'),
    'nOperationMode':         (8,    '<h'),
    'lActualAcqLength':       (10,   '<i'),
    'lActualEpisodes':        (16,   '<i'),
    'lFileStartDate':         (20,   '<i'),
    'lFileStartTime':         (24,   '<i'),
    'lDataSectionPtr':        (40,   '<i'),
    'nDataFormat':            (100,  '<h'),
    'nADCNumChannels':        (120,  '<h'),
    'fADCSampleInterval':     (122,  '<f'),
    'fADCRange':              (244,  '<f'),
    'lADCResolution':         (252,  '<i'),
    'nADCSamplingSeq':        (410,  '<16h'),
    'fADCProgrammableGain':   (730,  '<16f'),
    'fInstrumentScaleFactor': (922,  '<16f'),
    'fInstrumentOffset':      (986,  '<16f'),
    'fSignalGain':            (1050, '<16f'),
    'fSignalOffset':          (1114, '<16f'),
    'nTelegraphEnable':       (4512, '<16h'),
    'fTelegraphAdditGain':    (4576, '<16f'),
}


def _abf_v1_read(path: str) -> dict:
    """直接解析 ABF v1 檔案，回傳 dict（不需 pyabf）。

    回傳欄位：channels(list[np.ndarray])、names、units、fs、
             rec_datetime、protocol、n_ch
    """
    import struct
    with open(path, 'rb') as f:
        head = f.read(6144)
        if len(head) < 6144:
            raise ValueError('ABF 標頭不完整（檔案過小）')
        sig = head[:4]
        if sig not in (b'ABF ', b'ABF2'):
            raise ValueError(f'不是 ABF 檔案（簽章 {sig!r}）')
        if sig == b'ABF2':
            raise ValueError('ABF2 格式請用 pyabf 讀取')

        H = {}
        for k, (off, fmt) in _ABF_V1_OFF.items():
            vals = struct.unpack_from(fmt, head, off)
            H[k] = vals[0] if len(vals) == 1 else list(vals)

        ver      = float(H['fFileVersionNumber'])
        n_ch     = int(H['nADCNumChannels'])
        if n_ch < 1 or n_ch > 16:
            raise ValueError(f'通道數異常：{n_ch}')
        # fADCSampleInterval 是「每個樣本」的間隔 (µs)，需除以通道數
        si_us = float(H['fADCSampleInterval']) * n_ch
        if si_us <= 0:
            raise ValueError('取樣間隔異常')
        fs = 1e6 / si_us

        seq = [int(x) for x in H['nADCSamplingSeq'][:n_ch]]
        # 通道名稱 / 單位（16 × 10 chars / 16 × 8 chars）
        def _strs(off, width, n=16):
            out = []
            for i in range(n):
                raw = head[off + i * width: off + (i + 1) * width]
                out.append(raw.decode('ascii', 'replace').strip() or f'CH{i}')
            return out
        all_names = _strs(442, 10)
        all_units = _strs(602, 8)

        names = [all_names[c] if 0 <= c < 16 else f'CH{c}' for c in seq]
        units = [all_units[c] if 0 <= c < 16 else '' for c in seq]

        # ── 讀取資料區 ──
        total = int(H['lActualAcqLength'])
        if total <= 0:
            raise ValueError('資料長度為 0')
        dfmt = int(H['nDataFormat'])
        dtype = np.dtype('<f4') if dfmt == 1 else np.dtype('<i2')
        f.seek(int(H['lDataSectionPtr']) * 512)
        buf = f.read(total * dtype.itemsize)
        raw = np.frombuffer(buf, dtype=dtype)

    n_per = len(raw) // n_ch
    raw = raw[:n_per * n_ch].reshape(n_per, n_ch)

    channels = []
    for j, adc in enumerate(seq):
        col = np.ascontiguousarray(raw[:, j], dtype=np.float32)
        if dfmt != 1:                       # int16 → 物理量
            gain = 1.0
            for arr in ('fInstrumentScaleFactor', 'fSignalGain',
                        'fADCProgrammableGain'):
                g = float(H[arr][adc]) if 0 <= adc < 16 else 1.0
                if g:
                    gain /= g
            if ver > 1.6 and 0 <= adc < 16 and int(H['nTelegraphEnable'][adc]) == 1:
                g = float(H['fTelegraphAdditGain'][adc])
                if g:
                    gain /= g
            gain *= float(H['fADCRange'])
            res = int(H['lADCResolution'])
            if res:
                gain /= res
            off = (float(H['fInstrumentOffset'][adc])
                   - float(H['fSignalOffset'][adc])) if 0 <= adc < 16 else 0.0
            col = col.astype(np.float64) * gain + off
        channels.append(col)

    # ── 起始時間 ──
    rec_dt = None
    try:
        d, s = int(H['lFileStartDate']), int(H['lFileStartTime'])
        if d < 1000000:                     # 舊版為 YYMMDD
            d += (19000000 if d // 10000 >= 80 else 20000000)
        y, mo, dy = d // 10000, (d // 100) % 100, d % 100
        rec_dt = datetime.datetime(y, mo, dy) + datetime.timedelta(seconds=s)
    except Exception:
        rec_dt = None

    mode = {1: 'event-driven (variable)', 2: 'event-driven (fixed)',
            3: 'gap-free', 4: 'high-speed oscilloscope',
            5: 'episodic stimulation'}.get(int(H['nOperationMode']), '?')
    return {
        'channels': channels, 'names': names, 'units': units,
        'fs': float(fs), 'n_ch': n_ch, 'rec_datetime': rec_dt,
        'protocol': f'ABF v{ver:.2f} · {mode} · '
                    f'{"float32" if dfmt == 1 else "int16"}',
    }


class ABFData:
    def __init__(self, path: str):
        self.path = path
        self.abf = None
        self._fallback = None
        err_pyabf = None
        if _PYABF_OK:
            try:
                self.abf = pyabf.ABF(path)
            except Exception as e:           # 含 float 資料不支援等情形
                err_pyabf = e
                self.abf = None
        if self.abf is not None:
            self.fs = float(self.abf.sampleRate)
            self.n_ch = self.abf.channelCount
            self.ch_names = list(self.abf.adcNames)
            self.ch_units = list(self.abf.adcUnits)
            self._protocol = self.abf.protocol
        else:
            # pyabf 讀不了（或沒安裝）→ 試自行解析 ABF v1
            try:
                self._fallback = _abf_v1_read(path)
            except Exception as e2:
                if not _PYABF_OK:
                    raise ImportError(
                        "開啟 .abf 檔案需要 pyabf 套件。\n"
                        "請執行 install.command 安裝。\n"
                        f"（內建備援解析器亦失敗：{e2}）") from e2
                raise ValueError(
                    f"無法讀取此 .abf 檔案。\npyabf：{err_pyabf}\n"
                    f"內建備援解析器：{e2}") from e2
            fb = self._fallback
            self.fs = fb['fs']
            self.n_ch = fb['n_ch']
            self.ch_names = list(fb['names'])
            self.ch_units = list(fb['units'])
            self._protocol = fb['protocol']
        # .abf 所有通道共用同一取樣率
        self.ch_fs = [float(self.fs)] * self.n_ch
        self.channels: dict[int, np.ndarray] = {}
        self._load()

    def _load(self):
        if self._fallback is not None:
            for i, arr in enumerate(self._fallback['channels']):
                self.channels[i] = arr
            self._fallback['channels'] = None   # 釋放參照
            return
        for i in range(self.n_ch):
            self.abf.setSweep(0, channel=i)
            self.channels[i] = self.abf.sweepY.copy()

    @property
    def rec_datetime(self):
        if self._fallback is not None:
            return self._fallback.get('rec_datetime')
        return getattr(self.abf, 'abfDateTime', None)

    def abs_time(self, rel_sec: float):
        t0 = self.rec_datetime
        if t0 is None:
            return fmt_hms(rel_sec)
        abs_t = t0 + datetime.timedelta(seconds=rel_sec)
        return abs_t.strftime('%H:%M:%S.%f')[:-3]

    def info(self) -> dict:
        rec = self.rec_datetime
        end = (rec + datetime.timedelta(seconds=self.duration)) if rec else None
        return {
            'file':      os.path.basename(self.path),
            'fs':        self.fs,
            'duration':  self.duration,
            'channels':  self.n_ch,
            'protocol':  self._protocol,
            'rec_date':  rec.strftime('%Y-%m-%d') if rec else '—',
            'rec_time':  rec.strftime('%H:%M:%S') if rec else '—',
            'rec_end':   end.strftime('%H:%M:%S') if end else '—',
        }

    def fs_of(self, ch: int) -> float:
        """取得指定通道的取樣率（.abf 各通道相同）。"""
        try:
            return float(self.ch_fs[ch])
        except (IndexError, TypeError):
            return float(self.fs)

    @property
    def duration(self) -> float:
        return len(self.channels[0]) / self.fs_of(0)

    def time_array(self) -> np.ndarray:
        return np.arange(len(self.channels[0])) / self.fs_of(0)

    def segment(self, ch: int, t0: float, t1: float):
        data = self.channels[ch]
        fs = self.fs_of(ch)
        s = max(0, int(t0 * fs))
        e = min(len(data), int(t1 * fs) + 1)
        t = np.arange(s, e) / fs
        return t, data[s:e]


# ══════════════════════════════════════════════════════════════════════════════
# EDF 資料讀取（內建解析器，不需額外套件）
# ══════════════════════════════════════════════════════════════════════════════
class EDFData:
    """
    歐洲資料格式 (EDF / EDF+) 讀取器。
    不需要外部套件，直接解析二進位格式。
    """

    def __init__(self, path: str):
        self.path = path
        self.channels: dict[int, np.ndarray] = {}
        self._rec_datetime = None
        self._parse()

    def _parse(self):
        with open(self.path, 'rb') as f:
            # ── 全域標頭 (256 bytes) ──────────────────────────────────────
            hdr = f.read(256)

            startdate     = hdr[168:176].decode('ascii', errors='replace').strip()  # dd.mm.yy
            starttime     = hdr[176:184].decode('ascii', errors='replace').strip()  # hh.mm.ss
            n_header_bytes= int(hdr[184:192].decode('ascii', errors='replace').strip())
            n_records     = int(hdr[236:244].decode('ascii', errors='replace').strip())
            record_dur    = float(hdr[244:252].decode('ascii', errors='replace').strip())
            n_signals     = int(hdr[252:256].decode('ascii', errors='replace').strip())

            # 解析記錄開始時間
            try:
                dd, mm, yy = map(int, startdate.split('.'))
                hh, mn, ss = map(int, starttime.split('.'))
                year = (2000 + yy) if yy < 85 else (1900 + yy)
                self._rec_datetime = datetime.datetime(year, mm, dd, hh, mn, ss)
            except Exception:
                self._rec_datetime = None

            # ── 訊號標頭 (n_signals × 256 bytes) ─────────────────────────
            sig_hdr = f.read(n_signals * 256)

            def _field(size, ns=n_signals, buf=sig_hdr):
                nonlocal _field_offset
                out = [buf[_field_offset + i*size: _field_offset + i*size + size]
                       .decode('ascii', errors='replace').strip()
                       for i in range(ns)]
                _field_offset += size * ns
                return out

            _field_offset = 0
            labels    = _field(16)
            _field(80)                        # transducer
            phys_dims = _field(8)
            phys_mins = [float(x) for x in _field(8)]
            phys_maxs = [float(x) for x in _field(8)]
            dig_mins  = [int(x)   for x in _field(8)]
            dig_maxs  = [int(x)   for x in _field(8)]
            _field(80)                        # prefilter
            n_samp    = [int(x)   for x in _field(8)]

            # 過濾掉 EDF+ 的 Annotations 通道
            data_idx = [i for i in range(n_signals)
                        if 'EDF Annotations' not in labels[i]]

            if not data_idx:
                raise ValueError("EDF 檔案中找不到資料通道")

            # 整理通道資訊（空白或亂碼的 label 以 CH{n} 替代）
            def _clean_label(lbl, idx):
                cleaned = lbl.strip().replace('\x00', '').replace('?', '')
                return cleaned if cleaned else f'CH{idx}'

            self.ch_names = [_clean_label(labels[i], i) for i in data_idx]
            self.ch_units = [phys_dims[i] if phys_dims[i] else 'mV' for i in data_idx]
            self.n_ch     = len(data_idx)

            # 取樣率：EDF 允許每個通道有不同取樣率，必須逐通道記錄，
            # 否則 5 kHz 通道套用 10 kHz 會讓時間軸壓縮、後半段資料讀不到。
            self.ch_fs = [(n_samp[i] / record_dur) if record_dur > 0 else 1.0
                          for i in data_idx]
            # self.fs 保留為「主要取樣率」（最高者），僅供顯示與相容用途；
            # 任何跟通道有關的計算一律用 fs_of(ch)。
            self.fs = max(self.ch_fs) if self.ch_fs else 1.0
            self.mixed_fs = len(set(self.ch_fs)) > 1

            # ── 校正係數 ──────────────────────────────────────────────────
            gains, offsets_cal = [], []
            for i in data_idx:
                dmin, dmax = dig_mins[i], dig_maxs[i]
                pmin, pmax = phys_mins[i], phys_maxs[i]
                gain = (pmax - pmin) / (dmax - dmin) if (dmax - dmin) != 0 else 1.0
                gains.append(gain)
                offsets_cal.append(pmin - dmin * gain)

            # ── 讀取資料紀錄（一次性，用 numpy 解析加速）────────────────
            total_samp = sum(n_samp)
            raw_bytes  = f.read()

        n_rec_avail = len(raw_bytes) // (total_samp * 2)
        if n_rec_avail == 0:
            raise ValueError("EDF 檔案資料區塊為空")

        raw = np.frombuffer(
            raw_bytes[:n_rec_avail * total_samp * 2],
            dtype='<i2'
        ).reshape(n_rec_avail, total_samp)

        # 拆分各通道並做物理單位換算
        col = 0
        col_map = {}
        for i in range(n_signals):
            col_map[i] = col
            col += n_samp[i]

        for ch_new, (ch_orig, gain, off) in enumerate(zip(data_idx, gains, offsets_cal)):
            c0 = col_map[ch_orig]
            c1 = c0 + n_samp[ch_orig]
            sig_raw = raw[:, c0:c1].flatten().astype(np.float64)
            self.channels[ch_new] = sig_raw * gain + off

    # ── 公用介面（與 ABFData 相同）─────────────────────────────────────────

    @property
    def rec_datetime(self):
        return self._rec_datetime

    def abs_time(self, rel_sec: float) -> str:
        t0 = self._rec_datetime
        if t0 is None:
            return fmt_hms(rel_sec)
        abs_t = t0 + datetime.timedelta(seconds=rel_sec)
        return abs_t.strftime('%H:%M:%S.%f')[:-3]

    def fs_of(self, ch: int) -> float:
        """取得指定通道的取樣率。EDF 各通道可以不同。"""
        try:
            return float(self.ch_fs[ch])
        except (IndexError, TypeError):
            return float(self.fs)

    @property
    def duration(self) -> float:
        if not self.channels:
            return 0.0
        # 各通道長度不同但時間長度相同，取最大值以免截掉尾端
        return max(len(self.channels[i]) / self.fs_of(i)
                   for i in range(self.n_ch))

    def time_array(self) -> np.ndarray:
        return np.arange(len(self.channels[0])) / self.fs_of(0)

    def segment(self, ch: int, t0: float, t1: float):
        data = self.channels[ch]
        fs = self.fs_of(ch)
        s = max(0, int(t0 * fs))
        e = min(len(data), int(t1 * fs) + 1)
        t = np.arange(s, e) / fs
        return t, data[s:e]

    def info(self) -> dict:
        rec = self._rec_datetime
        end = (rec + datetime.timedelta(seconds=self.duration)) if rec else None
        return {
            'file':      os.path.basename(self.path),
            'fs':        self.fs,
            'duration':  self.duration,
            'channels':  self.n_ch,
            'protocol':  'EDF',
            'rec_date':  rec.strftime('%Y-%m-%d') if rec else '—',
            'rec_time':  rec.strftime('%H:%M:%S') if rec else '—',
            'rec_end':   end.strftime('%H:%M:%S') if end else '—',
        }


# ══════════════════════════════════════════════════════════════════════════════
# ACQ 資料讀取（BIOPAC AcqKnowledge，需 bioread 套件）
# ══════════════════════════════════════════════════════════════════════════════
class ACQData:
    """
    BIOPAC AcqKnowledge (.acq) 讀取器。

    直接讀原生檔的好處：
      - 通道名稱不會被 EDF 的 16 字元上限截斷
      - 各通道原始取樣率完整保留（AcqKnowledge 的 frequency divider）
      - 不需要先轉檔，也不會產生轉檔時的降頻複本
    """

    def __init__(self, path: str):
        if not _BIOREAD_OK:
            raise ImportError(
                "開啟 .acq 檔案需要 bioread 套件。\n"
                "請執行 install.command（或 pip3 install bioread）安裝。")
        self.path = path
        self.channels: dict[int, np.ndarray] = {}
        self._rec_datetime = None
        self._parse()

    def _parse(self):
        f = bioread.read(self.path)

        self.file_marks = self._read_markers(f)

        chans = list(f.channels)
        if not chans:
            raise ValueError("ACQ 檔案中找不到資料通道")

        self.n_ch    = len(chans)
        self.ch_names = [(c.name or f'CH{i}').strip() or f'CH{i}'
                         for i, c in enumerate(chans)]
        self.ch_units = [(c.units or 'mV').strip() or 'mV' for c in chans]
        self.ch_fs    = [float(c.samples_per_second) for c in chans]
        self.fs       = max(self.ch_fs) if self.ch_fs else 1.0
        self.mixed_fs = len(set(self.ch_fs)) > 1

        for i, c in enumerate(chans):
            self.channels[i] = np.asarray(c.data, dtype=np.float64)

        # 錄製分段：AcqKnowledge 每次按下暫停再繼續，就會多一個 apnd 標記，
        # 記錄「這一段從第幾個樣本開始、實際幾點幾分開始錄」。暫停期間沒有
        # 存資料，所以檔案裡的連續時間軸跟時鐘時間會越差越多，
        # 必須逐段對齊才能換算出正確的時鐘時間。
        self._segments = self._read_segments(f)

        if self._segments:
            self._rec_datetime = self._segments[0][1]
        else:
            # 沒有分段資訊時退回最早的標記時間（舊行為）
            t0 = self._to_local(getattr(f, 'earliest_marker_created_at', None))
            self._rec_datetime = t0
            if t0 is not None:
                self._segments = [(0.0, t0)]

    @staticmethod
    def _to_local(dt_val):
        """bioread 給的是 timezone-aware UTC，轉成本地時間後去掉 tzinfo，
        讓下游的 datetime 運算跟 ABF/EDF 一致。"""
        if not isinstance(dt_val, datetime.datetime):
            return None
        try:
            if dt_val.tzinfo is not None:
                dt_val = dt_val.astimezone().replace(tzinfo=None)
            return dt_val
        except Exception:
            return None

    def _read_segments(self, f) -> list:
        """回傳 [(相對秒數, 該段開始的本地時間)]，依相對秒數排序。"""
        segs = []
        try:
            markers = list(getattr(f, 'event_markers', None) or [])
        except Exception:
            return segs
        sps = float(getattr(f, 'samples_per_second', 0) or 0) or float(self.fs)
        for m in markers:
            if str(getattr(m, 'type_code', '') or '').lower() != 'apnd':
                continue
            si = getattr(m, 'sample_index', None)
            when = self._to_local(getattr(m, 'date_created_utc', None))
            if si is None or when is None or not sps:
                continue
            segs.append((float(si) / sps, when))
        segs.sort(key=lambda x: x[0])
        return segs

    @staticmethod
    def _read_markers(f) -> list:
        """讀出 AcqKnowledge 在錄製時按下的事件標記。

        回傳 [{'t', 'name', 'kind'}]，格式與 SKNA 時間點位相同，
        可直接餵給 pair_marks_to_intervals()。

        兩種標記要分開看：
          usr1 — 使用者自己按下的標記，就是實驗事件（baseline / stress …）
          apnd — AcqKnowledge 記錄「這裡接續了一段新錄製」的位置，
                 是儀器行為不是實驗事件，這裡不帶入。
        其餘型別（儀器自動插入的各種註記）一併略過。

        配對規則：usr1 依時間排序後，第 1↔2、3↔4… 成對，
        奇數個時最後一個留成未配對的起點。名稱取起點的文字；
        使用者常常只在起點打字、終點留空，所以終點沿用起點的名稱。
        """
        out = []
        try:
            markers = list(getattr(f, 'event_markers', None) or [])
        except Exception:
            return out
        usr = []
        for m in markers:
            if str(getattr(m, 'type_code', '') or '').lower() != 'usr1':
                continue
            t = getattr(m, 'time_index', None)
            if t is None:
                si = getattr(m, 'sample_index', None)
                sps = getattr(f, 'samples_per_second', None)
                if si is None or not sps:
                    continue
                t = float(si) / float(sps)
            usr.append((float(t), str(getattr(m, 'text', '') or '').strip()))
        usr.sort(key=lambda x: x[0])

        for i in range(0, len(usr), 2):
            t_a, name_a = usr[i]
            pair = usr[i + 1] if i + 1 < len(usr) else None
            label = name_a or (pair[1] if pair and pair[1] else '')
            if not label:
                label = f'區段 {i // 2 + 1}'
            out.append({'t': t_a, 'name': label, 'kind': 'start'})
            if pair is not None:
                out.append({'t': pair[0], 'name': label, 'kind': 'end'})
        return out

    # ── 公用介面（與 ABFData / EDFData 相同）─────────────────────────────────

    @property
    def rec_datetime(self):
        return self._rec_datetime

    def _segment_index(self, rel_sec: float) -> int:
        """rel_sec 落在第幾個錄製分段。"""
        idx = 0
        for i, (s_rel, _) in enumerate(self._segments):
            if rel_sec >= s_rel:
                idx = i
            else:
                break
        return idx

    def abs_datetime(self, rel_sec: float):
        """相對秒數 → 實際時鐘時間（依所在分段的開始時間推算）。"""
        if not self._segments:
            return None
        s_rel, s_dt = self._segments[self._segment_index(rel_sec)]
        return s_dt + datetime.timedelta(seconds=rel_sec - s_rel)

    def rel_from_datetime(self, target):
        """實際時鐘時間 → 相對秒數。

        落在暫停期間（兩段之間沒有資料）的時間，對到下一段的開頭。"""
        if not self._segments:
            return None
        segs = self._segments
        idx = 0
        for i, (_, s_dt) in enumerate(segs):
            if target >= s_dt:
                idx = i
        s_rel, s_dt = segs[idx]
        rel = s_rel + (target - s_dt).total_seconds()
        if idx + 1 < len(segs) and rel > segs[idx + 1][0]:
            rel = segs[idx + 1][0]
        return rel

    @property
    def segments(self) -> list:
        return list(self._segments)

    def abs_time(self, rel_sec: float) -> str:
        t = self.abs_datetime(rel_sec)
        if t is None:
            return fmt_hms(rel_sec)
        return t.strftime('%H:%M:%S.%f')[:-3]

    def fs_of(self, ch: int) -> float:
        try:
            return float(self.ch_fs[ch])
        except (IndexError, TypeError):
            return float(self.fs)

    @property
    def duration(self) -> float:
        if not self.channels:
            return 0.0
        return max(len(self.channels[i]) / self.fs_of(i)
                   for i in range(self.n_ch))

    def time_array(self) -> np.ndarray:
        return np.arange(len(self.channels[0])) / self.fs_of(0)

    def segment(self, ch: int, t0: float, t1: float):
        data = self.channels[ch]
        fs = self.fs_of(ch)
        s = max(0, int(t0 * fs))
        e = min(len(data), int(t1 * fs) + 1)
        t = np.arange(s, e) / fs
        return t, data[s:e]

    def info(self) -> dict:
        rec = self._rec_datetime
        end = self.abs_datetime(self.duration) if rec else None
        return {
            'file':      os.path.basename(self.path),
            'fs':        self.fs,
            'duration':  self.duration,
            'channels':  self.n_ch,
            'protocol':  (f'BIOPAC ACQ（{len(self._segments)} 個錄製分段）'
                          if len(self._segments) > 1 else 'BIOPAC ACQ'),
            'rec_date':  rec.strftime('%Y-%m-%d') if rec else '—',
            'rec_time':  rec.strftime('%H:%M:%S') if rec else '—',
            'rec_end':   end.strftime('%H:%M:%S') if end else '—',
        }


# ── 相對秒數 ↔ 時鐘時間 ──────────────────────────────────────────────────────
# ACQ 檔有暫停分段，不能直接用「起始時間 + 秒數」換算，
# 所以統一經過這兩個函式：資料物件有自己的換算方法就用，否則線性推算。

def data_abs_datetime(data, rel_sec: float):
    fn = getattr(data, 'abs_datetime', None)
    if callable(fn):
        return fn(rel_sec)
    t0 = getattr(data, 'rec_datetime', None)
    return (t0 + datetime.timedelta(seconds=rel_sec)) if t0 else None


def data_rel_from_datetime(data, target):
    fn = getattr(data, 'rel_from_datetime', None)
    if callable(fn):
        return fn(target)
    t0 = getattr(data, 'rec_datetime', None)
    return (target - t0).total_seconds() if t0 else None


# ── 工廠函數：依副檔名選擇讀取器 ─────────────────────────────────────────────
SUPPORTED_EXTS = ('.abf', '.edf', '.acq')
FILE_DIALOG_FILTER = ('ECG Files (*.abf *.edf *.acq);;ABF Files (*.abf);;'
                      'EDF Files (*.edf);;BIOPAC ACQ Files (*.acq);;All Files (*)')


def load_ecg_file(path: str):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.edf':
        return EDFData(path)
    elif ext == '.abf':
        return ABFData(path)
    elif ext == '.acq':
        return ACQData(path)
    else:
        raise ValueError(
            f"不支援的檔案格式：{ext}（僅支援 .abf、.edf 和 .acq）")


# ══════════════════════════════════════════════════════════════════════════════
# 濾波器工具函數
# ══════════════════════════════════════════════════════════════════════════════
def apply_notch(y: np.ndarray, fs: float, freq: float) -> np.ndarray:
    if freq <= 0 or fs <= 0:
        return y
    nyq = fs / 2
    if freq >= nyq:
        return y
    b, a = iirnotch(freq / nyq, Q=30.0)
    return filtfilt(b, a, y)


def apply_bandpass(y: np.ndarray, fs: float, lo_hz: float, hi_hz: float) -> np.ndarray:
    nyq = fs / 2
    if nyq <= 0 or lo_hz >= hi_hz:
        return y
    lo = max(lo_hz / nyq, 1e-4)
    hi = min(hi_hz / nyq, 0.9999)
    if lo >= hi:
        return y
    b, a = butter(3, [lo, hi], btype='band')
    return filtfilt(b, a, y)


# ══════════════════════════════════════════════════════════════════════════════
# SKNA（皮膚交感神經活性）分析核心
# ══════════════════════════════════════════════════════════════════════════════
#
# 參考：Su et al., "Sympathetic nerve activity recovery from the skin recording
#       using the modern optimal shrinkage technique",
#       Biomedical Signal Processing and Control 119 (2026) 109710
#
# 本模組實作論文中的「傳統 BPF 法」(rSNA-BPF)：
#     原始 SKNA-I → band-pass → 全波整流 → 移動平均 → 強度指標
#
# 論文指出 BPF 法的主要缺陷是心跳（QRS）諧波會洩漏進通帶，心率越高越嚴重。
# 小鼠（HR 約 400 bpm）尤其明顯：在 500–1500 Hz 帶內，QRS 窗內的振幅可達窗外
# 的 3–5 倍。本軟體的 BPF 模式「不」對訊號做任何 QRS 排除，完整保留全部樣本
# （與文獻傳統作法一致）；若需要去除心電干擾，請改用 S3 分解模式。

SKNA_PRESETS = {
    '500–1500 Hz（高採樣率）': (500.0, 1500.0),
    '500–1000 Hz（文獻傳統值）':     (500.0, 1000.0),
    '300–500 Hz（Holter / 1 kHz）':  (300.0, 500.0),
}

SKNA_DEFAULTS = {
    'src_ch':        None,     # SKNA 來源通道（軌道 2）；None = 尚未設定
    'src_ch2':       None,     # 軌道 3 的來源通道；None = 與軌道 2 相同
    'ecg_ch':        None,     # R-peak 參考通道
    'bp_lo':         500.0,    # 軌道 2 帶通
    'bp_hi':         1000.0,
    'bp_lo2':        500.0,    # 軌道 3 帶通
    'bp_hi2':        1500.0,
    'order':         4,
    'env_ms':        100.0,    # 整流後移動平均窗長 (ms)
    'notch':         0.0,      # 額外工頻陷波（0 = 關閉）
    'rpeak_source':  'auto',   # 'auto' = SKNA 專用偵測；'screen' = 沿用畫面標記
    'method':        'bpf',    # 'bpf' = 傳統帶通；'s3' = 先用 S3 移除心電成分
    'disp1':         'bpf',    # 軌道 2 顯示：'bpf'（Bandpass）或 's3'
    'disp2':         'bpf',    # 軌道 3 顯示：'bpf'（Bandpass）或 's3'
    's3_hp_hz':      1.0,      # S3 前置高通截止 (Hz)
    's3_K':          30,       # S3 非局部中位數鄰居數
    's3_detrend':    True,     # S3 後移除慢速漂移
    'nact_compat':   True,     # 另外輸出 Nerveact 相容的 aSKNA（逐窗單向濾波）
    'nact_win':      10.0,     # Nerveact 相容模式的切窗長度 (s)
}


def peak_decimate(t: np.ndarray, y: np.ndarray, max_pts: int):
    """把長訊號抽稀到約 max_pts 點，每個區塊保留最小值與最大值。

    SKNA 是 500–1500 Hz 的高頻訊號，用單純的等間隔取樣（y[::step]）會
    嚴重混疊，畫出來的振幅比實際小很多、形狀也不對。保留每段的極值才能
    正確反映包絡。
    """
    n = len(y)
    if n <= max_pts or max_pts < 4:
        return t, y
    block = int(np.ceil(n / (max_pts / 2)))
    usable = (n // block) * block
    if usable < block:
        return t, y
    yb = y[:usable].reshape(-1, block)
    tb = t[:usable].reshape(-1, block)
    lo_i = yb.argmin(axis=1)
    hi_i = yb.argmax(axis=1)
    rows = np.arange(yb.shape[0])
    # 依原本的時間順序交錯輸出最小/最大值，線條才不會左右來回跳
    first_is_min = lo_i <= hi_i
    a_i = np.where(first_is_min, lo_i, hi_i)
    b_i = np.where(first_is_min, hi_i, lo_i)
    t_out = np.empty(yb.shape[0] * 2)
    y_out = np.empty(yb.shape[0] * 2)
    t_out[0::2] = tb[rows, a_i]; y_out[0::2] = yb[rows, a_i]
    t_out[1::2] = tb[rows, b_i]; y_out[1::2] = yb[rows, b_i]
    if usable < n:
        t_out = np.append(t_out, t[usable:])
        y_out = np.append(y_out, y[usable:])
    return t_out, y_out


def channel_rails(x: np.ndarray):
    """通道的物理上下極限（放大器滿格的位置）。"""
    fin = np.asarray(x)
    fin = fin[np.isfinite(fin)]
    if fin.size == 0:
        return 0.0, 0.0
    return float(fin.min()), float(fin.max())


def signal_defect_mask(x: np.ndarray, fs: float, rails=None,
                       win_ms: float = 5.0):
    """標出「這段沒有可用訊號」的樣本，分成兩種情形。

    回傳 (sat_mask, flat_mask)：

    sat  — 貼在通道上下極限：放大器被推到滿格，輸出削平成直線，
           那段時間的訊號內容完全遺失。
    flat — 在 win_ms 的窗內完全沒有變化：訊號死掉了。原始通道飽和時，
           由它衍生出來的濾波通道不會停在滿格，而是停在某個定值（例如
           高通後停在 0），光看有沒有貼齊極限是抓不到的，所以要另外判。

    兩者都代表那段資料不能拿來算 aSKNA，也無法做 S3 分解。
    """
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    if n == 0:
        return np.zeros(0, dtype=bool), np.zeros(0, dtype=bool)

    if rails is None:
        lo, hi = channel_rails(x)
    else:
        lo, hi = rails
    tol = max((hi - lo) * 1e-6, 1e-12)
    sat = (x >= hi - tol) | (x <= lo + tol)

    # 局部極差為 0 → 這個窗內訊號一動也沒動。16 位元量化的真實訊號
    # 至少會抖動 1 個 LSB，所以極差完全為 0 是很明確的死訊號指標。
    w = max(2, int(round(win_ms / 1000.0 * fs)))
    if n >= w:
        try:
            from scipy.ndimage import minimum_filter1d, maximum_filter1d
            rng = (maximum_filter1d(x, w, mode='nearest')
                   - minimum_filter1d(x, w, mode='nearest'))
            flat = rng <= 0.0
        except Exception:
            flat = np.zeros(n, dtype=bool)
    else:
        flat = np.zeros(n, dtype=bool)
    return sat, flat


def defect_pct(x: np.ndarray, fs: float, rails=None):
    """回傳 (飽和%, 死訊號%, 兩者聯集%)。"""
    if len(x) == 0:
        return 0.0, 0.0, 0.0
    sat, flat = signal_defect_mask(x, fs, rails)
    return (float(sat.mean() * 100.0), float(flat.mean() * 100.0),
            float((sat | flat).mean() * 100.0))


def channel_defect_report(data, max_samples: int = 1_000_000) -> dict:
    """整個檔案每個通道的訊號缺陷比例，開檔時算一次存起來。

    回傳 {ch: {'sat':%, 'flat':%, 'bad':%, 'rails':(lo,hi)}}

    對長檔案採抽樣估計：飽和與死訊號都是長片段（動輒數秒到數分鐘），
    等間隔抽樣得到的比例是不偏估計，誤差遠小於判讀所需的精度，但可以
    把開檔時間從 1 秒降到 0.1 秒以下。rails（通道極值）一律用完整資料，
    因為極值只要漏抓一個點就會整個判錯。
    """
    out = {}
    for i in range(data.n_ch):
        try:
            x = data.channels[i]
            rails = channel_rails(x)          # 極值必須看全部資料
            fs = data.fs_of(i)
            step = max(1, int(np.ceil(len(x) / max(max_samples, 1000))))
            if step > 1:
                sp, fp, bp = defect_pct(x[::step], fs / step, rails)
            else:
                sp, fp, bp = defect_pct(x, fs, rails)
            out[i] = {'sat': sp, 'flat': fp, 'bad': bp,
                      'rails': rails, 'step': step}
        except Exception:
            out[i] = {'sat': 0.0, 'flat': 0.0, 'bad': 0.0,
                      'rails': (0.0, 0.0), 'step': 1}
    return out


def unit_to_uv(unit: str):
    """回傳 (換算成 µV 的倍率, 顯示用單位字串)。

    無法辨識的單位就不換算，直接沿用原單位，避免出現看似 µV、
    實際上是別種單位的數字。"""
    u = (unit or '').strip().replace('μ', 'u').replace('µ', 'u').lower()
    table = {'v': 1e6, 'mv': 1e3, 'uv': 1.0, 'nv': 1e-3}
    if u in table:
        return table[u], 'µV'
    return 1.0, (unit or '').strip() or 'a.u.'


def skna_effective_band(fs: float, bp_lo: float, bp_hi: float):
    """依 Nyquist 夾住通帶。回傳 (lo, hi, 警告訊息或 None)。"""
    nyq = fs / 2.0
    warn = None
    lo, hi = float(bp_lo), float(bp_hi)
    if hi >= nyq:
        hi = nyq * 0.98
        warn = (f'高截止 {bp_hi:.0f} Hz 超過 Nyquist（fs/2 = {nyq:.0f} Hz），'
                f'已自動降為 {hi:.0f} Hz。')
    if lo >= hi:
        lo = max(1.0, hi * 0.5)
        warn = ((warn or '') +
                f' 低截止過高，已自動降為 {lo:.0f} Hz。').strip()
    return lo, hi, warn


_SOS_CACHE: dict = {}


def _butter_band_sos(order: int, wlo: float, whi: float):
    """帶通 SOS 係數快取：平移時每次重畫都要濾波，係數不必每次重新設計。"""
    k = (order, round(wlo, 9), round(whi, 9))
    sos = _SOS_CACHE.get(k)
    if sos is None:
        if len(_SOS_CACHE) > 64:
            _SOS_CACHE.clear()
        sos = butter(order, [wlo, whi], btype='band', output='sos')
        _SOS_CACHE[k] = sos
    return sos


def skna_band_cfg(cfg: dict, band: int = 1) -> dict:
    """band=1 → 軌道 2 的帶通（bp_lo/bp_hi）；band=2 → 軌道 3（bp_lo2/bp_hi2）。

    回傳的 cfg 一律把帶通放在 bp_lo/bp_hi，下游函式不必知道是哪一軌。
    """
    if band != 2:
        return cfg
    c = dict(cfg)
    c['bp_lo'] = float(cfg.get('bp_lo2', 500.0))
    c['bp_hi'] = float(cfg.get('bp_hi2', 1500.0))
    if cfg.get('src_ch2') is not None:
        c['src_ch'] = cfg['src_ch2']
    return c


def skna_tracks_differ(cfg: dict) -> bool:
    """軌道 2 與軌道 3 是否用不同的來源通道。"""
    s1, s2 = cfg.get('src_ch'), cfg.get('src_ch2')
    return s1 is not None and s2 is not None and s1 != s2


def skna_band_label(cfg: dict, band: int = 1) -> str:
    """欄位名稱用的軌道標示：帶通範圍；兩軌來源通道不同時前面加上通道。"""
    c = skna_band_cfg(cfg, band)
    b = f"{float(c.get('bp_lo', 500.0)):.0f}–{float(c.get('bp_hi', 1000.0)):.0f}"
    if skna_tracks_differ(cfg):
        b = f"CH{c['src_ch']} {b}"
    return b


def compute_skna(y: np.ndarray, fs: float, bp_lo: float = 500.0,
                 bp_hi: float = 1500.0, order: int = 4,
                 env_ms: float = 100.0, notch: float = 0.0,
                 bandpass: bool = True):
    """對一段訊號做 SKNA 處理。

    回傳 (rsna, env)：
      rsna — 零相位帶通後的訊號（論文中的 rSNA-BPF）
      env  — |rsna| 的移動平均包絡（類似 microneurography 的積分神經圖）

    bandpass=False 時不做帶通，直接把輸入當成 rSNA。用在 S3 的輸出：
    S3 分解出來的就已經是去除心電成分的 SKNA，不再套帶通。
    """
    y = np.asarray(y, dtype=np.float64)
    if not bandpass:
        if len(y) == 0 or fs <= 0:
            return np.zeros_like(y), np.zeros_like(y)
        if notch and notch > 0 and len(y) >= 16:
            y = apply_notch(y, fs, notch)
        n_env = max(1, int(round(env_ms / 1000.0 * fs)))
        env = uniform_filter1d(np.abs(y), size=n_env, mode='nearest')
        return y, env
    return _compute_skna_bpf(y, fs, bp_lo, bp_hi, order, env_ms, notch)


def _compute_skna_bpf(y, fs, bp_lo, bp_hi, order, env_ms, notch):
    """compute_skna 的帶通版本（傳統 rSNA-BPF）。

    用 SOS 形式的 Butterworth：在 10 kHz 取樣下 500/5000 = 0.1 這種很小的
    正規化頻率，傳統 (b, a) 係數在 4 階以上會數值不穩定產生假振盪，
    second-order sections 則不會。
    """
    y = np.asarray(y, dtype=np.float64)
    if len(y) < 16 or fs <= 0:
        return np.zeros_like(y), np.zeros_like(y)

    if notch and notch > 0:
        y = apply_notch(y, fs, notch)

    lo, hi, _ = skna_effective_band(fs, bp_lo, bp_hi)
    nyq = fs / 2.0
    sos = _butter_band_sos(int(order), lo / nyq, hi / nyq)

    # sosfiltfilt 需要足夠長度做邊緣延拓，太短就退回單向濾波
    padlen = 3 * (2 * len(sos) + 1)
    if len(y) > padlen:
        rsna = sosfiltfilt(sos, y)
    else:
        from scipy.signal import sosfilt
        rsna = sosfilt(sos, y)

    n_env = max(1, int(round(env_ms / 1000.0 * fs)))
    env = uniform_filter1d(np.abs(rsna), size=n_env, mode='nearest')
    return rsna, env


def skna_segment(data, ch: int, t0: float, t1: float, cfg: dict,
                 pad_sec: float = 0.25, sig=None, bandpass=None):
    """取出 [t0, t1] 的 SKNA。

    實際濾波時左右各多取 pad_sec 秒再裁掉，避免濾波器邊緣暫態污染
    區間頭尾的數值（尤其影響短區間的 aSKNA）。

    sig 若有給，就用它取代原始通道資料（用來餵入 S3 分解後、已經不含
    心電成分的訊號），取樣率仍沿用該通道的。S3 的輸出本身就是 SKNA，
    所以給了 sig 時預設不再帶通（bandpass=None → 依 sig 自動決定）。
    回傳 (t, rsna, env)。
    """
    if bandpass is None:
        bandpass = sig is None
    fs = data.fs_of(ch)
    full = data.channels[ch] if sig is None else np.asarray(sig)
    n = len(full)
    s = max(0, int(t0 * fs))
    e = min(n, int(t1 * fs) + 1)
    if e <= s:
        empty = np.array([], dtype=np.float64)
        return empty, empty.copy(), empty.copy()

    pad = int(pad_sec * fs)
    sp = max(0, s - pad)
    ep = min(n, e + pad)

    rsna_p, env_p = compute_skna(
        full[sp:ep], fs,
        bp_lo=cfg.get('bp_lo', 500.0), bp_hi=cfg.get('bp_hi', 1500.0),
        order=cfg.get('order', 4), env_ms=cfg.get('env_ms', 100.0),
        notch=cfg.get('notch', 0.0), bandpass=bandpass)

    a = s - sp
    b = a + (e - s)
    t = np.arange(s, e) / fs
    return t, rsna_p[a:b], env_p[a:b]


def skna_metrics(rsna: np.ndarray, fs: float, scale: float = 1.0) -> dict:
    """由 rSNA 計算強度指標（使用區間內全部樣本，不排除任何樣本）。

    scale — 換算成 µV 的倍率

    aSKNA — 平均整流振幅，文獻上最常用的交感活性指標
    iSKNA — 整流訊號的 L1 norm（論文用的 Riemann sum）
            ＝ aSKNA × 區間總長，區間之間可互相比較。
    """
    if rsna is None or len(rsna) == 0 or fs <= 0:
        return {}
    s = np.asarray(rsna, dtype=np.float64) * scale
    x = np.abs(s)
    total_sec = len(x) / fs
    a_skna = float(x.mean())
    return {
        'valid':  True,
        'aSKNA':  a_skna,
        'iSKNA':  a_skna * total_sec,          # µV·s
        'RMS':    float(np.sqrt(np.mean(s ** 2))),
        'peak':   float(x.max()),
        'SD':     float(s.std(ddof=0)),
        'n_sec':  total_sec,
        'n_used': int(len(x)),
    }


def skna_nerveact_compat(data, ch: int, t0: float, t1: float, cfg: dict):
    """Nerveact 相容的 rSNA（只用來和 Nerveact 的數值對照）。

    由 HFD2-1／4／5 的原始資料與 Nerveact 輸出反推（600 個窗格逐窗重現，
    誤差 < 0.001 µV，即 Nerveact 輸出的小數第三位捨入）：
      1. 從區間起點依 nact_win（預設 10 s）切窗
      2. 每一窗「各自」用 Butterworth 帶通單向濾波（sosfilt），從零狀態開始
      3. 全波整流後取平均 → aSKNA

    與 _compute_skna_bpf 的差別：
      • 每窗起點的直流電位等於一個階躍輸入，會激起濾波器暫態並被算進
        aSKNA（約每 10 mV 直流偏移 +0.45 µV）；完全飽和的窗格會得到
        0.450（500–1000 Hz）／0.429（500–1500 Hz）而不是 0。
      • 單向濾波的 −3 dB 通帶就是設定值，零相位（sosfiltfilt）會把通帶
        收窄，所以本函式的數值約高 6–10%。
    不套用工頻陷波、不做前後延伸。回傳 (rsna, 窗數)。
    """
    from scipy.signal import sosfilt
    fs = data.fs_of(ch)
    full = data.channels[ch]
    n = len(full)
    s = max(0, int(round(t0 * fs)))
    e = min(n, int(round(t1 * fs)))
    if e - s < 16 or fs <= 0:
        return np.zeros(0), 0
    lo, hi, _ = skna_effective_band(fs, cfg.get('bp_lo', 500.0),
                                    cfg.get('bp_hi', 1500.0))
    nyq = fs / 2.0
    sos = butter(int(cfg.get('order', 4)), [lo / nyq, hi / nyq],
                 btype='band', output='sos')
    L = max(16, int(round(float(cfg.get('nact_win', 10.0)) * fs)))
    parts = []
    for a in range(s, e, L):
        b = min(e, a + L)
        if b - a < 16:          # 尾端不到 16 個樣本，濾波沒有意義
            break
        parts.append(sosfilt(sos, np.asarray(full[a:b], dtype=np.float64)))
    if not parts:
        return np.zeros(0), 0
    return np.concatenate(parts), len(parts)


def estimate_rr_period(energy: np.ndarray, fs: float,
                       rr_min: float = 0.04, rr_max: float = 3.0):
    """用自相關估計心動週期（秒）。找不到就回傳 None。

    這樣做的目的是讓 R-peak 偵測能自動適應物種：人類 RR 約 0.6–1.2 s，
    小鼠只有 0.09–0.2 s。固定的 refractory period 在小鼠身上會漏抓，
    固定的門檻在雜訊大的訊號上會誤抓 T 波，因此先估出週期再據此設定。
    """
    n = len(energy)
    if n < int(rr_max * fs) or fs <= 0:
        return None
    x = energy - energy.mean()
    # 用 FFT 算自相關，長訊號才不會慢
    nfft = 1 << int(np.ceil(np.log2(2 * n)))
    ac = np.fft.irfft(np.abs(np.fft.rfft(x, nfft)) ** 2)[:n]
    if ac[0] <= 0:
        return None
    ac /= ac[0]
    lo = max(1, int(rr_min * fs))
    hi = min(n - 1, int(rr_max * fs))
    if hi <= lo + 2:
        return None
    seg = ac[lo:hi]
    gmax = float(seg.max())
    if gmax < 0.1:            # 週期性太弱，判定為不可靠
        return None

    # 取「第一個」夠顯著的自相關局部極大，而不是取全域最大值。
    #
    # 自相關在真實週期 P 的整數倍（2P、3P…）也會有很高的峰，訊號越規律
    # 越明顯，全域最大值有時就落在 2P 上。若拿 2P 當週期，之後算出來的
    # 不應期會比真實 RR 還長，find_peaks 每隔一拍才抓到一個，心率直接
    # 少一半（實測在小鼠資料上會把 464 bpm 讀成 233 bpm）。
    # 基頻一定是最小的那個顯著峰，所以改取第一個。
    cand, _ = find_peaks(seg, height=0.6 * gmax)
    if len(cand) > 0:
        best = lo + int(cand[0])
    else:
        best = lo + int(np.argmax(seg))
    return best / fs


def detect_rpeaks_robust(y: np.ndarray, fs: float, notch: float = 0.0):
    """給 SKNA 分析（心率統計與 S3 對齊）用的 R-peak 偵測。

    跟 detect_r_peaks_and_stats() 分開的理由：後者是為人類心率調的，在
    小鼠（HR 約 400 bpm）上會把 T 波也當成 R 波，數量多出將近一倍。
    S3 若用到這種結果，心跳矩陣會對不齊，心率也會算成兩倍。

    流程（Pan–Tompkins 精神的簡化版，但門檻與不應期都由資料自己決定）：
      1. 帶通 → 微分 → 平方 → 移動積分，做出 QRS 能量訊號
      2. 自相關估計心動週期（取第一個顯著峰，避免抓到 2 倍週期），
         據此設定最小峰間距（0.55 × RR）
      3. 以能量的高分位數當門檻抓峰
      4. 依振幅剔除明顯偏小的峰（多半是 T 波或雜訊）
      5. 回到原始訊號在鄰域內精修峰值位置

    回傳絕對樣本索引（相對於傳入的 y）。
    """
    y = np.asarray(y, dtype=np.float64)
    n = len(y)
    if n < int(0.5 * fs) or fs <= 0:
        return np.array([], dtype=int)

    if notch and notch > 0:
        y = apply_notch(y, fs, notch)

    nyq = fs / 2.0
    lo = 10.0 / nyq
    hi = min(200.0, nyq * 0.9) / nyq
    if lo >= hi:
        filt = y - np.median(y)
    else:
        sos = butter(3, [lo, hi], btype='band', output='sos')
        filt = sosfiltfilt(sos, y) if n > 40 else y - np.median(y)

    # QRS 能量：微分 → 平方 → 移動積分
    deriv = np.diff(filt, prepend=filt[0])
    energy = deriv ** 2
    win = max(1, int(round(0.010 * fs)))       # 10 ms 積分窗
    energy = uniform_filter1d(energy, size=win, mode='nearest')

    rr_est = estimate_rr_period(energy, fs)
    if rr_est is None:
        rr_est = 0.8 if fs < 3000 else 0.8      # 沒把握時用人類的預設值
    min_dist = max(1, int(round(0.55 * rr_est * fs)))

    thr = np.percentile(energy, 95) * 0.25
    if thr <= 0:
        thr = float(energy.mean()) or 1e-12
    pk, _ = find_peaks(energy, height=thr, distance=min_dist)
    if len(pk) == 0:
        return np.array([], dtype=int)

    # 剔除明顯偏小的峰：以偵測到的峰能量中位數為基準
    amp = energy[pk]
    keep = amp >= 0.30 * np.median(amp)
    pk = pk[keep]
    if len(pk) == 0:
        return np.array([], dtype=int)

    # 回原始訊號精修位置（在 ±25% RR 的鄰域內找絕對值最大點）
    half = max(1, int(round(0.25 * rr_est * fs)))
    half = min(half, max(1, int(0.02 * fs)))
    base = np.median(y)
    refined = []
    for i in pk:
        a = max(0, i - half)
        b = min(n, i + half + 1)
        if b > a:
            refined.append(a + int(np.argmax(np.abs(y[a:b] - base))))
    pk = np.unique(np.asarray(refined, dtype=int))

    # 再做一次不應期檢查（精修後可能有兩個峰靠得太近）
    if len(pk) > 1:
        out = [pk[0]]
        for i in pk[1:]:
            if i - out[-1] >= min_dist * 0.8:
                out.append(i)
            elif np.abs(y[i] - base) > np.abs(y[out[-1]] - base):
                out[-1] = i
        pk = np.asarray(out, dtype=int)
    return pk


def skna_rpeak_times(data, cfg: dict, t0: float, t1: float,
                     cached_peaks=None, cached_ch: int | None = None):
    """取得 [t0, t1] 內的 R-peak 絕對時間（秒）。回傳 (times, 來源說明)。

    預設用 SKNA 專用的 detect_rpeaks_robust()，而不是畫面上「偵測
    R-peaks (P)」留下的標記。原因是主畫面那個偵測器是為人類心率調的，
    在高心率（例如小鼠）下峰值位置會抖得很厲害，S3 分解與心率統計用它
    定位就會抓錯地方。若你已經在畫面上人工校正過峰值、想沿用，可以在
    SKNA 設定裡把來源改成「畫面上的 R-peak 標記」。
    """
    pad = 0.5
    if cfg.get('rpeak_source') == 'screen' and cached_peaks is not None \
            and len(cached_peaks) > 0 and cached_ch is not None:
        fs_c = data.fs_of(cached_ch)
        t = np.asarray(cached_peaks, dtype=float) / fs_c
        sel = t[(t >= t0 - pad) & (t <= t1 + pad)]
        if len(sel) >= 2:
            return sel, f'畫面上的 R-peak 標記（CH{cached_ch}）'

    ecg_ch = cfg.get('ecg_ch')
    if ecg_ch is None:
        return np.array([]), '無（未指定 ECG 參考通道）'

    fs_e = data.fs_of(ecg_ch)
    full = data.channels[ecg_ch]
    s = max(0, int((t0 - pad) * fs_e))
    e = min(len(full), int((t1 + pad) * fs_e) + 1)
    if e - s < int(0.5 * fs_e):
        return np.array([]), '無（區間太短）'
    pk = detect_rpeaks_robust(full[s:e], fs_e, notch=cfg.get('notch', 0.0))
    times = (s + pk) / fs_e
    return times, f'自動偵測（CH{ecg_ch}: {data.ch_names[ecg_ch]}）'


def analyze_skna_interval(data, cfg: dict, t0: float, t1: float,
                          rpeak_times=None, s3_sig=None):
    """分析單一時間區間。

    回傳的 dict 中最多有兩組指標，方便互相對照：
      all — 傳統 BPF，使用區間內全部樣本（含 QRS，不做任何排除）
      s3  — S3 移除心電成分後的訊號直接計算（不再帶通）
    """
    ch = cfg['src_ch']
    fs = data.fs_of(ch)
    scale, unit_lbl = unit_to_uv(data.ch_units[ch])

    _t, rsna, _env = skna_segment(data, ch, t0, t1, cfg)
    if len(rsna) == 0:
        return {'ok': False, 'reason': '此區間沒有資料'}

    # 飽和要看「原始」訊號，不能看帶通後的：帶通會把削平的直流段濾掉，
    # 看起來就正常了，飽和的痕跡反而消失
    _tr, raw_seg = data.segment(ch, t0, t1)
    rep_ = getattr(data, '_defect_report', None) or {}
    rails = rep_.get(ch, {}).get('rails')
    if len(raw_seg):
        sat_pct, flat_pct, bad_pct = defect_pct(raw_seg, fs, rails)
    else:
        sat_pct = flat_pct = bad_pct = 0.0

    m_all = skna_metrics(rsna, fs, scale)

    # 軌道 3 的帶通（第二組 BPF）
    cfg2 = skna_band_cfg(cfg, 2)
    ch2 = cfg2['src_ch']
    fs2 = data.fs_of(ch2)
    scale2, _u2 = unit_to_uv(data.ch_units[ch2])
    _t2, rsna2, _e2 = skna_segment(data, ch2, t0, t1, cfg2)
    m_all2 = skna_metrics(rsna2, fs2, scale2) if len(rsna2) else {}
    bad_pct2 = bad_pct
    if ch2 != ch:
        _tr2, raw2 = data.segment(ch2, t0, t1)
        if len(raw2):
            _s2, _f2, bad_pct2 = defect_pct(
                raw2, fs2, rep_.get(ch2, {}).get('rails'))

    m_s3 = {}
    if s3_sig is not None:
        _t3, rsna3, _e3 = skna_segment(data, ch, t0, t1, cfg, sig=s3_sig)
        if len(rsna3):
            m_s3 = skna_metrics(rsna3, fs, scale)

    m_nact = {}
    if cfg.get('nact_compat'):
        rsna_n, n_win = skna_nerveact_compat(data, ch, t0, t1, cfg)
        if len(rsna_n):
            m_nact = skna_metrics(rsna_n, fs, scale)
            m_nact['n_win'] = n_win
    m_nact2 = {}
    if cfg.get('nact_compat'):
        rsna_n2, n_win2 = skna_nerveact_compat(data, ch2, t0, t1, cfg2)
        if len(rsna_n2):
            m_nact2 = skna_metrics(rsna_n2, fs2, scale2)
            m_nact2['n_win'] = n_win2

    hr = np.nan
    rr_cv = np.nan
    n_beat = 0
    if rpeak_times is not None and len(rpeak_times) >= 2:
        rt = np.asarray(rpeak_times, dtype=float)
        rt = rt[(rt >= t0) & (rt <= t1)]
        n_beat = len(rt)
        if len(rt) >= 2:
            rr = np.diff(rt)
            rr = rr[(rr > 0.04) & (rr < 3.0)]
            if len(rr):
                hr = 60.0 / float(np.median(rr))
                if np.mean(rr) > 0:
                    rr_cv = float(np.std(rr) / np.mean(rr) * 100.0)

    # ── 訊號品質提示 ──
    # 目的不是自動剔除資料，而是把「這段可能不能用」標出來讓你自己判斷。
    # 錄製開頭、電極接觸不良、動物掙扎等等都會產生這類段落，若不注意
    # 直接拿去算平均，一段雜訊就能把整組數據帶偏。
    flags = []
    if sat_pct >= 1.0:
        flags.append(f'訊號飽和 {sat_pct:.0f}%')
    elif flat_pct >= 1.0:
        flags.append(f'訊號無變化 {flat_pct:.0f}%')
    if not np.isfinite(hr):
        flags.append('無 R-peak')
    else:
        if hr < 150 or hr > 900:
            flags.append(f'心率異常({hr:.0f})')
        if np.isfinite(rr_cv) and rr_cv > 25:
            flags.append(f'RR 不穩(CV {rr_cv:.0f}%)')
    if ch2 != ch and bad_pct2 >= 1.0:
        flags.append(f'軌道 3 訊號無效 {bad_pct2:.0f}%')
    if m_all.get('valid') and m_all.get('peak', 0) > 0:
        crest = m_all['peak'] / max(m_all['aSKNA'], 1e-12)
        if crest > 60:
            flags.append('疑似突波雜訊')
    # ACQ 暫停後續錄的接縫：前後兩段在時間上不連續，區間跨過去的話
    # 等於把兩段不相干的訊號接在一起算
    for s_rel, _dt in (getattr(data, 'segments', None) or [])[1:]:
        if t0 < s_rel < t1:
            flags.append('跨錄製暫停')
            break

    return {
        'ok': True, 't0': t0, 't1': t1, 'dur': t1 - t0,
        'unit': unit_lbl, 'fs': fs,
        'all': m_all, 's3': m_s3, 'nact': m_nact,
        'all2': m_all2, 'nact2': m_nact2, 'bad_pct2': bad_pct2,
        'band1': skna_band_label(cfg, 1), 'band2': skna_band_label(cfg, 2),
        'hr': hr, 'rr_cv': rr_cv, 'n_beat': n_beat,
        'sat_pct': sat_pct, 'flat_pct': flat_pct, 'bad_pct': bad_pct,
        'flags': flags,
    }


def guess_skna_channels(data):
    """依通道名稱與取樣率猜測預設的 SKNA 來源通道與 ECG 參考通道。

    只是給一個合理起點，使用者仍可在設定對話框改。挑選原則：
      - SKNA 來源：取樣率最高（頻寬才夠做 500–1500 Hz），名稱含 skna/
        tungsten/sna/nerve 者優先；名稱含 'raw' 再加分，因為已經被儀器
        濾過的通道再濾一次會疊上來路不明的第二層濾波器。
      - ECG 參考：名稱含 ecg/ekg 者優先。
    """
    n = data.n_ch
    if n == 0:
        return 0, 0
    names = [(data.ch_names[i] or '').lower() for i in range(n)]
    fss   = [data.fs_of(i) for i in range(n)]
    fs_max = max(fss) if fss else 0.0

    # 訊號缺陷（飽和／死訊號）嚴重的通道不適合當分析來源，先算出來扣分
    rep_ = getattr(data, '_defect_report', None) or channel_defect_report(data)
    sat = {i: rep_.get(i, {}).get('bad', 0.0) for i in range(n)}

    def src_score(i):
        s_ = 0.0
        if fss[i] >= fs_max - 1e-9:
            s_ += 100
        s_ += fss[i] / 1e6
        # 飽和每 1% 扣 3 分：輕微的（<2%）幾乎不影響排序，
        # 但像 17% 這種就會被排到明顯較差的通道後面
        s_ -= min(sat.get(i, 0.0), 60.0) * 3.0
        for kw, w in (('skna', 40), ('tungsten', 40), ('sna', 20),
                      ('nerve', 30), ('needle', 10)):
            if kw in names[i]:
                s_ += w
        if 'raw' in names[i]:
            s_ += 25
        if 'ecg' in names[i] or 'ekg' in names[i]:
            s_ -= 15
        return s_

    def ecg_score(i):
        s_ = 0.0
        s_ -= min(sat.get(i, 0.0), 60.0) * 3.0
        for kw, w in (('ecg', 50), ('ekg', 50)):
            if kw in names[i]:
                s_ += w
        if 'skna' in names[i] or 'sna' in names[i]:
            s_ -= 40
        if 'raw' in names[i]:
            s_ += 10
        s_ += fss[i] / 1e6
        return s_

    src = max(range(n), key=src_score)
    ecg = max(range(n), key=ecg_score)
    return src, ecg


# ══════════════════════════════════════════════════════════════════════════════
# R-peak 偵測（共用邏輯，供背景執行緒與測量範圍 BPM 共用）
# ══════════════════════════════════════════════════════════════════════════════
def detect_r_peaks_and_stats(data: np.ndarray, fs: float,
                              notch_freq: float = 0.0,
                              bp_enabled: bool = False,
                              bp_lo: float = 1.0, bp_hi: float = 150.0):
    """偵測 R-peak 並計算 RR/HR 統計。回傳 (peaks, stats)；資料不足時 stats 為 {}。"""
    # notch filter（先做，避免電源雜訊干擾），保留一份供之後定位精修使用
    raw = data
    if notch_freq > 0:
        raw = apply_notch(raw, fs, notch_freq)

    # bandpass: use user-defined range if enabled, else default 5–150 Hz
    # （此頻帶濾波僅用來讓「粗略」峰值偵測更穩定；帶通會把很尖銳的
    #   needle 訊號抹平，因此實際峰值位置之後會在原始訊號中重新精修）
    lo_hz = bp_lo if bp_enabled else 5.0
    hi_hz = bp_hi if bp_enabled else 150.0
    nyq = fs / 2
    lo = max(lo_hz / nyq, 1e-4)
    hi = min(hi_hz / nyq, 0.98)
    if lo < hi:
        b, a = butter(3, [lo, hi], btype='band')
        filt = filtfilt(b, a, raw)
    else:
        filt = raw.copy()

    thresh = np.percentile(filt, 88)
    flipped = False
    if thresh <= 0:
        filt = -filt
        flipped = True
        thresh = np.percentile(filt, 88)

    # min_dist 只是用來避免同一個 QRS/spike 的抖動或 overshoot 被誤算成
    # 兩拍，跟「兩次真正心跳最少要間隔多久」無關，所以只需比單一個尖峰
    # 波形本身的寬度稍大即可。用太大的值（例如假設最快心跳 460 bpm）在
    # 心跳很快、很規律的資料上，會讓 find_peaks 自己的 distance 限制
    # 把兩個都合法、只是間距較近的真實峰值直接刪掉一個。這裡改用較保守
    # 的下限（約對應 1000 bpm），只防止單一尖峰內的雜訊重複偵測。
    min_dist = max(5, int(fs * 0.06))
    peaks, _ = find_peaks(filt, height=thresh * 0.65, distance=min_dist)

    # ── 排除較弱的假峰值（例如 T 波／隆起波形）────────────────────────────
    # 縮小 min_dist 後，QRS 之間較弱的隆起波形有機會因為離兩側真正的
    # R-peak 都超過 min_dist，而被單獨偵測成一個多餘的峰值。真正的
    # R-peak 彼此振幅通常相當接近，明顯比雜訊/T 波矮很多，所以用候選
    # 峰值本身振幅的中位數做一個相對門檻，把明顯偏矮的候選點濾掉。
    if len(peaks) >= 3:
        heights = filt[peaks]
        med_h = np.median(heights)
        peaks = peaks[heights >= med_h * 0.5]

    # ── 峰值定位精修 ──────────────────────────────────────────────────────
    # 帶通濾波後找到的位置只是「粗略」位置，尖銳的 needle 訊號常被濾波
    # 平滑掉，導致峰值誤定位到旁邊較寬的隆起波形。這裡在「原始（僅濾除
    # 電源雜訊，未經頻帶平滑）」訊號中，於每個粗略峰值自己的區間內
    # （以與左右相鄰峰值的中點為界，避免誤跨到別拍）尋找振幅真正最大的
    # 樣本點，把峰值精確定位到該點上。
    if len(peaks) > 0:
        sign = -1.0 if flipped else 1.0
        n = len(raw)
        # 第一拍／最後一拍沒有左右相鄰峰值可以取中點，改用資料本身估計
        # 出的典型拍間距（其餘峰值間距的中位數）當作搜尋範圍，找不到就
        # 退回較大的固定值，避免範圍太小而搜尋不到真正的尖峰。
        if len(peaks) > 1:
            edge_span = max(min_dist, int(np.median(np.diff(peaks)) * 0.9))
        else:
            edge_span = max(min_dist, int(fs * 0.2))
        refined = []
        for i, p in enumerate(peaks):
            lo_b = (peaks[i - 1] + p) // 2 if i > 0 else max(0, p - edge_span)
            hi_b = (p + peaks[i + 1]) // 2 if i < len(peaks) - 1 else min(n - 1, p + edge_span)
            lo_b = max(0, min(int(lo_b), n - 1))
            hi_b = max(lo_b + 1, min(int(hi_b) + 1, n))
            local = raw[lo_b:hi_b] * sign
            refined.append(lo_b + int(np.argmax(local)))

        # 註：每個精修區間都以左右相鄰「粗略」峰值的中點為界，區間彼此
        # 不重疊，因此不會有兩個精修後的點落在同一個區間內；這裡只需去除
        # 完全相同索引的邊界情況即可，不應再用 min_dist 做二次合併──
        # 真實心跳間距可能非常接近甚至小於 min_dist（例如快速心律），
        # 用 min_dist 二次過濾會把相鄰的真實 R-peak 誤刪。
        peaks = np.array(sorted(set(refined)))

    stats = rr_stats_from_peaks(peaks, fs)
    return peaks, stats


def rr_stats_from_peaks(peaks: np.ndarray, fs: float) -> dict:
    """從一組 R-peak 樣本索引計算 RR/HR 統計。供自動偵測與手動編輯共用。"""
    if peaks is None or len(peaks) < 2:
        return {}
    rr = np.diff(np.sort(peaks)) / fs * 1000
    rr = rr[(rr > 80) & (rr < 2000)]
    if len(rr) == 0:
        return {}
    return {
        'count':   len(peaks),
        'hr':      round(60000 / rr.mean(), 1),
        'rr_mean': round(rr.mean(), 1),
        'rr_std':  round(rr.std(), 1),
        'rmssd':   round(float(np.sqrt(np.mean(np.diff(rr) ** 2))), 1) if len(rr) > 1 else 0,
        'cv':      round(rr.std() / rr.mean() * 100, 1),
    }


def rr_stats_from_times(times) -> dict:
    """跟 rr_stats_from_peaks 相同，但直接吃『秒』為單位的時間陣列
    （例如已換算成絕對時間的 R-peak 標記），給測量範圍 BPM 沿用既有
    標記時使用。"""
    times = np.sort(np.asarray(times, dtype=float))
    if len(times) < 2:
        return {}
    rr = np.diff(times) * 1000
    rr = rr[(rr > 80) & (rr < 2000)]
    if len(rr) == 0:
        return {}
    return {
        'count':   len(times),
        'hr':      round(60000 / rr.mean(), 1),
        'rr_mean': round(rr.mean(), 1),
        'rr_std':  round(rr.std(), 1),
        'rmssd':   round(float(np.sqrt(np.mean(np.diff(rr) ** 2))), 1) if len(rr) > 1 else 0,
        'cv':      round(rr.std() / rr.mean() * 100, 1),
    }


class PeakDetector(QThread):
    finished = pyqtSignal(object, object)   # peaks, stats

    def __init__(self, data: np.ndarray, fs: float, t_offset: float,
                 notch_freq: float = 0.0,
                 bp_enabled: bool = False, bp_lo: float = 1.0, bp_hi: float = 150.0):
        super().__init__()
        self.data = data
        self.fs = fs
        self.t_offset = t_offset
        self.notch_freq = notch_freq
        self.bp_enabled = bp_enabled
        self.bp_lo = bp_lo
        self.bp_hi = bp_hi

    def run(self):
        try:
            peaks, stats = detect_r_peaks_and_stats(
                self.data, self.fs,
                notch_freq=self.notch_freq,
                bp_enabled=self.bp_enabled,
                bp_lo=self.bp_lo, bp_hi=self.bp_hi)
            self.finished.emit(peaks, stats)
        except Exception:
            self.finished.emit(np.array([]), {})


# ══════════════════════════════════════════════════════════════════════════════
# 時間戳記管理
# ══════════════════════════════════════════════════════════════════════════════
class TimestampManager:
    def __init__(self, abf_path: str):
        base = os.path.splitext(abf_path)[0]
        self.json_path = base + '_timestamps.json'
        self.csv_path  = base + '_timestamps.csv'
        self.records: list[dict] = []
        self._load()

    def _load(self):
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, encoding='utf-8') as f:
                    self.records = json.load(f)
            except Exception:
                self.records = []

    def add(self, t_start: float, t_end: float | None,
            label: str = '', note: str = '', tag: str = '',
            ecg_data=None) -> dict:
        abs_start = ecg_data.abs_time(t_start) if ecg_data else ''
        abs_end   = ecg_data.abs_time(t_end)   if (ecg_data and t_end is not None) else ''
        rec_date  = ecg_data.rec_datetime.strftime('%Y-%m-%d') if (ecg_data and ecg_data.rec_datetime) else ''
        rec = {
            'id':           len(self.records) + 1,
            'created':      datetime.datetime.now().isoformat(timespec='seconds'),
            'label':        label or f'TS-{len(self.records)+1:03d}',
            'tag':          tag,
            'note':         note,
            'rec_date':     rec_date,
            't_start':      round(t_start, 4),
            't_end':        round(t_end, 4) if t_end is not None else None,
            'duration':     round(t_end - t_start, 4) if t_end is not None else None,
            't_start_hms':  fmt_hms(t_start),
            't_end_hms':    fmt_hms(t_end) if t_end is not None else '',
            'abs_start':    abs_start,
            'abs_end':      abs_end,
        }
        self.records.append(rec)
        self.save()
        return rec

    def remove(self, idx: int):
        if 0 <= idx < len(self.records):
            self.records.pop(idx)
            # 重新編號
            for i, r in enumerate(self.records):
                r['id'] = i + 1
            self.save()

    def save(self):
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)
        if self.records:
            keys = ['id','created','label','tag','note','rec_date',
                    't_start','t_end','duration','t_start_hms','t_end_hms',
                    'abs_start','abs_end']
            with open(self.csv_path, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
                w.writeheader()
                w.writerows(self.records)

    def update(self, idx: int, label: str, note: str, tag: str):
        if 0 <= idx < len(self.records):
            self.records[idx]['label'] = label
            self.records[idx]['note']  = note
            self.records[idx]['tag']   = tag
            self.save()

    @property
    def save_dir(self):
        return os.path.dirname(self.json_path)


# ══════════════════════════════════════════════════════════════════════════════
# 右側面板：資訊 + 時間戳記
# ══════════════════════════════════════════════════════════════════════════════
class SidePanel(QWidget):
    ts_selected   = pyqtSignal(int)      # 選中某筆 timestamp
    ts_deleted    = pyqtSignal(list)     # 刪除多筆 timestamp（index 列表）
    ts_renamed    = pyqtSignal(int, str, str, str)  # 編輯（index, label, note, tag）
    ts_goto       = pyqtSignal(float)    # 跳到指定時間
    ts_save_requested = pyqtSignal()     # 觸發儲存時間戳記
    skna_settings_requested  = pyqtSignal()      # 開啟 SKNA 設定
    skna_intervals_requested = pyqtSignal()      # 開啟 SKNA 區間分析視窗
    skna_add_requested       = pyqtSignal()      # 節錄目前選取範圍
    skna_delete_requested    = pyqtSignal(list)  # 刪除選取的 SKNA 區間
    skna_goto_index          = pyqtSignal(int)   # 跳到第 n 段 SKNA 區間
    skna_review_requested    = pyqtSignal()      # 開啟 Artifact 逐段判讀
    skna_goto                = pyqtSignal(float) # 跳到指定時間
    page_requested           = pyqtSignal(int)   # 切換 ECG / SKNA 頁
    s3_run_requested         = pyqtSignal(bool)  # 執行 S3（True=整檔）
    mark_add_requested       = pyqtSignal()      # 進入新增時間點位模式
    mark_delete_requested    = pyqtSignal(list)  # 刪除選取的時間點位
    mark_goto_index          = pyqtSignal(int)   # 跳到第 n 個時間點位

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(260)
        self.setMaximumWidth(340)
        self._build()

    def _build(self):
        # 側邊欄內容比視窗高的時候（尤其 SKNA 頁多了兩個群組），若直接塞進
        # 固定版面，Qt 會把每個群組壓扁到重疊。包一層捲動區就不會。
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── 頁面切換（放在捲動區外，捲到哪裡都看得到）──
        tabrow = QWidget()
        tabrow.setObjectName('sideTabs')
        tabrow.setStyleSheet(f'QWidget#sideTabs{{background:{C["bg"]};}}')
        tl = QHBoxLayout(tabrow)
        tl.setContentsMargins(8, 8, 8, 6)
        tl.setSpacing(6)
        tab_style = (
            f'QPushButton{{background:{C["panel"]};color:{C["dim"]};'
            f'border:1px solid {C["border"]};border-radius:6px;'
            f'padding:7px 0px;font-size:13px;font-weight:bold;}}'
            f'QPushButton:hover{{background:{C["border"]};color:{C["text"]};}}'
            f'QPushButton:checked{{background:{C["accent"]};color:{C["bg"]};'
            f'border:1px solid {C["accent"]};}}')
        self.page_btns = []
        for i, (name, tip) in enumerate((
                ('ECG', 'R-peak 偵測與編輯、濾波、時間戳記'),
                ('SKNA', '皮膚交感神經活性：S3 分解、時間點位、區間分析'))):
            b = QPushButton(name)
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setToolTip(tip)
            b.setStyleSheet(tab_style)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=i: self.page_requested.emit(k))
            tl.addWidget(b, 1)
            self.page_btns.append(b)
        outer.addWidget(tabrow)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setObjectName('sideScroll')
        self._scroll.setStyleSheet(
            f'QScrollArea#sideScroll{{background:{C["bg"]};border:none;}}'
            f'QScrollBar:vertical{{background:{C["bg"]};width:9px;margin:0;}}'
            f'QScrollBar::handle:vertical{{background:{C["border"]};'
            f'border-radius:4px;min-height:24px;}}'
            f'QScrollBar::handle:vertical:hover{{background:{C["dim"]};}}'
            f'QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}'
            f'QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{{background:none;}}')
        inner = QWidget()
        # 用 objectName 限定範圍。直接寫 'background:...' 會串到所有子元件，
        # 把 QGroupBox 的標題樣式一起蓋掉，標題就會被畫到邊框上變得看不清楚。
        inner.setObjectName('sideInner')
        inner.setStyleSheet(f'QWidget#sideInner{{background:{C["bg"]};}}')
        self._scroll.setWidget(inner)
        outer.addWidget(self._scroll)

        lay = QVBoxLayout(inner)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # ── 檔案資訊 ──
        grp_info = QGroupBox("檔案資訊")
        info_lay = QVBoxLayout(grp_info)
        info_lay.setSpacing(3)

        self.lbl_file      = self._kv('檔案', '—')
        self.lbl_fs        = self._kv('取樣率', '—')
        self.lbl_dur       = self._kv('總長度', '—')
        self.lbl_ch        = self._kv('通道數', '—')
        self.lbl_rec_date  = self._kv('記錄日期', '—')
        self.lbl_rec_start = self._kv('開始時間', '—')
        self.lbl_rec_end   = self._kv('結束時間', '—')

        for w in [self.lbl_file, self.lbl_fs, self.lbl_dur, self.lbl_ch,
                  self.lbl_rec_date, self.lbl_rec_start, self.lbl_rec_end]:
            info_lay.addWidget(w)
        lay.addWidget(grp_info)

        # ── 目前視窗 ──
        grp_view = QGroupBox("目前視窗")
        view_lay = QVBoxLayout(grp_view)
        view_lay.setSpacing(3)
        self.lbl_view_start = self._kv('起點', '—')
        self.lbl_view_end   = self._kv('終點', '—')
        self.lbl_view_win   = self._kv('視窗', '—')
        for w in [self.lbl_view_start, self.lbl_view_end, self.lbl_view_win]:
            view_lay.addWidget(w)
        lay.addWidget(grp_view)

        # ── 測量結果 ──
        self.grp_meas = grp_meas = QGroupBox("時間測量")
        meas_lay = QVBoxLayout(grp_meas)
        meas_lay.setSpacing(3)
        self.lbl_pt_a    = self._kv('A點', '—')
        self.lbl_pt_b    = self._kv('B點', '—')
        self.lbl_delta   = self._kv('Δt', '—')
        self.lbl_delta_ms= self._kv('Δt (ms)', '—')
        self.lbl_bpm     = self._kv('平均 BPM', '—')
        for w in [self.lbl_pt_a, self.lbl_pt_b, self.lbl_delta, self.lbl_delta_ms, self.lbl_bpm]:
            meas_lay.addWidget(w)
        lay.addWidget(grp_meas)

        # ── RR 統計 ──
        self.grp_rr = grp_rr = QGroupBox("節律分析")
        rr_lay = QVBoxLayout(grp_rr)
        rr_lay.setSpacing(3)
        self.lbl_hr     = self._kv('心率', '—')
        self.lbl_rr     = self._kv('RR 間距', '—')
        self.lbl_rmssd  = self._kv('RMSSD', '—')
        self.lbl_cv     = self._kv('CV%', '—')
        for w in [self.lbl_hr, self.lbl_rr, self.lbl_rmssd, self.lbl_cv]:
            rr_lay.addWidget(w)
        lay.addWidget(grp_rr)

        # ── 時間戳記列表 ──
        self.grp_ts = grp_ts = QGroupBox("時間戳記")
        ts_lay = QVBoxLayout(grp_ts)
        ts_lay.setSpacing(4)

        # 儲存時間戳記按鈕（移到側邊欄）
        self.btn_save_ts = QPushButton("+ 儲存時間戳記  (T)")
        self.btn_save_ts.setObjectName('btn_success')
        self.btn_save_ts.clicked.connect(lambda: self.ts_save_requested.emit())
        ts_lay.addWidget(self.btn_save_ts)

        self.ts_list = QListWidget()
        self.ts_list.setMinimumHeight(140)
        self.ts_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.ts_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ts_list.customContextMenuRequested.connect(self._on_ts_context_menu)
        self.ts_list.itemClicked.connect(self._on_ts_click)
        self.ts_list.itemDoubleClicked.connect(self._on_ts_goto)
        ts_lay.addWidget(self.ts_list)

        btn_row = QHBoxLayout()
        self.btn_del_ts = QPushButton("刪除選取")
        self.btn_del_ts.setObjectName('btn_danger')
        self.btn_del_ts.clicked.connect(self._on_ts_delete)
        btn_row.addWidget(self.btn_del_ts)

        self.btn_open_folder = QPushButton("開啟資料夾")
        self.btn_open_folder.clicked.connect(self._on_open_folder)
        btn_row.addWidget(self.btn_open_folder)
        ts_lay.addLayout(btn_row)

        # AFib 加總
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet(f'color:{C["border"]};')
        ts_lay.addWidget(div)

        def _afib_lbl(text):
            lbl = QLabel(text)
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setWordWrap(True)
            return lbl

        self.lbl_afib = _afib_lbl(
            f'<span style="color:{C["dim"]}">AFib 總時長：</span>'
            f'<span style="color:{C["purple"]}; font-weight:bold;">—</span>')
        self.lbl_afib_baseline = _afib_lbl(
            f'<span style="color:{C["dim"]}">AFib (Baseline)：</span>'
            f'<span style="color:{C["purple"]}; font-weight:bold;">—</span>')
        self.lbl_afib_apamin = _afib_lbl(
            f'<span style="color:{C["dim"]}">AFib (Apamin)：</span>'
            f'<span style="color:{C["purple"]}; font-weight:bold;">—</span>')
        ts_lay.addWidget(self.lbl_afib)
        ts_lay.addWidget(self.lbl_afib_baseline)
        ts_lay.addWidget(self.lbl_afib_apamin)

        lay.addWidget(grp_ts)

        # ── SKNA 設定摘要（只在 SKNA 頁顯示）──
        self.grp_skna_cfg = QGroupBox("SKNA 設定")
        sc_lay = QVBoxLayout(self.grp_skna_cfg)
        sc_lay.setSpacing(5)

        self.lbl_skna_method = self._kv('演算法', '—')
        self.lbl_skna_src    = self._kv('來源通道', '—')
        self.lbl_skna_ecg    = self._kv('ECG 參考', '—')
        self.lbl_skna_band   = self._kv('帶通', '—')
        self.lbl_skna_env    = self._kv('包絡窗長', '—')
        self.lbl_skna_s3     = self._kv('S3 狀態', '—')
        for w in [self.lbl_skna_method, self.lbl_skna_src, self.lbl_skna_ecg,
                  self.lbl_skna_band, self.lbl_skna_env,
                  self.lbl_skna_s3]:
            sc_lay.addWidget(w)

        self.btn_skna_cfg = QPushButton("SKNA 設定...")
        self.btn_skna_cfg.clicked.connect(
            lambda: self.skna_settings_requested.emit())
        sc_lay.addWidget(self.btn_skna_cfg)

        self.btn_s3_run = QPushButton("S3 分解（整檔）")
        self.btn_s3_run.setObjectName('btn_success')
        self.btn_s3_run.setToolTip(
            '對整個檔案執行 S3，分解掉心電成分，得到不含心跳干擾的 SKNA')
        self.btn_s3_run.clicked.connect(
            lambda: self.s3_run_requested.emit(True))
        sc_lay.addWidget(self.btn_s3_run)

        lay.addWidget(self.grp_skna_cfg)

        # ── SKNA 時間點位（只在 SKNA 頁顯示）──
        self.grp_skna_marks = QGroupBox("SKNA 時間點位")
        sm_lay = QVBoxLayout(self.grp_skna_marks)
        sm_lay.setSpacing(4)

        self.btn_mark_add = QPushButton("＋ 新增時間點位")
        self.btn_mark_add.setObjectName('btn_success')
        self.btn_mark_add.setToolTip(
            '進入點位標記模式，然後在波形上點一下，輸入名稱並選擇起點／終點')
        self.btn_mark_add.setCheckable(True)
        self.btn_mark_add.clicked.connect(
            lambda: self.mark_add_requested.emit())
        sm_lay.addWidget(self.btn_mark_add)

        self.mark_list = QListWidget()
        self.mark_list.setMinimumHeight(130)
        self.mark_list.setWordWrap(True)
        self.mark_list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection)
        self.mark_list.itemDoubleClicked.connect(self._on_mark_goto)
        sm_lay.addWidget(self.mark_list)

        self.btn_mark_del = QPushButton("刪除選取")
        self.btn_mark_del.setObjectName('btn_danger')
        self.btn_mark_del.clicked.connect(self._on_mark_delete)
        sm_lay.addWidget(self.btn_mark_del)

        self.lbl_mark_hint = QLabel('')
        self.lbl_mark_hint.setWordWrap(True)
        self.lbl_mark_hint.setStyleSheet(f'color:{C["dim"]};font-size:11px;')
        sm_lay.addWidget(self.lbl_mark_hint)
        lay.addWidget(self.grp_skna_marks)

        # ── SKNA 時間區段（只在 SKNA 頁顯示）──
        self.grp_skna_iv = QGroupBox("SKNA 時間區段")
        si_lay = QVBoxLayout(self.grp_skna_iv)
        si_lay.setSpacing(4)

        self.btn_skna_add = QPushButton("＋ 加入目前顯示範圍")
        self.btn_skna_add.setToolTip(
            '把目前顯示的時間範圍當成一個分析區間加入清單。'
            '一般情況建議改用上面的時間點位標記')
        self.btn_skna_add.clicked.connect(
            lambda: self.skna_add_requested.emit())
        si_lay.addWidget(self.btn_skna_add)

        self.skna_list = QListWidget()
        self.skna_list.setMinimumHeight(150)
        # 每筆是多行（標籤／起訖時間／aSKNA／警示），不開 wordWrap 會被截成
        # 兩行加上省略號
        self.skna_list.setWordWrap(True)
        self.skna_list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection)
        self.skna_list.itemDoubleClicked.connect(self._on_skna_goto)
        si_lay.addWidget(self.skna_list)

        sb_row = QHBoxLayout()
        self.btn_skna_del = QPushButton("刪除選取")
        self.btn_skna_del.setObjectName('btn_danger')
        self.btn_skna_del.clicked.connect(self._on_skna_delete)
        sb_row.addWidget(self.btn_skna_del)
        self.btn_skna_open = QPushButton("區間分析...")
        self.btn_skna_open.clicked.connect(
            lambda: self.skna_intervals_requested.emit())
        sb_row.addWidget(self.btn_skna_open)
        si_lay.addLayout(sb_row)
        self.btn_skna_review = QPushButton("Artifact")
        self.btn_skna_review.setToolTip(
            '依序檢視每一段 SKNA 波形，人工判讀為「保留」或「Artifact」\n'
            '（預設保留；Bandpass 與 S3 都可用；判讀結果會寫進匯出的 Excel 總表）')
        self.btn_skna_review.clicked.connect(
            lambda: self.skna_review_requested.emit())
        si_lay.addWidget(self.btn_skna_review)

        self.lbl_skna_hint = QLabel('')
        self.lbl_skna_hint.setWordWrap(True)
        self.lbl_skna_hint.setStyleSheet(f'color:{C["dim"]};font-size:11px;')
        si_lay.addWidget(self.lbl_skna_hint)
        lay.addWidget(self.grp_skna_iv)

        lay.addStretch()

        self._ts_manager = None
        self.set_page(0)

    # ── 頁面切換 ─────────────────────────────────────────────────────────

    def set_page(self, page: int):
        """ECG 頁顯示節律分析與時間戳記；SKNA 頁改顯示 SKNA 設定與區間清單。

        檔案資訊、目前視窗、時間測量兩頁都留著 —— SKNA 區間就是靠測量模式
        圈選出來的，時間測量拿掉的話就沒辦法確認選到哪裡。
        """
        ecg = (page == 0)
        for i, b in enumerate(self.page_btns):
            b.setChecked(i == page)
        for w in (self.grp_rr, self.grp_ts):
            w.setVisible(ecg)
        # 時間測量在 SKNA 頁用不到了：那邊改用時間點位標記，不是 A→B 測量
        self.grp_meas.setVisible(ecg)
        for w in (self.grp_skna_cfg, self.grp_skna_iv, self.grp_skna_marks):
            w.setVisible(not ecg)

    # ── SKNA 摘要與區間清單 ───────────────────────────────────────────────

    def update_skna_cfg(self, data, cfg: dict, s3_cache=None, s3_valid=False):
        """更新 SKNA 設定摘要。"""
        if data is None or cfg.get('src_ch') is None:
            for lbl, k in ((self.lbl_skna_method, '演算法'),
                           (self.lbl_skna_src, '來源通道'),
                           (self.lbl_skna_ecg, 'ECG 參考'),
                           (self.lbl_skna_band, '帶通'),
                           (self.lbl_skna_env, '包絡窗長'),
                           (self.lbl_skna_s3, 'S3 狀態')):
                self._set_kv(lbl, k, '—')
            return

        src, ecg_ch = cfg['src_ch'], cfg['ecg_ch']
        fs = data.fs_of(src)
        lo, hi, warn = skna_effective_band(fs, cfg['bp_lo'], cfg['bp_hi'])
        lo2, hi2, warn2 = skna_effective_band(fs, cfg.get('bp_lo2', 500.0),
                                              cfg.get('bp_hi2', 1500.0))
        is_s3 = cfg.get('method') == 's3'

        self._set_kv(self.lbl_skna_method, '演算法',
                     'S3（不再帶通）' if is_s3 else '傳統帶通 (BPF)')
        if skna_tracks_differ(cfg):
            s2_ = cfg['src_ch2']
            self._set_kv(self.lbl_skna_src, '來源通道',
                         f'軌2 CH{src} {data.ch_names[src]}／軌3 CH{s2_} {data.ch_names[s2_]}')
        else:
            self._set_kv(self.lbl_skna_src, '來源通道',
                         f'CH{src} {data.ch_names[src]}')
        self._set_kv(self.lbl_skna_ecg, 'ECG 參考',
                     f'CH{ecg_ch} {data.ch_names[ecg_ch]}')
        self._set_kv(self.lbl_skna_band, '帶通',
                     f'軌2 {lo:.0f}–{hi:.0f}／軌3 {lo2:.0f}–{hi2:.0f} Hz'
                     + ('  ⚠' if (warn or warn2) else '')
                     + (lambda t_: f'（{t_} 顯示 S3）' if t_ else '')(
                         '、'.join(n_ for n_, k_, b_ in (('軌2', 'disp1', 1),
                                                         ('軌3', 'disp2', 2))
                                   if is_s3 and cfg.get(k_, 'bpf') == 's3'
                                   and (b_ == 1 or not skna_tracks_differ(cfg)))))
        self._set_kv(self.lbl_skna_env, '包絡窗長', f"{cfg['env_ms']:.0f} ms")
        if not is_s3:
            txt, col = '未使用', C['dim']
        elif s3_valid and s3_cache:
            rng = ('整檔' if s3_cache.get('whole_file')
                   else f"{fmt_hms(s3_cache['t0'])}–{fmt_hms(s3_cache['t1'])}")
            txt, col = f"已分解（{rng}）", C['green']
        else:
            txt, col = '尚未分解 ⚠', C['yellow']
        self.lbl_skna_s3.setText(
            f'<span style="color:{C["dim"]}">S3 狀態：</span>'
            f'<span style="color:{col}; font-weight:bold;">{txt}</span>')

    def refresh_skna_list(self, rows: list, data=None):
        """更新 SKNA 時間區段清單。"""
        self.skna_list.clear()
        for i, r in enumerate(rows):
            res = r.get('res') or {}
            a = res.get('all', {}) if res.get('ok') else {}
            s3 = res.get('s3', {}) if res.get('ok') else {}
            src_m = s3 if s3.get('aSKNA') is not None else a
            val = src_m.get('aSKNA')
            ival = src_m.get('iSKNA')
            tag = 'S3' if s3.get('aSKNA') is not None else 'BPF'
            unit = res.get('unit', 'µV')
            dur = r['t1'] - r['t0']
            head = f"{r.get('label') or f'區間 {i + 1}'}"
            if r.get('kind') == 'mark':
                head = '📍 ' + head
            elif r.get('kind') == 'auto':
                head = '⏱ ' + head
            body = f"{fmt_hms(r['t0'])} → {fmt_hms(r['t1'])}　({dur:.1f} s)"
            # 側邊欄只有約 340 px：每個軌道一行 aSKNA，iSKNA 留給區間分析表
            b1, b2 = res.get('band1', ''), res.get('band2', '')
            if val is not None and np.isfinite(val):
                body += (f"\nS3 aSKNA {val:.3f} {unit}" if tag == 'S3'
                         else f"\nBPF {b1} aSKNA {val:.3f} {unit}")
            a2 = res.get('all2', {}) if res.get('ok') else {}
            v2 = a2.get('aSKNA')
            if v2 is not None and np.isfinite(v2):
                body += f"\nBPF {b2} aSKNA {v2:.3f} {unit}"
            na = res.get('nact', {}) if res.get('ok') else {}
            na2 = res.get('nact2', {}) if res.get('ok') else {}
            nv, nv2 = na.get('aSKNA'), na2.get('aSKNA')
            if nv is not None and np.isfinite(nv):
                body += f"\nNerveact aSKNA {nv:.3f}" + (
                    f" / {nv2:.3f}" if nv2 is not None and np.isfinite(nv2) else '') + f" {unit}"
            flags = res.get('flags', [])
            if flags:
                body += f"\n⚠ {'、'.join(flags)}"
            if r.get('judge') == 'artifact':
                head = '✗ ' + head + '　[Artifact]'
            text = f"{head}\n{body}"
            it = QListWidgetItem(text)
            it.setData(Qt.ItemDataRole.UserRole, i)
            # QListWidget 不會依多行內容自動加高，沒給 sizeHint 的話第三行
            # （aSKNA／警示）會被截成省略號
            fm = self.skna_list.fontMetrics()
            it.setSizeHint(QSize(0, fm.lineSpacing() * (text.count('\n') + 1) + 10))
            if r.get('judge') == 'artifact':
                it.setForeground(QColor(C['red']))
            elif flags:
                it.setForeground(QColor(C['yellow']))
            self.skna_list.addItem(it)
        if rows:
            self.lbl_skna_hint.setText(
                f'共 {len(rows)} 段。雙擊可跳到該段起點；'
                '「區間分析...」可看完整指標並匯出 Excel。')
        else:
            self.lbl_skna_hint.setText(
                '按 M 進入測量模式，在波形上點 A 點與 B 點圈出範圍，'
                '再按上方「節錄目前選取範圍」。')

    def refresh_marks(self, marks: list, unpaired=None, data=None,
                      mark_mode: bool = False):
        """更新時間點位清單。"""
        unpaired = set(unpaired or [])
        self.mark_list.clear()
        order = sorted(range(len(marks)), key=lambda i: marks[i]['t'])
        for i in order:
            m = marks[i]
            is_start = m.get('kind') == 'start'
            icon = '▶ 起點' if is_start else '■ 終點'
            abs_t = data.abs_time(m['t']) if data is not None else ''
            # 標出哪些是從檔案本身帶進來的（.acq 錄製時按下的事件標記），
            # 跟自己在畫面上點的分開來看
            from_file = '　📍檔案' if m.get('src') == 'acq' else ''
            text = (f"{icon}　{m.get('name', '')}{from_file}\n"
                    f"{fmt_hms(m['t'])}" + (f"　（{abs_t}）" if abs_t else ''))
            if i in unpaired:
                text += '\n⚠ 尚未配對'
            it = QListWidgetItem(text)
            it.setData(Qt.ItemDataRole.UserRole, i)
            fm = self.mark_list.fontMetrics()
            it.setSizeHint(QSize(0, fm.lineSpacing() * (text.count('\n') + 1) + 10))
            it.setForeground(QColor(
                C['yellow'] if i in unpaired
                else (C['green'] if is_start else C['red'])))
            self.mark_list.addItem(it)

        self.btn_mark_add.setChecked(bool(mark_mode))
        if mark_mode:
            self.lbl_mark_hint.setText(
                '標記模式開啟中 — 在波形上點一下即可新增點位，'
                '再按一次上方按鈕結束。')
            self.lbl_mark_hint.setStyleSheet(
                f'color:{C["accent"]};font-size:11px;')
            return

        self.lbl_mark_hint.setStyleSheet(f'color:{C["dim"]};font-size:11px;')
        if not marks:
            self.lbl_mark_hint.setText(
                '按上方按鈕（或 M）後點擊波形新增點位。起點與其後最近的終點'
                '會自動配對成區間，SKNA 指標會自動算好。')
        elif unpaired:
            self.lbl_mark_hint.setText(
                f'共 {len(marks)} 個點位，其中 {len(unpaired)} 個還沒配對成區間。'
                '雙擊可跳到該點位。')
        else:
            self.lbl_mark_hint.setText(
                f'共 {len(marks)} 個點位，全部已配對。雙擊可跳到該點位。')

    def _on_mark_goto(self, item):
        i = item.data(Qt.ItemDataRole.UserRole)
        if i is not None:
            self.mark_goto_index.emit(int(i))

    def _on_mark_delete(self):
        idx = []
        for row in {i.row() for i in self.mark_list.selectedIndexes()}:
            it = self.mark_list.item(row)
            if it is not None:
                v = it.data(Qt.ItemDataRole.UserRole)
                if v is not None:
                    idx.append(int(v))
        if idx:
            self.mark_delete_requested.emit(idx)

    def _on_skna_goto(self, item):
        i = item.data(Qt.ItemDataRole.UserRole)
        if i is not None:
            self.skna_goto_index.emit(int(i))

    def _on_skna_delete(self):
        idx = sorted({i.row() for i in self.skna_list.selectedIndexes()},
                     reverse=True)
        if idx:
            self.skna_delete_requested.emit(idx)

    def _kv(self, key: str, val: str) -> QLabel:
        lbl = QLabel(f'<span style="color:{C["dim"]}">{key}：</span>'
                     f'<span style="color:{C["accent"]}">{val}</span>')
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        return lbl

    def _set_kv(self, lbl: QLabel, key: str, val: str):
        lbl.setText(f'<span style="color:{C["dim"]}">{key}：</span>'
                    f'<span style="color:{C["accent"]}">{val}</span>')

    def update_file_info(self, data):
        name = os.path.basename(data.path)
        name = name if len(name) <= 20 else '…' + name[-17:]
        ext  = os.path.splitext(data.path)[1].upper().lstrip('.')
        self._set_kv(self.lbl_file, '檔案', name)
        if getattr(data, 'mixed_fs', False):
            uniq = sorted({data.fs_of(i) for i in range(data.n_ch)}, reverse=True)
            fs_txt = ' / '.join(f'{v:,.0f}' for v in uniq) + ' Hz'
        else:
            fs_txt = f'{data.fs:,.0f} Hz'
        self._set_kv(self.lbl_fs,   '取樣率', fs_txt)
        self._set_kv(self.lbl_dur,  '總長度', fmt_hms(data.duration))
        self._set_kv(self.lbl_ch,   '通道數', f'{data.n_ch}  [{ext}]')
        try:
            info = data.info()
        except Exception:
            info = {}
        self._set_kv(self.lbl_rec_date,  '記錄日期', info.get('rec_date', '—'))
        self._set_kv(self.lbl_rec_start, '開始時間', info.get('rec_time', '—'))
        self._set_kv(self.lbl_rec_end,   '結束時間', info.get('rec_end', '—'))

    def update_view(self, t0: float, t1: float):
        self._set_kv(self.lbl_view_start, '起點', fmt_hms(t0))
        self._set_kv(self.lbl_view_end,   '終點', fmt_hms(t1))
        self._set_kv(self.lbl_view_win,   '視窗', f'{t1-t0:.3f} s')
        if hasattr(self, '_ecg_data_ref') and self._ecg_data_ref is not None:
            self._set_kv(self.lbl_view_start, '起點',
                f'{fmt_hms(t0)}  ({self._ecg_data_ref.abs_time(t0)})')
            self._set_kv(self.lbl_view_end, '終點',
                f'{fmt_hms(t1)}  ({self._ecg_data_ref.abs_time(t1)})')

    def update_measure(self, pts: list, bpm_info: dict | None = None):
        a = pts[0] if len(pts) > 0 else None
        b = pts[1] if len(pts) > 1 else None
        self._set_kv(self.lbl_pt_a, 'A點', fmt_hms(a) if a is not None else '—（點擊波形）')
        self._set_kv(self.lbl_pt_b, 'B點', fmt_hms(b) if b is not None else '—（再次點擊）')
        if a is not None and b is not None:
            dt = abs(b - a)
            self._set_kv(self.lbl_delta,    'Δt', f'{dt:.4f} s')
            self._set_kv(self.lbl_delta_ms, 'Δt(ms)', f'{dt*1000:.2f} ms')
        else:
            self._set_kv(self.lbl_delta,    'Δt', '—')
            self._set_kv(self.lbl_delta_ms, 'Δt(ms)', '—')

        if not bpm_info:
            self._set_kv(self.lbl_bpm, '平均 BPM', '—')
        elif bpm_info.get('skipped'):
            self._set_kv(self.lbl_bpm, '平均 BPM', '範圍過大，請改用 P 偵測')
        elif bpm_info.get('hr') is not None:
            self._set_kv(self.lbl_bpm, '平均 BPM',
                         f"{bpm_info['hr']} bpm"
                         f"（{bpm_info.get('count', '—')} 個 R-peak）")
        elif bpm_info.get('count', 0) > 0:
            self._set_kv(self.lbl_bpm, '平均 BPM', f"僅偵測到 {bpm_info['count']} 個峰值，不足以計算")
        else:
            self._set_kv(self.lbl_bpm, '平均 BPM', '—（範圍內未偵測到 R-peak）')

    def update_rr(self, stats: dict):
        if not stats:
            for lbl, k in [(self.lbl_hr,'心率'),(self.lbl_rr,'RR間距'),
                           (self.lbl_rmssd,'RMSSD'),(self.lbl_cv,'CV%')]:
                self._set_kv(lbl, k, '—')
            return
        self._set_kv(self.lbl_hr,    '心率',   f"{stats.get('hr','—')} bpm")
        self._set_kv(self.lbl_rr,    'RR間距', f"{stats.get('rr_mean','—')}±{stats.get('rr_std','—')} ms")
        self._set_kv(self.lbl_rmssd, 'RMSSD',  f"{stats.get('rmssd','—')} ms")
        self._set_kv(self.lbl_cv,    'CV%',    f"{stats.get('cv','—')} %")

    def set_ecg_data(self, data):
        self._ecg_data_ref = data

    def set_ts_manager(self, mgr: TimestampManager):
        self._ts_manager = mgr
        self.refresh_ts_list()

    def refresh_ts_list(self):
        self.ts_list.clear()
        self._reset_afib_labels()
        if not self._ts_manager:
            return
        totals = {'AFib': 0.0, 'AFib (Baseline)': 0.0, 'AFib (Apamin)': 0.0}
        for r in self._ts_manager.records:
            dur = f"Δ{r['duration']:.3f}s" if r['duration'] else '(點)'
            tag = r.get('tag', '')
            tag_str = f'  [{tag}]' if tag else ''
            t_disp = r.get('abs_start') or r['t_start_hms']
            item = QListWidgetItem(
                f"#{r['id']:02d}  {r['label']}{tag_str}\n"
                f"     {t_disp}  {dur}\n"
                f"     {r['note'][:30] if r['note'] else ''}"
            )
            if tag in totals:
                item.setForeground(QColor(C['purple']))
                if r.get('duration') is not None:
                    totals[tag] += r['duration']
            else:
                item.setForeground(QColor(C['text']))
            self.ts_list.addItem(item)

        grand = totals['AFib'] + totals['AFib (Baseline)'] + totals['AFib (Apamin)']
        self._set_afib_lbl(self.lbl_afib,          'AFib 總時長',     grand)
        self._set_afib_lbl(self.lbl_afib_baseline,  'AFib (Baseline)', totals['AFib (Baseline)'])
        self._set_afib_lbl(self.lbl_afib_apamin,    'AFib (Apamin)',   totals['AFib (Apamin)'])

    def _set_afib_lbl(self, lbl: QLabel, key: str, sec: float):
        if sec > 0:
            lbl.setText(
                f'<span style="color:{C["dim"]}">{key}：</span>'
                f'<span style="color:{C["purple"]}; font-weight:bold;">'
                f'{fmt_hms(sec)}  ({sec:.2f} s)</span>')
        else:
            lbl.setText(
                f'<span style="color:{C["dim"]}">{key}：</span>'
                f'<span style="color:{C["purple"]}; font-weight:bold;">—</span>')

    def _reset_afib_labels(self):
        for lbl, key in [
            (self.lbl_afib,          'AFib 總時長'),
            (self.lbl_afib_baseline, 'AFib (Baseline)'),
            (self.lbl_afib_apamin,   'AFib (Apamin)'),
        ]:
            lbl.setText(
                f'<span style="color:{C["dim"]}">{key}：</span>'
                f'<span style="color:{C["purple"]}; font-weight:bold;">—</span>')

    def _on_ts_click(self, item):
        idx = self.ts_list.row(item)
        self.ts_selected.emit(idx)

    def _on_ts_goto(self, item):
        idx = self.ts_list.row(item)
        if self._ts_manager and 0 <= idx < len(self._ts_manager.records):
            t = self._ts_manager.records[idx]['t_start']
            self.ts_goto.emit(t)

    def _on_ts_delete(self):
        indices = sorted([self.ts_list.row(item)
                          for item in self.ts_list.selectedItems()], reverse=True)
        if indices:
            self.ts_deleted.emit(indices)

    def _on_ts_context_menu(self, pos):
        item = self.ts_list.itemAt(pos)
        if item is None:
            return
        idx = self.ts_list.row(item)

        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(
            f'QMenu{{background:{C["panel"]};border:1px solid {C["border"]};'
            f'color:{C["text"]};font-size:12px;}}'
            f'QMenu::item:selected{{background:{C["accent"]};color:{C["bg"]};}}')

        act_rename = menu.addAction('✏️  修改名稱')
        act_delete = menu.addAction('🗑  刪除')

        chosen = menu.exec(self.ts_list.viewport().mapToGlobal(pos))
        if chosen == act_rename:
            self._do_rename(idx)
        elif chosen == act_delete:
            self.ts_deleted.emit([idx])

    def _do_rename(self, idx: int):
        if not self._ts_manager or idx >= len(self._ts_manager.records):
            return
        rec = self._ts_manager.records[idx]
        dlg = TimestampDialog(
            rec['t_start'], rec.get('t_end'),
            parent=self,
            init_label=rec.get('label', ''),
            init_note=rec.get('note', ''),
            init_tag=rec.get('tag', ''),
            edit_mode=True)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            label, note, tag = dlg.get_data()
            self.ts_renamed.emit(idx, label, note, tag)

    def _on_open_folder(self):
        if self._ts_manager:
            import subprocess
            path = self._ts_manager.save_dir
            if sys.platform == 'darwin':
                subprocess.run(['open', path])
            elif sys.platform.startswith('win'):
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.run(['xdg-open', path])


# ══════════════════════════════════════════════════════════════════════════════
# 時間戳記儲存對話框
# ══════════════════════════════════════════════════════════════════════════════
class TimestampDialog(QDialog):
    def __init__(self, t_start: float, t_end: float | None, parent=None,
                 init_label: str = '', init_note: str = '', init_tag: str = '',
                 edit_mode: bool = False):
        super().__init__(parent)
        self.setWindowTitle('修改時間戳記' if edit_mode else '新增時間戳記')
        self.setModal(True)
        self.setMinimumWidth(360)
        self.t_start    = t_start
        self.t_end      = t_end
        self.init_label = init_label
        self.init_note  = init_note
        self.init_tag   = init_tag
        self.edit_mode  = edit_mode
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        # 時間資訊
        grp = QGroupBox('時間範圍')
        g_lay = QVBoxLayout(grp)
        if self.t_end is not None:
            dt = abs(self.t_end - self.t_start)
            info = (f"起點：{fmt_hms(self.t_start)}\n"
                    f"終點：{fmt_hms(self.t_end)}\n"
                    f"時間長：{dt:.4f} s  ({dt*1000:.2f} ms)")
        else:
            info = f"時間點：{fmt_hms(self.t_start)}"
        lbl = QLabel(info)
        lbl.setStyleSheet(f'color: {C["accent"]}; font-size: 13px;')
        g_lay.addWidget(lbl)
        lay.addWidget(grp)

        # 類型標籤（快速選擇）
        lay.addWidget(QLabel('類型標籤：'))
        self.combo_tag = QComboBox()
        self.combo_tag.addItems(['', 'AFib', 'AFib (Baseline)', 'AFib (Apamin)', 'Pacing', 'Tachycardia', 'Bradycardia', 'VF', '其他'])
        self.combo_tag.setStyleSheet(
            f'QComboBox{{background:{C["panel"]};color:{C["purple"]};'
            f'border:1px solid {C["border"]};border-radius:5px;'
            f'padding:4px 8px;font-size:12px;}}'
            f'QComboBox::drop-down{{border:none;}}')
        self.combo_tag.currentTextChanged.connect(self._on_tag_changed)
        # 預填 tag
        idx = self.combo_tag.findText(self.init_tag)
        if idx >= 0:
            self.combo_tag.setCurrentIndex(idx)
        lay.addWidget(self.combo_tag)

        # 標籤
        lay.addWidget(QLabel('標籤名稱：'))
        self.edit_label = QLineEdit()
        self.edit_label.setPlaceholderText('例如：AFib onset / Pacing / 心搏過速...')
        self.edit_label.setText(self.init_label)
        lay.addWidget(self.edit_label)

        # 備註
        lay.addWidget(QLabel('備註（可留空）：'))
        self.edit_note = QLineEdit()
        self.edit_note.setPlaceholderText('補充說明...')
        self.edit_note.setText(self.init_note)
        lay.addWidget(self.edit_note)

        # 按鈕
        btn_row = QHBoxLayout()
        btn_ok = QPushButton('✅ 儲存變更' if self.edit_mode else '✅ 儲存時間戳記')
        btn_ok.setObjectName('btn_success')
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton('取消')
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        lay.addLayout(btn_row)

    def _on_tag_changed(self, tag: str):
        if tag and not self.edit_label.text().strip() and not self.edit_mode:
            self.edit_label.setText(tag)

    def get_data(self):
        return self.edit_label.text().strip(), self.edit_note.text().strip(), self.combo_tag.currentText()


# ══════════════════════════════════════════════════════════════════════════════
# Excel 實驗記錄匯入
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_event_label(action, cl, srp) -> str:
    action = str(action or '').strip()
    if action.lower().startswith('a '):
        action = action[2:]
    label = action
    if cl is not None:
        label += f' {cl}'
    if str(srp or '').strip().lower() == 'p':
        label += 'p'
    return label.strip()


def parse_domap(xlsx_path: str) -> list[dict]:
    """解析 dOMAP 分頁，回傳所有有 OMAP# 的事件列表。"""
    try:
        import openpyxl
    except ImportError:
        raise ImportError('請先安裝 openpyxl：pip3 install openpyxl')

    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    if 'dOMAP' not in wb.sheetnames:
        raise ValueError("找不到 'dOMAP' 分頁，請確認 Excel 檔案格式")

    ws = wb['dOMAP']
    all_rows = list(ws.iter_rows(values_only=True))

    # 預先解析每列的時間字串（None 表示該列無時間值）
    row_times = []
    for row in all_rows:
        time_val = row[0] if len(row) > 0 else None
        if time_val is not None:
            try:
                row_times.append(str(int(float(str(time_val)))).zfill(4))
            except (ValueError, TypeError):
                row_times.append(None)
        else:
            row_times.append(None)

    events = []

    for i, row in enumerate(all_rows):
        omap_no  = row[1] if len(row) > 1 else None
        action   = row[2] if len(row) > 2 else None
        cl       = row[3] if len(row) > 3 else None
        srp      = row[4] if len(row) > 4 else None
        note_val = row[5] if len(row) > 5 else None

        # 只保留有 OMAP# 且為數字、且 Action 為 'SR' 的列
        if omap_no is None:
            continue
        omap_str = str(omap_no).strip()
        if not omap_str or not omap_str.isdigit():
            continue
        if str(action or '').strip() != 'SR':
            continue

        # 找 SR 行下方最近的時間戳記
        next_time_str = None
        for j in range(i + 1, len(all_rows)):
            if row_times[j] is not None:
                next_time_str = row_times[j]
                break

        label = _fmt_event_label(action, cl, srp)
        if not label:
            label = f'#{omap_str}'

        events.append({
            'omap_no':  omap_str,
            'time_str': next_time_str,
            'label':    label,
            'note':     str(note_val or '').strip(),
        })

    return events


class ExcelImportDialog(QDialog):
    def __init__(self, events: list[dict], ecg_data, parent=None):
        super().__init__(parent)
        self.events   = events
        self.abf_data = ecg_data   # 保持內部命名相容
        self.resolved = []
        self.setWindowTitle('匯入實驗記錄')
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setMinimumHeight(420)
        self._resolve()
        self._build()

    def _resolve(self):
        import datetime as dt
        t0  = self.abf_data.rec_datetime if self.abf_data else None
        dur = self.abf_data.duration     if self.abf_data else None

        for ev in self.events:
            ts       = ev['time_str']
            t_sec    = None
            abs_str  = '—'
            warn     = ''

            if not t0:
                warn = '⚠ ABF 無時間'
            elif not ts or len(ts) < 4:
                warn = '⚠ 無時間資訊'
            else:
                try:
                    h = int(ts[:2]);  m = int(ts[2:4])
                    target  = t0.replace(hour=h, minute=m, second=0, microsecond=0)
                    if target < t0:
                        target += dt.timedelta(days=1)
                    abs_str = target.strftime('%H:%M:%S')
                    t_sec   = data_rel_from_datetime(self.abf_data, target)
                    if dur and not (0 <= t_sec <= dur):
                        warn  = '⚠ 超出錄音範圍'
                        t_sec = max(0.0, min(dur, t_sec))
                except Exception:
                    warn = '⚠ 時間解析失敗'

            self.resolved.append({**ev, 't_sec': t_sec, 'abs_str': abs_str, 'warn': warn})

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lay.setContentsMargins(12, 12, 12, 12)

        t0        = self.abf_data.rec_datetime if self.abf_data else None
        t0_str    = t0.strftime('%H:%M:%S') if t0 else '（無時間資訊）'
        valid_cnt = sum(1 for r in self.resolved if r['t_sec'] is not None)

        lbl_info = QLabel(
            f'ABF 錄音開始：<b style="color:{C["accent"]}">{t0_str}</b>　　'
            f'找到 <b>{len(self.resolved)}</b> 筆事件，'
            f'<b style="color:{C["green"]}">{valid_cnt}</b> 筆可匯入')
        lbl_info.setTextFormat(Qt.TextFormat.RichText)
        lbl_info.setStyleSheet(f'color:{C["text"]}; font-size:12px;')
        lay.addWidget(lbl_info)

        self.list_w = QListWidget()
        self.list_w.setMinimumHeight(280)
        self.list_w.setStyleSheet(
            f'QListWidget{{background:{C["panel"]};border:1px solid {C["border"]};'
            f'border-radius:6px;font-size:11px;}}'
            f'QListWidget::item{{padding:3px 6px;}}'
            f'QListWidget::item:selected{{background:{C["accent"]};color:{C["bg"]}}}')

        for r in self.resolved:
            text = (f"#{r['omap_no']}  {r['abs_str']}"
                    f"  |  {r['label']}")
            if r['note']:
                text += f"  ({r['note']})"
            if r['warn']:
                text += f"  {r['warn']}"
            item = QListWidgetItem(text)
            if r['t_sec'] is None:
                item.setForeground(QColor(C['dim']))
            elif r['warn']:
                item.setForeground(QColor(C['yellow']))
            else:
                item.setForeground(QColor(C['text']))
            self.list_w.addItem(item)

        lay.addWidget(self.list_w)

        lbl_note = QLabel('灰色項目（無時間或超出範圍）不會被匯入')
        lbl_note.setStyleSheet(f'color:{C["dim"]}; font-size:11px;')
        lay.addWidget(lbl_note)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton(f'✅ 匯入 {valid_cnt} 筆時間戳記')
        btn_ok.setObjectName('btn_success')
        btn_ok.setEnabled(valid_cnt > 0)
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton('取消')
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        lay.addLayout(btn_row)

    def get_valid_events(self):
        return [r for r in self.resolved if r['t_sec'] is not None]


# ══════════════════════════════════════════════════════════════════════════════
# 波形顯示區
# ══════════════════════════════════════════════════════════════════════════════
class WaveformWidget(QWidget):
    measure_updated = pyqtSignal(list)     # 傳出測量點列表
    view_changed    = pyqtSignal(float, float)
    peaks_edited    = pyqtSignal(object, dict)   # 手動新增/刪除 R-peak 後：peaks, stats
    mark_clicked    = pyqtSignal(float)          # 點位模式下點到的時間
    skna_track_edit = pyqtSignal(dict)           # 在軌道標題列改了 SKNA 來源／帶通

    def __init__(self):
        super().__init__()
        self.data = None   # ABFData | EDFData
        self.ch_idx   = 0
        self.t_start  = 0.0
        self.t_end    = 10.0
        self.measure_mode = False
        self.measure_pts  = []      # [t_a, t_b]
        self.mark_mode    = False   # SKNA 時間點位標記模式
        self.marks        = []      # [{'t','name','kind'}]
        self._mark_items  = []
        self.review_regions = []      # [(t0, t1, 'artifact'|'keep'|None)]
        self.review_cur     = None    # 目前判讀中的 (t0, t1)
        self._review_items  = []
        self.peak_edit_mode = False
        self.line_a: InfiniteLine | None = None
        self._peaks_cache    = None
        self._ts_items_cache = []
        self.y_scale         = 1.0
        self._y_auto         = True
        self._y_auto0        = True    # 軌道 1 是否處於自動縱軸縮放
        self._y_auto1        = True    # 軌道 2 是否處於自動縱軸縮放
        self._y_auto2        = True    # 軌道 3（SKNA 第二帶通）自動縱軸縮放
        self.dual_mode       = True    # 預設雙通道顯示
        self.ch_idx2         = 1          # 第二軌道通道索引
        self._drawing        = False      # 防止重入
        self._draw_dirty     = False      # 重入時記下「畫完要再補一次」
        self._draw_req       = False      # 已排定一次合併重畫
        self._last_draw_ms   = 0.0        # 上一次重畫耗時，連發平移用來自我節流
        self._lbl_cache      = {}         # 軸標籤快取：內容沒變就不重設
        self._limits_dur     = None       # setLimits 只在檔案長度改變時呼叫
        self.notch_freq      = 0.0        # 工頻陷波：0=關閉, 50=50 Hz, 60=60 Hz
        self.bp_enabled      = False      # 帶通濾波器啟用
        self.bp_lo           = 1.0        # 帶通下限 Hz
        self.bp_hi           = 150.0      # 帶通上限 Hz
        self.skna_enabled    = False      # 軌道 2 改顯示 SKNA
        self.skna_cfg        = dict(SKNA_DEFAULTS)
        self.s3_sna          = None       # S3 分解後的 SKNA（整條通道）
        self.s3_ecg          = None       # S3 分離出的心電成分
        self.show_s3_ecg     = False      # 軌道 1 疊上分離出的心電成分
        self._build()

    def _y_buttons(self, track: int):
        """軌道標題列上的縱軸控制（放大／縮小／自動）。

        原本放在工具列，但它們是針對某一軌的操作，放在該軌的標題旁邊
        比較直覺，也不會在切換頁面時跟著消失。
        """
        keys = {0: ('W', 'S'), 1: ('E', 'C')}.get(track, ('', ''))
        style = (
            f'QPushButton{{background:{C["panel"]};color:{C["accent"]};'
            f'border:1px solid {C["border"]};border-radius:4px;'
            f'padding:0px 6px;font-size:11px;min-height:18px;max-height:20px;}}'
            f'QPushButton:hover{{background:{C["border"]};color:{C["text"]}}}'
            f'QPushButton:pressed{{background:{C["accent"]};color:{C["bg"]}}}')
        out = []
        for text, tip, cb in (
                ('▲', '縱軸放大' + (f' ({keys[0]})' if keys[0] else ''),
                 lambda _=0, t=track: self.zoom_y(2.0, t)),
                ('▼', '縱軸縮小' + (f' ({keys[1]})' if keys[1] else ''),
                 lambda _=0, t=track: self.zoom_y(0.5, t)),
                ('自動', '縱軸自動縮放',
                 lambda _=0, t=track: self.reset_y(t))):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setStyleSheet(style)
            b.setFixedHeight(20)
            b.setMaximumWidth(34 if text == '自動' else 26)
            b.clicked.connect(cb)
            out.append(b)
        return out

    def _mode_combo(self, track: int) -> QComboBox:
        """S3 模式下，軌道標題列上的「帶通／S3」顯示選單。"""
        cb = QComboBox()
        cb.addItems(['Bandpass', 'S3'])
        cb.setMaximumHeight(22)
        cb.setStyleSheet(
            f'QComboBox{{background:{C["panel"]};color:{C["orange"]};'
            f'border:1px solid {C["border"]};border-radius:4px;'
            f'padding:1px 6px;font-size:11px;}}'
            f'QComboBox::drop-down{{border:none;}}')
        cb.setToolTip(f'軌道 {track + 1} 顯示 Bandpass（帶通）或 S3 分解結果。'
                      '選 S3 時若還沒做過 S3 分解，會自動對整個檔案分解。')
        cb.currentIndexChanged.connect(lambda i, t=track: self._on_mode_edit(t, i))
        cb.setVisible(False)
        return cb

    def _s3_ok_for(self, band: int) -> bool:
        """S3 是對軌道 2 的來源通道分解的；軌道 3 要同一通道才能顯示 S3。"""
        if band == 1:
            return True
        return skna_band_cfg(self.skna_cfg, 2).get('src_ch') == self.skna_cfg.get('src_ch')

    def _track_shows_s3(self, band: int) -> bool:
        cfg = self.skna_cfg
        return (cfg.get('method') == 's3'
                and cfg.get('disp1' if band == 1 else 'disp2', 'bpf') == 's3'
                and self._s3_ok_for(band))

    def _on_mode_edit(self, track: int, idx: int):
        key = 'disp1' if track == 1 else 'disp2'
        val = 's3' if idx == 1 else 'bpf'
        shown = 's3' if self._track_shows_s3(track) else 'bpf'
        if shown != val:
            self.skna_track_edit.emit({key: val})

    def _band_widget(self, track: int):
        """SKNA 軌道標題列上的帶通欄位：[低截止]–[高截止] Hz。"""
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(4, 0, 4, 0)
        h.setSpacing(3)
        style = (f'QDoubleSpinBox{{background:{C["panel"]};color:{C["accent"]};'
                 f'border:1px solid {C["border"]};border-radius:4px;'
                 f'padding:0px 2px;font-size:11px;}}'
                 # 顯示 S3 時帶通欄位與此軌無關、不可修改：整組變灰
                 f'QDoubleSpinBox:disabled{{color:{C["dim"]};background:{C["bg"]};'
                 f'border:1px solid {C["border"]};}}')
        spins = []
        for tip in ('低截止 (Hz)', '高截止 (Hz)'):
            s = QDoubleSpinBox()
            s.setRange(1, 20000); s.setDecimals(0); s.setSingleStep(50)
            s.setKeyboardTracking(False)       # 打完數字（Enter／離開）才套用
            s.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            s.setFixedWidth(52); s.setMaximumHeight(22)
            s.setStyleSheet(style)
            s.setToolTip(f'軌道 {track + 1} 帶通{tip}；輸入後按 Enter 套用')
            s.valueChanged.connect(lambda _v, t=track: self._on_band_edit(t))
            spins.append(s)
        dash = QLabel('–'); hz = QLabel('Hz')
        for l_ in (dash, hz):
            l_.setStyleSheet(f'QLabel{{color:{C["dim"]}; font-size:11px;}}'
                             f'QLabel:disabled{{color:{C["border"]};}}')
        h.addWidget(spins[0]); h.addWidget(dash); h.addWidget(spins[1]); h.addWidget(hz)
        w.setVisible(False)
        return w, spins[0], spins[1]

    def _build(self):
        lay = QVBoxLayout(self)
        # 左、上、右、下留白：避免軌道標題與縱軸標籤貼齊視窗邊緣
        lay.setContentsMargins(16, 8, 10, 10)
        lay.setSpacing(4)

        # ── CH0 header row ──
        hdr0 = QHBoxLayout()
        hdr0.setContentsMargins(0, 2, 0, 0)
        lbl_ch0 = QLabel('軌道 1：')
        lbl_ch0.setStyleSheet(f'color:{C["dim"]}; font-size:11px;')
        hdr0.addWidget(lbl_ch0)
        self.combo_ch0 = QComboBox()
        self.combo_ch0.setMinimumWidth(130)
        self.combo_ch0.setMaximumHeight(22)
        self.combo_ch0.setStyleSheet(
            f'QComboBox{{background:{C["panel"]};color:{C["accent"]};'
            f'border:1px solid {C["border"]};border-radius:4px;'
            f'padding:1px 6px;font-size:11px;}}'
            f'QComboBox::drop-down{{border:none;}}')
        self.combo_ch0.currentIndexChanged.connect(self._on_combo_ch0)
        hdr0.addWidget(self.combo_ch0)
        for b in self._y_buttons(0):
            hdr0.addWidget(b)
        hdr0.addStretch()
        lay.addLayout(hdr0)

        # ── CH0 波形（上軌）──
        self.plot_wave = PlotWidget()
        self.plot_wave.setLabel('left', '')
        self.plot_wave.showGrid(x=True, y=True, alpha=0.2)
        self.plot_wave.setDownsampling(auto=True, mode='peak')
        self.plot_wave.setClipToView(True)
        self.plot_wave.getPlotItem().getAxis('bottom').setStyle(showValues=False)
        self.plot_wave.scene().sigMouseClicked.connect(self._on_click)
        # 停用內建滾輪縮放，改用工具列按鈕控制
        self.plot_wave.getViewBox().setMouseEnabled(x=False, y=False)
        self.plot_wave.setMinimumHeight(60)
        lay.addWidget(self.plot_wave, stretch=2)

        # ── CH1 header row ──
        hdr1 = QHBoxLayout()
        hdr1.setContentsMargins(0, 2, 0, 0)
        self.lbl_ch1 = QLabel('軌道 2：')
        self.lbl_ch1.setStyleSheet(f'color:{C["dim"]}; font-size:11px;')
        hdr1.addWidget(self.lbl_ch1)
        self.combo_ch1 = QComboBox()
        self.combo_ch1.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_ch1.setMinimumContentsLength(10)
        self.combo_ch1.setMinimumWidth(90)
        self.combo_ch1.setMaximumHeight(22)
        self.combo_ch1.setStyleSheet(self.combo_ch0.styleSheet())
        self.combo_ch1.currentIndexChanged.connect(self._on_combo_ch1)
        hdr1.addWidget(self.combo_ch1)
        self.mode_cb2 = self._mode_combo(1)
        hdr1.addWidget(self.mode_cb2)
        self.band_w2, self.spin_t2_lo, self.spin_t2_hi = self._band_widget(1)
        hdr1.addWidget(self.band_w2)
        self.lbl_a2 = QLabel('')
        self.lbl_a2.setStyleSheet(f'color:{C["orange"]}; font-size:11px;')
        self.lbl_a2.setToolTip('目前畫面範圍內的 aSKNA')
        self.lbl_a2.setSizePolicy(QSizePolicy.Policy.Ignored,
                                   QSizePolicy.Policy.Preferred)
        self.lbl_a2.setMinimumWidth(0)
        self.lbl_a2.setVisible(False)
        hdr1.addWidget(self.lbl_a2)
        for b in self._y_buttons(1):
            hdr1.addWidget(b)
        hdr1.addStretch()
        self.hdr1_widget = QWidget()
        self.hdr1_widget.setLayout(hdr1)
        self.hdr1_widget.setVisible(False)
        lay.addWidget(self.hdr1_widget)

        # ── CH1 波形（下軌）──
        self.plot_wave2 = PlotWidget()
        self.plot_wave2.setLabel('left', '')
        self.plot_wave2.setLabel('bottom', '時間 (s)')
        self.plot_wave2.showGrid(x=True, y=True, alpha=0.2)
        self.plot_wave2.setDownsampling(auto=True, mode='peak')
        self.plot_wave2.scene().sigMouseClicked.connect(self._on_click2)
        self.plot_wave2.getViewBox().setMouseEnabled(x=False, y=False)
        self.plot_wave2.setVisible(False)
        self.plot_wave2.setMinimumHeight(60)
        lay.addWidget(self.plot_wave2, stretch=2)

        # ── 軌道 3：SKNA 第二組帶通（只在 SKNA 頁顯示，取代 RR 軌）──
        hdr3 = QHBoxLayout()
        hdr3.setContentsMargins(0, 2, 0, 0)
        self.lbl_ch3 = QLabel('軌道 3（SKNA）：')
        self.lbl_ch3.setStyleSheet(f'color:{C["orange"]}; font-size:11px;')
        hdr3.addWidget(self.lbl_ch3)
        self.combo_ch3 = QComboBox()
        self.combo_ch3.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_ch3.setMinimumContentsLength(10)
        self.combo_ch3.setMinimumWidth(90)
        self.combo_ch3.setMaximumHeight(22)
        self.combo_ch3.setStyleSheet(self.combo_ch0.styleSheet())
        self.combo_ch3.setToolTip('軌道 3 的 SKNA 來源通道')
        self.combo_ch3.currentIndexChanged.connect(self._on_combo_ch3)
        hdr3.addWidget(self.combo_ch3)
        self.mode_cb3 = self._mode_combo(2)
        hdr3.addWidget(self.mode_cb3)
        self.band_w3, self.spin_t3_lo, self.spin_t3_hi = self._band_widget(2)
        self.band_w3.setVisible(True)
        hdr3.addWidget(self.band_w3)
        self.lbl_a3 = QLabel('')
        self.lbl_a3.setStyleSheet(f'color:{C["orange"]}; font-size:11px;')
        self.lbl_a3.setToolTip('目前畫面範圍內的 aSKNA')
        self.lbl_a3.setSizePolicy(QSizePolicy.Policy.Ignored,
                                   QSizePolicy.Policy.Preferred)
        self.lbl_a3.setMinimumWidth(0)
        hdr3.addWidget(self.lbl_a3)
        for b in self._y_buttons(2):
            hdr3.addWidget(b)
        hdr3.addStretch()
        self.hdr3_widget = QWidget()
        self.hdr3_widget.setLayout(hdr3)
        self.hdr3_widget.setVisible(False)
        lay.addWidget(self.hdr3_widget)

        self.plot_wave3 = PlotWidget()
        self.plot_wave3.setLabel('left', '')
        self.plot_wave3.setLabel('bottom', '時間 (s)')
        self.plot_wave3.showGrid(x=True, y=True, alpha=0.2)
        self.plot_wave3.setDownsampling(auto=True, mode='peak')
        self.plot_wave3.scene().sigMouseClicked.connect(self._on_click3)
        self.plot_wave3.getViewBox().setMouseEnabled(x=False, y=False)
        self.plot_wave3.setVisible(False)
        self.plot_wave3.setMinimumHeight(60)
        lay.addWidget(self.plot_wave3, stretch=2)

        # ── RR tachogram（最下方；SKNA 頁改顯示軌道 3）──
        self.plot_rr = PlotWidget()
        self.plot_rr.setLabel('left', 'RR (ms)')
        self.plot_rr.setLabel('bottom', '時間 (s)')
        self.plot_rr.showGrid(x=True, y=True, alpha=0.2)
        self.plot_rr.setXLink(self.plot_wave)
        self.plot_rr.setMinimumHeight(40)
        lay.addWidget(self.plot_rr, stretch=1)

        # 三個圖的左軸固定同寬，繪圖區才會對齊。
        # 否則刻度文字長度不同（例如 300 vs -10），各圖的繪圖區起點會差好幾
        # 個像素，同一個時間點在不同軌道上的水平位置就對不起來，
        # 疊圖、點位線與波形之間的對照全都會歪掉。
        for _pl in (self.plot_wave, self.plot_wave2, self.plot_wave3, self.plot_rr):
            _pl.getPlotItem().getAxis('left').setWidth(62)
            # 拖進來的檔案交給主視窗處理（詢問是否開啟新檔案）
            _pl.setAcceptDrops(False)
            _pl.viewport().setAcceptDrops(False)

        # 預建持久曲線
        self._curve_wave  = self.plot_wave.plot([], [], pen=pg.mkPen(C['wave'], width=1.0))
        self._curve_wave2 = self.plot_wave2.plot([], [], pen=pg.mkPen(C['wave_alt'], width=1.0))
        # SKNA 整流包絡（疊在軌道 2 的 rSNA 上）
        self._curve_skna_env = self.plot_wave2.plot(
            [], [], pen=pg.mkPen(C['orange'], width=1.8))
        self._curve_skna_env.setZValue(10)
        self._curve_wave3 = self.plot_wave3.plot([], [], pen=pg.mkPen(C['wave_alt'], width=1.0))
        self._curve_skna_env3 = self.plot_wave3.plot(
            [], [], pen=pg.mkPen(C['orange'], width=1.8))
        self._curve_skna_env3.setZValue(10)
        # S3 分離出的心電成分，疊在軌道 1 上用來確認分解是否合理
        self._curve_s3_ecg = self.plot_wave.plot(
            [], [], pen=pg.mkPen(C['red'], width=1.2))
        self._curve_s3_ecg.setZValue(5)
        self._curve_peaks = self.plot_wave.plot([], [], pen=None, symbol='t1',
                                                 symbolSize=9, symbolBrush=C['red'])
        self._curve_rr     = self.plot_rr.plot([], [], pen=pg.mkPen(C['green'], width=1.5))
        self._curve_rr_pts = self.plot_rr.plot([], [], pen=None, symbol='o',
                                                symbolSize=4, symbolBrush=C['wave_alt'])

        # 測量線（CH0 上）
        self._line_a = InfiniteLine(pos=0, angle=90, pen=pg.mkPen(C['meas_a'] + 'cc', width=1.5))
        self._line_b = InfiniteLine(pos=0, angle=90, pen=pg.mkPen(C['meas_b'] + 'cc', width=1.5))
        self._region_meas = LinearRegionItem(
            values=[0, 1], brush=pg.mkBrush(QColor(0, 0, 0, 0)), movable=False,
            pen=pg.mkPen(QColor(0, 0, 0, 0)))
        self._line_a.setVisible(False)
        self._line_b.setVisible(False)
        self._region_meas.setVisible(False)
        self.plot_wave.addItem(self._line_a)
        self.plot_wave.addItem(self._line_b)
        self.plot_wave.addItem(self._region_meas)

        # 測量線（CH1 上，同步）
        self._line_a2 = InfiniteLine(pos=0, angle=90, pen=pg.mkPen(C['meas_a'] + 'cc', width=1.5))
        self._line_b2 = InfiniteLine(pos=0, angle=90, pen=pg.mkPen(C['meas_b'] + 'cc', width=1.5))
        self._region_meas2 = LinearRegionItem(
            values=[0, 1], brush=pg.mkBrush(QColor(0, 0, 0, 0)), movable=False,
            pen=pg.mkPen(QColor(0, 0, 0, 0)))
        self._line_a2.setVisible(False)
        self._line_b2.setVisible(False)
        self._region_meas2.setVisible(False)
        self.plot_wave2.addItem(self._line_a2)
        self.plot_wave2.addItem(self._line_b2)
        self.plot_wave2.addItem(self._region_meas2)

        # 測量線（軌道 3 上，同步）
        self._line_a3 = InfiniteLine(pos=0, angle=90, pen=pg.mkPen(C['meas_a'] + 'cc', width=1.5))
        self._line_b3 = InfiniteLine(pos=0, angle=90, pen=pg.mkPen(C['meas_b'] + 'cc', width=1.5))
        self._region_meas3 = LinearRegionItem(
            values=[0, 1], brush=pg.mkBrush(QColor(0, 0, 0, 0)), movable=False,
            pen=pg.mkPen(QColor(0, 0, 0, 0)))
        for _it in (self._line_a3, self._line_b3, self._region_meas3):
            _it.setVisible(False)
            self.plot_wave3.addItem(_it)

        # Slider 防抖動
        self._slider_timer = QTimer()
        self._slider_timer.setSingleShot(True)
        self._slider_timer.timeout.connect(self._draw)


        # 底部 slider
        slider_row = QHBoxLayout()
        slider_row.addWidget(QLabel('位置：'))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(10000)
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self._on_slider)
        slider_row.addWidget(self.slider)
        self.lbl_pos = QLabel('00:00.000')
        self.lbl_pos.setStyleSheet(f'color:{C["accent"]}; font-size:11px; min-width:80px;')
        slider_row.addWidget(self.lbl_pos)
        lay.addLayout(slider_row)
    # ── 資料載入 ─────────────────────────────────────────────────────────────

    def load(self, data):
        self._clear_ts_items()
        self._reset_label_cache()   # 新檔案，舊的軸標題一律重設
        self.data = data
        self.ch_idx   = 0
        self.ch_idx2  = min(1, data.n_ch - 1)
        self.t_start  = 0.0
        self.t_end    = min(10.0, data.duration)
        self._peaks_cache    = None
        self.measure_pts     = []
        self._y_auto0        = True
        self._y_auto1        = True
        self._y_auto2        = True
        self._populate_combos()
        # 監聽 ViewBox 的 X 範圍變化（鼠標拖曳 / 滾輪縮放）
        self._draw()

    def _populate_combos(self):
        if self.data is None:
            return
        for combo in [self.combo_ch0, self.combo_ch1, self.combo_ch3]:
            combo.blockSignals(True)
            combo.clear()
            for i in range(self.data.n_ch):
                combo.addItem(f'CH{i}: {self.data.ch_names[i]}')
            combo.blockSignals(False)
        self.combo_ch0.setCurrentIndex(self.ch_idx)
        self.combo_ch1.setCurrentIndex(self.ch_idx2)

    def _on_combo_ch0(self, idx: int):
        self.ch_idx = idx
        self._peaks_cache = None
        self._y_auto0 = True
        self._draw()

    def _on_combo_ch3(self, idx: int):
        cur = skna_band_cfg(self.skna_cfg, 2).get('src_ch')
        if idx >= 0 and idx != cur:
            self.skna_track_edit.emit({'src_ch2': idx})

    def _on_band_edit(self, track: int):
        lo_s, hi_s = ((self.spin_t2_lo, self.spin_t2_hi) if track == 1
                      else (self.spin_t3_lo, self.spin_t3_hi))
        lo, hi = lo_s.value(), hi_s.value()
        if lo >= hi:
            self._sync_skna_headers()     # 不合理的範圍就還原
            return
        keys = ('bp_lo', 'bp_hi') if track == 1 else ('bp_lo2', 'bp_hi2')
        if (abs(lo - float(self.skna_cfg.get(keys[0], 0))) < 0.5 and
                abs(hi - float(self.skna_cfg.get(keys[1], 0))) < 0.5):
            return
        self.skna_track_edit.emit({keys[0]: lo, keys[1]: hi})

    def _sync_skna_headers(self):
        """把目前 SKNA 設定（來源、帶通）同步到軌道 2／3 標題列。"""
        cfg = self.skna_cfg
        pairs = ((self.spin_t2_lo, cfg.get('bp_lo', 500.0)),
                 (self.spin_t2_hi, cfg.get('bp_hi', 1000.0)),
                 (self.spin_t3_lo, cfg.get('bp_lo2', 500.0)),
                 (self.spin_t3_hi, cfg.get('bp_hi2', 1500.0)))
        for s, v in pairs:
            s.blockSignals(True); s.setValue(float(v)); s.blockSignals(False)
        src2 = skna_band_cfg(cfg, 2).get('src_ch')
        if src2 is not None and 0 <= src2 < self.combo_ch3.count():
            self.combo_ch3.blockSignals(True)
            self.combo_ch3.setCurrentIndex(src2)
            self.combo_ch3.blockSignals(False)
        s3 = cfg.get('method') == 's3'
        on_skna = self.skna_enabled and cfg.get('src_ch') is not None
        for band, cb, w_ in ((1, self.mode_cb2, self.band_w2),
                             (2, self.mode_cb3, self.band_w3)):
            ok = self._s3_ok_for(band)
            cb.blockSignals(True)
            cb.model().item(1).setEnabled(ok)
            cb.setCurrentIndex(1 if self._track_shows_s3(band) else 0)
            cb.blockSignals(False)
            cb.setVisible(on_skna)
            if band == 2 and not ok:
                cb.setToolTip('S3 是對軌道 2 的來源通道分解的；軌道 3 要選同一個'
                              '通道才能顯示 S3')
            shows = self._track_shows_s3(band)
            # 顯示 S3 時帶通欄位沒有作用（S3 輸出不再帶通），只用於 BPF 欄位
            for s_ in w_.findChildren(QDoubleSpinBox) + w_.findChildren(QLabel):
                s_.setEnabled(not shows)
            w_.setToolTip('顯示 S3 時帶通設定不影響畫面，只用於區間分析的 BPF 欄位'
                          if shows else '')

    def _on_combo_ch1(self, idx: int):
        if self.skna_enabled and self.skna_cfg.get('src_ch') is not None:
            # SKNA 模式下這個選單就是軌道 2 的 SKNA 來源
            if idx != self.skna_cfg.get('src_ch'):
                self.skna_track_edit.emit({'src_ch': idx})
            return
        self.ch_idx2 = idx
        self._y_auto1 = True
        self._draw()

    def set_channel(self, ch: int):
        self.ch_idx = ch
        self.combo_ch0.blockSignals(True)
        self.combo_ch0.setCurrentIndex(ch)
        self.combo_ch0.blockSignals(False)
        self._peaks_cache = None
        self._draw()

    # ── 繪圖 ─────────────────────────────────────────────────────────────────

    def _pt_budget(self) -> int:
        """依繪圖區實際像素寬決定一條線要畫幾個點。

        螢幕上一個像素只能畫一條線，所以不需要把十萬點全部餵進去。
        但也不能砍太兇：SKNA 是高頻雜訊訊號，判讀時看的就是「雜訊底噪
        有多厚、心跳尖峰突出多少」這個對比。min/max 抽稀雖然保得住極值，
        區塊切太大時每個像素欄能分到的點不夠，畫出來的帶狀範圍會失真。

        實測（1950 px 畫布、10 秒視窗、10 kHz）每個像素欄上下範圍的誤差：
            3 點/像素  → 13.3%      心跳突出度 5.90（真值 6.89）
            6 點/像素  →  4.9%
           10 點/像素  →  0.9%      心跳突出度 6.84（真值 6.89）
        而 6,000 與 20,000 點的平移耗時差在量測誤差內（都是 66–92 ms），
        所以取 10 點/像素：忠實度幾乎等同完整解析度，速度沒有代價。
        """
        try:
            w = int(self.plot_wave.getPlotItem().getViewBox().width())
        except Exception:
            w = 0
        if w <= 0:
            w = 1200
        if getattr(self, '_fast', False):
            # 按住往前／往後連續移動時先用草稿解析度（每像素 3 點），
            # 每一步畫得快、放開時跟得上；停下來後立刻用完整解析度重畫
            return int(min(8_000, max(3_000, w * 3)))
        return int(min(24_000, max(8_000, w * 10)))

    def _reset_label_cache(self):
        """換檔案或切換顯示模式時清掉軸標籤快取。

        快取是用「上次寫進去的文字」來判斷要不要重設。只要有人繞過
        _set_ylabel 直接改標籤，快取就會跟畫面脫鉤，之後該更新的標籤
        會被誤判成「沒變」而不更新，畫面上就留著上一個檔案的舊標題。
        """
        self._lbl_cache = {}

    def _set_ylabel(self, plot, text: str):
        """只有在文字真的變了才呼叫 setLabel。

        setLabel 會讓 pyqtgraph 丟掉整個座標軸的繪圖快取並重新產生，
        實測是平移時最貴的單一項目；但平移時標籤內容其實沒變。
        """
        k = id(plot)
        if self._lbl_cache.get(k) != text:
            plot.setLabel('left', text)
            self._lbl_cache[k] = text

    def _draw(self):
        if self.data is None:
            return
        if self._drawing:
            # 上一次還沒畫完（例如連發平移），記下來，畫完再補一次，
            # 否則畫面會停在舊位置
            self._draw_dirty = True
            return
        self._drawing = True
        _t_begin = time.perf_counter()

        MAX = self._pt_budget()
        t0 = self.t_start
        t1 = self.t_end

        vb = self.plot_wave.getViewBox()
        vb.blockSignals(True)

        # ── CH0 資料 ──
        ch0 = self.ch_idx
        t, y = self.data.segment(ch0, t0, t1)
        if len(t) == 0:
            vb.blockSignals(False)
            self._drawing = False
            self._draw_dirty = False
            return
        fs0 = self.data.fs_of(ch0)
        if self.notch_freq > 0 and len(y) > 10:
            y = apply_notch(y, fs0, self.notch_freq)
        if self.bp_enabled and len(y) > 10:
            y = apply_bandpass(y, fs0, self.bp_lo, self.bp_hi)
        if len(t) > MAX:
            # 用 min/max 抽稀而不是 y[::step]：等間隔取樣會漏掉尖銳的 QRS
            # 與高頻成分，畫出來的振幅比實際小
            t, y = peak_decimate(t, y, MAX)

        unit0 = self.data.ch_units[ch0]
        self._set_ylabel(self.plot_wave,
                         f'CH{ch0}: {self.data.ch_names[ch0]} ({unit0})')
        # 先設定範圍，再 setData（clipToView 裁切依賴當前 viewRange）
        self.plot_wave.setXRange(t0, t1, padding=0)
        if self._limits_dur != self.data.duration:
            self.plot_wave.setLimits(xMin=0, xMax=self.data.duration)
            self._limits_dur = self.data.duration
        self._curve_wave.setData(t, y)

        # S3 分離出的心電成分：只在軌道 1 正好顯示 SKNA 來源通道時才疊，
        # 否則兩條線來自不同通道，疊在一起沒有意義
        s3_overlay = None
        if (self.show_s3_ecg and self.s3_ecg is not None
                and ch0 == self.skna_cfg.get('src_ch')):
            _t3, y3 = self.data.segment(ch0, t0, t1)
            i0 = max(0, int(t0 * fs0))
            e3 = np.asarray(self.s3_ecg[i0:i0 + len(y3)], dtype=np.float64)
            t3 = np.arange(i0, i0 + len(e3)) / fs0

            # S3 的心電成分是在「高通之後」的訊號上重建的，沒有原始通道的
            # 直流偏移（這批資料大約 -4 mV）。直接畫會落在 0 附近，跟軌道 1
            # 的原始波形差好幾 mV，整條線跑到畫面外看起來就像沒有作用。
            # 這裡把它平移到原始訊號的準位，兩條線才疊得起來、才能比對 QRS。
            if len(e3):
                fin_e = e3[np.isfinite(e3)]
                fin_y = y3[np.isfinite(y3)]
                if fin_e.size and fin_y.size:
                    e3 = e3 + (np.median(fin_y) - np.median(fin_e))
                # S3 只跑部分範圍時，未分解的區域是 NaN，畫出來會斷線，
                # 直接濾掉那些點
                ok = np.isfinite(e3)
                if not ok.all():
                    t3, e3 = t3[ok], e3[ok]
            if len(t3) > MAX:
                t3, e3 = peak_decimate(t3, e3, MAX)
            if len(t3):
                s3_overlay = e3
            self._curve_s3_ecg.setData(t3, e3)
        else:
            self._curve_s3_ecg.setData([], [])

        if self._y_auto0:
            self._auto_y_range(self.plot_wave, y, extra=s3_overlay)

        vb.blockSignals(False)

        # ── CH1 資料（同樣用 t0/t1，不受上面 setXRange 影響）──
        if self.dual_mode and self.data.n_ch > 1:
            if self.skna_enabled and self.skna_cfg.get('src_ch') is not None:
                t2, y2, env2 = self._draw_skna_track(t0, t1, MAX)
            else:
                env2 = None
                ch1 = self.ch_idx2
                t2, y2 = self.data.segment(ch1, t0, t1)
                fs1 = self.data.fs_of(ch1)
                if self.notch_freq > 0 and len(y2) > 10:
                    y2 = apply_notch(y2, fs1, self.notch_freq)
                if self.bp_enabled and len(y2) > 10:
                    y2 = apply_bandpass(y2, fs1, self.bp_lo, self.bp_hi)
                if len(t2) > MAX:
                    t2, y2 = peak_decimate(t2, y2, MAX)
                unit1 = self.data.ch_units[ch1]
                self._set_ylabel(
                    self.plot_wave2,
                    f'CH{ch1}: {self.data.ch_names[ch1]} ({unit1})')
                self._sync_hdr1()
            # 先設定範圍，再 setData（clipToView 會用當前 viewRange 裁切）
            actual_vr = self.plot_wave.getViewBox().viewRange()
            vb2 = self.plot_wave2.getViewBox()
            vb2.blockSignals(True)
            vb2.enableAutoRange(axis=vb2.XAxis, enable=False)
            vb2.setRange(xRange=actual_vr[0], padding=0)
            vb2.blockSignals(False)
            self._curve_wave2.setData(t2, y2)
            if env2 is not None:
                self._curve_skna_env.setData(*env2)
            else:
                self._curve_skna_env.setData([], [])
            if self._y_auto1:
                self._auto_y_range(self.plot_wave2, y2)
            self.plot_wave2.setVisible(True)
            # 標題列一律保留。SKNA 模式下只是把通道選單鎖起來（來源由 SKNA
            # 設定決定），▲ ▼ 自動 這些縱軸按鈕仍然要能用。
            self.hdr1_widget.setVisible(True)
            self._sync_hdr1()
            self.plot_rr.getPlotItem().getAxis('bottom').setStyle(showValues=False)
            three = self.skna_enabled and self.skna_cfg.get('src_ch') is not None
        else:
            self._curve_wave2.setData([], [])
            self._curve_skna_env.setData([], [])
            self.plot_wave2.setVisible(False)
            self.hdr1_widget.setVisible(False)
            self.plot_rr.getPlotItem().getAxis('bottom').setStyle(showValues=True)
            three = False

        # ── 軌道 3：SKNA 第二組帶通，SKNA 頁取代 RR 軌 ──
        if three:
            t3, y3, env3 = self._draw_skna_track(t0, t1, MAX, band=2)
            actual_vr = self.plot_wave.getViewBox().viewRange()
            vb3 = self.plot_wave3.getViewBox()
            vb3.blockSignals(True)
            vb3.enableAutoRange(axis=vb3.XAxis, enable=False)
            vb3.setRange(xRange=actual_vr[0], padding=0)
            vb3.blockSignals(False)
            self._curve_wave3.setData(t3, y3)
            self._curve_skna_env3.setData(*env3)
            if self._y_auto2:
                self._auto_y_range(self.plot_wave3, y3)
            self.plot_wave3.setVisible(True)
            self.hdr3_widget.setVisible(True)
            self.plot_rr.setVisible(False)
            self.plot_wave2.getPlotItem().showAxis('bottom', False)
        else:
            self._curve_wave3.setData([], [])
            self._curve_skna_env3.setData([], [])
            self.plot_wave3.setVisible(False)
            self.hdr3_widget.setVisible(False)
            self.plot_rr.setVisible(True)
            self.plot_wave2.getPlotItem().showAxis('bottom', True)

        # 更新測量線、時間戳記、點位、slider
        self._update_measure_lines()
        self._draw_timestamps()
        self._draw_marks()
        self._draw_review()
        self._update_slider()
        self.view_changed.emit(t0, t1)
        self._last_draw_ms = (time.perf_counter() - _t_begin) * 1000.0
        self._drawing = False
        if self._draw_dirty:
            self._draw_dirty = False
            QTimer.singleShot(0, self._draw)

    def _sync_hdr1(self):
        """依目前模式調整軌道 2 標題列。

        SKNA 模式下軌道 2 畫的是分析結果，來源通道由「SKNA 設定」決定，
        所以把通道選單鎖住並指向那個通道（避免顯示成無關的通道造成誤會），
        但縱軸的 ▲ ▼ 自動 仍然可用。
        """
        use_skna = self.skna_enabled and self.skna_cfg.get('src_ch') is not None
        if use_skna:
            src = self.skna_cfg['src_ch']
            self.lbl_ch1.setText('軌道 2（SKNA）：')
            self.lbl_ch1.setStyleSheet(
                f'color:{C["orange"]}; font-size:11px;')
            if 0 <= src < self.combo_ch1.count():
                self.combo_ch1.blockSignals(True)
                self.combo_ch1.setCurrentIndex(src)
                self.combo_ch1.blockSignals(False)
            self.combo_ch1.setEnabled(True)
            self.combo_ch1.setToolTip('軌道 2 的 SKNA 來源通道')
            self.band_w2.setVisible(True)
            self.lbl_a2.setVisible(True)
            self._sync_skna_headers()
        else:
            self.lbl_ch1.setText('軌道 2：')
            self.lbl_ch1.setStyleSheet(f'color:{C["dim"]}; font-size:11px;')
            # 進 SKNA 模式時把選單暫時指到 SKNA 來源通道，離開時要指回
            # 使用者原本選的那個（ch_idx2 全程沒被改過）
            if (0 <= self.ch_idx2 < self.combo_ch1.count()
                    and self.combo_ch1.currentIndex() != self.ch_idx2):
                self.combo_ch1.blockSignals(True)
                self.combo_ch1.setCurrentIndex(self.ch_idx2)
                self.combo_ch1.blockSignals(False)
            self.combo_ch1.setEnabled(True)
            self.combo_ch1.setToolTip('選擇軌道 2 顯示的通道')
            self.band_w2.setVisible(False)
            self.mode_cb2.setVisible(False)
            self.lbl_a2.setVisible(False)

    def _track_plots(self):
        """目前看得到的波形軌道（畫點位、時間戳記、測量線、判讀框用）。"""
        plots = [self.plot_wave]
        if self.plot_wave2.isVisible() and self.dual_mode:
            plots.append(self.plot_wave2)
        if self.plot_wave3.isVisible():
            plots.append(self.plot_wave3)
        return plots

    def _draw_skna_track(self, t0: float, t1: float, max_pts: int, band: int = 1):
        """軌道 2（band=1）或軌道 3（band=2）畫 SKNA：rSNA 細線 + 整流包絡粗線。

        軌道 3 一律是傳統帶通（第二組帶通設定）；S3 只顯示在軌道 2。
"""
        return self._draw_skna_track_impl(t0, t1, max_pts, band)

    def _draw_skna_track_impl(self, t0: float, t1: float, max_pts: int, band: int = 1):
        """軌道 2 畫 SKNA：rSNA 細線 + 整流包絡粗線。

        回傳 (t, rsna, env)，皆已抽稀到可繪製的點數。抽稀用峰值法而不是
        等間隔取樣，否則 500–1500 Hz 的訊號會混疊、振幅看起來比實際小。
        """
        cfg = skna_band_cfg(self.skna_cfg, band)
        plot = self.plot_wave3 if band == 2 else self.plot_wave2
        ch  = cfg['src_ch']
        fs  = self.data.fs_of(ch)
        scale, unit = unit_to_uv(self.data.ch_units[ch])
        lo, hi, warn = skna_effective_band(fs, cfg['bp_lo'], cfg['bp_hi'])
        if band == 2:
            self._sync_skna_headers()

        use_s3 = self._track_shows_s3(band) and self.s3_sna is not None
        t, rsna, env = self._skna_cached(band, ch, t0, t1, cfg, use_s3)
        if len(t) == 0:
            self._set_ylabel(plot, 'SKNA（此範圍無資料）')
            return t, rsna, (t, env)

        rsna = rsna * scale
        env  = env * scale
        if not np.all(np.isfinite(rsna)):
            rsna = np.nan_to_num(rsna, nan=0.0, posinf=0.0, neginf=0.0)
            env = np.nan_to_num(env, nan=0.0, posinf=0.0, neginf=0.0)
        a_win = float(np.abs(rsna).mean())

        tag = 'S3' if use_s3 else 'BPF'
        band_txt = 'S3 輸出（未帶通）' if use_s3 else f'{lo:.0f}–{hi:.0f} Hz'
        # 視窗 aSKNA 每次平移都會變，放在標題列的 QLabel；縱軸標題只在
        # 通道／帶通改變時才需要重設（setLabel 會讓整條座標軸重繪，很貴）
        (self.lbl_a3 if band == 2 else self.lbl_a2).setText(
            f'視窗 aSKNA {a_win:.3f} {unit}')
        label = (f'SKNA [{tag}]　CH{ch}: {self.data.ch_names[ch]}　'
                 f'{band_txt}　({unit})')
        if self._track_shows_s3(band) and self.s3_sna is None:
            label += '　⚠ 尚未執行 S3 分解，顯示的是原始帶通結果'
        if warn and not use_s3:
            label += '　⚠ 已受 Nyquist 限制'
        self._set_ylabel(plot, label)

        # 包絡是平滑的低頻訊號（100 ms 移動平均），每個像素兩點就夠；
        # 粗線畫上萬個點在 Qt 裡很慢，是 SKNA 頁平移卡頓的主因之一
        n_env = int(min(len(t), max(400, max_pts // 5)))
        if n_env < len(t):
            idx = np.linspace(0, len(t) - 1, n_env).astype(np.int64)
            env_xy = (t[idx], env[idx])
        else:
            env_xy = (t, env)
        if len(t) > max_pts:
            t_d, r_d = peak_decimate(t, rsna, max_pts)
            return t_d, r_d, env_xy
        return t, rsna, env_xy

    # 平移時每一步只移動視窗的 15%：一次把畫面前後各多一個視窗寬度的
    # SKNA 濾好存起來，之後幾步直接切片，不必每一步都重新濾波
    _SKNA_CACHE_MAX_SEC = 60.0

    def _skna_cached(self, band, ch, t0, t1, cfg, use_s3):
        key = (id(self.data), ch, float(cfg.get('bp_lo', 0)), float(cfg.get('bp_hi', 0)),
               int(cfg.get('order', 4)), float(cfg.get('env_ms', 100.0)),
               float(cfg.get('notch', 0.0)), bool(use_s3),
               id(self.s3_sna) if use_s3 else 0)
        win = t1 - t0
        if win > self._SKNA_CACHE_MAX_SEC:
            # 畫面很寬時快取三倍範圍太占記憶體，直接算畫面範圍
            return skna_segment(self.data, ch, t0, t1, cfg,
                                sig=(self.s3_sna if use_s3 else None))
        cache = getattr(self, '_skna_cache', None)
        if cache is None:
            cache = self._skna_cache = {}
        c = cache.get(band)
        if c is None or c['key'] != key or t0 < c['a'] - 1e-9 or t1 > c['b'] + 1e-9:
            dur = self.data.duration
            a, b = max(0.0, t0 - win), min(dur, t1 + win)
            tt, rr, ee = skna_segment(self.data, ch, a, b, cfg,
                                      sig=(self.s3_sna if use_s3 else None))
            c = {'key': key, 'a': a if len(tt) else t0, 'b': b if len(tt) else t1,
                 't': tt, 'r': rr, 'e': ee}
            cache[band] = c
        tt = c['t']
        i0 = int(np.searchsorted(tt, t0, side='left'))
        i1 = int(np.searchsorted(tt, t1, side='right'))
        return tt[i0:i1], c['r'][i0:i1], c['e'][i0:i1]

    def set_skna(self, enabled: bool, cfg: dict | None = None):
        if cfg is not None:
            self.skna_cfg = dict(cfg)
        self.skna_enabled = bool(enabled)
        self._draw()

    def set_s3(self, sna, ecg):
        """設定 S3 分解結果（None 表示清除）。"""
        self.s3_sna = sna
        self.s3_ecg = ecg
        if sna is None:
            self.show_s3_ecg = False
        self._draw()

    def _clear_ts_items(self):
        for item, container in self._ts_items_cache:
            try:
                container.removeItem(item)
            except Exception:
                pass
        self._ts_items_cache = []

    def _draw_timestamps(self):
        self._clear_ts_items()

        if not hasattr(self, '_ts_mgr') or self._ts_mgr is None:
            return

        plots = self._track_plots()

        # 只畫落在目前視窗裡的：匯入實驗記錄後常有上百筆戳記，每次平移都
        # 把全部重建一遍，光是建立 Qt 物件就會讓連發平移卡住
        v0, v1 = self.t_start, self.t_end

        for rec in self._ts_mgr.records:
            ts  = rec['t_start']
            te  = rec.get('t_end')
            lbl = rec['label']
            if (te if te is not None else ts) < v0 or ts > v1:
                continue

            for plot in plots:
                vb    = plot.getViewBox()
                vr    = plot.viewRange()
                y_max = vr[1][1]
                y_min = vr[1][0]
                y_rng = y_max - y_min if y_max != y_min else 1.0

                # 起點線
                ln = InfiniteLine(
                    pos=ts, angle=90,
                    pen=pg.mkPen(C['ts_color'], width=1.8))
                ln.setZValue(10)
                vb.addItem(ln, ignoreBounds=True)
                self._ts_items_cache.append((ln, vb))

                # 標籤（只在上軌）
                if plot is self.plot_wave:
                    text = pg.TextItem(
                        f'▼ {lbl}',
                        color=C['ts_color'],
                        anchor=(0.0, 0.0))
                    text.setPos(ts, y_max - y_rng * 0.02)
                    text.setZValue(20)
                    vb.addItem(text, ignoreBounds=True)
                    self._ts_items_cache.append((text, vb))

                # 終點 + 頂端橫線（若有區間）
                if te is not None:
                    ln2 = InfiniteLine(
                        pos=te, angle=90,
                        pen=pg.mkPen(C['ts_color'], width=1.2,
                                     style=Qt.PenStyle.DashLine))
                    ln2.setZValue(10)
                    vb.addItem(ln2, ignoreBounds=True)
                    self._ts_items_cache.append((ln2, vb))

                    top_y = y_max - y_rng * 0.015
                    top_ln = pg.PlotCurveItem(
                        [ts, te], [top_y, top_y],
                        pen=pg.mkPen(C['ts_color'], width=2.5))
                    top_ln.setZValue(10)
                    vb.addItem(top_ln, ignoreBounds=True)
                    self._ts_items_cache.append((top_ln, vb))

    def _update_measure_lines(self):
        show_a = len(self.measure_pts) >= 1
        show_b = len(self.measure_pts) >= 2

        for line_a, line_b, region in [
            (self._line_a, self._line_b, self._region_meas),
            (self._line_a2, self._line_b2, self._region_meas2),
            (self._line_a3, self._line_b3, self._region_meas3),
        ]:
            if show_a:
                line_a.setPos(self.measure_pts[0])
                line_a.setVisible(True)
            else:
                line_a.setVisible(False)

            if show_b:
                line_b.setPos(self.measure_pts[1])
                line_b.setVisible(True)
                ta, tb = sorted(self.measure_pts)
                region.setRegion([ta, tb])
                region.setVisible(True)
            else:
                line_b.setVisible(False)
                region.setVisible(False)

        # 移除舊的頂端橫線
        for item, vb in getattr(self, '_meas_top_cache', []):
            try: vb.removeItem(item)
            except Exception: pass
        self._meas_top_cache = []

        # 畫新的頂端橫線
        if show_b:
            ta, tb = sorted(self.measure_pts)
            for plot in self._track_plots():
                vb  = plot.getViewBox()
                vr  = plot.viewRange()
                y_max = vr[1][1]
                y_rng = (vr[1][1] - vr[1][0]) or 1.0
                top_y = y_max - y_rng * 0.015
                top_ln = pg.PlotCurveItem(
                    [ta, tb], [top_y, top_y],
                    pen=pg.mkPen(C['yellow'], width=2.0))
                top_ln.setZValue(10)
                vb.addItem(top_ln, ignoreBounds=True)
                self._meas_top_cache.append((top_ln, vb))

    def set_ts_manager(self, mgr):
        self._clear_ts_items()
        self._ts_mgr = mgr

    def set_peaks(self, peaks: np.ndarray, stats: dict):
        """peaks 一律是相對於整個檔案（從 t=0 開始）的絕對樣本索引，
        跟目前畫面平移到哪裡無關，這樣平移視窗後峰值標記不會消失或跑位。"""
        peaks = None if peaks is None else np.asarray(peaks, dtype=int)
        self._peaks_cache = peaks
        if self.data is None or peaks is None or len(peaks) == 0:
            self._curve_peaks.setData([], [])
            self._curve_rr.setData([], [])
            self._curve_rr_pts.setData([], [])
            return

        fs = self.data.fs_of(self.ch_idx)
        full_y = self.data.channels[self.ch_idx]
        valid = peaks[(peaks >= 0) & (peaks < len(full_y))]

        # 波形上的峰值標記：只需要畫「目前有資料涵蓋」的點即可，
        # y 值直接從完整通道資料取（不受目前視窗範圍限制）。
        pk_t_all = valid / fs
        pk_y_all = full_y[valid]
        self._curve_peaks.setData(pk_t_all, pk_y_all)

        # RR tachogram：用全部峰值（不限於目前視窗）算 RR，
        # 因為 plot_rr 已跟波形圖共用 X 軸（setXLink），平移時會自動同步顯示。
        if len(valid) >= 2:
            rr = np.diff(valid) / fs * 1000
            rr_t = pk_t_all[1:]
            mask = (rr > 80) & (rr < 2000)
            self._curve_rr.setData(rr_t[mask], rr[mask])
            self._curve_rr_pts.setData(rr_t[mask], rr[mask])
        else:
            self._curve_rr.setData([], [])
            self._curve_rr_pts.setData([], [])

    def clear_peaks(self):
        """移除全部 R-peak 標記與統計。"""
        self.set_peaks(np.array([], dtype=int), {})

    # ── 導航 ─────────────────────────────────────────────────────────────────

    def request_draw(self):
        """合併短時間內的多次重畫請求，在事件迴圈的下一輪畫一次。

        連按平移鈕時，若每一下都當場完整重畫，十下就是十次重畫依序排隊，
        程式得把積欠的舊畫面全部畫完才會回應，看起來就是愈按愈頓、像當掉。
        這裡只更新要顯示的範圍，中間被跳過的位置本來也來不及看見，
        最後停在正確的位置。
        """
        if self._draw_req:
            return
        self._draw_req = True
        QTimer.singleShot(0, self._draw_coalesced)

    def _draw_coalesced(self):
        self._draw_req = False
        self._draw()

    def pan(self, direction: float, sync: bool = False):
        """sync=True 時當場重畫（連續平移用，確保畫完才排下一步）。"""
        if self.data is None:
            return
        win  = self.t_end - self.t_start
        step = win * 0.15 * direction
        new_start = max(0, min(self.data.duration - win, self.t_start + step))
        if abs(new_start - self.t_start) < 1e-12:
            return                      # 已經到頭了，不用重畫
        self.t_start = new_start
        self.t_end   = new_start + win
        if sync:
            self._draw()
        else:
            self.request_draw()

    def zoom(self, factor: float):
        if self.data is None:
            return
        center = (self.t_start + self.t_end) / 2
        win    = (self.t_end - self.t_start) / factor
        win    = max(0.5, min(self.data.duration, win))   # 最小 0.5 秒
        self.t_start = max(0.0, center - win / 2)
        self.t_end   = min(self.data.duration, self.t_start + win)
        self.request_draw()

    def reset_view(self):
        if self.data is None:
            return
        self.t_start = 0.0
        self.t_end   = min(10.0, self.data.duration)
        self.y_scale = 1.0
        self._y_auto = True
        self.plot_wave.enableAutoRange(axis='y')
        self._draw()

    def zoom_y(self, factor: float, ch: int = 0):
        """縱軸縮放：ch=0 調整 CH0，ch=1 調整 CH1"""
        if self.data is None:
            return
        # 手動調整過就不要再被自動縮放蓋掉，直到按「自動」為止
        if ch == 0:
            self._y_auto0 = False
        elif ch == 1:
            self._y_auto1 = False
        else:
            self._y_auto2 = False
        plot = {0: self.plot_wave, 1: self.plot_wave2}.get(ch, self.plot_wave3)
        vr = plot.viewRange()
        y_min, y_max = vr[1]
        y_center = (y_min + y_max) / 2
        y_half = (y_max - y_min) / 2 / factor
        plot.setYRange(y_center - y_half, y_center + y_half, padding=0)

    def reset_y(self, ch: int = 0):
        """縱軸回到自動縮放"""
        if self.data is None:
            return
        if ch == 0:
            self._y_auto0 = True
        elif ch == 1:
            self._y_auto1 = True
        else:
            self._y_auto2 = True
        self._draw()

    @staticmethod
    def _auto_y_range(plot, y, extra=None):
        """依目前可見資料設定縱軸範圍。

        不直接用 pyqtgraph 的 enableAutoRange，因為訊號幾乎是常數時
        （例如放大器飽和、整段貼在滿格）它會把範圍縮到 1e-4 mV 這種
        沒有意義的窄帶，波形就緊貼在圖框邊緣看起來像跑出視窗外。
        這裡自己算，並保證留有可讀的邊距。
        """
        y = np.asarray(y)
        if y.size == 0:
            return
        fin = y[np.isfinite(y)]
        if fin.size == 0:
            return
        lo = float(fin.min())
        hi = float(fin.max())
        if extra is not None:
            ex = np.asarray(extra)
            ex = ex[np.isfinite(ex)]
            if ex.size:
                lo = min(lo, float(ex.min()))
                hi = max(hi, float(ex.max()))
        span = hi - lo
        # 帶通遇到完全平坦（飽和）的輸入時，輸出是 1e-14 等級的浮點殘值，
        # 實際上就是 0；若照常自動縮放會把這些殘值放大成滿版雜訊
        if span <= max(1e-9, max(abs(lo), abs(hi)) * 1e-9):
            # 完全是常數：以該值為中心給一個相對寬度，至少看得到那條線
            pad = max(abs(hi) * 1e-4, 1e-6)
        else:
            pad = span * 0.08
        new_lo, new_hi = lo - pad, hi + pad

        # 只有在範圍真的變了才設。每次平移都重設縱軸有兩個代價：
        # pyqtgraph 要丟掉整個座標軸的繪圖快取重畫（實測是平移時最貴的
        # 一項），畫面也會跟著上下呼吸、不好判讀。變動小於 3% 就沿用舊
        # 範圍，波形一樣完整落在框內。
        try:
            cur_lo, cur_hi = plot.getViewBox().viewRange()[1]
            cur_span = cur_hi - cur_lo
            if cur_span > 0:
                drift = (abs(new_lo - cur_lo) + abs(new_hi - cur_hi)) / cur_span
                inside = new_lo >= cur_lo and new_hi <= cur_hi
                if drift < 0.03 or (inside and drift < 0.25):
                    return
        except Exception:
            pass
        plot.setYRange(new_lo, new_hi, padding=0)

    def goto(self, t: float):
        if self.data is None:
            return
        win = self.t_end - self.t_start
        self.t_start = max(0, min(self.data.duration - win, t - win / 4))
        self.t_end   = self.t_start + win
        self._draw()

    def _on_slider(self, val: int):
        if self.data is None:
            return
        win   = self.t_end - self.t_start
        ratio = val / 10000
        new_t = ratio * max(0, self.data.duration - win)
        self.t_start = new_t
        self.t_end   = new_t + win
        self.lbl_pos.setText(fmt_hms(new_t))
        # 拖曳時 valueChanged 會連續發射，合併成一次重畫，
        # 否則放開滑鼠後還要把中間每一格都補畫完才停下來
        self.request_draw()

    def _update_slider(self):
        if self.data is None:
            return
        win = self.t_end - self.t_start
        denom = max(self.data.duration - win, 0.001)
        ratio = self.t_start / denom
        self.slider.blockSignals(True)
        self.slider.setValue(int(ratio * 10000))
        self.slider.blockSignals(False)
        self.lbl_pos.setText(fmt_hms(self.t_start))

    # ── 測量模式 ─────────────────────────────────────────────────────────────

    def _on_click(self, event):
        self._handle_click(event, self.plot_wave)

    def _on_click2(self, event):
        self._handle_click(event, self.plot_wave2)

    def _on_click3(self, event):
        self._handle_click(event, self.plot_wave3)

    def _handle_click(self, event, plot):
        if not (self.measure_mode or self.peak_edit_mode or self.mark_mode):
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.scenePos()
        vb  = plot.getViewBox()
        if not plot.sceneBoundingRect().contains(pos):
            return
        mapped = vb.mapSceneToView(pos)
        t_click = mapped.x()

        if self.mark_mode:
            self.mark_clicked.emit(float(t_click))
            return

        if self.peak_edit_mode:
            self._handle_peak_edit_click(t_click)
            return

        if len(self.measure_pts) < 2:
            self.measure_pts.append(t_click)
        else:
            self.measure_pts = [t_click]

        self._update_measure_lines()
        self.measure_updated.emit(self.measure_pts)

    # ── R-peak 手動編輯 ──────────────────────────────────────────────────────
    # 注意：_peaks_cache 一律存「絕對樣本索引」（相對整個檔案的 t=0），
    # 而不是相對目前視窗的位置，所以這裡一律用完整通道資料
    # （self.data.channels[ch]）查值，不受目前平移/縮放到哪裡影響。
    def _handle_peak_edit_click(self, t_click: float):
        """點擊已存在的峰值 → 刪除；點擊空白處 → 在附近振幅最大點新增峰值。"""
        if self.data is None:
            return
        fs = self.data.fs_of(self.ch_idx)
        full_y = self.data.channels[self.ch_idx]
        n = len(full_y)
        if n == 0:
            return

        idx_click = int(round(t_click * fs))
        idx_click = max(0, min(n - 1, idx_click))

        peaks = self._peaks_cache
        peaks = np.array([], dtype=int) if peaks is None else np.asarray(peaks, dtype=int)

        # 點擊容許誤差：依目前縮放的可視範圍比例調整，限制在 3~50 ms 之間
        win_view = max(self.t_end - self.t_start, 1e-6)
        tol_sec  = min(max(win_view * 0.01, 0.003), 0.05)
        tol_samp = max(1, int(tol_sec * fs))

        if len(peaks) > 0:
            nearest = peaks[int(np.argmin(np.abs(peaks - idx_click)))]
            if abs(int(nearest) - idx_click) <= tol_samp:
                peaks = peaks[peaks != nearest]
                self._apply_edited_peaks(peaks)
                return

        # 新增峰值：判斷極性（依現有峰值的振幅方向，沒有峰值就預設正向）
        sign = 1.0
        if len(peaks) > 0:
            valid = peaks[(peaks >= 0) & (peaks < n)]
            if len(valid) > 0:
                baseline = np.median(full_y)
                sign = 1.0 if np.median(full_y[valid] - baseline) >= 0 else -1.0

        add_win = max(tol_samp, int(0.03 * fs))   # 至少 ±30ms
        lo = max(0, idx_click - add_win)
        hi = min(n, idx_click + add_win + 1)
        if hi <= lo:
            return
        local = full_y[lo:hi] * sign
        new_idx = lo + int(np.argmax(local))

        if len(peaks) > 0 and np.any(np.abs(peaks - new_idx) <= tol_samp):
            return   # 附近已經有峰值了，避免重複新增

        peaks = np.sort(np.append(peaks, new_idx)).astype(int)
        self._apply_edited_peaks(peaks)

    def _apply_edited_peaks(self, peaks: np.ndarray):
        stats = (rr_stats_from_peaks(peaks, self.data.fs_of(self.ch_idx))
                 if self.data is not None else {})
        self.set_peaks(peaks, stats)
        self.peaks_edited.emit(peaks, stats)

    def remove_all_peaks(self):
        """移除全部 R-peak 標記（可搭配編輯模式重新手動標記）。"""
        self.clear_peaks()
        self.peaks_edited.emit(np.array([], dtype=int), {})

    def toggle_peak_edit(self, on: bool):
        self.peak_edit_mode = on

    def toggle_dual(self, on: bool):
        """切換雙通道同時顯示"""
        self.dual_mode = on
        self._draw()

    def wheelEvent(self, event):
        """攔截滾輪事件，用我們自己的 zoom 方法處理。

        縮放量跟著滾動量走：一般滑鼠滾一格（angleDelta = 120）放大 1.25 倍；
        Mac 觸控板／Magic Mouse 一次滑動會送出幾十個小事件（每個只有幾度），
        若每個事件都固定縮放 1.5 倍，輕輕一滑就縮放好幾十倍。
        """
        delta = event.angleDelta().y()
        if delta == 0:
            event.accept()
            return
        factor = 1.25 ** (delta / 120.0)
        factor = max(1 / 1.25, min(1.25, factor))   # 單一事件最多 1.25 倍
        if abs(factor - 1.0) > 1e-4:
            self.zoom(factor)
        event.accept()

    def toggle_mark_mode(self, on: bool):
        """SKNA 時間點位標記模式。"""
        self.mark_mode = bool(on)
        if on:
            self.measure_mode = False
            self.measure_pts = []
            self._line_a.setVisible(False)
            self._line_b.setVisible(False)
            self._region_meas.setVisible(False)

    def show_range(self, a: float, b: float):
        """把檢視範圍設成 [a, b]（會夾在檔案範圍內）。"""
        if self.data is None:
            return
        dur = self.data.duration
        w = max(0.05, min(dur, b - a))
        a = max(0.0, min(a, dur - w))
        self.t_start = a
        self.t_end = a + w
        self._draw()

    def set_review(self, regions: list, cur=None):
        self.review_regions = list(regions or [])
        self.review_cur = cur
        self._draw_review()

    def _draw_review(self):
        """Artifact 區段畫紅色底，目前判讀中的區段畫橘色框。"""
        for item, container in self._review_items:
            try:
                container.removeItem(item)
            except Exception:
                pass
        self._review_items = []
        if self.data is None or (not self.review_regions and self.review_cur is None):
            return
        v0, v1 = self.t_start, self.t_end
        plots = self._track_plots()
        spans = [(a, b, pg.mkBrush(248, 81, 73, 55), None)
                 for a, b, st in self.review_regions
                 if st == 'artifact' and b > v0 and a < v1]
        if self.review_cur is not None:
            a, b = self.review_cur
            spans.append((a, b, pg.mkBrush(255, 166, 87, 28),
                          pg.mkPen(C['orange'], width=2)))
        for a, b, brush, pen in spans:
            for plot in plots:
                reg = LinearRegionItem(values=(a, b), movable=False, brush=brush)
                reg.setZValue(-10)
                reg.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                for ln in reg.lines:
                    ln.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                    ln.setPen(pen if pen is not None else pg.mkPen(None))
                    ln.setHoverPen(pen if pen is not None else pg.mkPen(None))
                plot.addItem(reg)
                self._review_items.append((reg, plot))

    def set_marks(self, marks: list):
        self.marks = list(marks or [])
        self._draw_marks()

    def _clear_mark_items(self):
        for item, container in self._mark_items:
            try:
                container.removeItem(item)
            except Exception:
                pass
        self._mark_items = []

    def _draw_marks(self):
        """把時間點位畫成垂直線：起點綠色、終點紅色，並標上名稱。"""
        self._clear_mark_items()
        if self.data is None or not self.marks:
            return
        t0, t1 = self.t_start, self.t_end
        plots = self._track_plots()
        for m in self.marks:
            t = float(m.get('t', 0.0))
            if not (t0 - 1e-9 <= t <= t1 + 1e-9):
                continue
            is_start = m.get('kind') == 'start'
            col = C['green'] if is_start else C['red']
            for pi, plot in enumerate(plots):
                line = InfiniteLine(
                    pos=t, angle=90,
                    pen=pg.mkPen(col, width=1.6,
                                 style=Qt.PenStyle.DashLine))
                if pi == 0:
                    line.label = pg.InfLineLabel(
                        line,
                        f"{'▶' if is_start else '■'} {m.get('name', '')}",
                        position=0.94, color=col, movable=False,
                        fill=pg.mkBrush(QColor(13, 17, 23, 200)))
                plot.addItem(line)
                self._mark_items.append((line, plot))

    def toggle_measure(self, on: bool):
        self.measure_mode = on
        if on:
            self.mark_mode = False
        if not on:
            self.measure_pts = []
            self._line_a.setVisible(False)
            self._line_b.setVisible(False)
            self._region_meas.setVisible(False)
            self.measure_updated.emit([])

    def clear_measure(self):
        self.measure_pts = []
        self._line_a.setVisible(False)
        self._line_b.setVisible(False)
        self._region_meas.setVisible(False)
        self.measure_updated.emit([])





# ══════════════════════════════════════════════════════════════════════════════
# 啟動畫面（拖放區）
# ══════════════════════════════════════════════════════════════════════════════
class DropZone(QWidget):
    file_dropped = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumSize(500, 360)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon = QLabel('🫀')
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet('font-size: 72px;')
        lay.addWidget(icon)

        title = QLabel('ECG Analyzer V5')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f'color: {C["accent"]}; font-size: 28px; font-weight: bold; '
            f'font-family: "SF Pro Display", "Helvetica Neue", "Segoe UI", "Microsoft JhengHei";')
        lay.addWidget(title)

        sub = QLabel('拖放 .abf / .edf / .acq 檔案到這裡，或點擊開啟')
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f'color: {C["dim"]}; font-size: 14px; margin: 8px;')
        lay.addWidget(sub)

        self.btn_open = btn = QPushButton('  📂  選擇檔案')
        btn.setFixedSize(200, 44)
        self._btn_style = (
            f'QPushButton {{ background: {C["accent"]}; color: {C["bg"]}; '
            f'font-size: 14px; font-weight: bold; border-radius: 8px; }}'
            f'QPushButton:hover {{ background: #79b8ff; }}'
            f'QPushButton:disabled {{ background: {C["border"]}; '
            f'color: {C["dim"]}; }}')
        btn.setStyleSheet(self._btn_style)
        btn.clicked.connect(self._open_dialog)
        lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self.lbl_busy = QLabel('')
        self.lbl_busy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_busy.setStyleSheet(
            f'color: {C["accent"]}; font-size: 13px; margin-top: 10px;')
        self.lbl_busy.setVisible(False)
        lay.addWidget(self.lbl_busy)

        note = QLabel('支援格式：.abf (Axon Binary Format)  ·  .edf (European Data Format)'
                      '  ·  .acq (BIOPAC AcqKnowledge)\n'
                      '取樣率不限，自動偵測通道數；各通道可有不同取樣率')
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet(f'color: {C["dim"]}; font-size: 11px; margin-top: 16px;')
        lay.addWidget(note)

    def set_busy(self, on: bool, name: str = ''):
        """讀檔期間在起始畫面上顯示進度，並停用按鈕避免重複點擊。"""
        self.btn_open.setEnabled(not on)
        self.setAcceptDrops(not on)
        self.lbl_busy.setVisible(bool(on))
        if on:
            self.lbl_busy.setText(f'⏳ 正在讀取 {name} …')
        self.repaint()

    def _is_supported(self, path: str) -> bool:
        return path.lower().endswith(SUPPORTED_EXTS)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            urls = e.mimeData().urls()
            if any(self._is_supported(u.toLocalFile()) for u in urls):
                e.acceptProposedAction()
                self.setStyleSheet(
                    f'background: {C["panel"]}; border: 2px dashed {C["accent"]};')

    def dragLeaveEvent(self, e):
        self.setStyleSheet('')

    def dropEvent(self, e: QDropEvent):
        self.setStyleSheet('')
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if self._is_supported(path):
                self.file_dropped.emit(path)
                break

    def _open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '開啟 ECG 檔案', last_open_dir(), FILE_DIALOG_FILTER)
        if path:
            self.file_dropped.emit(path)


# ══════════════════════════════════════════════════════════════════════════════
# 濾波設定對話框
# ══════════════════════════════════════════════════════════════════════════════
class FilterSettingsDialog(QDialog):
    def __init__(self, parent, notch_freq=0.0, bp_enabled=False,
                 bp_lo=1.0, bp_hi=150.0):
        super().__init__(parent)
        self.setWindowTitle('濾波設定')
        self.setModal(True)
        self.setFixedWidth(340)

        base_style = (
            f'background:{C["bg"]};color:{C["text"]};'
            f'font-size:12px;'
        )
        self.setStyleSheet(
            f'QDialog{{{base_style}}}'
            f'QGroupBox{{color:{C["accent"]};border:1px solid {C["border"]};'
            f'border-radius:6px;margin-top:{group_title_margin()}px;'
            f'padding:{group_title_margin() - 4}px 10px 8px 10px;}}'
            f'QGroupBox::title{{subcontrol-origin:margin;left:10px;'
            f'padding:0 4px;color:{C["accent"]};font-weight:bold;}}'
            f'QRadioButton{{color:{C["text"]};spacing:6px;}}'
            f'QRadioButton::indicator{{width:14px;height:14px;}}'
            f'QCheckBox{{color:{C["text"]};spacing:6px;}}'
            f'QLabel{{color:{C["text"]};font-size:12px;}}'
            f'QDoubleSpinBox{{background:{C["panel"]};color:{C["text"]};'
            f'border:1px solid {C["border"]};border-radius:4px;padding:2px 6px;}}'
            f'QPushButton{{background:{C["panel"]};color:{C["accent"]};'
            f'border:1px solid {C["border"]};border-radius:5px;'
            f'padding:5px 18px;font-size:12px;}}'
            f'QPushButton:hover{{background:{C["border"]};color:{C["text"]}}}'
            f'QPushButton:pressed{{background:{C["accent"]};color:{C["bg"]}}}'
        )

        lay = QVBoxLayout(self)
        lay.setSpacing(12)
        lay.setContentsMargins(16, 16, 16, 16)

        # ── Notch ──
        grp_notch = HelpGroupBox(
            'Notch 陷波濾波器',
            '濾掉電源線干擾：台灣、歐洲用 50 Hz，美國、日本東部用 60 Hz。\n\n'
            '只影響「畫面顯示」與主畫面的 R-peak 偵測，'
            '不會改變 SKNA 的計算結果——SKNA 有自己的帶通設定'
            '（500 Hz 以上，工頻早就在通帶之外）。')
        notch_row = QHBoxLayout(grp_notch)
        notch_row.setSpacing(16)
        self.rb_notch_off = QRadioButton('關閉')
        self.rb_notch_50  = QRadioButton('50 Hz')
        self.rb_notch_60  = QRadioButton('60 Hz')
        self._notch_grp = QButtonGroup(self)
        self._notch_grp.addButton(self.rb_notch_off, 0)
        self._notch_grp.addButton(self.rb_notch_50,  1)
        self._notch_grp.addButton(self.rb_notch_60,  2)
        if notch_freq == 50.0:
            self.rb_notch_50.setChecked(True)
        elif notch_freq == 60.0:
            self.rb_notch_60.setChecked(True)
        else:
            self.rb_notch_off.setChecked(True)
        for rb in (self.rb_notch_off, self.rb_notch_50, self.rb_notch_60):
            notch_row.addWidget(rb)
        notch_row.addStretch()
        lay.addWidget(grp_notch)

        # ── Bandpass ──
        grp_bp = HelpGroupBox(
            'Bandpass 帶通濾波器',
            '把顯示中的波形限制在指定頻帶，用來看清楚 ECG 形態'
            '（心電圖常用 0.05–150 Hz）。\n\n'
            '⚠ 這裡是「顯示用」的濾波器，跟 SKNA 分析無關。'
            'SKNA 的帶通請到 SKNA 頁的「SKNA 設定」裡調，兩者互不影響。')
        bp_lay = QVBoxLayout(grp_bp)
        bp_lay.setSpacing(8)

        self.chk_bp = QCheckBox('啟用')
        self.chk_bp.setChecked(bp_enabled)
        bp_lay.addWidget(self.chk_bp)

        spin_style = (
            f'QDoubleSpinBox{{background:{C["panel"]};color:{C["text"]};'
            f'border:1px solid {C["border"]};border-radius:4px;'
            f'padding:2px 6px;min-width:80px;}}'
        )

        row_lo = QHBoxLayout()
        lbl_lo = QLabel('Low cutoff (Hz):')
        lbl_lo.setMinimumWidth(120)
        self.spin_lo = QDoubleSpinBox()
        self.spin_lo.setRange(0.1, 9999.0)
        self.spin_lo.setDecimals(1)
        self.spin_lo.setSingleStep(1.0)
        self.spin_lo.setValue(bp_lo)
        self.spin_lo.setStyleSheet(spin_style)
        row_lo.addWidget(lbl_lo)
        row_lo.addWidget(self.spin_lo)
        row_lo.addStretch()
        bp_lay.addLayout(row_lo)

        row_hi = QHBoxLayout()
        lbl_hi = QLabel('High cutoff (Hz):')
        lbl_hi.setMinimumWidth(120)
        self.spin_hi = QDoubleSpinBox()
        self.spin_hi.setRange(0.1, 9999.0)
        self.spin_hi.setDecimals(1)
        self.spin_hi.setSingleStep(10.0)
        self.spin_hi.setValue(bp_hi)
        self.spin_hi.setStyleSheet(spin_style)
        row_hi.addWidget(lbl_hi)
        row_hi.addWidget(self.spin_hi)
        row_hi.addStretch()
        bp_lay.addLayout(row_hi)

        lay.addWidget(grp_bp)

        self._toggle_bp(bp_enabled)
        self.chk_bp.toggled.connect(self._toggle_bp)
        self.finished.connect(lambda *_: HelpBadge.close_all())

        # ── Buttons ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_apply = QPushButton('套用')
        btn_apply.setDefault(True)
        btn_apply.clicked.connect(self.accept)
        btn_cancel = QPushButton('取消')
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_apply)
        btn_row.addWidget(btn_cancel)
        lay.addLayout(btn_row)

    def _toggle_bp(self, enabled: bool):
        self.spin_lo.setEnabled(enabled)
        self.spin_hi.setEnabled(enabled)

    def get_settings(self) -> dict:
        freq_map = {0: 0.0, 1: 50.0, 2: 60.0}
        return {
            'notch_freq': freq_map.get(self._notch_grp.checkedId(), 0.0),
            'bp_enabled': self.chk_bp.isChecked(),
            'bp_lo':      self.spin_lo.value(),
            'bp_hi':      self.spin_hi.value(),
        }




# ══════════════════════════════════════════════════════════════════════════════
# S3 演算法（SNA from Shrink and Subtraction）
# ══════════════════════════════════════════════════════════════════════════════
#
# 由 CodeforTraining/ 資料夾中的 MATLAB 參考實作移植：
#   optimal_shrinkage_color.m  →  optimal_shrinkage_color()
#   createPseudoNoise.m        →  _create_pseudo_noise()
#   OSdecomp.m（GOS=1 分支）    →  os_decomp()
#   stitchALL.m                →  stitch_all()
#   AnalyzeExample.m           →  s3_decompose()
#
# 論文：Su P-C, Chen C-Y, Kuo C-H, Tsai W-C, Wu H-T.
#       Biomed Signal Process Control 119 (2026) 109710.
#
# 概念：SKNA-I 訊號 = 心電成分 + 交感神經活性 + 雜訊。心電成分是準週期的，
# 把每個心跳切成等長片段排成矩陣後，這些欄位彼此高度相似，因此心電成分在
# 矩陣中是「低秩」的，而交感神經活性是隨機的、散布在所有奇異值上。
# 於是可以用最佳奇異值收縮（optimal shrinkage）把低秩的心電成分估出來，
# 從原訊號減掉，剩下的就是不含心電干擾的 SKNA。
#
# 這跟帶通濾波的差別在於：BPF 是在「頻率」上切，但 QRS 的諧波本來就落在
# SKNA 的頻帶裡，切不乾淨；S3 是在「波形形態」上切，跟頻率無關，所以能
# 保留完整頻譜的 SNA。


def _create_pseudo_noise(fY, k, strategy='i'):
    """createPseudoNoise.m：從殘餘奇異值推估純雜訊的奇異值分布。"""
    fZ = np.sort(np.asarray(fY, dtype=np.float64))[::-1].copy()
    p = len(fZ)
    if k >= p:
        raise ValueError('k too large; procedure requires k < min(n, p)')
    if k > 0:
        if strategy == '0':
            fZ[:k] = 0.0
        elif strategy == 'w':
            fZ[:k] = fZ[k]
        elif strategy == 'i':
            diff = fZ[k] - fZ[min(2 * k, p - 1)]
            l = np.arange(1, k + 1, dtype=np.float64)
            a = (1.0 - ((l - 1) / k) ** (2.0 / 3.0)) / (2.0 ** (2.0 / 3.0) - 1.0)
            fZ[:k] = fZ[k] + a * diff
        else:
            raise ValueError('unknown strategy')
    return fZ


def optimal_shrinkage_color(Y, loss='fro', c=1.0 / 2.01):
    """eOptShrink：可分離共變異數結構下的最佳奇異值收縮。

    對應 optimal_shrinkage_color.m（Su & Wu 2023, Appl Comput Harmon Anal 74）。
    與傳統截斷式 SVD 去噪的差別在於，它不是把小的奇異值直接砍掉，而是依據
    雜訊的譜分布把每個奇異值「修正」到最佳值，因此不會連帶砍掉混在裡面的
    訊號成分。

    回傳 (去噪後矩陣, 收縮後奇異值, 估計有效秩, 使用的 k)。
    """
    Y = np.asarray(Y, dtype=np.float64)
    transposed = False
    if Y.shape[0] > Y.shape[1]:
        Y = Y.T
        transposed = True
    p, n = Y.shape
    if p < 8 or n < 8:
        raise ValueError('矩陣太小，無法進行最佳收縮')

    U, s, Vt = np.linalg.svd(Y, full_matrices=False)
    lab = np.sort(s ** 2)[::-1]

    k = int(np.floor(p ** c))
    k = max(1, min(k, (p - 1) // 2 - 1))

    def _bulk_edge(kk):
        # 方程式 (41)：估計雜訊譜的右邊界
        return (lab[kk] + (lab[kk] - lab[min(2 * kk, p - 1)])
                / (2.0 ** (2.0 / 3.0) - 1.0))

    def _eff_rank(edge):
        # 方程式 (42)：超過邊界的奇異值視為訊號
        if edge <= 0:
            return 1
        return int(np.sum(lab / edge - 1.0 > p ** (-1.0 / 3.0)))

    lambda_p = _bulk_edge(k)
    r_p = max(1, min(_eff_rank(lambda_p), p - 2))

    fZ = _create_pseudo_noise(s[r_p:], k, 'i') ** 2
    for _ in range(200):
        if k + 1 >= len(s[r_p:]) or 2 * (k + 1) >= p:
            break
        fZ2 = _create_pseudo_noise(s[r_p:], k + 1, 'i') ** 2
        if fZ2[0] != 0 and abs(fZ[0] / fZ2[0] - 1.0) > p ** (-1.0 / 3.0):
            k += 1
            fZ = fZ2
            lambda_p = _bulk_edge(k)
            r_p = max(1, min(_eff_rank(lambda_p), p - 2))
        else:
            break

    ov = lab[:r_p]
    eta = np.zeros(len(s), dtype=np.float64)
    with np.errstate(divide='ignore', invalid='ignore'):
        for j in range(r_p):
            den = fZ - ov[j]
            if not np.all(np.isfinite(den)) or np.any(den == 0):
                continue
            # 方程式 (48)-(50)：Stieltjes 轉換及其導數的數值估計
            m1 = np.sum(1.0 / den) / (p - r_p)
            dm1 = np.sum(1.0 / den ** 2) / (p - r_p)
            m2 = -(1.0 - p / n) / ov[j] + m1 * p / n
            dm2 = (1.0 - p / n) / ov[j] ** 2 + dm1 * p / n
            dTau = m1 * m2 + ov[j] * dm1 * m2 + ov[j] * m1 * dm2
            val = ov[j] * m1 * m2
            if not np.isfinite(val) or val <= 0 or dTau == 0:
                continue
            d = 1.0 / np.sqrt(val)
            a1 = abs(m1 / (d ** 2 * dTau))
            a2 = m2 / (d ** 2 * dTau)
            # 方程式 (52)
            if loss == 'fro':
                eta[j] = d * np.sqrt(abs(a1 * a2))
            elif loss == 'op':
                eta[j] = d
            elif loss == 'op2':
                lo_, hi_ = min(a1, a2), max(a1, a2)
                eta[j] = d * np.sqrt(lo_ / hi_) if hi_ > 0 else 0.0
            elif loss == 'nuc':
                eta[j] = abs(d * (np.sqrt(abs(a1 * a2))
                                  - np.sqrt(abs((1 - a1) * (1 - a2)))))
    eta[~np.isfinite(eta)] = 0.0

    Y_os = (U * eta) @ Vt
    if transposed:
        Y_os = Y_os.T
    return Y_os, eta, r_p, k


def _build_cycle_matrix(x, locs, p1, p2):
    """OSdecomp.m 前半段：把每個心跳切成等長片段，排成矩陣 Y（p × n）。

    每一欄是一個心跳（以 R-peak 對齊，左取 p1 點、右取 p2 點）。超出相鄰
    RR 間期 2/3 的部分會歸零，免得把隔壁心跳的內容帶進這一欄，破壞
    「各欄形態相似」這個低秩假設。
    """
    x = np.asarray(x, dtype=np.float64)
    N = len(x)
    p = p1 + p2 + 1
    n = len(locs)
    Y = np.zeros((p, n), dtype=np.float64)
    for jj in range(n):
        L = int(locs[jj])
        if L - p1 < 0:
            seg = x[:L + p2 + 1]
            tmp = np.concatenate([np.zeros(p - len(seg)), seg])
        else:
            seg = x[L - p1: min(L + p2 + 1, N)]
            tmp = (np.concatenate([seg, np.zeros(p - len(seg))])
                   if len(seg) < p else seg.copy())
        tmp = np.array(tmp, dtype=np.float64, copy=True)

        q1, q2 = p1, p2
        if 0 < jj < n - 1:
            q1 = int(round((locs[jj] - locs[jj - 1] + 1) * 2.0 / 3.0))
            q2 = int(round((locs[jj + 1] - locs[jj] + 1) * 2.0 / 3.0))
        if q2 < p2:
            tmp[p - (p2 - q2):] = 0.0
        if q1 < p1:
            tmp[:p1 - q1] = 0.0

        Y[:, jj] = tmp - np.median(tmp)
    return Y


def _knn_indices(A, k, should_stop=None):
    """每一欄在歐氏距離下最近的 k 個鄰居（含自己）。

    分塊計算距離矩陣，避免 n 很大時一次配置 n×n 撐爆記憶體。
    """
    B = np.ascontiguousarray(np.asarray(A, dtype=np.float64).T)   # n × d
    n = B.shape[0]
    k = max(1, min(k, n))
    sq = np.einsum('ij,ij->i', B, B)
    out = np.empty((n, k), dtype=np.int64)
    step = max(1, int(2e7 // max(n, 1)))
    for s0 in range(0, n, step):
        if should_stop is not None and should_stop():
            raise InterruptedError('使用者取消')
        e0 = min(n, s0 + step)
        d2 = sq[s0:e0, None] - 2.0 * (B[s0:e0] @ B.T) + sq[None, :]
        idx = np.argpartition(d2, k - 1, axis=1)[:, :k]
        rows = np.arange(e0 - s0)[:, None]
        order = np.argsort(d2[rows, idx], axis=1)
        out[s0:e0] = idx[rows, order]
    return out


def os_decomp(x, locs, p1, p2, K=30, loss='fro', c=1.0 / 2.01,
              progress=None, should_stop=None):
    """OSdecomp.m 的 GOS（全域最佳收縮）分支 + 非局部中位數。

    兩個步驟：
      1. 最佳收縮把心跳矩陣去噪，得到低秩的心電成分估計 YOSc
      2. 在 YOSc 的空間裡找每個心跳最相似的 K 個鄰居，回到「原始」矩陣 Y
         取這些鄰居的逐點中位數。用中位數而不是平均，是因為中位數對少數
         形態異常的心跳（早期收縮、雜訊）不敏感，不會被拉歪。
    """
    if progress:
        progress(0.15, f'建立心跳矩陣（{p1 + p2 + 1} × {len(locs)}）…')
    Y = _build_cycle_matrix(x, locs, p1, p2)

    if should_stop is not None and should_stop():
        raise InterruptedError('使用者取消')
    if progress:
        progress(0.25, '最佳奇異值收縮（SVD）…')
    YOSc, _eta, r_p, k = optimal_shrinkage_color(Y, loss, c)

    if should_stop is not None and should_stop():
        raise InterruptedError('使用者取消')
    if progress:
        progress(0.65, f'非局部中位數（有效秩 {r_p}）…')
    ind2 = _knn_indices(YOSc, K, should_stop=should_stop)

    YOSc2 = np.empty_like(Y)
    n = Y.shape[1]
    for ii in range(n):
        if should_stop is not None and (ii & 255) == 0 and should_stop():
            raise InterruptedError('使用者取消')
        YOSc2[:, ii] = np.median(Y[:, ind2[ii]], axis=1)
        if progress and (ii & 511) == 0:
            progress(0.75 + 0.15 * ii / max(n, 1), '非局部中位數…')
    return Y, YOSc, YOSc2, r_p, k


def stitch_all(Yc, locs, N, p1):
    """stitchALL.m：把去噪後的心跳片段接回時間軸。

    相鄰心跳的片段會重疊（尤其心率快的時候），直接相加會在接縫處出現
    突起。這裡用 cos²／sin² 互補的權重做交叉淡入淡出，兩段權重相加恆為 1，
    接縫處才不會有階梯或凹陷。
    """
    Yc = np.asarray(Yc, dtype=np.float64)
    p, n = Yc.shape
    p2 = p - p1 - 1
    xq = np.zeros(N, dtype=np.float64)
    CHECK = np.zeros(N, dtype=np.float64)
    FACTOR1 = 4.0 / 5.0
    WWl = np.ones(p1)

    def _place(tmpc, tmpCHECK, L):
        L = int(L)
        if L - p1 < 0:
            q0s, q0e = 0, L + p2 + 1
            qs = p - (q0e - q0s)
        elif L + p2 + 1 > N:
            q0s, q0e = L - p1, N
            qs = 0
        else:
            q0s, q0e = L - p1, L + p2 + 1
            qs = 0
        m = min(q0e - q0s, p - qs)
        if m <= 0 or q0s < 0:
            return
        xq[q0s:q0s + m] += tmpc[qs:qs + m]
        CHECK[q0s:q0s + m] += tmpCHECK[qs:qs + m]

    for jj in range(n - 1):
        tmpc = Yc[:, jj].copy()
        tmpCHECK = np.ones(p)
        tmpc[:p1] *= WWl
        tmpCHECK[:p1] *= WWl

        if locs[jj] + p2 > locs[jj + 1] - p1:
            Qlen2 = int(np.ceil((locs[jj + 1] - locs[jj]) * FACTOR1))
            if p2 > Qlen2 >= p1:
                p2t = Qlen2
                OV = (locs[jj] + p2t) - (locs[jj + 1] - p1) + 1
                WWr = np.zeros(p2); WWr[:min(p2t, p2)] = 1.0
                if OV > 0 and p2t - OV >= 0:
                    WWr[p2t - OV:p2t] = np.cos(np.linspace(0, np.pi / 2, OV)) ** 2
                WWl = np.ones(p1)
                if OV > 0:
                    WWl[:min(OV, p1)] = (np.sin(np.linspace(0, np.pi / 2, OV)) ** 2
                                         )[:min(OV, p1)]
            elif p2 > Qlen2 and p1 > Qlen2:
                p2t = p1t = Qlen2
                OV = (locs[jj] + p2t) - (locs[jj + 1] - p1t) + 1
                WWr = np.zeros(p2); WWr[:min(p2t, p2)] = 1.0
                if OV > 0 and p2t - OV >= 0:
                    WWr[p2t - OV:p2t] = np.cos(np.linspace(0, np.pi / 2, OV)) ** 2
                WWl = np.zeros(p1); WWl[p1 - p1t:] = 1.0
                if OV > 0:
                    seg = np.sin(np.linspace(0, np.pi / 2, OV)) ** 2
                    end = min(p1 - p1t + OV, p1)
                    WWl[p1 - p1t:end] = seg[:end - (p1 - p1t)]
            else:
                OV = (locs[jj] + p2) - (locs[jj + 1] - p1) + 1
                WWr = np.ones(p2)
                if 0 < OV <= p2:
                    WWr[p2 - OV:] = np.cos(np.linspace(0, np.pi / 2, OV)) ** 2
                WWl = np.ones(p1)
                if 0 < OV <= p1:
                    WWl[:OV] = np.sin(np.linspace(0, np.pi / 2, OV)) ** 2
        else:
            WWr = np.ones(p2)
            WWl = np.ones(p1)

        tmpc[p1 + 1:] *= WWr
        tmpCHECK[p1 + 1:] *= WWr
        _place(tmpc, tmpCHECK, locs[jj])

    tmpc = Yc[:, -1].copy()
    tmpCHECK = np.ones(p)
    tmpc[:p1] *= WWl
    tmpCHECK[:p1] *= WWl
    _place(tmpc, tmpCHECK, locs[-1])
    return xq, CHECK


def _slow_trend(y, fs):
    """近似 MATLAB 的 smooth(medfilt1(y, Fs/10), Fs/8, 'loess')。

    原式對每個樣本做局部加權二次迴歸，在 10 kHz、上千萬點的訊號上用
    Python 跑會慢到不能用。這裡先降取樣到約 200 Hz，在低取樣率上做中位數
    濾波與兩次移動平均，再內插回原取樣率。要抽的只是遠低於 1 Hz 的慢速
    漂移，降取樣不影響結果，速度卻差好幾個數量級。
    """
    from scipy.ndimage import median_filter
    n = len(y)
    decim = max(1, int(round(fs / 200.0)))
    yd = np.asarray(y[::decim], dtype=np.float64)
    if len(yd) < 8:
        return np.zeros(n)
    w_med = max(1, (int(round(0.1 * fs / decim)) | 1))
    w_smo = max(1, int(round(0.125 * fs / decim)))
    t = median_filter(yd, size=min(w_med, len(yd)), mode='nearest')
    t = uniform_filter1d(t, size=min(w_smo, len(t)), mode='nearest')
    t = uniform_filter1d(t, size=min(w_smo, len(t)), mode='nearest')
    xp = np.arange(0, n, decim)[:len(t)]
    return np.interp(np.arange(n), xp, t)


def _refine_rpeaks_for_s3(x, locs, fs, win_sec=0.05, min_gap_sec=0.01):
    """AnalyzeExample.m 的峰值精修：在 ±win_sec 內取最大值，再移除過近的峰。

    S3 是把各心跳疊在一起做矩陣分解，所有欄位必須精準對齊在同一個基準點上；
    只要 R-peak 位置抖動幾毫秒，低秩假設就會被破壞、心電成分估不準。
    """
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    w = max(1, int(round(win_sec * fs)))
    out = []
    for L in locs:
        a = max(0, int(L) - w)
        b = min(n, int(L) + w + 1)
        if b > a:
            out.append(a + int(np.argmax(x[a:b])))
    locs = np.unique(np.asarray(out, dtype=np.int64))
    if len(locs) < 2:
        return locs
    gap = max(1, int(round(min_gap_sec * fs)))
    keep = [locs[0]]
    for L in locs[1:]:
        if L - keep[-1] >= gap:
            keep.append(L)
        elif x[L] > x[keep[-1]]:
            keep[-1] = L
    return np.asarray(keep, dtype=np.int64)


S3_DEFAULTS = {
    'hp_hz':   1.0,     # 前置高通截止 (Hz)：移除基線漂移
    'K':       30,      # 非局部中位數的鄰居數
    'detrend': True,    # 減去慢速漂移
    'loss':    'fro',
}


def s3_decompose(x, fs, locs, hp_hz=1.0, K=30, detrend=True, loss='fro',
                 progress=None, should_stop=None):
    """完整 S3 流程，對應 AnalyzeExample.m。

    回傳 dict：
      sna   — 去除心電成分後的 SKNA（全頻譜，這就是「沒有心電圖干擾」的訊號）
      ecg   — 被分離出來的心源性成分，拿來檢查分解是否合理
      locs  — 實際使用的 R-peak 位置（已精修）
      p1/p2/rank/k/flipped — 診斷資訊
    """
    x = np.asarray(x, dtype=np.float64)
    N = len(x)
    if N < 100:
        raise ValueError('訊號太短')

    # 必須在高通之前檢查：高通會把削平的直流段濾成看似正常的波形，
    # 飽和的痕跡就消失了
    sat_pct, flat_pct, bad_pct = defect_pct(x, fs)

    if progress:
        progress(0.02, '高通濾波…')
    if hp_hz and hp_hz > 0 and fs > 2 * hp_hz:
        sos = butter(4, hp_hz / (fs / 2.0), btype='high', output='sos')
        padlen = 3 * (2 * len(sos) + 1)
        if N > padlen:
            x = sosfiltfilt(sos, x)

    locs = np.asarray(locs, dtype=np.int64)
    locs = locs[(locs >= 0) & (locs < N)]
    if len(locs) < 10:
        raise ValueError(
            f'這段訊號只偵測到 {len(locs)} 個 R-peak，至少需要 10 個才能'
            '建立心跳矩陣。請確認 ECG 參考通道選對了。')

    if bad_pct > 50.0:
        kind = '放大器飽和（削平）' if sat_pct >= flat_pct else '完全沒有變化'
        raise ValueError(
            f'來源訊號有 {bad_pct:.0f}% 的樣本處於{kind}狀態。\n'
            '那些區段等於沒有訊號內容，心跳形態無法對齊，S3 分解不會有意義。\n'
            '請改選其他通道，或只對正常的時間範圍執行。')

    # R 波統一朝上：矩陣分解假設各心跳形態一致，極性必須先一致
    flipped = False
    if np.median(x[locs]) < 0:
        x = -x
        flipped = True

    locs = _refine_rpeaks_for_s3(x, locs, fs)
    if len(locs) < 10:
        raise ValueError('精修後 R-peak 數量不足')

    rr = np.diff(locs)
    q95 = float(np.quantile(rr, 0.95))
    p1 = int(np.ceil(q95 * 0.5))      # R-peak 左側長度
    p2 = int(np.ceil(q95 * 0.75))     # R-peak 右側長度
    if p1 < 4 or p2 < 4:
        raise ValueError('心跳間距太短，無法切出有效片段')
    if p1 + p2 + 1 > N:
        raise ValueError('訊號長度不足以容納一個完整心跳片段')

    _Y, _YOSc, YOSc2, r_p, k = os_decomp(
        x, locs, p1, p2, K=K, loss=loss,
        progress=progress, should_stop=should_stop)

    if should_stop is not None and should_stop():
        raise InterruptedError('使用者取消')
    if progress:
        progress(0.92, '重組心電成分…')
    xq_ecg, _chk = stitch_all(YOSc2, locs, N, p1)

    sna0 = x - xq_ecg
    if detrend:
        if progress:
            progress(0.97, '移除慢速漂移…')
        trend = _slow_trend(sna0, fs)
    else:
        trend = np.zeros(N)
    sna = sna0 - trend
    ecg = xq_ecg + trend

    if flipped:
        sna = -sna
        ecg = -ecg

    if progress:
        progress(1.0, '完成')
    return {'sna': sna, 'ecg': ecg, 'locs': locs, 'p1': p1, 'p2': p2,
            'rank': int(r_p), 'k': int(k), 'flipped': flipped,
            'n_beat': len(locs), 'sat_pct': sat_pct,
            'flat_pct': flat_pct, 'bad_pct': bad_pct}


def s3_residual_ratio(sig, fs, locs, bp_lo=500.0, bp_hi=1500.0, half_ms=10.0):
    """量化心跳假影殘留：QRS 窗內與窗外的帶通振幅比值。

    1.0 代表 QRS 附近的振幅跟其他地方一樣，也就是完全看不出心跳的痕跡。
    數字越大代表殘留越多。用來比較 S3 前後的改善幅度。
    """
    sig = np.asarray(sig, dtype=np.float64)
    n = len(sig)
    if n < 64 or len(locs) == 0:
        return float('nan')
    lo, hi, _ = skna_effective_band(fs, bp_lo, bp_hi)
    sos = butter(4, [lo / (fs / 2), hi / (fs / 2)], btype='band', output='sos')
    padlen = 3 * (2 * len(sos) + 1)
    y = sosfiltfilt(sos, sig) if n > padlen else sig
    env = uniform_filter1d(np.abs(y), max(1, int(0.005 * fs)), mode='nearest')
    m = np.zeros(n, dtype=bool)
    w = max(1, int(half_ms / 1000.0 * fs))
    for i in np.asarray(locs, dtype=np.int64):
        m[max(0, i - w):min(n, i + w)] = True
    if not m.any() or m.all():
        return float('nan')
    out = env[~m].mean()
    return float(env[m].mean() / out) if out > 0 else float('nan')


# ══════════════════════════════════════════════════════════════════════════════
# S3 背景執行
# ══════════════════════════════════════════════════════════════════════════════
class S3Worker(QThread):
    """在背景執行緒跑 S3 分解。

    整檔 10 kHz、12 分鐘的資料大約需要 15 秒、峰值記憶體 1.3 GB，放在主
    執行緒會讓視窗整個凍住，所以獨立一條執行緒跑並回報進度。
    """
    progress_sig = pyqtSignal(float, str)
    done_sig     = pyqtSignal(object, str)      # (結果 dict 或 None, 錯誤訊息)

    def __init__(self, data, cfg, t0=None, t1=None):
        super().__init__()
        self.data = data
        self.cfg  = dict(cfg)
        self.t0   = t0
        self.t1   = t1
        self._stop = False

    def cancel(self):
        self._stop = True

    def _should_stop(self):
        return self._stop

    def run(self):
        try:
            data, cfg = self.data, self.cfg
            src, ecg_ch = cfg['src_ch'], cfg['ecg_ch']
            fs_s = data.fs_of(src)
            n_src = len(data.channels[src])

            if self.t0 is None:
                s0, s1 = 0, n_src
            else:
                s0 = max(0, int(self.t0 * fs_s))
                s1 = min(n_src, int(self.t1 * fs_s) + 1)
            if s1 - s0 < int(2 * fs_s):
                raise ValueError('選取範圍太短，至少需要 2 秒')

            self.progress_sig.emit(0.01, '偵測 R-peak…')
            if self._stop:
                raise InterruptedError('使用者取消')

            # R-peak 在 ECG 參考通道上偵測，再換算成來源通道的樣本索引
            # （兩個通道的取樣率可能不同）
            fs_e = data.fs_of(ecg_ch)
            e0 = max(0, int(s0 / fs_s * fs_e))
            e1 = min(len(data.channels[ecg_ch]), int(s1 / fs_s * fs_e) + 1)
            pk = detect_rpeaks_robust(data.channels[ecg_ch][e0:e1], fs_e,
                                      notch=cfg.get('notch', 0.0))
            if len(pk) < 10:
                raise ValueError(
                    f'ECG 參考通道 CH{ecg_ch} 只偵測到 {len(pk)} 個 R-peak，'
                    '不足以進行 S3 分解。請在 SKNA 設定裡改選一個 QRS 清楚的通道。')
            locs = np.round((e0 + pk) / fs_e * fs_s).astype(np.int64) - s0
            locs = locs[(locs >= 0) & (locs < s1 - s0)]

            if self._stop:
                raise InterruptedError('使用者取消')

            res = s3_decompose(
                data.channels[src][s0:s1], fs_s, locs,
                hp_hz=cfg.get('s3_hp_hz', 1.0),
                K=int(cfg.get('s3_K', 30)),
                detrend=bool(cfg.get('s3_detrend', True)),
                progress=lambda f, m: self.progress_sig.emit(f, m),
                should_stop=self._should_stop)

            # 補回整條通道的長度：未分解的部分留 NaN，統計時就不會誤用
            if s0 == 0 and s1 == n_src:
                sna_full, ecg_full = res['sna'], res['ecg']
            else:
                sna_full = np.full(n_src, np.nan)
                ecg_full = np.full(n_src, np.nan)
                sna_full[s0:s1] = res['sna']
                ecg_full[s0:s1] = res['ecg']

            out = {
                'sna': sna_full, 'ecg': ecg_full,
                'ch': src, 'ecg_ch': ecg_ch,
                't0': s0 / fs_s, 't1': s1 / fs_s,
                'whole_file': (s0 == 0 and s1 == n_src),
                'locs': (res['locs'] + s0),
                'p1': res['p1'], 'p2': res['p2'], 'rank': res['rank'],
                'k': res['k'], 'n_beat': res['n_beat'],
                'sat_pct': res.get('sat_pct', 0.0),
                'bad_pct': res.get('bad_pct', 0.0),
                'params': s3_param_key(cfg),
                'when': datetime.datetime.now(),
            }
            self.done_sig.emit(out, '')
        except InterruptedError:
            self.done_sig.emit(None, '已取消')
        except Exception as ex:
            self.done_sig.emit(None, f'{ex}')


def s3_param_key(cfg: dict):
    """會影響 S3 結果的參數組合；用來判斷快取是否還有效。"""
    return (cfg.get('src_ch'), cfg.get('ecg_ch'),
            float(cfg.get('s3_hp_hz', 1.0)), int(cfg.get('s3_K', 30)),
            bool(cfg.get('s3_detrend', True)), float(cfg.get('notch', 0.0)))


# ══════════════════════════════════════════════════════════════════════════════
# SKNA 設定對話框
# ══════════════════════════════════════════════════════════════════════════════
def parse_time_str(txt: str):
    """把 '90' / '1:30' / '1:30.5' / '00:01:30.500' 解析成秒。失敗回傳 None。"""
    txt = (txt or '').strip()
    if not txt:
        return None
    try:
        parts = txt.split(':')
        if len(parts) == 1:
            return float(parts[0])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    except ValueError:
        return None
    return None


_DLG_STYLE_CACHE = None


def group_title_margin() -> int:
    """群組框標題要留多高才不會被切到。

    標題是粗體，中文字的高度又比英數大。寫死一個像素值在某些系統／字體
    設定下就會不夠（標題的上下會被裁掉），所以依目前實際字體算出來。
    """
    try:
        f = QFont(QApplication.font())
        f.setBold(True)
        return max(16, QFontMetrics(f).height() + 4)
    except Exception:
        return 20


def _dialog_style() -> str:
    global _DLG_STYLE_CACHE
    if _DLG_STYLE_CACHE is None:
        _mt = group_title_margin()
        _DLG_STYLE_CACHE = (
            f'QDialog{{background:{C["bg"]};color:{C["text"]};font-size:12px;}}'
            f'QGroupBox{{color:{C["accent"]};border:1px solid {C["border"]};'
            f'border-radius:6px;margin-top:{_mt}px;'
            f'padding:{_mt - 4}px 10px 8px 10px;}}'
            f'QGroupBox::title{{subcontrol-origin:margin;left:10px;padding:0 4px;'
            f'color:{C["accent"]};font-weight:bold;}}'
            f'QLabel{{color:{C["text"]};font-size:12px;}}'
            f'QCheckBox{{color:{C["text"]};spacing:6px;}}'
            f'QRadioButton{{color:{C["text"]};spacing:6px;}}'
            f'QComboBox,QSpinBox,QDoubleSpinBox,QLineEdit{{background:{C["panel"]};'
            f'color:{C["text"]};border:1px solid {C["border"]};border-radius:4px;'
            f'padding:3px 6px;}}'
            f'QComboBox::drop-down{{border:none;}}'
            f'QPushButton{{background:{C["panel"]};color:{C["accent"]};'
            f'border:1px solid {C["border"]};border-radius:5px;padding:5px 14px;}}'
            f'QPushButton:hover{{background:{C["border"]};color:{C["text"]}}}'
            f'QPushButton:pressed{{background:{C["accent"]};color:{C["bg"]}}}'
            f'QPushButton:disabled{{color:{C["dim"]};}}'
            f'QTableWidget{{background:{C["panel"]};color:{C["text"]};'
            f'gridline-color:{C["border"]};border:1px solid {C["border"]};'
            f'selection-background-color:{C["accent"]};selection-color:{C["bg"]};}}'
            f'QHeaderView::section{{background:{C["bg"]};color:{C["accent"]};'
            f'border:1px solid {C["border"]};padding:4px;font-size:11px;}}'
        )
    return _DLG_STYLE_CACHE


class SknaSettingsDialog(QDialog):
    """SKNA 分析參數設定。"""

    def __init__(self, parent, data, cfg: dict, s3_state: str = ''):
        super().__init__(parent)
        self.setWindowTitle('SKNA 分析設定')
        self.setModal(True)
        self.setMinimumWidth(470)
        self.setStyleSheet(_dialog_style())
        self.data = data
        self._cfg = dict(cfg)
        self._s3_state = s3_state
        self._build()

    def _build(self):
        # 內容放在捲動區裡：這個對話框很長，螢幕高度不夠時若直接塞進
        # 視窗，版面會去壓縮可伸縮的元件（尤其是換行的說明文字），
        # 文字就會被切掉、跟下面的元件疊在一起。改成捲動就不會。
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        grp_ch = HelpGroupBox(
            '通道',
            'SKNA 來源通道：要拿來算 SKNA 的那一路訊號。取樣率要夠高，'
            '頻寬才撐得住 500–1500 Hz 的帶通。軌道 2 與軌道 3 可以用不同通道'
            '（例如鎢針與皮膚電極），也可以直接在波形區的軌道標題列上切換。'
            'S3 一律使用軌道 2 的來源。\n\n'
            'ECG 參考通道：只用來偵測 R-peak，供心率／心跳數統計，以及讓 S3 '
            '把每個心跳對齊排成矩陣。它不會參與 SKNA 的數值計算。\n\n'
            '下拉選單裡若標示 ⚠ 飽和／無訊號，代表該通道有相當比例的樣本'
            '沒有有效內容，不適合當分析來源。')
        g = QGridLayout(grp_ch)
        g.setSpacing(8)
        self.combo_src = QComboBox()
        self.combo_src2 = QComboBox()
        self.combo_ecg = QComboBox()
        self._sat = getattr(self.data, '_defect_report', None)
        if self._sat is None:
            self._sat = channel_defect_report(self.data)
            try:
                self.data._defect_report = self._sat
            except Exception:
                pass
        for i in range(self.data.n_ch):
            rr_ = self._sat.get(i, {})
            sp = rr_.get('bad', 0.0)
            kind = '飽和' if rr_.get('sat', 0) >= rr_.get('flat', 0) else '無訊號'
            warn = f'　⚠ {kind} {sp:.0f}%' if sp >= 1.0 else ''
            label = (f'CH{i}: {self.data.ch_names[i]}  '
                     f'({self.data.fs_of(i):,.0f} Hz){warn}')
            self.combo_src.addItem(label)
            self.combo_src2.addItem(label)
            self.combo_ecg.addItem(label)
        self.combo_src.setCurrentIndex(self._cfg.get('src_ch') or 0)
        s2 = self._cfg.get('src_ch2')
        self.combo_src2.setCurrentIndex(
            s2 if s2 is not None else (self._cfg.get('src_ch') or 0))
        self.combo_ecg.setCurrentIndex(self._cfg.get('ecg_ch') or 0)
        self.combo_src.currentIndexChanged.connect(self._refresh_hint)
        g.addWidget(QLabel('SKNA 來源（軌道 2）：'), 0, 0)
        g.addWidget(self.combo_src, 0, 1)
        g.addWidget(QLabel('SKNA 來源（軌道 3）：'), 1, 0)
        g.addWidget(self.combo_src2, 1, 1)
        g.addWidget(QLabel('ECG 參考通道：'), 2, 0)
        g.addWidget(self.combo_ecg, 2, 1)
        lay.addWidget(grp_ch)

        grp_m = HelpGroupBox(
            '演算法',
            'BPF（傳統帶通）：只在頻率上切，計算時使用區間內全部樣本（含 '
            'QRS），與文獻傳統作法一致。但 QRS 的諧波本來就落在 SKNA 頻帶裡，'
            '心率越高殘留越多。\n\n'
            'S3：改在「波形形態」上切——把每個心跳排成矩陣，用最佳奇異值收縮'
            '估出低秩的心電成分再減掉，得到不含心電干擾的 SKNA。'
            'S3 的輸出直接拿來計算 aSKNA / iSKNA，不再套下方的帶通'
            '（帶通設定只用於 BPF 欄位）。'
            '整檔需先執行一次分解（12 分鐘的檔約 15 秒）。\n\n'
            '前置高通：S3 分解前先濾掉基線漂移的截止頻率。\n\n'
            '鄰居數 K：非局部中位數用幾個相似心跳來估心電成分'
            '（MATLAB 參考實作用 30）。K 越小心跳假影壓得越乾淨，'
            '但也會開始削到 SKNA 本身；K 越大越保守。')
        vm = QVBoxLayout(grp_m); vm.setSpacing(6)
        self.rb_bpf = QRadioButton('傳統帶通（BPF）')
        self.rb_s3  = QRadioButton('S3：分解掉心電成分（輸出即 SKNA，不再帶通）')
        self._m_grp = QButtonGroup(self)
        self._m_grp.addButton(self.rb_bpf, 0)
        self._m_grp.addButton(self.rb_s3, 1)
        (self.rb_s3 if self._cfg.get('method') == 's3'
         else self.rb_bpf).setChecked(True)
        vm.addWidget(self.rb_bpf)
        vm.addWidget(self.rb_s3)

        s3row = QHBoxLayout()
        self.spin_s3_hp = QDoubleSpinBox(); self.spin_s3_hp.setRange(0.0, 50.0)
        self.spin_s3_hp.setDecimals(1); self.spin_s3_hp.setSingleStep(0.5)
        self.spin_s3_hp.setValue(float(self._cfg.get('s3_hp_hz', 1.0)))
        self.spin_s3_K = QSpinBox(); self.spin_s3_K.setRange(3, 200)
        self.spin_s3_K.setValue(int(self._cfg.get('s3_K', 30)))
        self.chk_s3_dt = QCheckBox('移除慢速漂移')
        self.chk_s3_dt.setChecked(bool(self._cfg.get('s3_detrend', True)))
        s3row.addWidget(QLabel('S3 前置高通')); s3row.addWidget(self.spin_s3_hp)
        s3row.addWidget(QLabel('Hz    鄰居數 K')); s3row.addWidget(self.spin_s3_K)
        s3row.addWidget(self.chk_s3_dt)
        s3row.addStretch()
        vm.addLayout(s3row)

        self.lbl_s3_state = WrapLabel('')
        vm.addWidget(self.lbl_s3_state)

        def _sync_s3(*_):
            on = self.rb_s3.isChecked()
            for w_ in (self.spin_s3_hp, self.spin_s3_K, self.chk_s3_dt):
                w_.setEnabled(on)
            if not on:
                self.lbl_s3_state.setText('')
                return
            if self._s3_state == 'ready':
                self.lbl_s3_state.setText('✓ 這個檔案已經分解過，套用後會直接顯示 S3 結果。')
                self.lbl_s3_state.setStyleSheet(
                    f'color:{C["green"]};font-size:11px;'
                    f'border:1px solid {C["border"]};border-radius:4px;padding:5px 7px;')
            else:
                self.lbl_s3_state.setText(
                    '⚠ 這個檔案還沒分解過。S3 必須先對整個檔案跑一次分解，'
                    '之後畫面與區間統計才會用 S3 的結果；在那之前顯示的仍是'
                    '傳統帶通。按「套用」後會問你要不要現在執行。')
                self.lbl_s3_state.setStyleSheet(
                    f'color:{C["yellow"]};font-size:11px;'
                    f'border:1px solid {C["border"]};border-radius:4px;padding:5px 7px;')
        self.rb_s3.toggled.connect(_sync_s3)
        _sync_s3()
        lay.addWidget(grp_m)

        self._bp_help = (
            '把原始訊號帶通到神經活性所在的頻帶，得到 rSNA。\n\n'
            'SKNA 頁有兩個 SKNA 軌道，各有自己的帶通：軌道 2（預設 500–1000 Hz）'
            '與軌道 3（預設 500–1500 Hz）。區間分析、Artifact 判讀與匯出的 Excel '
            '會同時計算兩組。套用 S3 時兩個軌道都會自動顯示 S3，之後可在軌道標題列的'
            '「Bandpass／S3」選單各自切換（軌道 3 需與軌道 2 同一通道才能顯示 S3）。\n\n'
            '預設值：\n'
            '  500–1000 Hz — Kusayama 2020 Nature Protocols 的標準設定，'
            '要對照文獻數值請用這一組。\n'
            '  500–1500 Hz — 高採樣率錄製時頻寬利用較完整；'
            '實測 aSKNA 會比 500–1000 高約 16%。\n'
            '  300–500 Hz — Holter 等 1 kHz 採樣設備適用。\n\n'
            '階數：Butterworth 濾波器階數，以 SOS 形式、零相位（sosfiltfilt）'
            '套用，不會造成相位位移。\n\n'
            '高截止若超過該通道的 Nyquist（fs / 2）會自動夾住，並在下方標示。')
        grp_bp = HelpGroupBox('帶通濾波（rSNA-BPF）', self._bp_help)
        self._bp_badge = grp_bp.badge
        v = QVBoxLayout(grp_bp)
        v.setSpacing(8)
        def _spin(val):
            s_ = QDoubleSpinBox(); s_.setRange(1, 20000)
            s_.setDecimals(0); s_.setSingleStep(50); s_.setValue(float(val))
            s_.valueChanged.connect(self._refresh_hint)
            return s_

        gb = QGridLayout(); gb.setSpacing(6)
        gb.addWidget(QLabel('預設值'), 0, 1)
        gb.addWidget(QLabel('低截止 (Hz)'), 0, 2)
        gb.addWidget(QLabel('高截止 (Hz)'), 0, 3)
        self.combo_preset = QComboBox()
        self.combo_preset.addItems(list(SKNA_PRESETS.keys()) + ['自訂'])
        self.combo_preset.currentTextChanged.connect(self._on_preset)
        self.combo_preset2 = QComboBox()
        self.combo_preset2.addItems(list(SKNA_PRESETS.keys()) + ['自訂'])
        self.combo_preset2.currentTextChanged.connect(self._on_preset2)
        self.spin_lo = _spin(self._cfg.get('bp_lo', 500.0))
        self.spin_hi = _spin(self._cfg.get('bp_hi', 1000.0))
        self.spin_lo2 = _spin(self._cfg.get('bp_lo2', 500.0))
        self.spin_hi2 = _spin(self._cfg.get('bp_hi2', 1500.0))
        for r_, (lbl_, cb_, lo_, hi_) in enumerate((
                ('軌道 2：', self.combo_preset, self.spin_lo, self.spin_hi),
                ('軌道 3：', self.combo_preset2, self.spin_lo2, self.spin_hi2)), 1):
            gb.addWidget(QLabel(lbl_), r_, 0)
            gb.addWidget(cb_, r_, 1)
            gb.addWidget(lo_, r_, 2)
            gb.addWidget(hi_, r_, 3)
        gb.setColumnStretch(1, 1)
        v.addLayout(gb)

        row_f = QHBoxLayout()
        self.spin_ord = QSpinBox(); self.spin_ord.setRange(2, 8)
        self.spin_ord.setValue(int(self._cfg.get('order', 4)))
        row_f.addWidget(QLabel('階數（兩軌共用）')); row_f.addWidget(self.spin_ord)
        row_f.addStretch()
        v.addLayout(row_f)

        self.lbl_hint = WrapLabel('')
        self.lbl_hint.setStyleSheet(f'color:{C["dim"]};font-size:11px;')
        v.addWidget(self.lbl_hint)
        lay.addWidget(grp_bp)

        grp_na = HelpGroupBox(
            'Nerveact 相容模式',
            '開啟後，每個區間會「另外」多算一組 Nerveact 相容的 aSKNA / iSKNA，'
            '原本的 BPF 與 S3 數值不受影響。\n\n'
            'Nerveact 的計算方式（由原始資料與 Nerveact 輸出反推，600 個窗格'
            '逐窗重現，誤差 < 0.001 µV）：\n'
            '  1. 從區間起點依窗長（預設 10 s）切窗\n'
            '  2. 每一窗各自以 Butterworth 帶通「單向」濾波，從零狀態開始\n'
            '  3. 全波整流後取平均\n\n'
            '與本程式 BPF 的差異：\n'
            '  • 每窗起點的直流電位會激起濾波器暫態並被算進 aSKNA'
            '（約每 10 mV 直流偏移 +0.45 µV）。放大器飽和的窗格會得到 '
            '0.450（500–1000 Hz）／0.429（500–1500 Hz）而不是 0。\n'
            '  • 單向濾波的通帶比零相位寬，數值約高 6–10%。\n\n'
            '用途：與 Nerveact 數據或以 Nerveact 分析的文獻數值對照。'
            '這個數值含有直流偏移造成的暫態，不建議當作主要分析指標。\n\n'
            '要和 Nerveact 逐窗對齊：區間長度設成與窗長相同（例如「自動分段'
            '計算」每 10 s 一段），起點也要和 Nerveact 相同。帶通頻率與階數'
            '沿用上方設定（Nerveact 為 4 階）；不套用工頻陷波。')
        hn = QHBoxLayout(grp_na)
        self.chk_nact = QCheckBox('另外計算 Nerveact 相容的 aSKNA')
        self.chk_nact.setChecked(bool(self._cfg.get('nact_compat', True)))
        self.spin_nact = QDoubleSpinBox(); self.spin_nact.setRange(0.5, 600.0)
        self.spin_nact.setDecimals(1); self.spin_nact.setSingleStep(1.0)
        self.spin_nact.setValue(float(self._cfg.get('nact_win', 10.0)))
        self.spin_nact.setEnabled(self.chk_nact.isChecked())
        self.chk_nact.toggled.connect(self.spin_nact.setEnabled)
        hn.addWidget(self.chk_nact)
        hn.addSpacing(12)
        hn.addWidget(QLabel('切窗長度')); hn.addWidget(self.spin_nact)
        hn.addWidget(QLabel('s'))
        hn.addStretch()
        lay.addWidget(grp_na)

        grp_env = HelpGroupBox(
            '整流與包絡',
            'rSNA 全波整流後取移動平均，得到軌道 2 上那條橘色包絡線，'
            '形狀類似微神經圖的積分神經圖。\n\n'
            '100 ms 是文獻慣例（Kusayama 2020 用的是時間常數 0.1 s 的'
            '洩漏積分器，概念相同）。\n\n'
            '這個設定只影響「顯示」。aSKNA / iSKNA 是直接由 rSNA 計算，'
            '不受窗長影響。')
        h = QHBoxLayout(grp_env)
        self.spin_env = QDoubleSpinBox(); self.spin_env.setRange(1, 5000)
        self.spin_env.setDecimals(0); self.spin_env.setSingleStep(10)
        self.spin_env.setValue(self._cfg.get('env_ms', 100.0))
        h.addWidget(QLabel('移動平均窗長：')); h.addWidget(self.spin_env)
        h.addWidget(QLabel('ms'))
        h.addStretch()
        lay.addWidget(grp_env)

        grp_bl = HelpGroupBox(
            'R-peak 偵測（心率統計與 S3 定位用）',
            'R-peak 只用來算心率／心跳數，以及讓 S3 把每個心跳對齊排成矩陣。\n'
            'SKNA 的強度指標（aSKNA / iSKNA）一律使用區間內全部樣本，'
            '不會因為 R-peak 而排除任何資料。\n\n'
            '自動偵測：SKNA 專用演算法，會先用自相關估出心動週期，再據此設定'
            '門檻與不應期，因此能自動適應人類與小鼠等差異極大的心率，'
            '比主畫面的「偵測 R-peaks」穩定得多。\n\n'
            '沿用畫面上的標記：只有在你已經人工校正過畫面上的峰值、'
            '想沿用時才選這一項。')
        v2 = QVBoxLayout(grp_bl); v2.setSpacing(6)

        h3 = QHBoxLayout()
        h3.addWidget(QLabel('R-peak 來源：'))
        self.combo_rsrc = QComboBox()
        self.combo_rsrc.addItems(['自動偵測（建議）', '沿用畫面上的 R-peak 標記'])
        self.combo_rsrc.setCurrentIndex(
            1 if self._cfg.get('rpeak_source') == 'screen' else 0)
        self.combo_rsrc.setToolTip(
            '自動偵測用的是 SKNA 專用演算法，會依訊號自己估心動週期，'
            '在高心率（例如小鼠）下比主畫面的「偵測 R-peaks」穩定得多。\n'
            '只有在你已經人工校正過畫面上的峰值、想沿用時才選第二項。')
        h3.addWidget(self.combo_rsrc, 1)
        v2.addLayout(h3)
        lay.addWidget(grp_bl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        # 按鈕列固定在底下，捲動時一直看得到
        btnw = QWidget()
        btn = QHBoxLayout(btnw)
        btn.setContentsMargins(16, 8, 16, 12)
        btn.addStretch()
        b_ok = QPushButton('套用'); b_ok.setDefault(True)
        b_ok.clicked.connect(self.accept)
        b_no = QPushButton('取消'); b_no.clicked.connect(self.reject)
        btn.addWidget(b_ok); btn.addWidget(b_no)
        outer.addWidget(btnw)

        self._sync_preset()
        self._refresh_hint()
        self._fit_to_screen(body)

    def closeEvent(self, ev):
        HelpBadge.close_all()
        super().closeEvent(ev)

    def done(self, r):
        HelpBadge.close_all()
        super().done(r)

    def _fit_to_screen(self, body):
        """預設開成剛好裝得下內容的大小，但不超過螢幕。"""
        try:
            avail = self.screen().availableGeometry()
        except Exception:
            self.resize(560, 760)
            return
        w = min(max(560, body.sizeHint().width() + 24), avail.width() - 80)
        need = body.heightForWidth(w - 24) if body.hasHeightForWidth() else 0
        need = max(need, body.sizeHint().height())
        h = min(need + 60, int(avail.height() * 0.92))
        self.resize(int(w), int(h))

    def _sync_preset(self):
        for combo, s_lo, s_hi in ((self.combo_preset, self.spin_lo, self.spin_hi),
                                  (self.combo_preset2, self.spin_lo2, self.spin_hi2)):
            cur = (s_lo.value(), s_hi.value())
            combo.blockSignals(True)
            target = '自訂'
            for name, band in SKNA_PRESETS.items():
                if abs(band[0] - cur[0]) < 0.5 and abs(band[1] - cur[1]) < 0.5:
                    target = name
                    break
            combo.setCurrentText(target)
            combo.blockSignals(False)

    def _on_preset(self, name: str):
        if name in SKNA_PRESETS:
            lo, hi = SKNA_PRESETS[name]
            self.spin_lo.setValue(lo)
            self.spin_hi.setValue(hi)
        self._refresh_hint()

    def _on_preset2(self, name: str):
        if name in SKNA_PRESETS:
            lo, hi = SKNA_PRESETS[name]
            self.spin_lo2.setValue(lo)
            self.spin_hi2.setValue(hi)
        self._refresh_hint()

    def _refresh_hint(self, *_):
        ch = self.combo_src.currentIndex()
        fs = self.data.fs_of(ch)
        lo, hi, warn = skna_effective_band(fs, self.spin_lo.value(),
                                           self.spin_hi.value())
        lo2, hi2, warn2 = skna_effective_band(fs, self.spin_lo2.value(),
                                              self.spin_hi2.value())
        scale, unit = unit_to_uv(self.data.ch_units[ch])
        # 目前通道的基本資訊屬於「說明」，收進標題旁的問號裡；
        # 外面只留跟這筆資料有關的警告，不能藏起來。
        if getattr(self, '_bp_badge', None) is not None:
            self._bp_badge.set_text(
                f'目前來源 CH{ch}：fs = {fs:,.0f} Hz'
                f'（Nyquist {fs / 2:,.0f} Hz），'
                f'原始單位 {self.data.ch_units[ch]} → 輸出以 {unit} 表示。'
                f'實際生效帶通：軌道 2 {lo:.0f}–{hi:.0f} Hz、'
                f'軌道 3 {lo2:.0f}–{hi2:.0f} Hz。\n\n'
                + self._bp_help)

        msgs = []
        rr_ = self._sat.get(ch, {})
        sp = rr_.get('bad', 0.0)
        if sp >= 1.0:
            kind = ('放大器飽和（波形被削平）'
                    if rr_.get('sat', 0) >= rr_.get('flat', 0)
                    else '完全沒有變化（死訊號）')
            msgs.append(
                f'⚠ 此通道有 {sp:.0f}% 的樣本處於{kind}。'
                '那些區段沒有訊號內容，算出來的 aSKNA 不具物理意義，'
                'S3 也無法分解。建議改用其他通道，或只分析正常的時間範圍。')
        if warn:
            msgs.append('⚠ 軌道 2：' + warn)
        if warn2:
            msgs.append('⚠ 軌道 3：' + warn2)
        if unit != 'µV':
            msgs.append('⚠ 無法辨識的單位，數值不做換算，直接沿用原單位。')
        self.lbl_hint.setText('  '.join(msgs))
        self.lbl_hint.setStyleSheet(f'color:{C["yellow"]};font-size:11px;')
        self.lbl_hint.setVisible(bool(msgs))
        self._sync_preset()

    def get_settings(self) -> dict:
        cfg = dict(self._cfg)
        cfg.update({
            'src_ch':        self.combo_src.currentIndex(),
            'src_ch2':       self.combo_src2.currentIndex(),
            'ecg_ch':        self.combo_ecg.currentIndex(),
            'bp_lo':         self.spin_lo.value(),
            'bp_hi':         self.spin_hi.value(),
            'bp_lo2':        self.spin_lo2.value(),
            'bp_hi2':        self.spin_hi2.value(),
            'order':         int(self.spin_ord.value()),
            'env_ms':        self.spin_env.value(),
            'rpeak_source':  ('screen' if self.combo_rsrc.currentIndex() == 1
                              else 'auto'),
            'method':        ('s3' if self.rb_s3.isChecked() else 'bpf'),
            's3_hp_hz':      self.spin_s3_hp.value(),
            's3_K':          int(self.spin_s3_K.value()),
            's3_detrend':    self.chk_s3_dt.isChecked(),
            'nact_compat':   self.chk_nact.isChecked(),
            'nact_win':      self.spin_nact.value(),
        })
        return cfg


# ══════════════════════════════════════════════════════════════════════════════
# SKNA 區間分析
# ══════════════════════════════════════════════════════════════════════════════
class IntervalInputDialog(QDialog):
    """手動輸入一個時間區間。"""

    def __init__(self, parent, duration: float):
        super().__init__(parent)
        self.setWindowTitle('新增時間區間')
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setStyleSheet(_dialog_style())
        self.duration = duration
        self._result = None

        lay = QVBoxLayout(self); lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)
        g = QGridLayout(); g.setSpacing(8)
        self.ed_label = QLineEdit()
        self.ed_label.setPlaceholderText('例如 baseline / cold pressor / recovery')
        self.ed_t0 = QLineEdit()
        self.ed_t1 = QLineEdit()
        for ed in (self.ed_t0, self.ed_t1):
            ed.setPlaceholderText('mm:ss.mmm 或秒數，例如 5:30.5 或 330.5')
        g.addWidget(QLabel('標籤：'), 0, 0);     g.addWidget(self.ed_label, 0, 1)
        g.addWidget(QLabel('起始時間：'), 1, 0); g.addWidget(self.ed_t0, 1, 1)
        g.addWidget(QLabel('結束時間：'), 2, 0); g.addWidget(self.ed_t1, 2, 1)
        lay.addLayout(g)

        hint = QLabel(f'檔案總長度：{fmt_hms(duration)}（{duration:.1f} 秒）')
        hint.setStyleSheet(f'color:{C["dim"]};font-size:11px;')
        lay.addWidget(hint)
        self.lbl_err = QLabel('')
        self.lbl_err.setStyleSheet(f'color:{C["red"]};font-size:11px;')
        lay.addWidget(self.lbl_err)

        btn = QHBoxLayout(); btn.addStretch()
        b_ok = QPushButton('確定'); b_ok.setDefault(True)
        b_ok.clicked.connect(self._on_ok)
        b_no = QPushButton('取消'); b_no.clicked.connect(self.reject)
        btn.addWidget(b_ok); btn.addWidget(b_no)
        lay.addLayout(btn)

    def _on_ok(self):
        a = parse_time_str(self.ed_t0.text())
        b = parse_time_str(self.ed_t1.text())
        if a is None or b is None:
            self.lbl_err.setText('時間格式無法解析，請用 mm:ss.mmm 或直接輸入秒數。')
            return
        if b <= a:
            self.lbl_err.setText('結束時間必須大於起始時間。')
            return
        if a < 0 or b > self.duration + 1e-6:
            self.lbl_err.setText(f'超出檔案範圍（0 ~ {self.duration:.1f} 秒）。')
            return
        self._result = (a, b, self.ed_label.text().strip())
        self.accept()

    def get_interval(self):
        return self._result


class MarkPointDialog(QDialog):
    """新增／編輯一個 SKNA 時間點位。"""

    def __init__(self, parent, t: float, abs_t: str = '', name: str = '',
                 kind: str = 'start', suggest: str = ''):
        super().__init__(parent)
        self.setWindowTitle('新增時間點位')
        self.setModal(True)
        self.setMinimumWidth(380)
        self.setStyleSheet(_dialog_style())
        self._result = None

        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        head = QLabel(f'時間：<b>{fmt_hms(t)}</b>'
                      + (f'　（{abs_t}）' if abs_t else ''))
        head.setTextFormat(Qt.TextFormat.RichText)
        head.setStyleSheet(f'color:{C["accent"]};font-size:13px;')
        lay.addWidget(head)

        g = QGridLayout()
        g.setSpacing(8)
        g.addWidget(QLabel('名稱：'), 0, 0)
        self.ed_name = QLineEdit(name or suggest)
        self.ed_name.setPlaceholderText('例如 baseline / cold pressor / recovery')
        self.ed_name.selectAll()
        g.addWidget(self.ed_name, 0, 1)

        g.addWidget(QLabel('類型：'), 1, 0)
        krow = QHBoxLayout()
        self.rb_start = QRadioButton('起點')
        self.rb_end = QRadioButton('終點')
        grp = QButtonGroup(self)
        grp.addButton(self.rb_start, 0)
        grp.addButton(self.rb_end, 1)
        (self.rb_end if kind == 'end' else self.rb_start).setChecked(True)
        krow.addWidget(self.rb_start)
        krow.addWidget(self.rb_end)
        krow.addStretch()
        g.addLayout(krow, 1, 1)
        lay.addLayout(g)

        note = QLabel(
            '同名的「起點」與其後最近的「終點」會自動配對成一個分析區間，'
            'SKNA 指標會自動算好，也會出現在區間分析與 Excel 匯出裡。')
        note.setWordWrap(True)
        note.setStyleSheet(f'color:{C["dim"]};font-size:11px;')
        lay.addWidget(note)

        self.lbl_err = QLabel('')
        self.lbl_err.setStyleSheet(f'color:{C["red"]};font-size:11px;')
        lay.addWidget(self.lbl_err)

        btn = QHBoxLayout()
        btn.addStretch()
        b_ok = QPushButton('確定')
        b_ok.setDefault(True)
        b_ok.clicked.connect(self._on_ok)
        b_no = QPushButton('取消')
        b_no.clicked.connect(self.reject)
        btn.addWidget(b_ok)
        btn.addWidget(b_no)
        lay.addLayout(btn)

        self.ed_name.setFocus()

    def _on_ok(self):
        nm = self.ed_name.text().strip()
        if not nm:
            self.lbl_err.setText('請輸入名稱。')
            return
        self._result = (nm, 'end' if self.rb_end.isChecked() else 'start')
        self.accept()

    def get_mark(self):
        return self._result


def make_auto_windows(duration: float, win: float, step: float,
                      t_start: float = 0.0, t_end: float | None = None,
                      count: int | None = None, drop_partial: bool = True):
    """產生等間隔的分析區間 [(t0, t1), ...]。

    win   — 每段長度（秒）
    step  — 相鄰兩段起點的間距（秒）；等於 win 就是連續不重疊，
            大於 win 是「每隔 step 秒取 win 秒」，小於 win 則會重疊
    t_start / t_end — 範圍；t_end 省略就到檔案結尾
    count — 最多幾段（None 表示不限，排到範圍結束為止）
    drop_partial — 最後一段不足 win 時是否捨去（不捨去就截到範圍結尾）

    起點用 t_start + k·step 算，而不是一直累加，避免浮點誤差累積到
    後面幾百段時起點偏掉。
    """
    out = []
    if win <= 0 or step <= 0 or duration <= 0:
        return out
    t_start = max(0.0, float(t_start))
    t_end = duration if t_end is None else min(float(t_end), duration)
    eps = 1e-9
    k = 0
    while True:
        if count is not None and len(out) >= count:
            break
        a = t_start + k * step
        if a >= t_end - eps:
            break
        b = a + win
        if b > t_end + eps:
            if drop_partial:
                break
            b = t_end
        out.append((round(a, 6), round(b, 6)))
        k += 1
    return out


class AutoWindowDialog(QDialog):
    """自動分段：依固定長度與間隔，一次產生並計算多個 SKNA 區間。"""

    _KEY = 'skna_auto_windows'

    def __init__(self, parent, data, points=None):
        super().__init__(parent)
        self.setWindowTitle('自動分段計算 SKNA')
        # [(t, 顯示文字, 名稱, 'start'|'end'|'')] —— SKNA 時間點位與時間戳記
        self.points = sorted(points or [], key=lambda p: p[0])
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setStyleSheet(_dialog_style())
        self.data = data
        self.duration = float(data.duration)
        self._windows = []
        self._build()
        self._load()
        self._update()

    # ── 版面 ──────────────────────────────────────────────────────────────
    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        grp_w = HelpGroupBox(
            '分段方式',
            '每段長度：每個分析區間有多長。\n\n'
            '每隔：相鄰兩段起點之間的距離。\n'
            '  • 與長度相同（例如 10 / 10）→ 連續、不重疊地切\n'
            '  • 大於長度（例如 長度 10、每隔 60）→ 每分鐘取 10 秒\n'
            '  • 小於長度（例如 長度 10、每隔 5）→ 互相重疊的滑動視窗')
        g = QGridLayout(grp_w)
        g.setSpacing(8)
        self.spin_win = QDoubleSpinBox()
        self.spin_win.setRange(0.1, 1e6); self.spin_win.setDecimals(1)
        self.spin_win.setValue(10.0); self.spin_win.setSuffix(' 秒')
        self.spin_step = QDoubleSpinBox()
        self.spin_step.setRange(0.1, 1e6); self.spin_step.setDecimals(1)
        self.spin_step.setValue(10.0); self.spin_step.setSuffix(' 秒')
        self.chk_link = QCheckBox('與長度相同（連續不重疊）')
        self.chk_link.setChecked(True)
        g.addWidget(QLabel('每段長度：'), 0, 0); g.addWidget(self.spin_win, 0, 1)
        g.addWidget(QLabel('每隔：'), 1, 0);     g.addWidget(self.spin_step, 1, 1)
        g.addWidget(self.chk_link, 1, 2)
        lay.addWidget(grp_w)

        grp_r = HelpGroupBox(
            '計算範圍',
            '時間可以輸入秒數（例如 330.5）或 mm:ss / hh:mm:ss（例如 5:30）。\n'
            '一律是從檔案開頭起算的相對時間。\n\n'
            '起點／終點旁的下拉選單可以直接選已標記的時間：📍 是 SKNA 時間點位，'
            '🕒 是時間戳記。選了起點而它有同名的終點時，終點會自動帶入，'
            '並切換成「指定時間區間」。')
        vr = QGridLayout(grp_r)
        vr.setSpacing(8)
        self.rb_all   = QRadioButton('整個檔案')
        self.rb_total = QRadioButton('從起點開始，總共計算')
        self.rb_count = QRadioButton('從起點開始，共計算')
        self.rb_range = QRadioButton('指定時間區間')
        self._r_grp = QButtonGroup(self)
        for i, rb in enumerate((self.rb_all, self.rb_total,
                                self.rb_count, self.rb_range)):
            self._r_grp.addButton(rb, i)
        self.rb_all.setChecked(True)

        self.ed_start = QLineEdit('0')
        self.ed_start.setPlaceholderText('秒數或 mm:ss')
        self.spin_total = QDoubleSpinBox()
        self.spin_total.setRange(0.1, 1e7); self.spin_total.setDecimals(1)
        self.spin_total.setValue(min(1000.0, self.duration)); self.spin_total.setSuffix(' 秒')
        self.spin_count = QSpinBox()
        self.spin_count.setRange(1, 100000); self.spin_count.setValue(100)
        self.spin_count.setSuffix(' 段')
        self.ed_end = QLineEdit(f'{self.duration:.1f}')
        self.ed_end.setPlaceholderText('秒數或 mm:ss')

        vr.addWidget(self.rb_all, 0, 0, 1, 3)
        vr.addWidget(self.rb_total, 1, 0); vr.addWidget(self.spin_total, 1, 1)
        vr.addWidget(self.rb_count, 2, 0); vr.addWidget(self.spin_count, 2, 1)
        self.combo_pt_start = self._point_combo('起點')
        self.combo_pt_end = self._point_combo('終點')
        vr.addWidget(self.rb_range, 3, 0, 1, 3)
        # 起點在上、終點在下（起點也用於「總共計算」「共計算」兩種模式）
        vr.addWidget(QLabel('起點：'), 4, 0)
        rs = QHBoxLayout()
        rs.addWidget(self.ed_start); rs.addWidget(self.combo_pt_start, 1)
        vr.addLayout(rs, 4, 1, 1, 2)
        self.lbl_start_note = QLabel('')
        self.lbl_start_note.setStyleSheet(f'color:{C["dim"]};font-size:11px;')
        vr.addWidget(self.lbl_start_note, 5, 1, 1, 2)
        self.lbl_end = QLabel('終點：')
        vr.addWidget(self.lbl_end, 6, 0)
        rr = QHBoxLayout()
        rr.addWidget(self.ed_end); rr.addWidget(self.combo_pt_end, 1)
        vr.addLayout(rr, 6, 1, 1, 2)
        self.chk_partial = QCheckBox('最後不足一段長度時捨去')
        self.chk_partial.setChecked(True)
        vr.addWidget(self.chk_partial, 7, 0, 1, 3)
        self.combo_pt_start.activated.connect(self._on_pick_start)
        self.combo_pt_end.activated.connect(self._on_pick_end)
        self.ed_start.textEdited.connect(lambda *_: self.combo_pt_start.setCurrentIndex(0))
        self.ed_end.textEdited.connect(lambda *_: self.combo_pt_end.setCurrentIndex(0))
        lay.addWidget(grp_r)

        grp_o = QGroupBox('其他')
        go = QGridLayout(grp_o)
        go.setSpacing(8)
        self.ed_prefix = QLineEdit('自動')
        go.addWidget(QLabel('標籤前綴：'), 0, 0); go.addWidget(self.ed_prefix, 0, 1)
        self.chk_clear = QCheckBox('先清除之前自動產生的區間')
        self.chk_clear.setChecked(True)
        go.addWidget(self.chk_clear, 1, 0, 1, 2)
        lay.addWidget(grp_o)

        self.lbl_prev = WrapLabel('')
        self.lbl_prev.setStyleSheet(
            f'color:{C["accent"]};font-size:12px;border:1px solid {C["border"]};'
            f'border-radius:4px;padding:6px 8px;background:{C["panel"]};')
        lay.addWidget(self.lbl_prev)

        btn = QHBoxLayout(); btn.addStretch()
        self.b_ok = QPushButton('產生並計算'); self.b_ok.setDefault(True)
        self.b_ok.clicked.connect(self._on_ok)
        b_no = QPushButton('取消'); b_no.clicked.connect(self.reject)
        btn.addWidget(self.b_ok); btn.addWidget(b_no)
        lay.addLayout(btn)

        for w_ in (self.spin_win, self.spin_step, self.spin_total, self.spin_count):
            w_.valueChanged.connect(self._update)
        for w_ in (self.ed_start, self.ed_end):
            w_.textChanged.connect(self._update)
        for w_ in (self.rb_all, self.rb_total, self.rb_count, self.rb_range,
                   self.chk_partial, self.chk_link):
            w_.toggled.connect(self._update)
        self.spin_win.valueChanged.connect(self._sync_link)
        self.chk_link.toggled.connect(self._sync_link)
        self.finished.connect(lambda *_: HelpBadge.close_all())

    def _point_combo(self, what: str) -> QComboBox:
        cb = QComboBox()
        if self.points:
            cb.addItem(f'從已標記的時間選{what}…', None)
            for t, text, _n, _k in self.points:
                cb.addItem(text, float(t))
        else:
            cb.addItem('（尚無時間點位／時間戳記）', None)
            cb.setEnabled(False)
        cb.setToolTip('📍 SKNA 時間點位　🕒 時間戳記')
        return cb

    def _on_pick_start(self, idx: int):
        t = self.combo_pt_start.itemData(idx)
        if t is None:
            return
        self.ed_start.setText(f'{t:.3f}')
        # 有同名的終點就一併帶入
        _t, _txt, name, kind = self.points[idx - 1]
        if kind == 'start' and name:
            ends = [k for k, p in enumerate(self.points)
                    if p[2] == name and p[3] == 'end' and p[0] > t]
            if ends:
                k = min(ends, key=lambda k: self.points[k][0])
                self.ed_end.setText(f'{self.points[k][0]:.3f}')
                self.combo_pt_end.setCurrentIndex(k + 1)
                self.rb_range.setChecked(True)
        if self._r_grp.checkedId() == 0:
            self.rb_range.setChecked(True)
        self._update()

    def _on_pick_end(self, idx: int):
        t = self.combo_pt_end.itemData(idx)
        if t is None:
            return
        self.ed_end.setText(f'{t:.3f}')
        self.rb_range.setChecked(True)
        self._update()

    def _sync_link(self, *_):
        linked = self.chk_link.isChecked()
        self.spin_step.setEnabled(not linked)
        if linked:
            self.spin_step.setValue(self.spin_win.value())

    # ── 記住上次的設定 ────────────────────────────────────────────────────
    def _load(self):
        try:
            raw = QSettings(_SETTINGS_ORG, _SETTINGS_APP).value(self._KEY, '')
            s = json.loads(raw) if raw else {}
        except Exception:
            s = {}
        if s:
            self.spin_win.setValue(float(s.get('win', 10.0)))
            self.chk_link.setChecked(bool(s.get('link', True)))
            self.spin_step.setValue(float(s.get('step', 10.0)))
            self.spin_total.setValue(float(s.get('total', self.spin_total.value())))
            self.spin_count.setValue(int(s.get('count', 100)))
            self.chk_partial.setChecked(bool(s.get('drop', True)))
            self.ed_prefix.setText(str(s.get('prefix', '自動')))
            self.chk_clear.setChecked(bool(s.get('clear', True)))
            b = self._r_grp.button(int(s.get('mode', 0)))
            if b is not None:
                b.setChecked(True)
        self._sync_link()

    def _save(self):
        s = {'win': self.spin_win.value(), 'step': self.spin_step.value(),
             'link': self.chk_link.isChecked(),
             'mode': self._r_grp.checkedId(),
             'total': self.spin_total.value(), 'count': self.spin_count.value(),
             'drop': self.chk_partial.isChecked(),
             'prefix': self.ed_prefix.text(), 'clear': self.chk_clear.isChecked()}
        try:
            QSettings(_SETTINGS_ORG, _SETTINGS_APP).setValue(
                self._KEY, json.dumps(s))
        except Exception:
            pass

    # ── 計算預覽 ──────────────────────────────────────────────────────────
    def _compute(self):
        """依目前的輸入產生區間清單。回傳 (windows, 錯誤訊息)。"""
        mode = self._r_grp.checkedId()
        win, step = self.spin_win.value(), self.spin_step.value()
        dur = self.duration
        start = 0.0
        if mode != 0:
            start = parse_time_str(self.ed_start.text())
            if start is None:
                return [], '起點時間無法解析。'
            if not (0 <= start < dur):
                return [], f'起點超出檔案範圍（0 – {dur:.1f} 秒）。'
        end, count = None, None
        if mode == 1:
            end = start + self.spin_total.value()
        elif mode == 2:
            count = self.spin_count.value()
        elif mode == 3:
            end = parse_time_str(self.ed_end.text())
            if end is None:
                return [], '結束時間無法解析。'
            if end <= start:
                return [], '結束時間必須大於起點。'
        wins = make_auto_windows(dur, win, step, start, end, count,
                                 self.chk_partial.isChecked())
        if not wins:
            return [], '這個範圍放不下任何一段，請縮短每段長度或擴大範圍。'
        return wins, ''

    def _update(self, *_):
        mode = self._r_grp.checkedId()
        self.ed_start.setEnabled(mode != 0)
        self.spin_total.setEnabled(mode == 1)
        self.spin_count.setEnabled(mode == 2)
        self.ed_end.setEnabled(mode == 3)
        self.lbl_end.setEnabled(mode == 3)
        st = parse_time_str(self.ed_start.text())
        self.lbl_start_note.setText(
            f'（時鐘 {self.data.abs_time(st)}）' if (st is not None and mode != 0
                                                and 0 <= st < self.duration)
            else '')

        wins, err = self._compute()
        self._windows = wins
        self.b_ok.setEnabled(bool(wins))
        if err:
            self.lbl_prev.setText('⚠ ' + err)
            self.lbl_prev.setStyleSheet(
                f'color:{C["yellow"]};font-size:12px;border:1px solid {C["border"]};'
                f'border-radius:4px;padding:6px 8px;background:{C["panel"]};')
            return
        a, b = wins[0][0], wins[-1][1]
        win, step = self.spin_win.value(), self.spin_step.value()
        how = ('連續不重疊' if abs(step - win) < 1e-9
               else (f'每隔 {step:g} 秒取 {win:g} 秒' if step > win
                     else f'重疊 {win - step:g} 秒的滑動視窗'))
        txt = (f'將產生 {len(wins)} 段（{how}），範圍 {fmt_hms(a)} → {fmt_hms(b)}'
               f'（時鐘 {self.data.abs_time(a)} → {self.data.abs_time(b)}）')
        last = wins[-1][1] - wins[-1][0]
        if last < win - 1e-6:
            txt += f'\n最後一段只有 {last:.1f} 秒。'
        if len(wins) > 2000:
            txt += '\n⚠ 段數很多，計算會花一些時間（可隨時取消）。'
        self.lbl_prev.setText(txt)
        self.lbl_prev.setStyleSheet(
            f'color:{C["accent"]};font-size:12px;border:1px solid {C["border"]};'
            f'border-radius:4px;padding:6px 8px;background:{C["panel"]};')

    def _on_ok(self):
        if not self._windows:
            return
        self._save()
        self.accept()

    def result_settings(self):
        """回傳 (windows, 標籤前綴, 是否先清除舊的自動區間)。"""
        return (list(self._windows), self.ed_prefix.text().strip() or '自動',
                self.chk_clear.isChecked())


def pair_marks_to_intervals(marks: list):
    """把時間點位配對成分析區間。

    規則：依時間排序後，每個「起點」和它之後最近的一個「終點」配成一段。
    已被配掉的終點不會再被使用，所以 起-終-起-終 會得到兩段，
    而 起-起-終 只會用到第二個起點（第一個起點沒有對應的終點，會被標成未配對）。

    回傳 (intervals, unpaired)：
      intervals — [{'label', 't0', 't1', 'i_start', 'i_end'}]
      unpaired  — 沒有配到對的點位索引
    """
    order = sorted(range(len(marks)), key=lambda i: marks[i]['t'])
    intervals = []
    used = set()
    pending_start = None
    for i in order:
        m = marks[i]
        if m.get('kind') == 'start':
            pending_start = i
        else:
            if pending_start is not None:
                a, b = marks[pending_start], m
                if b['t'] > a['t']:
                    label = a.get('name') or '區間'
                    if b.get('name') and b['name'] != a.get('name'):
                        label = f"{a.get('name')} → {b['name']}"
                    intervals.append({
                        'label': label,
                        't0': float(a['t']), 't1': float(b['t']),
                        'i_start': pending_start, 'i_end': i})
                    used.add(pending_start)
                    used.add(i)
                pending_start = None
    unpaired = [i for i in range(len(marks)) if i not in used]
    return intervals, unpaired


# ── Artifact 判讀 ───────────────────────────────────────────────────────────
# 判讀結果以「起訖時間」為鍵存在 MainWindow.skna_judge（並寫進
# 檔名_SKNA_marks.json），不綁在區間物件上：重新自動分段、換帶通重算，
# 只要區段起訖相同，判讀就會自動套回去。
# 預設一律「保留」，只記錄被判為 Artifact 的區段。
JUDGE_LABEL = {'artifact': 'Artifact', 'keep': '保留', None: '保留'}


def judge_key(t0: float, t1: float) -> str:
    return f'{float(t0):.3f}-{float(t1):.3f}'


class ArtifactReviewDialog(QDialog):
    """逐段檢視 SKNA 區間，人工判讀為「保留」或「Artifact」。

    Bandpass 與 S3 都可用：軌道顯示哪一種就看哪一種的波形判讀，判讀結果
    同時套用到該區段的所有指標（BPF、S3、Nerveact 相容）。
    主視窗會跟著跳到每一段（前後各多顯示一點），並把目前這段框起來。
    """
    MARGIN = 1.0   # 前後多顯示的秒數

    def __init__(self, main_window, start: int = 0):
        super().__init__(main_window, Qt.WindowType.Tool)
        self.mw = main_window
        self.setWindowTitle('Artifact')
        self.setModal(False)
        self.setStyleSheet(_dialog_style())
        self.i = 0
        self._build()
        self.goto(start)

    # ── UI ──
    def _build(self):
        lay = QVBoxLayout(self); lay.setSpacing(8)
        lay.setContentsMargins(14, 12, 14, 12)
        top = QHBoxLayout(); top.setSpacing(6)
        self.lbl_pos = QLabel('')
        self.lbl_pos.setStyleSheet(f'color:{C["accent"]};font-size:15px;font-weight:bold;')
        top.addWidget(self.lbl_pos)
        top.addStretch()
        top.addWidget(HelpBadge(
            '逐段檢視 SKNA 波形（軌道上顯示 Bandpass 或 S3 都可以），每段預設為「保留」，'
            '看到 artifact 就標記為 Artifact。\n\n'
            '快捷鍵：\n'
            '  K／空白鍵　保留\n'
            '  A／X　　　Artifact\n'
            '  ←／→　　 上一段／下一段\n'
            '  Esc　　　 完成\n\n'
            '判讀結果會自動存檔（檔名_SKNA_marks.json），以區段起訖時間對應；'
            '重新分段或改帶通重算後，起訖相同的區段仍會套用。'
            '匯出 Excel 時，總表會分別列出全部區間與排除 Artifact 後的統計。',
            self))
        lay.addLayout(top)
        self.lbl_time = QLabel('')
        self.lbl_time.setStyleSheet(f'color:{C["text"]};font-size:12px;')
        lay.addWidget(self.lbl_time)
        self.lbl_vals = WrapLabel('')
        self.lbl_vals.setStyleSheet(f'color:{C["dim"]};font-size:12px;')
        lay.addWidget(self.lbl_vals)
        self.lbl_state = QLabel('')
        self.lbl_state.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(self.lbl_state)

        def btn(text, tip, fn, obj=None):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)   # 讓快捷鍵不被按鈕吃掉
            if obj:
                b.setObjectName(obj)
            b.clicked.connect(fn)
            return b

        r1 = QHBoxLayout(); r1.setSpacing(6)
        r1.addWidget(btn('◀ 上一段', '←', lambda: self.goto(self.i - 1)))
        self.b_keep = btn('✓ 保留  (K)', 'K 或空白鍵', lambda: self.judge('keep'))
        self.b_art = btn('✗ Artifact  (A)', 'A 或 X', lambda: self.judge('artifact'),
                         'btn_danger')
        r1.addWidget(self.b_keep); r1.addWidget(self.b_art)
        r1.addWidget(btn('下一段 ▶', '→', lambda: self.goto(self.i + 1)))
        lay.addLayout(r1)

        r2 = QHBoxLayout(); r2.setSpacing(6)
        self.chk_auto = QCheckBox('判讀後自動跳到下一段')
        self.chk_auto.setChecked(True)
        self.chk_auto.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        r2.addWidget(self.chk_auto)
        r2.addStretch()
        r2.addWidget(btn('完成', 'Esc', self.close))
        lay.addLayout(r2)

        self.lbl_count = QLabel('')
        self.lbl_count.setStyleSheet(f'color:{C["dim"]};font-size:11px;')
        lay.addWidget(self.lbl_count)

        K = Qt.Key
        self._keymap = {
            K.Key_K: lambda: self.judge('keep'),
            K.Key_Space: lambda: self.judge('keep'),
            K.Key_A: lambda: self.judge('artifact'),
            K.Key_X: lambda: self.judge('artifact'),
            K.Key_Left: lambda: self.goto(self.i - 1),
            K.Key_Right: lambda: self.goto(self.i + 1),
        }
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumWidth(460)

    # 這個視窗是主視窗的 Tool 子視窗，主視窗的快捷鍵（K＝SKNA 開關、
    # R、P…）在這裡也會生效。先在 ShortcutOverride 階段把判讀用的按鍵
    # 攔下來，按鍵才會交給這個視窗，而不是去觸發主視窗的功能。
    def event(self, e):
        if e.type() == QEvent.Type.ShortcutOverride and \
                e.modifiers() == Qt.KeyboardModifier.NoModifier and \
                e.key() in self._keymap:
            e.accept()
            return True
        return super().event(e)

    def keyPressEvent(self, e):
        fn = self._keymap.get(e.key()) \
            if e.modifiers() == Qt.KeyboardModifier.NoModifier else None
        if fn is not None and not e.isAutoRepeat():
            fn()
            e.accept()
            return
        if fn is not None:
            e.accept()
            return
        super().keyPressEvent(e)

    # ── 邏輯 ──
    @property
    def rows(self):
        return self.mw.skna_rows

    def _state(self, i):
        r = self.rows[i]
        return ('artifact' if self.mw.skna_judge.get(judge_key(r['t0'], r['t1']))
                == 'artifact' else 'keep')

    def goto(self, i: int):
        n = len(self.rows)
        if n == 0:
            self.close()
            return
        self.i = max(0, min(n - 1, int(i)))
        r = self.rows[self.i]
        self.mw._review_cur = (r['t0'], r['t1'])
        self.mw.waveform.show_range(r['t0'] - self.MARGIN, r['t1'] + self.MARGIN)
        self.mw._update_review_overlay()
        try:
            self.mw.side.skna_list.setCurrentRow(self.i)
        except Exception:
            pass
        self._refresh()

    def judge(self, state):
        if not self.rows:
            return
        self.mw.skna_set_judge([self.i], state)
        if self.chk_auto.isChecked() \
                and self.i < len(self.rows) - 1:
            self.goto(self.i + 1)
        else:
            self.goto(self.i)

    def _refresh(self):
        n = len(self.rows)
        r = self.rows[self.i]
        res = r.get('res') or {}
        a = res.get('all', {}) if res.get('ok') else {}
        na = res.get('nact', {}) if res.get('ok') else {}
        a2 = res.get('all2', {}) if res.get('ok') else {}
        na2 = res.get('nact2', {}) if res.get('ok') else {}
        unit = res.get('unit', 'µV')
        self.lbl_pos.setText(f'第 {self.i + 1} / {n} 段　｜　{r.get("label", "")}')
        self.lbl_time.setText(f"{fmt_hms(r['t0'])} → {fmt_hms(r['t1'])}"
                              f"（{r['t1'] - r['t0']:.1f} s）")
        parts = []
        for m_, b_ in ((a, res.get('band1', '')), (a2, res.get('band2', ''))):
            if m_.get('aSKNA') is not None:
                parts.append(f"BPF {b_} aSKNA {m_['aSKNA']:.3f} {unit}")
        s3_ = res.get('s3', {}) if res.get('ok') else {}
        if s3_.get('aSKNA') is not None:
            parts.append(f"S3 aSKNA {s3_['aSKNA']:.3f} {unit}")
        if na.get('aSKNA') is not None:
            parts.append(f"Nerveact aSKNA {na['aSKNA']:.3f}"
                         + (f" / {na2['aSKNA']:.3f}" if na2.get('aSKNA') is not None else '')
                         + f" {unit}")
        flags = res.get('flags', [])
        if flags:
            parts.append('⚠ ' + '、'.join(flags))
        self.lbl_vals.setText('　'.join(parts) or '（尚未計算）')
        st = self._state(self.i)
        col = C['red'] if st == 'artifact' else C['green']
        self.lbl_state.setText(
            f'<span style="color:{C["dim"]}">目前判讀：</span>'
            f'<span style="color:{col};font-weight:bold;font-size:14px;">'
            f'{JUDGE_LABEL[st]}</span>')
        n_art = sum(1 for k in range(n) if self._state(k) == 'artifact')
        self.lbl_count.setText(f"保留 {n - n_art}　Artifact {n_art}　（共 {n} 段）")

    def _finish(self):
        """判讀結束的清理。按「完成」、視窗關閉鈕或 Esc 都會走到這裡；
        Esc 走的是 reject() → done()，不會觸發 closeEvent，所以兩邊都要接。"""
        if getattr(self, '_finished', False):
            return
        self._finished = True
        self.mw._review_cur = None
        self.mw.review_dlg = None
        # 紅色 Artifact 標記與橘色框只在判讀時顯示，結束後全部清掉
        self.mw._update_review_overlay()
        # 從「SKNA 區間分析」進來時那個視窗先收起來，判讀完再叫回來
        if getattr(self.mw, '_review_restore_dlg', False) and self.mw.skna_dlg is not None:
            self.mw._review_restore_dlg = False
            self.mw.skna_dlg._rebuild_table()
            self.mw.skna_dlg.show()
            self.mw.skna_dlg.raise_()

    def closeEvent(self, ev):
        super().closeEvent(ev)
        self._finish()

    def done(self, r):
        super().done(r)
        self._finish()


class SknaIntervalDialog(QDialog):
    """SKNA 區間分析表格 + Excel 匯出。"""

    N_COLS = 21

    def _col_labels(self):
        """表格欄位標題。振幅類欄位的單位取決於來源通道，所以動態產生。"""
        u = 'µV'
        d, cfg = self.mw.ecg_data, self.mw.skna_cfg
        if d is not None and cfg.get('src_ch') is not None:
            try:
                _, u = unit_to_uv(d.ch_units[cfg['src_ch']])
            except Exception:
                pass
        b1, b2 = skna_band_label(cfg, 1), skna_band_label(cfg, 2)
        return ['標籤', '起始', '結束', '時長 (s)', 'HR (bpm)', '心跳數',
                f'BPF {b1}\naSKNA ({u})', f'BPF {b1}\niSKNA ({u}·s)',
                f'BPF {b2}\naSKNA ({u})', f'BPF {b2}\niSKNA ({u}·s)',
                f'S3 aSKNA\n({u})', f'S3 iSKNA\n({u}·s)',
                f'S3 RMS\n({u})', f'S3 Peak\n({u})',
                f'Nerveact {b1}\naSKNA ({u})', f'Nerveact {b1}\niSKNA ({u}·s)',
                f'Nerveact {b2}\naSKNA ({u})', f'Nerveact {b2}\niSKNA ({u}·s)',
                '無效訊號 (%)', '品質', '判讀']

    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.mw = main_window
        self.setWindowTitle('SKNA 區間分析')
        self.setModal(False)
        self.resize(1200, 560)
        self.setStyleSheet(_dialog_style())
        self._build()

    @property
    def rows(self):
        """區間清單存在 MainWindow，側邊欄與這個視窗共用同一份資料，
        任何一邊新增或刪除，另一邊立刻同步。"""
        return self.mw.skna_rows

    @rows.setter
    def rows(self, v):
        self.mw.skna_rows = list(v)

    def _build(self):
        lay = QVBoxLayout(self); lay.setSpacing(8)
        lay.setContentsMargins(12, 12, 12, 12)

        self.lbl_cfg = QLabel('')
        self.lbl_cfg.setWordWrap(True)
        self.lbl_cfg.setStyleSheet(
            f'color:{C["dim"]};font-size:11px;border:1px solid {C["border"]};'
            f'border-radius:4px;padding:6px 8px;background:{C["panel"]};')
        lay.addWidget(self.lbl_cfg)

        row1 = QHBoxLayout(); row1.setSpacing(6)
        self.badge = HelpBadge(
            '建立區間：\n'
            '  ＋ 加入目前選取範圍 — 用測量模式 (M) 圈選的 A→B 範圍\n'
            '  ＋ 手動輸入 — 直接打起訖時間\n'
            '  ＋ 從時間戳記匯入 — 已存的、有起訖範圍的時間戳記\n'
            '  ＋ 目前顯示範圍 — 畫面上看到的那一段\n'
            '  ⏱ 自動分段計算 — 設定每段長度、間隔與範圍（整檔、總長幾秒、'
            '幾段、或指定起訖），一次產生並算完\n'
            '另外，SKNA 頁的時間點位配對出來的區間（前面有 📍）會自動出現在'
            '這裡，與側邊欄同步。\n\n'
            '複製數值：拖曳框選儲存格後按 ⌘C／Ctrl+C，貼到 Excel 欄位會自動'
            '對齊；按右鍵還可以選「含欄位標題」或「複製整列」。\n\n'
            '匯出：「匯出並開啟 Excel」不問位置，直接產生暫存檔並用 Excel '
            '打開，要保留請在 Excel 裡另存新檔；「另存新檔...」則是自己選位置'
            '存成永久檔。\n\n'
            '標籤欄可以直接雙擊修改。改動 SKNA 設定或跑完 S3 之後，'
            '按「重新計算全部」會用新設定重算所有區間。',
            self)
        row1.addWidget(self.badge)
        b_sel = QPushButton('＋ 加入目前選取範圍')
        b_sel.setToolTip('把測量模式 (M) 圈選的 A→B 範圍加入清單')
        b_sel.clicked.connect(self._add_from_measure)
        b_man = QPushButton('＋ 手動輸入')
        b_man.clicked.connect(self._add_manual)
        b_ts = QPushButton('＋ 從時間戳記匯入')
        b_ts.setToolTip('把已儲存、且有起訖範圍的時間戳記加入清單')
        b_ts.clicked.connect(self._add_from_timestamps)
        b_view = QPushButton('＋ 目前顯示範圍')
        b_view.clicked.connect(self._add_from_view)
        b_auto = QPushButton('⏱ 自動分段計算…')
        b_auto.setToolTip('設定每段長度與間隔（例如每 10 秒一段），\n'
                          '一次對整個檔案或指定範圍產生區間並計算 SKNA')
        b_auto.clicked.connect(self._add_auto)
        b_rev = QPushButton('Artifact')
        b_rev.setToolTip('依序檢視每一段 SKNA 波形，預設保留，'
                         '標出 Artifact 區段（Bandpass 與 S3 都可用）')
        b_rev.clicked.connect(lambda: self.mw._open_artifact_review(
            self._first_selected_row(), from_dialog=True))
        for b in (b_sel, b_man, b_ts, b_view, b_auto, b_rev):
            row1.addWidget(b)
        row1.addStretch()
        lay.addLayout(row1)

        self.table = QTableWidget(0, self.N_COLS)
        self.table.setHorizontalHeaderLabels(self._col_labels())
        # 可以框選個別儲存格（而不是整列），才能只複製想要的那幾個數字。
        # 刪除選取列仍然是看選取範圍涵蓋到哪幾列，所以不受影響。
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.SelectedClicked)
        self.table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._table_menu)
        sc = QShortcut(QKeySequence.StandardKey.Copy, self.table)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(self._copy_cells)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._on_item_changed)
        lay.addWidget(self.table, 1)

        row2 = QHBoxLayout(); row2.setSpacing(6)
        b_del = QPushButton('刪除選取列'); b_del.clicked.connect(self._delete_rows)
        b_up = QPushButton('重新計算全部'); b_up.clicked.connect(self.recalc_all)
        b_clr = QPushButton('清空'); b_clr.clicked.connect(self._clear)
        row2.addWidget(b_del); row2.addWidget(b_up); row2.addWidget(b_clr)
        row2.addStretch()
        b_save = QPushButton('另存新檔...')
        b_save.setToolTip('自己選位置與檔名，存成永久檔案')
        b_save.clicked.connect(self._export_as)
        row2.addWidget(b_save)
        b_xl = QPushButton('匯出並開啟 Excel')
        b_xl.setToolTip('直接產生結果並用 Excel 開啟，不先問存檔位置。\n'
                        '產生的是暫存檔，要保留請在 Excel 裡「另存新檔」。')
        b_xl.setStyleSheet(
            f'QPushButton{{background:{C["accent"]};color:{C["bg"]};'
            f'border:none;border-radius:5px;padding:6px 20px;font-weight:bold;}}'
            f'QPushButton:hover{{background:#79c0ff;}}')
        b_xl.clicked.connect(self._export)
        row2.addWidget(b_xl)
        b_close = QPushButton('關閉'); b_close.clicked.connect(self.close)
        row2.addWidget(b_close)
        lay.addLayout(row2)

        self.lbl_status = QLabel('尚未加入任何區間。')
        self.lbl_status.setStyleSheet(f'color:{C["dim"]};font-size:11px;')
        lay.addWidget(self.lbl_status)


        self.refresh_header()
        self.finished.connect(lambda *_: HelpBadge.close_all())
        # 區間清單存在 MainWindow，開窗時可能側邊欄已經節錄了幾段，
        # 一開始就要把它們畫出來
        self._rebuild_table()

    def refresh_header(self):
        cfg = self.mw.skna_cfg
        d = self.mw.ecg_data
        if d is None or cfg.get('src_ch') is None:
            self.lbl_cfg.setText('尚未載入檔案。')
            return
        src, ecg = cfg['src_ch'], cfg['ecg_ch']
        fs = d.fs_of(src)
        lo, hi, warn = skna_effective_band(fs, cfg['bp_lo'], cfg['bp_hi'])
        _, unit = unit_to_uv(d.ch_units[src])
        txt = (f"來源 CH{src}: {d.ch_names[src]} ({fs:,.0f} Hz)　|　"
               f"ECG 參考 CH{ecg}: {d.ch_names[ecg]}　|　"
               f"帶通 軌道2 {lo:.0f}–{hi:.0f}／軌道3 {skna_band_label(cfg, 2)} Hz"
               f" ({cfg['order']} 階)　|　"
               f"包絡 {cfg['env_ms']:.0f} ms　|　單位 {unit}")
        c3 = self.mw.s3_cache
        if c3 is not None and self.mw._s3_is_valid():
            rng = ('整檔' if c3.get('whole_file')
                   else f"{fmt_hms(c3['t0'])}–{fmt_hms(c3['t1'])}")
            txt += (f"\nS3 已分解（{rng}）：{c3['n_beat']} 心跳，"
                    f"片段 {c3['p1'] + c3['p2'] + 1} 點，有效秩 {c3['rank']}，"
                    f"K={cfg.get('s3_K', 30)}")
        else:
            txt += ("\nS3 尚未分解 — S3 欄位會是空的。"
                    "按右側欄位的「S3 分解（整檔）」後再回來按「重新計算全部」。")
        if warn:
            txt += f"\n⚠ {warn}"
        self.lbl_cfg.setText(txt)

    def _add(self, t0: float, t1: float, label: str = ''):
        if self.mw.ecg_data is None or t1 <= t0:
            return
        if not label:
            label = f'區間 {len(self.rows) + 1}'
        self.rows.append({'label': label, 't0': t0, 't1': t1,
                          'res': None, 'src': ''})
        self._compute_row(len(self.rows) - 1)
        self._rebuild_table()

    def _add_from_measure(self):
        pts = self.mw.waveform.measure_pts
        if len(pts) < 2:
            QMessageBox.information(
                self, '沒有選取範圍',
                '請先按 M 進入測量模式，在波形上點擊 A 點與 B 點，'
                '再回到這裡按「加入目前選取範圍」。')
            return
        a, b = sorted(pts[:2])
        self._add(a, b)

    def _add_from_view(self):
        self._add(self.mw.waveform.t_start, self.mw.waveform.t_end)

    def _add_manual(self):
        if self.mw.ecg_data is None:
            return
        dlg = IntervalInputDialog(self, self.mw.ecg_data.duration)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            iv = dlg.get_interval()
            if iv:
                self._add(iv[0], iv[1], iv[2])

    def _add_from_timestamps(self):
        mgr = self.mw.ts_mgr
        if mgr is None or not (getattr(mgr, 'records', None) or getattr(mgr, 'stamps', None)):
            QMessageBox.information(self, '沒有時間戳記',
                                    '目前檔案還沒有任何已儲存的時間戳記。')
            return
        n = 0
        for st in (getattr(mgr, 'records', None) or getattr(mgr, 'stamps', None) or []):
            a = st.get('t_start')
            b = st.get('t_end')
            if a is None or b is None or float(b) <= float(a):
                continue
            lbl = st.get('label') or st.get('tag') or ''
            self.rows.append({'label': lbl, 't0': float(a), 't1': float(b),
                              'res': None, 'src': ''})
            self._compute_row(len(self.rows) - 1)
            n += 1
        if n == 0:
            QMessageBox.information(
                self, '沒有可用的時間戳記',
                '只有含「起訖範圍」的時間戳記才能當作分析區間；'
                '單一時間點的戳記沒有長度，無法計算。')
            return
        self._rebuild_table()

    def _time_points(self):
        """自動分段可選的時間：SKNA 時間點位 + 時間戳記（起／迄）。"""
        pts = []
        for m in (self.mw.skna_marks or []):
            try:
                t = float(m['t'])
            except Exception:
                continue
            kind = 'end' if m.get('kind') == 'end' else 'start'
            name = str(m.get('name', ''))
            pts.append((t, f"📍 {name} {'起點' if kind == 'start' else '終點'}　{fmt_hms(t)}",
                        name, kind))
        mgr = self.mw.ts_mgr
        for st in (getattr(mgr, 'records', None) or []) if mgr else []:
            lbl = str(st.get('label') or st.get('tag') or '時間戳記')
            a, b = st.get('t_start'), st.get('t_end')
            if a is not None:
                pts.append((float(a), f"🕒 {lbl}{' 起' if b is not None else ''}　{fmt_hms(float(a))}",
                            '🕒' + lbl, 'start' if b is not None else ''))
            if b is not None:
                pts.append((float(b), f"🕒 {lbl} 迄　{fmt_hms(float(b))}", '🕒' + lbl, 'end'))
        return sorted(pts, key=lambda p: p[0])

    def _add_auto(self):
        d = self.mw.ecg_data
        if d is None or self.mw.skna_cfg.get('src_ch') is None:
            return
        dlg = AutoWindowDialog(self, d, self._time_points())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        wins, prefix, clear = dlg.result_settings()
        if not wins:
            return

        old = list(self.rows)
        if clear:
            self.rows = [r for r in self.rows if r.get('kind') != 'auto']
        base = len(self.rows)
        width = len(str(len(wins)))
        for k, (a, b) in enumerate(wins, start=1):
            self.rows.append({'label': f'{prefix} {k:0{width}d}',
                              't0': float(a), 't1': float(b),
                              'res': None, 'src': '', 'kind': 'auto'})

        # 大量區間時在主執行緒逐段算，用進度對話框讓畫面不會像當掉，
        # 也能中途取消（取消就還原成原本的清單）
        prog = QProgressDialog('計算 SKNA…', '取消', 0, len(wins), self)
        prog.setWindowTitle('自動分段計算')
        prog.setWindowModality(Qt.WindowModality.WindowModal)
        prog.setMinimumDuration(300)
        cancelled = False
        for k in range(len(wins)):
            if prog.wasCanceled():
                cancelled = True
                break
            self._compute_row(base + k)
            if k % 5 == 0:
                prog.setValue(k)
                prog.setLabelText(f'計算 SKNA… {k + 1} / {len(wins)}')
                QApplication.processEvents()
        prog.setValue(len(wins))
        if cancelled:
            self.rows = old
            self._rebuild_table()
            self.lbl_status.setText('已取消自動分段，清單維持原狀。')
            return
        self._rebuild_table()
        self.lbl_status.setText(
            self.lbl_status.text() +
            f'　已自動產生 {len(wins)} 段：{fmt_hms(wins[0][0])} → '
            f'{fmt_hms(wins[-1][1])}。')

    def _compute_row(self, i: int):
        d = self.mw.ecg_data
        cfg = self.mw.skna_cfg
        if d is None or cfg.get('src_ch') is None:
            return
        r = self.rows[i]
        rt, src = skna_rpeak_times(
            d, cfg, r['t0'], r['t1'],
            cached_peaks=self.mw.waveform._peaks_cache,
            cached_ch=self.mw.waveform.ch_idx)
        r['res'] = analyze_skna_interval(d, cfg, r['t0'], r['t1'], rt,
                                         s3_sig=self.mw._s3_signal())
        r['src'] = src

    def recalc_all(self):
        if not self.rows:
            self.refresh_header()
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for i in range(len(self.rows)):
                self._compute_row(i)
        finally:
            QApplication.restoreOverrideCursor()
        self._rebuild_table()
        self.refresh_header()

    @staticmethod
    def _fmt(v, nd: int = 4) -> str:
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            return '—'
        return f'{v:.{nd}f}'

    def _rebuild_table(self):
        self.mw._sync_skna_side()
        self.table.blockSignals(True)
        self.table.setHorizontalHeaderLabels(self._col_labels())
        self.table.setRowCount(len(self.rows))
        d = self.mw.ecg_data
        for i, r in enumerate(self.rows):
            res = r['res'] or {}
            a = res.get('all', {}) if res.get('ok') else {}
            s3 = res.get('s3', {}) if res.get('ok') else {}
            na = res.get('nact', {}) if res.get('ok') else {}
            a2 = res.get('all2', {}) if res.get('ok') else {}
            na2 = res.get('nact2', {}) if res.get('ok') else {}
            t0s = d.abs_time(r['t0']) if d else fmt_hms(r['t0'])
            t1s = d.abs_time(r['t1']) if d else fmt_hms(r['t1'])
            hr = res.get('hr', float('nan'))
            flags = res.get('flags', [])
            vals = [
                r['label'],
                f"{fmt_hms(r['t0'])}\n{t0s}",
                f"{fmt_hms(r['t1'])}\n{t1s}",
                f"{r['t1'] - r['t0']:.3f}",
                ('—' if not np.isfinite(hr) else f'{hr:.0f}'),
                str(res.get('n_beat', 0)),
                self._fmt(a.get('aSKNA')), self._fmt(a.get('iSKNA'), 2),
                self._fmt(a2.get('aSKNA')), self._fmt(a2.get('iSKNA'), 2),
                self._fmt(s3.get('aSKNA')), self._fmt(s3.get('iSKNA'), 2),
                self._fmt(s3.get('RMS')), self._fmt(s3.get('peak')),
                self._fmt(na.get('aSKNA')), self._fmt(na.get('iSKNA'), 2),
                self._fmt(na2.get('aSKNA')), self._fmt(na2.get('iSKNA'), 2),
                self._fmt(res.get('bad_pct'), 1),
                ('✓' if not flags else '⚠ ' + '、'.join(flags)),
                JUDGE_LABEL.get(r.get('judge'), '保留'),
            ]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if j != 0:
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if j >= 3:
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight |
                                        Qt.AlignmentFlag.AlignVCenter)
                if j == len(vals) - 1:
                    if r.get('judge') == 'artifact':
                        it.setForeground(QColor(C['red']))
                if j == len(vals) - 2 and flags:
                    it.setForeground(QColor(C['yellow']))
                self.table.setItem(i, j, it)
        self.table.blockSignals(False)
        self.table.resizeRowsToContents()

        n_flag = sum(1 for r in self.rows if (r['res'] or {}).get('flags'))
        src_note = self.rows[-1]['src'] if self.rows else ''
        msg = f'共 {len(self.rows)} 個區間。'
        if src_note:
            msg += f'　R-peak 來源：{src_note}。'
        if n_flag:
            msg += f'　⚠ {n_flag} 個區間有品質警示，建議先回波形確認。'
        self.lbl_status.setText(msg)
        # 匯出時會把這行改成黃色警告，重建表格時要還原
        self.lbl_status.setStyleSheet(f'color:{C["dim"]};font-size:11px;')

    # ── 複製 ─────────────────────────────────────────────────────────────

    @staticmethod
    def _flat(txt: str) -> str:
        """儲存格裡的換行換成空白，貼到 Excel 才不會把一格拆成兩列。"""
        return ' '.join(str(txt).split('\n')).strip()

    def _selected_block(self):
        """把選取的儲存格整理成矩形區塊。

        回傳 (rows, cols, 表格文字)。沒選到就回傳 None。
        只選幾格就只複製那幾格；框住的矩形裡沒選到的位置留空，
        貼到 Excel 時欄位仍然對得起來。
        """
        idx = self.table.selectedIndexes()
        if not idx:
            return None
        rows = sorted({i.row() for i in idx})
        cols = sorted({i.column() for i in idx})
        picked = {(i.row(), i.column()) for i in idx}
        out = []
        for r in rows:
            line = []
            for c in cols:
                if (r, c) in picked:
                    it = self.table.item(r, c)
                    line.append(self._flat(it.text()) if it else '')
                else:
                    line.append('')
            out.append('\t'.join(line))
        return rows, cols, '\n'.join(out)

    def _copy_cells(self, with_header: bool = False):
        blk = self._selected_block()
        if blk is None:
            self.lbl_status.setText('請先選取要複製的儲存格（可拖曳框選）。')
            self.lbl_status.setStyleSheet(f'color:{C["yellow"]};font-size:11px;')
            return
        rows, cols, text = blk
        if with_header:
            labels = self._col_labels()
            head = '\t'.join(self._flat(labels[c]) if c < len(labels) else ''
                              for c in cols)
            text = head + '\n' + text
        QApplication.clipboard().setText(text)
        self.lbl_status.setText(
            f'已複製 {len(rows)} 列 × {len(cols)} 欄'
            + ('（含欄位標題）' if with_header else '')
            + ' — 可直接貼到 Excel。')
        self.lbl_status.setStyleSheet(f'color:{C["green"]};font-size:11px;')

    def _copy_rows(self):
        """把選取範圍涵蓋到的整列複製起來（含所有欄位）。"""
        idx = self.table.selectedIndexes()
        if not idx:
            self.lbl_status.setText('請先選取至少一列。')
            self.lbl_status.setStyleSheet(f'color:{C["yellow"]};font-size:11px;')
            return
        rows = sorted({i.row() for i in idx})
        labels = self._col_labels()
        lines = ['\t'.join(self._flat(x) for x in labels)]
        for r in rows:
            lines.append('\t'.join(
                self._flat(self.table.item(r, c).text())
                if self.table.item(r, c) else ''
                for c in range(self.table.columnCount())))
        QApplication.clipboard().setText('\n'.join(lines))
        self.lbl_status.setText(
            f'已複製 {len(rows)} 整列（含欄位標題）— 可直接貼到 Excel。')
        self.lbl_status.setStyleSheet(f'color:{C["green"]};font-size:11px;')

    def _table_menu(self, pos):
        menu = QMenu(self.table)
        menu.setStyleSheet(
            f'QMenu{{background:{C["panel"]};border:1px solid {C["border"]};'
            f'color:{C["text"]};padding:4px;}}'
            f'QMenu::item{{padding:5px 22px;}}'
            f'QMenu::item:selected{{background:{C["accent"]};color:{C["bg"]};}}')
        has = bool(self.table.selectedIndexes())
        a1 = menu.addAction('複製選取的儲存格\t⌘C')
        a2 = menu.addAction('複製選取的儲存格（含欄位標題）')
        a3 = menu.addAction('複製整列（含欄位標題）')
        menu.addSeparator()
        menu.addSeparator()
        j1 = menu.addAction('標記為 Artifact')
        j2 = menu.addAction('標記為保留')
        j4 = menu.addAction('從這一列開始 Artifact 判讀…')
        for a in (j1, j2, j4):
            a.setEnabled(has)
        menu.addSeparator()
        a4 = menu.addAction('全選')
        for a in (a1, a2, a3):
            a.setEnabled(has)
        act = menu.exec(self.table.viewport().mapToGlobal(pos))
        if act is a1:
            self._copy_cells()
        elif act is a2:
            self._copy_cells(with_header=True)
        elif act is a3:
            self._copy_rows()
        elif act in (j1, j2):
            sel = sorted({i.row() for i in self.table.selectedIndexes()})
            self.mw.skna_set_judge(sel, 'artifact' if act is j1 else 'keep')
        elif act is j4:
            self.mw._open_artifact_review(self._first_selected_row(),
                                          from_dialog=True)
        elif act is a4:
            self.table.selectAll()

    def _on_item_changed(self, item):
        if item.column() != 0:
            return
        i = item.row()
        if 0 <= i < len(self.rows):
            self.rows[i]['label'] = item.text()

    def _delete_rows(self):
        idx = sorted({i.row() for i in self.table.selectedIndexes()},
                     reverse=True)
        for i in idx:
            if 0 <= i < len(self.rows):
                self.rows.pop(i)
        if idx:
            self._rebuild_table()

    def _clear(self):
        if self.rows and QMessageBox.question(
                self, '清空', '確定要清除所有區間嗎？') \
                != QMessageBox.StandardButton.Yes:
            return
        self.rows = []
        self._rebuild_table()

    def _first_selected_row(self) -> int:
        sel = sorted({i.row() for i in self.table.selectedIndexes()})
        return sel[0] if sel else 0

    def _write_xlsx(self, path: str) -> bool:
        """實際寫檔，錯誤都轉成對話框。成功回傳 True。"""
        try:
            self.mw._apply_judge()
            export_skna_xlsx(
                path, self.mw.ecg_data, self.mw.skna_cfg, self.rows,
                s3_info=(self.mw.s3_cache if self.mw._s3_is_valid() else None))
        except PermissionError:
            QMessageBox.critical(
                self, '無法寫入',
                f'檔案可能正在 Excel 中開啟，請先關閉再試一次：\n{path}')
            return False
        except Exception as ex:
            QMessageBox.critical(self, '匯出失敗',
                                 f'{ex}\n\n{traceback.format_exc()}')
            return False
        return True

    def _export(self):
        """直接產生結果並用 Excel 開啟，不先問存檔位置。

        產生的是暫存檔：先看到數字、確認沒問題，再在 Excel 裡「另存新檔」
        決定要不要留、要留在哪。想一步到位選位置的話用旁邊的「另存新檔...」。
        """
        if not self._check_rows():
            return
        d = self.mw.ecg_data
        base = os.path.splitext(os.path.basename(d.path))[0] or 'SKNA'
        tmpdir = os.path.join(tempfile.gettempdir(), 'ECG Analyzer SKNA')
        try:
            os.makedirs(tmpdir, exist_ok=True)
        except Exception:
            tmpdir = tempfile.gettempdir()
        path = unique_path(os.path.join(tmpdir, f'{base}_SKNA.xlsx'))
        if not self._write_xlsx(path):
            return
        ok, err = open_in_default_app(path)
        if ok:
            self.lbl_status.setText(
                f'已用 Excel 開啟暫存檔 {os.path.basename(path)} — '
                f'⚠ 這是暫存檔，要保留請在 Excel 裡「另存新檔」')
            self.lbl_status.setStyleSheet(
                f'color:{C["yellow"]};font-size:11px;')
        else:
            # 開不起來（沒裝 Excel 之類）就至少把檔案位置講清楚
            self.lbl_status.setText(f'已產生暫存檔：{path}（無法自動開啟：{err}）')
            self.lbl_status.setStyleSheet(f'color:{C["yellow"]};font-size:11px;')
            QMessageBox.information(
                self, '已產生檔案',
                f'無法自動開啟（{err}）。\n檔案在：\n{path}')

    def _export_as(self):
        """傳統流程：自己選位置與檔名，存成永久檔案。"""
        if not self._check_rows():
            return
        d = self.mw.ecg_data
        base = os.path.splitext(os.path.basename(d.path))[0]
        default = unique_path(
            os.path.join(os.path.dirname(d.path), f'{base}_SKNA.xlsx'))
        path, _ = QFileDialog.getSaveFileName(
            self, '匯出 SKNA 分析結果', default, 'Excel 活頁簿 (*.xlsx)')
        if not path:
            return
        if not self._write_xlsx(path):
            return
        self.lbl_status.setText(f'已匯出：{path}')
        self.lbl_status.setStyleSheet(f'color:{C["green"]};font-size:11px;')

    def _check_rows(self) -> bool:
        if not self.rows:
            QMessageBox.information(self, '沒有資料', '請先加入至少一個時間區間。')
            return False
        return True


def export_skna_xlsx(path: str, data, cfg: dict, rows: list, s3_info=None):
    """把區間分析結果寫成 .xlsx（SKNA Intervals + Settings 兩個分頁）。

    Settings 分頁記錄所有處理參數，是為了讓同一份結果日後能被重現／被
    審稿人檢視：只看數字無法判斷 aSKNA 是在哪個頻帶、有沒有排除 QRS
    的情況下算出來的。
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise ImportError('匯出 Excel 需要 openpyxl 套件：pip3 install openpyxl')

    src = cfg['src_ch']
    fs = data.fs_of(src)
    lo, hi, warn = skna_effective_band(fs, cfg['bp_lo'], cfg['bp_hi'])
    lo2, hi2, warn2 = skna_effective_band(fs, cfg.get('bp_lo2', 500.0),
                                          cfg.get('bp_hi2', 1500.0))
    if warn2:
        warn = ((warn + '；') if warn else '') + '軌道 3：' + warn2
    b1, b2 = skna_band_label(cfg, 1), skna_band_label(cfg, 2)
    _, unit = unit_to_uv(data.ch_units[src])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'SKNA Intervals'
    headers = [
        ('標籤', 16), ('起始 (s)', 11), ('結束 (s)', 11), ('時長 (s)', 10),
        ('起始時刻', 13), ('結束時刻', 13),
        ('心跳數', 8), ('平均 HR (bpm)', 13), ('RR CV (%)', 10),
        (f'BPF {b1} aSKNA ({unit})', 17), (f'BPF {b1} iSKNA ({unit}·s)', 18),
        (f'BPF {b1} RMS ({unit})', 15), (f'BPF {b1} Peak ({unit})', 16),
        (f'BPF {b1} SD ({unit})', 15),
        (f'BPF {b2} aSKNA ({unit})', 17), (f'BPF {b2} iSKNA ({unit}·s)', 18),
        (f'BPF {b2} RMS ({unit})', 15), (f'BPF {b2} Peak ({unit})', 16),
        (f'BPF {b2} SD ({unit})', 15),
        (f'S3 aSKNA ({unit})', 15), (f'S3 iSKNA ({unit}·s)', 16),
        (f'S3 RMS ({unit})', 13), (f'S3 Peak ({unit})', 14),
        (f'S3 SD ({unit})', 13),
        (f'Nerveact {b1} aSKNA ({unit})', 18),
        (f'Nerveact {b1} iSKNA ({unit}·s)', 19),
        (f'Nerveact {b2} aSKNA ({unit})', 18),
        (f'Nerveact {b2} iSKNA ({unit}·s)', 19),
        ('無效訊號 (%)', 12), ('R-peak 來源', 28), ('品質警示', 24),
        ('判讀', 10),
    ]
    hdr_fill = PatternFill('solid', fgColor='1F3864')
    hdr_font = Font(bold=True, color='FFFFFF', size=10)
    thin = Side(style='thin', color='BFBFBF')
    for j, (name, w) in enumerate(headers, start=1):
        c = ws.cell(row=1, column=j, value=name)
        c.fill = hdr_fill
        c.font = hdr_font
        c.alignment = Alignment(horizontal='center', vertical='center',
                                wrap_text=True)
        c.border = Border(bottom=thin)
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = 'A2'
    ws.row_dimensions[1].height = 32

    pct_col = [h for h, _ in headers].index('無效訊號 (%)') + 1
    warn_font = Font(color='9C6500')
    art_fill = PatternFill('solid', fgColor='FCE4D6')
    for i, r in enumerate(rows, start=2):
        res = r.get('res') or {}
        a = res.get('all', {}) if res.get('ok') else {}
        s3 = res.get('s3', {}) if res.get('ok') else {}
        na = res.get('nact', {}) if res.get('ok') else {}
        a2 = res.get('all2', {}) if res.get('ok') else {}
        na2 = res.get('nact2', {}) if res.get('ok') else {}
        flags = res.get('flags', [])

        def num(v):
            if v is None:
                return None
            try:
                v = float(v)
            except (TypeError, ValueError):
                return None
            return v if np.isfinite(v) else None

        vals = [
            r['label'], round(r['t0'], 4), round(r['t1'], 4),
            round(r['t1'] - r['t0'], 4),
            data.abs_time(r['t0']), data.abs_time(r['t1']),
            res.get('n_beat', 0), num(res.get('hr')), num(res.get('rr_cv')),
            num(a.get('aSKNA')), num(a.get('iSKNA')),
            num(a.get('RMS')), num(a.get('peak')), num(a.get('SD')),
            num(a2.get('aSKNA')), num(a2.get('iSKNA')),
            num(a2.get('RMS')), num(a2.get('peak')), num(a2.get('SD')),
            num(s3.get('aSKNA')), num(s3.get('iSKNA')),
            num(s3.get('RMS')), num(s3.get('peak')), num(s3.get('SD')),
            num(na.get('aSKNA')), num(na.get('iSKNA')),
            num(na2.get('aSKNA')), num(na2.get('iSKNA')),
            num(res.get('bad_pct')),
            r.get('src', ''),
            ('、'.join(flags) if flags else ''),
            JUDGE_LABEL.get(r.get('judge'), '保留'),
        ]
        for j, v in enumerate(vals, start=1):
            c = ws.cell(row=i, column=j, value=v)
            if isinstance(v, float):
                c.number_format = '0.0' if j in (8, 9, pct_col) else '0.0000'
            if j == len(vals) - 1 and flags:
                c.font = warn_font
            if r.get('judge') == 'artifact':
                c.fill = art_fill

    _add_judge_summary(wb, ws, headers, len(rows), unit, cfg)

    ws2 = wb.create_sheet('Settings')
    ws2.column_dimensions['A'].width = 26
    ws2.column_dimensions['B'].width = 66
    info = data.info()
    s3c = s3_info or {}
    items = [
        ('■ 檔案', ''),
        ('檔名', info['file']),
        ('完整路徑', getattr(data, 'path', '')),
        ('格式', info['protocol']),
        ('錄製日期', info['rec_date']),
        ('錄製時間', f"{info['rec_time']} → {info['rec_end']}"),
        ('總長度 (s)', round(data.duration, 3)),
        ('通道數', data.n_ch),
        ('', ''),
        ('■ 分析通道', ''),
        ('SKNA 來源通道（軌道 2）', f"CH{src}: {data.ch_names[src]}"),
        ('SKNA 來源通道（軌道 3）',
         (lambda s2_: f"CH{s2_}: {data.ch_names[s2_]}")(
             skna_band_cfg(cfg, 2)['src_ch'])),
        ('來源通道取樣率 (Hz)', fs),
        ('來源通道原始單位', data.ch_units[src]),
        ('輸出單位', unit),
        ('ECG 參考通道',
         f"CH{cfg['ecg_ch']}: {data.ch_names[cfg['ecg_ch']]}"),
        ('ECG 參考取樣率 (Hz)', data.fs_of(cfg['ecg_ch'])),
        ('', ''),
        ('■ 訊號處理', ''),
        ('帶通設定 (Hz)', f"軌道 2：{b1}；軌道 3：{b2}"),
        ('帶通實際生效 (Hz)', f"軌道 2：{lo:.0f} – {hi:.0f}；軌道 3：{lo2:.0f} – {hi2:.0f}"),
        ('濾波器',
         f"Butterworth {cfg['order']} 階，SOS 形式，零相位 (sosfiltfilt)"),
        ('整流方式', '全波整流 |rSNA|'),
        ('包絡移動平均 (ms)', cfg['env_ms']),
        ('工頻陷波 (Hz)', cfg.get('notch', 0.0) or '關閉'),
        ('樣本排除', '無（BPF 使用區間內全部樣本，不排除 QRS）'),
        ('Nerveact 相容模式',
         (f"開啟：每 {cfg.get('nact_win', 10.0):g} s 切窗，各窗獨立以 Butterworth "
          f"{cfg['order']} 階單向濾波 (sosfilt)、從零狀態開始，整流取平均")
         if cfg.get('nact_compat') else '關閉（Nerveact 欄位為空）'),
        ('R-peak 來源設定',
         ('沿用畫面上的 R-peak 標記' if cfg.get('rpeak_source') == 'screen'
          else '自動偵測（SKNA 專用演算法 detect_rpeaks_robust）')),
        ('', ''),
        ('■ S3 分解', ''),
        ('目前選用演算法',
         'S3（分解掉心電成分，輸出不再帶通）' if cfg.get('method') == 's3'
         else '傳統帶通 BPF'),
    ] + (
        [('S3 執行範圍',
          '整個檔案' if s3c.get('whole_file')
          else f"{fmt_hms(s3c['t0'])} – {fmt_hms(s3c['t1'])}"),
         ('S3 使用心跳數', s3c.get('n_beat')),
         ('S3 片段長度 (樣本)', s3c.get('p1', 0) + s3c.get('p2', 0) + 1),
         ('S3 估計有效秩', s3c.get('rank')),
         ('S3 前置高通 (Hz)', cfg.get('s3_hp_hz', 1.0)),
         ('S3 鄰居數 K', cfg.get('s3_K', 30)),
         ('S3 移除慢速漂移', '是' if cfg.get('s3_detrend', True) else '否'),
         ('S3 執行時間',
          s3c['when'].strftime('%Y-%m-%d %H:%M:%S')
          if isinstance(s3c.get('when'), datetime.datetime) else '')]
        if s3c else [('S3 狀態', '未執行分解，S3 欄位為空')]
    ) + [
        ('', ''),
        ('■ 指標定義', ''),
        ('aSKNA', f'區間內 |rSNA| 的平均值（{unit}）；使用全部樣本'),
        ('iSKNA', f'aSKNA × 區間長度（{unit}·s）'),
        ('RMS', 'rSNA 的均方根'),
        ('Peak', '區間內 |rSNA| 的最大值'),
        ('SD', 'rSNA 的標準差'),
        ('BPF 前綴的欄位', '原始訊號直接帶通後算出的指標，區間內全部樣本都計入'),
        ('S3 前綴的欄位', 'S3 分解掉心電成分後的輸出直接計算的同名指標，'
                   '不再套帶通（只有 S3 前置高通與慢速漂移移除），'
                   '因此頻寬比 BPF 那組寬，數值不能直接等同'),
        ('Nerveact 相容欄位', '重現 Nerveact 的算法：逐窗單向濾波、每窗從零狀態開始。'
                         '每窗起點的直流電位會產生濾波暫態並計入（約每 10 mV '
                         '+0.45 µV），單向濾波通帶也較寬（約高 6–10%）；'
                         '僅供與 Nerveact 數值對照'),
        ('無效訊號 (%)', '該區間內沒有有效訊號的樣本比例：放大器滿格（波形被'
                        '削平）或完全沒有變化。那些區段不含訊號內容，'
                        '數值不具物理意義'),
        ('判讀', '人工逐段判讀結果（預設保留，標記為 Artifact 者排除），套用到 BPF、S3 與 Nerveact 相容欄位。'
                '可直接在 Excel 的判讀欄下拉修改，「總表」與 *排除 Artifact* 欄會自動重算'),
        ('品質警示', '訊號無效、心率超出生理範圍、RR 間期不穩、或波峰因數過大時'
                    '標示；僅為提示，不會自動剔除資料'),
        ('', ''),
        ('■ 產生資訊', ''),
        ('分析時間', datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        ('程式', f'ECG Analyzer {APP_VERSION}'),
        ('方法', '傳統 BPF 法 (rSNA-BPF)，不排除 QRS'),
        ('方法參考', 'Su P-C, Chen C-Y, Kuo C-H, Tsai W-C, Wu H-T. '
                    'Sympathetic nerve activity recovery from the skin '
                    'recording using the modern optimal shrinkage technique. '
                    'Biomed Signal Process Control 119 (2026) 109710.'),
    ]
    if warn:
        items.insert(20, ('⚠ 帶通警告', warn))
    bold = Font(bold=True, color='1F3864')
    for i, (k, v) in enumerate(items, start=1):
        ck = ws2.cell(row=i, column=1, value=k)
        ws2.cell(row=i, column=2, value=v)
        if str(k).startswith('■'):
            ck.font = bold

    try:
        wb.calculation.fullCalcOnLoad = True
    except Exception:
        pass
    wb.save(path)
    return path


def _add_judge_summary(wb, ws, headers, n_rows: int, unit: str, cfg: dict):
    """在 SKNA Intervals 加上「排除 Artifact」輔助欄與判讀下拉選單，
    並建立「總表」分頁（全部區間 vs 排除 Artifact 的統計）。

    全部用公式：在 Excel 裡改判讀欄，總表會跟著重算。
    """
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter as L
    from openpyxl.worksheet.datavalidation import DataValidation
    names = [h for h, _ in headers]
    col = {h: names.index(h) + 1 for h in names}
    jcol = L(col['判讀'])
    last = n_rows + 1
    # 兩個軌道的 BPF、S3 與 Nerveact 相容 aSKNA / iSKNA
    metrics = [(h, h.rsplit(' (', 1)[0]) for h in names
               if (' aSKNA' in h or ' iSKNA' in h)]
    hdr_fill = PatternFill('solid', fgColor='1F3864')
    hdr_font = Font(bold=True, color='FFFFFF', size=10)
    helper = {}
    c0 = len(names) + 1
    for k, (h, short) in enumerate(metrics):
        cc = c0 + k
        helper[h] = L(cc)
        c = ws.cell(row=1, column=cc, value=f'{h}\n排除 Artifact')
        c.fill = PatternFill('solid', fgColor='7F6000'); c.font = hdr_font
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        ws.column_dimensions[L(cc)].width = 17
        src = L(col[h])
        for r in range(2, last + 1):
            x = ws.cell(row=r, column=cc,
                        value=f'=IF(OR(${jcol}{r}="Artifact",{src}{r}=""),"",{src}{r})')
            x.number_format = '0.0000'
    if n_rows:
        dv = DataValidation(type='list', formula1='"保留,Artifact"',
                            allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f'{jcol}2:{jcol}{last}')

    sm = wb.create_sheet('總表', 0)
    q = "'SKNA Intervals'!"
    sm['A1'] = 'SKNA 總表（人工 Artifact 判讀）'
    sm['A1'].font = Font(bold=True, size=13, color='1F3864')
    sm['A2'] = (f"帶通：軌道 2 {skna_band_label(cfg, 1)} Hz、軌道 3 {skna_band_label(cfg, 2)} Hz。"
                '判讀套用到 BPF、S3 與 Nerveact 相容欄位（S3 欄位需先執行 S3 分解才有數值）；'
                '在 SKNA Intervals 的「判讀」欄修改後，本頁自動重算。')
    jr = f'{q}${jcol}$2:${jcol}${last}'
    cnt = [('區間總數', f'=COUNTA({q}$A$2:$A${last})'),
           ('保留', f'=COUNTIF({jr},"保留")'),
           ('Artifact', f'=COUNTIF({jr},"Artifact")')]
    for i, (k, f) in enumerate(cnt):
        sm.cell(row=4 + i, column=1, value=k).font = Font(bold=True)
        sm.cell(row=4 + i, column=2, value=f)
    hr = 9
    heads = ['指標', '全部：平均', '全部：SD', '全部：中位數', '全部：n',
             '排除 Artifact：平均', '排除 Artifact：SD', '排除 Artifact：中位數',
             '排除 Artifact：n', '差異 (%)']
    for j, h in enumerate(heads, 1):
        c = sm.cell(row=hr, column=j, value=h)
        c.fill = hdr_fill; c.font = hdr_font
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    for i, (h, short) in enumerate(metrics):
        r = hr + 1 + i
        a = f'{q}${L(col[h])}$2:${L(col[h])}${last}'
        b = f'{q}${helper[h]}$2:${helper[h]}${last}'
        vals = [short,
                f'=IFERROR(AVERAGE({a}),"")', f'=IFERROR(STDEV({a}),"")',
                f'=IFERROR(MEDIAN({a}),"")', f'=COUNT({a})',
                f'=IFERROR(AVERAGE({b}),"")', f'=IFERROR(STDEV({b}),"")',
                f'=IFERROR(MEDIAN({b}),"")', f'=COUNT({b})',
                f'=IFERROR((F{r}-B{r})/B{r},"")']
        for j, v in enumerate(vals, 1):
            c = sm.cell(row=r, column=j, value=v)
            c.number_format = '0.0%' if j == 10 else ('0' if j in (5, 9) else '0.0000')
    sm.cell(row=hr + len(metrics) + 2, column=1,
            value='註：Nerveact 相容欄位只有在 SKNA 設定開啟「Nerveact 相容模式」時才有數值。'
                  '未標記為 Artifact 的區段一律視為保留。')
    for j, w in enumerate([22, 12, 11, 12, 8, 15, 14, 15, 13, 10], 1):
        sm.column_dimensions[L(j)].width = w
    sm.row_dimensions[hr].height = 32


# ══════════════════════════════════════════════════════════════════════════════
# 主視窗
# ══════════════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ECG Analyzer V5')
        self.resize(1280, 780)
        # 允許視窗（連同裡面的 3 個波形圖＋底部 slider）縮到比較小的
        # 筆電螢幕也能完整顯示，避免因為子元件的最小尺寸加總起來太高，
        # 導致視窗被 Qt 強制撐高、下緣（底部 slider）跑到畫面外。
        self.setMinimumSize(800, 480)
        self.setAcceptDrops(True)

        self.ecg_data = None   # ABFData | EDFData | ACQData
        self.ts_mgr   : TimestampManager | None = None
        self.detector_thread: PeakDetector | None = None
        self.skna_cfg = dict(SKNA_DEFAULTS)
        self.skna_dlg: 'SknaIntervalDialog | None' = None
        self.s3_cache = None            # S3 分解結果（整條通道）
        self.s3_thread: 'S3Worker | None' = None
        self.skna_rows: list[dict] = []  # SKNA 時間區段（側邊欄與區間視窗共用）
        self.skna_marks: list[dict] = [] # SKNA 時間點位（起點／終點）
        self.skna_judge: dict = {}       # Artifact 判讀 {judge_key: 'artifact'|'keep'}
        self.review_dlg = None
        self._review_cur = None
        self._review_restore_dlg = False
        self._mark_unpaired: list[int] = []
        self.page = 0                   # 0 = ECG 頁, 1 = SKNA 頁

        self._build_ui()
        self._build_toolbar()
        self._build_statusbar()
        self.side.set_page(self.page)
        # 還沒開檔時工具列上的功能全都不能用，藏起來讓起始畫面乾淨一點
        self.toolbar.setVisible(False)

        self._fitted_to_screen = False

    # ── 螢幕可用區域校正 ─────────────────────────────────────────────────────
    # Windows 在高 DPI 縮放（125%／150%…）或筆電較小的螢幕解析度時，若視窗
    # 高度超過工作區域（扣掉工作列後的可視範圍），視窗下緣（狀態列、底部
    # slider）會被裁到螢幕外或被工作列蓋住而點不到。這裡在視窗顯示後，
    # 依實際可用區域夾住大小並置中；如果可用高度比預設值還小很多，直接
    # 最大化視窗（showMaximized 交給作業系統自己處理工作列/多螢幕邊界，
    # 比自己手動算座標更不容易出錯），確保整個視窗都在可視範圍內。
    def _fit_to_screen(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()

        if avail.height() < self.height() or avail.width() < self.width():
            self.showMaximized()
            return

        w = min(self.width(), avail.width())
        h = min(self.height(), avail.height())
        if w != self.width() or h != self.height():
            self.resize(w, h)
        x = avail.x() + max(0, (avail.width() - w) // 2)
        y = avail.y() + max(0, (avail.height() - h) // 2)
        self.move(x, y)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._fitted_to_screen:
            self._fitted_to_screen = True
            self._fit_to_screen()

    # ── UI 建構 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.stack = QWidget()
        self.setCentralWidget(self.stack)
        self.stack_lay = QVBoxLayout(self.stack)
        self.stack_lay.setContentsMargins(0, 0, 0, 0)

        # 拖放區
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self.open_file)
        self.stack_lay.addWidget(self.drop_zone)

        # 主工作區（隱藏直到載入檔案）
        self.main_widget = QWidget()
        self.main_widget.setVisible(False)
        main_col = QVBoxLayout(self.main_widget)
        main_col.setContentsMargins(0, 0, 0, 0)
        main_col.setSpacing(0)
        body = QWidget()
        main_lay = QHBoxLayout(body)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)
        main_col.addWidget(body, 1)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 波形區
        self.waveform = WaveformWidget()
        self.waveform.measure_updated.connect(self._on_measure_updated)
        self.waveform.view_changed.connect(self._on_view_changed)
        self.waveform.peaks_edited.connect(self._on_peaks_edited)
        self.waveform.mark_clicked.connect(self._on_mark_clicked)
        self.waveform.skna_track_edit.connect(self._on_skna_track_edit)
        splitter.addWidget(self.waveform)

        # 側邊面板
        self.side = SidePanel()
        self.side.ts_selected.connect(self._on_ts_selected)
        self.side.ts_deleted.connect(self._on_ts_deleted)
        self.side.ts_renamed.connect(self._on_ts_renamed)
        self.side.ts_goto.connect(self.waveform.goto)
        splitter.addWidget(self.side)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        main_lay.addWidget(splitter)

        self.side.skna_settings_requested.connect(self._open_skna_settings)
        self.side.skna_intervals_requested.connect(self._open_skna_intervals)
        self.side.skna_add_requested.connect(self._skna_add_from_measure)
        self.side.skna_delete_requested.connect(self._skna_delete_rows)
        self.side.skna_goto.connect(self.waveform.goto)
        self.side.skna_goto_index.connect(self._skna_goto_index)
        self.side.page_requested.connect(self.set_page)
        self.side.s3_run_requested.connect(self._run_s3)
        self.side.mark_add_requested.connect(self._mark_begin)
        self.side.mark_delete_requested.connect(self._mark_delete)
        self.side.mark_goto_index.connect(self._mark_goto_index)
        self.side.skna_review_requested.connect(
            lambda: self._open_artifact_review(None))

        self.stack_lay.addWidget(self.main_widget)

    def _build_toolbar(self):
        tb = self.addToolBar('主工具列')
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        self.toolbar = tb

        # 依頁面顯示的工具列項目。QToolBar.addWidget/addAction 回傳的 QAction
        # 就是控制可見性的把手，收集起來之後統一切換。
        self._tb_ecg = []
        self._tb_skna = []
        bucket = [None]     # None = 共用

        def _reg(a):
            if bucket[0] is not None:
                bucket[0].append(a)
            return a

        def act(text, tip, cb, shortcut=None, checkable=False):
            a = QAction(text, self)
            a.setToolTip(tip)
            if checkable:
                a.setCheckable(True)
                a.toggled.connect(cb)
            else:
                a.triggered.connect(cb)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            tb.addAction(a)
            _reg(a)
            return a

        btn_style = (
            f'QPushButton{{background:{C["panel"]};color:{C["accent"]};'
            f'border:1px solid {C["border"]};border-radius:5px;padding:5px 10px;}}'
            f'QPushButton:hover{{background:{C["border"]};color:{C["text"]}}}'
            f'QPushButton:pressed{{background:{C["accent"]};color:{C["bg"]}}}')
        self._btn_style = btn_style

        def push(text, tip, cb):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setStyleSheet(btn_style)
            b.clicked.connect(cb)
            _reg(tb.addWidget(b))
            return b

        def label(txt, color=None):
            lb = QLabel(txt)
            lb.setStyleSheet(f'color:{color or C["dim"]};font-size:11px;')
            _reg(tb.addWidget(lb))
            return lb

        def sep():
            _reg(tb.addSeparator())

        # ══ 共用 ══════════════════════════════════════════════════════════
        act('開啟', '開啟 .abf / .edf / .acq 檔案', self._menu_open, 'Ctrl+O')
        sep()

        self._pan_timer = QTimer()
        # 單次計時器：每一步畫完、處理完排隊的輸入（包含放開按鈕）之後才排
        # 下一步。用固定節拍的重複計時器時，重畫比節拍慢就會一直堆積觸發，
        # 放開按鈕的事件被排在後面，畫面放開後還會繼續走一段。
        self._pan_timer.setSingleShot(True)
        # 只在這裡接一次。以前是每次按下都 connect 一個新的 lambda、放開再
        # 全部 disconnect，只要有一次 released 沒收到（例如按著按鈕時鍵盤
        # 也觸發了平移），連線就會殘留，下一次連發會一次跑好幾格。
        self._pan_direction = 0
        self._pan_timer.timeout.connect(self._on_pan_tick)
        self._key_pan_timer = QTimer()
        self._key_pan_timer.setInterval(80)

        btn_prev = QPushButton('◀ 往前')
        btn_prev.setToolTip('往前平移，按住持續移動 (←)')
        btn_prev.setStyleSheet(btn_style)
        btn_prev.pressed.connect(lambda: self._start_pan(-1))
        btn_prev.released.connect(self._stop_pan)
        tb.addWidget(btn_prev)

        btn_next = QPushButton('往後 ▶')
        btn_next.setToolTip('往後平移，按住持續移動 (→)')
        btn_next.setStyleSheet(btn_style)
        btn_next.pressed.connect(lambda: self._start_pan(+1))
        btn_next.released.connect(self._stop_pan)
        tb.addWidget(btn_next)

        act('放大', '放大時間軸 (+)', lambda: self.waveform.zoom(2.0), '+')
        act('縮小', '縮小時間軸 (-)', lambda: self.waveform.zoom(0.5), '-')
        act('重設', '重設視圖 (R)', self.waveform.reset_view, 'R')
        sep()

        # 測量兩頁都要：SKNA 區間分析的「加入目前選取範圍」靠它圈選
        self.act_measure = act('測量', '測量模式：點擊 A→B 計算時間差 (M)',
                               self._toggle_measure, 'M', checkable=True)
        sep()

        # ══ ECG 頁 ════════════════════════════════════════════════════════
        bucket[0] = self._tb_ecg
        act('偵測 R-peaks', '自動偵測 R-peak 並計算 RR 間距 (P)',
            self._detect_peaks, 'P')
        self.act_peak_edit = act(
            '編輯 R-peak',
            '手動修正 R-peak：點擊已標記的峰值可刪除，'
            '點擊空白處會在附近振幅最大點新增 (X)',
            self._toggle_peak_edit, 'X', checkable=True)
        act('清除 R-peak', '移除目前所有 R-peak 標記', self._clear_all_peaks)
        sep()
        push('濾波...', '設定 Notch 陷波 / Bandpass 帶通濾波器',
             self._open_filter_dialog)
        self.lbl_filter_state = label('  Off')
        sep()
        push('匯入實驗記錄', '從 Excel dOMAP 分頁匯入時間戳記',
             self._import_excel)
        sep()

        # ══ SKNA 頁 ═══════════════════════════════════════════════════════
        bucket[0] = self._tb_skna
        # SKNA 顯示切換、設定、S3 都移到側邊欄的 SKNA 區塊了；
        # 進入 SKNA 頁會自動開啟顯示，不需要再按一次。
        # act_skna 仍然保留（快捷鍵 K 與程式內部狀態都靠它），只是不放工具列。
        self.act_skna = QAction('SKNA', self)
        self.act_skna.setCheckable(True)
        self.act_skna.setShortcut(QKeySequence('K'))
        self.act_skna.toggled.connect(self._toggle_skna)
        self.addAction(self.act_skna)
        self.act_s3_ecg = act(
            '疊心電成分',
            '在軌道 1 疊上 S3 分離出來的心電成分（紅色），'
            '用來確認分解是否貼合實際 QRS',
            self._toggle_s3_ecg_overlay, checkable=True)
        push('SKNA 區間分析...', '依時間區間計算 aSKNA / iSKNA 並匯出 Excel',
             self._open_skna_intervals)
        self.lbl_skna_state = label('  Off', C['dim'])
        sep()

        # ══ 共用（尾端）═══════════════════════════════════════════════════
        bucket[0] = None
        act('截圖', '儲存目前畫面 (Q)', self._screenshot, 'Q')
        act('前往時間點', '跳到指定時間點 (G)', self._show_goto_dialog, 'G')
        act('說明', '快捷鍵說明', self._show_help)

        self._apply_page_to_toolbar()

    def _apply_page_to_toolbar(self):
        ecg = (self.page == 0)
        for a in self._tb_ecg:
            a.setVisible(ecg)
        for a in self._tb_skna:
            a.setVisible(not ecg)

    def set_page(self, page: int):
        """切換 ECG / SKNA 頁面。波形區共用，切頁不會改變目前檢視位置。"""
        page = 0 if page == 0 else 1
        if getattr(self, 'page', None) == page:
            return
        self.page = page
        # 切頁前先離開目前的模式，免得帶著 ECG 的測量狀態進到 SKNA 頁
        if self.act_measure.isChecked():
            self.act_measure.setChecked(False)
        self._apply_page_to_toolbar()
        self._refresh_measure_action()
        self.side.set_page(page)

        # 離開 ECG 頁時關掉 R-peak 編輯模式，免得在 SKNA 頁誤點改到峰值
        if page == 1 and self.act_peak_edit.isChecked():
            self.act_peak_edit.setChecked(False)
        self._sync_skna_side()

        if page == 1:
            # SKNA 頁就是要看 SKNA，不必再按一次開關
            if self.ecg_data is not None and not self.waveform.skna_enabled:
                self.act_skna.setChecked(True)
            self.lbl_status.setText('SKNA 頁面')
        else:
            # 回到 ECG 頁就把 S3 的心電疊圖關掉，否則軌道 1 會多一條紅線
            if self.act_s3_ecg.isChecked():
                self.act_s3_ecg.setChecked(False)
            # SKNA 顯示也一併關掉，軌道 2 回到一般通道顯示。
            # SKNA 開關已經不在工具列上，留著會變成 ECG 頁看到 SKNA 波形、
            # 通道選單還被鎖住，卻找不到地方關掉。
            if self.waveform.skna_enabled:
                self.act_skna.setChecked(False)
            self.lbl_status.setText('ECG 頁面')

    def _build_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.lbl_status = QLabel('請開啟 .abf / .edf / .acq 檔案，或將其拖入視窗')
        self.lbl_status.setStyleSheet(f'color:{C["dim"]}')
        self.status.addWidget(self.lbl_status)

        self.lbl_mode = QLabel()
        self.lbl_mode.setStyleSheet(f'color:{C["yellow"]}; font-weight:bold;')
        self.status.addPermanentWidget(self.lbl_mode)

    # ── 檔案開啟 ─────────────────────────────────────────────────────────────

    def _menu_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '開啟 ECG 檔案',
            last_open_dir(getattr(self.ecg_data, 'path', None)),
            FILE_DIALOG_FILTER)
        if path:
            self.open_file(path)

    def open_file(self, path: str):
        # 大檔（尤其 .acq 要解壓縮）讀起來要一兩秒，全在主執行緒上跑。
        # 不給任何回饋的話畫面會整個凍住，看起來就像程式當掉。
        name = os.path.basename(path)
        self.drop_zone.set_busy(True, name)
        self.lbl_status.setText(f'載入中：{name} …')
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            self.ecg_data = load_ecg_file(path)
            remember_dir(path)      # 下次開檔對話框停在同一個資料夾
            self.ts_mgr   = TimestampManager(path)
            self.lbl_status.setText(f'載入中：{name} — 檢查訊號品質 …')
            QApplication.processEvents()

            # 換檔案就重設 SKNA 設定：通道編號、取樣率、單位都可能不同，
            # 沿用上一個檔案的設定很容易在不知情的情況下分析到錯的通道。
            sat_full = channel_defect_report(self.ecg_data)
            self.ecg_data._defect_report = sat_full
            sat = {i: v['bad'] for i, v in sat_full.items()}
            src, ecg = guess_skna_channels(self.ecg_data)
            self.skna_cfg = dict(SKNA_DEFAULTS)
            self.skna_cfg['src_ch'] = src
            self.skna_cfg['src_ch2'] = src
            self.skna_cfg['ecg_ch'] = ecg
            self.s3_cache = None
            self.skna_rows = []
            self._marks_load()
            n_imported = self._marks_import_from_file()
            self.waveform.set_marks(self.skna_marks)
            self.waveform.set_s3(None, None)
            self.waveform.show_s3_ecg = False
            if getattr(self, 'act_s3_ecg', None) is not None:
                self.act_s3_ecg.blockSignals(True)
                self.act_s3_ecg.setChecked(False)
                self.act_s3_ecg.blockSignals(False)
            if self.skna_dlg is not None:
                self.skna_dlg.close()
                self.skna_dlg = None
            self.act_skna.blockSignals(True)
            self.act_skna.setChecked(False)
            self.act_skna.blockSignals(False)
            self.waveform.skna_enabled = False
            self.waveform.skna_cfg = dict(self.skna_cfg)
            self._update_skna_label()
            self._rebuild_mark_intervals()
            self._refresh_measure_action()

            self.waveform.set_ts_manager(self.ts_mgr)
            self.side.set_ts_manager(self.ts_mgr)
            self.side.set_ecg_data(self.ecg_data)
            self.side.update_file_info(self.ecg_data)
            try:
                self.side.ts_save_requested.disconnect()
            except Exception:
                pass
            self.side.ts_save_requested.connect(self._save_timestamp)
            self.waveform.load(self.ecg_data)

            # 前面把 SKNA 顯示重設掉了（新檔案的通道編號、取樣率、單位都
            # 可能不同，沿用舊設定很容易在不知情的情況下分析到錯的通道）。
            # 但如果人還停在 SKNA 頁，畫面就會變成「SKNA 頁卻顯示原始
            # 通道」，得切到 ECG 頁再切回來才會恢復。這裡用新檔案猜出來的
            # 通道把顯示接回去。要等 waveform.load() 之後才做，否則新的
            # 通道編號會套在還沒換掉的舊資料上。
            if self.page == 1 and self.ecg_data.n_ch > 1 \
                    and self.skna_cfg.get('src_ch') is not None:
                self.act_skna.setChecked(True)

            self.drop_zone.setVisible(False)
            self.main_widget.setVisible(True)
            self.toolbar.setVisible(True)

            self.setWindowTitle(f'ECG Analyzer V5 — {name}')
            info = self.ecg_data.info()
            dt_str = (f"  |  📅 {info['rec_date']}  🕐 {info['rec_time']} → {info['rec_end']}"
                      if info['rec_date'] != '—' else '')
            if getattr(self.ecg_data, 'mixed_fs', False):
                uniq = sorted({self.ecg_data.fs_of(i)
                               for i in range(self.ecg_data.n_ch)}, reverse=True)
                fs_txt = ' / '.join(f'{v:,.0f}' for v in uniq) + ' Hz（混合）'
            else:
                fs_txt = f'{self.ecg_data.fs:,.0f} Hz'
            self.lbl_status.setText(
                f'{name}  |  {fs_txt}  |  '
                f'{fmt_hms(self.ecg_data.duration)}  |  '
                f'{self.ecg_data.n_ch} 通道{dt_str}'
                + (f'  |  📍 已帶入檔案內建的 {n_imported} 個事件標記'
                   if n_imported else ''))

            bad = {i: v for i, v in sat.items() if v >= 5.0}
            if bad:
                lines = '\n'.join(
                    f'　CH{i}: {self.ecg_data.ch_names[i]} — {v:.0f}%'
                    + ('（飽和）' if sat_full[i]['sat'] >= sat_full[i]['flat']
                       else '（無變化）')
                    for i, v in sorted(bad.items(), key=lambda kv: -kv[1]))
                QMessageBox.warning(
                    self, '通道飽和警告',
                    f'以下通道有相當比例的樣本沒有有效訊號'
                    f'（放大器飽和被削平，或完全沒有變化）：\n\n'
                    f'{lines}\n\n'
                    '那些區段沒有訊號內容，該時段的 aSKNA 不具物理意義，'
                    'S3 也無法分解。\n\n'
                    f'已自動避開，選擇 CH{src}: {self.ecg_data.ch_names[src]}'
                    f'（{sat.get(src, 0):.0f}%）作為 SKNA 來源；'
                    '可在「SKNA 設定」裡改選，或只分析正常的時間範圍。')

        except Exception as e:
            QMessageBox.critical(self, '錯誤',
                                 f'無法開啟檔案：\n{e}\n\n{traceback.format_exc()}')
        finally:
            QApplication.restoreOverrideCursor()
            self.drop_zone.set_busy(False)

    # ── 工具列動作 ────────────────────────────────────────────────────────────

    def _pan_interval(self) -> int:
        """連發平移的間隔：跟著上一次重畫的實際耗時走。

        固定 80 ms 的問題是，大視窗、高採樣率或 SKNA 模式下一次重畫可能
        要 100 ms 以上，計時器卻還是每 80 ms 叫一次，畫面永遠追不上輸入，
        看起來就是愈按愈頓、最後像當掉。讓間隔不小於重畫時間的 1.4 倍，
        重畫快的時候照樣是 80 ms 的流暢連發。
        """
        ms = getattr(self.waveform, '_last_draw_ms', 0.0)
        return int(min(400, max(80, ms * 1.4)))

    _PAN_REPEAT_DELAY = 300   # 按住多久才開始連續移動 (ms)；一般單擊只走一步
    _PAN_GAP = 30             # 連續移動時，每一步畫完後留給輸入事件的空檔 (ms)

    def _on_pan_tick(self):
        if self._pan_direction == 0:
            return
        direction = self._pan_direction
        self.waveform._fast = True
        self.waveform.pan(direction, sync=True)
        # 把這一步的畫面真的畫出來，同時處理已經排隊的輸入。若使用者已經
        # 放開按鈕／方向鍵，_stop_pan 會在這裡被呼叫，下面就不會再排下一步
        QApplication.processEvents()
        if self._pan_direction != direction or self._pan_timer.isActive():
            return
        self._pan_timer.start(self._PAN_GAP)

    def _start_pan(self, direction: int):
        # 已經在往同一個方向移動就不要再插一次，否則按鈕與方向鍵同時
        # 觸發時會一次跳兩格
        if self._pan_direction == direction:
            return
        self._pan_direction = direction
        self.waveform.pan(direction, sync=True)      # 立即移動一次
        self._pan_timer.start(self._PAN_REPEAT_DELAY)

    def _stop_pan(self):
        self._pan_direction = 0
        self._pan_timer.stop()
        if getattr(self.waveform, '_fast', False):
            # 連續移動結束：用完整解析度重畫一次
            self.waveform._fast = False
            self.waveform.request_draw()

    def _toggle_dual(self, on: bool):
        self.waveform.toggle_dual(on)
        if on:
            self.lbl_mode.setText('⊕ 雙通道模式  |  藍=主通道  綠=次通道（振幅正規化）')
        else:
            self.lbl_mode.setText('')

    def _toggle_measure(self, on: bool):
        """同一顆按鈕，兩頁不同行為。

        ECG 頁：A→B 時間測量（原本的功能）。
        SKNA 頁：新增時間點位 —— 點一下波形就標一個起點或終點，
        配對起來的區間會自動算 SKNA。
        """
        if on and self.act_peak_edit.isChecked():
            self.act_peak_edit.setChecked(False)

        if self.page == 1:
            self.waveform.toggle_measure(False)
            self.waveform.toggle_mark_mode(on)
            self.lbl_mode.setText(
                '📍 新增時間點位  |  點擊波形 → 輸入名稱並選擇起點／終點'
                if on else '')
        else:
            self.waveform.toggle_mark_mode(False)
            self.waveform.toggle_measure(on)
            self.lbl_mode.setText(
                '📏 測量模式  |  點擊波形設定 A / B 點' if on else '')
        self._sync_skna_side()

    def _refresh_measure_action(self):
        """依目前頁面調整「測量」按鈕的文字與說明。"""
        if self.page == 1:
            self.act_measure.setText('新增點位')
            self.act_measure.setToolTip(
                '新增 SKNA 時間點位：點擊波形後輸入名稱，並選擇起點或終點。'
                '起點與其後最近的終點會自動配對成分析區間 (M)')
        else:
            self.act_measure.setText('測量')
            self.act_measure.setToolTip('測量模式：點擊 A→B 計算時間差 (M)')

    def _toggle_peak_edit(self, on: bool):
        if on and self.act_measure.isChecked():
            self.act_measure.setChecked(False)
        self.waveform.toggle_peak_edit(on)
        if on:
            self.lbl_mode.setText('✏️ R-peak 編輯模式  |  點擊峰值刪除、點擊空白處新增')
        else:
            self.lbl_mode.setText('')

    def _on_peaks_edited(self, peaks, stats: dict):
        self.side.update_rr(stats)
        if stats:
            self.lbl_status.setText(
                f'手動編輯後：{stats["count"]} 個 R-peaks  |  '
                f'HR: {stats["hr"]} bpm  |  '
                f'RR: {stats["rr_mean"]}±{stats["rr_std"]} ms')
        else:
            self.lbl_status.setText(f'手動編輯後：{len(peaks)} 個 R-peaks（統計資料不足）')

    def _clear_all_peaks(self):
        if self.waveform._peaks_cache is None or len(self.waveform._peaks_cache) == 0:
            return
        reply = QMessageBox.question(
            self, '清除 R-peak',
            '確定要移除目前所有 R-peak 標記嗎？\n（可以之後重新按 P 偵測，或用 X 編輯模式手動標記）',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.waveform.remove_all_peaks()
        self.side.update_rr({})
        self.lbl_status.setText('已移除所有 R-peak 標記')

    def _save_timestamp(self):
        if self.ecg_data is None:
            return
        pts = self.waveform.measure_pts
        if len(pts) == 0:
            QMessageBox.information(self, '提示',
                '請先進入測量模式（M）並點擊 A / B 點，\n或直接以目前視窗中心作為單點時間戳記。')
            t_mid = (self.waveform.t_start + self.waveform.t_end) / 2
            dlg = TimestampDialog(t_mid, None, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                label, note, tag = dlg.get_data()
                self.ts_mgr.add(t_mid, None, label, note, tag)
                self.side.refresh_ts_list()
                self.waveform._draw()
            return

        t_a = pts[0]
        t_b = pts[1] if len(pts) > 1 else None
        dlg = TimestampDialog(t_a, t_b, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            label, note, tag = dlg.get_data()
            rec = self.ts_mgr.add(
                min(t_a, t_b) if t_b else t_a,
                max(t_a, t_b) if t_b else None,
                label, note, tag, self.ecg_data)
            self.side.refresh_ts_list()
            self.waveform._draw()
            self.lbl_status.setText(
                f'時間戳記已儲存：{rec["label"]}  {rec["t_start_hms"]}')

    def _open_filter_dialog(self):
        dlg = FilterSettingsDialog(
            self,
            notch_freq=self.waveform.notch_freq,
            bp_enabled=self.waveform.bp_enabled,
            bp_lo=self.waveform.bp_lo,
            bp_hi=self.waveform.bp_hi,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            s = dlg.get_settings()
            self.waveform.notch_freq = s['notch_freq']
            self.waveform.bp_enabled = s['bp_enabled']
            self.waveform.bp_lo      = s['bp_lo']
            self.waveform.bp_hi      = s['bp_hi']
            self._update_filter_label()
            self.waveform._draw()

    # ── SKNA ────────────────────────────────────────────────────────────────

    def _require_file(self) -> bool:
        if self.ecg_data is None:
            QMessageBox.information(self, '尚未開檔',
                                    '請先開啟 .abf / .edf / .acq 檔案。')
            return False
        return True

    def _toggle_skna(self, on: bool):
        if on and not self._require_file():
            self.act_skna.blockSignals(True)
            self.act_skna.setChecked(False)
            self.act_skna.blockSignals(False)
            return
        if on:
            # SKNA 畫在軌道 2，雙軌顯示必須是開著的
            self.waveform.dual_mode = True
        self.waveform.set_skna(on, self.skna_cfg)
        self._update_skna_label()
        if (on and self.skna_cfg.get('method') == 's3'
                and not self._s3_is_valid()):
            self.lbl_status.setText(
                '⚠ 目前選的是 S3，但尚未分解 — 畫面顯示的仍是傳統帶通結果。'
                '請按右側欄位的「S3 分解（整檔）」。')

    def _update_skna_label(self):
        if not getattr(self, 'lbl_skna_state', None):
            return
        cfg = self.skna_cfg
        if self.ecg_data is None or cfg.get('src_ch') is None:
            self.lbl_skna_state.setText('  Off')
            self.lbl_skna_state.setStyleSheet(f'color:{C["dim"]};font-size:11px;')
            return
        src = cfg['src_ch']
        fs = self.ecg_data.fs_of(src)
        lo, hi, warn = skna_effective_band(fs, cfg['bp_lo'], cfg['bp_hi'])
        if cfg.get('method') == 's3':
            ok = self._s3_is_valid()
            meth = 'S3 ✓' if ok else 'S3（待分解）'
        else:
            meth = 'BPF'
        txt = f'  {meth} | CH{src} | {lo:.0f}–{hi:.0f}／{skna_band_label(cfg, 2)} Hz'
        if warn:
            txt += ' ⚠'
        self.lbl_skna_state.setText(txt)
        self.lbl_skna_state.setStyleSheet(
            f'color:{C["yellow"] if warn else C["orange"]};font-size:11px;')

    def _open_skna_settings(self):
        if not self._require_file():
            return
        dlg = SknaSettingsDialog(
            self, self.ecg_data, self.skna_cfg,
            s3_state=('ready' if self._s3_is_valid() else 'none'))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._apply_skna_cfg(dlg.get_settings(), interactive=True)

    def _on_skna_track_edit(self, upd: dict):
        """在軌道標題列直接改了 SKNA 來源或帶通。"""
        if self.ecg_data is None:
            return
        new = dict(self.skna_cfg)
        new.update(upd)
        if set(upd) <= {'disp1', 'disp2'}:
            self._on_track_display(upd, new)
            return
        n = len(self.skna_rows)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._apply_skna_cfg(new, interactive=False)
        finally:
            QApplication.restoreOverrideCursor()
        what = ('軌道 2' if ('src_ch' in upd or 'bp_lo' in upd) else '軌道 3')
        self.lbl_status.setText(
            f'已更新{what}：來源 / 帶通 = '
            + (f"{skna_band_label(self.skna_cfg, 1)} Hz" if what == '軌道 2'
               else f"{skna_band_label(self.skna_cfg, 2)} Hz")
            + (f'，已重算 {n} 個區間' if n else ''))

    def _on_track_display(self, upd: dict, new: dict):
        """軌道標題列的「Bandpass／S3」選單。

        演算法跟著軌道走：只要有一軌顯示 S3 就是 S3 模式（區間分析才會有
        S3 欄位），兩軌都回到 Bandpass 就回到帶通模式。選 S3 而這個檔案
        還沒分解過時，直接對整個檔案執行 S3 分解。
        """
        key, val = next(iter(upd.items()))
        which = '軌道 2' if key == 'disp1' else '軌道 3'
        was_s3 = self.skna_cfg.get('method') == 's3'
        if val == 's3' and not was_s3:
            # 原本是帶通模式：另一軌維持顯示 Bandpass，不要一起被切成 S3
            other = 'disp2' if key == 'disp1' else 'disp1'
            new[other] = 'bpf'
        same_ch = not skna_tracks_differ(new) or \
            skna_band_cfg(new, 2).get('src_ch') == new.get('src_ch')
        any_s3 = (new.get('disp1', 'bpf') == 's3'
                  or (new.get('disp2', 'bpf') == 's3' and same_ch))
        new['method'] = 's3' if any_s3 else 'bpf'

        if new['method'] != self.skna_cfg.get('method'):
            # 演算法改變：區間要重算（S3 欄位出現或消失）
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self._apply_skna_cfg(new, interactive=False)
            finally:
                QApplication.restoreOverrideCursor()
        else:
            # 只是換另一軌的顯示，數值不變，不必重算
            self.skna_cfg = new
            self.waveform.skna_cfg = dict(new)
            self.waveform._draw()
            self._sync_skna_side()
        self.lbl_status.setText(
            f"{which} 改為顯示 {'S3' if val == 's3' else 'Bandpass'}")

        if val == 's3' and not self._s3_is_valid():
            running = self.s3_thread is not None and self.s3_thread.isRunning()
            if not running:
                self.lbl_status.setText(f'{which} 選擇 S3：這個檔案還沒分解過，'
                                        '自動執行 S3 分解（整檔）…')
                QTimer.singleShot(0, lambda: self._run_s3(True))

    def _apply_skna_cfg(self, new_cfg: dict, interactive: bool = True):
        old_key = s3_param_key(self.skna_cfg)
        self.skna_cfg = dict(new_cfg)
        if interactive:
            # 從 SKNA 設定套用演算法時，兩個軌道的顯示一起跟著切換
            d_ = 's3' if self.skna_cfg.get('method') == 's3' else 'bpf'
            self.skna_cfg['disp1'] = d_
            self.skna_cfg['disp2'] = d_
        self.waveform.skna_cfg = dict(self.skna_cfg)
        if self.s3_cache is not None and s3_param_key(self.skna_cfg) != old_key:
            self._invalidate_s3('通道或 S3 參數已變更')
        self._update_skna_label()
        if self.waveform.skna_enabled:
            self.waveform._draw()
        if self.skna_dlg is not None:
            self.skna_dlg.recalc_all()
        else:
            for i in range(len(self.skna_rows)):
                self._skna_compute_row(i)
        self._sync_skna_side()

        if self.skna_cfg.get('method') == 's3' and self.ecg_data is not None:
            if self._s3_is_valid():
                # 已經分解過而且參數沒變，直接把結果顯示出來
                if not self.waveform.skna_enabled:
                    self.act_skna.setChecked(True)
            else:
                est = max(1, int(len(self.ecg_data.channels[
                    self.skna_cfg['src_ch']])
                    / self.ecg_data.fs_of(self.skna_cfg['src_ch'])
                    / 60 * 1.5))
                if QMessageBox.question(
                        self, '執行 S3 分解？',
                        '已切換到 S3 演算法，但這個檔案還沒分解過。\n\n'
                        'S3 需要先對整個檔案跑一次分解，之後所有區間分析'
                        '才會有 S3 的數字；在那之前畫面與表格顯示的都還是'
                        '傳統帶通的結果。\n\n'
                        f'現在執行嗎？（預估約 {est} 秒）'
                ) == QMessageBox.StandardButton.Yes if interactive else False:
                    self._run_s3(True)
                else:
                    self.lbl_status.setText(
                        '已選擇 S3，但尚未分解。請按右側欄位的「S3 分解（整檔）」，'
                        '否則顯示與統計仍是傳統帶通的結果。')
        elif (self.skna_cfg.get('method') == 'bpf'
              and self.waveform.skna_enabled):
            self.waveform._draw()

    def _open_skna_intervals(self):
        if not self._require_file():
            return
        if self.skna_dlg is None:
            self.skna_dlg = SknaIntervalDialog(self, self)
        self.skna_dlg.refresh_header()
        self.skna_dlg._rebuild_table()
        self.skna_dlg.show()
        self.skna_dlg.raise_()
        self.skna_dlg.activateWindow()

    # ── SKNA 時間點位 ────────────────────────────────────────────────────

    def _marks_path(self):
        if self.ecg_data is None:
            return None
        base = os.path.splitext(getattr(self.ecg_data, 'path', ''))[0]
        return (base + '_SKNA_marks.json') if base else None

    def _marks_load(self):
        """開檔時載入先前存的時間點位。"""
        self.skna_marks = []
        self.skna_judge = {}
        self._marks_imported = False
        pth = self._marks_path()
        if not pth or not os.path.exists(pth):
            return
        try:
            with open(pth, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._marks_imported = bool(data.get('imported_from_file'))
            out = []
            for m in (data.get('marks', []) if isinstance(data, dict) else data):
                t = float(m.get('t'))
                out.append({'t': t,
                            'name': str(m.get('name', '')),
                            'kind': 'end' if m.get('kind') == 'end' else 'start',
                            'src': str(m.get('src', '') or '')})
            self.skna_marks = out
            if isinstance(data, dict) and isinstance(data.get('judgements'), dict):
                self.skna_judge = {str(k): v for k, v in data['judgements'].items()
                                   if v in ('artifact', 'keep')}
        except Exception:
            self.skna_marks = []

    def _marks_import_from_file(self) -> int:
        """把檔案本身帶的事件標記（目前是 .acq 的 usr1）帶進時間點位。

        只在這個檔案還沒匯入過時做一次，並把「已匯入」記在點位檔裡。
        否則你刪掉不要的自動點位之後，下次開檔又會全部長回來。
        時間已經有點位的（±0.2 s）不重複加入，手動調整過的位置不會被蓋掉。
        """
        if getattr(self, '_marks_imported', False):
            return 0
        src = list(getattr(self.ecg_data, 'file_marks', None) or [])
        if not src:
            return 0
        exist = [float(m['t']) for m in self.skna_marks]
        added = 0
        for m in src:
            t = float(m['t'])
            if any(abs(t - e) < 0.2 for e in exist):
                continue
            self.skna_marks.append({
                't': t,
                'name': str(m.get('name', '')),
                'kind': 'end' if m.get('kind') == 'end' else 'start',
                'src': 'acq'})
            exist.append(t)
            added += 1
        self.skna_marks.sort(key=lambda m: m['t'])
        self._marks_imported = True
        if added:
            self._marks_save()
        return added

    def _marks_save(self):
        pth = self._marks_path()
        if not pth:
            return
        try:
            payload = {
                'file': os.path.basename(getattr(self.ecg_data, 'path', '')),
                'saved_at': datetime.datetime.now().isoformat(timespec='seconds'),
                'imported_from_file': bool(getattr(self, '_marks_imported', False)),
                'marks': self.skna_marks,
                'judgements': self.skna_judge,
            }
            with open(pth, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as ex:
            self.lbl_status.setText(f'時間點位存檔失敗：{ex}')

    def _mark_begin(self):
        """由側邊欄按鈕觸發：進入點位標記模式。"""
        if not self._require_file():
            return
        if self.page != 1:
            self.set_page(1)
        self.act_measure.setChecked(True)

    def _on_mark_clicked(self, t: float):
        """在波形上點了一下，問名稱與類型後加入點位。"""
        if self.ecg_data is None:
            return
        t = max(0.0, min(float(t), self.ecg_data.duration))

        # 預設值：交錯建議起點／終點，名稱沿用上一個起點，省去重打
        kind = 'start'
        suggest = ''
        if self.skna_marks:
            prev = sorted(self.skna_marks, key=lambda m: m['t'])
            before = [m for m in prev if m['t'] <= t]
            last = before[-1] if before else None
            if last is not None and last.get('kind') == 'start':
                kind = 'end'
                suggest = last.get('name', '')
        if not suggest:
            n = sum(1 for m in self.skna_marks if m.get('kind') == 'start')
            suggest = f'區段 {n + 1}'

        dlg = MarkPointDialog(self, t, self.ecg_data.abs_time(t),
                              kind=kind, suggest=suggest)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        got = dlg.get_mark()
        if not got:
            return
        name, kind = got
        self.skna_marks.append({'t': float(t), 'name': name, 'kind': kind})
        self.skna_marks.sort(key=lambda m: m['t'])
        self._marks_changed()
        self.lbl_status.setText(
            f"已新增{'起點' if kind == 'start' else '終點'}「{name}」"
            f"於 {fmt_hms(t)}")

    def _mark_delete(self, indices: list):
        for i in sorted(indices, reverse=True):
            if 0 <= i < len(self.skna_marks):
                self.skna_marks.pop(i)
        self._marks_changed()

    def _mark_goto_index(self, i: int):
        if 0 <= i < len(self.skna_marks):
            self.waveform.goto(self.skna_marks[i]['t'])

    def _marks_changed(self):
        """點位有異動：重畫、重建配對出來的區間、存檔。"""
        self.waveform.set_marks(self.skna_marks)
        self._rebuild_mark_intervals()
        self._marks_save()

    def _rebuild_mark_intervals(self):
        """依點位配對重建分析區間。

        手動加入的區間（'manual'）不動，只重建由點位產生的那些，
        這樣使用者兩種方式可以混用而不會互相覆蓋。
        """
        pairs, unpaired = pair_marks_to_intervals(self.skna_marks)
        self._mark_unpaired = unpaired

        manual = [r for r in self.skna_rows if r.get('kind') != 'mark']
        derived = []
        for pr in pairs:
            derived.append({'label': pr['label'], 't0': pr['t0'], 't1': pr['t1'],
                            'res': None, 'src': '', 'kind': 'mark'})
        self.skna_rows = derived + manual

        if self.ecg_data is not None and self.skna_cfg.get('src_ch') is not None:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                for i in range(len(self.skna_rows)):
                    self._skna_compute_row(i)
            finally:
                QApplication.restoreOverrideCursor()

        self._sync_skna_side()
        if self.skna_dlg is not None:
            self.skna_dlg._rebuild_table()

    # ── 側邊欄的 SKNA 區塊 ────────────────────────────────────────────────

    def _sync_skna_side(self):
        """把目前的 SKNA 設定與區間清單推到側邊欄。"""
        if not hasattr(self, 'side'):
            return
        self.side.update_skna_cfg(
            self.ecg_data, self.skna_cfg, self.s3_cache,
            self._s3_is_valid() if self.ecg_data is not None else False)
        self.side.refresh_marks(self.skna_marks, self._mark_unpaired,
                                self.ecg_data,
                                mark_mode=self.waveform.mark_mode)
        self._apply_judge()
        self.side.refresh_skna_list(self.skna_rows, self.ecg_data)
        self._update_review_overlay()

    def _skna_compute_row(self, i: int):
        """計算單一 SKNA 區間的指標（側邊欄新增時用，與區間視窗共用邏輯）。"""
        d, cfg = self.ecg_data, self.skna_cfg
        if d is None or cfg.get('src_ch') is None or not (0 <= i < len(self.skna_rows)):
            return
        r = self.skna_rows[i]
        rt, src = skna_rpeak_times(
            d, cfg, r['t0'], r['t1'],
            cached_peaks=self.waveform._peaks_cache,
            cached_ch=self.waveform.ch_idx)
        r['res'] = analyze_skna_interval(d, cfg, r['t0'], r['t1'], rt,
                                         s3_sig=self._s3_signal())
        r['src'] = src

    def _skna_add_from_measure(self):
        """把測量選取（沒有的話就用目前顯示範圍）加入 SKNA 區間清單。"""
        if not self._require_file():
            return
        pts = self.waveform.measure_pts
        if len(pts) >= 2:
            a, b = sorted(pts[:2])
            how = '測量選取'
        else:
            a, b = self.waveform.t_start, self.waveform.t_end
            how = '目前顯示範圍'
        if b - a <= 0:
            return
        self.skna_rows.append({
            'label': f'區間 {len(self.skna_rows) + 1}',
            't0': float(a), 't1': float(b), 'res': None, 'src': ''})
        self._skna_compute_row(len(self.skna_rows) - 1)
        self._sync_skna_side()
        if self.skna_dlg is not None:
            self.skna_dlg._rebuild_table()
        self.lbl_status.setText(
            f'已節錄 {how}：{fmt_hms(a)} → {fmt_hms(b)}（{b - a:.1f} 秒）')

    def _skna_delete_rows(self, indices: list):
        for i in sorted(indices, reverse=True):
            if 0 <= i < len(self.skna_rows):
                self.skna_rows.pop(i)
        self._sync_skna_side()
        if self.skna_dlg is not None:
            self.skna_dlg._rebuild_table()

    # ── Artifact 判讀 ───────────────────────────────────────────────────

    def _apply_judge(self):
        """把判讀結果（以起訖時間為鍵）套到目前的區間清單上。"""
        for r in self.skna_rows:
            r['judge'] = self.skna_judge.get(judge_key(r['t0'], r['t1']))

    def skna_set_judge(self, indices: list, state):
        """state：'artifact'、'keep'，或 None（清除）。"""
        for i in indices:
            if 0 <= i < len(self.skna_rows):
                r = self.skna_rows[i]
                k = judge_key(r['t0'], r['t1'])
                if state != 'artifact':           # 預設就是保留，不必存
                    self.skna_judge.pop(k, None)
                else:
                    self.skna_judge[k] = state
        self._marks_save()
        self._sync_skna_side()
        if self.skna_dlg is not None:
            self.skna_dlg._rebuild_table()

    def _update_review_overlay(self):
        if not hasattr(self, 'waveform'):
            return
        # 只在 Artifact 判讀視窗開著時標示；關掉之後畫面不留紅底與框
        if (self.ecg_data is None or getattr(self, 'page', 0) != 1
                or (self.review_dlg is None and self._review_cur is None)):
            self.waveform.set_review([], None)
            return
        regions = [(r['t0'], r['t1'],
                    self.skna_judge.get(judge_key(r['t0'], r['t1'])))
                   for r in self.skna_rows]
        self.waveform.set_review(regions, self._review_cur)

    def _open_artifact_review(self, start=None, from_dialog: bool = False):
        if not self._require_file():
            return
        if not self.skna_rows:
            QMessageBox.information(
                self, 'Artifact 判讀',
                '目前沒有任何 SKNA 區間。\n請先在「區間分析」用「自動分段計算」'
                '產生區段（例如每 10 秒一段），再逐段判讀。')
            return
        if from_dialog and self.skna_dlg is not None and self.skna_dlg.isVisible():
            self.skna_dlg.hide()
            self._review_restore_dlg = True
        if self.page != 1:
            self.set_page(1)
        if start is None:
            start = max(0, self.side.skna_list.currentRow())
        if self.review_dlg is None:
            self.review_dlg = ArtifactReviewDialog(self, start)
            g = self.geometry()
            self.review_dlg.adjustSize()
            self.review_dlg.move(g.right() - self.review_dlg.width() - 40,
                                 g.bottom() - self.review_dlg.height() - 80)
        else:
            self.review_dlg.goto(start)
        self.review_dlg.show()
        self.review_dlg.raise_()
        self.review_dlg.activateWindow()

    def _skna_goto_index(self, i: int):
        if 0 <= i < len(self.skna_rows):
            self.waveform.goto(self.skna_rows[i]['t0'])

    # ── S3 分解 ──────────────────────────────────────────────────────────────

    def _s3_is_valid(self) -> bool:
        """快取是否還對應得上目前的檔案與參數。"""
        c = self.s3_cache
        return (c is not None and self.ecg_data is not None
                and c.get('params') == s3_param_key(self.skna_cfg)
                and c.get('ch') == self.skna_cfg.get('src_ch'))

    def _s3_signal(self):
        """目前可用的 S3 SKNA 訊號；沒有或已失效就回 None。"""
        if self.skna_cfg.get('method') != 's3' or not self._s3_is_valid():
            return None
        return self.s3_cache['sna']

    def _invalidate_s3(self, reason: str = ''):
        if self.s3_cache is not None:
            self.s3_cache = None
            self.waveform.set_s3(None, None)
            if reason:
                self.lbl_status.setText(f'S3 分解結果已失效（{reason}），請重新執行。')
        self._update_skna_label()
        self._sync_skna_side()

    def _run_s3(self, whole_file: bool = True):
        if not self._require_file():
            return
        if self.s3_thread is not None and self.s3_thread.isRunning():
            QMessageBox.information(self, 'S3 執行中', '已經有一個 S3 分解在執行了。')
            return

        cfg = self.skna_cfg
        src = cfg.get('src_ch')
        if src is None:
            return

        t0 = t1 = None
        if not whole_file:
            pts = self.waveform.measure_pts
            if len(pts) >= 2:
                t0, t1 = sorted(pts[:2])
            else:
                t0, t1 = self.waveform.t_start, self.waveform.t_end
            if t1 - t0 < 2.0:
                QMessageBox.information(
                    self, '範圍太短',
                    'S3 需要至少 2 秒、且包含 10 個以上心跳的資料。')
                return

        fs = self.ecg_data.fs_of(src)
        n = (len(self.ecg_data.channels[src]) if whole_file
             else int((t1 - t0) * fs))
        est = max(1, int(n / fs / 60 * 1.5))     # 每分鐘約 1.5 秒（10 kHz 實測）
        rng = ('整個檔案' if whole_file
               else f'{fmt_hms(t0)} ～ {fmt_hms(t1)}')

        dlg = QProgressDialog(
            f'正在對 {rng} 執行 S3 分解…\n'
            f'來源 CH{src}: {self.ecg_data.ch_names[src]}',
            '取消', 0, 1000, self)
        dlg.setWindowTitle('S3 分解')
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumWidth(420)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setValue(0)
        dlg.setStyleSheet(_dialog_style())
        self._s3_dlg = dlg

        worker = S3Worker(self.ecg_data, cfg, t0, t1)
        self.s3_thread = worker
        # done_sig 是在 run() 裡面發出來的，那時執行緒還沒真正結束。
        # 若在該處就把 self.s3_thread 設成 None，最後一個 Python 參照會消失，
        # 垃圾回收可能在 run() 還在跑的時候把 QThread 物件銷毀，Qt 會直接
        # abort（「QThread: Destroyed while thread is still running」）。
        # 改成等 finished（run() 已返回）才放掉參照。
        worker.finished.connect(self._s3_thread_finished)

        def _on_prog(frac, msg):
            if not dlg.isVisible():
                return
            dlg.setValue(int(max(0.0, min(1.0, frac)) * 1000))
            dlg.setLabelText(
                f'正在對 {rng} 執行 S3 分解…\n'
                f'來源 CH{src}: {self.ecg_data.ch_names[src]}\n\n{msg}')

        def _on_done(res, err):
            dlg.close()
            if res is None:
                if err and err != '已取消':
                    QMessageBox.warning(self, 'S3 分解失敗', err)
                    self.lbl_status.setText(f'S3 分解失敗：{err}')
                else:
                    self.lbl_status.setText('S3 分解已取消。')
                return
            self.s3_cache = res
            self.waveform.set_s3(res['sna'], res['ecg'])
            self._update_skna_label()
            for i in range(len(self.skna_rows)):
                self._skna_compute_row(i)
            self._sync_skna_side()

            # 量化改善幅度，讓你當場知道這次分解有沒有效
            try:
                a, b = res['t0'], min(res['t1'], res['t0'] + 120.0)
                fs_s = self.ecg_data.fs_of(res['ch'])
                i0, i1 = int(a * fs_s), int(b * fs_s)
                lc = res['locs'][(res['locs'] >= i0) & (res['locs'] < i1)] - i0
                raw = self.ecg_data.channels[res['ch']][i0:i1]
                r_before = s3_residual_ratio(raw, fs_s, lc,
                                             cfg['bp_lo'], cfg['bp_hi'])
                r_after = s3_residual_ratio(res['sna'][i0:i1], fs_s, lc,
                                            cfg['bp_lo'], cfg['bp_hi'])
                imp = (f'　心跳殘留比 {r_before:.2f} → {r_after:.2f}'
                       if np.isfinite(r_before) and np.isfinite(r_after) else '')
            except Exception:
                imp = ''

            sat_note = ''
            sp = res.get('bad_pct', res.get('sat_pct', 0.0))
            if sp >= 1.0:
                sat_note = f'　⚠ 來源訊號有 {sp:.0f}% 無有效訊號，該部分結果不可信。'
            self.lbl_status.setText(
                f'S3 分解完成：{res["n_beat"]} 個心跳，片段長 '
                f'{res["p1"] + res["p2"] + 1} 點，有效秩 {res["rank"]}。{imp}{sat_note}')
            if sp >= 5.0:
                QMessageBox.warning(
                    self, 'S3 完成，但來源訊號有飽和',
                    f'分解已完成，但來源通道有 {sp:.0f}% 的樣本沒有有效訊號'
                    f'（飽和或完全無變化）。\n\n'
                    '那些區段的波形被削平、沒有訊號內容，S3 無法還原，'
                    '算出來的數值不具物理意義。\n'
                    '請在區間分析的「無效%」欄確認各區間的狀況。')
            if self.skna_dlg is not None:
                self.skna_dlg.recalc_all()

            # 分解完成後自動切到 SKNA 顯示。
            # 否則畫面上還是原始通道，使用者看不出 S3 到底有沒有生效，
            # 還得自己知道要再按一次 K。
            if not self.waveform.skna_enabled:
                self.act_skna.setChecked(True)      # 會觸發 _toggle_skna
            else:
                self.waveform._draw()

        worker.progress_sig.connect(_on_prog)
        worker.done_sig.connect(_on_done)
        dlg.canceled.connect(worker.cancel)
        self.lbl_status.setText(f'S3 分解中（預估約 {est} 秒）…')
        worker.start()
        dlg.show()

    def _toggle_s3_ecg_overlay(self, on: bool):
        if on and self.s3_cache is None:
            QMessageBox.information(
                self, '尚未分解',
                '請先在右側欄位按「S3 分解（整檔）」，才能疊上分離出來的心電成分。')
            self.act_s3_ecg.blockSignals(True)
            self.act_s3_ecg.setChecked(False)
            self.act_s3_ecg.blockSignals(False)
            return
        if on:
            src = self.skna_cfg.get('src_ch')
            if src is not None and self.waveform.ch_idx != src:
                self.waveform.set_channel(src)
        self.waveform.show_s3_ecg = bool(on)
        self.waveform._draw()

    def _update_filter_label(self):
        parts = []
        nf = self.waveform.notch_freq
        if nf > 0:
            parts.append(f'Notch {int(nf)} Hz')
        if self.waveform.bp_enabled:
            parts.append(f'BP {self.waveform.bp_lo:.0f}–{self.waveform.bp_hi:.0f} Hz')
        if parts:
            self.lbl_filter_state.setText('  ' + ' | '.join(parts))
            self.lbl_filter_state.setStyleSheet(f'color:{C["accent"]};font-size:11px;')
        else:
            self.lbl_filter_state.setText('  Off')
            self.lbl_filter_state.setStyleSheet(f'color:{C["dim"]};font-size:11px;')

    def _detect_peaks(self):
        if self.ecg_data is None:
            return
        t, y = self.ecg_data.segment(
            self.waveform.ch_idx,
            self.waveform.t_start,
            self.waveform.t_end)

        self.lbl_status.setText('正在偵測 R-peaks...')
        self.detector_thread = PeakDetector(
            y, self.ecg_data.fs_of(self.waveform.ch_idx), self.waveform.t_start,
            notch_freq=self.waveform.notch_freq,
            bp_enabled=self.waveform.bp_enabled,
            bp_lo=self.waveform.bp_lo,
            bp_hi=self.waveform.bp_hi)
        self.detector_thread.finished.connect(self._on_peaks_done)
        self.detector_thread.start()

    def _on_peaks_done(self, peaks, stats):
        # PeakDetector 是對「目前視窗那段」資料做偵測，回傳的 peaks 是相對
        # 那一段的索引；轉成絕對樣本索引（相對整個檔案）存起來，這樣之後
        # 平移視窗，峰值標記才不會消失或對不上。用偵測當下記錄的
        # t_offset，而不是現在的 self.waveform.t_start，避免偵測跑的期間
        # 剛好被平移過而算錯。
        if self.ecg_data is not None and self.detector_thread is not None and len(peaks) > 0:
            s_off = max(0, int(self.detector_thread.t_offset
                               * self.ecg_data.fs_of(self.waveform.ch_idx)))
            peaks = np.asarray(peaks, dtype=int) + s_off
        self.waveform.set_peaks(peaks, stats)
        self.side.update_rr(stats)
        if stats:
            self.lbl_status.setText(
                f'偵測到 {stats["count"]} 個 R-peaks  |  '
                f'HR: {stats["hr"]} bpm  |  '
                f'RR: {stats["rr_mean"]}±{stats["rr_std"]} ms  |  '
                f'RMSSD: {stats["rmssd"]} ms  |  CV: {stats["cv"]}%')
        else:
            self.lbl_status.setText('R-peak 偵測完成（結果不足）')

    def _show_goto_dialog(self):
        if self.ecg_data is None:
            return

        rec_dt = self.ecg_data.rec_datetime
        dur    = self.ecg_data.duration

        dlg = QDialog(self)
        dlg.setWindowTitle('前往時間點')
        dlg.setModal(True)
        dlg.setFixedWidth(360)

        lay = QVBoxLayout(dlg)
        lay.setSpacing(10)
        lay.setContentsMargins(16, 16, 16, 16)

        # 記錄時間資訊
        if rec_dt:
            end_dt  = data_abs_datetime(self.ecg_data, dur)
            info_str = f'{rec_dt.strftime("%H:%M:%S")} → {end_dt.strftime("%H:%M:%S")}   ({fmt_hms(dur)})'
        else:
            info_str = f'總長度：{fmt_hms(dur)}'
        lbl_info = QLabel(f'記錄時間：{info_str}')
        lbl_info.setStyleSheet(f'color:{C["accent"]}; font-size:11px;')
        lay.addWidget(lbl_info)

        edit_style = (
            f'QLineEdit{{background:{C["panel"]};color:{C["text"]};'
            f'border:1px solid {C["border"]};border-radius:6px;'
            f'padding:6px 10px;font-size:14px;}}'
            f'QLineEdit:focus{{border-color:{C["accent"]};}}')

        # ── 相對時間 ──
        grp_rel = QGroupBox('相對時間（從記錄開始）')
        grp_rel.setStyleSheet(f'QGroupBox{{color:{C["dim"]};font-size:11px;}}')
        rel_lay = QVBoxLayout(grp_rel)
        edit_rel = QLineEdit()
        edit_rel.setPlaceholderText('秒數  /  mm:ss  /  hh:mm:ss    例：48    01:23    1:23:45')
        edit_rel.setStyleSheet(edit_style)
        rel_lay.addWidget(edit_rel)
        lay.addWidget(grp_rel)

        # ── 絕對時間 ──
        grp_abs = QGroupBox('絕對時間（時鐘時間）')
        grp_abs.setStyleSheet(f'QGroupBox{{color:{C["dim"]};font-size:11px;}}')
        abs_lay = QVBoxLayout(grp_abs)
        edit_abs = QLineEdit()
        if rec_dt:
            edit_abs.setPlaceholderText(f'HH:MM:SS    例：{rec_dt.strftime("%H:%M:%S")}')
            edit_abs.setEnabled(True)
        else:
            edit_abs.setPlaceholderText('（此檔案無記錄時間資訊）')
            edit_abs.setEnabled(False)
        edit_abs.setStyleSheet(edit_style)
        abs_lay.addWidget(edit_abs)
        lay.addWidget(grp_abs)

        lbl_err = QLabel('')
        lbl_err.setStyleSheet(f'color:{C["red"]}; font-size:11px;')
        lay.addWidget(lbl_err)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton('前往')
        btn_ok.setObjectName('btn_success')
        btn_cancel = QPushButton('取消')
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        lay.addLayout(btn_row)

        def parse_rel(text):
            parts = text.replace(',', '.').split(':')
            if len(parts) == 1:   return float(parts[0])
            elif len(parts) == 2: return int(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
            return None

        def parse_abs(text):
            if not rec_dt: return None
            parts = text.replace(',', '.').split(':')
            if len(parts) == 2:
                h = rec_dt.hour; m = int(parts[0]); s = float(parts[1])
            elif len(parts) == 3:
                h = int(parts[0]); m = int(parts[1]); s = float(parts[2])
            else: return None
            target = rec_dt.replace(hour=h, minute=m,
                                    second=int(s),
                                    microsecond=int((s % 1) * 1_000_000))
            if target < rec_dt:
                target += datetime.timedelta(days=1)
            return data_rel_from_datetime(self.ecg_data, target)

        def do_goto():
            t_sec = None
            text_abs = edit_abs.text().strip()
            text_rel = edit_rel.text().strip()
            try:
                if text_abs and rec_dt:
                    t_sec = parse_abs(text_abs)
                elif text_rel:
                    t_sec = parse_rel(text_rel)
            except (ValueError, AttributeError):
                t_sec = None
            if t_sec is None:
                lbl_err.setText('無法解析，請確認格式')
                return
            t_sec = max(0.0, min(dur, t_sec))
            self.waveform.goto(t_sec)
            self.lbl_status.setText(
                f'已前往：{fmt_hms(t_sec)}  ({self.ecg_data.abs_time(t_sec)})')
            dlg.accept()

        btn_ok.clicked.connect(do_goto)
        btn_cancel.clicked.connect(dlg.reject)
        edit_rel.returnPressed.connect(do_goto)
        edit_abs.returnPressed.connect(do_goto)
        edit_rel.setFocus()
        dlg.exec()

    def _import_excel(self):
        if self.ecg_data is None:
            QMessageBox.information(self, '提示', '請先開啟 ECG 檔案')
            return

        path, _ = QFileDialog.getOpenFileName(
            self, '選擇實驗記錄 Excel',
            last_open_dir(getattr(self.ecg_data, 'path', None)),
            'Excel Files (*.xlsx *.xls);;All Files (*)')
        if not path:
            return

        try:
            events = parse_domap(path)
        except ImportError as e:
            QMessageBox.critical(self, '缺少套件',
                f'{e}\n\n請執行 install.command 重新安裝。')
            return
        except Exception as e:
            QMessageBox.critical(self, '讀取失敗', str(e))
            return

        if not events:
            QMessageBox.information(self, '結果', '找不到有 OMAP# 編號的事件')
            return

        dlg = ExcelImportDialog(events, self.ecg_data, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        valid = dlg.get_valid_events()
        for ev in valid:
            self.ts_mgr.add(ev['t_sec'], None, ev['label'], ev['note'],
                            '', self.ecg_data)

        self.side.refresh_ts_list()
        self.waveform._draw()
        self.lbl_status.setText(
            f'已匯入 {len(valid)} 筆時間戳記（來自 {os.path.basename(path)}）')

    def _screenshot(self):
        if self.ecg_data is None:
            return
        base = os.path.splitext(self.ecg_data.path)[0]
        now  = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        path = f'{base}_screenshot_{now}.png'
        pixmap = self.grab()
        pixmap.save(path)
        self.lbl_status.setText(f'截圖已儲存：{os.path.basename(path)}')

    def _show_help(self):
        QMessageBox.information(self, '快捷鍵說明', f"""
ECG Analyzer {APP_VERSION} 快捷鍵
支援格式：.abf / .edf / .acq
程式版本（原始碼最後修改）：{build_stamp()}
  ※ 更新程式後要「結束程式再重新開啟」才會生效，
    這一行可以用來確認目前跑的是哪一版。
━━━━━━━━━━━━━━━━━━━━━━━
兩個頁面（右側欄位最上方切換）：
  ECG   — R-peak 偵測與編輯、濾波、時間戳記
  SKNA  — SKNA 顯示、S3 分解、時間點位、區間分析

  兩頁共用同一個波形區，切換頁面不會改變目前
  檢視的位置。開啟／平移／縮放／重設／截圖／
  前往時間點／說明兩頁都有。
  縱軸的 ▲ ▼ 自動 按鈕在各軌道標題列上。
  進入 SKNA 頁會自動開啟 SKNA 顯示，離開時自動關閉；
  SKNA 設定與 S3 分解按鈕都在右側欄位的「SKNA 設定」區塊。
  SKNA 模式下軌道 2 的通道選單會鎖住（來源由 SKNA 設定
  決定），但 ▲ ▼ 自動 縱軸按鈕仍然可用。
  換檔案時若人還停在 SKNA 頁，會自動用新檔案重新判斷
  的來源通道接回 SKNA 顯示，不必切頁來回一趟。

「SKNA 區間分析」表格可以複製數值：
  拖曳框選想要的儲存格 → ⌘C（Windows 是 Ctrl+C），
  貼到 Excel 欄位會自動對齊。在表格上按右鍵還可以選
  「含欄位標題」或「複製整列」。
━━━━━━━━━━━━━━━━━━━━━━━
← / →     平移波形
+ / -     縮放時間軸
R         重設視圖
W / S     軌道 1 縱軸放大 / 縮小
E / C     軌道 2 縱軸放大 / 縮小
M         ECG 頁：切換測量模式
          SKNA 頁：切換新增時間點位模式
T         儲存時間戳記
P         偵測 R-peaks
X         切換 R-peak 編輯模式
K         切換 SKNA 顯示
S         截圖存檔

測量模式（ECG 頁）：
  進入 M 後，左鍵點擊波形設定 A 點，
  再次點擊設定 B 點，側邊欄顯示 Δt、Δt(ms) 與該範圍平均 BPM。
  按 T 將區間儲存為時間戳記（JSON + CSV）。

時間點位（SKNA 頁）：
  同一顆按鈕在 SKNA 頁變成「新增點位」。進入後點擊
  波形，輸入名稱並選擇「起點」或「終點」。
  起點會畫成綠色虛線、終點紅色虛線，並標上名稱。

  每個起點會和它之後最近的一個終點自動配對成分析
  區間，SKNA 指標立刻算好，並出現在側邊欄的
  「SKNA 時間區段」、區間分析視窗與 Excel 匯出中。
  沒配到對的點位會標成「尚未配對」。

  點位存在 檔名_SKNA_marks.json，下次開同一個檔案
  會自動載回。

R-peak 編輯模式：
  進入 X 後，點擊已標記的三角形可以刪除該峰值；
  點擊空白處會在附近振幅最大的樣本點新增峰值。
  編輯後 RR 間距與 HR 統計會即時更新。
  R-peak 標記會保留、不受平移視窗影響；
  工具列「清除 R-peak」可一次移除全部標記。

時間戳記：
  側邊欄可點選跳至對應時間，雙擊跳轉。
  儲存位置：與原始檔同目錄。

SKNA（皮膚交感神經活性）— 切到 SKNA 頁：
  按 K 或工具列「SKNA」→ 軌道 2 顯示帶通後的 rSNA
  （細線）與整流包絡（橘色粗線），軸標籤即時顯示
  目前視窗的 aSKNA。
  「SKNA 設定...」可調通道、頻帶（預設 500–1500 Hz）
  與包絡窗長。
  「SKNA 區間分析...」可用測量選取／手動輸入／時間戳記
  建立時間區間，計算 aSKNA、iSKNA 等指標並匯出 Excel。
  ※ 「匯出並開啟 Excel」不會先問存檔位置，直接產生暫存檔
    並用 Excel 打開；要保留請在 Excel 裡「另存新檔」。
    想一步到位選位置就用旁邊的「另存新檔...」。

  SKNA 頁的側邊欄會顯示目前的 SKNA 設定摘要，並有
  「SKNA 時間區段」清單：按 M 圈選範圍後按「節錄目前
  選取範圍」即可加入，雙擊清單項目跳到該段起點。
  這份清單與「SKNA 區間分析」視窗是同一份資料，
  任一邊新增或刪除，另一邊會同步。

  ※ BPF 模式不做任何樣本排除：aSKNA／iSKNA 一律用區間
    內全部樣本計算（含 QRS），與文獻傳統作法一致。
    心跳的高頻諧波仍會殘留在 SKNA 頻帶裡，心率越高越
    嚴重；若要去掉這部分干擾，請改用 S3 分解。

S3 演算法（移除心電干擾）：
  右側欄位「SKNA 設定」區的「S3 分解（整檔）」→ 對整檔執行
  （12 分鐘的檔約 15 秒）。
  分解完成後，軌道 2 的標籤會顯示 [S3]，區間分析與
  Excel 會多出一組 S3 欄位，與 BPF 那組並列可直接對照。

  原理：把每個心跳切成等長片段排成矩陣，心電成分因為
  形態高度相似而呈現低秩，用最佳奇異值收縮估出來再減掉，
  剩下的就是不含心電干擾的 SKNA。跟 BPF 不同的是，它是
  在「波形形態」上分離而不是在頻率上切，所以連 50–500 Hz
  這種 BPF 完全處理不了的低頻帶也能清乾淨。

  「疊心電成分」按鈕會把分離出來的心電成分（紅色）疊在
  軌道 1 上，用來確認分解有沒有貼合實際的 QRS。
━━━━━━━━━━━━━━━━━━━━━━━
""")

    # ── 訊號處理 ─────────────────────────────────────────────────────────────



    # 測量範圍超過此秒數就不即時計算 BPM（避免大範圍時卡住 UI），
    # 請改用「偵測 R-peaks (P)」在背景執行緒中計算。
    MEASURE_BPM_MAX_SEC = 300

    def _cached_peak_times_in_range(self, t_a: float, t_b: float):
        """回傳目前已標記（『偵測 R-peaks』或手動新增/刪除過）的峰值中，
        落在 [t_a, t_b] 範圍內的絕對時間。峰值一律存絕對樣本索引，跟
        目前畫面平移到哪裡無關；若沒有任何標記，回傳 None 讓呼叫端改用
        即時偵測。"""
        peaks = self.waveform._peaks_cache
        if peaks is None or len(peaks) == 0 or self.ecg_data is None:
            return None
        fs = self.ecg_data.fs_of(self.waveform.ch_idx)
        times = np.asarray(peaks, dtype=float) / fs
        return times[(times >= t_a) & (times <= t_b)]

    def _on_measure_updated(self, pts: list):
        bpm_info = None
        if len(pts) >= 2 and self.ecg_data is not None:
            t_a, t_b = sorted(pts[:2])
            dur = t_b - t_a
            if dur > 0:
                # 優先沿用畫面上已經有的峰值標記（可能是「偵測 R-peaks」
                # 的結果，也可能已經被手動新增/刪除修正過），確保測量範圍
                # 的 BPM 跟你在圖上實際看到、修正過的峰值一致，而不是每次
                # 都重新跑一次自動偵測、把你手動的修正忽略掉。
                cached_times = self._cached_peak_times_in_range(t_a, t_b)
                if cached_times is not None and len(cached_times) > 0:
                    bpm_info = rr_stats_from_times(cached_times) or {'count': len(cached_times)}
                elif dur > self.MEASURE_BPM_MAX_SEC:
                    bpm_info = {'skipped': True}
                else:
                    try:
                        _, y = self.ecg_data.segment(self.waveform.ch_idx, t_a, t_b)
                        peaks, stats = detect_r_peaks_and_stats(
                            y, self.ecg_data.fs_of(self.waveform.ch_idx),
                            notch_freq=self.waveform.notch_freq,
                            bp_enabled=self.waveform.bp_enabled,
                            bp_lo=self.waveform.bp_lo,
                            bp_hi=self.waveform.bp_hi)
                        bpm_info = stats if stats else {'count': len(peaks)}
                    except Exception:
                        bpm_info = None
        self.side.update_measure(pts, bpm_info)

    def _on_view_changed(self, t0: float, t1: float):
        self.side.update_view(t0, t1)

    def _on_ts_selected(self, idx: int):
        pass  # 可以加高亮

    def _on_ts_deleted(self, indices: list):
        if self.ts_mgr:
            for idx in sorted(indices, reverse=True):
                self.ts_mgr.remove(idx)
            self.side.refresh_ts_list()
            self.waveform._draw()

    def _on_ts_renamed(self, idx: int, label: str, note: str, tag: str):
        if self.ts_mgr:
            self.ts_mgr.update(idx, label, note, tag)
            self.side.refresh_ts_list()
            self.waveform._draw()

    # ── 拖放（主視窗）────────────────────────────────────────────────────────

    def _s3_thread_finished(self):
        """S3 執行緒真的跑完了才放掉參照（見 _run_s3 裡的說明）。"""
        th = self.s3_thread
        if th is not None and not th.isRunning():
            self.s3_thread = None

    def closeEvent(self, event):
        """關視窗前先把背景的 S3 執行緒收乾淨。

        S3 分解跑整檔要十幾秒。這段期間關掉視窗的話，QThread 物件會連同
        視窗一起被回收，但執行緒還在跑，Qt 會直接 abort（終端機上看到
        「QThread: Destroyed while thread is still running」）。
        先要求取消再等它結束，就不會在關閉時當掉。
        """
        th = getattr(self, 's3_thread', None)
        if th is not None and th.isRunning():
            try:
                th.cancel()
                self.lbl_status.setText('正在結束 S3 分解…')
                QApplication.processEvents()
                if not th.wait(5000):
                    th.terminate()
                    th.wait(1000)
            except Exception:
                pass
        self.s3_thread = None
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return   # 忽略系統的 auto-repeat，我們自己控制
        key = event.key()
        if key == Qt.Key.Key_Left:
            self._start_pan(-1)
        elif key == Qt.Key.Key_Right:
            self._start_pan(+1)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            return
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self._stop_pan()
        else:
            super().keyReleaseEvent(event)

    # ── 拖放檔案開啟 ────────────────────────────────────────────────────────
    # 分析畫面上直接把 .abf / .edf / .acq 拖進來即可開啟；
    # 已有開啟中的檔案時會先跳視窗確認，避免誤拖把目前的分析換掉。

    @staticmethod
    def _dropped_file(e) -> str | None:
        md = e.mimeData()
        if not md.hasUrls():
            return None
        for u in md.urls():
            path = u.toLocalFile()
            if path and path.lower().endswith(SUPPORTED_EXTS) and os.path.isfile(path):
                return path
        return None

    def dragEnterEvent(self, e: QDragEnterEvent):
        path = self._dropped_file(e)
        if path:
            e.acceptProposedAction()
            if self.ecg_data is not None:
                self._drop_prev_status = self.lbl_status.text()
                self.lbl_status.setText(f'📂 放開以開啟：{os.path.basename(path)}')
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if self._dropped_file(e):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        prev = getattr(self, '_drop_prev_status', None)
        if prev is not None:
            self.lbl_status.setText(prev)
            self._drop_prev_status = None

    def dropEvent(self, e: QDropEvent):
        path = self._dropped_file(e)
        prev = getattr(self, '_drop_prev_status', None)
        if prev is not None:
            self.lbl_status.setText(prev)
            self._drop_prev_status = None
        if not path:
            e.ignore()
            return
        e.acceptProposedAction()
        # 等拖放動作結束後再跳視窗，否則 macOS 的 Finder 會卡在拖曳狀態
        QTimer.singleShot(0, lambda p=path: self._open_dropped_file(p))

    def _open_dropped_file(self, path: str):
        if self.ecg_data is None:
            self.open_file(path)
            return
        cur_path = getattr(self.ecg_data, 'path', '') or ''
        new_name = os.path.basename(path)
        cur_name = os.path.basename(cur_path) if cur_path else '目前的檔案'
        if cur_path and os.path.abspath(cur_path) == os.path.abspath(path):
            msg = (f'「{new_name}」目前已經開啟。\n\n'
                   '要重新載入這個檔案嗎？')
            title = '重新載入檔案'
        else:
            msg = (f'要開啟新檔案嗎？\n\n'
                   f'新檔案：{new_name}\n'
                   f'目前檔案：{cur_name}（將會關閉）\n\n'
                   '時間戳記與 SKNA 標記點會自動儲存；\n'
                   '尚未匯出的分析結果（例如 R-peak 手動修改、SKNA 區間表）請先匯出。')
            title = '開啟新檔案'
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(title)
        box.setText(msg)
        btn_open = box.addButton('開啟', QMessageBox.ButtonRole.AcceptRole)
        box.addButton('取消', QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(btn_open)
        box.exec()
        if box.clickedButton() is btn_open:
            self.open_file(path)


# ══════════════════════════════════════════════════════════════════════════════
# 進入點
# ══════════════════════════════════════════════════════════════════════════════
def main():
    app = QApplication(sys.argv)
    app.setApplicationName('ECG Analyzer V5')
    # Dock / 視窗圖示（由 ECG Analyzer.app 傳入）
    _icon = os.environ.get('ECG_APP_ICON')
    if _icon and os.path.exists(_icon):
        from PyQt6.QtGui import QIcon
        app.setWindowIcon(QIcon(_icon))
    app.setApplicationVersion('5.0')
    app.setOrganizationName('Lab Tools')
    app.setStyleSheet(STYLESHEET)

    win = MainWindow()
    win.show()

    # 命令列直接開啟
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        win.open_file(sys.argv[1])

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
