import inspect
from contextlib import suppress
from dataclasses import dataclass, field
from functools import cached_property, lru_cache, partial
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, TypeVar, cast, overload

from fastapi import BackgroundTasks, Request, Response, WebSocket, routing
from fastapi.dependencies import utils
from fastapi.dependencies.utils import get_typed_signature
from fastapi.exceptions import RequestValidationError

from ._bases import ForceDataclass
from ._permissions import Permission, PermissionWrapper
from ._resolvers import BaseResolvedPermission, PermissionResolver
from ._results import CheckResult, Skipped, SkipPermissionCheck
from .types import Exceptions

_DEPENDENCY_CACHE_KEY = "__fastapi_has_permissions_dependency_cache__"

if not TYPE_CHECKING:
    _base_solve_dependencies = utils.solve_dependencies

    async def _solve_dependencies(
        *,
        request: Request | WebSocket,
        **kwargs: Any,
    ) -> utils.SolvedDependency:
        solved = await _base_solve_dependencies(request=request, **kwargs)

        # cache the solved dependencies for the current request to avoid redundant computations
        request.scope[_DEPENDENCY_CACHE_KEY] = solved.dependency_cache

        return solved

    utils.solve_dependencies = _solve_dependencies
    routing.solve_dependencies = _solve_dependencies

_AnyRoute: TypeAlias = routing.APIRoute | routing.APIWebSocketRoute


@lru_cache(maxsize=1024)
def _resolver_to_dependant(path: str, resolver: PermissionResolver) -> utils.Dependant:
    return utils.get_dependant(
        path=path,
        call=resolver,
    )


async def _get_request_body(request: Request) -> Any:
    # TODO: add proper handling of json/body
    with suppress(Exception):
        return await request.json()

    with suppress(Exception):
        return await request.body()

    return None


async def _solve_dependencies_for_dependant(
    request: Request,
    response: Response,
    dependant: utils.Dependant,
) -> utils.SolvedDependency:
    route: _AnyRoute = request.scope["route"]
    astack = request.scope["fastapi_inner_astack"]

    dependency_cache = request.scope.get(_DEPENDENCY_CACHE_KEY, {})
    body = await _get_request_body(request)

    return await utils.solve_dependencies(
        request=request,
        dependant=dependant,
        body=body,
        dependency_cache=dependency_cache,
        background_tasks=cast("BackgroundTasks", response.background),
        response=response,
        dependency_overrides_provider=route.dependency_overrides_provider,
        async_exit_stack=astack,
        embed_body_fields=route._embed_body_fields,  # noqa: SLF001
    )


class LazyResolvedPermission(ForceDataclass, BaseResolvedPermission):
    permission: Permission
    request: Request
    response: Response
    skip_on_exc: Exceptions = ()

    @cached_property
    def _eager_resolver(self) -> PermissionResolver:
        return PermissionResolver(self.permission)

    async def check_permissions(self) -> CheckResult:
        try:
            return await self._check_permissions()
        except SkipPermissionCheck as e:
            return Skipped(reason=e.reason)
        except self.skip_on_exc:
            return Skipped()

    async def _check_permissions(self) -> CheckResult:
        route: _AnyRoute = self.request.scope["route"]
        dependant = _resolver_to_dependant(route.path, self._eager_resolver)

        solved = await _solve_dependencies_for_dependant(self.request, self.response, dependant)

        if solved.errors:
            raise RequestValidationError(solved.errors)

        final_permission = await self._eager_resolver(**solved.values)
        return await final_permission.check_permissions()


class LazyPermissionResolver(PermissionResolver):
    skip_on_exc: Exceptions = field(default=(), kw_only=True)

    def __get_signature__(self) -> inspect.Signature:
        return get_typed_signature(self.__call__)

    async def __call__(self, request: Request, response: Response) -> BaseResolvedPermission:
        return LazyResolvedPermission(
            permission=self.permission,
            request=request,
            response=response,
            skip_on_exc=self.skip_on_exc,
        )


@dataclass
class _HasSkipOnExc:
    skip_on_exc: Exceptions = field(default=(), kw_only=True)


class LazyPermission(_HasSkipOnExc, Permission):
    def __to_resolver__(self) -> LazyPermissionResolver:
        return LazyPermissionResolver(self, skip_on_exc=self.skip_on_exc)


class LazyPermissionWrapper(_HasSkipOnExc, PermissionWrapper):
    def __to_resolver__(self) -> LazyPermissionResolver:
        return LazyPermissionResolver(self.permission, skip_on_exc=self.skip_on_exc)


TCls = TypeVar("TCls", bound=type[Permission])
TPermission = TypeVar("TPermission", bound=Permission)


class _LazyDecorator(Protocol):
    @overload
    def __call__(self, arg: TCls, /) -> TCls:
        pass

    @overload
    def __call__(self, arg: TPermission, /) -> LazyPermissionWrapper:
        pass


@overload
def lazy(
    arg: None = None,
    /,
    *,
    skip_on_exc: Exceptions | None = None,
) -> _LazyDecorator:
    pass


@overload
def lazy(cls: TCls, /) -> TCls:
    pass


@overload
def lazy(
    permission: TPermission,
    /,
    *,
    skip_on_exc: Exceptions | None = None,
) -> LazyPermissionWrapper:
    pass


def lazy(
    arg: type[Permission] | Permission | None = None,
    /,
    *,
    skip_on_exc: Exceptions | None = None,
) -> type[Permission] | LazyPermissionWrapper | _LazyDecorator:
    if arg is None:
        return cast(
            "_LazyDecorator",
            partial(lazy, skip_on_exc=skip_on_exc),
        )

    if isinstance(arg, type):
        if issubclass(arg, LazyPermission):
            raise TypeError("Cannot apply @lazy to a subclass of LazyPermission")

        ns = {}
        if skip_on_exc is not None:
            ns["skip_on_exc"] = skip_on_exc

        return type(f"Lazy{arg.__name__}", (LazyPermission, arg), ns)

    return LazyPermissionWrapper(
        permission=arg,
        skip_on_exc=skip_on_exc or (),
    )


__all__ = [
    "LazyPermission",
    "LazyPermissionResolver",
    "lazy",
]
