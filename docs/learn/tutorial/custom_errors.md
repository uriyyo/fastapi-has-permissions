# Custom Error Responses

By default, when a permission check fails, `fastapi-has-permissions` raises an `HTTPException` with
status code `403 Forbidden` and detail `"Permission denied"`. You can customize both the message
and the status code.

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

## Composed Permission Defaults

The built-in composition classes have their own default messages:

| Class | Default Message |
|-------|----------------|
| `AllPermissions` (`&`) | `"Not all permissions were satisfied"` |
| `AnyPermissions` (`\|`) | `"None of the permissions were satisfied"` |
| `NotPermission` (`~`) | `"The permission was satisfied, but it should not have been"` |

You can override these by passing `message` to the composition result:

```python
perm = HasAuthorizationHeader() & HasAdminRole()
perm.message = "You must be an authenticated admin"
```

## Using `Failed` for Per-Check Messages

You can also return `Failed(reason="...")` from `check_permissions` to provide a specific error
message for that particular failure:

```python
from fastapi_has_permissions import Permission
from fastapi_has_permissions._results import Failed


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
