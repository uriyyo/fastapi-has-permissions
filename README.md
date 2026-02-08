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

`fastapi-has-permissions` is a Python library that provides a declarative permissions system for FastAPI applications.
It allows you to define permission checks as classes or functions and compose them using boolean operators
(`&`, `|`, `~`) into complex permission expressions. These composed permissions integrate directly
with FastAPI's dependency injection system.

Features:

* **Class-based permissions** -- subclass `Permission` and override `check_permissions()`
* **Function-based permissions** -- use the `@permission` decorator to wrap async functions
* **Boolean composition** -- combine permissions with `&` (AND), `|` (OR), `~` (NOT)
* **Lazy evaluation** -- defer dependency resolution to request time with `lazy()`
* **Skip mechanism** -- conditionally bypass permission checks using `SkipPermissionCheck`
* **Customizable error responses** -- override default 403 status code and error messages
* **Full FastAPI DI integration** -- permission check functions support all FastAPI dependency injection features
* Compatible with Python 3.10 and higher

---

## Installation

```bash
pip install fastapi-has-permissions
```

## Quickstart

Define a permission by subclassing `Permission` and use it as a FastAPI dependency:

```python
from dataclasses import dataclass

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

## Boolean Composition

Permissions can be combined using `&` (AND), `|` (OR), and `~` (NOT) operators:

```python
from dataclasses import dataclass

from fastapi import Depends, Request

from fastapi_has_permissions import Permission


class HasAuthorizationHeader(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return "Authorization" in request.headers


@dataclass
class HasRole(Permission):
    role: str

    async def check_permissions(self, request: Request) -> bool:
        return request.headers.get("role") == self.role


# All permissions must pass
@app.get(
    "/admin",
    dependencies=[Depends(HasAuthorizationHeader() & HasRole("admin"))],
)
async def admin_only():
    return {"message": "Admin access granted"}


# Any permission must pass
@app.get(
    "/flexible",
    dependencies=[Depends(HasAuthorizationHeader() | HasRole("admin"))],
)
async def flexible_access():
    return {"message": "Access granted"}


# Negated permission
@app.get(
    "/no-auth",
    dependencies=[Depends(~HasAuthorizationHeader())],
)
async def no_auth_required():
    return {"message": "No auth header present"}
```

## Function-Based Permissions

Use the `@permission` decorator to create permissions from async functions:

```python
from typing import Annotated

from fastapi import Depends, Header

from fastapi_has_permissions import permission


@permission
async def has_admin_role(role: Annotated[str, Header()]) -> bool:
    return role == "admin"


@app.get(
    "/admin",
    dependencies=[Depends(has_admin_role)],
)
async def admin_endpoint():
    return {"message": "Admin access granted"}
```

Function-based permissions also support boolean composition:

```python
@permission
async def has_authorization(request: Request) -> bool:
    return "Authorization" in request.headers


# Combine function-based permissions
@app.get(
    "/combined",
    dependencies=[Depends(has_authorization & has_admin_role)],
)
async def combined():
    return {"message": "Access granted"}
```

## Lazy Permissions

Use `lazy()` to defer dependency resolution to request time. This is useful when a permission's
dependencies may not always be available:

```python
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header
from fastapi.exceptions import RequestValidationError

from fastapi_has_permissions import Permission, lazy


@dataclass
class AgeIsMoreThan(Permission):
    age: int

    async def check_permissions(self, age: Annotated[int, Header()]) -> bool:
        return age > self.age


# If the "age" header is missing/invalid, skip the check instead of failing
@app.get(
    "/age-restricted",
    dependencies=[
        Depends(lazy(AgeIsMoreThan(age=18), skip_on_exc=(RequestValidationError,))),
    ],
)
async def age_restricted():
    return {"message": "Access granted"}
```

## Custom Error Responses

Override the default 403 response by setting class variables or overriding methods:

```python
class CustomPermission(Permission):
    default_exc_message = "Custom error message"
    default_exc_status_code = 401

    async def check_permissions(self, request: Request) -> bool:
        return "Authorization" in request.headers
```

For dynamic error messages, override `get_exc_message()` or `get_exc_status_code()`:

```python
@dataclass
class HasRole(Permission):
    role: str

    async def check_permissions(self, request: Request) -> bool:
        return request.headers.get("role") == self.role

    def get_exc_message(self) -> str:
        return f"Role '{self.role}' is required"
```
