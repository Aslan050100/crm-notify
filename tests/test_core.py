import datetime as dt

import pytest

from crm_notify.crm.amocrm import AmoCRM
from crm_notify.models import Person
from crm_notify.scenarios import birthday
from crm_notify.storage import Store
from crm_notify.utils import date_from_crm_timestamp, is_birthday, normalize_phone, render


# ---------- утилиты ----------
@pytest.mark.parametrize("raw,expected", [
    ("+7 (701) 123-45-67", "77011234567"),
    ("8 701 123 45 67", "77011234567"),
    ("7011234567", "77011234567"),
    ("77011234567, входящий", "77011234567"),
    ("abc", None),
    (None, None),
])
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("ts,expected", [
    (520102800, dt.date(1986, 6, 26)),    # полночь +07 (как сохранил amoCRM)
    (-646120800, dt.date(1949, 7, 12)),   # 11.07 18:00 UTC = полночь 12.07 по +06
    (674676000, dt.date(1991, 5, 20)),    # полночь +06
    (1761505200, dt.date(2025, 10, 27)),  # полночь +05
    (0, dt.date(1970, 1, 1)),             # полночь UTC
])
def test_date_from_crm_timestamp(ts, expected):
    assert date_from_crm_timestamp(ts) == expected


def test_is_birthday_feb29():
    b = dt.date(2000, 2, 29)
    assert is_birthday(b, dt.date(2027, 2, 28))      # невисокосный год → 28 февраля
    assert not is_birthday(b, dt.date(2028, 2, 28))  # високосный → ждём 29-го
    assert is_birthday(b, dt.date(2028, 2, 29))


def test_render_missing_vars():
    assert render("{greeting} {nope}!", greeting="Привет") == "Привет!"


# ---------- имя для обращения ----------
@pytest.mark.parametrize("first,expected", [
    ("Акнур", "Акнур"),
    ("акнур", "Акнур"),
    ("Галина Яковлевна", "Галина"),
    ("Клиент", ""),
    ("77023059955, входящий", ""),
    ("", ""),
    ("⠀", ""),
    ("Aidana", "Aidana"),
])
def test_clean_first_name(first, expected):
    assert birthday.clean_first_name(Person(crm_id="1", first_name=first)) == expected


# ---------- разбор контакта amoCRM ----------
def test_amo_contact_parsing():
    contact = {
        "id": 17058393, "name": "Акнур Айтбекова", "first_name": "Акнур", "last_name": "Айтбекова",
        "custom_fields_values": [
            {"field_id": 505431, "field_code": "PHONE", "values": [{"value": "+7 (702) 305-99-55"}, {"value": "87023059955"}]},
            {"field_id": 720115, "field_code": None, "values": [{"value": 520102800}]},
            {"field_id": 783169, "field_code": None, "values": [{"value": True}]},
            {"field_id": 900001, "field_code": None, "values": [{"value": "2026"}]},
        ],
    }
    p = AmoCRM._to_person(contact, 720115, 783169, {"birthday": 900001})
    assert p.phones == ["77023059955"]
    assert p.birthday == dt.date(1986, 6, 26)
    assert p.opted_out is True
    assert p.marks == {"birthday": "2026"}


# ---------- сценарий ----------
class FakeCRM:
    def __init__(self, people):
        self.people = people
        self.marks, self.notes = [], []

    def iter_people_with_birthday(self):
        yield from self.people

    def set_mark(self, person, scenario, value):
        self.marks.append((person.crm_id, value))

    def add_note(self, person, text):
        self.notes.append(person.crm_id)


class FakeChannel:
    def __init__(self, fail_for=()):
        self.sent, self.fail_for = [], set(fail_for)

    def send(self, phone, text):
        if phone in self.fail_for:
            raise RuntimeError("канал недоступен")
        self.sent.append((phone, text))
        return f"msg-{len(self.sent)}"


