<h1 align="center">
  fastapi-has-permissions
</h1>

<div align="center">
<img alt="license" src="https://img.shields.io/badge/License-MIT-lightgrey">
<img alt="test" src="https://github.com/uriyyo/fastapi-has-permissions/workflows/Test/badge.svg">
<img alt="codecov" src="https://codecov.io/gh/uriyyo/fastapi-has-permissions/branch/main/graph/badge.svg">
<a href="https://pypi.org/project/fastapi-has-permissions"><img alt="pypi" src="https://img.shields.io/pypi/v/fastapi-has-permissions"></a>
<a href="https://pepy.tech/project/fastapi-has-permissions"><img alt="downloads" src="https://pepy.tech/badge/fastapi-has-permissions"></a>
</div>

## Introduction

Declarative permissions system for FastAPI. Define permission checks as classes or functions,
compose them with `&`, `|`, `~` operators, and plug them into FastAPI's dependency injection.

## Installation

```bash
pip install fastapi-has-permissions
```

## Usage

### Class-Based Permissions

Subclass `Permission` and implement `check_permissions()`:

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

Permissions with parameters are automatically dataclasses:

```python
class HasRole(Permission):
    role: str

    async def check_permissions(self, request: Request) -> bool:
        return request.headers.get("role") == self.role
```

### Boolean Composition

Combine permissions with `&` (AND), `|` (OR), and `~` (NOT):

```python
# All must pass
Depends(HasAuthorizationHeader() & HasRole("admin"))

# Any must pass
Depends(HasAuthorizationHeader() | HasRole("admin"))

# Negated
Depends(~HasAuthorizationHeader())
```

### Function-Based Permissions

Use the `@permission` decorator for a lightweight alternative:

```python
from typing import Annotated

from fastapi import Header

from fastapi_has_permissions import permission


@permission
async def has_admin_role(role: Annotated[str, Header()]) -> bool:
    return role == "admin"


@app.get("/admin", dependencies=[Depends(has_admin_role())])
async def admin_endpoint():
    return {"message": "Admin access granted"}
```

Function-based permissions support the same `&`, `|`, `~` composition.

### Lazy Permissions

Defer dependency resolution to request time with `lazy()` - useful when dependencies
may not always be available:

```python
from fastapi.exceptions import RequestValidationError

from fastapi_has_permissions import lazy

# Skip the check instead of failing if the "age" header is missing
Depends(lazy(AgeIsMoreThan(age=18), skip_on_exc=(RequestValidationError,)))
```

### Other Features

- **Custom error responses** -- set `default_exc_message` / `default_exc_status_code` class variables
  or override `get_exc_message()` / `get_exc_status_code()` methods
- **Skip / Fail helpers** -- call `skip()` or `fail()` inside `check_permissions()` for explicit control flow
- **Built-in common permissions** -- `IsAuthenticated`, `HasScope`, `HasRole` ready to use with your auth dependencies
- **Full FastAPI DI support** -- `check_permissions()` accepts any FastAPI-injectable parameters
