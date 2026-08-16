from typing import Annotated, ClassVar

from fastapi import Header
from ty_extensions import static_assert
from ty_extensions._internal import (
    CallableTypeOf,
    TypeOf,
    is_assignable_to,
    is_equivalent_to,
    is_subtype_of,
)

from fastapi_has_permissions import Dep, DepFactory, Permission, Policy
from fastapi_has_permissions.common import Allow, Deny


class Doc:
    name: str


class Other:
    pass


async def get_doc(x_name: Annotated[str, Header()] = "doc") -> Doc:
    doc = Doc()
    doc.name = x_name
    return doc


async def get_role(x_role: Annotated[str, Header()] = "user") -> str:
    return x_role


DocDep = DepFactory[Doc, get_doc]
RoleDep = DepFactory[str, get_role]


class IsAdmin(Permission):
    role_dep: Dep[str]

    async def check_permissions(self, role: str, /) -> bool:
        return role == "admin"


class DocPolicy(Policy[Doc]):
    read: ClassVar[Permission] = Allow()
    publish: ClassVar[Permission] = Deny()

    __resource__ = DocDep


class OtherPolicy(Policy[Other]):
    read: ClassVar[Permission] = Allow()


__all__ = [
    "Allow",
    "CallableTypeOf",
    "Deny",
    "Doc",
    "DocDep",
    "DocPolicy",
    "IsAdmin",
    "Other",
    "OtherPolicy",
    "RoleDep",
    "TypeOf",
    "get_doc",
    "get_role",
    "is_assignable_to",
    "is_equivalent_to",
    "is_subtype_of",
    "static_assert",
]
