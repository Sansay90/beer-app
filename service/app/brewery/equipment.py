"""Оборудование пивовара: без подключения (кастрюля, котёл, любая система) или пивоварня, которой управляют
с сайта (Easy Brew Connect). Одно — основное: его объём, эффективность и испарение подставляются в новые рецепты
и в расчёт воды. Первое добавленное — основное; основное удалили — основным становится самое раннее из
оставшихся. Пивоварню, которую завёл агент, оборудованием делает attach_device; пока она привязана, это
оборудование не удалить.
"""
from sqlmodel import select

from ..db import session
from ..errors import Conflict, Invalid, NotFound
from ..models import Equipment, parse_id

MANUAL, EASYBREW = "manual", "easybrew"
MAX = 10
NAME_MAX = 60


def check_name(name):
    name = (name or "").strip()
    if not name:
        raise Invalid("назовите оборудование")
    if len(name) > NAME_MAX:
        raise Invalid(f"название длиннее {NAME_MAX} знаков — сократите")
    return name


def view(e):
    return {"id": str(e.id), "name": e.name, "kind": e.kind, "connected": e.device_id is not None,
            "volume": e.volume, "efficiency": e.efficiency, "evaporation": e.evaporation, "kettle": e.kettle,
            "main": e.main}


def own(s, user_id, equipment_id):
    """Оборудование пользователя по id; чужое или нет такого — NotFound."""
    e = s.get(Equipment, eid) if (eid := parse_id(equipment_id)) else None
    if e is None or e.user_id != user_id:
        raise NotFound("оборудование не найдено")
    return e


def main_of(s, user_id):
    """Основное оборудование пользователя или None."""
    return s.exec(select(Equipment).where(Equipment.user_id == user_id, Equipment.main)).first()


def attach_device(s, device):
    """Пивоварня, которую агент завёл впервые, — оборудованием пивовара: заранее добавленное «Easy Brew» без
    пивоварни получает её, иначе заводится новое; основным — если основного ещё нет. В сессии s, без commit."""
    e = s.exec(select(Equipment).where(Equipment.user_id == device.user_id, Equipment.kind == EASYBREW,
                                       Equipment.device_id.is_(None)).order_by(Equipment.created_at)).first()
    if e is None:
        e = Equipment(user_id=device.user_id, name=device.name or "Easy Brew", kind=EASYBREW,
                      main=main_of(s, device.user_id) is None)
    e.device_id = device.id
    s.add(e)


class EquipmentStore:
    """Оборудование пользователя user. NotFound — чужое или нет такого."""

    def __init__(self, user):
        self.user = user

    def list(self):
        """Основное первым, остальное — по порядку добавления."""
        with session() as s:
            rows = s.exec(select(Equipment).where(Equipment.user_id == self.user.id)
                          .order_by(Equipment.main.desc(), Equipment.created_at)).all()
        return [view(e) for e in rows]

    def create(self, name, kind, volume, efficiency, evaporation, kettle=None):
        name = check_name(name)
        with session() as s:
            mine = s.exec(select(Equipment.id).where(Equipment.user_id == self.user.id)).all()
            if len(mine) >= MAX:
                raise Conflict(f"оборудования уже {MAX} — удалите ненужное")
            e = Equipment(user_id=self.user.id, name=name, kind=kind, volume=volume, efficiency=efficiency,
                          evaporation=evaporation, kettle=kettle, main=not mine)
            s.add(e)
            s.commit()
            return view(e)

    def update(self, equipment_id, name, volume, efficiency, evaporation, kettle=None):
        """Вид оборудования не меняется."""
        name = check_name(name)
        with session() as s:
            e = self._row(s, equipment_id)
            e.name, e.volume, e.efficiency, e.evaporation, e.kettle = name, volume, efficiency, evaporation, kettle
            s.add(e)
            s.commit()
            return view(e)

    def make_main(self, equipment_id):
        with session() as s:
            e = self._row(s, equipment_id)
            if (old := main_of(s, self.user.id)) is not None and old.id != e.id:
                old.main = False
                s.add(old)
            e.main = True
            s.add(e)
            s.commit()
            return view(e)

    def delete(self, equipment_id):
        with session() as s:
            e = self._row(s, equipment_id)
            if e.device_id is not None:
                raise Conflict("пивоварня подключена к сайту — сначала отвяжите её")
            s.delete(e)
            if e.main:
                rest = s.exec(select(Equipment).where(Equipment.user_id == self.user.id, Equipment.id != e.id)
                              .order_by(Equipment.created_at)).first()
                if rest is not None:
                    rest.main = True
                    s.add(rest)
            s.commit()

    def _row(self, s, equipment_id):
        return own(s, self.user.id, equipment_id)
