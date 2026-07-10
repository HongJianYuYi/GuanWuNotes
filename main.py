import json
import os
import re
import sys
import time

import fitz
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QImage
from PyQt5.QtWidgets import *
from lunar_python import Solar


# ============================================
# 常量加载
# ============================================
def load_constants():
    constants_file = "constants.json"
    if not os.path.exists(constants_file):
        raise FileNotFoundError(f"找不到常量文件: {constants_file}")
    try:
        with open(constants_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise Exception(f"加载常量文件失败: {str(e)}")


CONSTANTS = load_constants()
Code = CONSTANTS["Code"]
Code_to_Gua = CONSTANTS["Code_to_Gua"]
Gua_to_Code = CONSTANTS["Gua_to_Code"]
Xian_Tian = CONSTANTS["Xian_Tian"]
Hou_Tian = CONSTANTS["Hou_Tian"]
Gua = CONSTANTS["Gua"]
Gan = CONSTANTS["Gan"]
Zhi = CONSTANTS["Zhi"]
Yue = CONSTANTS["Yue"]
Ri = CONSTANTS["Ri"]
Shi = CONSTANTS["Shi"]
Yi_Gua = CONSTANTS["Yi_Gua"]
Ce = CONSTANTS["Ce"]
Gui = CONSTANTS["Gui"]


# ============================================
# 通用函数
# ============================================
def calc_lunar_vars(Y, M, D, H):
    solar = Solar.fromYmd(Y, M, D)
    lunar = solar.getLunar()
    data = lunar.toFullString().split()
    y = int(Zhi[data[1][1]])
    data = data[0].split("年")
    data = data[1].split("月")
    m = int(Yue[data[0]])
    d = int(Ri[data[1]])
    h = int(Shi[str(H)])
    return y, m, d, h


def compute_guas(up_sym, down_sym, move):
    """根据上卦、下卦、动爻(1-6)计算本互变错综。
    返回的每个卦符组合均为"上卦+下卦"的顺序，与 Yi_Gua 及原程序显示一致。"""
    up_code = Gua_to_Code[up_sym]
    down_code = Gua_to_Code[down_sym]
    all_now = down_code + up_code  # [0:3]=下卦, [3:6]=上卦

    idx = move - 1
    all_will = list(all_now)
    all_will[idx] = '1' if all_will[idx] == '0' else '0'
    all_will = "".join(all_will)

    # 互卦：上卦=3,4,5爻(all_now[2:5])，下卦=2,3,4爻(all_now[1:4])
    hu = Code_to_Gua[all_now[2:5]] + Code_to_Gua[all_now[1:4]]

    # 变卦：上卦=all_will[3:6]，下卦=all_will[0:3]
    bian = Code_to_Gua[all_will[3:6]] + Code_to_Gua[all_will[0:3]]

    # 综卦：all_now反转后，前3位为综卦下卦，后3位为综卦上卦
    zong_s = all_now[::-1]
    zong = Code_to_Gua[zong_s[3:6]] + Code_to_Gua[zong_s[0:3]]

    # 错卦：all_now取反后，前3位为错卦上卦，后3位为错卦下卦
    cuo_s = "".join('1' if c == '0' else '0' for c in all_now)
    cuo = Code_to_Gua[cuo_s[3:6]] + Code_to_Gua[cuo_s[0:3]]

    # 本卦
    ben = up_sym + down_sym
    return [ben, hu, bian, cuo, zong], move


def calc_cegui(up_sym, down_sym, move):
    up_num = Gua_to_Code[up_sym]
    down_num = Gua_to_Code[down_sym]
    all_num = up_num + down_num
    s = sum(1 for c in all_num if c == '1')
    Yuan_Ce = Ce[s]
    Yuan_Gui = Gui[s]
    if move > 3:
        Ce_num = (move * 10 * Yuan_Ce) + (int(Xian_Tian[up_sym]) * Yuan_Ce) + Yuan_Ce + (
                int(Xian_Tian[up_sym]) + int(Xian_Tian[down_sym])) + move
        Gui_num = (move * 10 * Yuan_Gui) + (int(Hou_Tian[up_sym]) * Yuan_Gui) + Yuan_Gui + (
                int(Hou_Tian[up_sym]) + int(Hou_Tian[down_sym])) + move
    else:
        Ce_num = (int(Xian_Tian[down_sym]) * 10 * Yuan_Ce) + (move * Yuan_Ce) + Yuan_Ce + (
                int(Xian_Tian[up_sym]) + int(Xian_Tian[down_sym])) + move
        Gui_num = (int(Hou_Tian[down_sym]) * 10 * Yuan_Gui) + (move * Yuan_Gui) + Yuan_Gui + (
                int(Hou_Tian[up_sym]) + int(Hou_Tian[down_sym])) + move
    return Ce_num, Gui_num


def get_shizhi_num(hour):
    return int(Shi[str(hour)])


def get_lunar_text(year, month, day, hour):
    solar = Solar.fromYmd(year, month, day)
    lunar = solar.getLunar()
    shichen_map = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    shichen = shichen_map[get_shizhi_num(hour) - 1]
    return f"{lunar.getYearInGanZhi()}年 {lunar.getMonthInChinese()}月 {lunar.getDayInChinese()} {shichen}时"


# ============================================
# 卜辞模块
# ============================================
class YaoCiModule:
    @staticmethod
    def load_gua_data(gua_str):
        if not os.path.exists("YiCi.json"):
            return None, "未找到 YiCi.json 文件"
        try:
            with open("YiCi.json", "r", encoding="utf-8") as f:
                all_guas = json.load(f)
            gua_name = Yi_Gua.get(gua_str)
            if not gua_name or gua_name not in all_guas:
                return None, f"未找到卦象 {gua_str} 的爻辞数据"
            return all_guas[gua_name], None
        except Exception as e:
            return None, f"读取爻辞失败：{str(e)}"


# ============================================
# 可点击卦画标签
# ============================================
class ClickableGuaLabel(QLabel):
    clicked = pyqtSignal(int)

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.setCursor(Qt.PointingHandCursor)
        self._base_style = ""

    def setBaseStyle(self, style):
        self._base_style = style
        self.setStyleSheet(style)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.index)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.setStyleSheet(self._base_style + "\nQLabel { background: rgba(255,255,200,200); }")
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self._base_style)
        super().leaveEvent(event)


# ============================================
# 爻辞窗口
# ============================================
class YaoCiWindow(QMainWindow):
    def __init__(self, gua_name, gua_data, move, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"爻辞详解 · {gua_name}")
        self.resize(560, 780)
        self.setFixedSize(560, 780)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)
        self.setStyleSheet("background-color: #ffffff;")

        central = QWidget()
        self.setCentralWidget(central)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { background: #ffffff; border: none; }
            QScrollBar:vertical {
                background: #f0f0f0;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        container = QWidget()
        scroll.setWidget(container)
        main_layout = QVBoxLayout(central)
        main_layout.addWidget(scroll)

        layout = QVBoxLayout(container)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel(gua_name)
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("KaiTi", 22, QFont.Bold))
        title.setStyleSheet("color: #2c3e50; padding: 10px; border-bottom: 2px solid #34495e;")
        layout.addWidget(title)

        if "卦辞" in gua_data:
            layout.addWidget(self._create_card("卦辞", gua_data["卦辞"]))
        if "彖辞" in gua_data:
            layout.addWidget(self._create_card("彖辞", gua_data["彖辞"]))
        if "《象》曰" in gua_data:
            layout.addWidget(self._create_card("象辞", gua_data["《象》曰"]))

        all_yaos = ["初六", "初九", "六二", "九二", "六三", "九三",
                    "六四", "九四", "六五", "九五", "上六", "上九"]
        valid_yaos = [yao for yao in all_yaos if yao in gua_data]

        for i, yao in enumerate(valid_yaos):
            is_move = (i == move - 1)
            layout.addWidget(self._create_yao_card(yao, gua_data[yao], is_move))
        layout.addStretch()

    def _create_card(self, title, content):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(card)
        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("KaiTi", 14, QFont.Bold))
        content_lbl = QLabel(content)
        content_lbl.setWordWrap(True)
        content_lbl.setFont(QFont("KaiTi", 12))
        layout.addWidget(title_lbl)
        layout.addWidget(content_lbl)
        return card

    def _create_yao_card(self, yao, data, is_move):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: #ffffff;
                border: 2px solid {'#d00' if is_move else '#333'};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        layout = QVBoxLayout(card)
        name_text = f"🔴 {yao}" if is_move else yao
        name_lbl = QLabel(name_text)
        name_lbl.setFont(QFont("KaiTi", 14, QFont.Bold))
        name_lbl.setStyleSheet(f"color: {'#d00' if is_move else '#000'};")
        layout.addWidget(name_lbl)
        yao_lbl = QLabel(data.get("爻辞", ""))
        yao_lbl.setWordWrap(True)
        yao_lbl.setFont(QFont("KaiTi", 12))
        layout.addWidget(yao_lbl)
        xiang_lbl = QLabel(f"《象》曰：{data.get('象曰', '')}")
        xiang_lbl.setWordWrap(True)
        xiang_lbl.setFont(QFont("KaiTi", 12))
        xiang_lbl.setStyleSheet("color: #555;")
        layout.addWidget(xiang_lbl)
        return card


