"""小鱼干鼠标：32px 原生 Windows 光标，和本机桌面猫互动。"""
import atexit
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import sys
import time
from PySide6.QtCore import Qt, QTimer, QBuffer, QIODevice, QRectF, QPointF, QLockFile, QStandardPaths
from PySide6.QtGui import QImage, QPainter, QPen, QColor, QPainterPath, QCursor, QIcon, QPixmap, QActionGroup
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QMessageBox

PORT = 49673
CURSOR_IDS = [32512,32513,32514,32515,32516,32642,32643,32644,32645,32646,32648,32649,32650,32651]

def fish_image():
    image=QImage(32,32,QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p=QPainter(image);p.setRenderHint(QPainter.RenderHint.Antialiasing)
    outline=QColor('#785438')
    p.setPen(QPen(outline,1.6,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap));p.setBrush(QColor('#edbf78'))
    body=QPainterPath(QPointF(3,16))
    body.cubicTo(8,6,19,6,23,13)
    body.lineTo(29,9);body.lineTo(28,16);body.lineTo(30,23);body.lineTo(23,20)
    body.cubicTo(16,27,7,24,3,16);p.drawPath(body)
    p.setPen(QPen(QColor('#b67f48'),1.1));p.drawLine(QPointF(11,16),QPointF(22,16))
    for x in [13,17,21]:
        p.drawLine(QPointF(x,16),QPointF(x-2,12));p.drawLine(QPointF(x,16),QPointF(x-2,20))
    p.setPen(Qt.PenStyle.NoPen);p.setBrush(outline);p.drawEllipse(QRectF(7,13,2.8,2.8));p.end()
    return image

def hand_image():
    image=QImage(32,32,QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p=QPainter(image);p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor('#93634c'),1.3,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap));p.setBrush(QColor('#ffe0c6'))
    hand=QPainterPath(QPointF(11,28))
    hand.lineTo(5,19);hand.cubicTo(2,14,5,12,9,16)
    hand.lineTo(10,17);hand.lineTo(10,5);hand.cubicTo(10,1,15,1,15,5)
    hand.lineTo(15,12);hand.cubicTo(15,8,20,8,20,12)
    hand.cubicTo(21,9,25,10,25,14);hand.cubicTo(28,12,30,15,29,20)
    hand.lineTo(27,28);hand.closeSubpath();p.drawPath(hand)
    for x in [19,24]:p.drawLine(QPointF(x,13),QPointF(x,19))
    p.setPen(QPen(QColor('#edb5a6'),1));p.drawLine(QPointF(14,22),QPointF(23,22));p.end()
    return image

def write_cursor(path,mode='fish'):
    image=hand_image() if mode=='hand' else fish_image()
    pixels=bytearray()
    mask=bytearray()
    # 经典32位CUR位图，兼容Windows原生LoadImage；像素和遮罩均从底行开始。
    for y in range(31,-1,-1):
        bits=0
        for x in range(32):
            c=image.pixelColor(x,y)
            pixels.extend((c.blue(),c.green(),c.red(),c.alpha()))
            if c.alpha()==0:bits|=1<<(31-x)
        mask.extend(bits.to_bytes(4,'big'))
    bitmap=struct.pack('<IiiHHIIiiII',40,32,64,1,32,0,len(pixels),0,0,0,0)+pixels+mask
    # 实际点击热点位于鱼嘴 (3,16)。
    hx,hy=(12,3) if mode=='hand' else (3,16)
    path.write_bytes(struct.pack('<HHH',0,2,1)+struct.pack('<BBBBHHII',32,32,0,0,hx,hy,len(bitmap),22)+bitmap)

def restore_cursors():
    if sys.platform=='win32':
        ctypes.windll.user32.SystemParametersInfoW(0x0057,0,None,0)

class WindowsCursor:
    def __init__(self,paths):
        if sys.platform!='win32':raise RuntimeError('小鱼干鼠标需要 Windows。')
        self.paths=paths
        self.mode='fish'
        self.user32=ctypes.WinDLL('user32',use_last_error=True)
        self.user32.LoadImageW.argtypes=[wintypes.HINSTANCE,wintypes.LPCWSTR,wintypes.UINT,ctypes.c_int,ctypes.c_int,wintypes.UINT]
        self.user32.LoadImageW.restype=wintypes.HANDLE
        self.user32.SetSystemCursor.argtypes=[wintypes.HANDLE,wintypes.DWORD]
        self.user32.SetSystemCursor.restype=wintypes.BOOL
        self.user32.DestroyCursor.argtypes=[wintypes.HANDLE]
    def apply(self):
        try:
            for cursor_id in CURSOR_IDS:
                handle=self.user32.LoadImageW(None,str(self.paths[self.mode]),2,32,32,0x0010)
                if not handle:raise ctypes.WinError(ctypes.get_last_error())
                if not self.user32.SetSystemCursor(handle,cursor_id):
                    self.user32.DestroyCursor(handle)
                    raise ctypes.WinError(ctypes.get_last_error())
        except Exception:
            restore_cursors();raise
    def restore(self):restore_cursors()

