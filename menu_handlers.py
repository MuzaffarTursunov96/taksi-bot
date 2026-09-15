import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BotCommandScopeChat,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

import commands
import telethon_accounts
import link_account
from link_account import BTN_LINK_ACCOUNT
import storage

logger = logging.getLogger(__name__)
router = Router()


async def _safe_edit_text(message: Message, text: str, reply_markup=None) -> None:
    """Telegram bir xil matn/tugmalarni qayta yuborishga ruxsat bermaydi —
    bunday xatoni sezilmas qilib o'tkazib yuboramiz."""
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise


async def _safe_edit_markup(message: Message, reply_markup=None) -> None:
    try:
        await message.edit_reply_markup(reply_markup=reply_markup)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

BTN_BOT = "🤖 Bot"
BTN_GROUPS = "👥 Guruhlar"
BTN_DRIVERS = "🚕 Shofyorlar"
BTN_ADMINS = "👤 Adminlar"
BTN_STATUS = "📊 Holat"


GROUPS_PAGE_SIZE = 8


class AdminInput(StatesGroup):
    driver_add = State()
    driver_remove = State()
    admin_add = State()
    admin_remove = State()


class DriverGroupPick(StatesGroup):
    picking = State()


def _is_admin(message: Message) -> bool:
    return storage.is_admin(message.from_user.id)


def _is_founder(message: Message) -> bool:
    return storage.is_founder(message.from_user.id)


def _is_root(message: Message) -> bool:
    return storage.is_root(message.from_user.id)


def _parse_chat_id(text: str) -> int | None:
    text = (text or "").strip()
    if text.lstrip("-").isdigit():
        return int(text)
    return None


def main_reply_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BTN_GROUPS), KeyboardButton(text=BTN_DRIVERS)],
        [KeyboardButton(text=BTN_STATUS), KeyboardButton(text=BTN_LINK_ACCOUNT)],
    ]
    bottom_row = []
    if storage.is_root(user_id):
        bottom_row.append(KeyboardButton(text=BTN_BOT))
    if storage.is_founder(user_id):
        bottom_row.append(KeyboardButton(text=BTN_ADMINS))
    if bottom_row:
        rows.append(bottom_row)
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def bot_inline_keyboard() -> InlineKeyboardMarkup:
    ai_state = "🧠 AI: YOQILGAN ✅" if storage.is_ai_enabled() else "🧠 AI: O'CHIRILGAN ⏸"
    bot_state = "🤖 Bot: YOQILGAN ✅" if storage.is_processing_enabled() else "🤖 Bot: O'CHIRILGAN ⏸"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=bot_state, callback_data="noop")],
            [
                InlineKeyboardButton(text="▶️ Botni yoqish", callback_data="bot:on"),
                InlineKeyboardButton(text="⏸ Botni o'chirish", callback_data="bot:off"),
            ],
            [InlineKeyboardButton(text=ai_state, callback_data="noop")],
            [
                InlineKeyboardButton(text="🧠 AI yoqish", callback_data="ai:on"),
                InlineKeyboardButton(text="🧠 AI o'chirish", callback_data="ai:off"),
            ],
        ]
    )


def _short(title: str, limit: int = 30) -> str:
    return title if len(title) <= limit else title[: limit - 1] + "…"


def _group_display_name(chat_id: int, fallback: str) -> str:
    """Telethon xotirasidagi haqiqiy nomni afzal ko'radi (agar mavjud bo'lsa)."""
    known = storage.get_known_groups()
    return known.get(chat_id, fallback)


def groups_menu_text() -> str:
    return (
        "👥 <b>Guruhlar boshqaruvi</b>\n\n"
        "🎯 Bot faqat pastdagi \"Tinglanayotganlar\" ro'yxatidagi guruhlarni tekshiradi, "
        "qolganlarini e'tiborsiz qoldiradi."
    )


def groups_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Tinglanayotganlar", callback_data="group:list")],
            [InlineKeyboardButton(text="➕ Guruh qo'shish", callback_data="group:addpage:0")],
        ]
    )


def monitored_groups_keyboard() -> InlineKeyboardMarkup:
    groups = storage.get_monitored_groups()
    rows = [
        [
            InlineKeyboardButton(
                text=_short(_group_display_name(chat_id, title)),
                callback_data=f"group:view:{chat_id}",
            )
        ]
        for chat_id, title in groups.items()
    ]
    if not rows:
        rows.append([InlineKeyboardButton(text="(bo'sh)", callback_data="noop")])
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="group:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def group_view_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛑 Tinglashni to'xtatish", callback_data=f"group:disable:{chat_id}")],
            [InlineKeyboardButton(text="🔙 Ro'yxatga qaytish", callback_data="group:list")],
        ]
    )


