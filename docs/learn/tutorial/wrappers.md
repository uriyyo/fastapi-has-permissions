# Permission Wrappers

A wrapper is a permission that wraps another permission and adjusts its result. Wrappers are
regular permissions, so they compose with `&`, `|` and `~` and can be applied to a single branch
of a permission tree instead of the whole thing.

## Result Wrappers

`AllowSkipped`, `DenySkipped` and `Advisory` rewrite one kind of result into another:

| Wrapper | `True` | `Failed` | `Skipped` |
|---------|--------|----------|-----------|
| `AllowSkipped` | pass | fail | **pass** |
| `DenySkipped` | pass | fail | **fail** |
| `Advisory` | pass | **skip** | skip |

### `AllowSkipped` -- Skip Means Allow

A skip that reaches the root of a permission tree is denied. `AllowSkipped` declares explicitly
that an abstention grants access:

```python
from fastapi import Depends

from fastapi_has_permissions import AllowSkipped

Depends(AllowSkipped(RequiresTokenIfPresent()))
```

See [Skip & Fail Helpers](skip_and_fail.md) for the full skip semantics.

### `DenySkipped` -- Make a Branch Decide

Inside a composition a skip abstains, so the remaining permissions decide on their own:

```python
# the license check skips -> an admin gets in without a license
Depends(HasValidLicense() & IsAdmin())
```

`DenySkipped` removes that escape hatch -- the wrapped permission has to reach a decision, and a
skip is treated as a failure:

```python
Depends(DenySkipped(HasValidLicense(), message="License check unavailable") & IsAdmin())
```

### `Advisory` -- A Branch That Cannot Deny

`Advisory` is the mirror image: a failure becomes an abstention, so the permission can contribute
a success but can never deny the request on its own.

```python
# access is granted to admins, `IsInBetaCohort` can only help, never block
Depends(Advisory(IsInBetaCohort()) & IsAdmin())
```

## `When` -- Say a Rule Does Not Apply

`When(guard, permission)` answers a different question from the rest of this page: not *is access
granted*, but *does this rule have an opinion at all*. If the guard does not succeed the whole
branch skips, and the wrapped permission never runs:

```python
from fastapi_has_permissions import When

When(IsTeacherActor(), OwnsStudent(FromPath[UUID]))
```

This is what makes a rule set that serves several kinds of caller expressible. Because
[`|` ignores a skipped branch](boolean_composition.md), each branch abstains unless it applies,
and whichever one does applies decides:

```python
read = (
      When(IsTeacherActor(), OwnsStudent(FromPath[UUID]))
    | When(IsStudentActor(), StudentIsSelf(FromPath[UUID]))
    | When(IsCapabilityActor(), GrantCovers(FromPath[UUID]))
)
```

- a teacher is judged only by `OwnsStudent`, and a denial there is a real denial
- a student is judged only by `StudentIsSelf`
- a caller no branch claims skips every branch, and a skip at the root **denies**

That last point is the reason to reach for `When` rather than assembling something out of the
other combinators. The obvious spellings are wrong, and one of them is wrong in the dangerous
direction:

| Instead of | What happens when the guard fails |
| --- | --- |
| `~guard \| permission` | `~guard` **succeeds**, so the branch **allows** |
| `guard & permission` | a hard denial, so sibling branches never get their say |
| `Advisory(guard) & permission` | the guard abstains, and the rule runs anyway |

!!! note

    A guard that *skips* also makes the branch skip -- the wrapper asks whether the guard
    succeeded, not whether it failed. The guard's reason is carried onto the skip, so an
    abstention stays debuggable.

