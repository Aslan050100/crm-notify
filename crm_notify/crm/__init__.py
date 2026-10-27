from .base import CRMConnector


def build_connector(cfg: dict) -> CRMConnector:
    kind = cfg.get("type")
    if kind == "amocrm":
        from .amocrm import AmoCRM

        return AmoCRM(cfg)
    if kind == "bitrix24":
        from .bitrix24 import Bitrix24

        return Bitrix24(cfg)
    raise ValueError(f"Неизвестный тип CRM: {kind!r} (поддерживаются amocrm, bitrix24)")


__all__ = ["CRMConnector", "build_connector"]