def add_group_keyboard(page: int) -> InlineKeyboardMarkup:
    known = storage.get_known_groups()
    monitored_ids = set(storage.get_monitored_groups().keys())
    candidates = sorted(
        ((cid, title) for cid, title in known.items() if cid not in monitored_ids),
        key=lambda item: item[1].lower(),
    )
    start = page * GROUPS_PAGE_SIZE
    page_items = candidates[start : start + GROUPS_PAGE_SIZE]

    rows = [
        [InlineKeyboardButton(text=_short(title), callback_data=f"group:enable:{chat_id}:{page}")]
        for chat_id, title in page_items
    ]
    if not candidates:
        rows.append([InlineKeyboardButton(text="(qo'shiladigan guruh yo'q)", callback_data="noop")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"group:addpage:{page - 1}"))
    nav.append(InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"group:addpage:{page}"))
    if start + GROUPS_PAGE_SIZE < len(candidates):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"group:addpage:{page + 1}"))
    rows.append(nav)

    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="group:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def drivers_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Ro'yxatni ko'rish", callback_data="driver:list")],
            [
                InlineKeyboardButton(text="➕ Shofyor qo'shish", callback_data="driver:add"),
                InlineKeyboardButton(text="➖ Shofyor o'chirish", callback_data="driver:remove"),
            ],
        ]
    )


def admins_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Ro'yxatni ko'rish", callback_data="admin:list")],
            [
                InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="admin:add"),
                InlineKeyboardButton(text="➖ Admin o'chirish", callback_data="admin:remove"),
            ],
            [InlineKeyboardButton(text="📢 Buyurtmalar guruhi", callback_data="dispatch:menu")],
            [InlineKeyboardButton(text="🚪 Tekshiruv guruhi", callback_data="verify:menu")],
            [InlineKeyboardButton(text="🔌 Ulangan akkauntlar", callback_data="accounts:status")],
        ]
    )


def verify_menu_text() -> str:
    chat_id = storage.get_verification_group_id()
    if chat_id is None:
        return (
            "🚪 <b>Tekshiruv guruhi</b>\n\n"
            "Hozircha sozlanmagan — yangi odam /start bersa, hech qanday tekshiruv bo'lmaydi."
        )
    title = storage.get_known_groups().get(chat_id, str(chat_id))
    return (
        f"🚪 <b>Tekshiruv guruhi</b>\n\n"
        f"Joriy: {title} (<code>{chat_id}</code>)\n\n"
        "Yangi odam botga /start bersa, shu guruh a'zosi ekanligi tekshiriladi. "
        "A'zo bo'lmasa, adminlarga xabar boradi."
    )


def verify_menu_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="📋 Guruh tanlash", callback_data="verify:pick:0")]]
    if storage.get_verification_group_id() is not None:
        rows.append([InlineKeyboardButton(text="🗑 O'chirish", callback_data="verify:clear")])
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def verify_pick_keyboard(page: int) -> InlineKeyboardMarkup:
    known = sorted(storage.get_known_groups().items(), key=lambda item: item[1].lower())
    start = page * GROUPS_PAGE_SIZE
    page_items = known[start : start + GROUPS_PAGE_SIZE]

    rows = [
        [InlineKeyboardButton(text=_short(title), callback_data=f"verify:set:{chat_id}")]
        for chat_id, title in page_items
    ]
    if not known:
        rows.append([InlineKeyboardButton(text="(guruh topilmadi)", callback_data="noop")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"verify:pick:{page - 1}"))
    if start + GROUPS_PAGE_SIZE < len(known):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"verify:pick:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="verify:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


_DELIVERY_MODE_LABELS = {
    "both": "📤 DM + guruh (ikkalasi ham)",
    "group_only": "👥 Faqat guruhga",
    "private_only": "📩 Faqat shaxsiy DM",
}


