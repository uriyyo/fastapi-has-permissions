# Lazy Permissions

Lazy permissions defer dependency resolution until the permission is actually checked at request time.
This is useful when a permission depends on a resource that may not always be available or valid.

## The Problem

Consider a permission that checks if the current user owns a specific resource. The resource is loaded
from a database using a path parameter:

```python
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Path

from fastapi_has_permissions import Permission


async def get_article(article_id: Annotated[UUID, Path()]) -> Article:
    return await db.get(Article, article_id)


class IsArticleAuthor(Permission):
    async def check_permissions(
        self,
        article: Annotated[Article, Depends(get_article)],
        current_user: CurrentUserDep,
    ) -> bool:
        return article.author_id == current_user.id
```

This works for routes like `GET /articles/{article_id}`, but what about `GET /articles` (list endpoint)?
There's no `article_id` path parameter, so the dependency resolution fails with a `RequestValidationError`.

## `lazy()` -- Defer Resolution

The `lazy()` function wraps a permission to defer its dependency resolution. Combined with `skip_on_exc`,
it can gracefully skip the check when dependencies can't be resolved:

```python
from fastapi.exceptions import RequestValidationError

from fastapi_has_permissions import lazy

lazy_author_check = lazy(
    IsArticleAuthor(),
    skip_on_exc=(RequestValidationError,),
)
```

Now you can safely use this permission on a router that includes both list and detail endpoints:

```python
from fastapi import APIRouter, Depends

router = APIRouter(
    prefix="/articles",
    dependencies=[Depends(lazy_author_check)],
)


@router.get("")
async def list_articles():
    # IsArticleAuthor is skipped (no article_id param)
    return await db.list(Article)


@router.get("/{article_id}")
async def get_article(article_id: UUID):
    # IsArticleAuthor is evaluated normally
    return await db.get(Article, article_id)
```

## `LazyPermission` Base Class

Instead of wrapping with `lazy()`, you can subclass `LazyPermission` directly:

```python
from dataclasses import dataclass

from fastapi_has_permissions import LazyPermission


@dataclass
class IsArticleAuthor(LazyPermission):
    async def check_permissions(
        self,
        article: Annotated[Article, Depends(get_article)],
        current_user: CurrentUserDep,
    ) -> bool:
        return article.author_id == current_user.id
```

`LazyPermission` instances automatically defer dependency resolution. You can set `skip_on_exc` as a
class-level default:

```python
from dataclasses import field

from fastapi.exceptions import RequestValidationError

from fastapi_has_permissions import LazyPermission
from fastapi_has_permissions.types import Exceptions


class GracefulLazyPermission(LazyPermission):
    """Base class that skips on validation errors."""
    skip_on_exc: Exceptions = field(default=(RequestValidationError,), kw_only=True)


class IsArticleAuthor(GracefulLazyPermission):
    async def check_permissions(self, article: ArticleDep, user: UserDep) -> bool:
        return article.author_id == user.id
```

## `lazy()` as a Decorator

You can also use `lazy()` as a class decorator:

```python
from fastapi_has_permissions import Permission, lazy


@lazy
class IsArticleAuthor(Permission):
    async def check_permissions(self, article: ArticleDep, user: UserDep) -> bool:
        return article.author_id == user.id
```

Or with `skip_on_exc`:

```python
@lazy(skip_on_exc=(RequestValidationError,))
class IsArticleAuthor(Permission):
    async def check_permissions(self, article: ArticleDep, user: UserDep) -> bool:
        return article.author_id == user.id
```

## Usage with Composition

Lazy permissions work with boolean composition:

```python
from fastapi import APIRouter, Depends

from fastapi_has_permissions import lazy

router = APIRouter(
    prefix="/articles",
    dependencies=[
        Depends(
            IsEditor()
            | lazy(IsArticleAuthor(), skip_on_exc=(RequestValidationError,))
            | (IsTeamLead() & lazy(BelongsToSameTeam(), skip_on_exc=(RequestValidationError,)))
        ),
    ],
)
```

This means: allow access if the user is an editor, **or** if they authored the article, **or** if they're
a team lead and the article belongs to their team. On list endpoints where the article can't
be loaded, the lazy checks are skipped and only `IsEditor()` and `IsTeamLead()` are evaluated.

!!! tip

    Lazy permissions are essential for router-level permission declarations where the same
    permission set applies to both collection and resource endpoints.
