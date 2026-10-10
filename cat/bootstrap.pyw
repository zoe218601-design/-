"""无控制台入口；只记录启动错误，不记录键盘输入。"""
import ctypes
import os
from pathlib import Path
import runpy
import sys
import traceback

folder = Path(__file__).resolve().parent
os.chdir(folder)
sys.path.insert(0, str(folder))
try:
    runpy.run_path(str(folder / 'cat.py'), run_name='__main__')
except Exception:
    error_folder = Path(os.environ.get('LOCALAPPDATA', str(folder))) / 'StrawberryDesktopCat'
    error_file = error_folder / 'startup_error.txt'
    try:
        error_folder.mkdir(parents=True, exist_ok=True)
        error_file.write_text(traceback.format_exc(), encoding='utf-8')
        message = f'小猫启动失败。请先运行 install.bat，或运行 start.bat 查看报错。\n\n错误详情：{error_file}'
    except OSError:
        message = '小猫启动失败。请运行 start.bat 查看报错。'
    if sys.platform == 'win32':
        ctypes.windll.user32.MessageBoxW(None, message, '草莓桌面猫', 0x10)
    raise SystemExit(1)