def dispatch_menu_text() -> str:
    chat_id = storage.get_dispatch_group_id()
    mode_label = _DELIVERY_MODE_LABELS.get(storage.get_delivery_mode(), "?")
    if chat_id is None:
        group_line = "Hozircha sozlanmagan."
    else:
        title = storage.get_known_groups().get(chat_id, str(chat_id))
        group_line = f"Joriy: {title} (<code>{chat_id}</code>)"
    return f"📢 <b>Buyurtmalar guruhi</b>\n\n{group_line}\n\n🔀 Yuborish rejimi: <b>{mode_label}</b>"


def dispatch_menu_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="📋 Guruh tanlash", callback_data="dispatch:pick:0")]]
    if storage.get_dispatch_group_id() is not None:
        rows.append([InlineKeyboardButton(text="🗑 O'chirish", callback_data="dispatch:clear")])
    rows.append(
        [
            InlineKeyboardButton(text="📤 DM+guruh", callback_data="dispatch:mode:both"),
            InlineKeyboardButton(text="👥 Faqat guruh", callback_data="dispatch:mode:group_only"),
            InlineKeyboardButton(text="📩 Faqat DM", callback_data="dispatch:mode:private_only"),
        ]
    )
    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dispatch_pick_keyboard(page: int) -> InlineKeyboardMarkup:
    known = sorted(storage.get_known_groups().items(), key=lambda item: item[1].lower())
    start = page * GROUPS_PAGE_SIZE
    page_items = known[start : start + GROUPS_PAGE_SIZE]

    rows = [
        [InlineKeyboardButton(text=_short(title), callback_data=f"dispatch:set:{chat_id}")]
        for chat_id, title in page_items
    ]
    if not known:
        rows.append([InlineKeyboardButton(text="(guruh topilmadi)", callback_data="noop")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"dispatch:pick:{page - 1}"))
    if start + GROUPS_PAGE_SIZE < len(known):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"dispatch:pick:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="dispatch:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _status_text() -> str:
    bot_state = "▶️ YOQILGAN" if storage.is_processing_enabled() else "⏸ O'CHIRILGAN"
    ai_state = "▶️ YOQILGAN" if storage.is_ai_enabled() else "⏸ O'CHIRILGAN"
    return (
        f"🤖 Bot: <b>{bot_state}</b>\n"
        f"🧠 ChatGPT tahlili: <b>{ai_state}</b>\n"
        f"👥 Guruh rejimi: <b>🎯 TANLANGAN (doim)</b>"
    )


BTN_MY_GROUPS = "➕ Guruh qo'shish"


def _driver_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_MY_GROUPS)]],
        resize_keyboard=True,
    )


async def _is_member_of(bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status not in ("left", "kicked")
    except TelegramBadRequest:
        return False


async def _notify_admins_new_person(message: Message) -> None:
    user = message.from_user
    who = f"@{user.username}" if user.username else user.full_name
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Guruhga qo'shdim", callback_data=f"verify:confirm:{user.id}")]
        ]
    )
    text = (
        f"🔔 Yangi odam botga /start berdi, lekin tekshiruv guruhida emas.\n\n"
        f"Kim: {who} (<code>{user.id}</code>)\n\n"
        "Uni tekshiruv guruhiga qo'shgandan so'ng, shu tugmani bosing:"
    )
    for admin_id in storage.get_admin_ids():
        try:
            await message.bot.send_message(admin_id, text, reply_markup=keyboard)
        except Exception:
            logger.exception("Admin (%s)ga yangi odam haqida xabar yuborib bo'lmadi", admin_id)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id
    if not storage.is_admin(user_id):
        if storage.is_driver(user_id):
            await message.answer(
                "🚕 Salom! Guruhlaringizni kuzatuvga qo'shish uchun pastdagi tugmani bosing:",
                reply_markup=_driver_reply_keyboard(),
            )
            return

        verification_group_id = storage.get_verification_group_id()
        if verification_group_id is not None:
            if await _is_member_of(message.bot, verification_group_id, user_id):
                storage.add_driver_id(user_id)
                await message.answer(
                    "🚕 Xush kelibsiz! Guruhlaringizni kuzatuvga qo'shish uchun "
                    "pastdagi tugmani bosing:",
                    reply_markup=_driver_reply_keyboard(),
                )
                return
            await message.reply(
                "🚪 Assalomu alaykum! Sizni ko'rib chiqish uchun administratorlarga "
                "xabar berdik. Tez orada javob bo'ladi."
            )
            await _notify_admins_new_person(message)
            return

        await message.reply(
            "🤖 Salom! Bu bot yo'nalish e'lonlarini avtomatik kuzatib boradi.\n"
            "O'z chat ID'ingizni bilish uchun: /mening_id"
        )
        return
    await message.answer(
        "Boshqaruv menyusi:",
        reply_markup=main_reply_keyboard(message.from_user.id),
    )


