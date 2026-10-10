"""草莓冰淇淋桌面猫：Windows 按键轮询 + Qt 绘画，无按键日志。"""
import ctypes
import json
import socket
import math
import random
import sys
import time
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF, QLockFile, QStandardPaths, QSettings
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QPainterPath, QFont, QCursor, QPolygonF, QPixmap, QRegion, QTransform, QIcon
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon, QMessageBox
from PySide6.QtCore import QPointF

# 每项是 (Windows 实体按键编号, 键帽文字, 相对宽度)。可自行修改。
ROWS = [
    [(0x1B, 'Esc', 1.4)] + [(48+i, str(i), 1) for i in range(1,10)] + [(48,'0',1),(8,'←',1.4)],
    [(9,'Tab',1.4)] + [(ord(c),c,1) for c in 'QWERTYUIOP'],
    [(20,'Caps',1.6)] + [(ord(c),c,1) for c in 'ASDFGHJKL'] + [(13,'Enter',1.8)],
    [(16,'Shift',1.8)] + [(ord(c),c,1) for c in 'ZXCVBNM'] + [(38,'↑',1),(46,'Del',1.2)],
    [(17,'Ctrl',1.4),(18,'Alt',1.2),(32,'Space',5),(37,'←',1),(40,'↓',1),(39,'→',1)],
]
EXTRA_KEYS = {0xBA,0xBB,0xBC,0xBD,0xBE,0xBF,0xC0,0xDB,0xDC,0xDD,0xDE,0x5B,0x5C,*range(96,112),*range(112,124)}
ALL_KEYS = {v for row in ROWS for v,_,_ in row} | EXTRA_KEYS

