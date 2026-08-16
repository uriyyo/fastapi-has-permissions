# Real-World Usage Patterns

This page shows common patterns for using `fastapi-has-permissions` in production applications.

## Pattern 1: Define a Permission Module

Create a `permissions/` package in your application with reusable permission classes:

```
app/
    permissions/
        __init__.py
        common.py
        articles.py
    api/
        endpoints/
            articles.py
    auth/
        dependencies.py
```

### `permissions/common.py`

Define base permissions tied to your authentication system:

```python
from fastapi.exceptions import RequestValidationError

from fastapi_has_permissions import Permission, PermissionWrapper, SkipOnExc, WithError

from app.auth.dependencies import get_current_user, User

# Type alias for your auth dependency
from typing import Annotated
from fastapi import Depends, status

CurrentUserDep = Annotated[User, Depends(get_current_user)]


class IsAuthenticated(Permission):
    async def check_permissions(self, user: CurrentUserDep) -> bool:
        return user is not None


class IsAdmin(Permission):
    async def check_permissions(self, user: CurrentUserDep) -> bool:
        return user is not None and user.role == "admin"


class IsEditor(Permission):
    async def check_permissions(self, user: CurrentUserDep) -> bool:
        return user is not None and user.role in ("admin", "editor")


class HasServiceToken(Permission):
    async def check_permissions(self, request: Request) -> bool:
        token = request.headers.get("x-service-token")
        return token == settings.SERVICE_TOKEN


# Pre-composed permission: admin OR service token
class IsPrivilegedUser(PermissionWrapper):
    permission: Permission = IsAdmin() | HasServiceToken()


# Abstain instead of failing when a resource dependency cannot be resolved
def graceful(permission: Permission) -> Permission:
    return SkipOnExc(permission, (RequestValidationError,))


# Reusable policy: this subtree answers 404 instead of admitting the resource exists
def hidden(permission: Permission) -> Permission:
    return WithError(
        permission,
        message="Not found",
        status_code=status.HTTP_404_NOT_FOUND,
        code="not_found",
    )
```

### `permissions/articles.py`

Define resource-specific permissions:

```python
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Path

from fastapi_has_permissions import Permission
from fastapi_has_permissions.types import Dep

from app.db import AsyncSessionDep
from app.models import Article

from .common import CurrentUserDep


async def get_current_article(
    db: AsyncSessionDep,
    article_id: Annotated[UUID, Path()],
) -> Article:
    return await db.get(Article, article_id)


ArticleDep = Annotated[Article, Depends(get_current_article)]


class IsArticleAuthor(Permission):
    async def check_permissions(self, user: CurrentUserDep, article: ArticleDep) -> bool:
        return article.created_by == user.email


class BelongsToSameWorkspace(Permission):
    resource_dep: Dep

    async def check_permissions(self, resource: Any, /, user: CurrentUserDep) -> bool:
        return resource.workspace_id == user.workspace_id
```

## Pattern 2: Router-Level Permissions

Apply permissions at the router level so all endpoints under it are protected:

```python
from fastapi import APIRouter, Depends

from app.permissions.common import IsAuthenticated, IsPrivilegedUser

# All endpoints require authentication
router = APIRouter(
    prefix="/api/v1/users",
    dependencies=[Depends(IsAuthenticated())],
)

# All endpoints require admin or service token
admin_router = APIRouter(
    prefix="/api/v1/admin",
    dependencies=[Depends(IsPrivilegedUser())],
)
```

## Pattern 3: Two-Tier Router

Use a main router with basic auth and a sub-router with stricter permissions:

```python
from fastapi import APIRouter, Depends

from app.permissions.common import IsAuthenticated, IsPrivilegedUser

# Public-ish endpoints (just need auth)
router = APIRouter(
    prefix="/articles",
    dependencies=[Depends(IsAuthenticated())],
)


@router.get("")
async def list_articles(): ...


@router.get("/{article_id}")
async def get_article(article_id: UUID): ...


# Admin-only endpoints on the same prefix
admin_router = APIRouter(
    prefix="",
    dependencies=[Depends(IsPrivilegedUser())],
)


@admin_router.delete("/{article_id}")
async def delete_article(article_id: UUID): ...


@admin_router.post("/{article_id}/publish")
async def publish_article(article_id: UUID): ...


# Nest admin under main router
router.include_router(admin_router)
```

## Pattern 4: Complex Composed Permissions

Use boolean operators for resource-level access control, wrapping the checks whose resource
may not load:

```python
from fastapi import APIRouter, Depends

from app.permissions.common import IsPrivilegedUser, IsEditor, graceful
from app.permissions.articles import IsArticleAuthor, BelongsToSameWorkspace, ArticleDep

router = APIRouter(
    prefix="/articles",
    dependencies=[
        Depends(
            IsPrivilegedUser()
            | graceful(IsArticleAuthor())
            | (IsEditor() & graceful(BelongsToSameWorkspace(ArticleDep)))
        ),
    ],
)
```

