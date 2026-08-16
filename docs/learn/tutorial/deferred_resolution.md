# Deferred Resolution

Every permission resolves its dependencies at check time, not when the route is declared.
A dependency is only paid for if the permission that needs it is actually reached, and a
permission whose dependencies cannot be resolved can decide what that means instead of
crashing the request.

## The Problem

Consider a permission that checks whether the current user owns a resource, loaded from a
path parameter:

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

This works for `GET /articles/{article_id}`, but not for `GET /articles` -- there is no
`article_id` there, so resolving `get_article` raises a `RequestValidationError`.

## `SkipOnExc` -- Abstain Instead of Failing

Wrap the permission to turn that failure into an abstention:

```python
from fastapi.exceptions import RequestValidationError

from fastapi_has_permissions import SkipOnExc

author_check = SkipOnExc(IsArticleAuthor(), (RequestValidationError,))
```

A skip that reaches the root of a permission tree is denied, so wrap the check in
`AllowSkipped` to let the list endpoint through:

```python
from fastapi import APIRouter, Depends

from fastapi_has_permissions import AllowSkipped

router = APIRouter(
    prefix="/articles",
    dependencies=[Depends(AllowSkipped(author_check))],
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

## What the Exception Wrappers Cover

`SkipOnExc` and `FailOnExc` cover the whole check -- both resolving the permission's
dependencies and running `check_permissions`.

| Failure | Result |
|---------|--------|
| A dependency cannot be resolved | handled by `SkipOnExc` / `FailOnExc` |
| `check_permissions` raises | handled by `SkipOnExc` / `FailOnExc` |

They nest, which is the usual choice when a permission both takes a path parameter and
talks to an external service -- a missing parameter abstains, a broken backend denies:

```python
from redis.exceptions import RedisError

from fastapi_has_permissions import FailOnExc

Depends(
    FailOnExc(
        SkipOnExc(IsArticleAuthor(), (RequestValidationError,)),
        (RedisError,),
        message="Authorization backend unavailable",
    ),
)
```

## Usage with Composition

Deferral applies at every depth, so a wrapped permission behaves the same nested inside a
composition as it does at the root:

```python
from fastapi import APIRouter, Depends

router = APIRouter(
    prefix="/articles",
    dependencies=[
        Depends(
            IsEditor()
            | SkipOnExc(IsArticleAuthor(), (RequestValidationError,))
            | (IsTeamLead() & SkipOnExc(BelongsToSameTeam(), (RequestValidationError,)))
        ),
    ],
)
```

This means: allow access if the user is an editor, **or** if they authored the article,
**or** if they are a team lead and the article belongs to their team. On list endpoints
where the article cannot be loaded, those checks abstain and only `IsEditor()` and
`IsTeamLead()` are evaluated. Because `|` short-circuits, a user who is an editor never
pays to load the article at all.

!!! note

    A permission's dependencies are resolved on demand rather than declared as route
    dependencies. That is what makes short-circuiting possible, and it is why a
    permission's parameters do not appear in the OpenAPI schema.
