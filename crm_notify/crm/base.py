"""Интерфейс коннектора к CRM. Каждая CRM реализует эти методы."""

from __future__ import annotations

import abc
from collections.abc import Iterator

from ..models import Person


class CRMConnector(abc.ABC):
    name = "base"

    @abc.abstractmethod
    def iter_people_with_birthday(self) -> Iterator[Person]:
        """Все люди, у которых заполнена дата рождения (фильтр по дате делает сценарий)."""

    @abc.abstractmethod
    def set_mark(self, person: Person, scenario: str, value: str) -> None:
        """Записать отметку сценария в CRM (например, «Поздравлен с ДР» = 2026)."""

    def add_note(self, person: Person, text: str) -> None:  # необязательно
        """Оставить примечание в карточке (если CRM поддерживает)."""

    def check(self) -> str:
        """Проверка доступа. Возвращает человекочитаемое описание."""
        return "ok"

    def setup(self) -> list[str]:
        """Создать недостающие поля в CRM. Возвращает список сделанного."""
        return []