@router.message(F.text == BTN_BOT, _is_root)
async def show_bot_menu(message: Message) -> None:
    await message.answer("🤖 Bot boshqaruvi:", reply_markup=bot_inline_keyboard())


@router.message(F.text == BTN_GROUPS, _is_admin)
async def show_groups_menu(message: Message) -> None:
    await message.answer(groups_menu_text(), reply_markup=groups_inline_keyboard())


@router.message(F.text == BTN_MY_GROUPS)
def _add_candidates(page: int) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    known = storage.get_known_groups()
    monitored_ids = set(storage.get_monitored_groups().keys())
    candidates = sorted(
        ((cid, title) for cid, title in known.items() if cid not in monitored_ids),
        key=lambda item: item[1].lower(),
    )
    start = page * GROUPS_PAGE_SIZE
    return candidates, candidates[start : start + GROUPS_PAGE_SIZE]


def driver_pick_keyboard(selected: set[int], page: int) -> InlineKeyboardMarkup:
    candidates, page_items = _add_candidates(page)
    start = page * GROUPS_PAGE_SIZE

    rows = [
        [
            InlineKeyboardButton(
                text=f"{'✅' if chat_id in selected else '⬜'} {_short(title)}",
                callback_data=f"pick:toggle:{chat_id}:{page}",
            )
        ]
        for chat_id, title in page_items
    ]
    if not candidates:
        rows.append([InlineKeyboardButton(text="(guruh topilmadi)", callback_data="noop")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"pick:page:{page - 1}"))
    if start + GROUPS_PAGE_SIZE < len(candidates):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"pick:page:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text=f"✅ Yuborish ({len(selected)})", callback_data="pick:submit")])
    rows.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="pick:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_my_groups_menu(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    if not (storage.is_driver(user_id) or storage.is_admin(user_id)):
        return
    if user_id not in storage.get_linked_accounts():
        await link_account.begin_link_flow(message, state)
        return

    if storage.is_admin(user_id):
        # Adminlar to'g'ridan-to'g'ri (tasdiqlashsiz) guruh qo'sha oladi.
        await message.answer(
            "➕ Qo'shish uchun guruhni tanlang:",
            reply_markup=add_group_keyboard(0),
        )
        return

    # Shofyorlar bir nechta guruhni belgilab, admin tasdiqlashi uchun yuboradi.
    await state.set_state(DriverGroupPick.picking)
    await state.update_data(selected=[])
    await message.answer(
        "➕ Kuzatuvga qo'shmoqchi bo'lgan guruhlaringizni belgilang, so'ng \"Yuborish\"ni bosing:",
        reply_markup=driver_pick_keyboard(set(), 0),
    )


@router.callback_query(DriverGroupPick.picking, F.data.startswith("pick:toggle:"))
async def cb_pick_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    chat_id, page = int(parts[2]), int(parts[3])
    data = await state.get_data()
    selected = set(data.get("selected", []))
    selected.symmetric_difference_update({chat_id})
    await state.update_data(selected=list(selected))
    await callback.answer()
    await _safe_edit_markup(callback.message, driver_pick_keyboard(selected, page))


@router.callback_query(DriverGroupPick.picking, F.data.startswith("pick:page:"))
async def cb_pick_page(callback: CallbackQuery, state: FSMContext) -> None:
    page = int(callback.data.split(":")[2])
    data = await state.get_data()
    selected = set(data.get("selected", []))
    await callback.answer()
    await _safe_edit_markup(callback.message, driver_pick_keyboard(selected, page))


@router.callback_query(DriverGroupPick.picking, F.data == "pick:cancel")
async def cb_pick_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Bekor qilindi")
    await _safe_edit_text(callback.message, "Bekor qilindi.")


