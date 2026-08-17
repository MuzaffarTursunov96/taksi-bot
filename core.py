import logging
import time

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import storage
from filters import classify_route, extract_phone, quick_prefilter

logger = logging.getLogger(__name__)

# Bir xil odamning ketma-ket yozgan xabarlarini birlashtirish uchun (masalan
# "toshkentdan ketmoqchi edim" va keyingi xabarda "noringa"). Kalit: (chat_id, user_id).
_RECENT_TTL_SECONDS = 10 * 60
_recent_messages: dict[tuple[int, int], tuple[str, float]] = {}


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
    from_city = route_info.get("from") or "?"
    to_city = route_info.get("to") or "?"
    role_labels = {"passenger": "🧑 Yo'lovchi", "driver": "🚕 Shofyor", "unclear": "❔ Noaniq"}
    role_label = role_labels.get(route_info.get("author_role"), "❔ Noaniq")

    lines = [
        "🚖 <b>Yangi buyurtma!</b>",
        "━━━━━━━━━━━━━━",
        f"📍 Yo'nalish: <b>{from_city} → {to_city}</b>",
        f"{role_label}: {sender_display}",
    ]
    if phone:
        lines.append(f"📞 Telefon: <code>{phone}</code>")
    if group_name:
        lines.append(f"👥 Guruh: {group_name}")
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

    if not quick_prefilter(text):
        return

    context_text = build_context(chat_id, user_id, text)

    route_info = await classify_route(context_text)
    logger.info("classify_route(%r) -> %r", context_text, route_info)
    if not route_info or not route_info.get("is_route"):
        return

    if route_info.get("author_role") == "driver":
        # Bu boshqa shofyorning o'z reklama e'loni ("odam/pochta olamiz" — yo'lovchi
        # qidirayapti), mijoz emas — o'tkazib yuboramiz.
        return

    phone = contact_phone or route_info.get("phone") or extract_phone(context_text)
    group_link = build_group_link(chat_id, group_username, message_id)
    caption = format_caption(route_info, sender_display, phone, context_text, group_name)
    keyboard = _build_keyboard(sender_username, group_link)

    for driver_chat_id in driver_chat_ids:
        try:
            await bot.send_message(driver_chat_id, caption, reply_markup=keyboard)
        except Exception:
            logger.exception("Shofyorga (%s) xabar yuborib bo'lmadi", driver_chat_id)