This means access is granted if:

1. **`IsPrivilegedUser()`** -- user is an admin or has a service token, **OR**
2. **`IsArticleAuthor()`** -- user is the author of the article, **OR**
3. **`IsEditor() & BelongsToSameWorkspace(ArticleDep)`** -- user is an editor and the article belongs to their workspace

On list endpoints (`GET /articles`), the wrapped checks (`IsArticleAuthor`, `BelongsToSameWorkspace`)
abstain because the `article_id` path parameter doesn't exist. Only `IsPrivilegedUser()` and
`IsEditor()` are evaluated -- and because `|` short-circuits, a privileged user never pays to load
the article at all.

!!! warning

    If *every* branch could skip on a given endpoint, the request is denied -- a check that never
    ran cannot grant access. Either keep one non-skippable branch in the composition (as
    `IsPrivilegedUser()` is above), or wrap the whole thing into `AllowSkipped` to state that an
    abstention is fine there.

## Pattern 5: Hiding Resources Instead of Denying Them

Answering `403` on a resource endpoint tells the caller the resource exists. `WithError` gives the
whole ownership check a single `404`, no matter which permission inside of it denied:

```python
from fastapi import APIRouter, Depends, status

from fastapi_has_permissions import WithError

from app.permissions.articles import IsArticleAuthor, BelongsToSameWorkspace, ArticleDep
from app.permissions.common import IsEditor, IsPrivilegedUser

router = APIRouter(
    prefix="/articles",
    dependencies=[
        Depends(
            WithError(
                IsPrivilegedUser() | IsArticleAuthor() | (IsEditor() & BelongsToSameWorkspace(ArticleDep)),
                message="Not found",
                status_code=status.HTTP_404_NOT_FOUND,
                code="article_not_found",
            ),
        ),
    ],
)
```

An operator-built composition has nowhere to put an error config of its own -- `a | b` produces a
plain `AnyPermissions`. `WithError` supplies one from the outside, and since it rewrites the result
instead of the raised exception, it keeps working when the subtree is nested deeper in a larger
composition or evaluated imperatively with `evaluate()`.

## Pattern 6: Surviving a Broken Backend

A permission that reads from a cache, a database or an authorization service can raise. Left
unhandled, that exception turns every request into a `500`. Decide per permission whether it should
deny or abstain:

```python
from redis.exceptions import RedisError

from fastapi_has_permissions import Advisory, FailOnExc, SkipOnExc


# entitlements are load-bearing -> deny, and say why
class HasEntitlement(Permission):
    async def check_permissions(self, user: CurrentUserDep, cache: CacheDep) -> bool:
        return await cache.sismember(f"entitlements:{user.id}", "articles.write")


entitlement_check = FailOnExc(
    HasEntitlement(),
    (RedisError,),
    message="Authorization backend unavailable",
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
)

# the beta cohort is a bonus signal -> abstain and let the other permissions decide
beta_check = SkipOnExc(IsInBetaCohort(), (RedisError,))

router = APIRouter(
    prefix="/articles",
    dependencies=[Depends(entitlement_check & (IsEditor() | beta_check))],
)
```

`FailOnExc` reports its own error config, so the exception itself never reaches the client. Anything
not listed in the wrapper is re-raised unchanged, so real bugs still surface.

For a permission whose failure should never block a request on its own, `Advisory` turns the denial
into an abstention:

```python
# `IsInBetaCohort` can only grant access, never take it away
Depends(Advisory(IsInBetaCohort()) & IsAuthenticated())
```

## Pattern 7: Endpoint-Level Overrides

Add extra permissions to specific endpoints beyond what the router requires:

```python
from fastapi import APIRouter, Depends, status

from app.permissions.common import IsAuthenticated, HasServiceToken

router = APIRouter(
    prefix="/billing",
    dependencies=[Depends(IsAuthenticated())],
)


@router.get("/invoices")
async def list_invoices(): ...


@router.post(
    "/usage",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(HasServiceToken())],  # extra: must also have a service token
)
async def report_usage(): ...
```

## Summary

| Pattern | When to Use |
|---------|------------|
| Permission module | Always -- organizes permissions in one place |
| Router-level | Most endpoints share the same access rule |
| Two-tier router | Mix of public and admin endpoints on the same prefix |
| Complex composition | Resource ownership + workspace membership checks |
| `WithError` | The caller should not learn that a resource exists |
| `FailOnExc` / `SkipOnExc` | A check talks to a backend that can be down |
| Endpoint-level | Specific endpoint needs extra restrictions |
