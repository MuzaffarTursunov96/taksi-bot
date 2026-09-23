import html
import logging
import time

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import storage
from filters import (
    OpenAIQuotaExceeded,
    classify_route,
    extract_phone,
    group_default_route,
    is_obvious_driver_ad,
    quick_prefilter,
)

logger = logging.getLogger(__name__)

_QUOTA_ALERT_COOLDOWN = 30 * 60  # adminlarni har xabarda emas, 30 daqiqada bir marta bezovta qilamiz
_last_quota_alert: float = 0.0


async def _notify_admins_quota_exceeded(bot: Bot) -> None:
    global _last_quota_alert
    now = time.monotonic()
    if now - _last_quota_alert < _QUOTA_ALERT_COOLDOWN:
        return
    _last_quota_alert = now

    storage.set_ai_enabled(False)
    text = (
        "⚠️ <b>OpenAI (ChatGPT) balansi tugadi yoki limit oshib ketdi!</b>\n\n"
        "AI tahlili avtomatik <b>o'chirildi</b> — xabarlar endi tekshirilmasdan "
        "(kamroq aniq) forward qilinadi.\n\n"
        "Hisobingizga mablag' qo'shgandan so'ng, qayta yoqish uchun: "
        "🤖 Bot menyusi → 🧠 AI yoqish."
    )
    for admin_id in storage.get_admin_ids():
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            logger.exception("Admin (%s)ga OpenAI xato haqida xabar yuborib bo'lmadi", admin_id)

# Bir xil odamning ketma-ket yozgan xabarlarini birlashtirish uchun (masalan
# "toshkentdan ketmoqchi edim" va keyingi xabarda "noringa"). Kalit: (chat_id, user_id).
_RECENT_TTL_SECONDS = 10 * 60
_recent_messages: dict[tuple[int, int], tuple[str, float]] = {}

# Bitta guruhni bir nechta ulangan akkaunt bir vaqtda tinglashi mumkin (masalan,
# ikkita shofyor bir xil guruhga a'zo) — bunday holda xuddi shu xabar ikki marta
# qayta ishlanmasligi uchun (chat_id, message_id) bo'yicha dublikatni tekshiramiz.
_DEDUP_TTL_SECONDS = 10 * 60
_processed_messages: dict[tuple[int, int], float] = {}


def _already_processed(chat_id: int, message_id: int | None) -> bool:
    if message_id is None:
        return False
    now = time.monotonic()
    for key, ts in list(_processed_messages.items()):
        if now - ts > _DEDUP_TTL_SECONDS:
            del _processed_messages[key]
    key = (chat_id, message_id)
    if key in _processed_messages:
        return True
    _processed_messages[key] = now
    return False


def build_context(chat_id: int, user_id: int, text: str) -> str:
    key = (chat_id, user_id)
    now = time.monotonic()
    prev = _recent_messages.get(key)
    if prev and now - prev[1] <= _RECENT_TTL_SECONDS:
        context_text = f"{prev[0]}\n{text}"
    else:
        context_text = text
    _recent_messages[key] = (context_text, now)
    return context_text


def build_group_link(chat_id: int, chat_username: str | None, message_id: int | None) -> str | None:
    if chat_username:
        base = f"https://t.me/{chat_username}"
        return f"{base}/{message_id}" if message_id else base
    # Xususiy super-guruhlar uchun ichki havola (faqat guruh a'zolarida ochiladi).
    chat_id_str = str(chat_id)
    if message_id and chat_id_str.startswith("-100"):
        internal_id = chat_id_str[4:]
        return f"https://t.me/c/{internal_id}/{message_id}"
    return None


def format_caption(
    route_info: dict,
    sender_display: str,
    phone: str | None,
    matched_text: str,
    group_name: str | None = None,
) -> str:
    # Diqqat: bu qiymatlar (shahar, telefon, guruh nomi, xabar matni) foydalanuvchi
    # yozgan yoki guruh nomidan olingan xom matn — HTML'dan xavfsiz "escape" qilinishi
    # shart, aks holda "<", ">", "&" belgilari borligida Telegram butun xabarni rad etadi
    # (masalan guruh nomida "TOSHKENT<>NORIN" bo'lsa).
    from_city = html.escape(route_info.get("from") or "?")
    to_city = html.escape(route_info.get("to") or "?")
    role_labels = {"passenger": "🧑 Yo'lovchi", "driver": "🚕 Shofyor", "unclear": "❔ Noaniq"}
    role_label = role_labels.get(route_info.get("author_role"), "❔ Noaniq")

    lines = [
        "🚖 <b>Yangi buyurtma!</b>",
        "━━━━━━━━━━━━━━",
        f"📍 Yo'nalish: <b>{from_city} → {to_city}</b>",
        f"{role_label}: {sender_display}",
    ]
    if phone:
        lines.append(f"📞 Telefon: <code>{html.escape(phone)}</code>")
    if group_name:
        lines.append(f"👥 Guruh: {html.escape(group_name)}")
    matched_text = html.escape(matched_text)
    lines += [
        "━━━━━━━━━━━━━━",
        "💬 Xabar matni:",
        f"<i>{matched_text}</i>",
    ]
    return "\n".join(lines)


