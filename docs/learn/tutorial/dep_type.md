# The Dep Type

The `Dep` type allows you to pass FastAPI dependencies as constructor arguments to permission classes.
This makes permissions reusable across different contexts where the same logical check applies to
different data sources.

## What Is `Dep`?

`Dep` is re-exported from [`fastapi-injected`](https://github.com/uriyyo/fastapi-injected), where it is
defined as `Annotated[T, Depends()]`. When a permission class has a field typed as `Dep[T]`, the library
treats it as a FastAPI dependency that should be resolved at request time. The resolved value is passed
as a positional argument to `check_permissions`.

The bare `Depends()` in the annotation is what marks the field as a *slot* you fill in at construction
time. An ordinary `Annotated[T, Depends(some_func)]` field is not a slot -- it already names its
dependency, so FastAPI resolves it on its own.

`Dep` accepts a type argument to indicate the expected resolved type:

- `Dep[HasWorkspaceID]` -- a dependency that resolves to a `HasWorkspaceID`-compatible object
- `Dep[str]` -- a dependency that resolves to a `str`
- `Dep[Any]` -- a dependency with no specific type (equivalent to bare `Dep`)

## Example: Shared Workspace Check

Consider a permission that checks whether the current user belongs to the same workspace as a resource.
Different resources (articles, comments, files) all have a `workspace_id`, but they're loaded by
different dependencies:

```python
from typing import Annotated, Protocol
from uuid import UUID

from fastapi import Depends, Path

from fastapi_has_permissions import Dep, Permission


class HasWorkspaceID(Protocol):
    workspace_id: UUID


# Dependencies for loading different resources
async def get_article(article_id: Annotated[UUID, Path()]) -> Article:
    return await db.get(Article, article_id)


async def get_comment(comment_id: Annotated[UUID, Path()]) -> Comment:
    return await db.get(Comment, comment_id)


# A single permission class that works with any resource
class BelongsToSameWorkspace(Permission):
    resource_dep: Dep[HasWorkspaceID]  # the dependency that provides the resource

    async def check_permissions(self, resource: HasWorkspaceID, /, current_user: CurrentUserDep) -> bool:
        return resource.workspace_id == current_user.workspace_id
```

!!! note

    The `resource` parameter is a positional argument (`/` separates positional from keyword arguments).
    It receives the resolved value of `resource_dep`. Keyword arguments after `/` are resolved
    via FastAPI's standard DI.

## Using `Dep` with Different Resources

Now you can reuse the same permission with different dependencies by passing them at construction time:

```python
from fastapi import APIRouter, Depends

ArticleDep = Annotated[Article, Depends(get_article)]
CommentDep = Annotated[Comment, Depends(get_comment)]

article_router = APIRouter(
    prefix="/articles",
    dependencies=[Depends(BelongsToSameWorkspace(ArticleDep))],
)

comment_router = APIRouter(
    prefix="/comments",
    dependencies=[Depends(BelongsToSameWorkspace(CommentDep))],
)
```

Both routers use the same `BelongsToSameWorkspace` permission, but each provides a different dependency
to load the resource.

## Building Dependencies With `DepFactory`

`DepFactory` is also re-exported from `fastapi-injected` and is a shorthand for building the annotated
dependencies you pass into `Dep` slots -- `DepFactory[T, func]` is exactly `Annotated[T, Depends(func)]`:

```python
from fastapi_has_permissions import DepFactory

ArticleDep = DepFactory[Article, get_article]
CommentDep = DepFactory[Comment, get_comment]

article_router = APIRouter(
    prefix="/articles",
    dependencies=[Depends(BelongsToSameWorkspace(ArticleDep))],
)
```

Any form FastAPI understands works in a `Dep` slot -- `DepFactory[...]`, a plain
`Annotated[T, Depends(func)]`, or a bare `Depends(func)`.

## Multiple `Dep` Fields

A permission can have multiple `Dep` fields. Each one is resolved and passed as a positional argument
to `check_permissions` in the order they're declared:

```python
class BothInSameWorkspace(Permission):
    source_dep: Dep[HasWorkspaceID]
    target_dep: Dep[HasWorkspaceID]

    async def check_permissions(self, source: HasWorkspaceID, target: HasWorkspaceID, /) -> bool:
        return source.workspace_id == target.workspace_id
```

## Dependencies That May Not Resolve

A `Dep` field is resolved at check time, so a route where it cannot be resolved does not have to
fail -- wrap the permission to abstain instead:

```python
from fastapi.exceptions import RequestValidationError

from fastapi_has_permissions import Dep, Permission, SkipOnExc


class BelongsToSameWorkspace(Permission):
    resource_dep: Dep[HasWorkspaceID]

    async def check_permissions(self, resource: HasWorkspaceID, /, current_user: CurrentUserDep) -> bool:
        return resource.workspace_id == current_user.workspace_id


graceful = SkipOnExc(BelongsToSameWorkspace(ArticleDep), (RequestValidationError,))
```

Now the check is skipped when the dependency can't be resolved (e.g., on list endpoints without a
path parameter). See [Deferred Resolution](deferred_resolution.md).

!!! warning

    The order of `Dep` fields in the class corresponds to the order of positional arguments
    in `check_permissions`. Make sure they match.
