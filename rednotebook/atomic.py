"""Cross-platform atomic filesystem publication helpers."""

import ctypes
import errno
import os
import sys
from pathlib import Path


def rename_directory_no_replace(source, destination):
    """Atomically rename a directory, failing if the destination exists."""
    source = Path(source)
    destination = Path(destination)
    if sys.platform == "win32":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        move_file = kernel32.MoveFileExW
        move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        move_file.restype = ctypes.c_int
        if not move_file(str(source), str(destination), 0):
            error = ctypes.get_last_error()
            if error in (80, 183):
                raise FileExistsError(error, os.strerror(error), str(destination))
            raise OSError(error, f"Atomic directory publish failed: {destination}")
        return

    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        try:
            rename = libc.renamex_np
        except AttributeError as exc:
            raise NotImplementedError(
                "Atomic no-replace directory rename is unavailable"
            ) from exc
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(os.fsencode(source), os.fsencode(destination), 0x00000004)
    elif sys.platform.startswith("linux"):
        try:
            rename = libc.renameat2
        except AttributeError as exc:
            raise NotImplementedError(
                "Atomic no-replace directory rename is unavailable"
            ) from exc
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    else:
        raise NotImplementedError("Atomic no-replace directory rename is unsupported")
    if result == 0:
        return
    error = ctypes.get_errno()
    if error in (errno.EEXIST, errno.ENOTEMPTY):
        raise FileExistsError(error, os.strerror(error), str(destination))
    if error in (errno.ENOSYS, errno.EINVAL):
        raise NotImplementedError("Atomic no-replace directory rename is unavailable")
    raise OSError(error, os.strerror(error), str(destination))
