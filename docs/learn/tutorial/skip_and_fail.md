# Skip & Fail Helpers

`fastapi-has-permissions` provides helper functions and result types for explicit control over
the permission check flow.

## `fail()` -- Explicitly Deny

Call `fail()` inside `check_permissions` to immediately deny the permission with a custom message:

```python
from fastapi import Request

from fastapi_has_permissions import Permission, fail


class HasValidToken(Permission):
    async def check_permissions(self, request: Request) -> bool:
        token = request.headers.get("Authorization")

        if token is None:
            fail("Authorization header is required")

        if not token.startswith("Bearer "):
            fail("Token must use Bearer scheme")

        return True
```

`fail()` raises a `PermissionCheckFailed` exception internally. The library catches it and converts
it into a `Failed` result with the provided reason. The reason is used as the HTTP exception detail.

!!! note

    `fail()` has a return type of `NoReturn`, so the code after it is unreachable.
    Your type checker will correctly understand that control flow stops at `fail()`.

## `skip()` -- Skip the Check

Call `skip()` inside `check_permissions` to skip the permission check entirely. A skipped permission
is treated as if it was never checked:

```python
from fastapi import Request

from fastapi_has_permissions import Permission, skip


class RequiresTokenIfPresent(Permission):
    """Only validates the token if it's provided. Skips otherwise."""

    async def check_permissions(self, request: Request) -> bool:
        if "Authorization" not in request.headers:
            skip("No token provided, skipping validation")

        return request.headers["Authorization"] == "Bearer valid-token"
```

`skip()` raises a `SkipPermissionCheck` exception internally. The library catches it and returns
a `Skipped` result.

## Result Types

You can also return `Failed` and `Skipped` instances directly instead of using the helper functions:

```python
from fastapi_has_permissions import Permission
from fastapi_has_permissions._results import CheckResult, Failed, Skipped


class MyPermission(Permission):
    async def check_permissions(self, request: Request) -> CheckResult:
        token = request.headers.get("Authorization")

        if token is None:
            return Skipped(reason="No token, skipping")

        if token != "Bearer valid":
            return Failed(reason="Invalid token")

        return True
```

### `CheckResult` Type

`CheckResult` is a type alias for `bool | Skipped | Failed`:

| Value | Meaning |
|-------|---------|
| `True` | Permission granted |
| `False` | Permission denied (uses default or class-level message) |
| `Failed(reason="...")` | Permission denied with a specific message |
| `Skipped(reason="...")` | Permission check skipped entirely |

## Type Guards

Use `is_failed()` and `is_skipped()` to check the result type:

```python
from fastapi_has_permissions import is_failed, is_skipped


result = await some_permission.check_permissions()

if is_skipped(result):
    print("Permission was skipped")
elif is_failed(result):
    print(f"Permission failed: {result.reason}")
```

These are `TypeIs` guards, so your type checker will narrow the type after the check.

## How Skip Interacts with Composition

Skipped permissions have special behavior when combined with `&` and `|`:

### AND (`&`)

| Scenario | Result |
|----------|--------|
| All skip | `Skipped` |
| Skip + Pass | Pass |
| Skip + Fail | Fail |

```python
# If AlwaysSkip skips, the AND result depends on the other permission
Depends(AlwaysSkip() & HasAuthorizationHeader())
# With auth header: 200 OK (skip is ignored, other passes)
# Without auth header: 403 Forbidden (skip is ignored, other fails)
```

### OR (`|`)

| Scenario | Result |
|----------|--------|
| All skip | `Skipped` |
| Skip + Pass | Pass |
| Skip + Fail | Fail |

```python
# If AlwaysSkip skips, the OR result depends on non-skipped permissions
Depends(AlwaysSkip() | HasAdminRole())
# With admin role: 200 OK (at least one passes)
# Without admin role: 403 Forbidden (non-skipped permission fails)
```

### NOT (`~`)

| Scenario | Result |
|----------|--------|
| Skip | `Skipped` (passthrough) |

```python
# Negating a skipped permission still skips
Depends(~AlwaysSkip())
# Always: 200 OK (skip passes through)
```

!!! warning

    When all permissions in a composition are skipped, the final result is `Skipped`, which means
    the request is allowed through. Design your permissions carefully to ensure at least one
    non-skippable check exists when needed.
