"""Командная строка crm-notify.

    python -m crm_notify check   [--client mydent]          проверить доступы и показать, у кого ДР сегодня
    python -m crm_notify setup   [--client mydent]          создать недостающие поля-отметки в CRM
    python -m crm_notify run     [--client mydent] [--date 2026-11-05]   выполнить сценарии сейчас
    python -m crm_notify due                                 выполнить то, чьё время пришло (для планировщика)
    python -m crm_notify serve                               работать постоянно, проверяя время раз в минуту
    python -m crm_notify log                                 последние записи журнала

Режим (test / live) задаётся в .env: MODE=test — только отчёт, MODE=live — реальная отправка.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
import time
from zoneinfo import ZoneInfo

from .channels import build_channel
from .config import ROOT, ConfigError, load_clients, mode
from .crm import build_connector
from .scenarios import SCENARIOS
from .storage import Store

log = logging.getLogger("crm_notify")


def _setup_logging() -> None:
    (ROOT / "data").mkdir(exist_ok=True)
    fmt = "%(asctime)s %(levelname)s %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(ROOT / "data" / "crm_notify.log", encoding="utf-8"),
        ],
    )
    for noisy in ("urllib3", "requests"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _now(client: dict) -> dt.datetime:
    return dt.datetime.now(ZoneInfo(client.get("timezone", "Asia/Almaty")))


def _hm(value: str) -> dt.time:
    h, m = str(value).split(":")
    return dt.time(int(h), int(m))


def run_client(client: dict, store: Store, today: dt.date | None = None, only_due: bool = False) -> None:
    current_mode = mode()
    now = _now(client)
    today = today or now.date()
    crm = channel = None
    for name, scfg in (client.get("scenarios") or {}).items():
        if not scfg.get("enabled", True) or name not in SCENARIOS:
            continue
        if only_due:
            if store.run_done(client["id"], name, today, current_mode):
                continue
            if not (_hm(scfg.get("send_at", "11:00")) <= now.time() <= _hm(scfg.get("send_until", "20:00"))):
                continue
        crm = crm or build_connector(client["crm"])
        channel = channel or build_channel(client["channel"])
        log.info("▶ %s / %s / %s / режим %s", client["id"], name, today.strftime("%d.%m.%Y"), current_mode.upper())
        res = SCENARIOS[name].run(client, crm, channel, store, today, current_mode)
        for p in res.candidates:
            log.info("   %s — +%s — ДР %s", p.name, p.phone, p.birthday.strftime("%d.%m.%Y"))
        log.info("■ %s / %s: %s. Отчёт: %s", client["id"], name, res.summary(), res.report_path)
        store.mark_run(client["id"], name, today, current_mode, res.summary())


def cmd_check(args) -> int:
    ok = True
    for client in load_clients(only=args.client):
        print(f"\n=== {client.get('title', client['id'])} ===")
        try:
            crm = build_connector(client["crm"])
            print("✔", crm.check())
        except Exception as exc:  # noqa: BLE001
            ok = False
            print("✖ CRM:", exc)
            continue
        try:
            print("✔", build_channel(client["channel"]).check())
        except Exception as exc:  # noqa: BLE001
            ok = False
            print("✖ Wazzup:", exc)
        if "birthday" in (client.get("scenarios") or {}):
            from .scenarios.birthday import build_text
            from .utils import is_birthday

            today = _now(client).date()
            total, todays = 0, []
            for p in crm.iter_people_with_birthday():
                total += 1
                if is_birthday(p.birthday, today):
                    todays.append(p)
            print(f"✔ Контактов с датой рождения: {total}. Сегодня ({today:%d.%m}) день рождения у {len(todays)}:")
            for p in todays:
                flag = " (запрет авто-сообщений)" if p.opted_out else ("" if p.phone else " (нет телефона)")
                print(f"   • {p.name} +{p.phone or '—'}{flag}")
            if todays:
                print("\nПример текста:\n" + build_text(client["scenarios"]["birthday"], todays[0]))
    print(f"\nРежим сейчас: {mode().upper()} ({'реальная отправка' if mode() == 'live' else 'только отчёт, без отправки'})")
    return 0 if ok else 1


def cmd_setup(args) -> int:
    for client in load_clients(only=args.client):
        for line in build_connector(client["crm"]).setup():
            print(f"[{client['id']}] {line}")
    return 0


def cmd_run(args) -> int:
    store = Store()
    day = dt.date.fromisoformat(args.date) if args.date else None
    for client in load_clients(only=args.client):
        run_client(client, store, today=day)
    return 0


def cmd_due(args) -> int:
    store = Store()
    for client in load_clients(only=args.client):
        try:
            run_client(client, store, only_due=True)
        except Exception:  # noqa: BLE001 — ошибка одного клиента не мешает остальным
            log.exception("Ошибка у клиента %s", client["id"])
    return 0


def cmd_serve(args) -> int:
    log.info("crm-notify запущен, проверяю расписание раз в минуту. Остановить: Ctrl+C")
    while True:
        cmd_due(args)
        time.sleep(60)


def cmd_log(args) -> int:
    for row in Store().recent(args.limit):
        print(" | ".join(str(x or "") for x in row))
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # эмодзи и кириллица в консоли Windows
    _setup_logging()
    parser = argparse.ArgumentParser(prog="crm_notify", description="Автоматические WhatsApp-сообщения из CRM")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("check", "setup", "run", "due", "serve", "log"):
        p = sub.add_parser(name)
        p.add_argument("--client", help="id клиента (имя файла в clients/ без .yaml)")
        if name == "run":
            p.add_argument("--date", help="выполнить за другую дату, ГГГГ-ММ-ДД (для проверки)")
        if name == "log":
            p.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)
    handler = {"check": cmd_check, "setup": cmd_setup, "run": cmd_run, "due": cmd_due,
               "serve": cmd_serve, "log": cmd_log}[args.cmd]
    try:
        return handler(args)
    except ConfigError as exc:
        print("Ошибка настроек:", exc)
        return 2
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
