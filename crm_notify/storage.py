"""Журнал отправок и запусков (SQLite в папке data/)."""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

from .config import ROOT

SCHEMA = """
create table if not exists sends (
    id integer primary key,
    client text not null,
    scenario text not null,
    crm_id text not null,
    period text not null,          -- для ДР: год
    phone text,
    name text,
    mode text not null,            -- test / live
    status text not null,          -- sent / failed / would_send
    message_id text,
    error text,
    created_at text not null
);
create index if not exists sends_lookup on sends(client, scenario, crm_id, period, status);
create table if not exists runs (
    client text not null,
    scenario text not null,
    run_date text not null,
    mode text not null,
    finished_at text not null,
    summary text,
    primary key (client, scenario, run_date, mode)
);
"""


class Store:
    def __init__(self, path: Path | None = None):
        path = path or ROOT / "data" / "crm_notify.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def already_sent(self, client: str, scenario: str, crm_id: str, period: str) -> bool:
        row = self.db.execute(
            "select 1 from sends where client=? and scenario=? and crm_id=? and period=? and status='sent' limit 1",
            (client, scenario, crm_id, period),
        ).fetchone()
        return row is not None

    def phone_sent(self, client: str, scenario: str, phone: str, period: str) -> bool:
        """Один номер у нескольких контактов (дубли) — поздравляем один раз."""
        row = self.db.execute(
            "select 1 from sends where client=? and scenario=? and phone=? and period=? and status='sent' limit 1",
            (client, scenario, phone, period),
        ).fetchone()
        return row is not None

    def log_send(self, *, client, scenario, crm_id, period, phone, name, mode, status, message_id="", error=""):
        self.db.execute(
            "insert into sends(client,scenario,crm_id,period,phone,name,mode,status,message_id,error,created_at)"
            " values(?,?,?,?,?,?,?,?,?,?,?)",
            (client, scenario, crm_id, period, phone, name, mode, status, message_id, error, _now()),
        )
        self.db.commit()

    def run_done(self, client: str, scenario: str, day: dt.date, mode: str) -> bool:
        row = self.db.execute(
            "select 1 from runs where client=? and scenario=? and run_date=? and mode=?",
            (client, scenario, day.isoformat(), mode),
        ).fetchone()
        return row is not None

    def mark_run(self, client: str, scenario: str, day: dt.date, mode: str, summary: str) -> None:
        self.db.execute(
            "insert or replace into runs values(?,?,?,?,?,?)",
            (client, scenario, day.isoformat(), mode, _now(), summary),
        )
        self.db.commit()

    def recent(self, limit: int = 50) -> list[tuple]:
        return self.db.execute(
            "select created_at, client, scenario, mode, status, name, phone, error from sends order by id desc limit ?",
            (limit,),
        ).fetchall()


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")
