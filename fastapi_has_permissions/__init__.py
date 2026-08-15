from fastapi_injected import Dep, DepFactory

from ._app import add_permissions
from ._evaluate import Evaluate, PermissionEvaluator, evaluate
from ._func import permission
from ._lazy import LazyPermission, lazy
from ._permissions import AllPermissions, AnyPermissions, NotPermission, Permission, PermissionWrapper
from ._results import CheckResult, Failed, Skipped, fail, is_failed, is_skipped, is_successful, skip

__all__ = [
    "AllPermissions",
    "AnyPermissions",
    "CheckResult",
    "Dep",
    "DepFactory",
    "Evaluate",
    "Failed",
    "LazyPermission",
    "NotPermission",
    "Permission",
    "PermissionEvaluator",
    "PermissionWrapper",
    "Skipped",
    "add_permissions",
    "evaluate",
    "fail",
    "is_failed",
    "is_skipped",
    "is_successful",
    "lazy",
    "permission",
    "skip",
]