# ============================================
# 保存成功弹窗
# ============================================
class SaveSuccessDialog(QDialog):
    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self.setWindowTitle("保存成功")
        self.setFixedSize(520, 220)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                border-radius: 8px;
            }
            QGroupBox {
                border: 1px solid #E0E0E0;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                font-family: "Microsoft YaHei";
                font-size: 13px;
                color: #333333;
            }
            QLabel {
                color: #000000;
                font-family: "KaiTi";
                font-size: 14px;
            }
            QPushButton {
                background-color: #F5F5F5;
                color: #000000;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 6px 24px;
                font-family: "KaiTi";
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #EBEBEB;
            }
            QPushButton:pressed {
                background-color: #DEDEDE;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        content_box = QGroupBox("保存详情")
        box_layout = QVBoxLayout(content_box)
        box_layout.setContentsMargins(16, 20, 16, 16)
        box_layout.setSpacing(12)

        success_label = QLabel("笔记已成功保存")
        success_label.setAlignment(Qt.AlignCenter)
        success_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2D5C2D;")

        info_layout = QFormLayout()
        info_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignTop)
        info_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        info_layout.setHorizontalSpacing(20)
        info_layout.setVerticalSpacing(10)

        path_label = QLabel(filepath)
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_label.setStyleSheet("color: #444444; line-height: 1.5;")

        info_layout.addRow("<b>文件路径：</b>", path_label)

        box_layout.addWidget(success_label)
        box_layout.addLayout(info_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        confirm_btn = QPushButton("确 定")
        confirm_btn.clicked.connect(self.accept)
        confirm_btn.setDefault(True)
        btn_layout.addWidget(confirm_btn)

        main_layout.addWidget(content_box)
        main_layout.addLayout(btn_layout)


# ============================================
# 卦象显示面板
# ============================================
class GuaResultPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.gua_info = []
        self.current_move = 0
        self.yao_windows = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)

        # 策数轨数
        ce_row = QHBoxLayout()
        ce_row.setAlignment(Qt.AlignLeft)
        ce_row.addWidget(self._lbl("策数："))
        self.ce_input = QLineEdit("0")
        self.ce_input.setReadOnly(True)
        self.ce_input.setAlignment(Qt.AlignLeft)
        self.ce_input.setStyleSheet("""
            QLineEdit {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                border:1px solid rgba(255,255,255,150); color:#000;
                font-size:16px; font-family:KaiTi; font-weight:bold; border-radius:5px; padding:5px;
            }
        """)
        ce_row.addWidget(self.ce_input, 1)

        ce_row.addWidget(self._lbl("轨数："))
        self.gui_input = QLineEdit("0")
        self.gui_input.setReadOnly(True)
        self.gui_input.setAlignment(Qt.AlignLeft)
        self.gui_input.setStyleSheet(self.ce_input.styleSheet())
        ce_row.addWidget(self.gui_input, 1)

        layout.addLayout(ce_row)

        # 卦位
        pos = QHBoxLayout()
        pos.setAlignment(Qt.AlignCenter)
        for t in ["本", "互", "变", "错", "综"]:
            lbl = QLabel(t)
            lbl.setFixedWidth(125)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("""
                color:#000; background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                font-size:18px; font-family:KaiTi; font-weight:bold;
                border:1px solid rgba(255,255,255,150); border-radius:5px; padding:5px;
            """)
            pos.addWidget(lbl)
        layout.addLayout(pos)

        # 卦画
        self.gua_row = QHBoxLayout()
        self.gua_row.setAlignment(Qt.AlignCenter)
        self.gua_labels = []
        gua_names = ["本", "互", "变", "错", "综"]
        base_gua_style = """
            QLabel {
                color:#000;
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                border:1px solid rgba(255,255,255,150);
                border-radius:5px;
                padding:8px;
            }
        """
        for i in range(5):
            l = ClickableGuaLabel(i)
            l.setFont(QFont("KaiTi", 30))
            l.setFixedWidth(125)
            l.setAlignment(Qt.AlignCenter)
            l.setBaseStyle(base_gua_style)
            l.clicked.connect(self.on_gua_clicked)
            l.setToolTip(f"点击查看{gua_names[i]}卦爻辞")
            self.gua_labels.append(l)
            self.gua_row.addWidget(l)
        layout.addLayout(self.gua_row)

        # 卦名
        self.name_row = QHBoxLayout()
        self.name_row.setAlignment(Qt.AlignCenter)
        self.name_labels = []
        for _ in range(5):
            l = QLabel("")
            l.setFixedWidth(125)
            l.setAlignment(Qt.AlignCenter)
            l.setStyleSheet("""
                color:#000; background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                font-size:16px; font-family:KaiTi; font-weight:bold;
                border:1px solid rgba(255,255,255,150); border-radius:5px; padding:5px;
            """)
            self.name_labels.append(l)
            self.name_row.addWidget(l)
        layout.addLayout(self.name_row)

    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet("color:#fff; background:transparent; font-size:18px; font-family:KaiTi; font-weight:bold;")
        return l

    def set_result(self, gua_strs, move, ce_num, gui_num):
        self.current_move = move
        self.gua_info = []
        for i, g in enumerate(gua_strs):
            name = Yi_Gua.get(g, "未知")
            self.gua_labels[i].setText(g[0] + "\n" + g[1])
            self.name_labels[i].setText(name)
            self.gua_info.append((name, g))
        self.ce_input.setText(str(ce_num))
        self.gui_input.setText(str(gui_num))

    def clear(self):
        self.current_move = 0
        self.gua_info = []
        for i in range(5):
            self.gua_labels[i].setText("")
            self.name_labels[i].setText("")
        self.ce_input.setText("0")
        self.gui_input.setText("0")

    def on_gua_clicked(self, index):
        if not self.gua_info or index >= len(self.gua_info):
            QMessageBox.warning(self, "提示", "请先起卦再查看爻辞")
            return
        gua_name, gua_str = self.gua_info[index]
        move = self.current_move if index == 0 else 0
        gua_data, err = YaoCiModule.load_gua_data(gua_str)
        if err:
            QMessageBox.warning(self, "错误", err)
            return
        win = YaoCiWindow(gua_name, gua_data, move, self)
        win.show()
        self.yao_windows.append(win)


# ============================================
# 爻条组件
# ============================================
class YaoWidget(QWidget):
    clicked = pyqtSignal(int)
    moveClicked = pyqtSignal(int)

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.is_yang = True
        self.is_move = False
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(5, 2, 5, 2)

        self.yao_btn = QPushButton("———")
        self.yao_btn.setFixedSize(120, 36)
        self.yao_btn.setCursor(Qt.PointingHandCursor)
        self.yao_btn.clicked.connect(self.on_yao_clicked)

        self.move_btn = QPushButton("动")
        self.move_btn.setFixedSize(32, 32)
        self.move_btn.setCheckable(True)
        self.move_btn.clicked.connect(self.on_move_clicked)

        layout.addStretch()
        layout.addWidget(self.yao_btn)
        layout.addWidget(self.move_btn)
        layout.addStretch()

        self.update_style()

    def update_style(self):
        self.yao_btn.setText("———" if self.is_yang else "-  -")

        yao_ss = """
            QPushButton {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                border:1px solid rgba(255,255,255,150); color:#000;
                font-size:20px; font-family:KaiTi; font-weight:bold;
                border-radius:5px; padding:2px;
            }
            QPushButton:hover {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,230,220),stop:1 rgba(255,255,200,150));
            }
        """
        if self.is_move:
            yao_ss = yao_ss.replace("border:1px solid rgba(255,255,255,150)", "border:2px solid #c00")
            self.move_btn.setStyleSheet("""
                QPushButton {
                    background: #c00; color:#fff; font-size:12px; font-weight:bold;
                    border:1px solid #900; border-radius:4px;
                }
            """)
        else:
            self.move_btn.setStyleSheet("""
                QPushButton {
                    background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                    color:#000; font-size:12px; font-weight:bold;
                    border:1px solid rgba(255,255,255,150); border-radius:4px;
                }
            """)
        self.yao_btn.setStyleSheet(yao_ss)

    def on_yao_clicked(self):
        self.is_yang = not self.is_yang
        self.update_style()
        self.clicked.emit(self.index)

    def on_move_clicked(self, checked):
        self.is_move = checked
        self.update_style()
        self.moveClicked.emit(self.index)

    def set_move(self, is_move):
        self.is_move = is_move
        self.move_btn.setChecked(is_move)
        self.update_style()

    def set_yang(self, is_yang):
        self.is_yang = is_yang
        self.update_style()