TODAY = dt.date(2026, 10, 27)
CLIENT = {
    "id": "test",
    "scenarios": {"birthday": {
        "template": "🎉 {greeting} 🎉\nТекст",
        "greeting_with_name": "{first_name}, с днём рождения!",
        "greeting_without_name": "С днём рождения!",
        "delay_seconds": [0, 0],
        "note": "Поздравлен",
    }},
}


def _people():
    bd = dt.date(1990, 10, 27)
    return [
        Person("1", "Акнур Айтбекова", "Акнур", "Айтбекова", ["77011111111"], bd),
        Person("2", "77022222222, входящий", "77022222222, входящий", "", ["77022222222"], bd),
        Person("3", "Запрет", "Запрет", "", ["77033333333"], bd, opted_out=True),
        Person("4", "Без телефона", "Без", "", [], bd),
        Person("5", "Уже", "Уже", "", ["77055555555"], bd, marks={"birthday": "2026"}),
        Person("6", "Дубль номера", "Дубль", "", ["77011111111"], bd),
        Person("7", "Не сегодня", "Не", "", ["77077777777"], dt.date(1990, 10, 28)),
        Person("8", "Прошлый год", "Прошлый", "", ["77088888888"], bd, marks={"birthday": "2025"}),
    ]


def test_birthday_test_mode_sends_nothing(tmp_path):
    crm, ch = FakeCRM(_people()), FakeChannel()
    res = birthday.run(CLIENT, crm, ch, Store(tmp_path / "db.sqlite"), TODAY, "test", sleep=lambda s: None)
    assert [p.crm_id for p in res.candidates] == ["1", "2", "8"]
    assert ch.sent == [] and crm.marks == []
    assert res.skipped == {"запрет авто-сообщений": 1, "нет телефона": 1, "уже поздравлен в этом году": 1, "дубль номера": 1}


def test_birthday_live_mode_and_no_repeat(tmp_path):
    store = Store(tmp_path / "db.sqlite")
    crm, ch = FakeCRM(_people()), FakeChannel(fail_for={"77088888888"})
    res = birthday.run(CLIENT, crm, ch, store, TODAY, "live", sleep=lambda s: None)
    assert res.sent == 2 and res.failed == 1
    assert ch.sent[0][1].startswith("🎉 Акнур, с днём рождения! 🎉")
    assert ch.sent[1][1].startswith("🎉 С днём рождения! 🎉")  # имя — цифры → без обращения
    assert crm.marks == [("1", "2026"), ("2", "2026")]
    # повторный запуск в тот же день: отправленным второй раз не пишем, упавшему — пробуем снова
    ch2 = FakeChannel()
    res2 = birthday.run(CLIENT, FakeCRM(_people()), ch2, store, TODAY, "live", sleep=lambda s: None)
    assert [p for p, _ in ch2.sent] == ["77088888888"]
    assert res2.skipped["уже поздравлен в этом году"] == 3


# ---------- настройки клиента ----------
def test_mydent_config_loads_and_renders(monkeypatch):
    from crm_notify.config import load_clients

    for k, v in {"MYDENT_AMO_SUBDOMAIN": "bo4smag", "MYDENT_AMO_TOKEN": "t",
                 "MYDENT_WAZZUP_API_KEY": "k", "MYDENT_WAZZUP_PHONE": "77475307747"}.items():
        monkeypatch.setenv(k, v)
    (client,) = load_clients(only="mydent")
    assert client["crm"]["subdomain"] == "bo4smag"
    assert client["crm"]["marks"]["birthday"] == "Поздравлен с ДР (год)"
    cfg = client["scenarios"]["birthday"]
    with_name = birthday.build_text(cfg, Person("1", "Акнур Айтбекова", "Акнур"))
    no_name = birthday.build_text(cfg, Person("2", "77011111111", "77011111111"))
    assert with_name.startswith("🎉🥳 Акнур, с днём рождения! 🥳🎉")
    assert no_name.startswith("🎉🥳 С днём рождения! 🥳🎉")
    assert "+7 747 530 77 47" in with_name and with_name.endswith("instagram.com/mydent_astana/")
