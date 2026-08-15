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

### Setup

Call `add_permissions()` on your app — it binds an inject scope to every request, which
is what lets `|`, `~`, `lazy()` and `Evaluate` resolve their dependencies at check time:

```python
from fastapi import FastAPI

from fastapi_has_permissions import add_permissions

app = FastAPI()
add_permissions(app)
```

`add_permissions()` is idempotent, but it has to be called **before** the routes are
declared — FastAPI copies the router dependencies into every route at registration time.

### Class-Based Permissions

Subclass `Permission` and implement `check_permissions()`:

```python
from fastapi import Depends, FastAPI, Request

from fastapi_has_permissions import Permission, add_permissions


class HasAuthorizationHeader(Permission):
    async def check_permissions(self, request: Request) -> bool:
        return "Authorization" in request.headers


app = FastAPI()
add_permissions(app)


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

`|` and `~` are **lazy**: each branch's dependencies are resolved at request time,
one branch at a time, and evaluation short-circuits at the first permission that
passes — a failing or expensive dependency in a losing branch is never resolved.
`&` resolves its dependencies eagerly (they all need to pass anyway), which keeps
them visible in the OpenAPI schema.

When a composed check fails, the failing permission's message, status code, error
code, and headers are propagated: `&` reports the first failing permission, and `|`
combines the failure reasons of all branches when none of them passed.

Skipped permissions (see `skip()`) are ignored by `&` and `|` — the remaining
permissions decide the outcome. A composite where _every_ permission skipped is
itself skipped, and `~` passes a skip through unchanged:

| Expression     | Result                              |
| -------------- | ----------------------------------- |
| `Pass & Skip`  | pass                                |
| `Fail & Skip`  | fail (with `Fail`'s message/status) |
| `Skip & Skip`  | skip                                |
| `Fail \| Skip` | fail                                |
| `Pass \| Skip` | pass                                |
| `Skip \| Skip` | skip                                |
| `~Skip`        | skip                                |

A skip is an abstention, not an approval: if it reaches the root of the tree — the
permission you passed to `Depends()` or to `evaluator.require()` — the request is
denied. Wrap the permission into `AllowSkipped` to state explicitly that an
abstention should grant access:

```python
from fastapi_has_permissions import AllowSkipped

# skipped -> 403 Forbidden
Depends(IsArticleAuthor())

# skipped -> allowed
Depends(AllowSkipped(IsArticleAuthor()))
```

> **Note:** every permission instance is a distinct FastAPI dependency (identity-based
> hashing), so two equal instances are resolved and checked independently within one
> request. Reuse the same instance when you want FastAPI's per-request dependency
> cache to apply.

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

Function-based permissions also support `Dep` arguments for injecting FastAPI dependencies:

```python
from fastapi_has_permissions import Dep, DepFactory, permission


async def get_admin_role() -> str:
    return "admin"


AdminRoleDep = DepFactory[str, get_admin_role]  # == Annotated[str, Depends(get_admin_role)]


@permission
async def has_role(admin_role: Dep[str], /, role: Annotated[str, Header()]) -> bool:
    return role == admin_role


@app.get("/admin", dependencies=[Depends(has_role(AdminRoleDep))])
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

### Imperative Checks

Use the `Evaluate` dependency to check permissions inside a handler body without
raising — for branching logic, partial responses, or explicit control:

```python
from fastapi_has_permissions import Evaluate


@app.get("/posts")
async def list_posts(evaluate: Evaluate):
    if await evaluate.check(IsAdmin()):
        return all_posts()

    return public_posts()
```

`evaluate(perm)` returns the raw `CheckResult`, `evaluate.check(perm)` returns a
`bool`, and `evaluate.require(perm)` raises the permission's HTTP error on failure.

Outside a request (e.g. in unit tests), the module-level `evaluate()` resolves
dependencies against a fresh scope — combine it with
`fastapi_injected.push_overrides` to stub them:

```python
from fastapi_has_permissions import evaluate
from fastapi_injected import push_overrides

with push_overrides({get_role: "admin"}):
    assert await evaluate(HasAdminRole())
```

### Error Model

- Permissions raise **403** by default; authentication-style permissions can set
  `default_exc_status_code = 401` and `default_exc_headers = {"WWW-Authenticate": "Bearer"}`
  (the built-in `IsAuthenticated` does exactly this)
- Set a machine-readable **error code** (`code=...` / `default_exc_code`) to get a
  structured body: `{"detail": {"code": "not_admin", "message": "Admin role required"}}`;
  without a code the body stays a plain string
- All of message, status code, code, and headers propagate through `&`, `|`, `~`
- A permission's own error config applies when it is the root of the tree; use `WithError(...)`
  to give a nested subtree one error (e.g. a `404` that does not admit the resource exists)

### Other Features

- **Custom error responses** -- set `default_exc_message` / `default_exc_status_code` /
  `default_exc_code` / `default_exc_headers` class variables or the corresponding
  `message` / `status_code` / `code` / `headers` init parameters
- **Skip / Fail helpers** -- call `skip()` or `fail()` inside `check_permissions()` for explicit control flow
- **Wrappers** -- `AllowSkipped` / `DenySkipped` / `Advisory` rewrite a check's result, `WithError`
  gives a whole subtree one error config, `FailOnExc` / `SkipOnExc` keep a broken check from
  turning into a 500
- **Built-in common permissions** -- `IsAuthenticated`, `HasScope`, `HasRole` ready to use with your auth dependencies
- **Full FastAPI DI support** -- `check_permissions()` accepts any FastAPI-injectable parameters
- **Built on [fastapi-injected](https://github.com/uriyyo/fastapi-injected)** -- `Dep` / `DepFactory` are
  re-exported from it, and lazy permissions resolve through its inject scope, so they share the request's
  dependency cache with the route