If "no branch applies" should mean allow rather than deny, that is
[`AllowSkipped`](#allowskipped-skip-means-allow) around the whole tree -- an explicit opt-in
rather than a default.

## `WithError` -- One Error for a Whole Subtree

Every permission reports its own message, status code, error code and headers, which is not always
what the caller should see. `WithError` gives an entire subtree a single error config, no matter
which permission inside of it denied:

```python
from fastapi import status

from fastapi_has_permissions import WithError

Depends(
    WithError(
        IsArticleAuthor() | IsEditor(),
        message="Not found",
        status_code=status.HTTP_404_NOT_FOUND,
    ),
)
```

This is the usual way to avoid leaking the existence of a resource -- a `403` tells the caller the
article exists, a `404` does not.

Fields that you do not set fall back to the failing permission's own values, so
`WithError(perm, status_code=404)` changes the status code and keeps the original reason.

!!! note

    Setting `message`/`status_code` directly on a permission only takes effect when that permission
    is the root of the tree. `WithError` rewrites the result itself, so it works at any depth.

## `FailOnExc` and `SkipOnExc` -- Handle Broken Checks

A permission that talks to a database, a cache or an authorization service can raise. Without a
wrapper that exception becomes a `500`:

```python
from redis.exceptions import RedisError

from fastapi_has_permissions import FailOnExc, SkipOnExc, SkipUnresolved

# the backend is down -> deny the request instead of failing the whole endpoint
Depends(FailOnExc(HasEntitlement(), (RedisError,)))

# the backend is down -> abstain and let the other permissions decide
Depends(SkipOnExc(IsInBetaCohort(), (RedisError,)) | IsAdmin())
```

`FailOnExc` reports its own error config, the exception is never exposed to the client:

```python
Depends(
    FailOnExc(
        HasEntitlement(),
        (RedisError,),
        message="Authorization backend unavailable",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    ),
)
```

Exceptions that are not listed are re-raised as usual.

!!! warning

    The error config you pass to a wrapper belongs to the wrapper itself, and -- like on any
    permission -- an explicit value on the **root** of the tree wins over the error the wrapped
    permission reported. A `FailOnExc(perm, (RedisError,), status_code=503)` used directly in
    `Depends()` therefore answers `503` for an ordinary denial of `perm` too. Nested in a
    composition it behaves as expected: the exception uses the wrapper's config and an ordinary
    denial keeps `perm`'s own error. Leave the config off (the failure then defaults to `403`) or
    nest the wrapper when the two have to differ.

!!! note

    Both wrappers cover the whole check -- resolving the wrapped permission's dependencies as
    well as running `check_permissions`. See
    [Deferred Resolution](deferred_resolution.md) for the dependency-cannot-be-resolved case.
    Nest them when the two failures should mean different things:

    ```python
    Depends(FailOnExc(SkipUnresolved(HasEntitlement()), (RedisError,)))
    ```

## `Undocumented` -- Keep a Check Out of the Schema

`add_permissions()` puts each route's permission requirements into the OpenAPI schema, which is
usually what you want -- a client cannot send a header it has not been told about. Occasionally it
is not: a check may read something callers are not meant to know exists, such as an internal
routing header or a break-glass token.

```python
from fastapi_has_permissions import Undocumented

Depends(Undocumented(HasBreakGlassToken()))
```

The check still runs and still denies; it just contributes nothing to the schema. Exclusion covers
the wrapped subtree only, so the rest of a composition documents itself as usual:

```python
# `x-public` is documented, the break-glass header is not
Depends(Undocumented(HasBreakGlassToken()) | HasPublicAccess())
```

!!! note

    This hides the requirement, it does not remove it. A caller who does not satisfy the check
    still gets a `403` -- they simply will not learn why from the schema.

## Custom Wrappers

`PermissionWrapper` is the base class for all of them. Subclass `ResultMapper` to rewrite a result,
or `ExcHandler` to turn an exception into one:

```python
from fastapi_has_permissions import CheckResult, ResultMapper, is_failed


class Inverted(ResultMapper):
    def __map_result__(self, result: CheckResult, /) -> CheckResult:
        if is_failed(result):
            return True

        return result
```
