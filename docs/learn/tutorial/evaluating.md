# Evaluating Imperatively

`Depends(permission)` and [`Eval`](eval.md) both attach a permission to a route. Sometimes the
decision has to happen somewhere a route signature can't reach -- inside a service function, a
background job, a message handler or a CLI command. The evaluator is the imperative form of the
same check.

## The Evaluator

`PermissionEvaluator` has four methods:

| Method | Result |
| --- | --- |
| `evaluator(permission)` | the raw `CheckResult` |
| `evaluator.check(permission)` | `True` only if the check succeeded |
| `evaluator.require(permission)` | raises on failure, otherwise returns the `CheckResult` |
| `evaluator.filter(items, factory)` | the items whose permission succeeded |

You get one in three ways, and all three behave identically.

### Inside a Route

Ask for it as a dependency:

```python
from fastapi_has_permissions import Evaluate


@app.get("/dashboard")
async def dashboard(perms: Evaluate) -> dict:
    data = {"welcome": "Hello!"}

    if await perms.check(HasAdminRole()):
        data["admin_panel"] = "You have admin access"

    return data
```

### Anywhere Else

`evaluate` is a ready-made evaluator, so the same calls work at module level:

```python
from fastapi_has_permissions import evaluate

if not await evaluate.check(OwnsArticle(Given(article))):
    raise NotFoundError
```

Each bare call resolves in a scope of its own. That is fine for a single check, but a loop wants
a scope -- see below.

## Scopes

`evaluate.scope()` opens one scope for a block of checks. It does two things: it binds
dependencies to values you already have, and it gives every check inside the block a shared
dependency cache.

```python
async with evaluate.scope({ActorDep: actor}) as perms:
    await perms.require(OwnsStudent(Given(student_id)))

    if await perms.check(CanEditSeries(Given(series_id))):
        ...
```

### Binding Dependencies

The mapping overrides dependencies for the duration of the block. Keys may be the dependency
function or the annotated alias -- both resolve to the same dependency:

```python
ActorDep = Annotated[Actor, Depends(get_actor)]

async with evaluate.scope({ActorDep: actor}) as perms:  # same as {get_actor: actor}
    ...
```

This is what lets a rule written for HTTP run in a background job: the job supplies the actor
that a request would otherwise have provided.

### One Cache per Block

Every check inside the block shares one dependency cache, so a repository or session used by
several rules is resolved once rather than once per check:

```python
# three separate scopes -- the repository is resolved three times
for student in students:
    await evaluate.check(OwnsStudent(Given(student.id)))

# one scope -- resolved once
async with evaluate.scope({ActorDep: actor}) as perms:
    for student in students:
        await perms.check(OwnsStudent(Given(student.id)))
```

`filter` is the shorthand for exactly that loop:

```python
async with evaluate.scope({ActorDep: actor}) as perms:
    mine = await perms.filter(students, lambda student: OwnsStudent(Given(student.id)))
```

!!! note

    `filter` evaluates sequentially. Checks in one scope usually share a database session, and
    resolving them concurrently is not safe to assume.

### Inside a Request

A scope opened during a request inherits that request, so request-bound dependencies keep
resolving while your overrides still apply:

```python
@app.get("/report")
async def report(perms: Evaluate) -> dict:
    async with evaluate.scope({ActorDep: service_account}) as elevated:
        # `elevated` sees the same request, but acts as the service account
        ...
```

Pass `request=` to supply one explicitly instead.

## Raising Something Other Than `PermissionDeniedError`

`require` raises a [`PermissionDeniedError`](custom_errors.md#the-error-a-denial-raises) built from
the permission's error configuration. That already carries no HTTP with it, so a job or a worker
can simply catch it. When you would rather raise your own type, pass `on_failure`:

```python
async with evaluate.scope({ActorDep: actor}, on_failure=to_tool_error) as perms:
    await perms.require(OwnsStudent(Given(student_id)))  # raises ToolError
```

The factory receives the permission and the `Failed` result, which carries `reason`,
`status_code`, `code` and `headers` -- enough to preserve a `404`-not-`403` convention or an
application error code:

```python
def to_tool_error(permission: Permission, failed: Failed) -> Exception:
    if failed.code == "student_inactive":
        return StudentInactiveError(failed.reason)

    return ToolError(failed.reason or "Permission denied")
```

!!! tip

    `check` and the plain call never raise, so they need no mapping. Reach for `on_failure` only
    where you use `require`.
