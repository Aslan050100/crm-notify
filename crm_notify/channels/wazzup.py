"""Отправка сообщений через Wazzup API v3.

Настройки клиента (clients/<id>.yaml → channel):
    type: wazzup
    api_key: ${MYDENT_WAZZUP_API_KEY}
    phone: ${MYDENT_WAZZUP_PHONE}     # номер канала, с которого отправляем, напр. 77475307747
    transport: whatsapp
Сообщение, отправленное через API, Wazzup сам показывает в чате карточки CRM.
"""

from __future__ import annotations

from ..http import ApiError, Http
from ..utils import normalize_phone


class Wazzup:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.http = Http(
            "https://api.wazzup24.com/v3",
            {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            min_interval=0.5,
        )
        self.transport = cfg.get("transport", "whatsapp")
        self._channel_id: str | None = cfg.get("channel_id")

    def channel_id(self) -> str:
        if self._channel_id:
            return self._channel_id
        want = normalize_phone(self.cfg.get("phone"))
        channels = self.http.get("channels") or []
        for ch in channels:
            if ch.get("transport") == self.transport and normalize_phone(ch.get("plainId")) == want:
                self._channel_id = ch["channelId"]
                return self._channel_id
        found = ", ".join(f"{c.get('transport')} {c.get('plainId')} ({c.get('state')})" for c in channels)
        raise ApiError(f"В Wazzup не найден канал {self.transport} {want}. Есть: {found or 'ничего'}")

    def check(self) -> str:
        cid = self.channel_id()
        channels = self.http.get("channels") or []
        state = next((c.get("state") for c in channels if c.get("channelId") == cid), "?")
        note = "" if state == "active" else "  ⚠️ канал не активен — сообщения не уйдут"
        return f"Wazzup: канал {self.transport} {self.cfg.get('phone')} найден, состояние: {state}{note}"

    def send(self, phone: str, text: str) -> str:
        data = self.http.post(
            "message",
            json={"channelId": self.channel_id(), "chatType": self.transport, "chatId": phone, "text": text},
        ) or {}
        return str(data.get("messageId", ""))


def build_channel(cfg: dict) -> Wazzup:
    if cfg.get("type", "wazzup") != "wazzup":
        raise ValueError(f"Неизвестный канал: {cfg.get('type')}")
    return Wazzup(cfg)
