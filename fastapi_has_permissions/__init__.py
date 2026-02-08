from ._func import permission
from ._lazy import LazyPermission, lazy
from ._permissions import AllPermissions, AnyPermissions, NotPermission, Permission

__all__ = [
    "AllPermissions",
    "AnyPermissions",
    "LazyPermission",
    "NotPermission",
    "Permission",
    "lazy",
    "permission",
]
