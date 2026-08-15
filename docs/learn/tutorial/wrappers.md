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

from fastapi_has_permissions import FailOnExc, SkipOnExc

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

    Both wrappers only cover exceptions raised by `check_permissions` itself -- dependencies are
    resolved before the wrapper runs. Use [`lazy(..., skip_on_exc=...)`](lazy_permissions.md) for a
    dependency that cannot be resolved, and combine the two when you need both:

    ```python
    Depends(FailOnExc(lazy(HasEntitlement(), skip_on_exc=(RequestValidationError,)), (RedisError,)))
    ```

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
