import asyncio
import json
import re
import time
from pathlib import Path

from openai import AsyncOpenAI, APIStatusError, RateLimitError

from config import CITY_ALIASES, OPENAI_API_KEY

PHONE_RE = re.compile(r"(\+?998[\s\-]?\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}|\b\d{9}\b)")

_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Kelajakda o'z modelimizni o'qitish uchun: OpenAI har bir tasnifini shu faylga
# yozib boradi (matn + natija). Fayl vaqt o'tishi bilan o'quv ma'lumotiga aylanadi.
TRAINING_DATA_PATH = Path(__file__).parent / "training_data.jsonl"


def _record_training_example(text: str, result: dict) -> None:
    try:
        with open(TRAINING_DATA_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "text": text, "label": result}, ensure_ascii=False) + "\n")
    except Exception:
        pass  # o'quv ma'lumotini yozib bo'lmasa ham, botning asosiy ishiga xalaqit bermasin


class OpenAIQuotaExceeded(Exception):
    """OpenAI balansi haqiqatan ham tugaganda (insufficient_quota) ko'tariladi.

    Oddiy vaqtinchalik "tezlik chegarasi" (rate limit) bundan farqli — u avtomatik
    qayta uriniladi, balans tugashi bilan aralashtirilmaydi.
    """


def _is_quota_exhausted(error: RateLimitError | APIStatusError) -> bool:
    body = getattr(error, "body", None)
    error_info = body.get("error", {}) if isinstance(body, dict) else {}
    if not isinstance(error_info, dict):
        error_info = {}
    code = error_info.get("code")
    err_type = error_info.get("type")
    return code == "insufficient_quota" or err_type == "insufficient_quota" or (
        "insufficient_quota" in str(error)
    )


def quick_prefilter(text: str) -> bool:
    """Xabarda kamida 1 ta shahar nomi uchraydimi, tez tekshiradi (arzon, OpenAI'siz).

    Odamlar yo'nalishni ko'pincha bir necha alohida xabarga bo'lib yozishadi
    (masalan "toshkentdan ketmoqchi edim" va keyingi xabarda "noringa"),
    shuning uchun 1 ta shahar yetarli — aniq qarorni OpenAI beradi.
    """
    if not text:
        return False
    lowered = text.lower()
    return any(
        alias in lowered
        for aliases in CITY_ALIASES.values()
        for alias in aliases
    )


def extract_phone(text: str) -> str | None:
    match = PHONE_RE.search(text or "")
    return match.group(0) if match else None