def _build_keyboard(sender_username: str | None, group_link: str | None) -> InlineKeyboardMarkup | None:
    # Eslatma: Telegram inline tugmalarida "tel:" havolasi qo'llab-quvvatlanmaydi,
    # shuning uchun telefon raqami xabar matnida <code> sifatida qoladi (bosib qo'ng'iroq qilinadi).
    row = []
    if sender_username:
        row.append(InlineKeyboardButton(text="💬 Yozish", url=f"https://t.me/{sender_username}"))
    if group_link:
        row.append(InlineKeyboardButton(text="👥 Guruhga o'tish", url=group_link))
    if not row:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[row])


async def process_text(
    *,
    bot: Bot,
    driver_chat_ids: list[int],
    chat_id: int,
    user_id: int,
    text: str,
    sender_display: str,
    sender_username: str | None = None,
    contact_phone: str | None = None,
    group_name: str | None = None,
    group_username: str | None = None,
    message_id: int | None = None,
) -> None:
    """Xabarni tekshiradi, yo'nalish topilsa shofyorlarga forward qiladi.

    Bot API (aiogram) va Telethon (userbot) manbalaridan kelgan xabarlar uchun umumiy.
    """
    if not storage.is_processing_enabled():
        return

    if _already_processed(chat_id, message_id):
        return

    default_route = group_default_route(group_name)

    if not quick_prefilter(text) and default_route is None:
        return

    context_text = build_context(chat_id, user_id, text)

    if is_obvious_driver_ad(context_text):
        # Mashina markasi tilga olingan — juda ishonchli shofyor belgisi, OpenAI'ga
        # yubormasdan (xarajatni tejash) darhol o'tkazib yuboramiz.
        return

    if not storage.is_ai_enabled():
        # AI o'chirilgan — tasniflashsiz, faqat shahar nomi topilgan xabarlarni
        # to'g'ridan-to'g'ri forward qilamiz (kamroq aniq, lekin OpenAI xarajatisiz).
        from_city, to_city = default_route if default_route else (None, None)
        route_info = {"is_route": True, "from": from_city, "to": to_city, "author_role": "unclear"}
    else:
        ai_input = context_text
        if default_route:
            # Guruh doimiy yo'nalishga bag'ishlangan (masalan "TOSHKENT<>NORIN") — a'zolar
            # ko'pincha shahar nomini qayta yozmaydi, shuning uchun AI'ga eslatib qo'yamiz.
            ai_input = (
                f"[Eslatma: bu guruh doimiy ravishda {default_route[0]} - {default_route[1]} "
                f"yo'nalishi uchun ishlatiladi. Xabarda shahar nomi yo'q bo'lsa, shu "
                f"yo'nalishni nazarda tutgan deb hisobla.]\n{context_text}"
            )
        try:
            route_info = await classify_route(ai_input)
        except OpenAIQuotaExceeded:
            logger.warning("OpenAI kvotasi tugadi, AI o'chirilmoqda")
            await _notify_admins_quota_exceeded(bot)
            return
        logger.info("classify_route(%r) -> %r", ai_input, route_info)
        if not route_info or not route_info.get("is_route"):
            return

        if route_info.get("author_role") == "driver":
            # Bu boshqa shofyorning o'z reklama e'loni ("odam/pochta olamiz" — yo'lovchi
            # qidirayapti), mijoz emas — o'tkazib yuboramiz.
            return

        if default_route:
            route_info.setdefault("from", None)
            route_info.setdefault("to", None)
            if not route_info.get("from"):
                route_info["from"] = default_route[0]
            if not route_info.get("to"):
                route_info["to"] = default_route[1]

    phone = contact_phone or route_info.get("phone") or extract_phone(context_text)
    group_link = build_group_link(chat_id, group_username, message_id)
    caption = format_caption(route_info, sender_display, phone, context_text, group_name)
    keyboard = _build_keyboard(sender_username, group_link)

    delivery_mode = storage.get_delivery_mode()

    if delivery_mode != "group_only":
        for driver_chat_id in driver_chat_ids:
            try:
                await bot.send_message(driver_chat_id, caption, reply_markup=keyboard)
            except Exception:
                logger.exception("Shofyorga (%s) xabar yuborib bo'lmadi", driver_chat_id)

    dispatch_group_id = storage.get_dispatch_group_id()
    if delivery_mode != "private_only" and dispatch_group_id is not None:
        try:
            await bot.send_message(dispatch_group_id, caption, reply_markup=keyboard)
        except Exception:
            logger.exception("Buyurtmalar guruhiga (%s) xabar yuborib bo'lmadi", dispatch_group_id)
