"""主程序停止后恢复 Windows 鼠标配置，避免指针一直残留。"""
import ctypes
from ctypes import wintypes
import sys
if sys.platform=='win32':
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenProcess.restype=wintypes.HANDLE
    k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    k.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=k.OpenProcess(0x00100000,False,int(sys.argv[1]))
    if handle:
        k.WaitForSingleObject(handle,0xFFFFFFFF);k.CloseHandle(handle)
    ctypes.windll.user32.SystemParametersInfoW(0x0057,0,None,0)
