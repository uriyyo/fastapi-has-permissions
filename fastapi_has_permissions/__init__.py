from fastapi_injected import DependencyResolutionError, Given

from ._app import add_permissions, permission_denied_handler
from ._errors import PermissionDeniedError, SyntheticScopeError
from ._evaluate import Eval, Evaluate, PermissionEvaluator, evaluate
from ._func import permission
from ._permissions import AllPermissions, AnyPermissions, NotPermission, Permission, PermissionWrapper
from ._policy import Policy
from ._requires import Requires
from ._results import (
    CheckResult,
    Failed,
    Skipped,
    Source,
    as_failed,
    fail,
    get_reason,
    is_failed,
    is_skipped,
    is_successful,
    skip,
)
from ._security import Security
from ._wrappers import (
    Advisory,
    AllowSkipped,
    DenySkipped,
    ExcHandler,
    FailOnExc,
    FailUnresolved,
    ResultMapper,
    SkipOnExc,
    SkipUnresolved,
    Undocumented,
    When,
    WithError,
)
from .common import Allow, Deny, HasRole, HasScope, IsAuthenticated
from .types import Dep, DepFactory, Resolved, Resource

__all__ = [
    "Advisory",
    "AllPermissions",
    "Allow",
    "AllowSkipped",
    "AnyPermissions",
    "CheckResult",
    "Deny",
    "DenySkipped",
    "Dep",
    "DepFactory",
    "DependencyResolutionError",
    "Depends",
    "Eval",
    "Evaluate",
    "ExcHandler",
    "FailOnExc",
    "FailUnresolved",
    "Failed",
    "Given",
    "HasRole",
    "HasScope",
    "IsAuthenticated",
    "NotPermission",
    "Permission",
    "PermissionDeniedError",
    "PermissionEvaluator",
    "PermissionWrapper",
    "Policy",
    "Requires",
    "Resolved",
    "Resource",
    "ResultMapper",
    "Security",
    "SkipOnExc",
    "SkipUnresolved",
    "Skipped",
    "Source",
    "SyntheticScopeError",
    "Undocumented",
    "When",
    "WithError",
    "add_permissions",
    "as_failed",
    "evaluate",
    "fail",
    "get_reason",
    "is_failed",
    "is_skipped",
    "is_successful",
    "permission",
    "permission_denied_handler",
    "skip",
]
