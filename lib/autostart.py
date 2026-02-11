from __future__ import annotations

from pathlib import Path
import ctypes
from ctypes import wintypes


def enable_autostart(target_path: Path) -> None:
    link = _startup_link_path()
    link.parent.mkdir(parents=True, exist_ok=True)
    _create_shortcut(link, target_path, target_path.parent)


def disable_autostart() -> None:
    link = _startup_link_path()
    if not link.exists():
        return
    link.unlink()


def _startup_link_path() -> Path:
    return (
        Path.home()
        / "AppData"
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
        / "NikkeWitchcraftStarter.lnk"
    )


def _create_shortcut(link_path: Path, target_path: Path, work_dir: Path) -> None:
    ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    ole32.CoInitialize.argtypes = [ctypes.c_void_p]
    ole32.CoInitialize.restype = ctypes.c_long
    ole32.CoUninitialize.argtypes = []
    ole32.CoUninitialize.restype = None
    ole32.CoCreateInstance.argtypes = [
        ctypes.POINTER(GUID),
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    ole32.CoCreateInstance.restype = ctypes.c_long

    hr = ole32.CoInitialize(None)
    if hr < 0:
        return
    try:
        psl = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(
            ctypes.byref(CLSID_ShellLink),
            None,
            1,
            ctypes.byref(IID_IShellLinkW),
            ctypes.byref(psl),
        )
        if hr < 0 or not psl:
            return
        try:
            link = ctypes.cast(psl, ctypes.POINTER(IShellLinkW))
            link.contents.lpVtbl.contents.SetPath(link, str(target_path))
            link.contents.lpVtbl.contents.SetWorkingDirectory(link, str(work_dir))
            ppf = ctypes.c_void_p()
            hr = link.contents.lpVtbl.contents.QueryInterface(
                link, ctypes.byref(IID_IPersistFile), ctypes.byref(ppf)
            )
            if hr < 0 or not ppf:
                return
            try:
                pf = ctypes.cast(ppf, ctypes.POINTER(IPersistFile))
                pf.contents.lpVtbl.contents.Save(pf, str(link_path), True)
            finally:
                pf.contents.lpVtbl.contents.Release(pf)
        finally:
            link.contents.lpVtbl.contents.Release(link)
    finally:
        ole32.CoUninitialize()


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]


def _guid(s: str) -> GUID:
    import uuid

    u = uuid.UUID(s)
    data4 = (wintypes.BYTE * 8).from_buffer_copy(u.bytes[8:])
    return GUID(u.time_low, u.time_mid, u.time_hi_version, data4)


CLSID_ShellLink = _guid("00021401-0000-0000-C000-000000000046")
IID_IShellLinkW = _guid("000214F9-0000-0000-C000-000000000046")
IID_IPersistFile = _guid("0000010b-0000-0000-C000-000000000046")

class IShellLinkW(ctypes.Structure):
    pass

class IPersistFile(ctypes.Structure):
    pass



class IShellLinkWVtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.POINTER(IShellLinkW), ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))),
        ("AddRef", ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.POINTER(IShellLinkW))),
        ("Release", ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.POINTER(IShellLinkW))),
        ("GetPath", ctypes.c_void_p),
        ("GetIDList", ctypes.c_void_p),
        ("SetIDList", ctypes.c_void_p),
        ("GetDescription", ctypes.c_void_p),
        ("SetDescription", ctypes.c_void_p),
        ("GetWorkingDirectory", ctypes.c_void_p),
        ("SetWorkingDirectory", ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.POINTER(IShellLinkW), wintypes.LPCWSTR)),
        ("GetArguments", ctypes.c_void_p),
        ("SetArguments", ctypes.c_void_p),
        ("GetHotkey", ctypes.c_void_p),
        ("SetHotkey", ctypes.c_void_p),
        ("GetShowCmd", ctypes.c_void_p),
        ("SetShowCmd", ctypes.c_void_p),
        ("GetIconLocation", ctypes.c_void_p),
        ("SetIconLocation", ctypes.c_void_p),
        ("SetRelativePath", ctypes.c_void_p),
        ("Resolve", ctypes.c_void_p),
        ("SetPath", ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.POINTER(IShellLinkW), wintypes.LPCWSTR)),
    ]


class IPersistFileVtbl(ctypes.Structure):
    _fields_ = [
        ("QueryInterface", ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.POINTER(IPersistFile), ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))),
        ("AddRef", ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.POINTER(IPersistFile))),
        ("Release", ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.POINTER(IPersistFile))),
        ("GetClassID", ctypes.c_void_p),
        ("IsDirty", ctypes.c_void_p),
        ("Load", ctypes.c_void_p),
        ("Save", ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.POINTER(IPersistFile), wintypes.LPCWSTR, wintypes.BOOL)),
        ("SaveCompleted", ctypes.c_void_p),
        ("GetCurFile", ctypes.c_void_p),
    ]


IShellLinkW._fields_ = [("lpVtbl", ctypes.POINTER(IShellLinkWVtbl))]
IPersistFile._fields_ = [("lpVtbl", ctypes.POINTER(IPersistFileVtbl))]
