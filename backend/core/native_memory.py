"""Return unused glibc pages after completed background maintenance."""

import ctypes
import logging
import sys

logger = logging.getLogger(__name__)


def trim_unused_native_memory() -> bool:
    """Keep live objects/caches intact; unsupported platforms are a no-op."""
    if sys.platform != "linux":
        return False
    try:
        libc = ctypes.CDLL(None)
        # Do not assume every Linux runtime uses glibc.
        getattr(libc, "gnu_get_libc_version")
        trim = libc.malloc_trim
        trim.argtypes = [ctypes.c_size_t]
        trim.restype = ctypes.c_int
        return trim(0) == 1
    except AttributeError:
        return False
    except OSError:
        logger.warning("Native memory trim unavailable", exc_info=True)
        return False
