"""Общие функции: телефоны, даты, шаблоны текстов."""

from __future__ import annotations

import datetime as dt
import re
import string


def normalize_phone(raw: str | None, default_country: str = "7") -> str | None:
    """Приводит телефон к виду 77011234567 (только цифры, с кодом страны).

    Поддерживает форматы «+7 (701) 123-45-67», «8 701 123 45 67», «7011234567».
    Возвращает None, если номер не похож на телефон.
    """
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 10:
        digits = default_country + digits
    elif len(digits) == 11 and digits[0] == "8" and default_country == "7":
        digits = "7" + digits[1:]
    if not 10 <= len(digits) <= 15:
        return None
    return digits


def date_from_crm_timestamp(ts: int | float | str) -> dt.date:
    """Дата из unix-времени поля «дата» amoCRM.

    amoCRM хранит дату как полночь в часовом поясе аккаунта (с историческими
    смещениями +5…+7 для Казахстана), то есть 17:00–19:00 UTC предыдущего дня.
    Сдвиг на +12 часов даёт правильную календарную дату для любого пояса
    от UTC−11 до UTC+12.
    """
    moment = dt.datetime.fromtimestamp(int(float(ts)), tz=dt.timezone.utc)
    return (moment + dt.timedelta(hours=12)).date()


def is_birthday(birth: dt.date, today: dt.date) -> bool:
    """Сегодня ли день рождения. Родившиеся 29 февраля в невисокосный год — 28-го."""
    if birth.month == 2 and birth.day == 29 and not _is_leap(today.year):
        return today.month == 2 and today.day == 28
    return (birth.month, birth.day) == (today.month, today.day)


def age_on(birth: dt.date, today: dt.date) -> int:
    years = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        years -= 1
    return years


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:  # неизвестная переменная не ломает текст
        return ""


def render(template: str, **values: object) -> str:
    """Подставляет {first_name}, {name} и т.п. Неизвестные переменные → пусто."""
    formatter = string.Formatter()
    text = formatter.vformat(template, (), _SafeDict(values))
    # убираем двойные пробелы и пробел перед запятой, если переменная пустая
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r" +([,!.])", r"\1", text)
    return text.strip()
