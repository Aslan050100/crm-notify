"""Проверка после установки (вызывается из install.bat)."""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        import requests  # noqa: F401
        import tzdata  # noqa: F401
    except ImportError as exc:
        print(f"ОШИБКА: библиотеки не установились ({exc}). Пришлите скрин этого окна.")
        return 1
    print("✔ Библиотеки установлены")
    env = ROOT / ".env"
    if not env.exists():
        shutil.copy(ROOT / ".env.example", env)
        print("✔ Создан файл .env — откройте его в Блокноте и впишите токен amoCRM и ключ Wazzup.")
    else:
        print("✔ Файл .env уже есть")
    print("\nГОТОВО. Дальше: заполните .env и запустите check.bat")
    return 0


if __name__ == "__main__":
    sys.exit(main())
