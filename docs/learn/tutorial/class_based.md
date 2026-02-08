# Class-Based Permissions

Class-based permissions are the primary way to define permission checks. You subclass `Permission` and
implement the `check_permissions` method.

## Basic Permission

The simplest permission class has no fields and uses only injected parameters:

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

## Permissions with Parameters

Permission classes are automatically turned into dataclasses. You can add fields to parameterize
the permission check:

```python
from dataclasses import dataclass

from fastapi import Depends, FastAPI, Request

from fastapi_has_permissions import Permission


@dataclass
class HasRole(Permission):
    role: str

    async def check_permissions(self, request: Request) -> bool:
        return request.headers.get("role") == self.role


app = FastAPI()


@app.get(
    "/admin",
    dependencies=[Depends(HasRole(role="admin"))],
)
async def admin_only():
    return {"message": "Admin access granted"}


@app.get(
    "/moderator",
    dependencies=[Depends(HasRole(role="moderator"))],
)
async def moderator_only():
    return {"message": "Moderator access granted"}
```

!!! note

    The `@dataclass` decorator is optional -- `Permission` subclasses are automatically
    converted to dataclasses. However, adding it explicitly can help your IDE with type hints
    and autocompletion.

## FastAPI Dependency Injection in `check_permissions`

The `check_permissions` method fully supports FastAPI's dependency injection. Any parameter
you declare will be resolved by FastAPI at request time:

```python
from typing import Annotated

from fastapi import Depends, FastAPI, Header

from fastapi_has_permissions import Permission


class HasAdminRole(Permission):
    async def check_permissions(self, role: Annotated[str, Header()]) -> bool:
        return role == "admin"


app = FastAPI()


@app.get(
    "/admin",
    dependencies=[Depends(HasAdminRole())],
)
async def admin_only():
    return {"message": "Admin access granted"}
```

You can also use `Depends()` inside `check_permissions` to inject other dependencies:

```python
from typing import Annotated

from fastapi import Depends, FastAPI, Header

from fastapi_has_permissions import Permission


async def get_current_user_role(x_role: Annotated[str, Header()]) -> str:
    return x_role


class HasAdminRole(Permission):
    async def check_permissions(
        self,
        role: Annotated[str, Depends(get_current_user_role)],
    ) -> bool:
        return role == "admin"


app = FastAPI()


@app.get(
    "/admin",
    dependencies=[Depends(HasAdminRole())],
)
async def admin_only():
    return {"message": "Admin access granted"}
```

## Return Types

The `check_permissions` method returns a `CheckResult`, which can be:

- `True` -- permission granted
- `False` -- permission denied (raises `HTTPException` with `403`)
- `Failed(reason="...")` -- permission denied with a custom message
- `Skipped(reason="...")` -- permission check is skipped entirely (treated as granted)

```python
from fastapi_has_permissions import Permission, fail
from fastapi_has_permissions._results import CheckResult, Failed


class HasValidToken(Permission):
    async def check_permissions(self, request: Request) -> CheckResult:
        token = request.headers.get("Authorization")

        if token is None:
            return Failed(reason="Authorization header is missing")

        if token != "Bearer valid-token":
            return Failed(reason="Invalid token")

        return True
```

!!! tip

    See [Skip & Fail Helpers](skip_and_fail.md) for more convenient ways to control
    the permission check flow.

## Router-Level Permissions

Instead of adding permissions to individual routes, you can apply them to an entire router:

```python
from fastapi import APIRouter, Depends, FastAPI

from fastapi_has_permissions import Permission


class IsAuthenticated(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return "Authorization" in request.headers


app = FastAPI()

router = APIRouter(
    prefix="/api",
    dependencies=[Depends(IsAuthenticated())],
)


@router.get("/users")
async def get_users():
    return [{"name": "Alice"}, {"name": "Bob"}]


@router.get("/items")
async def get_items():
    return [{"name": "Item 1"}, {"name": "Item 2"}]


app.include_router(router)
```

All routes under this router will require the `Authorization` header.
