from ._func import permission
from ._lazy import LazyPermission, lazy
from ._permissions import AllPermissions, AnyPermissions, NotPermission, Permission, PermissionWrapper
from ._results import CheckResult, Failed, Skipped, fail, is_failed, is_skipped, skip

__all__ = [
    "AllPermissions",
    "AnyPermissions",
    "CheckResult",
    "Failed",
    "LazyPermission",
    "NotPermission",
    "Permission",
    "PermissionWrapper",
    "Skipped",
    "fail",
    "is_failed",
    "is_skipped",
    "lazy",
    "permission",
    "skip",
]