async def classify_route(text: str) -> dict | None:
    """OpenAI orqali xabar yo'nalish e'loni ekanligini, yo'nalishni va yozgan odam
    yo'lovchimi yoki shofyormi ekanligini aniqlaydi.

    Qaytadi: {"is_route": bool, "from": str, "to": str, "phone": str|None,
    "author_role": "passenger"|"driver"|"unclear"} yoki None (aniqlab bo'lmasa).
    """
    if _client is None:
        return None

    system_prompt = (
        "Sen Telegram taksi/yo'lovchi guruhlaridagi xabarlarni tahlil qiluvchi yordamchisan.\n\n"
        "Xabar shaharlararo yo'nalish haqidami (is_route), qaysi shahardan qaysi shaharga "
        "(from/to), telefon raqami bormi (phone) va ENG MUHIMI — xabarni YO'LOVCHI yozganmi "
        "yoki SHOFYOR yozganmi (author_role) aniqlaysan.\n\n"
        f"Shaharlar: {', '.join(CITY_ALIASES.keys())}\n\n"
        "MUHIM QOIDA: bu guruhlarda 90% xabarlar SHOFYORLARNING REKLAMA E'LONLARI bo'ladi "
        "(o'zi mashinada, yo'lovchi/pochta qidiryapti). Agar odam (yoki bir nechta odam "
        "birga) o'zlari uchun joy/mashina qidirsa (\"kerak\", \"ketmoqchiman\", \"ketamiz\", "
        "\"2 kishimiz\") — bu passenger, hattoki ko'plikda yozilgan bo'lsa ham. Agar "
        "shubhalansang yoki xabar reklama/e'lon uslubida bo'lsa "
        "(raqam+kishi/joy KERAK, mashina/avto markasi haqida, \"olamiz\"/\"beramiz\" — "
        "BOSHQALARNI OLIB KETISH ma'nosida) — driver deb belgila, unclear emas.\n\n"
        "MUHIM: ko'plik fe'lining o'zi ({biz ketamiz}, {2 kishimiz}, {boramiz}) — bu "
        "SHOFYOR belgisi EMAS! Bir nechta do'st/qarindosh birga ketishi mumkin — bu ham "
        "yo'lovchi. Faqat mashina/avto markasi, \"olamiz\" (boshqalarni olib ketish), "
        "\"N kishi/joy KERAK\", \"N ta KAMDAMIZ/KAMMIZ\" (mashinada N ta bo'sh joy qolgani) "
        "yoki \"...ICHIDAMIZ\"/\"...DAMIZ\" (o'zi hozir o'sha shaharda, mashina bilan "
        "turibdi) bo'lsagina driver deb belgila.\n\n"
        "Misollar:\n"
        "Xabar: \"2 KISHI KERAK AYOLA BOR TEL.999976222\"\n"
        'Javob: {"is_route": true, "author_role": "driver"} '
        "(sabab: \"N KISHI KERAK\" — mashinadagi bo'sh joylarni to'ldirish e'loni)\n\n"
        "Xabar: \"Toshkentdan Chust Popga soat 16:00 da odam olamiz\"\n"
        'Javob: {"is_route": true, "author_role": "driver"} (sabab: \"olamiz\")\n\n'
        "Xabar: \"Towkentga yuramiz Uchqo'rg'on qogay norindan avto haval\"\n"
        'Javob: {"is_route": true, "author_role": "driver"} '
        "(sabab: avtomobil markasi \"avto haval\" tilga olingan)\n\n"
        "Xabar: \"Salom, menga Toshkentdan Noringa ketish kerak, joy bormi?\"\n"
        'Javob: {"is_route": true, "author_role": "passenger"} '
        "(sabab: birinchi shaxsda, o'zi uchun so'rayapti)\n\n"
        "Xabar: \"Toshkentga ketamiz 2 kishimiz\"\n"
        'Javob: {"is_route": true, "author_role": "passenger"} '
        "(sabab: bu shunchaki 2 kishilik yo'lovchi guruhi, mashina/reklama belgisi yo'q, "
        "\"kerak\"/\"olamiz\" so'zi yo'q — ko'plik shaklining o'zi driver belgisi emas)\n\n"
        "Xabar: \"Toshkent shahar ichidamiz Noringa ikkita kamdamiz, aloqa +998...\"\n"
        'Javob: {"is_route": true, "author_role": "driver"} '
        "(sabab: \"ichidamiz\" — o'zi hozir o'sha shaharda, mashina bilan; \"N ta kamdamiz\" "
        "— mashinada N ta bo'sh joy qolgani, yo'lovchi to'ldirish e'loni)\n\n"
        "Xabar: \"Toshkentdan Noringa 1 ta odam bor\"\n"
        'Javob: {"is_route": true, "author_role": "passenger"} '
        "(sabab: \"odam bor\" — biror kishi ketishga ehtiyoji borligini bildiryapti, "
        "\"olamiz\"/mashina/\"kerak\" so'zi yo'q, shuning uchun bu SHOFYOR emas — "
        "\"joy/odam bor\" so'zi yolg'iz holda, \"olamiz\"siz, driver belgisi emas)\n\n"
        "Faqat quyidagi JSON formatida javob ber, boshqa hech narsa yozma:\n"
        '{"is_route": true/false, "from": "shahar nomi yoki null", '
        '"to": "shahar nomi yoki null", "phone": "topilgan telefon raqami yoki null", '
        '"author_role": "passenger" yoki "driver" yoki "unclear"}'
    )

    response = None
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            response = await _client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f'Xabar: """{text}"""'},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            break
        except RateLimitError as e:
            if _is_quota_exhausted(e):
                raise OpenAIQuotaExceeded(str(e)) from e
            if attempt == max_attempts - 1:
                # Balans muammosi emas, shunchaki vaqtinchalik tezlik chegarasi —
                # bir necha marta urinib ko'rdik, hozircha bu xabarni o'tkazib yuboramiz.
                return None
            await asyncio.sleep(2 * (attempt + 1))
        except APIStatusError as e:
            if e.status_code == 429 and not _is_quota_exhausted(e):
                if attempt == max_attempts - 1:
                    return None
                await asyncio.sleep(2 * (attempt + 1))
                continue
            if _is_quota_exhausted(e):
                raise OpenAIQuotaExceeded(str(e)) from e
            raise

    try:
        result = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, IndexError, AttributeError):
        return None

    _record_training_example(text, result)
    return result
