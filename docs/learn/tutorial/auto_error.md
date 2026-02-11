# Auto Error

By default, when a permission check fails, `fastapi-has-permissions` automatically raises an
`HTTPException` with status code `403 Forbidden`. This behavior is controlled by the `auto_error`
parameter. When `auto_error=False`, failed permission checks return the result to your route handler
instead of raising an exception, letting you handle failures programmatically.

## Default Behavior (`auto_error=True`)

With the default `auto_error=True`, a failed permission check raises an `HTTPException` and the
route handler never executes:

```python
from fastapi import Depends, FastAPI, Request

from fastapi_has_permissions import Permission


class HasAuthorizationHeader(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return "Authorization" in request.headers


app = FastAPI()


@app.get(
    "/protected",
    dependencies=[Depends(HasAuthorizationHeader())],
)
async def protected():
    return {"message": "You have access!"}
```

- With `Authorization` header: `200 OK`
- Without `Authorization` header: `403 Forbidden` (automatic)

## Disabling Auto Error with `no_auto_error()`

The `no_auto_error()` helper wraps a permission so that failed checks return the result instead of
raising an exception. This lets your route handler inspect the result and decide what to do:

```python
from typing import Annotated

from fastapi import Depends, FastAPI, Request

from fastapi_has_permissions import CheckResult, Permission
from fastapi_has_permissions.common import no_auto_error


class HasAuthorizationHeader(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return "Authorization" in request.headers


app = FastAPI()


@app.get("/check-auth")
async def check_auth(
    *,
    has_auth: Annotated[
        CheckResult,
        Depends(no_auto_error(HasAuthorizationHeader())),
    ],
) -> dict[str, bool]:
    return {"has_auth": bool(has_auth)}
```

- With `Authorization` header: `200 OK` with `{"has_auth": true}`
- Without `Authorization` header: `200 OK` with `{"has_auth": false}`

The route always returns `200 OK` -- the permission result is available as a `CheckResult` value
that you can convert to `bool` or inspect further.

!!! note

    `no_auto_error()` returns a `PermissionWrapper` with `auto_error=False`. The wrapped permission
    itself is unchanged -- only the auto-error behavior is disabled.

## Use Cases

### Conditional Content

Show different content based on the user's permissions without blocking the request:

```python
from typing import Annotated

from fastapi import Depends

from fastapi_has_permissions import CheckResult
from fastapi_has_permissions.common import no_auto_error


@app.get("/dashboard")
async def dashboard(
    *,
    is_admin: Annotated[
        CheckResult,
        Depends(no_auto_error(HasAdminRole())),
    ],
) -> dict:
    data = {"welcome": "Hello!"}

    if is_admin:
        data["admin_panel"] = "You have admin access"

    return data
```

### Custom Error Responses

Return a custom response format instead of the default `HTTPException`:

```python
from typing import Annotated

from fastapi import Depends
from fastapi.responses import JSONResponse

from fastapi_has_permissions import CheckResult, is_failed
from fastapi_has_permissions.common import no_auto_error


@app.get("/resource")
async def get_resource(
    *,
    result: Annotated[
        CheckResult,
        Depends(no_auto_error(HasAuthorizationHeader())),
    ],
):
    if is_failed(result):
        return JSONResponse(
            status_code=403,
            content={"error": "access_denied", "reason": result.reason},
        )

    return {"data": "secret"}
```

### Combining Multiple Optional Checks

Check several permissions without short-circuiting on the first failure:

```python
from typing import Annotated

from fastapi import Depends

from fastapi_has_permissions import CheckResult
from fastapi_has_permissions.common import no_auto_error


@app.get("/profile")
async def profile(
    *,
    is_admin: Annotated[CheckResult, Depends(no_auto_error(HasAdminRole()))],
    is_moderator: Annotated[CheckResult, Depends(no_auto_error(HasModeratorRole()))],
) -> dict:
    return {
        "role": "admin" if is_admin else "moderator" if is_moderator else "user",
    }
```

## How It Works

The `auto_error` parameter is a field on the `Permission` base class. After running `check_permissions`,
the library checks `auto_error`:

- If `auto_error=True` (default) and the check failed, `raise_http_exception()` is called.
- If `auto_error=False`, the raw `CheckResult` is returned to the caller (your route handler).

The `no_auto_error()` function is a shorthand for wrapping a permission with `auto_error=False`:

```python
from fastapi_has_permissions import PermissionWrapper

# These are equivalent:
no_auto_error(HasAuthorizationHeader())
PermissionWrapper(HasAuthorizationHeader(), auto_error=False)
```

## With Boolean Composition

`no_auto_error()` works with composed permissions too:

```python
from fastapi_has_permissions.common import no_auto_error

composed = HasAuthorizationHeader() & HasAdminRole()

@app.get("/check")
async def check(
    *,
    result: Annotated[
        CheckResult,
        Depends(no_auto_error(composed)),
    ],
) -> dict[str, bool]:
    return {"allowed": bool(result)}
```

!!! tip

    Use `no_auto_error()` when you need the permission result inside your route handler.
    For standard "allow or deny" behavior, the default `auto_error=True` is simpler and
    more appropriate.
