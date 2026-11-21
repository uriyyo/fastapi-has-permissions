from dataclasses import field
from typing import Any

import pytest
from fastapi import Depends

from fastapi_has_permissions import Dep, Given, Permission, PermissionWrapper, evaluate

from .type_checking_perms import HasRoleTypeCheckingDep

pytestmark = pytest.mark.asyncio


class IsOne(Permission):
    value_dep: Dep[int]

    async def check_permissions(self, value: int, /) -> bool:
        return value == 1


class IsOneBundle(PermissionWrapper):
    value_dep: Dep[int]
    permission: Permission = field(init=False)

    def __post_init__(self) -> None:
        self.permission = IsOne(self.value_dep)


async def _admin() -> str:
    return "admin"


@pytest.mark.parametrize(("value", "expected"), [(1, True), (2, False)])
async def test_a_wrapper_with_dep_fields_hands_them_to_what_it_wraps(value: int, expected: bool) -> None:  # noqa: FBT001
    assert await evaluate.check(IsOneBundle(Given(value))) is expected


@pytest.mark.parametrize("dep", [Given("admin"), Depends(_admin)])
async def test_a_type_checking_only_dep_annotation_is_read_from_the_value(dep: Any) -> None:
    permission = HasRoleTypeCheckingDep(dep)

    assert [*permission.__deps__()] == [dep]
    assert await evaluate.check(permission)
