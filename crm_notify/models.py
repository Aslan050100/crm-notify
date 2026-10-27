"""Общие модели данных, независимые от конкретной CRM."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class Person:
    """Человек из CRM (контакт amoCRM, контакт Битрикс24 и т.п.)."""

    crm_id: str
    name: str = ""
    first_name: str = ""
    last_name: str = ""
    phones: list[str] = field(default_factory=list)  # уже нормализованные, 77011234567
    birthday: dt.date | None = None
    opted_out: bool = False  # «Запрет автоматических сообщений»
    marks: dict[str, str] = field(default_factory=dict)  # отметки сценариев, напр. {"birthday": "2026"}

    @property
    def phone(self) -> str | None:
        return self.phones[0] if self.phones else None

    @property
    def greeting_name(self) -> str:
        """Как обращаться в сообщении: имя, иначе полное имя контакта."""
        return (self.first_name or self.name or "").strip()
