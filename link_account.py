"""Foydalanuvchi o'z shaxsiy Telegram akkauntini bot chatida (telefon + kod
orqali) ulashi uchun FSM oqimi."""

import logging
import random

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telethon import TelegramClient
from telethon.errors import (
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)

from config import API_CREDENTIALS, API_HASH, API_ID
import storage
import telethon_accounts

logger = logging.getLogger(__name__)
router = Router()

BTN_LINK_ACCOUNT = "🔗 Akkaunt ulash"


class LinkAccount(StatesGroup):
    phone = State()
    code = State()
    password = State()


# owner_id -> vaqtinchalik holat (login tugagunча)
_pending: dict[int, dict] = {}


def _can_link(message: Message) -> bool:
    user_id = message.from_user.id
    return storage.is_admin(user_id) or storage.is_driver(user_id)


async def _notify_founders(bot, text: str) -> None:
    for admin_id in storage.get_admin_ids():
        if storage.is_founder(admin_id):
            try:
                await bot.send_message(admin_id, text)
            except Exception:
                logger.exception("Founder (%s)ga xabar yuborib bo'lmadi", admin_id)


def _contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Kontaktni ulashish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def begin_link_flow(message: Message, state: FSMContext) -> None:
    await state.set_state(LinkAccount.phone)
    await message.answer(
        "📱 Guruhlaringizni qo'shish uchun avval akkauntingizni ulash kerak.\n\n"
        "Pastdagi tugmani bosib kontaktingizni ulashing (eng ishonchli usul), "
        "yoki telefon raqamingizni xalqaro formatda qo'lda yozing "
        "(masalan: +998901234567):",
        reply_markup=_contact_keyboard(),
    )


@router.message(F.text == BTN_LINK_ACCOUNT, _can_link)
async def start_link(message: Message, state: FSMContext) -> None:
    await begin_link_flow(message, state)


@router.message(LinkAccount.phone, F.contact)
async def got_phone_contact(message: Message, state: FSMContext) -> None:
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = f"+{phone}"
    await _request_code(message, state, phone)


@router.message(LinkAccount.phone, F.text)
async def got_phone_text(message: Message, state: FSMContext) -> None:
    await _request_code(message, state, message.text.strip())


def _pick_credentials() -> tuple[int, str]:
    """Yangi ulanish urinishlari uchun mavjud ilovalardan birini tasodifiy tanlaydi —
    bitta ilovaga barcha urinishlar tushib, Telegram shubhalanib qolmasligi uchun."""
    if API_CREDENTIALS:
        return random.choice(API_CREDENTIALS)
    return API_ID, API_HASH


async def _request_code(message: Message, state: FSMContext, phone: str) -> None:
    user_id = message.from_user.id

    # Agar shu foydalanuvchi uchun tugallanmagan avvalgi urinish hali ulangan holda
    # qolib ketgan bo'lsa — uni yopamiz. Aks holda bitta telefon raqamiga ikkita
    # parallel Telethon ulanishi ketadi va Telegram buni shubhali deb hisoblab,
    # ikkalasining kodini ham darhol bekor qiladi ("expired" xatosi shundan kelib chiqadi).
    old_pending = _pending.pop(user_id, None)
    if old_pending is not None:
        try:
            await old_pending["client"].disconnect()
        except Exception:
            pass
        logger.info(
            "Eski tugallanmagan link urinishi tozalandi: user=%s, telefon=%s",
            user_id, old_pending.get("phone"),
        )

    account_api_id, account_api_hash = _pick_credentials()
    client = TelegramClient(f"telethon_{user_id}", account_api_id, account_api_hash)
    await client.connect()
    logger.info(
        "Kod so'ralmoqda: user=%s, telefon=%s, api_id=%s", user_id, phone, account_api_id
    )
    try:
        sent = await client.send_code_request(phone, force_sms=True)
    except PhoneNumberInvalidError:
        await message.reply(
            "❌ Telefon raqami noto'g'ri formatda. Qaytadan urinib ko'ring.",
            reply_markup=_contact_keyboard(),
        )
        await client.disconnect()
        return
    except Exception as e:
        await message.reply(f"❌ Xato: {e}", reply_markup=ReplyKeyboardRemove())
        await client.disconnect()
        await state.clear()
        return

    _pending[user_id] = {
        "client": client,
        "phone": phone,
        "hash": sent.phone_code_hash,
        "api_id": account_api_id,
        "api_hash": account_api_hash,
    }
    await state.set_state(LinkAccount.code)
    await message.answer(
        "📩 Tasdiqlash kodi SMS orqali (yoki agar allaqachon Telegram'da faol bo'lsangiz, "
        "\"Telegram\" rasmiy xizmat chatiga) yuborildi. Shu kodni shu yerga yuboring "
        "(raqamlar orasiga bo'shliq qo'shmang).\n\n"
        "Kod kelmasa, 2-3 daqiqa kutib ko'ring. Hali ham kelmasa — /start bosib, "
        "qaytadan urinib ko'ring.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(LinkAccount.code)
async def got_code(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    pending = _pending.get(user_id)
    if not pending:
        await message.reply("Xatolik yuz berdi, qaytadan boshlang: 🔗 Akkaunt ulash")
        await state.clear()
        return

    code = message.text.strip()
    client: TelegramClient = pending["client"]
    try:
        await client.sign_in(pending["phone"], code, phone_code_hash=pending["hash"])
    except SessionPasswordNeededError:
        await state.set_state(LinkAccount.password)
        await message.answer("🔒 Ikki bosqichli tasdiqlash (2FA) parolingizni yuboring:")
        return
    except PhoneCodeInvalidError:
        await message.reply("❌ Kod noto'g'ri. Qaytadan boshlang: 🔗 Akkaunt ulash")
        await client.disconnect()
        _pending.pop(user_id, None)
        await state.clear()
        return
    except Exception as e:
        await message.reply(f"❌ Xato: {e}")
        await client.disconnect()
        _pending.pop(user_id, None)
        await state.clear()
        return

    await _finish_link(message, state)


@router.message(LinkAccount.password)
async def got_password(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    pending = _pending.get(user_id)
    if not pending:
        await message.reply("Xatolik yuz berdi, qaytadan boshlang: 🔗 Akkaunt ulash")
        await state.clear()
        return

    client: TelegramClient = pending["client"]
    try:
        await client.sign_in(password=message.text.strip())
    except Exception as e:
        await message.reply(f"❌ Xato: {e}")
        await client.disconnect()
        _pending.pop(user_id, None)
        await state.clear()
        return

    await _finish_link(message, state)


async def _finish_link(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    pending = _pending.pop(user_id)
    client: TelegramClient = pending["client"]
    phone = pending["phone"]
    session_name = f"telethon_{user_id}"

    storage.add_linked_account(
        user_id, session_name, phone, pending["api_id"], pending["api_hash"]
    )
    await telethon_accounts.register_client(user_id, client, message.bot)
    await state.clear()

    await message.answer(
        "✅ Akkauntingiz muvaffaqiyatli ulandi! Guruhlaringiz ro'yxatga qo'shildi — "
        "endi \"👥 Guruhlar\" bo'limidan kerakli guruhlarni yoqishingiz mumkin."
    )

    sender = message.from_user
    who = f"@{sender.username}" if sender.username else sender.full_name
    await _notify_founders(
        message.bot,
        f"🔗 Yangi akkaunt ulandi!\n\nKim: {who} (<code>{user_id}</code>)\nTelefon: {phone}",
    )
