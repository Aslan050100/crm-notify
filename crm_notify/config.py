"""Загрузка настроек: клиенты из clients/*.yaml, секреты из .env / переменных окружения.

В yaml можно ссылаться на переменные окружения так: ${MYDENT_AMO_TOKEN}.
Секреты храним только в .env (он не попадает в git).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
_VAR = re.compile(r"\$\{([A-Z0-9_]+)\}")


def load_dotenv(path: Path | None = None) -> None:
    """Минимальный разбор .env: KEY=VALUE, комментарии с #. Уже заданные переменные не трогаем."""
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _expand(value):
    if isinstance(value, str):
        def repl(m: re.Match) -> str:
            name = m.group(1)
            if name not in os.environ:
                raise ConfigError(f"Не задана переменная {name} (добавьте её в файл .env)")
            return os.environ[name]

        return _VAR.sub(repl, value)
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    return value


class ConfigError(Exception):
    pass


def load_clients(clients_dir: Path | None = None, only: str | None = None) -> list[dict]:
    """Список включённых клиентов. Каждый — dict из своего yaml-файла."""
    load_dotenv()
    clients_dir = clients_dir or ROOT / "clients"
    result = []
    for path in sorted(clients_dir.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw.setdefault("id", path.stem)
        if only and raw["id"] != only:
            continue
        if not raw.get("enabled", True):
            continue
        result.append(_expand(raw))
    if only and not result:
        raise ConfigError(f"Клиент {only!r} не найден или выключен в папке {clients_dir}")
    return result


def mode() -> str:
    """test — только показать, кого бы поздравили; live — отправлять."""
    load_dotenv()
    value = os.environ.get("MODE", "test").strip().lower()
    return "live" if value == "live" else "test"
