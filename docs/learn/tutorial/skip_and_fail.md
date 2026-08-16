# Skip & Fail Helpers

`fastapi-has-permissions` provides helper functions and result types for explicit control over
the permission check flow.

## `fail()` -- Explicitly Deny

Call `fail()` inside `check_permissions` to immediately deny the permission with a custom message:

```python
from fastapi import Request

from fastapi_has_permissions import Permission, fail


class HasValidToken(Permission):
    async def check_permissions(self, request: Request) -> bool:
        token = request.headers.get("Authorization")

        if token is None:
            fail("Authorization header is required")

        if not token.startswith("Bearer "):
            fail("Token must use Bearer scheme")

        return True
```

`fail()` raises a `PermissionCheckFailed` exception internally. The library catches it and converts
it into a `Failed` result with the provided reason. The reason is used as the HTTP exception detail.

!!! note

    `fail()` has a return type of `NoReturn`, so the code after it is unreachable.
    Your type checker will correctly understand that control flow stops at `fail()`.

## `skip()` -- Skip the Check

Call `skip()` inside `check_permissions` to skip the permission check entirely. A skipped permission
is treated as if it was never checked, so the other permissions of a composition decide the outcome.
It is an abstention, not an approval -- a skip that reaches the root of a permission tree denies the
request unless you wrap it into [`AllowSkipped`](#allowskipped----opt-into-skip-means-allow):

```python
from fastapi import Request

from fastapi_has_permissions import Permission, skip


class RequiresTokenIfPresent(Permission):
    """Only validates the token if it's provided. Skips otherwise."""

    async def check_permissions(self, request: Request) -> bool:
        if "Authorization" not in request.headers:
            skip("No token provided, skipping validation")

        return request.headers["Authorization"] == "Bearer valid-token"
```

`skip()` raises a `SkipPermissionCheck` exception internally. The library catches it and returns
a `Skipped` result.

## Result Types

You can also return `Failed` and `Skipped` instances directly instead of using the helper functions:

```python
from fastapi_has_permissions import CheckResult, Failed, Permission, Skipped


class MyPermission(Permission):
    async def check_permissions(self, request: Request) -> CheckResult:
        token = request.headers.get("Authorization")

        if token is None:
            return Skipped(reason="No token, skipping")

        if token != "Bearer valid":
            return Failed(reason="Invalid token")

        return True
```

### `CheckResult` Type

`CheckResult` is a type alias for `bool | Skipped | Failed`:

| Value | Meaning |
|-------|---------|
| `True` | Permission granted |
| `False` | Permission denied (uses default or class-level message) |
| `Failed(reason="...")` | Permission denied with a specific message |
| `Skipped(reason="...")` | Permission check skipped entirely |

## Type Guards

Use `is_failed()` and `is_skipped()` to check the result type:

```python
from fastapi_has_permissions import is_failed, is_skipped


result = await some_permission.check_permissions()

if is_skipped(result):
    print("Permission was skipped")
elif is_failed(result):
    print(f"Permission failed: {result.reason}")
```

These are `TypeIs` guards, so your type checker will narrow the type after the check.

## Reading a Result

Two helpers cover what is otherwise an `isinstance` check. `get_reason()` returns whatever
explanation a result carries, and `as_failed()` gives you the `Failed` to propagate:

```python
from fastapi_has_permissions import as_failed, get_reason

get_reason(Skipped(reason="no opinion"))   # "no opinion"
get_reason(Failed(reason="denied"))        # "denied"
get_reason(True)                           # None -- a bare boolean explains nothing

as_failed(Failed(reason="denied"))         # the failure it already carries
as_failed(Skipped())                       # an empty `Failed`
as_failed(Skipped(), Failed(code="gone"))  # the fallback, for results carrying no failure
```

They are most useful in a [custom wrapper](wrappers.md#custom-wrappers), where a
`__map_result__` has to handle every kind of result:

```python
class Quieted(ResultMapper):
    def __map_result__(self, result: CheckResult, /) -> CheckResult:
        if is_failed(result):
            return Skipped(reason=get_reason(result))

        return result
```

## Where a Result Came From

A denial in a tree of rules says little on its own. Every `Failed` and `Skipped` carries a
`source` -- the branch that produced it, rendered as the decision it made:

```python
result = await evaluate(
    When(IsTeacherActor(), OwnsStudent(Given(student_id)))
    | When(IsStudentActor(), StudentIsSelf(Given(student_id)))
)

print(result.source)
# OwnsStudent[failed: student 42 is not yours]
#   | When(IsStudentActor[failed: Permission denied])[skipped: Permission denied]
```

Each entry is `Name[outcome]`, or `Name[outcome: reason]` where there is a reason to give.
Branches joined by `|` and `&` render as a chain, so a trace shows what ran and what each
branch decided:

```
IsStudent[failed: not a student] | IsTeacher[skipped: not applicable]
Allow[success] & IsStudent[failed: not a student]
Advisory(IsStudent[failed: not a student])[skipped: not a student]
```

Because `&` short-circuits, its chain stops at the first failure -- what you see is what ran.

The same trace reaches the raised
[`PermissionDeniedError`](custom_errors.md#the-error-a-denial-raises) as `exc.source`, which is
usually where you want it:

```python
except PermissionDeniedError as exc:
    log.warning("denied: %s", exc.source)
```

!!! note

    A source is diagnostic, so it takes no part in equality -- two denials of the same kind
    compare equal however the tree arrived at them. Set `__trace_name__` on a permission to
    report it under a friendlier name than its class.

## How Skip Interacts with Composition

Skipped permissions have special behavior when combined with `&` and `|`:

### AND (`&`)

| Scenario | Result |
|----------|--------|
| All skip | `Skipped` |
| Skip + Pass | Pass |
| Skip + Fail | Fail |

```python
# If AlwaysSkip skips, the AND result depends on the other permission
Depends(AlwaysSkip() & HasAuthorizationHeader())
# With auth header: 200 OK (skip is ignored, other passes)
# Without auth header: 403 Forbidden (skip is ignored, other fails)
```

### OR (`|`)

| Scenario | Result |
|----------|--------|
| All skip | `Skipped` |
| Skip + Pass | Pass |
| Skip + Fail | Fail |

```python
# If AlwaysSkip skips, the OR result depends on non-skipped permissions
Depends(AlwaysSkip() | HasAdminRole())
# With admin role: 200 OK (at least one passes)
# Without admin role: 403 Forbidden (non-skipped permission fails)
```

### NOT (`~`)

| Scenario | Result |
|----------|--------|
| Skip | `Skipped` (passthrough) |

```python
# Negating a skipped permission still skips
Depends(~AlwaysSkip())
# Always: 403 Forbidden (skip passes through and is denied at the root)
```

## Skip at the Root Is a Denial

A skip means "this check has no opinion". Inside a composition another permission can still
decide the outcome, but if the skip reaches the **root** of the tree -- the permission passed to
`Depends()` or to `evaluator.require()` -- there is nothing left to decide, so the request is
denied with the permission's regular error configuration:

```python
# skips when no Authorization header is present -> 403 Forbidden
Depends(RequiresTokenIfPresent())

# every branch skipped -> nothing decided -> 403 Forbidden
Depends(RequiresTokenIfPresent() & AlsoSkips())
```

This is the safe default: a check that never ran cannot grant access.

## `AllowSkipped` -- Opt Into Skip-Means-Allow

Wrap a permission into `AllowSkipped` to declare explicitly that an abstention grants access.
It turns a `Skipped` result into a successful one and leaves every other result untouched:

```python
from fastapi import Depends

from fastapi_has_permissions import AllowSkipped

# skipped -> 200 OK, failed -> 403 Forbidden
Depends(AllowSkipped(RequiresTokenIfPresent()))
```

`AllowSkipped` is a regular permission, so it composes like any other one and can be applied to
a single branch instead of the whole tree:

```python
Depends(AllowSkipped(RequiresTokenIfPresent()) & IsAuthenticated())
```

Its counterparts `DenySkipped` and `Advisory` cover the other directions -- see
[Permission Wrappers](wrappers.md).

It also works with imperative evaluation:

```python
await evaluator.require(AllowSkipped(RequiresTokenIfPresent()))
```

!!! note

    `evaluate()` and `evaluator.check()` are observational and never raise -- `evaluate()` returns
    the `Skipped` result as is, and `check()` reports `False` for it. Only `require()` and the root
    of a dependency tree turn an abstention into a denial.
