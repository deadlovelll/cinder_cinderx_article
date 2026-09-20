import ctypes.util
import os
import platform
import sys

from bench.harness.system.constants import ADDR_NO_RANDOMIZE, _REEXEC_GUARD


def aslr_disable_and_reexec(argv: list[str] | None = None) -> None:
    if os.environ.get(_REEXEC_GUARD) == "1":
        return
    if platform.system() != "Linux":
        os.environ[_REEXEC_GUARD] = "unsupported"
        return
    libc_name = ctypes.util.find_library("c")
    if not libc_name:
        os.environ[_REEXEC_GUARD] = "no_libc"
        return
    try:
        libc = ctypes.CDLL(libc_name, use_errno=True)
        libc.personality.argtypes = [ctypes.c_ulong]
        libc.personality.restype = ctypes.c_int
        if libc.personality(ADDR_NO_RANDOMIZE) < 0:
            os.environ[_REEXEC_GUARD] = f"errno={ctypes.get_errno()}"
            return
    except Exception as exc:
        os.environ[_REEXEC_GUARD] = f"failed:{type(exc).__name__}"
        return
    os.environ[_REEXEC_GUARD] = "1"
    args = argv if argv is not None else [sys.executable, *sys.argv]
    os.execv(args[0], args)
