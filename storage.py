import json
from pathlib import Path

from config import (
    DEFAULT_GROUP_MODE,
    INITIAL_ADMIN_IDS,
    INITIAL_DRIVER_CHAT_IDS,
    INITIAL_MONITORED_GROUP_IDS,
)

_STORAGE_PATH = Path(__file__).parent / "drivers.json"


def _load() -> list[int]:
    if not _STORAGE_PATH.exists():
        _save(INITIAL_DRIVER_CHAT_IDS)
        return list(INITIAL_DRIVER_CHAT_IDS)
    return json.loads(_STORAGE_PATH.read_text(encoding="utf-8"))


def _save(driver_ids: list[int]) -> None:
    _STORAGE_PATH.write_text(json.dumps(driver_ids), encoding="utf-8")


def get_driver_ids() -> list[int]:
    return _load()


def add_driver_id(chat_id: int) -> bool:
    """True qaytaradi agar yangi qo'shilgan bo'lsa, allaqachon bor bo'lsa False."""
    driver_ids = _load()
    if chat_id in driver_ids:
        return False
    driver_ids.append(chat_id)
    _save(driver_ids)
    return True


def remove_driver_id(chat_id: int) -> bool:
    """True qaytaradi agar o'chirilgan bo'lsa, ro'yxatda bo'lmasa False."""
    driver_ids = _load()
    if chat_id not in driver_ids:
        return False
    driver_ids.remove(chat_id)
    _save(driver_ids)
    return True


_GROUPS_PATH = Path(__file__).parent / "groups.json"


def _load_groups() -> dict[str, str]:
    if not _GROUPS_PATH.exists():
        initial = {str(chat_id): f"guruh {chat_id}" for chat_id in INITIAL_MONITORED_GROUP_IDS}
        _save_groups(initial)
        return initial
    return json.loads(_GROUPS_PATH.read_text(encoding="utf-8"))


def _save_groups(groups: dict[str, str]) -> None:
    _GROUPS_PATH.write_text(json.dumps(groups), encoding="utf-8")


def get_monitored_groups() -> dict[int, str]:
    """{chat_id: guruh_nomi} formatida yoqilgan guruhlar ro'yxati."""
    return {int(chat_id): title for chat_id, title in _load_groups().items()}


def enable_group(chat_id: int, title: str) -> None:
    groups = _load_groups()
    groups[str(chat_id)] = title
    _save_groups(groups)


def disable_group(chat_id: int) -> bool:
    """True qaytaradi agar o'chirilgan bo'lsa, ro'yxatda bo'lmasa False."""
    groups = _load_groups()
    if str(chat_id) not in groups:
        return False
    del groups[str(chat_id)]
    _save_groups(groups)
    return True


_SETTINGS_PATH = Path(__file__).parent / "settings.json"
_DEFAULT_SETTINGS = {
    "group_mode": DEFAULT_GROUP_MODE,
    "processing_enabled": True,
    "ai_enabled": True,
}


def _load_settings() -> dict:
    if not _SETTINGS_PATH.exists():
        _save_settings(_DEFAULT_SETTINGS)
        return dict(_DEFAULT_SETTINGS)
    return json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))


def _save_settings(settings: dict) -> None:
    _SETTINGS_PATH.write_text(json.dumps(settings), encoding="utf-8")


def get_group_mode() -> str:
    return _load_settings().get("group_mode", "all")


def set_group_mode(mode: str) -> None:
    settings = _load_settings()
    settings["group_mode"] = mode
    _save_settings(settings)


def is_group_monitored(chat_id: int) -> bool:
    if get_group_mode() == "all":
        return True
    return str(chat_id) in _load_groups()


def is_processing_enabled() -> bool:
    return _load_settings().get("processing_enabled", True)


def set_processing_enabled(enabled: bool) -> None:
    settings = _load_settings()
    settings["processing_enabled"] = enabled
    _save_settings(settings)


def is_ai_enabled() -> bool:
    return _load_settings().get("ai_enabled", True)


def set_ai_enabled(enabled: bool) -> None:
    settings = _load_settings()
    settings["ai_enabled"] = enabled
    _save_settings(settings)


_ADMINS_PATH = Path(__file__).parent / "admins.json"


def _load_admins() -> list[int]:
    if not _ADMINS_PATH.exists():
        _save_admins(INITIAL_ADMIN_IDS)
        return list(INITIAL_ADMIN_IDS)
    return json.loads(_ADMINS_PATH.read_text(encoding="utf-8"))


def _save_admins(admin_ids: list[int]) -> None:
    _ADMINS_PATH.write_text(json.dumps(admin_ids), encoding="utf-8")


def get_admin_ids() -> list[int]:
    return _load_admins()


def is_admin(user_id: int) -> bool:
    return user_id in _load_admins()


def is_founder(user_id: int) -> bool:
    """Asosiy (.env dagi OWNER_ID) adminlar — faqat ular boshqa adminlarni
    qo'sha/o'chira oladi."""
    return user_id in INITIAL_ADMIN_IDS


def add_admin_id(chat_id: int) -> bool:
    """True qaytaradi agar yangi qo'shilgan bo'lsa, allaqachon bor bo'lsa False."""
    admin_ids = _load_admins()
    if chat_id in admin_ids:
        return False
    admin_ids.append(chat_id)
    _save_admins(admin_ids)
    return True


def remove_admin_id(chat_id: int) -> bool:
    """True qaytaradi agar o'chirilgan bo'lsa; asosiy (.env dagi) adminlarni o'chirishga
    yo'l qo'ymaydi — ular doimiy himoyalangan."""
    if chat_id in INITIAL_ADMIN_IDS:
        return False
    admin_ids = _load_admins()
    if chat_id not in admin_ids:
        return False
    admin_ids.remove(chat_id)
    _save_admins(admin_ids)
    return True
