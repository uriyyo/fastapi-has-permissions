from ._dep import Dep
from ._func import permission
from ._lazy import LazyPermission, lazy
from ._permissions import AllPermissions, AnyPermissions, NotPermission, Permission, PermissionWrapper
from ._results import CheckResult, Failed, Skipped, fail, is_failed, is_skipped, is_successful, skip

__all__ = [
    "AllPermissions",
    "AnyPermissions",
    "CheckResult",
    "Dep",
    "Failed",
    "LazyPermission",
    "NotPermission",
    "Permission",
    "PermissionWrapper",
    "Skipped",
    "fail",
    "is_failed",
    "is_skipped",
    "is_successful",
    "lazy",
    "permission",
    "skip",
]
