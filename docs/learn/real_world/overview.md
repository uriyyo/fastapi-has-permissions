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
from dataclasses import field

from fastapi.exceptions import RequestValidationError

from fastapi_has_permissions import LazyPermission, Permission, PermissionWrapper
from fastapi_has_permissions.types import Exceptions

from app.auth.dependencies import get_current_user, User

# Type alias for your auth dependency
from typing import Annotated
from fastapi import Depends

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


# Base class for lazy permissions that skip on validation errors
class GracefulLazyPermission(LazyPermission):
    skip_on_exc: Exceptions = field(default=(RequestValidationError,), kw_only=True)
```

### `permissions/articles.py`

Define resource-specific permissions:

```python
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Path

from fastapi_has_permissions import LazyPermission
from fastapi_has_permissions.types import Dep

from app.db import AsyncSessionDep
from app.models import Article

from .common import CurrentUserDep, GracefulLazyPermission


async def get_current_article(
    db: AsyncSessionDep,
    article_id: Annotated[UUID, Path()],
) -> Article:
    return await db.get(Article, article_id)


ArticleDep = Annotated[Article, Depends(get_current_article)]


class IsArticleAuthor(GracefulLazyPermission, LazyPermission):
    async def check_permissions(self, user: CurrentUserDep, article: ArticleDep) -> bool:
        return article.created_by == user.email


class BelongsToSameWorkspace(GracefulLazyPermission):
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
async def list_articles():
    ...


@router.get("/{article_id}")
async def get_article(article_id: UUID):
    ...


# Admin-only endpoints on the same prefix
admin_router = APIRouter(
    prefix="",
    dependencies=[Depends(IsPrivilegedUser())],
)


@admin_router.delete("/{article_id}")
async def delete_article(article_id: UUID):
    ...


@admin_router.post("/{article_id}/publish")
async def publish_article(article_id: UUID):
    ...


# Nest admin under main router
router.include_router(admin_router)
```

## Pattern 4: Complex Composed Permissions

Use boolean operators and lazy permissions for resource-level access control:

```python
from fastapi import APIRouter, Depends

from app.permissions.common import IsPrivilegedUser, IsEditor
from app.permissions.articles import IsArticleAuthor, BelongsToSameWorkspace, ArticleDep

router = APIRouter(
    prefix="/articles",
    dependencies=[
        Depends(
            IsPrivilegedUser()
            | IsArticleAuthor()
            | (IsEditor() & BelongsToSameWorkspace(ArticleDep))
        ),
    ],
)
```

This means access is granted if:

1. **`IsPrivilegedUser()`** -- user is an admin or has a service token, **OR**
2. **`IsArticleAuthor()`** -- user is the author of the article, **OR**
3. **`IsEditor() & BelongsToSameWorkspace(ArticleDep)`** -- user is an editor and the article belongs to their workspace

On list endpoints (`GET /articles`), the lazy permissions (`IsArticleAuthor`, `BelongsToSameWorkspace`) are
skipped because the `article_id` path parameter doesn't exist. Only `IsPrivilegedUser()` and `IsEditor()`
are evaluated.

## Pattern 5: Endpoint-Level Overrides

Add extra permissions to specific endpoints beyond what the router requires:

```python
from fastapi import APIRouter, Depends, status

from app.permissions.common import IsAuthenticated, HasServiceToken

router = APIRouter(
    prefix="/billing",
    dependencies=[Depends(IsAuthenticated())],
)


@router.get("/invoices")
async def list_invoices():
    ...


@router.post(
    "/usage",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(HasServiceToken())],  # extra: must also have a service token
)
async def report_usage():
    ...
```

## Summary

| Pattern | When to Use |
|---------|------------|
| Permission module | Always -- organizes permissions in one place |
| Router-level | Most endpoints share the same access rule |
| Two-tier router | Mix of public and admin endpoints on the same prefix |
| Complex composition | Resource ownership + workspace membership checks |
| Endpoint-level | Specific endpoint needs extra restrictions |
