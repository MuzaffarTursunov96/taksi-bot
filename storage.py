import json
import random
import time
from pathlib import Path

from config import (
    DEFAULT_GROUP_MODE,
    INITIAL_ADMIN_IDS,
    INITIAL_DRIVER_CHAT_IDS,
    INITIAL_MONITORED_GROUP_IDS,
    ROOT_ADMIN_ID,
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


def is_driver(user_id: int) -> bool:
    return user_id in _load()


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


def _load_groups() -> dict[str, dict]:
    if not _GROUPS_PATH.exists():
        initial = {
            str(chat_id): {"title": f"guruh {chat_id}", "added_by": None}
            for chat_id in INITIAL_MONITORED_GROUP_IDS
        }
        _save_groups(initial)
        return initial
    raw = json.loads(_GROUPS_PATH.read_text(encoding="utf-8"))
    # Eski formatdagi ma'lumot ({chat_id: "nomi"}) bilan ham moslashadi.
    return {
        chat_id: (entry if isinstance(entry, dict) else {"title": entry, "added_by": None})
        for chat_id, entry in raw.items()
    }


def _save_groups(groups: dict[str, dict]) -> None:
    _GROUPS_PATH.write_text(json.dumps(groups), encoding="utf-8")


def get_monitored_groups() -> dict[int, str]:
    """{chat_id: guruh_nomi} formatida yoqilgan guruhlar ro'yxati."""
    return {int(chat_id): entry["title"] for chat_id, entry in _load_groups().items()}


def get_group_owner(chat_id: int) -> int | None:
    """Shu guruhni kim yoqqanini qaytaradi (bilinmasa None)."""
    entry = _load_groups().get(str(chat_id))
    return entry.get("added_by") if entry else None


def enable_group(chat_id: int, title: str, added_by: int | None = None) -> None:
    groups = _load_groups()
    existing = groups.get(str(chat_id))
    owner = added_by if added_by is not None else (existing.get("added_by") if existing else None)
    groups[str(chat_id)] = {"title": title, "added_by": owner}
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


def is_group_monitored(chat_id: int) -> bool:
    """Bot faqat qo'lda yoqilgan (tanlangan) guruhlarni tinglaydi — "hammasi" rejimi
    butunlay olib tashlandi."""
    return str(chat_id) in _load_groups()


_KNOWN_GROUPS_PATH = Path(__file__).parent / "known_groups.json"


def _load_known_groups() -> dict[str, str]:
    if not _KNOWN_GROUPS_PATH.exists():
        _save_known_groups({})
        return {}
    return json.loads(_KNOWN_GROUPS_PATH.read_text(encoding="utf-8"))


def _save_known_groups(groups: dict[str, str]) -> None:
    _KNOWN_GROUPS_PATH.write_text(json.dumps(groups), encoding="utf-8")


def record_known_group(chat_id: int, title: str | None) -> None:
    """Bot yoki Telethon ko'rgan har qanday guruh nomini eslab qoladi — bu ro'yxat
    "guruh qo'shish" menyusida nomlarni ko'rsatish uchun ishlatiladi."""
    if not title:
        return
    groups = _load_known_groups()
    if groups.get(str(chat_id)) != title:
        groups[str(chat_id)] = title
        _save_known_groups(groups)


def get_known_groups() -> dict[int, str]:
    return {int(chat_id): title for chat_id, title in _load_known_groups().items()}


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


def get_dispatch_group_id() -> int | None:
    """Topilgan buyurtmalar shaxsiy DM bilan bir qatorda shu guruhga ham
    yuboriladi (sozlanmagan bo'lsa None)."""
    return _load_settings().get("dispatch_group_id")


def set_dispatch_group_id(chat_id: int | None) -> None:
    settings = _load_settings()
    settings["dispatch_group_id"] = chat_id
    _save_settings(settings)


def get_verification_group_id() -> int | None:
    """Yangi shofyorlar botga /start bergunda shu guruh a'zosi ekanligi tekshiriladi
    (sozlanmagan bo'lsa tekshiruv o'tkazib yuboriladi)."""
    return _load_settings().get("verification_group_id")


def set_verification_group_id(chat_id: int | None) -> None:
    settings = _load_settings()
    settings["verification_group_id"] = chat_id
    _save_settings(settings)


_PENDING_REQUESTS_PATH = Path(__file__).parent / "pending_requests.json"


def _load_pending_requests() -> dict[str, dict]:
    if not _PENDING_REQUESTS_PATH.exists():
        _save_pending_requests({})
        return {}
    return json.loads(_PENDING_REQUESTS_PATH.read_text(encoding="utf-8"))


def _save_pending_requests(requests: dict[str, dict]) -> None:
    _PENDING_REQUESTS_PATH.write_text(json.dumps(requests), encoding="utf-8")


def create_pending_request(user_id: int, groups: dict[int, str]) -> str:
    """{chat_id: title} guruhlar ro'yxatini so'rov sifatida saqlaydi, so'rov ID qaytaradi."""
    requests = _load_pending_requests()
    request_id = f"{int(time.time())}{random.randint(100, 999)}"
    requests[request_id] = {"user_id": user_id, "groups": {str(k): v for k, v in groups.items()}}
    _save_pending_requests(requests)
    return request_id


def get_pending_request(request_id: str) -> dict | None:
    return _load_pending_requests().get(request_id)


def delete_pending_request(request_id: str) -> None:
    requests = _load_pending_requests()
    if request_id in requests:
        del requests[request_id]
        _save_pending_requests(requests)


def get_delivery_mode() -> str:
    """"both" — DM + guruh, "group_only" — faqat guruh, "private_only" — faqat DM."""
    return _load_settings().get("delivery_mode", "both")


def set_delivery_mode(mode: str) -> None:
    settings = _load_settings()
    settings["delivery_mode"] = mode
    _save_settings(settings)


_NOTIFIED_CONFLICTS_PATH = Path(__file__).parent / "notified_conflicts.json"


def _load_notified_conflicts() -> list[str]:
    if not _NOTIFIED_CONFLICTS_PATH.exists():
        _save_notified_conflicts([])
        return []
    return json.loads(_NOTIFIED_CONFLICTS_PATH.read_text(encoding="utf-8"))


def _save_notified_conflicts(items: list[str]) -> None:
    _NOTIFIED_CONFLICTS_PATH.write_text(json.dumps(items), encoding="utf-8")


def was_conflict_notified(chat_id: int, viewer_id: int) -> bool:
    return f"{chat_id}:{viewer_id}" in _load_notified_conflicts()


def mark_conflict_notified(chat_id: int, viewer_id: int) -> None:
    items = _load_notified_conflicts()
    key = f"{chat_id}:{viewer_id}"
    if key not in items:
        items.append(key)
        _save_notified_conflicts(items)


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


def is_root(user_id: int) -> bool:
    """Yagona shaxs — faqat u botni va AI'ni yoqa/o'chira oladi."""
    return ROOT_ADMIN_ID is not None and user_id == ROOT_ADMIN_ID


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


_ACCOUNTS_PATH = Path(__file__).parent / "linked_accounts.json"


def _load_accounts() -> dict[str, dict]:
    if not _ACCOUNTS_PATH.exists():
        _save_accounts({})
        return {}
    return json.loads(_ACCOUNTS_PATH.read_text(encoding="utf-8"))


def _save_accounts(accounts: dict[str, dict]) -> None:
    _ACCOUNTS_PATH.write_text(json.dumps(accounts), encoding="utf-8")


def get_linked_accounts() -> dict[int, dict]:
    """{owner_user_id: {"session": str, "phone": str, "api_id": int|None,
    "api_hash": str|None}} — ulangan Telethon akkauntlari."""
    return {int(owner_id): info for owner_id, info in _load_accounts().items()}


def add_linked_account(
    owner_id: int,
    session_name: str,
    phone: str,
    api_id: int | None = None,
    api_hash: str | None = None,
) -> None:
    accounts = _load_accounts()
    accounts[str(owner_id)] = {
        "session": session_name,
        "phone": phone,
        "api_id": api_id,
        "api_hash": api_hash,
    }
    _save_accounts(accounts)


def remove_linked_account(owner_id: int) -> bool:
    accounts = _load_accounts()
    if str(owner_id) not in accounts:
        return False
    del accounts[str(owner_id)]
    _save_accounts(accounts)
    return True
