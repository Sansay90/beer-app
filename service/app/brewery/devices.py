"""Пивоварни пользователей: то, что сервису нужно и без агента на связи, — модель, ограничения, профиль."""
import logging

from sqlmodel import select

from ..db import session
from ..errors import Conflict, Forbidden
from ..models import Device

log = logging.getLogger("brewapp.devices")


class DeviceStore:
    def attach(self, agent, tuya_id, name, model=None, limits=None):
        """Агент сообщил, какую пивоварню обслуживает, — завести её или привязать к нему. Возвращает id пивоварни.
        Forbidden — пивоварня заведена у другого пользователя."""
        with session() as s:
            d = s.exec(select(Device).where(Device.tuya_id == tuya_id)).first()
            if d is None:
                d = Device(user_id=agent.user_id, tuya_id=tuya_id, name=name)
                log.info("пивоварня «%s» заведена", name)
            elif d.user_id != agent.user_id:
                raise Forbidden(f"пивоварня {tuya_id} принадлежит другому пользователю")
            d.agent_id = agent.id
            d.model = model or d.model
            d.limits = limits or d.limits
            s.add(d)
            s.commit()
            return d.id

    def update(self, device_id, **fields):
        """Пустые значения не затирают известные."""
        with session() as s:
            d = s.get(Device, device_id)
            for k, v in fields.items():
                if v is not None:
                    setattr(d, k, v)
            s.add(d)
            s.commit()

    def current(self, user_id):
        """Пивоварня пользователя (пока она у него одна — последняя заведённая) или None."""
        with session() as s:
            return s.exec(select(Device.id).where(Device.user_id == user_id).order_by(Device.created_at.desc())).first()

    def limits(self, device_id):
        with session() as s:
            d = s.get(Device, device_id)
            return d.limits if d else None

    def equipment(self, device_id):
        with session() as s:
            d = s.get(Device, device_id) if device_id else None
            return (d.equipment if d else None) or {}

    def set_equipment(self, device_id, data):
        if device_id is None:
            raise Conflict("пивоварня ещё не подключена")
        with session() as s:
            d = s.get(Device, device_id)
            d.equipment = data
            s.add(d)
            s.commit()
