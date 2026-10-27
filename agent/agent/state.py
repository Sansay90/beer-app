"""Память агента между перезапусками — state.json (BREWAPP_STATE, по умолчанию agent/data/state.json).

Свою программу пивоварня в status не отдаёт (DP 128 приходит, только когда меняется), поэтому последнюю
агент помнит сам. Вместе с ней — что загружено из приложения (названия шагов и закладок), модель,
теплоёмкость бака (energy.py) и незакрытая варка: агент могли перезапустить посреди программы.
"""
import json
import logging
import os
import threading

log = logging.getLogger("brewapp.state")

FIELDS = ("model", "recipe_raw", "active", "heat_capacity", "brew")


class Memory:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self._data = {}
        try:
            with open(path, encoding="utf-8") as f:
                self._data = {k: v for k, v in json.load(f).items() if k in FIELDS}
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as e:
            log.warning("память агента не прочиталась (%s) — начинаю с пустой", e)

    def get(self, key):
        with self._lock:
            return self._data.get(key)

    def update(self, **fields):
        """Записать сразу: агент могут выключить в любой момент. Через временный файл — без полузаписи."""
        with self._lock:
            self._data.update(fields)
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            tmp = self.path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, ensure_ascii=False)
                os.replace(tmp, self.path)
            except OSError as e:
                log.warning("память агента не сохранилась: %s", e)