# ============================================
# 时间起卦法页面
# ============================================
class TimePredictWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("观物心易 · 学习笔记")
        self.resize(880, 520)
        self.setStyleSheet("background:transparent;")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(880, 520)

        self.bg = QLabel(self)
        self.bg.setScaledContents(True)
        self.bg.setPixmap(QPixmap("bg.jpg"))
        self.bg.lower()
        self.resize_bg()

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: rgba(255,255,255,50); width: 12px; border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,150); border-radius: 6px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        self.scroll_widget = QWidget()
        self.scroll_area.setWidget(self.scroll_widget)

        self.init_ui()
        self.auto_calculate()

    def resize_bg(self):
        self.bg.setGeometry(0, 0, self.width(), self.height())

    def resizeEvent(self, event):
        self.resize_bg()
        self.scroll_area.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def init_ui(self):
        layout = QVBoxLayout(self.scroll_widget)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        layout.setContentsMargins(20, 20, 20, 20)

        # 时间行
        row1 = QHBoxLayout()
        row1.setAlignment(Qt.AlignLeft)
        row1.setSpacing(3)
        row1.addWidget(self._lbl("公历："))

        current_time = time.localtime()
        self.y_spin = QSpinBox()
        self.m_spin = QSpinBox()
        self.d_spin = QSpinBox()
        self.h_spin = QSpinBox()

        self.y_spin.setRange(1, 2100)
        self.m_spin.setRange(1, 12)
        self.d_spin.setRange(1, 31)
        self.h_spin.setRange(0, 23)

        self.y_spin.setValue(current_time.tm_year)
        self.m_spin.setValue(current_time.tm_mon)
        self.d_spin.setValue(current_time.tm_mday)
        self.h_spin.setValue(current_time.tm_hour)

        spin_style = """
            QSpinBox {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                color:#000; font-size:18px; font-family:KaiTi; font-weight:bold;
                border:1px solid rgba(255,255,255,150); border-radius:5px; padding:2px;
            }
            QSpinBox::up-button, QSpinBox::down-button { width:0; height:0; border:none; }
        """
        units = ["年", "月", "日", "时"]
        spins = [self.y_spin, self.m_spin, self.d_spin, self.h_spin]
        for spin, unit in zip(spins, units):
            spin.setFixedWidth(65)
            spin.setStyleSheet(spin_style)
            row1.addWidget(spin)
            row1.addWidget(self._lbl(unit))
        layout.addLayout(row1)

        # 农历行
        row2 = QHBoxLayout()
        row2.setAlignment(Qt.AlignLeft)
        row2.addWidget(self._lbl("农历："))
        self.lunar_display = QLabel(
            get_lunar_text(current_time.tm_year, current_time.tm_mon, current_time.tm_mday, current_time.tm_hour))
        self.lunar_display.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.lunar_display.setStyleSheet("""
            color:#000; background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
            font-size:18px; font-family:KaiTi; font-weight:bold;
            border:1px solid rgba(255,255,255,150); border-radius:5px; padding:5px;
        """)
        row2.addWidget(self.lunar_display)
        layout.addLayout(row2)

        # 求测
        qiu_row = QHBoxLayout()
        qiu_row.setAlignment(Qt.AlignLeft)
        qiu_row.addWidget(self._lbl("求测："))
        self.q_input = QTextEdit()
        self.q_input.setPlaceholderText("请输入...")
        self.q_input.setFixedHeight(40)
        self.q_input.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.q_input.setStyleSheet("""
            QTextEdit {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                border:1px solid rgba(255,255,255,150); color:#000;
                font-size:16px; font-family:KaiTi; font-weight:bold; border-radius:5px; padding:5px;
            }
            QScrollBar:vertical { 
                background: transparent; width: 8px; border-radius: 4px; 
            }
            QScrollBar::handle:vertical { 
                background: #c0c0c0; border-radius: 4px; min-height: 10px; 
            }
            QScrollBar::handle:vertical:hover { 
                background: #a0a0a0; 
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        qiu_row.addWidget(self.q_input)
        layout.addLayout(qiu_row)

        # 策数轨数
        ce_gui_row = QHBoxLayout()
        ce_gui_row.setAlignment(Qt.AlignLeft)
        ce_group = QHBoxLayout()
        ce_group.addWidget(self._lbl("策数："))
        self.ce_input = QLineEdit("0")
        self.ce_input.setReadOnly(True)
        self.ce_input.setAlignment(Qt.AlignCenter)
        self.ce_input.setFixedWidth(98)
        self.ce_input.setStyleSheet("""
            QLineEdit {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                border:1px solid rgba(255,255,255,150); color:#000;
                font-size:16px; font-family:KaiTi; font-weight:bold; border-radius:5px; padding:5px;
            }
        """)
        ce_group.addWidget(self.ce_input)

        gui_group = QHBoxLayout()
        gui_group.addWidget(self._lbl("轨数："))
        self.gui_input = QLineEdit("0")
        self.gui_input.setReadOnly(True)
        self.gui_input.setAlignment(Qt.AlignCenter)
        self.gui_input.setFixedWidth(98)
        self.gui_input.setStyleSheet(self.ce_input.styleSheet())
        gui_group.addWidget(self.gui_input)

        ce_gui_row.addLayout(ce_group)
        ce_gui_row.addLayout(gui_group)
        layout.addLayout(ce_gui_row)

        # 卦位
        pos = QHBoxLayout()
        pos.setAlignment(Qt.AlignCenter)
        for t in ["本", "互", "变", "错", "综"]:
            lbl = QLabel(t)
            lbl.setFixedWidth(125)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("""
                color:#000; background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                font-size:18px; font-family:KaiTi; font-weight:bold;
                border:1px solid rgba(255,255,255,150); border-radius:5px; padding:5px;
            """)
            pos.addWidget(lbl)
        layout.addLayout(pos)

        # 卦画
        self.gua_row = QHBoxLayout()
        self.gua_row.setAlignment(Qt.AlignCenter)
        self.gua_labels = []
        gua_names = ["本", "互", "变", "错", "综"]
        base_gua_style = """
            QLabel {
                color:#000;
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                border:1px solid rgba(255,255,255,150);
                border-radius:5px;
                padding:8px;
            }
        """
        for i in range(5):
            l = ClickableGuaLabel(i)
            l.setFont(QFont("KaiTi", 30))
            l.setFixedWidth(125)
            l.setAlignment(Qt.AlignCenter)
            l.setBaseStyle(base_gua_style)
            l.clicked.connect(self.on_gua_clicked)
            l.setToolTip(f"点击查看{gua_names[i]}卦爻辞")
            self.gua_labels.append(l)
            self.gua_row.addWidget(l)
        layout.addLayout(self.gua_row)

        # 卦名
        self.name_row = QHBoxLayout()
        self.name_row.setAlignment(Qt.AlignCenter)
        self.name_labels = []
        for _ in range(5):
            l = QLabel("")
            l.setFixedWidth(125)
            l.setAlignment(Qt.AlignCenter)
            l.setStyleSheet("""
                color:#000; background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                font-size:16px; font-family:KaiTi; font-weight:bold;
                border:1px solid rgba(255,255,255,150); border-radius:5px; padding:5px;
            """)
            self.name_labels.append(l)
            self.name_row.addWidget(l)
        layout.addLayout(self.name_row)

        # 断语
        duan_row = QHBoxLayout()
        duan_row.setAlignment(Qt.AlignLeft)
        duan_row.addWidget(self._lbl("断语："))
        self.duanyu_input = QTextEdit()
        self.duanyu_input.setPlaceholderText("请输入...")
        self.duanyu_input.setFixedHeight(55)
        self.duanyu_input.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.duanyu_input.setStyleSheet("""
            QTextEdit {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                border:1px solid rgba(255,255,255,150); color:#000;
                font-size:16px; font-family:KaiTi; font-weight:bold; border-radius:5px; padding:5px;
            }
            QScrollBar:vertical { 
                background: transparent; width: 8px; border-radius: 4px; 
            }
            QScrollBar::handle:vertical { 
                background: #c0c0c0; border-radius: 4px; min-height: 10px; 
            }
            QScrollBar::handle:vertical:hover { 
                background: #a0a0a0; 
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        duan_row.addWidget(self.duanyu_input)
        layout.addLayout(duan_row)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        btn_row.setSpacing(20)
        self.calc_btn = QPushButton("开始起卦")
        self.calc_btn.clicked.connect(self.calc)
        self.calc_btn.setStyleSheet("""
            QPushButton {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,220),stop:1 rgba(255,255,255,150));
                border:1px solid rgba(255,255,255,180); color:#000;
                font-size:16px; font-family:KaiTi; font-weight:bold;
                border-radius:8px; padding:8px 30px;
            }
        """)
        btn_row.addWidget(self.calc_btn)
        layout.addLayout(btn_row)

        self.gua_info = []
        self.current_move = 0
        self.yao_windows = []

    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet("color:#fff; background:transparent; font-size:18px; font-family:KaiTi; font-weight:bold;")
        return l

    def auto_calculate(self):
        self.calc()

    def calc(self):
        y, m, d, h = calc_lunar_vars(self.y_spin.value(), self.m_spin.value(), self.d_spin.value(), self.h_spin.value())
        self.lunar_display.setText(
            get_lunar_text(self.y_spin.value(), self.m_spin.value(), self.d_spin.value(), self.h_spin.value()))

        up_num = str((y + m + d) % 8)
        down_num = str((y + m + d + h) % 8)
        up_gua = Gua[up_num]
        down_gua = Gua[down_num]

        move_raw = (y + m + d + h) % 6
        move = move_raw if move_raw != 0 else 6

        guas, move = compute_guas(up_gua, down_gua, move)
        ce, gui = calc_cegui(up_gua, down_gua, move)
        self.current_move = move
        self.gua_info.clear()
        for i, g in enumerate(guas):
            name = Yi_Gua.get(g, "未知")
            self.gua_labels[i].setText(g[0] + "\n" + g[1])
            self.name_labels[i].setText(name)
            self.gua_info.append((name, g))
        self.ce_input.setText(str(ce))
        self.gui_input.setText(str(gui))

    def on_gua_clicked(self, index):
        if not self.gua_info or index >= len(self.gua_info):
            QMessageBox.warning(self, "提示", "请先起卦再查看爻辞")
            return
        gua_name, gua_str = self.gua_info[index]
        move = self.current_move if index == 0 else 0
        gua_data, err = YaoCiModule.load_gua_data(gua_str)
        if err:
            QMessageBox.warning(self, "错误", err)
            return
        win = YaoCiWindow(gua_name, gua_data, move, self)
        win.show()
        self.yao_windows.append(win)

    def get_case_data(self):
        return {
            "year": self.y_spin.value(),
            "month": self.m_spin.value(),
            "day": self.d_spin.value(),
            "hour": self.h_spin.value(),
            "lunar": self.lunar_display.text()
        }

    def load_case(self, data):
        self.y_spin.setValue(data.get("year", self.y_spin.value()))
        self.m_spin.setValue(data.get("month", self.m_spin.value()))
        self.d_spin.setValue(data.get("day", self.d_spin.value()))
        self.h_spin.setValue(data.get("hour", self.h_spin.value()))
        self.lunar_display.setText(data.get("lunar", ""))
        self.calc()


# ============================================
# 三数起卦法页面
# ============================================
class NumberPredictWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("观物心易 · 学习笔记")
        self.resize(880, 520)
        self.setStyleSheet("background:transparent;")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(880, 520)

        self.bg = QLabel(self)
        self.bg.setScaledContents(True)
        self.bg.setPixmap(QPixmap("bg.jpg"))
        self.bg.lower()
        self.resize_bg()

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: rgba(255,255,255,50); width: 12px; border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,150); border-radius: 6px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        self.scroll_widget = QWidget()
        self.scroll_area.setWidget(self.scroll_widget)

        self.init_ui()

    def resize_bg(self):
        self.bg.setGeometry(0, 0, self.width(), self.height())

    def resizeEvent(self, event):
        self.resize_bg()
        self.scroll_area.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def init_ui(self):
        layout = QVBoxLayout(self.scroll_widget)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        layout.setContentsMargins(20, 20, 20, 20)

        # 公历时间（可编辑）
        time_row = QHBoxLayout()
        time_row.setAlignment(Qt.AlignLeft)
        time_row.setSpacing(3)
        time_row.addWidget(self._lbl("公历："))

        current_time = time.localtime()
        self.y_spin = QSpinBox()
        self.m_spin = QSpinBox()
        self.d_spin = QSpinBox()
        self.h_spin = QSpinBox()

        self.y_spin.setRange(1, 2100)
        self.m_spin.setRange(1, 12)
        self.d_spin.setRange(1, 31)
        self.h_spin.setRange(0, 23)

        self.y_spin.setValue(current_time.tm_year)
        self.m_spin.setValue(current_time.tm_mon)
        self.d_spin.setValue(current_time.tm_mday)
        self.h_spin.setValue(current_time.tm_hour)

        spin_style = """
            QSpinBox {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                color:#000; font-size:18px; font-family:KaiTi; font-weight:bold;
                border:1px solid rgba(255,255,255,150); border-radius:5px; padding:2px;
            }
            QSpinBox::up-button, QSpinBox::down-button { width:0; height:0; border:none; }
        """
        units = ["年", "月", "日", "时"]
        spins = [self.y_spin, self.m_spin, self.d_spin, self.h_spin]
        for spin, unit in zip(spins, units):
            spin.setFixedWidth(65)
            spin.setStyleSheet(spin_style)
            time_row.addWidget(spin)
            time_row.addWidget(self._lbl(unit))
        layout.addLayout(time_row)

        # 农历行
        lunar_row = QHBoxLayout()
        lunar_row.setAlignment(Qt.AlignLeft)
        lunar_row.addWidget(self._lbl("农历："))
        self.lunar_display = QLabel(
            get_lunar_text(current_time.tm_year, current_time.tm_mon, current_time.tm_mday, current_time.tm_hour))
        self.lunar_display.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.lunar_display.setStyleSheet("""
            color:#000; background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
            font-size:18px; font-family:KaiTi; font-weight:bold;
            border:1px solid rgba(255,255,255,150); border-radius:5px; padding:5px;
        """)
        lunar_row.addWidget(self.lunar_display)
        layout.addLayout(lunar_row)

        # 数字输入
        num_row = QHBoxLayout()
        num_row.setAlignment(Qt.AlignLeft)
        self.num1 = QSpinBox()
        self.num2 = QSpinBox()
        self.num3 = QSpinBox()
        for spin in [self.num1, self.num2, self.num3]:
            spin.setRange(0, 999999)
            spin.setFixedWidth(120)
            spin.setStyleSheet("""
                QSpinBox {
                    background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                    color:#000; font-size:18px; font-family:KaiTi; font-weight:bold;
                    border:1px solid rgba(255,255,255,150); border-radius:5px; padding:2px;
                }
                QSpinBox::up-button, QSpinBox::down-button { width:0; height:0; border:none; }
            """)
        num_row.addWidget(self._lbl("数字一："))
        num_row.addWidget(self.num1)
        num_row.addWidget(self._lbl("数字二："))
        num_row.addWidget(self.num2)
        num_row.addWidget(self._lbl("数字三："))
        num_row.addWidget(self.num3)
        num_row.addStretch()
        layout.addLayout(num_row)

        # 求测
        qiu_row = QHBoxLayout()
        qiu_row.setAlignment(Qt.AlignLeft)
        qiu_row.addWidget(self._lbl("求测："))
        self.q_input = QTextEdit()
        self.q_input.setPlaceholderText("请输入...")
        self.q_input.setFixedHeight(40)
        self.q_input.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.q_input.setStyleSheet("""
            QTextEdit {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                border:1px solid rgba(255,255,255,150); color:#000;
                font-size:16px; font-family:KaiTi; font-weight:bold; border-radius:5px; padding:5px;
            }
            QScrollBar:vertical { 
                background: transparent; width: 8px; border-radius: 4px; 
            }
            QScrollBar::handle:vertical { 
                background: #c0c0c0; border-radius: 4px; min-height: 10px; 
            }
            QScrollBar::handle:vertical:hover { 
                background: #a0a0a0; 
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        qiu_row.addWidget(self.q_input)
        layout.addLayout(qiu_row)

        # 策数轨数
        ce_gui_row = QHBoxLayout()
        ce_gui_row.setAlignment(Qt.AlignLeft)
        ce_group = QHBoxLayout()
        ce_group.addWidget(self._lbl("策数："))
        self.ce_input = QLineEdit("0")
        self.ce_input.setReadOnly(True)
        self.ce_input.setAlignment(Qt.AlignCenter)
        self.ce_input.setFixedWidth(98)
        self.ce_input.setStyleSheet("""
            QLineEdit {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                border:1px solid rgba(255,255,255,150); color:#000;
                font-size:16px; font-family:KaiTi; font-weight:bold; border-radius:5px; padding:5px;
            }
        """)
        ce_group.addWidget(self.ce_input)

        gui_group = QHBoxLayout()
        gui_group.addWidget(self._lbl("轨数："))
        self.gui_input = QLineEdit("0")
        self.gui_input.setReadOnly(True)
        self.gui_input.setAlignment(Qt.AlignCenter)
        self.gui_input.setFixedWidth(98)
        self.gui_input.setStyleSheet(self.ce_input.styleSheet())
        gui_group.addWidget(self.gui_input)

        ce_gui_row.addLayout(ce_group)
        ce_gui_row.addLayout(gui_group)
        layout.addLayout(ce_gui_row)

        # 卦位
        pos = QHBoxLayout()
        pos.setAlignment(Qt.AlignCenter)
        for t in ["本", "互", "变", "错", "综"]:
            lbl = QLabel(t)
            lbl.setFixedWidth(125)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("""
                color:#000; background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                font-size:18px; font-family:KaiTi; font-weight:bold;
                border:1px solid rgba(255,255,255,150); border-radius:5px; padding:5px;
            """)
            pos.addWidget(lbl)
        layout.addLayout(pos)

        # 卦画
        self.gua_row = QHBoxLayout()
        self.gua_row.setAlignment(Qt.AlignCenter)
        self.gua_labels = []
        gua_names = ["本", "互", "变", "错", "综"]
        base_gua_style = """
            QLabel {
                color:#000;
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                border:1px solid rgba(255,255,255,150);
                border-radius:5px;
                padding:8px;
            }
        """
        for i in range(5):
            l = ClickableGuaLabel(i)
            l.setFont(QFont("KaiTi", 30))
            l.setFixedWidth(125)
            l.setAlignment(Qt.AlignCenter)
            l.setBaseStyle(base_gua_style)
            l.clicked.connect(self.on_gua_clicked)
            l.setToolTip(f"点击查看{gua_names[i]}卦爻辞")
            self.gua_labels.append(l)
            self.gua_row.addWidget(l)
        layout.addLayout(self.gua_row)

        # 卦名
        self.name_row = QHBoxLayout()
        self.name_row.setAlignment(Qt.AlignCenter)
        self.name_labels = []
        for _ in range(5):
            l = QLabel("")
            l.setFixedWidth(125)
            l.setAlignment(Qt.AlignCenter)
            l.setStyleSheet("""
                color:#000; background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                font-size:16px; font-family:KaiTi; font-weight:bold;
                border:1px solid rgba(255,255,255,150); border-radius:5px; padding:5px;
            """)
            self.name_labels.append(l)
            self.name_row.addWidget(l)
        layout.addLayout(self.name_row)

        # 断语
        duan_row = QHBoxLayout()
        duan_row.setAlignment(Qt.AlignLeft)
        duan_row.addWidget(self._lbl("断语："))
        self.duanyu_input = QTextEdit()
        self.duanyu_input.setPlaceholderText("请输入...")
        self.duanyu_input.setFixedHeight(55)
        self.duanyu_input.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.duanyu_input.setStyleSheet("""
            QTextEdit {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                border:1px solid rgba(255,255,255,150); color:#000;
                font-size:16px; font-family:KaiTi; font-weight:bold; border-radius:5px; padding:5px;
            }
            QScrollBar:vertical { 
                background: transparent; width: 8px; border-radius: 4px; 
            }
            QScrollBar::handle:vertical { 
                background: #c0c0c0; border-radius: 4px; min-height: 10px; 
            }
            QScrollBar::handle:vertical:hover { 
                background: #a0a0a0; 
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        duan_row.addWidget(self.duanyu_input)
        layout.addLayout(duan_row)

        # 按钮
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        btn_row.setSpacing(20)
        self.calc_btn = QPushButton("开始起卦")
        self.calc_btn.clicked.connect(self.calc)
        self.calc_btn.setStyleSheet("""
            QPushButton {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,220),stop:1 rgba(255,255,255,150));
                border:1px solid rgba(255,255,255,180); color:#000;
                font-size:16px; font-family:KaiTi; font-weight:bold;
                border-radius:8px; padding:8px 30px;
            }
        """)
        btn_row.addWidget(self.calc_btn)
        layout.addLayout(btn_row)

        self.gua_info = []
        self.current_move = 0
        self.yao_windows = []

    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet("color:#fff; background:transparent; font-size:18px; font-family:KaiTi; font-weight:bold;")
        return l

    def calc(self):
        n1 = self.num1.value()
        n2 = self.num2.value()
        n3 = self.num3.value()

        self.lunar_display.setText(
            get_lunar_text(self.y_spin.value(), self.m_spin.value(), self.d_spin.value(), self.h_spin.value()))

        up_num = n1 % 8
        down_num = (n2 + n3) % 8

        up_gua = Gua[str(up_num)]
        down_gua = Gua[str(down_num)]

        shizhi = get_shizhi_num(self.h_spin.value())
        move_raw = (n1 + n2 + n3 + shizhi) % 6
        move = move_raw if move_raw != 0 else 6

        guas, move = compute_guas(up_gua, down_gua, move)
        ce, gui = calc_cegui(up_gua, down_gua, move)
        self.current_move = move
        self.gua_info.clear()
        for i, g in enumerate(guas):
            name = Yi_Gua.get(g, "未知")
            self.gua_labels[i].setText(g[0] + "\n" + g[1])
            self.name_labels[i].setText(name)
            self.gua_info.append((name, g))
        self.ce_input.setText(str(ce))
        self.gui_input.setText(str(gui))

    def on_gua_clicked(self, index):
        if not self.gua_info or index >= len(self.gua_info):
            QMessageBox.warning(self, "提示", "请先起卦再查看爻辞")
            return
        gua_name, gua_str = self.gua_info[index]
        move = self.current_move if index == 0 else 0
        gua_data, err = YaoCiModule.load_gua_data(gua_str)
        if err:
            QMessageBox.warning(self, "错误", err)
            return
        win = YaoCiWindow(gua_name, gua_data, move, self)
        win.show()
        self.yao_windows.append(win)

    def get_case_data(self):
        return {
            "year": self.y_spin.value(),
            "month": self.m_spin.value(),
            "day": self.d_spin.value(),
            "hour": self.h_spin.value(),
            "lunar": self.lunar_display.text(),
            "num1": self.num1.value(),
            "num2": self.num2.value(),
            "num3": self.num3.value()
        }

    def load_case(self, data):
        self.y_spin.setValue(data.get("year", self.y_spin.value()))
        self.m_spin.setValue(data.get("month", self.m_spin.value()))
        self.d_spin.setValue(data.get("day", self.d_spin.value()))
        self.h_spin.setValue(data.get("hour", self.h_spin.value()))
        if "lunar" in data:
            self.lunar_display.setText(data["lunar"])
        self.num1.setValue(data.get("num1", 0))
        self.num2.setValue(data.get("num2", 0))
        self.num3.setValue(data.get("num3", 0))
        self.calc()


# ============================================
# 端法起卦页面
# ============================================
class ManualPredictWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("观物心易 · 学习笔记")
        self.resize(880, 520)
        self.setStyleSheet("background:transparent;")
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(880, 520)

        self.bg = QLabel(self)
        self.bg.setScaledContents(True)
        self.bg.setPixmap(QPixmap("bg.jpg"))
        self.bg.lower()
        self.resize_bg()

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: rgba(255,255,255,50); width: 12px; border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,150); border-radius: 6px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        self.scroll_widget = QWidget()
        self.scroll_area.setWidget(self.scroll_widget)

        self.init_ui()

    def resize_bg(self):
        self.bg.setGeometry(0, 0, self.width(), self.height())

    def resizeEvent(self, event):
        self.resize_bg()
        self.scroll_area.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def init_ui(self):
        layout = QVBoxLayout(self.scroll_widget)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        layout.setContentsMargins(20, 20, 20, 20)

        # 公历时间（可编辑）
        time_row = QHBoxLayout()
        time_row.setAlignment(Qt.AlignLeft)
        time_row.setSpacing(3)
        time_row.addWidget(self._lbl("公历："))

        current_time = time.localtime()
        self.y_spin = QSpinBox()
        self.m_spin = QSpinBox()
        self.d_spin = QSpinBox()
        self.h_spin = QSpinBox()

        self.y_spin.setRange(1, 2100)
        self.m_spin.setRange(1, 12)
        self.d_spin.setRange(1, 31)
        self.h_spin.setRange(0, 23)

        self.y_spin.setValue(current_time.tm_year)
        self.m_spin.setValue(current_time.tm_mon)
        self.d_spin.setValue(current_time.tm_mday)
        self.h_spin.setValue(current_time.tm_hour)

        spin_style = """
            QSpinBox {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                color:#000; font-size:18px; font-family:KaiTi; font-weight:bold;
                border:1px solid rgba(255,255,255,150); border-radius:5px; padding:2px;
            }
            QSpinBox::up-button, QSpinBox::down-button { width:0; height:0; border:none; }
        """
        units = ["年", "月", "日", "时"]
        spins = [self.y_spin, self.m_spin, self.d_spin, self.h_spin]
        for spin, unit in zip(spins, units):
            spin.setFixedWidth(65)
            spin.setStyleSheet(spin_style)
            time_row.addWidget(spin)
            time_row.addWidget(self._lbl(unit))
        layout.addLayout(time_row)

        # 农历行
        lunar_row = QHBoxLayout()
        lunar_row.setAlignment(Qt.AlignLeft)
        lunar_row.addWidget(self._lbl("农历："))
        self.lunar_display = QLabel(
            get_lunar_text(current_time.tm_year, current_time.tm_mon, current_time.tm_mday, current_time.tm_hour))
        self.lunar_display.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.lunar_display.setStyleSheet("""
            color:#000; background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
            font-size:18px; font-family:KaiTi; font-weight:bold;
            border:1px solid rgba(255,255,255,150); border-radius:5px; padding:5px;
        """)
        lunar_row.addWidget(self.lunar_display)
        layout.addLayout(lunar_row)

        # 起卦输入区
        self.input_container = QWidget()
        input_layout = QVBoxLayout(self.input_container)
        input_layout.setSpacing(6)
        input_layout.setContentsMargins(0, 0, 0, 0)

        # 六个爻条（0=初爻，5=上爻，从下往上记录）
        # UI显示：上爻在最上面，初爻在最下面
        self.yao_widgets = []
        yao_names = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"]
        for i in range(6):
            yw = YaoWidget(i)
            yw.clicked.connect(self.on_yao_clicked)
            yw.moveClicked.connect(self.on_move_clicked)
            self.yao_widgets.append(yw)

        # 从上爻到初爻，逆序添加到布局（上爻显示在最上面）
        for i in range(5, -1, -1):
            row = QHBoxLayout()
            row.setAlignment(Qt.AlignCenter)
            lbl = self._lbl(yao_names[i] + "：")
            row.addWidget(lbl)
            row.addWidget(self.yao_widgets[i])
            input_layout.addLayout(row)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        self.calc_btn = QPushButton("开始起卦")
        self.calc_btn.clicked.connect(self.calc)
        self.calc_btn.setStyleSheet("""
            QPushButton {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,220),stop:1 rgba(255,255,255,150));
                border:1px solid rgba(255,255,255,180); color:#000;
                font-size:16px; font-family:KaiTi; font-weight:bold;
                border-radius:8px; padding:8px 30px;
            }
        """)
        btn_row.addWidget(self.calc_btn)
        input_layout.addLayout(btn_row)
        layout.addWidget(self.input_container)

        # 重新起卦按钮（默认隐藏）
        self.reset_btn = QPushButton("重新起卦")
        self.reset_btn.setStyleSheet(self.calc_btn.styleSheet())
        self.reset_btn.clicked.connect(self.on_reset)
        self.reset_btn.hide()
        reset_row = QHBoxLayout()
        reset_row.setAlignment(Qt.AlignCenter)
        reset_row.addWidget(self.reset_btn)
        layout.addLayout(reset_row)

        # 求测
        qiu_row = QHBoxLayout()
        qiu_row.setAlignment(Qt.AlignLeft)
        qiu_row.addWidget(self._lbl("求测："))
        self.q_input = QTextEdit()
        self.q_input.setPlaceholderText("请输入...")
        self.q_input.setFixedHeight(40)
        self.q_input.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.q_input.setStyleSheet("""
            QTextEdit {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                border:1px solid rgba(255,255,255,150); color:#000;
                font-size:16px; font-family:KaiTi; font-weight:bold; border-radius:5px; padding:5px;
            }
            QScrollBar:vertical { 
                background: transparent; width: 8px; border-radius: 4px; 
            }
            QScrollBar::handle:vertical { 
                background: #c0c0c0; border-radius: 4px; min-height: 10px; 
            }
            QScrollBar::handle:vertical:hover { 
                background: #a0a0a0; 
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        qiu_row.addWidget(self.q_input)
        layout.addLayout(qiu_row)

        # 策数轨数
        ce_gui_row = QHBoxLayout()
        ce_gui_row.setAlignment(Qt.AlignLeft)
        ce_group = QHBoxLayout()
        ce_group.addWidget(self._lbl("策数："))
        self.ce_input = QLineEdit("0")
        self.ce_input.setReadOnly(True)
        self.ce_input.setAlignment(Qt.AlignCenter)
        self.ce_input.setFixedWidth(98)
        self.ce_input.setStyleSheet("""
            QLineEdit {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                border:1px solid rgba(255,255,255,150); color:#000;
                font-size:16px; font-family:KaiTi; font-weight:bold; border-radius:5px; padding:5px;
            }
        """)
        ce_group.addWidget(self.ce_input)

        gui_group = QHBoxLayout()
        gui_group.addWidget(self._lbl("轨数："))
        self.gui_input = QLineEdit("0")
        self.gui_input.setReadOnly(True)
        self.gui_input.setAlignment(Qt.AlignCenter)
        self.gui_input.setFixedWidth(98)
        self.gui_input.setStyleSheet(self.ce_input.styleSheet())
        gui_group.addWidget(self.gui_input)

        ce_gui_row.addLayout(ce_group)
        ce_gui_row.addLayout(gui_group)
        layout.addLayout(ce_gui_row)

        # 卦位
        pos = QHBoxLayout()
        pos.setAlignment(Qt.AlignCenter)
        for t in ["本", "互", "变", "错", "综"]:
            lbl = QLabel(t)
            lbl.setFixedWidth(125)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("""
                color:#000; background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                font-size:18px; font-family:KaiTi; font-weight:bold;
                border:1px solid rgba(255,255,255,150); border-radius:5px; padding:5px;
            """)
            pos.addWidget(lbl)
        layout.addLayout(pos)

        # 卦画
        self.gua_row = QHBoxLayout()
        self.gua_row.setAlignment(Qt.AlignCenter)
        self.gua_labels = []
        gua_names = ["本", "互", "变", "错", "综"]
        base_gua_style = """
            QLabel {
                color:#000;
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                border:1px solid rgba(255,255,255,150);
                border-radius:5px;
                padding:8px;
            }
        """
        for i in range(5):
            l = ClickableGuaLabel(i)
            l.setFont(QFont("KaiTi", 30))
            l.setFixedWidth(125)
            l.setAlignment(Qt.AlignCenter)
            l.setBaseStyle(base_gua_style)
            l.clicked.connect(self.on_gua_clicked)
            l.setToolTip(f"点击查看{gua_names[i]}卦爻辞")
            self.gua_labels.append(l)
            self.gua_row.addWidget(l)
        layout.addLayout(self.gua_row)

        # 卦名
        self.name_row = QHBoxLayout()
        self.name_row.setAlignment(Qt.AlignCenter)
        self.name_labels = []
        for _ in range(5):
            l = QLabel("")
            l.setFixedWidth(125)
            l.setAlignment(Qt.AlignCenter)
            l.setStyleSheet("""
                color:#000; background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                font-size:16px; font-family:KaiTi; font-weight:bold;
                border:1px solid rgba(255,255,255,150); border-radius:5px; padding:5px;
            """)
            self.name_labels.append(l)
            self.name_row.addWidget(l)
        layout.addLayout(self.name_row)

        # 断语
        duan_row = QHBoxLayout()
        duan_row.setAlignment(Qt.AlignLeft)
        duan_row.addWidget(self._lbl("断语："))
        self.duanyu_input = QTextEdit()
        self.duanyu_input.setPlaceholderText("请输入...")
        self.duanyu_input.setFixedHeight(55)
        self.duanyu_input.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.duanyu_input.setStyleSheet("""
            QTextEdit {
                background: qradialgradient(cx:0.5,cy:0.5,radius:0.5,stop:0 rgba(255,255,255,200),stop:1 rgba(255,255,255,100));
                border:1px solid rgba(255,255,255,150); color:#000;
                font-size:16px; font-family:KaiTi; font-weight:bold; border-radius:5px; padding:5px;
            }
            QScrollBar:vertical { 
                background: transparent; width: 8px; border-radius: 4px; 
            }
            QScrollBar::handle:vertical { 
                background: #c0c0c0; border-radius: 4px; min-height: 10px; 
            }
            QScrollBar::handle:vertical:hover { 
                background: #a0a0a0; 
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        duan_row.addWidget(self.duanyu_input)
        layout.addLayout(duan_row)

        self.gua_info = []
        self.current_move = 0
        self.yao_windows = []

    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet("color:#fff; background:transparent; font-size:18px; font-family:KaiTi; font-weight:bold;")
        return l

    def on_yao_clicked(self, index):
        pass

    def on_move_clicked(self, index):
        for i, yw in enumerate(self.yao_widgets):
            if i != index:
                yw.set_move(False)

    def calc(self):
        self.lunar_display.setText(
            get_lunar_text(self.y_spin.value(), self.m_spin.value(), self.d_spin.value(), self.h_spin.value()))

        # 下卦 = 初爻、二爻、三爻 (index 0-2)
        down_code = "".join('1' if self.yao_widgets[i].is_yang else '0' for i in range(3))
        # 上卦 = 四爻、五爻、上爻 (index 3-5)
        up_code = "".join('1' if self.yao_widgets[i].is_yang else '0' for i in range(3, 6))
        up_gua = Code_to_Gua[up_code]
        down_gua = Code_to_Gua[down_code]

        move_yao = -1
        for i, yw in enumerate(self.yao_widgets):
            if yw.is_move:
                move_yao = i
                break

        if move_yao == -1:
            QMessageBox.warning(self, "提示", "请选择一个动爻")
            return

        move = move_yao + 1

        guas, move = compute_guas(up_gua, down_gua, move)
        ce, gui = calc_cegui(up_gua, down_gua, move)
        self.current_move = move
        self.gua_info.clear()
        for i, g in enumerate(guas):
            name = Yi_Gua.get(g, "未知")
            self.gua_labels[i].setText(g[0] + "\n" + g[1])
            self.name_labels[i].setText(name)
            self.gua_info.append((name, g))
        self.ce_input.setText(str(ce))
        self.gui_input.setText(str(gui))

        self.input_container.hide()
        self.reset_btn.show()

    def on_gua_clicked(self, index):
        if not self.gua_info or index >= len(self.gua_info):
            QMessageBox.warning(self, "提示", "请先起卦再查看爻辞")
            return
        gua_name, gua_str = self.gua_info[index]
        move = self.current_move if index == 0 else 0
        gua_data, err = YaoCiModule.load_gua_data(gua_str)
        if err:
            QMessageBox.warning(self, "错误", err)
            return
        win = YaoCiWindow(gua_name, gua_data, move, self)
        win.show()
        self.yao_windows.append(win)

    def on_reset(self):
        self.input_container.show()
        self.reset_btn.hide()
        for i in range(5):
            self.gua_labels[i].setText("")
            self.name_labels[i].setText("")
        self.ce_input.setText("0")
        self.gui_input.setText("0")
        self.gua_info.clear()
        self.current_move = 0

    def get_case_data(self):
        return {
            "year": self.y_spin.value(),
            "month": self.m_spin.value(),
            "day": self.d_spin.value(),
            "hour": self.h_spin.value(),
            "lunar": self.lunar_display.text(),
            "yaos": [1 if yw.is_yang else 0 for yw in self.yao_widgets],
            "move_yao": next((i for i, yw in enumerate(self.yao_widgets) if yw.is_move), -1)
        }

    def load_case(self, data):
        self.y_spin.setValue(data.get("year", self.y_spin.value()))
        self.m_spin.setValue(data.get("month", self.m_spin.value()))
        self.d_spin.setValue(data.get("day", self.d_spin.value()))
        self.h_spin.setValue(data.get("hour", self.h_spin.value()))
        if "lunar" in data:
            self.lunar_display.setText(data["lunar"])
        yaos = data.get("yaos", [1, 1, 1, 1, 1, 1])
        for i, v in enumerate(yaos):
            self.yao_widgets[i].set_yang(v == 1)
        move_yao = data.get("move_yao", -1)
        for i, yw in enumerate(self.yao_widgets):
            yw.set_move(i == move_yao)
        if move_yao != -1:
            self.calc()


# ============================================
# PDF阅读器（带书架功能）
# ============================================
class PDFViewerWindow(QMainWindow):
    def __init__(self, filepath=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("电子书阅读器")
        self.resize(880, 660)
        self.doc = None
        self.page_labels = []
        self.zoom_level = 1.5
        self.current_file = None
        self.books_dir = "books"
        os.makedirs(self.books_dir, exist_ok=True)
        self.init_ui()
        self.load_bookshelf()
        if filepath and os.path.exists(filepath):
            self.load_pdf(filepath)

    def init_ui(self):
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        toolbar.addAction("导入书籍", self.import_book)
        toolbar.addAction("打开文件", self.open_pdf)
        toolbar.addAction("放大", self.zoom_in)
        toolbar.addAction("缩小", self.zoom_out)

        main_splitter = QSplitter(Qt.Horizontal)

        bookshelf_widget = QWidget()
        bookshelf_layout = QVBoxLayout(bookshelf_widget)
        bookshelf_layout.setContentsMargins(5, 5, 5, 5)
        bookshelf_layout.setSpacing(5)

        bookshelf_title = QLabel("📚 书架")
        bookshelf_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        bookshelf_layout.addWidget(bookshelf_title)

        self.books_list = QListWidget()
        self.books_list.setStyleSheet("""
            QListWidget {
                background: #f8f8f8;
                font-family: "Microsoft YaHei";
                font-size: 13px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:hover {
                background: #e8f4fc;
            }
            QListWidget::item:selected {
                background: #3498db;
                color: white;
            }
        """)
        self.books_list.itemDoubleClicked.connect(self.on_book_selected)
        bookshelf_layout.addWidget(self.books_list)

        import_btn = QPushButton("导入书籍")
        import_btn.setStyleSheet("""
            QPushButton {
                background: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #2980b9;
            }
        """)
        import_btn.clicked.connect(self.import_book)
        bookshelf_layout.addWidget(import_btn)

        main_splitter.addWidget(bookshelf_widget)
        main_splitter.setSizes([200, 800])

        right_splitter = QSplitter(Qt.Vertical)

        self.toc_tree = QTreeWidget()
        self.toc_tree.setHeaderLabel("目录")
        self.toc_tree.itemClicked.connect(self.on_toc_clicked)
        self.toc_tree.setStyleSheet("""
            QTreeWidget {
                background: #f8f8f8;
                font-family: "Microsoft YaHei";
                font-size: 13px;
            }
            QTreeWidget::item {
                padding: 4px;
            }
        """)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { background: #333; border: none; }")
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(10)
        self.content_layout.setAlignment(Qt.AlignCenter)
        self.scroll.setWidget(self.content_widget)

        right_splitter.addWidget(self.toc_tree)
        right_splitter.addWidget(self.scroll)
        right_splitter.setSizes([150, 550])

        main_splitter.addWidget(right_splitter)
        self.setCentralWidget(main_splitter)

    def load_bookshelf(self):
        self.books_list.clear()
        if not os.path.exists(self.books_dir):
            os.makedirs(self.books_dir)
            return
        for filename in sorted(os.listdir(self.books_dir)):
            if filename.lower().endswith(".pdf"):
                item = QListWidgetItem(filename)
                item.setData(Qt.UserRole, os.path.join(self.books_dir, filename))
                self.books_list.addItem(item)

    def import_book(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择PDF文件", "", "PDF文件 (*.pdf)")
        if not path:
            return
        try:
            import shutil
            filename = os.path.basename(path)
            dest_path = os.path.join(self.books_dir, filename)
            if os.path.exists(dest_path):
                reply = QMessageBox.question(self, "提示", f"文件 {filename} 已存在，是否覆盖？",
                                             QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply != QMessageBox.Yes:
                    return
            shutil.copy2(path, dest_path)
            self.load_bookshelf()
            QMessageBox.information(self, "成功", f"书籍 {filename} 已导入书架")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败：{str(e)}")

    def on_book_selected(self, item):
        path = item.data(Qt.UserRole)
        if path:
            self.load_pdf(path)

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开PDF", "", "PDF文件 (*.pdf)")
        if path:
            self.load_pdf(path)

    def load_pdf(self, path):
        try:
            self.doc = fitz.open(path)
            self.current_file = path
            self.setWindowTitle(f"电子书阅读器 - {os.path.basename(path)}")
            self.render_pages()
            self.load_toc()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法打开PDF：{str(e)}")

    def render_pages(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.page_labels = []

        if not self.doc:
            return

        mat = fitz.Matrix(self.zoom_level, self.zoom_level)
        for i in range(len(self.doc)):
            page = self.doc.load_page(i)
            pix = page.get_pixmap(matrix=mat)
            fmt = QImage.Format_RGBA8888 if pix.n == 4 else QImage.Format_RGB888
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
            lbl = QLabel()
            lbl.setPixmap(QPixmap.fromImage(img))
            lbl.setStyleSheet("background: #fff;")
            self.content_layout.addWidget(lbl)
            self.page_labels.append(lbl)
        self.content_layout.addStretch()

    def load_toc(self):
        self.toc_tree.clear()
        if not self.doc:
            item = QTreeWidgetItem(["（请先打开书籍）"])
            self.toc_tree.addTopLevelItem(item)
            return
        toc = self.doc.get_toc()
        if not toc:
            item = QTreeWidgetItem(["（无目录）"])
            self.toc_tree.addTopLevelItem(item)
            return

        stack = [self.toc_tree.invisibleRootItem()]
        for level, title, page in toc:
            item = QTreeWidgetItem([title])
            item.setData(0, Qt.UserRole, page - 1)
            while len(stack) >= level + 1:
                stack.pop()
            if stack:
                stack[-1].addChild(item)
            else:
                self.toc_tree.addTopLevelItem(item)
            stack.append(item)
        self.toc_tree.expandAll()

    def on_toc_clicked(self, item, column):
        page_idx = item.data(0, Qt.UserRole)
        if page_idx is not None and 0 <= page_idx < len(self.page_labels):
            self.scroll.ensureWidgetVisible(self.page_labels[page_idx], 0, 0)

    def zoom_in(self):
        self.zoom_level += 0.2
        self.render_pages()

    def zoom_out(self):
        if self.zoom_level > 0.4:
            self.zoom_level -= 0.2
            self.render_pages()


# ============================================
# 帮助窗口
# ============================================
class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("使用指南")
        self.resize(640, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet("""
            QTextBrowser {
                background: #fff;
                font-family: "Microsoft YaHei", "KaiTi";
                font-size: 14px;
                line-height: 1.6;
                border: 1px solid #ccc;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        browser.setHtml("""
        <html>
        <head><meta charset="utf-8"></head>
        <body style="font-family: KaiTi, Microsoft YaHei; color: #333;">
        <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 6px;">观物心易 · 使用指南</h2>

        <h3 style="color: #c0392b;">一、时间起卦法</h3>
        <p>默认打开即为时间起卦法。输入公历的年、月、日、时，程序自动转换为农历，并按梅花易数规则排卦：</p>
        <ul>
            <li><b>上卦</b> = (年支 + 月 + 日) ÷ 8 之余数</li>
            <li><b>下卦</b> = (年支 + 月 + 日 + 时支) ÷ 8 之余数</li>
            <li><b>动爻</b> = (年支 + 月 + 日 + 时支) ÷ 6 之余数</li>
        </ul>
        <p>系统会自动计算出<b>本卦、互卦、变卦、错卦、综卦</b>，并显示策数与轨数。点击卦画可查看爻辞详解。</p>

        <h3 style="color: #c0392b;">二、三数起卦法</h3>
        <p>点击菜单 <b>工具 → 三数起卦法</b> 切换。输入任意三个数字：</p>
        <ul>
            <li><b>上卦</b> = 数字一 ÷ 8 之余数</li>
            <li><b>下卦</b> = (数字二 + 数字三) ÷ 8 之余数</li>
            <li><b>动爻</b> = (三数之和 + 当前时支) ÷ 6 之余数</li>
        </ul>
        <p>互、变、错、综的计算逻辑与时间起卦法完全一致。</p>

        <h3 style="color: #c0392b;">三、端法起卦</h3>
        <p>点击菜单 <b>工具 → 端法起卦</b> 切换。通过手动设定六爻来成卦：</p>
        <ul>
            <li>点击<b>爻条</b>可在阳爻（———）与阴爻（- -）之间切换</li>
            <li>点击爻条旁的<b>“动”</b>按钮设定动爻，仅允许选择一个动爻</li>
            <li>设定完成后点击<b>“开始起卦”</b>，系统将隐藏爻条并展示卦局</li>
            <li>点击<b>“重新起卦”</b>可再次调整六爻</li>
        </ul>

        <h3 style="color: #c0392b;">四、保存与导入案例</h3>
        <p><b>保存笔记：</b>点击菜单 <b>开始 → 保存笔记</b>，系统会将当前卦局、求测内容、断语等信息保存为 JSON 文件，存放于 <code>notes</code> 目录。</p>
        <p><b>案例导入：</b>点击菜单 <b>资料 → 案例导入</b>，选择之前保存的 JSON 文件，即可恢复当时的卦局与输入。</p>

        <h3 style="color: #c0392b;">五、电子书阅读器</h3>
        <p>点击菜单 <b>资料 → 电子书</b> 可打开 PDF 阅读器。支持目录树导航、页面跳转、放大缩小等功能。程序默认查找同级目录下的 <code>help.pdf</code>，若无则提示手动选择。</p>

        <h3 style="color: #c0392b;">六、爻辞查看</h3>
        <p>无论以何种方式起卦，点击卦局中的任意<b>卦画</b>，即可弹出该卦的爻辞窗口。动爻将以红色高亮显示，方便查阅。</p>

        <p style="margin-top: 20px; color: #888; font-size: 12px;">祝学习愉快，观物取象，心易灵通。</p>
        </body>
        </html>
        """)
        layout.addWidget(browser)

        btn = QPushButton("关 闭")
        btn.setStyleSheet("""
            QPushButton {
                background: #f0f0f0; border: 1px solid #ccc; border-radius: 4px;
                padding: 6px 24px; font-family: KaiTi; font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background: #e0e0e0; }
        """)
        btn.clicked.connect(self.accept)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)


# ============================================
# 主窗口
# ============================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("观物心易 · 学习笔记")
        self.resize(880, 550)
        self.setFixedSize(880, 550)

        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background: #000;
                color: #fff;
                font-family: KaiTi;
                font-size: 18px;
                padding: 6px 0;
            }
            QMenuBar::item {
                padding: 4px 12px;
            }
            QMenuBar::item:selected {
                background: #333;
            }
            QMenu {
                background: #1a1a1a;
                color: #fff;
                font-family: KaiTi;
                font-size: 16px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
            }
            QMenu::item:selected {
                background: #333;
            }
        """)

        start_menu = menubar.addMenu("开始")
        start_menu.addAction("起卦 / 刷新", self.do_calculate)
        start_menu.addSeparator()
        start_menu.addAction("保存笔记", self.save_note)
        start_menu.addAction("退出", self.close)

        tool_menu = menubar.addMenu("工具")
        tool_menu.addAction("时间起卦", lambda: self.switch_page(0))
        tool_menu.addAction("三数起卦", lambda: self.switch_page(1))
        tool_menu.addAction("端法起卦", lambda: self.switch_page(2))

        data_menu = menubar.addMenu("资料")
        data_menu.addAction("电子书", self.open_help)
        data_menu.addAction("案例导入", self.import_case)

        help_menu = menubar.addMenu("帮助")
        help_menu.addAction("使用指南", self.show_help)
        help_menu.addAction("关于", self.show_about)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")
        self.stack.setAttribute(Qt.WA_TranslucentBackground)
        self.time_widget = TimePredictWidget()
        self.number_widget = NumberPredictWidget()
        self.manual_widget = ManualPredictWidget()

        self.stack.addWidget(self.time_widget)
        self.stack.addWidget(self.number_widget)
        self.stack.addWidget(self.manual_widget)

        central_widget = QWidget()
        central_widget.setStyleSheet("background: transparent;")
        central_widget.setAttribute(Qt.WA_TranslucentBackground)
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.addWidget(self.stack)

        self.setCentralWidget(central_widget)
        self.statusBar().hide()

    def switch_page(self, index):
        self.stack.setCurrentIndex(index)

    def do_calculate(self):
        w = self.stack.currentWidget()
        if hasattr(w, 'calc'):
            w.calc()

    def save_note(self):
        w = self.stack.currentWidget()
        notes_dir = "notes"
        os.makedirs(notes_dir, exist_ok=True)

        question = w.q_input.toPlainText().strip()
        clean = re.sub(r'[<>:"/\\|?*]', '_', question)[:50].strip('. ') or "未命名"
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{clean}_{ts}.json"
        filepath = os.path.join(notes_dir, filename)

        gua_strs = []
        gua_names = []
        if w.gua_info:
            gua_strs = [g for _, g in w.gua_info]
            gua_names = [n for n, _ in w.gua_info]

        data = {
            "app": "观物心易",
            "version": "1.1",
            "type": ["time", "number", "manual"][self.stack.currentIndex()],
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "question": question,
            "duanyu": w.duanyu_input.toPlainText(),
            "inputs": w.get_case_data(),
            "result": {
                "guas": gua_strs,
                "gua_names": gua_names,
                "move": w.current_move,
                "ce": w.ce_input.text(),
                "gui": w.gui_input.text()
            }
        }

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            dialog = SaveSuccessDialog(filepath, self)
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败：{str(e)}")

    def show_help(self):
        dlg = HelpDialog(self)
        dlg.exec_()

    def show_about(self):
        QMessageBox.about(self, "关于", "<h2>观物心易 · 学习笔记</h2>"
                                        "<p>版本：1.1</p>"
                                        "<p>一款基于梅花易数的起卦与学习工具，支持时间起卦、三数起卦、端法起卦，"
                                        "并内置爻辞查询与 PDF 电子书阅读功能。</p>")

    def open_help(self):
        default_pdf = "help.pdf"
        if not os.path.exists(default_pdf):
            default_pdf = None
        self.pdf_win = PDFViewerWindow(default_pdf, self)
        self.pdf_win.show()

    def import_case(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入案例", "notes", "JSON文件 (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            case_type = data.get("type", "time")
            type_map = {"time": 0, "number": 1, "manual": 2}
            idx = type_map.get(case_type, 0)
            self.switch_page(idx)

            w = self.stack.widget(idx)
            if "inputs" in data:
                w.load_case(data["inputs"])
            if "question" in data:
                w.q_input.setPlainText(data["question"])
            if "duanyu" in data:
                w.duanyu_input.setPlainText(data["duanyu"])
            if "result" in data:
                r = data["result"]
                if r.get("guas"):
                    w.current_move = r.get("move", 0)
                    w.gua_info.clear()
                    for i, (name, g) in enumerate(zip(r.get("gua_names", []), r["guas"])):
                        if i < 5:
                            w.gua_labels[i].setText(g[0] + "\n" + g[1])
                            w.name_labels[i].setText(name)
                            w.gua_info.append((name, g))
                    w.ce_input.setText(str(r.get("ce", 0)))
                    w.gui_input.setText(str(r.get("gui", 0)))

        except Exception as e:
            QMessageBox.critical(self, "错误", f"导入失败：{str(e)}")


# ============================================
# 运行
# ============================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
