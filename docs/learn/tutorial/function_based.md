# Function-Based Permissions

For simpler permission checks, you can use the `@permission` decorator instead of defining a class.

## Basic Usage

```python
from fastapi import Depends, FastAPI, Request

from fastapi_has_permissions import permission


@permission
async def has_authorization_header(request: Request) -> bool:
    return "Authorization" in request.headers


app = FastAPI()


@app.get(
    "/protected",
    dependencies=[Depends(has_authorization_header())],
)
async def protected():
    return {"message": "You have access!"}
```

The `@permission` decorator wraps your async function into a permission factory. Call it to create
a `Permission` instance. This means it supports all the same features as class-based permissions,
including boolean composition.

## With FastAPI Dependency Injection

Just like class-based permissions, function-based permissions support FastAPI's DI:

```python
from typing import Annotated

from fastapi import Depends, FastAPI, Header

from fastapi_has_permissions import permission


@permission
async def has_admin_role(role: Annotated[str, Header()]) -> bool:
    return role == "admin"


app = FastAPI()


@app.get(
    "/admin",
    dependencies=[Depends(has_admin_role())],
)
async def admin_only():
    return {"message": "Admin access granted"}
```

## Custom Error Messages

You can pass `message` and `status_code` arguments to customize the error response:

```python
from fastapi_has_permissions import permission


@permission(message="You must be an admin", status_code=401)
async def has_admin_role(role: Annotated[str, Header()]) -> bool:
    return role == "admin"
```

When used with arguments, `@permission(...)` returns a decorator:

```python
# Without arguments (direct decorator)
@permission
async def my_check(...) -> bool:
    ...

# With arguments (decorator factory)
@permission(message="Custom message", status_code=401)
async def my_check(...) -> bool:
    ...
```

In both cases, the result is a **factory** -- call it to create a permission instance:

```python
Depends(my_check())  # call to create the permission instance
```

## Dependencies with `Dep`

Function-based permissions can accept `Dep` arguments, similar to class-based permissions with `Dep` fields.
Declare parameters with `Dep[T]` type annotations -- these must come before any regular parameters in the
function signature:

```python
from typing import Annotated

from fastapi import Depends, Header

from fastapi_has_permissions import Dep, permission


async def get_admin_role() -> str:
    return "admin"


@permission
async def has_role(
    admin_role: Dep[str],
    role: Annotated[str, Header()],
) -> bool:
    return role == admin_role
```

When creating the permission instance, pass the dependencies as positional arguments to the factory:

```python
AdminRoleDep = Annotated[str, Depends(get_admin_role)]

has_admin_role = has_role(AdminRoleDep)


@app.get(
    "/admin",
    dependencies=[Depends(has_admin_role)],
)
async def admin_only():
    return {"message": "Admin access granted"}
```

At request time, `Annotated[str, Depends(get_admin_role)]` is resolved by FastAPI and its value is
passed as the `admin_role` argument. The remaining parameters (`role`) are resolved via FastAPI's
standard DI.

!!! note

    All `Dep` parameters must be declared before non-`Dep` parameters in the function signature.
    The number of `Dep` parameters must match the number of arguments passed to the factory.

## Boolean Composition

Function-based permissions support the same `&`, `|`, `~` operators as class-based permissions:

```python
from fastapi import Depends, FastAPI, Request
from typing import Annotated
from fastapi import Header

from fastapi_has_permissions import permission


@permission
async def has_authorization(request: Request) -> bool:
    return "Authorization" in request.headers


@permission
async def has_admin_role(role: Annotated[str, Header()]) -> bool:
    return role == "admin"


app = FastAPI()


# Both must pass
@app.get(
    "/admin",
    dependencies=[Depends(has_authorization() & has_admin_role())],
)
async def admin_only():
    return {"message": "Authenticated admin access"}


# Either must pass
@app.get(
    "/flexible",
    dependencies=[Depends(has_authorization() | has_admin_role())],
)
async def flexible():
    return {"message": "Access granted"}
```

!!! tip

    Function-based permissions work well for both simple checks and parameterized checks
    using `Dep`. For permissions that need multiple configuration fields or complex
    state, consider [class-based permissions](class_based.md) instead.