class Cat(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('草莓冰淇淋猫')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.resize(320, 260)
        sheet = QPixmap(str(Path(__file__).with_name('cat_sprites.png')))
        if sheet.isNull():
            raise RuntimeError('Missing cat_sprites.png: please extract the entire ZIP first.')
        self.frames = []
        for row in range(2):
            for col in range(3):
                frame = sheet.copy(col*sheet.width()//3,row*sheet.height()//2,sheet.width()//3,sheet.height()//2)
                if row == 1 and col == 1:
                    frame = frame.transformed(QTransform().scale(-1,1))
                bounds = QRegion(frame.mask()).boundingRect()
                self.frames.append(frame.copy(bounds) if not bounds.isEmpty() else frame)
        self.sprite_scale = min(212/max(f.height() for f in self.frames),260/max(f.width() for f in self.frames))
        self.fish_point = None
        self.fish_seen = -100.0
        self.fish_visible = False
        self.fish_address = None
        self.fish_session = None
        self.fish_sequence = 0
        self.eating_until = 0.0
        self.fish_enabled = True
        self.fish_socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.fish_socket.bind(('127.0.0.1',49673))
        self.fish_socket.setblocking(False)
        atlas=QPixmap(str(Path(__file__).with_name('cat_actions.png')))
        if atlas.isNull():raise RuntimeError('Missing cat_actions.png. Please extract all files.')
        self.actions=[]
        for row in range(3):
            for col in range(4):
                frame=atlas.copy(col*atlas.width()//4,row*atlas.height()//3,atlas.width()//4,atlas.height()//3)
                bounds=QRegion(frame.mask()).boundingRect()
                self.actions.append(frame.copy(bounds) if not bounds.isEmpty() else frame)
        self.action_scale=min(210/max(f.height() for f in self.actions),260/max(f.width() for f in self.actions))
        self.action=None
        self.action_start=0.0
        self.action_until=0.0
        self.action_origin=None
        self.action_destination=None
        self.last_jump=-100.0
        self.last_pounce=-100.0
        self.next_idle=time.monotonic()+3
        self.idle_index=0
        self.pointer_mode='normal'
        self.stroking=False
        self.press_global=None
        self.press_local=None
        self.did_drag=False
        self.last_stroke=-100.0
        self.hiss_sound=True
        self.last_hiss_sound=-100.0
        self.t = 0
        self.settings=QSettings('DesktopToys','StrawberryCat')
        self.mode=self.settings.value('mode','auto')
        if self.mode not in ('auto','follow','sleep'):self.mode='auto'
        self.state = 'idle'
        self.drag = None
        self.pressed = set()
        self.last_type = -100.0
        self.last_activity = time.monotonic()
        self.next_walk = time.monotonic() + 12
        self.target = None
        self.face = 1
        self.keyboard_enabled = True
        self.previous_cursor = QCursor.pos()
        self.user32 = ctypes.WinDLL('user32', use_last_error=True) if sys.platform == 'win32' else None
        if self.user32:
            self.user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
            self.user32.GetAsyncKeyState.restype = ctypes.c_short
        area = QApplication.primaryScreen().availableGeometry()
        self.move(area.right()-self.width()-35, area.bottom()-self.height()-25)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)
        self.tray=None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray=QSystemTrayIcon(QIcon(self.actions[4]),self)
            tray_menu=QMenu(self)
            tray_menu.addAction('活动模式',lambda:self.set_mode('auto'))
            tray_menu.addAction('睡觉模式（保持睡觉）',lambda:self.set_mode('sleep'))
            tray_menu.addSeparator()
            tray_menu.addAction('叫回小猫',self.show_pet)
            tray_menu.addAction('退出小猫',self.close)
            self.tray.setContextMenu(tray_menu)
            self.tray.setToolTip('草莓猫 · 右键可以叫回或退出')
            self.tray.show()

    def show_pet(self):
        screen=QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        a=screen.availableGeometry()
        self.move(a.center()-QPoint(160,130))
        self.action=None;self.target=None
        self.last_activity=time.monotonic()
        self.show();self.raise_()

    def bounds(self):
        screen = QApplication.screenAt(self.pos() + QPoint(160,130)) or QApplication.primaryScreen()
        return screen.availableGeometry()

    def clamp(self, point):
        a = self.bounds()
        return QPoint(max(a.left(),min(point.x(),a.right()-self.width()+1)), max(a.top(),min(point.y(),a.bottom()-self.height()+1)))

    def read_fish(self, now):
        for _ in range(48):
            try:
                data,address = self.fish_socket.recvfrom(1024)
            except BlockingIOError:
                break
            except OSError:
                break
            if address[0] != '127.0.0.1': continue
            try:
                message = json.loads(data)
            except (ValueError,UnicodeDecodeError): continue
            if not isinstance(message,dict): continue
            if message.get('kind')=='show':
                self.show_pet()
                self.fish_socket.sendto(b'{"kind":"shown"}',address)
                continue
            if message.get('kind') != 'fish': continue
            x,y = message.get('x'),message.get('y')
            if type(x) != int or type(y) != int or abs(x)>100000 or abs(y)>100000: continue
            session,sequence = message.get('session'),message.get('sequence')
            if not isinstance(session,str) or len(session)!=16 or type(sequence)!=int: continue
            self.fish_point = QPoint(x+13,y)
            self.fish_seen = now
            self.fish_visible = message.get('visible') is True
            self.fish_address = address
            self.fish_session = session
            self.fish_sequence = sequence
            self.pointer_mode = message.get('cursor_mode','fish')

    def eat_fish(self, now):
        self.eating_until = now+1.0
        self.target = None
        self.state = 'eat'
        self.fish_visible = False
        reply = {'kind':'eat','session':self.fish_session,'sequence':self.fish_sequence}
        try:
            self.fish_socket.sendto(json.dumps(reply).encode(),self.fish_address)
        except OSError: pass

    def closeEvent(self,event):
        self.timer.stop()
        self.fish_socket.close()
        if self.tray:self.tray.hide()
        event.accept()
        QApplication.instance().quit()

    def start_action(self,name,duration,now=None,destination=None):
        now=time.monotonic() if now is None else now
        self.action=name
        self.action_start=now
        self.action_until=now+duration
        self.action_origin=self.pos()
        self.action_destination=destination
        self.state=name
        self.target=None

    def fish_active(self,now):
        return self.fish_enabled and self.fish_visible and now-self.fish_seen<.8 and self.mode!='sleep'

    def reached_fish(self):
        if self.fish_point is None:return False
        mouth=self.pos()+QPoint(160,130)
        delta=self.fish_point-mouth
        target=self.clamp(self.fish_point-QPoint(160,130))
        at_edge=target!=self.fish_point-QPoint(160,130)
        return math.hypot(delta.x(),delta.y())<27 or (at_edge and (self.pos()-target).manhattanLength()<8)

    def tick(self):
        self.t+=1
        now=time.monotonic()
        cursor=QCursor.pos()
        self.read_fish(now)
        if self.mode=='sleep':
            self.state='sleep'
            self.action=None
            self.target=None
            self.pressed.clear()
            self.update()
            return
        active=self.fish_active(now)
        held={key for key in ALL_KEYS if self.user32 and self.keyboard_enabled and self.user32.GetAsyncKeyState(key)&0x8000}
        if held:
            self.last_type=now
            self.last_activity=now
        self.pressed=held
        mouse_moved=(cursor-self.previous_cursor).manhattanLength()>3
        self.previous_cursor=cursor
        if self.action and now>=self.action_until:
            if self.action_destination is not None:self.move(self.action_destination)
            was_motion=self.action in ('jump','pounce')
            self.action=None
            if was_motion and active and self.reached_fish():
                self.eat_fish(now)
        if self.drag is not None and not self.stroking:
            self.state='idle'
            self.action=None
        elif self.action:
            self.state=self.action
            if self.action_destination is not None:
                progress=min(1,max(0,(now-self.action_start)/(self.action_until-self.action_start)))
                delta=self.action_destination-self.action_origin
                self.move(self.action_origin+QPoint(round(delta.x()*progress),round(delta.y()*progress)))
        elif now<self.eating_until:
            self.state='eat'
        elif now-self.last_type<2.5 and self.keyboard_enabled:
            self.state='typing'
        elif active:
            self.last_activity=now
            self.target=self.clamp(self.fish_point-QPoint(160,130))
            delta=self.target-self.pos()
            distance=math.hypot(delta.x(),delta.y())
            if abs(delta.x())>2:self.face=1 if delta.x()>0 else -1
            if self.reached_fish():
                self.eat_fish(now)
            elif 130<distance<260 and now-self.last_jump>4:
                self.last_jump=now
                self.start_action('jump',.6,now,self.target)
            elif distance<95 and now-self.last_pounce>1.2:
                self.last_pounce=now
                self.start_action('pounce',.42,now,self.target)
            else:
                self.state='run'
                self.move_toward(self.target,11 if distance>260 else 7)
        elif self.mode=='follow':
            self.target=self.clamp(cursor+QPoint(25,-120))
            self.state='run'
            self.move_toward(self.target,6)
        else:
            hand=self.pointer_mode=='hand' and now-self.fish_seen<.8
            if hand:
                self.target=None
            if not hand and mouse_moved and (cursor-(self.pos()+QPoint(160,130))).manhattanLength()<380 and not self.geometry().contains(cursor):
                self.target=self.clamp(cursor+QPoint(25,-120))
                self.last_activity=now
            if not hand and now>self.next_walk:
                self.target=self.clamp(self.pos()+QPoint(random.randint(-180,180),random.randint(-70,70)))
                self.next_walk=now+random.uniform(10,18)
            if self.target:
                self.state='walk'
                self.move_toward(self.target,3)
            else:
                self.state='idle'
                if now>self.next_idle:
                    name=['lick_paw','groom','scratch'][self.idle_index%3]
                    self.idle_index+=1
                    self.next_idle=now+random.uniform(5,8)
                    self.start_action(name,2.2,now)
        if self.fish_active(now) and self.state in ('run','walk','idle') and self.drag is None and self.reached_fish():
            self.eat_fish(now)
        self.update()

    def move_toward(self,target,speed):
        delta=target-self.pos()
        distance=math.hypot(delta.x(),delta.y())
        if distance<speed:
            self.move(target)
            self.target=None
            self.state='idle'
            return
        if abs(delta.x())>2:self.face=1 if delta.x()>0 else -1
        self.move(self.clamp(self.pos()+QPoint(round(delta.x()/distance*speed),round(delta.y()/distance*speed))))

    def pet_region(self,point):
        # 在静止坐姿的身体范围内区分部位。
        if point.x()>202 and point.y()>164:return 'hiss_rear'
        if 124<point.x()<197 and point.y()>163:return 'hiss_belly'
        return 'pet'

    def pet_at(self,point):
        if self.mode=='sleep':return
        now=time.monotonic()
        self.last_activity=now
        self.last_type=-100
        region=self.pet_region(point)
        self.start_action(region,1.8,now)
        if region.startswith('hiss_') and self.hiss_sound and now-self.last_hiss_sound>.8 and sys.platform=='win32':
            self.last_hiss_sound=now
            try:
                import winsound
                winsound.PlaySound(str(Path(__file__).with_name('hiss.wav')),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
            except RuntimeError:pass
        self.next_idle=now+5
        self.last_stroke=now

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            now=time.monotonic()
            self.press_global=event.globalPosition().toPoint()
            self.press_local=event.position().toPoint()
            self.drag=self.press_global-self.pos()
            self.did_drag=False
            self.stroking=self.mode!='sleep' and self.pointer_mode=='hand' and now-self.fish_seen<.8 and not bool(event.modifiers()&Qt.KeyboardModifier.AltModifier)
            self.target=None
            if self.stroking:self.pet_at(self.press_local)

    def mouseMoveEvent(self,event):
        if self.drag is not None:
            now=time.monotonic()
            if self.stroking:
                if now-self.last_stroke>.55:self.pet_at(event.position().toPoint())
            elif (event.globalPosition().toPoint()-self.press_global).manhattanLength()>5:
                self.did_drag=True
                self.move(self.clamp(event.globalPosition().toPoint()-self.drag))
                self.last_activity=now

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.drag is not None:
            if not self.did_drag and not self.stroking and self.pointer_mode=='hand':self.pet_at(event.position().toPoint())
            self.drag=None
            self.stroking=False
            self.last_activity=time.monotonic()

    def mouseDoubleClickEvent(self, event):
        if self.mode=='sleep':return
        self.set_mode('auto' if self.mode=='follow' else 'follow')

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        for label, mode in [('活动模式','auto'),('活动模式：追鼠标','follow'),('睡觉模式（保持睡觉）','sleep')]:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self.mode == mode)
            action.triggered.connect(lambda checked=False,m=mode: self.set_mode(m))
        menu.addSeparator()
        fish_action = menu.addAction('追逐小鱼干')
        fish_action.setCheckable(True)
        fish_action.setChecked(self.fish_enabled)
        fish_action.triggered.connect(lambda checked: setattr(self,'fish_enabled',checked))
        action = menu.addAction('打字同步小键盘')
        action.setCheckable(True)
        action.setChecked(self.keyboard_enabled)
        action.triggered.connect(self.set_keyboard)
        menu.addSeparator()
        sound=menu.addAction('哈气声音');sound.setCheckable(True);sound.setChecked(self.hiss_sound)
        sound.triggered.connect(lambda checked:setattr(self,'hiss_sound',checked))
        menu.addAction('退出小猫', self.close)
        menu.exec(event.globalPos())

    def set_mode(self, mode):
        self.mode = mode
        self.action = None
        self.target = None
        self.last_type = -100
        self.eating_until=0
        self.pressed.clear()
        self.state='sleep' if mode=='sleep' else 'idle'
        self.last_activity=time.monotonic()
        self.next_idle=self.last_activity+3
        self.settings.setValue('mode',mode)
        self.settings.sync()
        self.update()

    def set_keyboard(self, enabled):
        self.keyboard_enabled = enabled
        self.pressed.clear()
        self.last_type = -100

    def paintEvent(self, event):
        now=time.monotonic()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        typing = self.state == 'typing'
        walking = self.state in ('walk','run','jump','pounce')
        sleeping = self.state == 'sleep'
        if self.state in ('typing','idle','eat'):
            sprite=self.frames[0 if self.state=='typing' else [0,1,0,2][self.t//9%4]]
            scale=self.sprite_scale
        else:
            if self.state=='sleep':index=11
            elif self.state in ('walk','run'):index=self.t//(4 if self.state=='run' else 7)%2
            elif self.state=='jump':index=2
            elif self.state=='pounce':index=3
            elif self.state=='lick_paw':index=5 if self.t%16<12 else 4
            elif self.state=='groom':index=6
            elif self.state=='scratch':index=7
            elif self.state=='pet':index=8
            elif self.state=='hiss_belly':index=9
            elif self.state=='hiss_rear':index=10
            else:index=4
            sprite=self.actions[index]
            scale=self.action_scale
        bob=math.sin(self.t*.5)*2 if walking else math.sin(self.t*.09)*1.2
        if self.state in ('jump','pounce') and self.action:
            progress=max(0,min(1,(now-self.action_start)/(self.action_until-self.action_start)))
            bob=-math.sin(math.pi*progress)*(30 if self.state=='jump' else 12)
        elif self.state=='groom':bob+=math.sin(self.t*.45)*2
        elif self.state=='scratch':bob+=math.sin(self.t*.85)*2
        elif self.state.startswith('hiss_'):bob+=math.sin(self.t*1.2)*1.8
        p.save()
        # 第一行运动素材全部面向右；仅向左运动时镜像。
        if walking and self.face<0:
            p.translate(self.width(),0)
            p.scale(-1,1)
        width=sprite.width()*scale
        height=sprite.height()*scale
        p.drawPixmap(QRectF((320-width)/2,218-height+bob,width,height),sprite,QRectF(sprite.rect()))
        p.restore()
        if self.state.startswith('hiss_'):
            p.setPen(QColor('#c85d67'));p.setFont(QFont('Microsoft YaHei',11,QFont.Weight.Bold))
            p.drawText(238,78,'哈——')
        elif self.state=='pet':
            p.setPen(QColor('#c28b9f'));p.setFont(QFont('Microsoft YaHei',9))
            p.drawText(238,104,'呼噜~')
        if self.state == 'eat':
            # 嘴巴咀嚼及满足的小爱心。
            p.setPen(QPen(QColor('#25231f'),2))
            p.setBrush(QColor('#edb3a6'))
            p.drawEllipse(QRectF(154,128,12,5+(self.t%6)*.8))
            p.setPen(QColor('#cc819d'))
            p.setFont(QFont('Segoe UI',14,QFont.Weight.Bold))
            p.drawText(241,103-int(math.sin(self.t*.2)*4),'♥')
        if sleeping:
            p.setPen(QColor('#9a8bad'))
            p.setFont(QFont('Segoe UI',15,QFont.Weight.Bold))
            p.drawText(236,100-int(math.sin(self.t*.06)*5),'Z z')
        if typing:
            self.paint_keyboard(p)
            # 爪子伸向猫咪面前的按键面；只在敲击时交替下落。
            side = self.t//3 % 2 if self.pressed else 0
            for i,x in enumerate([118,182]):
                dy = 4 if self.pressed and side==i else 0
                p.setPen(QPen(QColor('#191916'),2.5))
                p.setBrush(QColor('#fffcec'))
                p.drawRoundedRect(QRectF(x,197+dy,26,18),9,9)
                for offset in [8,16]:
                    p.drawLine(QPointF(x+offset,208+dy),QPointF(x+offset,213+dy))
        p.end()

    def paint_keyboard(self, p):
        # 键盘面朝猫咪：整个键位平面旋转 180 度。
        # 猫咪在画面上方，因此空格靠猫，数字行靠观众。
        p.setPen(QPen(QColor('#665664'),2.5))
        p.setBrush(QColor('#d1c5d7'))
        p.drawRoundedRect(QRectF(34,224,252,25),7,7)
        p.setBrush(QColor('#eae0ef'))
        p.drawRoundedRect(QRectF(34,199,252,41),7,7)
        p.save()
        p.translate(320,438)
        p.rotate(180)
        for r,row in enumerate(ROWS):
            unit=236/sum(width for _,_,width in row)
            x=42.0
            for vk,label,width in row:
                rect=QRectF(x,202+r*6.5,width*unit-2,5.8)
                p.setPen(QPen(QColor('#b4a5bb'),.5))
                p.setBrush(QColor('#f5b954' if vk in self.pressed else '#fffafc'))
                p.drawRoundedRect(rect,1.2,1.2)
                p.setPen(QColor('#78637a'))
                p.setFont(QFont('Segoe UI',4))
                p.drawText(rect,Qt.AlignmentFlag.AlignCenter,label)
                x+=width*unit
        p.restore()
        # 观众看到的是键盘背侧的实体外壳。
        p.setPen(QPen(QColor('#a997b1'),1))
        p.drawLine(QPointF(45,244),QPointF(275,244))
        if self.pressed & EXTRA_KEYS:
            p.setPen(QColor('#c58c3f'));p.setFont(QFont('Segoe UI',9))
            p.drawText(270,246,'•')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # 避免自动启动后又双击，出现多只猫。
    lock_folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation))
    instance_lock = QLockFile(str(lock_folder / 'StrawberryDesktopCat.lock'))
    if not instance_lock.tryLock(100):
        request=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        request.settimeout(.5)
        try:
            request.sendto(b'{"kind":"show"}',('127.0.0.1',49673))
            reply,_=request.recvfrom(256)
            if reply!=b'{"kind":"shown"}':raise OSError('No show response')
        except OSError:
            QMessageBox.information(None,'小猫已在运行','另一个版本的小猫还在后台运行。请先退出旧版小猫，再启动新版。')
        finally:request.close()
        sys.exit(0)
    cat = Cat()
    cat.show()
    sys.exit(app.exec())
