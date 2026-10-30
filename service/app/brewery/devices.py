"""Пивоварни пользователей: то, что сервису нужно и без агента на связи, — модель и ограничения. Заведённая
пивоварня становится оборудованием пивовара (equipment.py)."""
import logging

from sqlmodel import select

from ..db import session
from ..errors import Forbidden
from ..models import Device
from .equipment import attach_device, controlled_device

log = logging.getLogger("brewapp.devices")


class DeviceStore:
    def attach(self, agent, tuya_id, name, model=None, limits=None):
        """Агент сообщил, какую пивоварню обслуживает, — завести её или привязать к нему. Возвращает id пивоварни.
        Forbidden — пивоварня заведена у другого пользователя."""
        with session() as s:
            d = s.exec(select(Device).where(Device.tuya_id == tuya_id)).first()
            if d is None:
                d = Device(user_id=agent.user_id, tuya_id=tuya_id, name=name)
                s.add(d)
                s.flush()
                attach_device(s, d)
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
            return controlled_device(s, user_id)

    def limits(self, device_id):
        with session() as s:
            d = s.get(Device, device_id)
            return d.limits if d else None