@router.callback_query(DriverGroupPick.picking, F.data == "pick:submit")
async def cb_pick_submit(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected = data.get("selected", [])
    if not selected:
        return await callback.answer("Hech narsa belgilanmagan", show_alert=True)

    known = storage.get_known_groups()
    groups = {chat_id: known.get(chat_id, str(chat_id)) for chat_id in selected}
    request_id = storage.create_pending_request(callback.from_user.id, groups)
    await state.clear()
    await callback.answer("Yuborildi ✅")
    await _safe_edit_text(callback.message, "✅ So'rovingiz yuborildi. Admin tasdiqlashini kuting.")

    user = callback.from_user
    who = f"@{user.username}" if user.username else user.full_name
    lines = "\n".join(f"• {title}" for title in groups.values())
    text = (
        f"📥 <b>Yangi guruh so'rovi!</b>\n\nKim: {who} (<code>{user.id}</code>)\n\n"
        f"Guruhlar:\n{lines}"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"reqgrp:accept:{request_id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reqgrp:reject:{request_id}"),
            ]
        ]
    )
    for admin_id in storage.get_admin_ids():
        try:
            await callback.bot.send_message(admin_id, text, reply_markup=keyboard)
        except Exception:
            logger.exception("Admin (%s)ga guruh so'rovini yuborib bo'lmadi", admin_id)


@router.callback_query(F.data.startswith("reqgrp:accept:"))
async def cb_reqgrp_accept(callback: CallbackQuery) -> None:
    if not storage.is_admin(callback.from_user.id):
        return await callback.answer()
    request_id = callback.data.split(":", 2)[2]
    req = storage.get_pending_request(request_id)
    if not req:
        return await callback.answer("So'rov topilmadi (eskirgan bo'lishi mumkin)", show_alert=True)

    for chat_id_str, title in req["groups"].items():
        storage.enable_group(int(chat_id_str), title, added_by=req["user_id"])
    storage.delete_pending_request(request_id)

    await callback.answer("Qabul qilindi ✅")
    await _safe_edit_text(callback.message, callback.message.html_text + "\n\n✅ <b>Qabul qilindi</b>")
    try:
        await callback.bot.send_message(
            req["user_id"], "✅ Guruhlaringiz qabul qilindi va endi tinglanmoqda!"
        )
    except Exception:
        logger.exception("Foydalanuvchi (%s)ga tasdiq xabarini yuborib bo'lmadi", req["user_id"])


@router.callback_query(F.data.startswith("reqgrp:reject:"))
async def cb_reqgrp_reject(callback: CallbackQuery) -> None:
    if not storage.is_admin(callback.from_user.id):
        return await callback.answer()
    request_id = callback.data.split(":", 2)[2]
    req = storage.get_pending_request(request_id)
    if req:
        storage.delete_pending_request(request_id)

    await callback.answer("Rad etildi")
    await _safe_edit_text(callback.message, callback.message.html_text + "\n\n❌ <b>Rad etildi</b>")
    if req:
        try:
            await callback.bot.send_message(req["user_id"], "❌ Guruh so'rovingiz rad etildi.")
        except Exception:
            logger.exception("Foydalanuvchi (%s)ga rad javobini yuborib bo'lmadi", req["user_id"])


@router.message(F.text == BTN_DRIVERS, _is_admin)
async def show_drivers_menu(message: Message) -> None:
    await message.answer("🚕 Shofyorlar boshqaruvi:", reply_markup=drivers_inline_keyboard())


@router.message(F.text == BTN_ADMINS, _is_founder)
async def show_admins_menu(message: Message) -> None:
    await message.answer("👤 Adminlar boshqaruvi:", reply_markup=admins_inline_keyboard())


@router.message(F.text == BTN_STATUS, _is_admin)
async def show_status(message: Message) -> None:
    await message.answer(await _status_text())


# --- Callback (inline tugma) handlerlar ---


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "bot:on")
async def cb_bot_on(callback: CallbackQuery) -> None:
    if not storage.is_root(callback.from_user.id):
        return await callback.answer()
    storage.set_processing_enabled(True)
    await callback.answer("Bot yoqildi ✅")
    await _safe_edit_markup(callback.message, bot_inline_keyboard())


@router.callback_query(F.data == "bot:off")
async def cb_bot_off(callback: CallbackQuery) -> None:
    if not storage.is_root(callback.from_user.id):
        return await callback.answer()
    storage.set_processing_enabled(False)
    await callback.answer("Bot o'chirildi ⏸")
    await _safe_edit_markup(callback.message, bot_inline_keyboard())


@router.callback_query(F.data == "ai:on")
async def cb_ai_on(callback: CallbackQuery) -> None:
    if not storage.is_root(callback.from_user.id):
        return await callback.answer()
    storage.set_ai_enabled(True)
    await callback.answer("AI tahlili yoqildi ✅")
    await _safe_edit_markup(callback.message, bot_inline_keyboard())


