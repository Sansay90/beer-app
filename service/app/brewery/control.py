"""Пивоварня того, кто спрашивает: её id, состояние и команды через агента — зависимость для роутеров."""
import asyncio
import uuid
from typing import Annotated

from fastapi import Depends

from ..auth.dependencies import CurrentUser, Viewer
from ..deps import DevicesDep, HubDep
from ..errors import AppError
from ..recipes.program import build_program, check_boil_items, check_program, program_steps
from ..schemas import Ok

COMMAND_TIMEOUT_S = 35                # агент сам ждёт пивоварню до 30 с — дольше значит, что агент пропал


class Brewery:
    """device_id — пивоварня пользователя (пока она у него одна) или None: гость или агент ещё ни разу
    не подключался. Тогда состояние — «не в сети», ограничения — по умолчанию, команды — 503."""

    def __init__(self, hub, device_id):
        self.hub = hub
        self.device_id = device_id

    def snapshot(self):
        return self.hub.snapshot(self.device_id)

    def limits(self):
        return self.hub.limits(self.device_id)

    async def run(self, name, not_found=None, **args):
        """Команда через агента: 400 — неверные данные, 404 — нет такого (not_found — текст), 502/504 — пивоварня
        не подтвердила или не ответила, 503 — агента нет на связи (hub.AgentOffline)."""
        try:
            async with asyncio.timeout(COMMAND_TIMEOUT_S):
                res = await self.hub.command(self.device_id, name, **args)
        except TimeoutError:
            raise AppError("пивоварня не ответила", 504) from None
        if not res.get("ok"):
            status = res.get("status") or 502
            raise AppError((status == 404 and not_found) or res.get("error") or "пивоварня не подтвердила команду",
                           status)
        return Ok()

    def check(self, recipe):
        """Invalid, если пивоварня программу рецепта не примет. Рецепт без программы сохранить можно (черновик,
        импорт) — загрузить в пивоварню нельзя."""
        check_boil_items(recipe)
        if program_steps(recipe):
            check_program(build_program("", recipe), self.limits())

    def loaded(self, recipe_id):
        """Этот рецепт загружен в пивоварню."""
        return ((self.snapshot().get("deviceRecipe") or {}).get("id")) == recipe_id

    async def recipe_changed(self, recipe_id, recipe):
        """Рецепт поправили: если он в пивоварне — агенту свежие названия шагов и закладок."""
        if self.loaded(recipe_id):
            await self.hub.notify(self.device_id, {"type": "program", "program": build_program(recipe_id, recipe)})

    async def recipe_deleted(self, recipe_id):
        if self.loaded(recipe_id):
            await self.hub.notify(self.device_id, {"type": "forget", "forget": recipe_id})


def user_device(user: CurrentUser, devices: DevicesDep) -> uuid.UUID | None:
    return devices.current(user.id)


def viewer_device(viewer: Viewer, devices: DevicesDep) -> uuid.UUID | None:
    return devices.current(viewer.id) if viewer is not None else None


def user_brewery(hub: HubDep, device_id: Annotated[uuid.UUID | None, Depends(user_device)]) -> Brewery:
    return Brewery(hub, device_id)


def viewer_brewery(hub: HubDep, device_id: Annotated[uuid.UUID | None, Depends(viewer_device)]) -> Brewery:
    return Brewery(hub, device_id)


UserBrewery = Annotated[Brewery, Depends(user_brewery)]
ViewerBrewery = Annotated[Brewery, Depends(viewer_brewery)]
