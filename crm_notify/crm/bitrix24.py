"""Коннектор Битрикс24 через входящий вебхук (REST).

⚠️ Черновой вариант: ещё не проверен на реальном портале (подключим с Sapa Dent).

Настройки клиента (clients/<id>.yaml → crm):
    type: bitrix24
    webhook: ${SAPADENT_B24_WEBHOOK}     # https://<портал>.bitrix24.kz/rest/<user>/<код>/
    opt_out_field: UF_CRM_...            # необязательно, пользовательское поле «да/нет»
    marks:
      birthday: UF_CRM_...               # пользовательское строковое поле для отметки
У контактов Битрикс24 дата рождения — стандартное поле BIRTHDATE.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

from ..http import Http
from ..models import Person
from ..utils import normalize_phone
from .base import CRMConnector


class Bitrix24(CRMConnector):
    name = "bitrix24"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.http = Http(cfg["webhook"].rstrip("/") + "/", {}, min_interval=0.5)

    def iter_people_with_birthday(self) -> Iterator[Person]:
        opt = self.cfg.get("opt_out_field")
        marks = self.cfg.get("marks") or {}
        select = ["ID", "NAME", "LAST_NAME", "SECOND_NAME", "BIRTHDATE", "PHONE", *([opt] if opt else []), *marks.values()]
        start = 0
        while True:
            data = self.http.post(
                "crm.contact.list.json",
                json={"filter": {"!BIRTHDATE": ""}, "select": select, "start": start},
            ) or {}
            for c in data.get("result", []):
                birthday = _parse_b24_date(c.get("BIRTHDATE"))
                if not birthday:
                    continue
                phones = []
                for p in c.get("PHONE") or []:
                    n = normalize_phone(p.get("VALUE"))
                    if n and n not in phones:
                        phones.append(n)
                yield Person(
                    crm_id=str(c["ID"]),
                    name=" ".join(x for x in (c.get("NAME"), c.get("LAST_NAME")) if x),
                    first_name=c.get("NAME") or "",
                    last_name=c.get("LAST_NAME") or "",
                    phones=phones,
                    birthday=birthday,
                    opted_out=str(c.get(opt, "")).upper() in ("Y", "1", "TRUE") if opt else False,
                    marks={k: str(c.get(v) or "").strip() for k, v in marks.items()},
                )
            if "next" not in data:
                break
            start = data["next"]

    def set_mark(self, person: Person, scenario: str, value: str) -> None:
        field = (self.cfg.get("marks") or {}).get(scenario)
        if field:
            self.http.post("crm.contact.update.json", json={"id": person.crm_id, "fields": {field: value}})

    def add_note(self, person: Person, text: str) -> None:
        self.http.post(
            "crm.timeline.comment.add.json",
            json={"fields": {"ENTITY_ID": person.crm_id, "ENTITY_TYPE": "contact", "COMMENT": text}},
        )

    def check(self) -> str:
        data = self.http.post("profile.json") or {}
        r = data.get("result", {})
        return f"Битрикс24: вебхук работает (пользователь {r.get('NAME', '')} {r.get('LAST_NAME', '')})"


def _parse_b24_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