@router.callback_query(F.data == "ai:off")
async def cb_ai_off(callback: CallbackQuery) -> None:
    if not storage.is_root(callback.from_user.id):
        return await callback.answer()
    storage.set_ai_enabled(False)
    await callback.answer("AI tahlili o'chirildi ⏸")
    await _safe_edit_markup(callback.message, bot_inline_keyboard())


@router.callback_query(F.data == "group:menu")
async def cb_group_menu(callback: CallbackQuery) -> None:
    if not storage.is_admin(callback.from_user.id):
        return await callback.answer()
    await callback.answer()
    await _safe_edit_text(callback.message, groups_menu_text(), groups_inline_keyboard())


@router.callback_query(F.data == "group:list")
async def cb_group_list(callback: CallbackQuery) -> None:
    if not storage.is_admin(callback.from_user.id):
        return await callback.answer()
    await callback.answer()
    await _safe_edit_text(
        callback.message,
        "📋 Tinglanayotgan guruhlar (to'xtatish uchun bosing):",
        monitored_groups_keyboard(),
    )


@router.callback_query(F.data.startswith("group:view:"))
async def cb_group_view(callback: CallbackQuery) -> None:
    if not storage.is_admin(callback.from_user.id):
        return await callback.answer()
    chat_id = int(callback.data.split(":")[2])
    fallback = storage.get_monitored_groups().get(chat_id, str(chat_id))
    title = _group_display_name(chat_id, fallback)
    await callback.answer()
    await _safe_edit_text(
        callback.message,
        f"👥 <b>{title}</b>\n<code>{chat_id}</code>",
        group_view_keyboard(chat_id),
    )


@router.callback_query(F.data.startswith("group:disable:"))
async def cb_group_disable(callback: CallbackQuery) -> None:
    if not storage.is_admin(callback.from_user.id):
        return await callback.answer()
    chat_id = int(callback.data.split(":")[2])
    storage.disable_group(chat_id)
    await callback.answer("Tinglash to'xtatildi ✅")
    await _safe_edit_text(
        callback.message,
        "📋 Tinglanayotgan guruhlar (to'xtatish uchun bosing):",
        monitored_groups_keyboard(),
    )


@router.callback_query(F.data.startswith("group:addpage:"))
async def cb_group_addpage(callback: CallbackQuery) -> None:
    if not _can_add_group(callback.from_user.id):
        return await callback.answer()
    page = int(callback.data.split(":")[2])
    await callback.answer()
    await _safe_edit_text(
        callback.message,
        "➕ Qo'shish uchun guruhni tanlang:",
        add_group_keyboard(page),
    )


def _can_add_group(user_id: int) -> bool:
    # Shofyorlar endi alohida (tasdiqlash talab qiladigan) oqimdan foydalanadi — "pick:*".
    return storage.is_admin(user_id)


@router.callback_query(F.data.startswith("group:enable:"))
async def cb_group_enable(callback: CallbackQuery) -> None:
    if not _can_add_group(callback.from_user.id):
        return await callback.answer()
    parts = callback.data.split(":")
    chat_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    title = storage.get_known_groups().get(chat_id, f"chat {chat_id}")
    storage.enable_group(chat_id, title, added_by=callback.from_user.id)
    await callback.answer(f"{title} qo'shildi ✅")
    await _safe_edit_markup(callback.message, add_group_keyboard(page))


@router.callback_query(F.data == "driver:list")
async def cb_driver_list(callback: CallbackQuery) -> None:
    if not storage.is_admin(callback.from_user.id):
        return await callback.answer()
    driver_ids = storage.get_driver_ids()
    text = "\n".join(f"• <code>{chat_id}</code>" for chat_id in driver_ids) or "Ro'yxat bo'sh."
    await callback.answer()
    await callback.message.answer(f"Shofyorlar:\n{text}")


@router.callback_query(F.data == "driver:add")
async def cb_driver_add(callback: CallbackQuery, state: FSMContext) -> None:
    if not storage.is_admin(callback.from_user.id):
        return await callback.answer()
    await state.set_state(AdminInput.driver_add)
    await callback.answer()
    await callback.message.answer("Yangi shofyorning chat ID'sini yuboring:")


