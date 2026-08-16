from fastapi_has_permissions import Dep, Given, Resource

from .deps import (
    Doc,
    IsAdmin,
    Other,
    TypeOf,
    is_assignable_to,
    static_assert,
)

# `Given(value)` produces a `Dep` for the value's own type, so a literal the caller
# already has is spelled the same way as a request-bound marker
static_assert(is_assignable_to(TypeOf[Given("admin")], Dep[str]))
static_assert(is_assignable_to(TypeOf[Given(Doc())], Dep[Doc]))

# ... and it stays typed - a constant of one type is not a marker for another
static_assert(not is_assignable_to(TypeOf[Given("admin")], Dep[Doc]))
static_assert(not is_assignable_to(TypeOf[Given(Doc())], Dep[Other]))

# a `Given` is a dep like any other, so it is equally usable as a resource
static_assert(is_assignable_to(TypeOf[Given(Doc())], Resource[Doc]))
static_assert(not is_assignable_to(TypeOf[Given(Doc())], Resource[Other]))

# the value is not the marker, the same way `Dep[R]` is not an `R`
static_assert(not is_assignable_to(TypeOf[Given(Doc())], Doc))

# the whole point of the parametrisation: a literal of the wrong type is caught at the
# call site, which a bare `Depends(lambda: value)` cannot do
_owned = IsAdmin(Given("admin"))


def _negatives() -> None:
    IsAdmin(Given(Doc()))  # type: ignore[ty:invalid-argument-type]
    IsAdmin(Given(1))  # type: ignore[ty:invalid-argument-type]

    Given()  # type: ignore[ty:missing-argument]
    Given("admin", "extra")  # type: ignore[ty:too-many-positional-arguments]
