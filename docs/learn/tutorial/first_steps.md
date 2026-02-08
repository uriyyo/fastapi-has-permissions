# First Steps

Here is a minimal example of using `fastapi-has-permissions` to protect a route:

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

Steps:

1. Import `Permission` from `fastapi_has_permissions`.
2. Create a class that inherits from `Permission` and implement the `check_permissions` method.
3. Instantiate the permission and pass it to `Depends()` in the route's `dependencies` list.

When a request is made to `/protected`:

- If the `Authorization` header is present, the route handler executes normally and returns `200 OK`.
- If the header is missing, `check_permissions` returns `False` and the library raises an `HTTPException`
  with status code `403 Forbidden`.

## How It Works

`Permission` subclasses integrate directly with FastAPI's dependency injection system. When you write
`Depends(HasAuthorizationHeader())`, the permission instance is called as a FastAPI dependency. It:

1. Resolves any parameters declared in `check_permissions` using FastAPI's DI (e.g., `Request`, `Header`, etc.).
2. Calls `check_permissions` with the resolved values.
3. If the result is `True`, the request proceeds.
4. If the result is `False`, an `HTTPException` is raised with status `403` and detail `"Permission denied"`.

!!! tip

    The `check_permissions` method supports any parameter that FastAPI can inject -- `Request`, `Header`,
    `Depends`, `Query`, `Path`, and more. This makes permission checks fully integrated with your
    existing FastAPI dependencies.
