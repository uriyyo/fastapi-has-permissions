# Policies

A `Policy` groups the rules for one resource in one place, the way Pundit policies or
Bodyguard policy modules do. Each action is an ordinary permission, and the request method
decides which one runs.

```python
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Path

from fastapi_has_permissions import DepFactory, Policy, Requires, add_permissions
from fastapi_has_permissions.common import Allow, HasRole


async def get_post(post_id: Annotated[int, Path()]) -> Post:
    return await db.get(Post, post_id)


async def get_role(x_role: Annotated[str, Header()] = "guest") -> str:
    return x_role


PostDep = DepFactory[Post, get_post]
RoleDep = DepFactory[str, get_role]


class PostPolicy(Policy[Post]):
    read = Allow()
    create = HasRole(RoleDep, "author")
    update = HasRole(RoleDep, "author")
    delete = HasRole(RoleDep, "admin")

    __resource__ = PostDep
```

Two things are being declared: the **actions**, which are permissions, and `__resource__`,
the dependency that loads the object the policy is about.

## How a request picks an action

| Request method         | Action    |
| ---------------------- | --------- |
| `GET`, `QUERY`, `HEAD` | `read`    |
| `POST`                 | `create`  |
| `PUT`, `PATCH`         | `update`  |
| `DELETE`               | `delete`  |
| anything else          | `default` |

All five default to `Deny()`. A policy that declares nothing denies everything, including
methods you never thought about -- an unmapped verb falls to `default`, not through the net.
Declare only what you want to open.

## Using a policy

### As a gate

Attach the policy as a dependency and it checks the request, nothing more:

```python
@app.get("/posts/{post_id}", dependencies=[Depends(PostPolicy())])
async def read(post_id: int) -> Post: ...
```

### On a router -- one policy for a whole resource

This is what the method mapping is for. Attach the policy once to the router and every route
under it is covered by the action matching its verb:

```python
posts = APIRouter(prefix="/posts", dependencies=[Depends(PostPolicy())])


@posts.get("")  # -> read
async def list_posts() -> list[Post]: ...


@posts.post("")  # -> create
async def create_post(body: PostIn) -> Post: ...


@posts.get("/{post_id}")  # -> read
async def get_post(post_id: int) -> Post: ...


@posts.put("/{post_id}")  # -> update
async def update_post(post_id: int, body: PostIn) -> Post: ...


@posts.delete("/{post_id}")  # -> delete
async def delete_post(post_id: int) -> None: ...


app.include_router(posts)
```

One line of authorization for the whole resource, and the rules live in one place instead of
being restated on five routes.

The reason this is safe rather than merely convenient:

- **New routes are covered the moment they are added.** A `PATCH` added next month maps to
  `update` without anyone remembering to attach a permission -- and a verb with no action
  falls to `default`, which denies. You cannot add an unprotected route to this router by
  forgetting something.
- **A gate never resolves `__resource__`.** `GET /posts` and `GET /posts/{post_id}` run the
  same `read` action, but the collection route is never asked for a `post_id` it does not
  have. Attaching something that loaded the object would break the list route.

Object-level checks still compose on top: keep the router-level gate for the coarse rule and
add `Requires` on the routes that operate on a single object.

```python
@posts.get("/{post_id}")
async def get_post(post: Annotated[Post, Depends(Requires(PostPolicy()))]) -> Post:
    return post
```

The same policy runs twice here -- once as the router gate, once inside `Requires` -- which
is cheap, since the action is the same object and the resource resolves once per request.

The same works at app level, for a rule that covers everything:

```python
app = FastAPI(dependencies=[Depends(SessionPolicy())])
add_permissions(app)
```

!!! warning

    `add_permissions()` has to run **before** the routes are declared -- FastAPI copies
    router dependencies into each route at registration time.

### With `Requires` -- check _and_ inject

`Requires` runs the check and then hands the loaded resource to your handler:

```python
@app.get("/posts/{post_id}")
async def read(post: Annotated[Post, Depends(Requires(PostPolicy()))]) -> Post:
    # if we got here the check passed, and `post` is already loaded
    return post
```

Two properties worth stating outright:

- **The check cannot be skipped.** The permission is resolved before the resource, and both
  before the handler body runs. There is no way to forget to call it.
- **The resource is loaded once.** It is resolved through the request's inject scope, so
  several `Requires` on one route share a single load.

`Requires(...)` returns a dependency callable, so it goes inside `Depends(...)`.

## Actions beyond CRUD

Not every action is an HTTP verb. Declare it on the policy like any other, then name it at
the call site:

```python
class PostPolicy(Policy[Post]):
    read = Allow()
    publish = HasRole(RoleDep, "editor")

    __resource__ = PostDep


@app.post("/posts/{post_id}/publish")
async def publish(post: Annotated[Post, Depends(Requires(PostPolicy(), PostPolicy.publish))]) -> Post:
    return post
```

Naming an action replaces the method mapping -- this route is `publish`, not `create`,
even though it is a `POST`. Because actions are plain attributes, `PostPolicy.publish` is
just a reference: your editor can jump to it and a typo is an `AttributeError` at import.

## The four forms of `Requires`

| Call                                 | Resource                    | Check           |
| ------------------------------------ | --------------------------- | --------------- |
| `Requires(policy)`                   | the policy's `__resource__` | method dispatch |
| `Requires(policy, permission)`       | the policy's `__resource__` | that permission |
| `Requires(resource_dep, policy)`     | `resource_dep`              | method dispatch |
| `Requires(resource_dep, permission)` | `resource_dep`              | that permission |

The last form needs no policy at all, so object-level checks are available to plain
permissions too:

```python
async def read(post: Annotated[Post, Depends(Requires(PostDep, IsAuthenticated(AuthDep)))]) -> Post: ...
```

## Declaring `__resource__`

`__resource__` is a dependency: a `DepFactory[...]`, an `Annotated[..., Depends(...)]`, or a
plain callable. Left undeclared it resolves to `None`, which is fine for a policy you only
ever use as a gate.

### Reusing rules against another loader

`bind()` returns a subclass with a different `__resource__` and the same actions:

```python
DraftPolicy = PostPolicy.bind(DepFactory[Post, get_draft])


@app.get("/drafts/{post_id}")
async def draft(post: Annotated[Post, Depends(Requires(DraftPolicy()))]) -> Post:
    return post
```

The original policy is untouched.

### Overriding one action

Subclassing inherits every action and `__resource__`:

```python
class ModeratedPostPolicy(PostPolicy):
    delete = HasRole(RoleDep, "moderator")
```

## Things to know

### Actions are ordinary permissions

Everything you already know keeps working -- composition, the wrappers, custom error config:

```python
class PostPolicy(Policy[Post]):
    update = IsAuthenticated(AuthDep) & HasRole(RoleDep, "author")
    delete = HasRole(RoleDep, "admin") | HasRole(RoleDep, "owner")
    create = WithError(HasRole(RoleDep, "author"), message="Only authors may post", code="not_an_author")
```

An action's `message` / `status_code` / `code` / `headers` reach the client unchanged, a
`skip()` reaching the root denies, and `auto_error=False` suppresses the raise -- the same
as when the permission is used through `Depends` directly.

### Pass a policy instance, not the class

`Requires(PostPolicy)` raises `TypeError`. The policy has to be constructed, because the
instance is what FastAPI resolves.

### Permission parameters do not appear in OpenAPI

A policy resolves its actions through the inject scope rather than declaring them as
sub-dependencies. Checks are still enforced, but a header a permission requires will not be
documented in the schema, and generated clients will not know to send it.

### `from __future__ import annotations`

Do not use it in a module that defines permissions. It turns annotations into strings, and
`Dep` fields are recognised by their annotation -- with it, they stop being detected as
dependencies at all. This applies to permissions generally, not just to policies.
