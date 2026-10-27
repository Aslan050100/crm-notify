"""Коннектор amoCRM (API v4, долгосрочный токен внешней интеграции).

Настройки клиента (clients/<id>.yaml → crm):
    type: amocrm
    subdomain: bo4smag
    token: ${MYDENT_AMO_TOKEN}
    birthday_field: "День Рождения"            # имя или id поля «дата» у контакта
    opt_out_field: "Запрет автоматических сообщений"   # чекбокс, необязательно
    marks:
      birthday: "Поздравлен с ДР (год)"         # поле-отметка; создаётся командой setup
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

from ..http import ApiError, Http
from ..models import Person
from ..utils import date_from_crm_timestamp, normalize_phone
from .base import CRMConnector

log = logging.getLogger(__name__)


class AmoCRM(CRMConnector):
    name = "amocrm"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        sub = cfg["subdomain"].replace(".amocrm.ru", "")
        self.http = Http(
            f"https://{sub}.amocrm.ru/api/v4",
            {"Authorization": f"Bearer {cfg['token']}", "Content-Type": "application/json"},
            min_interval=0.15,  # лимит amoCRM — 7 запросов в секунду
        )
        self._fields: dict[str, dict] | None = None

    # ---------- поля ----------
    def _contact_fields(self) -> dict[str, dict]:
        """Поля контактов: ключи — и id (строкой), и название в нижнем регистре."""
        if self._fields is None:
            fields: dict[str, dict] = {}
            page = 1
            while True:
                data = self.http.get("contacts/custom_fields", params={"limit": 250, "page": page})
                items = (data or {}).get("_embedded", {}).get("custom_fields", [])
                for f in items:
                    fields[str(f["id"])] = f
                    fields[f["name"].strip().lower()] = f
                if len(items) < 250:
                    break
                page += 1
            self._fields = fields
        return self._fields

    def field_id(self, ref: str | int | None) -> int | None:
        if ref in (None, ""):
            return None
        f = self._contact_fields().get(str(ref).strip().lower())
        return int(f["id"]) if f else None

    def _require_field(self, ref, what: str) -> int:
        fid = self.field_id(ref)
        if fid is None:
            raise ApiError(f"В amoCRM не найдено поле контакта «{ref}» ({what}). Запустите setup или поправьте настройки.")
        return fid

    # ---------- чтение ----------
    def iter_people_with_birthday(self) -> Iterator[Person]:
        bday_id = self._require_field(self.cfg.get("birthday_field", "День Рождения"), "дата рождения")
        opt_id = self.field_id(self.cfg.get("opt_out_field"))
        mark_ids = {k: self.field_id(v) for k, v in (self.cfg.get("marks") or {}).items()}

        page = 1
        while True:
            data = self.http.get("contacts", params={"limit": 250, "page": page})
            contacts = (data or {}).get("_embedded", {}).get("contacts", [])
            for c in contacts:
                person = self._to_person(c, bday_id, opt_id, mark_ids)
                if person.birthday:
                    yield person
            if len(contacts) < 250:
                break
            page += 1

    @staticmethod
    def _to_person(c: dict, bday_id: int, opt_id: int | None, mark_ids: dict[str, int | None]) -> Person:
        values = {f["field_id"]: f for f in (c.get("custom_fields_values") or [])}
        phones: list[str] = []
        for f in c.get("custom_fields_values") or []:
            if f.get("field_code") == "PHONE":
                for v in f.get("values", []):
                    p = normalize_phone(v.get("value"))
                    if p and p not in phones:
                        phones.append(p)
        birthday = None
        if bday_id in values and values[bday_id].get("values"):
            try:
                birthday = date_from_crm_timestamp(values[bday_id]["values"][0]["value"])
            except (TypeError, ValueError):
                birthday = None
        opted_out = False
        if opt_id and opt_id in values:
            opted_out = bool(values[opt_id]["values"] and values[opt_id]["values"][0].get("value"))
        marks = {}
        for scenario, fid in mark_ids.items():
            if fid and fid in values and values[fid].get("values"):
                marks[scenario] = str(values[fid]["values"][0].get("value", "")).strip()
        return Person(
            crm_id=str(c["id"]),
            name=c.get("name") or "",
            first_name=c.get("first_name") or "",
            last_name=c.get("last_name") or "",
            phones=phones,
            birthday=birthday,
            opted_out=opted_out,
            marks=marks,
        )

    # ---------- запись ----------
    def set_mark(self, person: Person, scenario: str, value: str) -> None:
        ref = (self.cfg.get("marks") or {}).get(scenario)
        if not ref:
            return
        if self.field_id(ref) is None:  # поля ещё нет — создаём его сами
            self.setup()
        fid = self._require_field(ref, f"отметка сценария {scenario}")
        self.http.patch(
            "contacts",
            json=[{"id": int(person.crm_id), "custom_fields_values": [{"field_id": fid, "values": [{"value": value}]}]}],
        )

    def add_note(self, person: Person, text: str) -> None:
        try:
            self.http.post(f"contacts/{person.crm_id}/notes", json=[{"note_type": "common", "params": {"text": text}}])
        except ApiError as exc:  # примечание — не критично
            log.warning("Не удалось добавить примечание контакту %s: %s", person.crm_id, exc)

    # ---------- служебное ----------
    def check(self) -> str:
        acc = self.http.get("account")
        return f"amoCRM: аккаунт «{acc.get('name')}» ({acc.get('subdomain')}.amocrm.ru) — доступ есть"

    def setup(self) -> list[str]:
        done = []
        for scenario, name in (self.cfg.get("marks") or {}).items():
            if self.field_id(name) is None:
                self.http.post("contacts/custom_fields", json=[{"name": str(name), "type": "text", "sort": 600}])
                self._fields = None
                done.append(f"Создано поле контакта «{name}» (сценарий {scenario})")
            else:
                done.append(f"Поле «{name}» уже есть")
        return done
