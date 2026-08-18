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
import storage

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


def _is_admin(message: Message) -> bool:
    return storage.is_founder(message.from_user.id)


def _parse_chat_id(text: str) -> int | None:
    text = (text or "").strip()
    if text.lstrip("-").isdigit():
        return int(text)
    return None


def main_reply_keyboard(is_founder: bool) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BTN_BOT), KeyboardButton(text=BTN_GROUPS)],
        [KeyboardButton(text=BTN_DRIVERS), KeyboardButton(text=BTN_STATUS)],
    ]
    if is_founder:
        rows.append([KeyboardButton(text=BTN_ADMINS)])
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
    mode = storage.get_group_mode()
    if mode == "all":
        return (
            "👥 <b>Guruhlar boshqaruvi</b>\n\n"
            "🌐 Joriy rejim: <b>BARCHA GURUHLAR</b>\n"
            "Bot a'zo bo'lgan <b>har qanday</b> guruhdagi xabarlarni tekshiradi."
        )
    return (
        "👥 <b>Guruhlar boshqaruvi</b>\n\n"
        "🎯 Joriy rejim: <b>FAQAT TANLANGANLAR</b>\n"
        "Bot faqat pastdagi \"Tinglanayotganlar\" ro'yxatidagi guruhlarni tekshiradi, "
        "qolganlarini e'tiborsiz qoldiradi."
    )


def groups_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🌐 Barchasini tinglash", callback_data="group:mode_all"),
                InlineKeyboardButton(text="🎯 Faqat tanlanganlarni", callback_data="group:mode_selected"),
            ],
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
        ]
    )


async def _status_text() -> str:
    bot_state = "▶️ YOQILGAN" if storage.is_processing_enabled() else "⏸ O'CHIRILGAN"
    ai_state = "▶️ YOQILGAN" if storage.is_ai_enabled() else "⏸ O'CHIRILGAN"
    mode_state = "🌐 HAMMASI" if storage.get_group_mode() == "all" else "🎯 TANLANGAN"
    return (
        f"🤖 Bot: <b>{bot_state}</b>\n"
        f"🧠 ChatGPT tahlili: <b>{ai_state}</b>\n"
        f"👥 Guruh rejimi: <b>{mode_state}</b>"
    )


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if not storage.is_founder(message.from_user.id):
        await message.reply(
            "🤖 Salom! Bu bot yo'nalish e'lonlarini avtomatik kuzatib boradi.\n"
            "O'z chat ID'ingizni bilish uchun: /mening_id"
        )
        return
    await message.answer(
        "Boshqaruv menyusi:",
        reply_markup=main_reply_keyboard(storage.is_founder(message.from_user.id)),
    )


@router.message(F.text == BTN_BOT, _is_admin)
async def show_bot_menu(message: Message) -> None:
    await message.answer("🤖 Bot boshqaruvi:", reply_markup=bot_inline_keyboard())


@router.message(F.text == BTN_GROUPS, _is_admin)
async def show_groups_menu(message: Message) -> None:
    await message.answer(groups_menu_text(), reply_markup=groups_inline_keyboard())


@router.message(F.text == BTN_DRIVERS, _is_admin)
async def show_drivers_menu(message: Message) -> None:
    await message.answer("🚕 Shofyorlar boshqaruvi:", reply_markup=drivers_inline_keyboard())


@router.message(F.text == BTN_ADMINS, _is_admin)
async def show_admins_menu(message: Message) -> None:
    if not storage.is_founder(message.from_user.id):
        return
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
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    storage.set_processing_enabled(True)
    await callback.answer("Bot yoqildi ✅")
    await _safe_edit_markup(callback.message, bot_inline_keyboard())