@router.callback_query(F.data == "driver:remove")
async def cb_driver_remove(callback: CallbackQuery, state: FSMContext) -> None:
    if not storage.is_admin(callback.from_user.id):
        return await callback.answer()
    await state.set_state(AdminInput.driver_remove)
    await callback.answer()
    await callback.message.answer("O'chiriladigan shofyorning chat ID'sini yuboring:")


@router.callback_query(F.data == "admin:list")
async def cb_admin_list(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    admin_ids = storage.get_admin_ids()
    await callback.answer()

    lines = []
    for chat_id in admin_ids:
        try:
            chat = await callback.bot.get_chat(chat_id)
            name = chat.full_name or (f"@{chat.username}" if chat.username else None) or "Noma'lum"
        except Exception:
            name = "Noma'lum"
        lines.append(f"• {name} — <code>{chat_id}</code>")
    text = "\n".join(lines) or "Ro'yxat bo'sh."
    await callback.message.answer(f"Adminlar:\n{text}")


@router.callback_query(F.data == "admin:add")
async def cb_admin_add(callback: CallbackQuery, state: FSMContext) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer("Faqat asosiy adminlar uchun", show_alert=True)
    await state.set_state(AdminInput.admin_add)
    await callback.answer()
    await callback.message.answer("Yangi adminning chat ID'sini yuboring:")


@router.callback_query(F.data == "admin:remove")
async def cb_admin_remove(callback: CallbackQuery, state: FSMContext) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer("Faqat asosiy adminlar uchun", show_alert=True)
    await state.set_state(AdminInput.admin_remove)
    await callback.answer()
    await callback.message.answer("O'chiriladigan adminning chat ID'sini yuboring:")


@router.callback_query(F.data == "admin:menu")
async def cb_admin_menu(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    await callback.answer()
    await _safe_edit_text(callback.message, "👤 Adminlar boshqaruvi:", admins_inline_keyboard())


@router.callback_query(F.data == "accounts:status")
async def cb_accounts_status(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    await callback.answer()

    linked = storage.get_linked_accounts()
    active_ids = set(telethon_accounts.get_active_owner_ids())

    if not linked:
        text = "🔌 Hozircha hech kim akkaunt ulamagan."
    else:
        lines = ["🔌 Ulangan akkauntlar:\n"]
        for owner_id, info in linked.items():
            status = "🟢 Faol" if owner_id in active_ids else "🔴 Ulanmagan"
            phone = info.get("phone", "?")
            lines.append(f"{status} — <code>{owner_id}</code> ({phone})")
        text = "\n".join(lines)

    rows = [[InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin:menu")]]
    await _safe_edit_text(callback.message, text, InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data == "dispatch:menu")
async def cb_dispatch_menu(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    await callback.answer()
    await _safe_edit_text(callback.message, dispatch_menu_text(), dispatch_menu_keyboard())


@router.callback_query(F.data.startswith("dispatch:pick:"))
async def cb_dispatch_pick(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    page = int(callback.data.split(":")[2])
    await callback.answer()
    await _safe_edit_text(
        callback.message,
        "📢 Buyurtmalar yuboriladigan guruhni tanlang:",
        dispatch_pick_keyboard(page),
    )


@router.callback_query(F.data.startswith("dispatch:set:"))
async def cb_dispatch_set(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    chat_id = int(callback.data.split(":")[2])
    storage.set_dispatch_group_id(chat_id)
    await callback.answer("✅ Buyurtmalar guruhi sozlandi")
    await _safe_edit_text(callback.message, dispatch_menu_text(), dispatch_menu_keyboard())


@router.callback_query(F.data == "dispatch:clear")
async def cb_dispatch_clear(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    storage.set_dispatch_group_id(None)
    await callback.answer("O'chirildi")
    await _safe_edit_text(callback.message, dispatch_menu_text(), dispatch_menu_keyboard())


@router.callback_query(F.data.startswith("dispatch:mode:"))
async def cb_dispatch_mode(callback: CallbackQuery) -> None:
    if not storage.is_root(callback.from_user.id):
        return await callback.answer("Faqat root admin uchun", show_alert=True)
    mode = callback.data.split(":")[2]
    storage.set_delivery_mode(mode)
    await callback.answer(f"✅ Rejim: {_DELIVERY_MODE_LABELS.get(mode, mode)}")
    await _safe_edit_text(callback.message, dispatch_menu_text(), dispatch_menu_keyboard())


@router.callback_query(F.data == "verify:menu")
async def cb_verify_menu(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    await callback.answer()
    await _safe_edit_text(callback.message, verify_menu_text(), verify_menu_keyboard())


@router.callback_query(F.data.startswith("verify:pick:"))
async def cb_verify_pick(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    page = int(callback.data.split(":")[2])
    await callback.answer()
    await _safe_edit_text(
        callback.message, "🚪 Tekshiruv guruhini tanlang:", verify_pick_keyboard(page)
    )


@router.callback_query(F.data.startswith("verify:set:"))
async def cb_verify_set(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    chat_id = int(callback.data.split(":")[2])
    storage.set_verification_group_id(chat_id)
    await callback.answer("✅ Tekshiruv guruhi sozlandi")
    await _safe_edit_text(callback.message, verify_menu_text(), verify_menu_keyboard())


@router.callback_query(F.data == "verify:clear")
async def cb_verify_clear(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    storage.set_verification_group_id(None)
    await callback.answer("O'chirildi")
    await _safe_edit_text(callback.message, verify_menu_text(), verify_menu_keyboard())


@router.callback_query(F.data.startswith("verify:confirm:"))
async def cb_verify_confirm(callback: CallbackQuery) -> None:
    if not storage.is_admin(callback.from_user.id):
        return await callback.answer()
    target_id = int(callback.data.split(":")[2])
    storage.add_driver_id(target_id)
    await callback.answer("✅ Tasdiqlandi")
    await _safe_edit_text(
        callback.message, callback.message.html_text + "\n\n✅ <b>Tasdiqlandi</b>"
    )
    try:
        await callback.bot.send_message(
            target_id,
            "✅ Siz tasdiqlandingiz! Guruhlaringizni qo'shish uchun /start deb yozing.",
        )
    except Exception:
        logger.exception("Foydalanuvchi (%s)ga tasdiq xabarini yuborib bo'lmadi", target_id)


# --- ID kutilayotgan matn kiritishlar (FSM) ---


@router.message(AdminInput.driver_add)
async def input_driver_add(message: Message, state: FSMContext) -> None:
    chat_id = _parse_chat_id(message.text)
    await state.clear()
    if chat_id is None:
        await message.reply("Noto'g'ri format. Faqat raqam yuboring.")
        return
    if storage.add_driver_id(chat_id):
        await message.reply(f"✅ {chat_id} shofyorlar ro'yxatiga qo'shildi.")
    else:
        await message.reply("Bu chat ID allaqachon ro'yxatda bor.")


@router.message(AdminInput.driver_remove)
async def input_driver_remove(message: Message, state: FSMContext) -> None:
    chat_id = _parse_chat_id(message.text)
    await state.clear()
    if chat_id is None:
        await message.reply("Noto'g'ri format. Faqat raqam yuboring.")
        return
    if storage.remove_driver_id(chat_id):
        await message.reply(f"✅ {chat_id} ro'yxatdan o'chirildi.")
    else:
        await message.reply("Bu chat ID ro'yxatda topilmadi.")


@router.message(AdminInput.admin_add)
async def input_admin_add(message: Message, state: FSMContext) -> None:
    chat_id = _parse_chat_id(message.text)
    await state.clear()
    if chat_id is None:
        await message.reply("Noto'g'ri format. Faqat raqam yuboring.")
        return
    if storage.add_admin_id(chat_id):
        storage.add_driver_id(chat_id)  # xabarlarni olishi uchun shofyor sifatida ham qo'shamiz
        await commands.sync_admin_commands(message.bot, chat_id)
        await message.reply(
            f"✅ {chat_id} qo'shildi — u faqat xabarlarni oladi (boshqaruv menyusi yo'q)."
        )
    else:
        await message.reply("Bu chat ID allaqachon admin.")


@router.message(AdminInput.admin_remove)
async def input_admin_remove(message: Message, state: FSMContext) -> None:
    chat_id = _parse_chat_id(message.text)
    await state.clear()
    if chat_id is None:
        await message.reply("Noto'g'ri format. Faqat raqam yuboring.")
        return
    if storage.remove_admin_id(chat_id):
        storage.remove_driver_id(chat_id)  # yo'lovchi xabarlarini olmasin
        try:
            await message.bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=chat_id))
        except Exception:
            pass
        await message.reply(f"✅ {chat_id} adminlikdan chiqarildi.")
    else:
        await message.reply(
            "Bu chat ID admin emas, yoki bu asosiy admin — uni o'chirib bo'lmaydi."
        )