class Fish:
    def __init__(self,app,manager):
        self.app=app;self.manager=manager
        self.enabled=True;self.hidden_until=0.0;self.mode='fish'
        self.session=secrets.token_hex(8)
        self.sequence=0;self.eaten=0;self.cleaned=False
        self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);self.sock.bind(('127.0.0.1',0));self.sock.setblocking(False)
        self.tray=QSystemTrayIcon(QIcon(QPixmap.fromImage(fish_image())),app)
        self.menu=QMenu()
        action=self.menu.addAction('启用玩具指针');action.setCheckable(True);action.setChecked(True);action.triggered.connect(self.set_enabled)
        self.cursor_group=QActionGroup(self.menu)
        for label,mode in [('鱼干：让猫追着吃','fish'),('小手：摸摸／挠痒痒','hand')]:
            choice=self.menu.addAction(label);choice.setCheckable(True);choice.setChecked(mode=='fish')
            self.cursor_group.addAction(choice)
            choice.triggered.connect(lambda checked=False,m=mode:self.set_mode(m))
        self.menu.addSeparator();self.menu.addAction('恢复原指针并退出',app.quit)
        self.tray.setContextMenu(self.menu);self.tray.setToolTip('小鱼干指针 · 右键可恢复原指针');self.tray.show()
        self.manager.apply()
        self.timer=QTimer();self.timer.timeout.connect(self.tick);self.timer.start(25)
        self.app.aboutToQuit.connect(self.cleanup)
        atexit.register(self.cleanup)
    def set_mode(self,mode):
        self.mode=mode;self.manager.mode=mode;self.sequence+=1;self.hidden_until=0
        self.tray.setIcon(QIcon(QPixmap.fromImage(hand_image() if mode=='hand' else fish_image())))
        self.tray.setToolTip('小手：摸猫／挠痒' if mode=='hand' else '小鱼干：猫咪追着吃')
        if self.enabled:self.manager.apply()

    def set_enabled(self,value):
        self.enabled=value;self.hidden_until=0
        if value:self.manager.apply()
        else:self.manager.restore()
    def tick(self):
        now=time.monotonic()
        for _ in range(32):
            try:data,address=self.sock.recvfrom(1024)
            except BlockingIOError:break
            except OSError:return
            if address!=('127.0.0.1',PORT):continue
            try:message=json.loads(data)
            except (ValueError,UnicodeDecodeError):continue
            if not isinstance(message,dict):continue
            if (message.get('kind')=='eat' and message.get('session')==self.session and message.get('sequence')==self.sequence and self.enabled and self.mode=='fish' and not self.hidden_until):
                self.eaten+=1;self.sequence+=1;self.hidden_until=now+1.2
                self.manager.restore()
                self.tray.setToolTip(f'小猫吃了 {self.eaten} 条鱼 · 右键退出')
        if self.hidden_until and now>=self.hidden_until:
            self.hidden_until=0
            if self.enabled:self.manager.apply()
        cursor=QCursor.pos()
        payload={'kind':'fish','session':self.session,'sequence':self.sequence,'x':cursor.x(),'y':cursor.y(),'visible':self.enabled and self.mode=='fish' and not bool(self.hidden_until),'cursor_mode':self.mode if self.enabled else 'normal'}
        try:self.sock.sendto(json.dumps(payload).encode(),('127.0.0.1',PORT))
        except OSError:pass
    def cleanup(self):
        if self.cleaned:return
        self.cleaned=True;self.timer.stop();self.manager.restore();self.tray.hide();self.sock.close()

if __name__=='__main__':
    app=QApplication(sys.argv);app.setQuitOnLastWindowClosed(False)
    lock=QLockFile(str(Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation))/'MouseDryFish.lock'))
    if not lock.tryLock(100):sys.exit(0)
    if sys.platform!='win32':
        QMessageBox.information(None,'小鱼干','这个鼠标指针版本需要 Windows。');sys.exit(1)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.warning(None,'小鱼干','无法显示退出入口，尚未修改鼠标指针。');sys.exit(1)
    folder=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'MouseDryFish'
    folder.mkdir(parents=True,exist_ok=True)
    paths={'fish':folder/'fish.cur','hand':folder/'hand.cur'}
    for mode,path in paths.items():write_cursor(path,mode)
    # 独立守护程序：即使鱼干程序异常退出，也恢复系统配置的原指针。
    executable=Path(sys.executable)
    pythonw=executable.with_name('pythonw.exe')
    if pythonw.exists():executable=pythonw
    watchdog=subprocess.Popen([str(executable),str(Path(__file__).with_name('restore_watchdog.pyw')),str(os.getpid())],creationflags=0x08000000)
    try:
        pet=Fish(app,WindowsCursor(paths))
        sys.exit(app.exec())
    finally:
        restore_cursors()
