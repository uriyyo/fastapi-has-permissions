# IsAuthenticated

`IsAuthenticated` is a built-in permission from `fastapi_has_permissions.common` that checks whether
the current user is authenticated.

## How It Works

`IsAuthenticated` takes a single `Dep` parameter -- a FastAPI dependency that returns a `bool`
indicating whether the user is authenticated.

```python
from fastapi_has_permissions.common import IsAuthenticated
```

## Example

```python
from typing import Annotated

from fastapi import Depends, FastAPI, Header

from fastapi_has_permissions.common import IsAuthenticated


async def get_is_authenticated(
    authorization: Annotated[str | None, Header()] = None,
) -> bool:
    return authorization is not None


app = FastAPI()


@app.get(
    "/protected",
    dependencies=[
        Depends(
            IsAuthenticated(
                Depends(get_is_authenticated),
            ),
        ),
    ],
)
async def protected():
    return {"message": "You have access!"}
```

The `Depends(get_is_authenticated)` dependency is resolved by FastAPI and its result (a `bool`)
is passed as a positional argument to `check_permissions`.

## How `check_permissions` Works

The implementation is straightforward:

```python
class IsAuthenticated(Permission):
    authentication_dep: Dep

    async def check_permissions(self, is_authenticated: bool, /) -> bool:
        return is_authenticated
```

The `authentication_dep: Dep` field tells the library to resolve this dependency and pass the result
as the first positional argument (`is_authenticated`).

## Combining with Other Permissions

`IsAuthenticated` supports boolean composition like any other permission:

```python
from fastapi_has_permissions.common import IsAuthenticated, HasRole


# Must be authenticated AND have admin role
Depends(
    IsAuthenticated(Depends(get_is_authenticated))
    & HasRole(Depends(get_role), roles=["admin"])
)
```

!!! tip

    For more complex authentication patterns (e.g., distinguishing between user types),
    consider creating a [custom class-based permission](../tutorial/class_based.md) instead.
