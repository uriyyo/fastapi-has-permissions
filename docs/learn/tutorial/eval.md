# Permission Results

A permission used as a dependency is a *guard*: when the check fails the library raises an
`HTTPException` and the route handler never runs. Sometimes you want the opposite -- to let the
request through and decide in the handler what a failure means. `Eval` is how you ask for the
result instead of the guard.

## The Default: a Guard

With `Depends(...)`, a failed check raises and the handler never executes:

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
- Without `Authorization` header: `403 Forbidden`

## Asking for the Result With `Eval`

`Eval[CheckResult, permission]` is an annotation that resolves the permission and hands you its
[`CheckResult`](skip_and_fail.md) rather than raising:

```python
from fastapi import FastAPI, Request

from fastapi_has_permissions import CheckResult, Eval, Permission


class HasAuthorizationHeader(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return "Authorization" in request.headers


app = FastAPI()


@app.get("/check-auth")
async def check_auth(
    has_auth: Eval[CheckResult, HasAuthorizationHeader()],
) -> dict[str, bool]:
    return {"has_auth": bool(has_auth)}
```

- With `Authorization` header: `200 OK` with `{"has_auth": true}`
- Without `Authorization` header: `200 OK` with `{"has_auth": false}`

The route always returns `200 OK` -- the permission result is available as a `CheckResult` value
that you can convert to `bool` or inspect further.

!!! note

    The first argument is the annotated type and the permission rides along as metadata, the same
    shape as [`DepFactory[T, factory]`](dep_type.md). To a type checker,
    `Eval[CheckResult, HasAuthorizationHeader()]` is simply a `CheckResult`.

## Use Cases

### Conditional Content

Show different content based on the user's permissions without blocking the request:

```python
from fastapi_has_permissions import CheckResult, Eval


@app.get("/dashboard")
async def dashboard(
    is_admin: Eval[CheckResult, HasAdminRole()],
) -> dict:
    data = {"welcome": "Hello!"}

    if is_admin:
        data["admin_panel"] = "You have admin access"

    return data
```

### Custom Error Responses

Return a custom response format instead of the default `HTTPException`:

```python
from fastapi.responses import JSONResponse

from fastapi_has_permissions import CheckResult, Eval, is_failed


@app.get("/resource")
async def get_resource(
    result: Eval[CheckResult, HasAuthorizationHeader()],
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
from fastapi_has_permissions import CheckResult, Eval


@app.get("/profile")
async def profile(
    is_admin: Eval[CheckResult, HasAdminRole()],
    is_moderator: Eval[CheckResult, HasModeratorRole()],
) -> dict:
    return {
        "role": "admin" if is_admin else "moderator" if is_moderator else "user",
    }
```

## With Boolean Composition

`Eval` takes any permission, so a composed expression works unchanged:

```python
composed = HasAuthorizationHeader() & HasAdminRole()


@app.get("/check")
async def check(
    result: Eval[CheckResult, composed],
) -> dict[str, bool]:
    return {"allowed": bool(result)}
```

## How It Works

`Eval` wraps the permission and resolves it as an ordinary dependency. Raising is something that
happens at the *root* of a permission tree, so wrapping is enough to suppress it -- the permission
inside is untouched, and a composed permission still short-circuits and propagates failures
exactly as it would under `Depends`.

Because the wrapped permission is reached the same way, it still contributes its dependencies and
security requirements to the [OpenAPI schema](../real_world/overview.md).

!!! tip

    Use `Eval` when you need the permission result inside your route handler. For standard
    "allow or deny" behavior, `Depends(permission)` is simpler and more appropriate.

## Outside a Request

`Eval` is an annotation, so it belongs on a route. In a service function, a background job or a
message handler there is no signature to annotate -- use
[`evaluate()`](deferred_resolution.md) instead, which likewise returns the `CheckResult` rather
than raising:

```python
from fastapi_has_permissions import evaluate, is_failed

if is_failed(await evaluate(HasAdminRole())):
    ...
```
