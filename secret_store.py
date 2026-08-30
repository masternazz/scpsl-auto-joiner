"""Small Windows DPAPI wrapper for local companion tokens."""
import base64
import ctypes
import ctypes.wintypes
import os


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data):
    raw = bytes(data)
    buffer = ctypes.create_string_buffer(raw)
    return DATA_BLOB(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def protect(value):
    if os.name != "nt":
        raise RuntimeError("DPAPI is available only on Windows")
    crypt = ctypes.windll.crypt32
    source, keepalive = _blob(str(value).encode("utf-8"))
    target = DATA_BLOB()
    if not crypt.CryptProtectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target)):
        raise OSError(ctypes.get_last_error(), "CryptProtectData failed")
    try:
        return base64.b64encode(ctypes.string_at(target.pbData, target.cbData)).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)


def unprotect(value):
    if os.name != "nt":
        raise RuntimeError("DPAPI is available only on Windows")
    raw = base64.b64decode(str(value), validate=True)
    source, keepalive = _blob(raw)
    target = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target)):
        raise OSError(ctypes.get_last_error(), "CryptUnprotectData failed")
    try:
        return ctypes.string_at(target.pbData, target.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)
