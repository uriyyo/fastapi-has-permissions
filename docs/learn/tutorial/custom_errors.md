# Custom Error Responses

By default, when a permission check fails, `fastapi-has-permissions` raises a
`PermissionDeniedError` carrying status code `403 Forbidden` and message `"Permission denied"`,
which is answered as an HTTP response of the same shape. You can customize both the message and
the status code.

## The Error a Denial Raises

A permission does not raise an `HTTPException` directly. It raises `PermissionDeniedError`, and
`add_permissions(app)` installs the handler that renders it:

```python
from fastapi_has_permissions import PermissionDeniedError

app = FastAPI()
add_permissions(app)   # installs the handler alongside everything else
```

The error carries the whole resolved configuration, plus the permission that produced it:

| Attribute | Meaning |
| --- | --- |
| `message` | the resolved message |
| `status_code` | the resolved status code |
| `code` | the resolved application error code, if any |
| `headers` | headers to send with the response, if any |
| `permission` | the permission that denied |

Two things follow. Outside a request -- in a background job, a worker or a CLI command -- there is
nothing HTTP to catch, so catch the error itself:

```python
try:
    await evaluate.require(OwnsArticle(Given(article)))
except PermissionDeniedError as exc:
    log.warning("denied by %s: %s", type(exc.permission).__name__, exc.message)
```

And inside a request, an application that answers in its own shape registers its own handler:

```python
@app.exception_handler(PermissionDeniedError)
async def denied(request: Request, exc: PermissionDeniedError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code or "forbidden", "detail": exc.message},
    )
```

Everything below configures what that error carries.

## Class-Level Defaults

Set `default_exc_message` and `default_exc_status_code` as class variables to change the defaults
for all instances of a permission:

```python
from fastapi import Depends, FastAPI, Request, status

from fastapi_has_permissions import Permission


class RequiresAuthentication(Permission):
    default_exc_message = "Authentication required"
    default_exc_status_code = status.HTTP_401_UNAUTHORIZED

    async def check_permissions(self, request: Request) -> bool:
        return "Authorization" in request.headers


app = FastAPI()


@app.get(
    "/protected",
    dependencies=[Depends(RequiresAuthentication())],
)
async def protected():
    return {"message": "You have access!"}
```

When the check fails, the response will be:

```json
{
    "detail": "Authentication required"
}
```

with HTTP status `401`.

## Instance-Level Overrides

You can override the message and status code per instance using the `message` and `status_code`
keyword arguments:

```python
@app.get(
    "/custom-message",
    dependencies=[
        Depends(
            RequiresAuthentication(
                message="Please provide a valid token",
                status_code=status.HTTP_401_UNAUTHORIZED,
            ),
        ),
    ],
)
async def custom_message():
    return {"message": "You have access!"}
```

!!! note

    Instance-level `message` and `status_code` take precedence over class-level defaults.

!!! warning

    A permission's own error config is applied when that permission is the **root** of the tree --
    the one passed to `Depends()`. A permission nested inside a composition reports the error of
    whichever child denied, so `(RequiresAuthentication(status_code=404) | IsAdmin())` still answers
    with the child's `401`. Use [`WithError`](#witherror----one-error-for-a-whole-subtree) to change
    the error of a nested subtree.

## `WithError` -- One Error for a Whole Subtree

`WithError` rewrites the error of whatever it wraps, so an entire subtree answers with a single
error config no matter which permission inside of it denied:

```python
from fastapi import status

from fastapi_has_permissions import WithError


@app.get(
    "/articles/{article_id}",
    dependencies=[
        Depends(
            WithError(
                IsArticleAuthor() | IsEditor(),
                message="Not found",
                status_code=status.HTTP_404_NOT_FOUND,
            ),
        ),
    ],
)
async def get_article(article_id: int): ...
```

Without it the response leaks information: a `403` tells the caller the article exists and they
are not allowed to see it, while a `404` does not.

Fields you leave unset fall back to the failing permission's own values, so
`WithError(perm, status_code=404)` changes only the status code and keeps the original message.
Unlike the `message` / `status_code` arguments of a plain permission, `WithError` works at any
depth of the tree. See [Permission Wrappers](wrappers.md) for the rest of the wrappers.

## Override Methods

For dynamic error messages, you can override `get_exc_message()` and `get_exc_status_code()`:

```python
from dataclasses import dataclass

from fastapi_has_permissions import Permission


@dataclass
class HasRole(Permission):
    role: str

    def get_exc_message(self) -> str:
        return f"You need the '{self.role}' role to access this resource"

    async def check_permissions(self, request: Request) -> bool:
        return request.headers.get("role") == self.role
```

These methods take no arguments and are consulted whenever this permission's own error config is
needed -- when it denies as the root of the tree, and when a wrapper such as `WithError`,
`FailOnExc` or `DenySkipped` builds a failure from it.

## Composed Permission Defaults

The built-in composition classes have their own default messages:

| Class | Default Message |
|-------|----------------|
| `AllPermissions` (`&`) | `"Not all permissions were satisfied"` |
| `AnyPermissions` (`\|`) | `"None of the permissions were satisfied"` |
| `NotPermission` (`~`) | `"The permission was satisfied, but it should not have been"` |

A composed permission only falls back to these defaults when none of its children reported an
error of their own. To give the whole composition one error, wrap it:

```python
perm = WithError(
    HasAuthorizationHeader() & HasAdminRole(),
    message="You must be an authenticated admin",
)
```

## Using `Failed` for Per-Check Messages

You can also return `Failed(reason="...")` from `check_permissions` to provide a specific error
message for that particular failure:

```python
from fastapi_has_permissions import Failed, Permission


class HasValidToken(Permission):
    async def check_permissions(self, request: Request) -> bool | Failed:
        token = request.headers.get("Authorization")

        if token is None:
            return Failed(reason="Authorization header is missing")

        if not token.startswith("Bearer "):
            return Failed(reason="Token must use Bearer scheme")

        return True
```

The `reason` from the `Failed` result will be used as the HTTP exception detail.
