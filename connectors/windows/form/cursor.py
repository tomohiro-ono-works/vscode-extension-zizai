"""Read the cursor position when the user requests it from the Windows form."""
import sys


def _read_cursor_position():
    if sys.platform != 'win32':
        raise OSError('Windowsのローカルカーネルが必要です。')
    import ctypes
    from ctypes import wintypes

    read_position = ctypes.WinDLL('user32.dll', use_last_error=True).GetCursorPos
    read_position.argtypes = (ctypes.POINTER(wintypes.POINT),)
    read_position.restype = wintypes.BOOL
    point = wintypes.POINT()
    if not read_position(ctypes.byref(point)):
        raise ctypes.WinError(ctypes.get_last_error())
    return point.x, point.y