@router.callback_query(F.data == "bot:off")
async def cb_bot_off(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    storage.set_processing_enabled(False)
    await callback.answer("Bot o'chirildi ⏸")
    await _safe_edit_markup(callback.message, bot_inline_keyboard())


@router.callback_query(F.data == "ai:on")
async def cb_ai_on(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    storage.set_ai_enabled(True)
    await callback.answer("AI tahlili yoqildi ✅")
    await _safe_edit_markup(callback.message, bot_inline_keyboard())


@router.callback_query(F.data == "ai:off")
async def cb_ai_off(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    storage.set_ai_enabled(False)
    await callback.answer("AI tahlili o'chirildi ⏸")
    await _safe_edit_markup(callback.message, bot_inline_keyboard())


@router.callback_query(F.data == "group:menu")
async def cb_group_menu(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    await callback.answer()
    await _safe_edit_text(callback.message, groups_menu_text(), groups_inline_keyboard())


@router.callback_query(F.data == "group:list")
async def cb_group_list(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    await callback.answer()
    await _safe_edit_text(
        callback.message,
        "📋 Tinglanayotgan guruhlar (to'xtatish uchun bosing):",
        monitored_groups_keyboard(),
    )


@router.callback_query(F.data.startswith("group:view:"))
async def cb_group_view(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
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
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    chat_id = int(callback.data.split(":")[2])
    storage.disable_group(chat_id)
    await callback.answer("Tinglash to'xtatildi ✅")
    await _safe_edit_text(
        callback.message,
        "📋 Tinglanayotgan guruhlar (to'xtatish uchun bosing):",
        monitored_groups_keyboard(),
    )


@router.callback_query(F.data == "group:mode_all")
async def cb_group_mode_all(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    storage.set_group_mode("all")
    await callback.answer("Endi barcha guruhlar tinglanadi ✅")
    await _safe_edit_text(callback.message, groups_menu_text(), groups_inline_keyboard())


@router.callback_query(F.data == "group:mode_selected")
async def cb_group_mode_selected(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    storage.set_group_mode("selected")
    await callback.answer("Endi faqat tanlangan guruhlar tinglanadi ✅")
    await _safe_edit_text(callback.message, groups_menu_text(), groups_inline_keyboard())


@router.callback_query(F.data.startswith("group:addpage:"))
async def cb_group_addpage(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    page = int(callback.data.split(":")[2])
    await callback.answer()
    await _safe_edit_text(
        callback.message,
        "➕ Qo'shish uchun guruhni tanlang:",
        add_group_keyboard(page),
    )


@router.callback_query(F.data.startswith("group:enable:"))
async def cb_group_enable(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    parts = callback.data.split(":")
    chat_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 0
    title = storage.get_known_groups().get(chat_id, f"chat {chat_id}")
    storage.enable_group(chat_id, title)
    await callback.answer(f"{title} qo'shildi ✅")
    await _safe_edit_markup(callback.message, add_group_keyboard(page))


@router.callback_query(F.data == "driver:list")
async def cb_driver_list(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    driver_ids = storage.get_driver_ids()
    text = "\n".join(f"• <code>{chat_id}</code>" for chat_id in driver_ids) or "Ro'yxat bo'sh."
    await callback.answer()
    await callback.message.answer(f"Shofyorlar:\n{text}")


@router.callback_query(F.data == "driver:add")
async def cb_driver_add(callback: CallbackQuery, state: FSMContext) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    await state.set_state(AdminInput.driver_add)
    await callback.answer()
    await callback.message.answer("Yangi shofyorning chat ID'sini yuboring:")


@router.callback_query(F.data == "driver:remove")
async def cb_driver_remove(callback: CallbackQuery, state: FSMContext) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    await state.set_state(AdminInput.driver_remove)
    await callback.answer()
    await callback.message.answer("O'chiriladigan shofyorning chat ID'sini yuboring:")


@router.callback_query(F.data == "admin:list")
async def cb_admin_list(callback: CallbackQuery) -> None:
    if not storage.is_founder(callback.from_user.id):
        return await callback.answer()
    admin_ids = storage.get_admin_ids()
    text = "\n".join(f"• <code>{chat_id}</code>" for chat_id in admin_ids)
    await callback.answer()
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
        try:
            await message.bot.delete_my_commands(scope=BotCommandScopeChat(chat_id=chat_id))
        except Exception:
            pass
        await message.reply(f"✅ {chat_id} adminlikdan chiqarildi.")
    else:
        await message.reply(
            "Bu chat ID admin emas, yoki bu asosiy admin — uni o'chirib bo'lmaydi."
        )
