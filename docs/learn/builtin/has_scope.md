# HasScope

`HasScope` is a built-in permission from `fastapi_has_permissions.common` that checks whether the
current user has the required OAuth2 scopes.

## How It Works

`HasScope` takes two parameters:

- `scope_dep: Dep` -- a FastAPI dependency that returns the user's current scopes as an `Iterable[str]`
- `scopes: Iterable[str]` -- the required scopes that must all be present

```python
from fastapi_has_permissions.common import HasScope
```

## Example

```python
from typing import Annotated

from fastapi import Depends, FastAPI, Header

from fastapi_has_permissions.common import HasScope


async def get_scopes(
    x_scopes: Annotated[str | None, Header()] = None,
) -> list[str]:
    if x_scopes is None:
        return []
    return x_scopes.split(",")


app = FastAPI()


@app.get(
    "/read-only",
    dependencies=[
        Depends(
            HasScope(
                Depends(get_scopes),
                scopes=["read"],
            ),
        ),
    ],
)
async def read_only():
    return {"message": "Read access granted"}


@app.get(
    "/read-write",
    dependencies=[
        Depends(
            HasScope(
                Depends(get_scopes),
                scopes=["read", "write"],
            ),
        ),
    ],
)
async def read_write():
    return {"message": "Read/write access granted"}
```

## Behavior

- All required scopes must be present in the user's scopes.
- Extra scopes beyond the required ones are allowed.
- If any required scope is missing, the permission is denied.

| User Scopes | Required Scopes | Result |
|-------------|-----------------|--------|
| `read` | `read` | Granted |
| `read, write` | `read` | Granted |
| `read, write, delete` | `read, write` | Granted |
| `read` | `read, write` | Denied |
| `write` | `read` | Denied |
| _(none)_ | `read` | Denied |

## OAuth2 Security Integration

`HasScope` integrates with FastAPI's `Security` system. Internally, it uses `Security(resolver, scopes=...)`
instead of `Depends(resolver)`, which means the required scopes appear in the OpenAPI documentation.

## How `check_permissions` Works

```python
class HasScope(Permission):
    scope_dep: Dep
    scopes: Iterable[str]

    def __resolver_to_depends__(self, resolver: PermissionResolver) -> Any:
        return Security(resolver, scopes=[*self.scopes])

    async def check_permissions(
        self,
        current_scopes: Iterable[str],
        /,
        security_scopes: SecurityScopes,
    ) -> bool:
        return all(
            required_scope in current_scopes
            for required_scope in security_scopes.scopes
        )
```

The `security_scopes: SecurityScopes` parameter is automatically provided by FastAPI's security system
and contains the scopes declared via `Security(...)`.
