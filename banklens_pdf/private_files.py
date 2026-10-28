"""Create private output files without inheriting a permissive Windows ACL."""
import os
from pathlib import Path
import secrets


def create_private(path):
    """Exclusively create a private file and return a binary file descriptor.

    Windows ACLs are set at creation, before any document data is written.
    Owner Rights, SYSTEM and Administrators receive full access. On POSIX,
    creation uses mode 0600. Existing files are never opened or replaced.
    """
    path = Path(path)
    if os.name != "nt":
        return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)

    import ctypes
    from ctypes import wintypes
    import msvcrt

    class SecurityAttributes(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("descriptor", wintypes.LPVOID),
                    ("inherit_handle", wintypes.BOOL)]

    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.LPVOID), ctypes.POINTER(wintypes.DWORD)]
    convert.restype = wintypes.BOOL
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.POINTER(SecurityAttributes), wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    security_info = advapi.GetSecurityInfo
    security_info.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                              ctypes.POINTER(wintypes.LPVOID), ctypes.POINTER(wintypes.LPVOID),
                              ctypes.POINTER(wintypes.LPVOID), ctypes.POINTER(wintypes.LPVOID),
                              ctypes.POINTER(wintypes.LPVOID)]
    security_info.restype = wintypes.DWORD
    get_control = advapi.GetSecurityDescriptorControl
    get_control.argtypes = [wintypes.LPVOID, ctypes.POINTER(wintypes.WORD), ctypes.POINTER(wintypes.DWORD)]
    get_control.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel.LocalFree.restype = wintypes.HLOCAL
    descriptor = wintypes.LPVOID()
    if not convert("D:P(A;;FA;;;OW)(A;;FA;;;SY)(A;;FA;;;BA)", 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
        handle = create(str(path), 0x40000000, 0x1 | 0x2 | 0x4, ctypes.byref(attributes), 1, 0x80, None)
        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            actual = wintypes.LPVOID()
            dacl = wintypes.LPVOID()
            status = security_info(handle, 1, 4, None, None, ctypes.byref(dacl), None, ctypes.byref(actual))
            if status:
                raise ctypes.WinError(status)
            try:
                control, revision = wintypes.WORD(), wintypes.DWORD()
                if not get_control(actual, ctypes.byref(control), ctypes.byref(revision)):
                    raise ctypes.WinError(ctypes.get_last_error())
                if not dacl.value or not (control.value & 0x1000):
                    raise OSError("private_acl_unavailable")
            finally:
                kernel.LocalFree(actual)
            return msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
        except BaseException:
            kernel.CloseHandle(handle)
            path.unlink(missing_ok=True)
            raise
    finally:
        kernel.LocalFree(descriptor)


def private_temporary(directory, prefix):
    """Create an unpredictable, private temporary file in an existing directory."""
    for _ in range(100):
        path = Path(directory) / (prefix + secrets.token_hex(16))
        try:
            return create_private(path), path
        except FileExistsError:
            continue
    raise FileExistsError("private_temporary_name_unavailable")
