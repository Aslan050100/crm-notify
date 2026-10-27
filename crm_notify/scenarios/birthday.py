"""Сценарий «День рождения»: поздравить тех, у кого сегодня ДР, и поставить отметку года.

Настройки (clients/<id>.yaml → scenarios.birthday):
    enabled: true
    send_at: "11:00"              # время запуска (часовой пояс — timezone клиента)
    send_until: "20:00"           # позже этого времени не отправляем (если компьютер был выключен)
    max_per_run: 50
    delay_seconds: [15, 45]       # пауза между сообщениями (бережём серый номер)
    greeting_with_name: "{first_name}, с днём рождения!"
    greeting_without_name: "С днём рождения!"
    template: |
      🎉🥳 {greeting} 🥳🎉
      ...
    note: "Отправлено поздравление с днём рождения (crm-notify)"
"""

from __future__ import annotations

import csv
import datetime as dt
import logging
import random
import re
import time
from dataclasses import dataclass, field

from ..config import ROOT
from ..models import Person
from ..utils import age_on, is_birthday, render

log = logging.getLogger(__name__)
SCENARIO = "birthday"

_NOT_A_NAME = {"клиент", "client", "пациент", "контакт", "unknown", "без", "имени"}


def clean_first_name(person: Person) -> str:
    """Имя для обращения или пустая строка, если в поле не имя (цифры, «Клиент», эмодзи...)."""
    raw = (person.first_name or "").strip()
    if not raw:
        return ""
    word = raw.split()[0]
    if re.search(r"\d", word) or word.lower() in _NOT_A_NAME:
        return ""
    if not re.fullmatch(r"[A-Za-zА-Яа-яЁёӘәІіҢңҒғҮүҰұҚқӨөҺһ\-]{2,}", word):
        return ""
    return word[:1].upper() + word[1:]


def build_text(cfg: dict, person: Person) -> str:
    first = clean_first_name(person)
    greeting = (
        render(cfg.get("greeting_with_name", "{first_name}, с днём рождения!"), first_name=first)
        if first
        else cfg.get("greeting_without_name", "С днём рождения!")
    )
    return render(cfg["template"], greeting=greeting, first_name=first, name=person.name)


@dataclass
class Result:
    candidates: list[Person] = field(default_factory=list)
    sent: int = 0
    failed: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    report_path: str = ""

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1

    def summary(self) -> str:
        parts = [f"к отправке {len(self.candidates)}", f"отправлено {self.sent}"]
        if self.failed:
            parts.append(f"ошибок {self.failed}")
        parts += [f"{k}: {v}" for k, v in self.skipped.items()]
        return ", ".join(parts)


def run(client: dict, crm, channel, store, today: dt.date, mode: str, sleep=time.sleep) -> Result:
    cfg = client["scenarios"][SCENARIO]
    period = str(today.year)
    res = Result()
    seen_phones: set[str] = set()

    for person in crm.iter_people_with_birthday():
        if not person.birthday or not is_birthday(person.birthday, today):
            continue
        if person.opted_out:
            res.skip("запрет авто-сообщений")
            continue
        if not person.phone:
            res.skip("нет телефона")
            continue
        if person.marks.get(SCENARIO) == period or store.already_sent(client["id"], SCENARIO, person.crm_id, period):
            res.skip("уже поздравлен в этом году")
            continue
        if person.phone in seen_phones or store.phone_sent(client["id"], SCENARIO, person.phone, period):
            res.skip("дубль номера")
            continue
        seen_phones.add(person.phone)
        res.candidates.append(person)

    limit = int(cfg.get("max_per_run", 50))
    if len(res.candidates) > limit:
        log.warning("Кандидатов %d больше лимита %d — остальные будут пропущены", len(res.candidates), limit)
        for _ in res.candidates[limit:]:
            res.skip("сверх лимита за запуск")
        res.candidates = res.candidates[:limit]

    res.report_path = _write_report(client["id"], today, mode, res.candidates, cfg)

    if mode != "live":
        for p in res.candidates:
            store.log_send(client=client["id"], scenario=SCENARIO, crm_id=p.crm_id, period=period,
                           phone=p.phone, name=p.name, mode=mode, status="would_send")
        return res

    delay = cfg.get("delay_seconds", [15, 45])
    for i, person in enumerate(res.candidates):
        if i:
            sleep(random.uniform(float(delay[0]), float(delay[1])))
        text = build_text(cfg, person)
        try:
            message_id = channel.send(person.phone, text)
        except Exception as exc:  # noqa: BLE001 — любая ошибка отправки не должна остановить остальных
            res.failed += 1
            log.error("Не отправлено %s (%s): %s", person.name, person.phone, exc)
            store.log_send(client=client["id"], scenario=SCENARIO, crm_id=person.crm_id, period=period,
                           phone=person.phone, name=person.name, mode=mode, status="failed", error=str(exc)[:500])
            continue
        res.sent += 1
        store.log_send(client=client["id"], scenario=SCENARIO, crm_id=person.crm_id, period=period,
                       phone=person.phone, name=person.name, mode=mode, status="sent", message_id=message_id)
        try:
            crm.set_mark(person, SCENARIO, period)
            if cfg.get("note"):
                crm.add_note(person, cfg["note"])
        except Exception as exc:  # noqa: BLE001 — отметка не встала, но журнал защитит от повтора
            log.warning("Сообщение ушло, но отметку в CRM поставить не удалось (%s): %s", person.name, exc)
    return res


def _write_report(client_id: str, today: dt.date, mode: str, people: list[Person], cfg: dict) -> str:
    folder = ROOT / "data" / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{today.isoformat()}_{client_id}_birthday_{mode}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["ID в CRM", "Имя в CRM", "Обращение", "Телефон", "Дата рождения", "Исполняется", "Текст"])
        for p in people:
            w.writerow([
                p.crm_id, p.name, clean_first_name(p) or "(без имени)", "+" + p.phone,
                p.birthday.strftime("%d.%m.%Y") if p.birthday else "",
                age_on(p.birthday, today) if p.birthday and p.birthday.year > 1900 else "",
                build_text(cfg, p),
            ])
    return str(path)
