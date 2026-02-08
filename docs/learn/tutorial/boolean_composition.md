# Boolean Composition

One of the most powerful features of `fastapi-has-permissions` is the ability to compose permissions
using boolean operators. This lets you build complex access control rules from simple building blocks.

## Operators

| Operator | Type | Description |
|----------|------|-------------|
| `&` | AND (`AllPermissions`) | All permissions must pass |
| `\|` | OR (`AnyPermissions`) | At least one permission must pass |
| `~` | NOT (`NotPermission`) | Inverts the result |

## AND -- All Must Pass

Use `&` to require that all permissions are satisfied:

```python
from fastapi import Depends, FastAPI, Request

from fastapi_has_permissions import Permission


class HasAuthorizationHeader(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return "Authorization" in request.headers


class HasAdminRole(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return request.headers.get("role") == "admin"


app = FastAPI()


@app.get(
    "/admin",
    dependencies=[Depends(HasAuthorizationHeader() & HasAdminRole())],
)
async def admin_only():
    return {"message": "Authenticated admin access"}
```

The request must have both the `Authorization` header and `role: admin` header to succeed.

## OR -- Any Must Pass

Use `|` to require that at least one permission is satisfied:

```python
@app.get(
    "/flexible",
    dependencies=[Depends(HasAuthorizationHeader() | HasAdminRole())],
)
async def flexible():
    return {"message": "Access granted"}
```

The request succeeds if either the `Authorization` header is present or the `role` is `admin`.

## NOT -- Invert

Use `~` to negate a permission:

```python
@app.get(
    "/guests-only",
    dependencies=[Depends(~HasAuthorizationHeader())],
)
async def guests_only():
    return {"message": "Guest access only"}
```

The request succeeds only if the `Authorization` header is **not** present.

Applying `~` twice returns the original permission:

```python
perm = HasAuthorizationHeader()
assert (~(~perm)).permission is perm  # double negation
```

## Complex Compositions

You can combine operators to build sophisticated access rules:

```python
@app.get(
    "/complex",
    dependencies=[
        Depends(
            (HasAuthorizationHeader() & HasAdminRole()) | ~HasAdminRole()
        ),
    ],
)
async def complex_route():
    return {"message": "Access granted"}
```

This means: allow access if the user is an authenticated admin, **or** if the user is not an admin at all
(i.e., admins must be authenticated, but non-admins can pass freely).

## PermissionWrapper

For frequently used permission compositions, you can create a named wrapper using `PermissionWrapper`:

```python
from fastapi_has_permissions import Permission, PermissionWrapper


class IsStaff(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return request.headers.get("role") == "staff"


class HasServiceToken(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return request.headers.get("x-service-token") == "secret-123"


class IsPrivilegedUser(PermissionWrapper):
    """Allows access for staff members or service tokens."""
    permission: Permission = IsStaff() | HasServiceToken()
```

Now you can use `IsPrivilegedUser()` as a single, reusable permission:

```python
from fastapi import APIRouter, Depends

admin_router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(IsPrivilegedUser())],
)


@admin_router.get("/dashboard")
async def dashboard():
    return {"message": "Admin dashboard"}
```

!!! tip

    `PermissionWrapper` is useful for defining organizational permission policies as named classes.
    This improves readability and keeps your route definitions clean.

## Chaining

When you chain multiple `&` or `|` operators, they are merged into a single `AllPermissions` or
`AnyPermissions` instance rather than being nested:

```python
# These are equivalent:
perm = A() & B() & C()
# Internally: AllPermissions([A(), B(), C()])
# Not: AllPermissions([AllPermissions([A(), B()]), C()])
```

This ensures efficient evaluation without unnecessary nesting.

## Evaluation Order

- `AllPermissions` (`&`): permissions are evaluated left-to-right. Evaluation stops at the first `False`.
- `AnyPermissions` (`|`): permissions are evaluated left-to-right. Evaluation stops at the first `True`.

!!! warning

    Unlike Python's built-in `and`/`or`, all dependencies for all permissions in the composition
    are resolved before evaluation begins. This is because FastAPI resolves dependencies at the
    DI level before the permission check runs.
