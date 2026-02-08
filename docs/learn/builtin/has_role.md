# HasRole

`HasRole` is a built-in permission from `fastapi_has_permissions.common` that checks whether the
current user has one of the required roles.

## How It Works

`HasRole` takes two parameters:

- `role_dep: Dep` -- a FastAPI dependency that returns the user's current role as a `str`
- `roles: Iterable[str]` -- the set of acceptable roles

```python
from fastapi_has_permissions.common import HasRole
```

## Example

```python
from typing import Annotated

from fastapi import Depends, FastAPI, Header

from fastapi_has_permissions.common import HasRole


async def get_role(
    x_role: Annotated[str | None, Header()] = None,
) -> str:
    return x_role or ""


app = FastAPI()


@app.get(
    "/admin",
    dependencies=[
        Depends(
            HasRole(
                Depends(get_role),
                roles=["admin"],
            ),
        ),
    ],
)
async def admin_only():
    return {"message": "Admin access granted"}


@app.get(
    "/staff",
    dependencies=[
        Depends(
            HasRole(
                Depends(get_role),
                roles=["admin", "moderator"],
            ),
        ),
    ],
)
async def staff_only():
    return {"message": "Staff access granted"}
```

## Behavior

The user's role must be **one of** the listed roles. This is an OR check (any role in the list is
sufficient).

| User Role | Required Roles | Result |
|-----------|---------------|--------|
| `admin` | `["admin"]` | Granted |
| `moderator` | `["admin", "moderator"]` | Granted |
| `admin` | `["admin", "moderator"]` | Granted |
| `user` | `["admin"]` | Denied |
| _(empty)_ | `["admin"]` | Denied |

## Combining with Other Permissions

Use boolean composition for complex role-based access control:

```python
# Admin OR moderator (equivalent to roles=["admin", "moderator"])
Depends(
    HasRole(Depends(get_role), roles=["admin"])
    | HasRole(Depends(get_role), roles=["moderator"])
)

# NOT admin (deny admins)
Depends(
    ~HasRole(Depends(get_role), roles=["admin"])
)
```

## How `check_permissions` Works

```python
class HasRole(Permission):
    role_dep: Dep
    roles: Iterable[str]

    async def check_permissions(self, current_role: str, /) -> bool:
        return current_role in self.roles
```

The `role_dep: Dep` field is resolved via FastAPI DI, and its result is passed as the `current_role`
positional argument. The check verifies that the current role is in the allowed `roles` set.
