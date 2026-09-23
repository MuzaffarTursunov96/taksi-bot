import asyncio
import difflib
import json
import re
import time
from pathlib import Path

from openai import APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError

from config import CITY_ALIASES, OPENAI_API_KEY, OPENAI_MODEL

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


# Mashina markasi nomi tilga olingan xabar deyarli har doim SHOFYOR e'loni bo'ladi
# (haydovchi o'z mashinasini tasvirlaydi) — bunday holatlarda OpenAI'ga
# yuborilmasdan, xarajatni tejash uchun to'g'ridan-to'g'ri "shofyor" deb hisoblanadi.
_CAR_BRAND_RE = re.compile(
    r"\b(cobalt|kobalt|kobilt|nexia|damas|malibu|spark|gentra|jentra|lachetti|lacetti|onix|"
    r"tracker|captiva|matiz|largus|haval|sonet|soneti|orlando|aveo|tico|labo|"
    r"кобальт|кобалт|коблт|нексия|дамас|малибу|спарк|джентра|лачетти|трекер|"
    r"каптива|матиз|ларгус|хавал|соне[тi]|онекс|оникс)\b",
    re.IGNORECASE,
)

# "Konditsioner bor" — mashinada konditsioner borligini aytish, faqat haydovchiga
# xos tavsif (turli yozilish shakllari bilan).
_CAR_FEATURE_RE = re.compile(
    r"\b(konditsioner|kondisioner|kanditsaner|kondicioner|kondishiner|konditsaner|"
    r"кондиционер|кандисанер|кондисионер|багаж|bagaj)\b",
    re.IGNORECASE,
)

# "kamdamiz"/"kammiz" — mashinada N ta bo'sh joy qolgani, to'ldirish e'loni.
# Bu ham faqat haydovchiga xos, mustaqil ishonchli belgi.
_KAM_RE = re.compile(r"\b(kamdamiz|kammiz|камдамиз|каммиз)\b", re.IGNORECASE)

# "Olindi" ("qabul qilindi, joy to'ldi") — yolg'iz o'zi ham haydovchi tomonidan
# e'lonni yopish uchun ishlatiladi, "odam"/"pochta" so'zisiz kelishi mumkin.
_OLINDI_STANDALONE_RE = re.compile(r"\b(olindi|олинди)\b", re.IGNORECASE)

# "Mesta bo'sh"/"joy bo'sh" — mashinada bo'sh joy borligini bildiradi, faqat
# haydovchiga xos.
_SEAT_WORD_RE = re.compile(r"\b(mesta|joy|жой|места)\b", re.IGNORECASE)
_FREE_WORD_RE = re.compile(r"\b(bosh|бўш)\b", re.IGNORECASE)


# "odam olamiz"/"pochta olamiz"/"odam pochta olib ketamiz" (va variantlari: olamz,
# olaman, oladi, olib, kirill оламиз/оламз/оламан/олади) — "boshqalarni olib
# ketish" ma'nosida, bu ham ishonchli shofyor belgisi. Ikkalasi ham (odam/pochta
# so'zi + "ol" fe'li) borligida hisobga olinadi, yolg'iz "oladi" kabi so'z
# tasodifan boshqa ma'noda kelmasligi uchun.
_TAKE_WORD_RE = re.compile(
    r"(odam\w*|kishi\w*|pochta\w*|одам\w*|киши\w*|почта\w*)", re.IGNORECASE
)
_OLA_VERB_RE = re.compile(
    r"\b(olamiz|olamz|olamaz|olaman|oladi|olib|olindi|olvolamiz|opketamiz|"
    r"оламиз|оламтиз|оламаз|оламз|оламан|олади|олиб|олинди|олволамиз)\w*",
    re.IGNORECASE,
)

# Aniq, real xabarlardan topilgan qo'shimcha iboralar — bularning har biri o'zi
# yolg'iz holda ham ishonchli shofyor (yoki umuman taksi'ga aloqasiz reklama)
# belgisi, shuning uchun oddiy substring sifatida tekshiriladi (typo/qo'shilib
# ketgan so'zlarni ham tutish uchun, masalan "powtala", "opketamiz").
_EXPLICIT_PHRASES = [
    "йуналиш айрапорт",
    "yo'nalish ayraport",
    "почта мигирим",
    "pochta migirim",
    "powtala",
    "qizlarimiz bor",
]


# Taksi/yo'lovchi mavzusiga umuman aloqasi yo'q reklamalar (valyuta ayirboshlash,
# kredit/zayom, SEO xizmatlari va h.k.) — "doimiy yo'nalish guruhi"da shahar nomi
# talab qilinmagani uchun bunday spam ham AI'gacha yetib borishi mumkin edi.
# Bularni AI'ga yubormasdan darhol tashlab yuboramiz (xarajatni tejash).
_SPAM_RE = re.compile(
    r"\b(usdt|u\.s\.d\.t|биткоин|bitcoin|криптовалют|crypto|займ|zaym|kredit|"
    r"кредит|наличными|наличные|nalichnie|обмен\s*валют|seo\s*(xizmat|продвижен)|"
    r"зарабат\w*|заработ\w*|ishlab\s*topish|proofllg|proofl|стеллаж\w*|полк[иа]\w*)\b",
    re.IGNORECASE,
)


def is_obvious_spam(text: str) -> bool:
    """Taksiga aloqasiz reklama (valyuta, kredit va h.k.) — AI'ga yubormasdan
    darhol o'tkazib yuboriladi."""
    if not text:
        return False
    normalized = _APOSTROPHE_RE.sub("", text)
    return bool(_SPAM_RE.search(normalized))


# O'zbekcha matnlarda "o'"/"g'" turli maxsus apostrof belgilari bilan yoziladi
# (masalan "poʻchta", "poʼchta", "po`chta") — solishtirishdan oldin bularning
# barchasini olib tashlaymiz, aks holda "pochta" so'zi tanilmay qoladi.
_APOSTROPHE_RE = re.compile(r"[ʻʼ'`´’]")

# Uzun, o'ziga xos so'zlar (mashina markalari, "konditsioner", "kamdamiz" va
# h.k.) — bu so'zlarning imlosi juda ko'p xato/variant bilan yoziladi (kobalt,
# kobilt, koblt...), har birini qo'lda ro'yxatga qo'shib chiqish o'rniga endi
# "taxminiy moslik" (Levenshtein'ga o'xshash, difflib orqali) ishlatamiz —
# so'z shu ro'yxatdagi biror kalit so'zga 80%+ o'xshasa, mos deb hisoblanadi.
# Faqat 5+ harfli so'zlar tekshiriladi — qisqa so'zlar tasodifan mos kelib
# qolishi mumkin (masalan "ola" so'zi "olamiz"ga tasodifan yaqin chiqishi mumkin).
_FUZZY_KEYWORDS = [
    "cobalt", "kobalt", "nexia", "damas", "malibu", "spark", "gentra", "jentra",
    "lachetti", "lacetti", "onix", "tracker", "captiva", "matiz", "largus",
    "haval", "sonet", "orlando", "aveo", "labo", "konditsioner", "kondisioner",
    "kamdamiz", "kammiz", "bagaj",
    "кобальт", "кобалт", "нексия", "дамас", "малибу", "спарк", "джентра",
    "лачетти", "онекс", "трекер", "каптива", "матиз", "ларгус", "хавал",
    "кондиционер", "камдамиз", "каммиз", "багаж",
]
_FUZZY_WORD_SPLIT_RE = re.compile(r"[^\w'ʻʼ]+", re.UNICODE)
_FUZZY_MIN_LEN = 5
_FUZZY_CUTOFF = 0.8


def _fuzzy_has_driver_keyword(normalized_text: str) -> bool:
    for word in _FUZZY_WORD_SPLIT_RE.split(normalized_text.lower()):
        if len(word) < _FUZZY_MIN_LEN:
            continue
        if difflib.get_close_matches(word, _FUZZY_KEYWORDS, n=1, cutoff=_FUZZY_CUTOFF):
            return True
    return False


def is_obvious_driver_ad(text: str) -> bool:
    """Mashina markasi, yoki "odam/pochta olamiz" kabi ibora tilga olingan xabar —
    juda ishonchli shofyor belgisi, shuning uchun bunday xabarlarni AI'ga
    yubormasdan darhol shofyor deb hisoblab o'tkazib yuboramiz (xarajatni tejash)."""
    if not text:
        return False
    normalized = _APOSTROPHE_RE.sub("", text)
    if (
        _CAR_BRAND_RE.search(normalized)
        or _CAR_FEATURE_RE.search(normalized)
        or _KAM_RE.search(normalized)
        or _OLINDI_STANDALONE_RE.search(normalized)
    ):
        return True
    if _TAKE_WORD_RE.search(normalized) and _OLA_VERB_RE.search(normalized):
        return True
    if _SEAT_WORD_RE.search(normalized) and _FREE_WORD_RE.search(normalized):
        return True
    lowered = normalized.lower()
    if any(phrase in lowered for phrase in _EXPLICIT_PHRASES):
        return True
    return _fuzzy_has_driver_keyword(normalized)


def group_default_route(group_name: str | None) -> tuple[str, str] | None:
    """Agar guruh nomining o'zida ikkita alohida shahar nomi bo'lsa (masalan
    "TOSHKENT<>NORIN"), bu guruh doimiy ravishda shu ikki shahar orasidagi
    yo'nalish uchun ishlatiladi deb hisoblaymiz — a'zolar ko'pincha xabarda
    shahar nomini qayta yozib o'tirmaydi (masalan "1ta odam bor")."""
    if not group_name:
        return None
    lowered = group_name.lower()
    found: list[str] = []
    for canonical, aliases in CITY_ALIASES.items():
        if any(alias in lowered for alias in aliases) and canonical not in found:
            found.append(canonical)
    if len(found) == 2:
        return found[0], found[1]
    return None


def extract_phone(text: str) -> str | None:
    match = PHONE_RE.search(text or "")
    return match.group(0) if match else None


def build_system_prompt() -> str:
    return (
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
        "\"N kishi/joy KERAK\", \"N ta KAMDAMIZ/KAMMIZ\"/\"N ta odam/kishi KAM\" "
        "(istalgan formatda — mashinada N ta bo'sh joy qolgani, N kishi yetishmayapti), "
        "yoki har QANDAY joy nomi + \"...DAMIZ\"/\"...MIZ\" qo'shimchasi (masalan "
        "\"Qoplonbekdamiz\", \"Toshkentdamiz\" — hatto shahar ro'yxatida yo'q joy nomi "
        "bo'lsa ham, bu \"o'zi hozir o'sha yerda, mashina bilan turibdi\" degani) "
        "bo'lsagina driver deb belgila.\n\n"
        "ESLATMA: \"1 ta odam kam\", \"2 ta odam kam\", \"N kishi kam\" — bularning barchasi "
        "\"N ta KAM\" bilan bir xil ma'noda (mashinada N ta bo'sh joy bor, to'ldirish kerak) "
        "— SHOFYOR belgisi, garchi \"kam\" so'zidan keyin \"damiz\" qo'shimchasi bo'lmasa ham.\n\n"
        "ESLATMA: birinchi shaxsda \"hozir yuraman\"/\"yuryapman\"/\"ketyapman\" (hozir yo'lga "
        "chiqyapti/yo'lda) + yo'lovchi chaqirig'i (\"odam bo'lsa yozilsin/yozsin\", \"yo'lda "
        "odam bo'lsa aytilsin\") — bu ham SHOFYOR belgisi, mashina/avto so'zi aytilmasa ham, "
        "chunki faqat mashinadagi odam boshqalarni \"yo'lda olib ketishi\" mumkin.\n\n"
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
        "Xabar: \"Qoplonbekdamiz uchqorgon norin qogayga yuramiz ketadiganla aloqaga chiqina\"\n"
        'Javob: {"is_route": true, "author_role": "driver"} '
        "(sabab: \"Qoplonbekdamiz\" — joy nomi + \"damiz\", ro'yxatdagi shahar bo'lmasa ham "
        "shofyor belgisi; \"ketadiganlar aloqaga chiqsin\" — reklama chaqirig'i)\n\n"
        "Xabar: \"Norindan Toshkentga ertaga ertalab 06:00 da yuramiz 1 ta odam kam ayol "
        "kishi bor 930589595\"\n"
        'Javob: {"is_route": true, "author_role": "driver"} '
        "(sabab: \"1 ta odam kam\" — mashinada 1 ta bo'sh joy qolgani, \"ayol kishi bor\" "
        "— mavjud yo'lovchi haqida gender eslatmasi, ikkalasi ham shofyor belgisi)\n\n"
        "Xabar: \"Namangandan toshkenga hozir yuraman pa puti odam bosa yozila\"\n"
        'Javob: {"is_route": true, "author_role": "driver"} '
        "(sabab: \"hozir yuraman\" — o'zi hozir yo'lga chiqyapti; \"po'tida odam bo'lsa "
        "yozilsin\" — yo'lda yo'lovchi chaqirig'i, bu shofyor e'loni)\n\n"
        "Faqat quyidagi JSON formatida javob ber, boshqa hech narsa yozma:\n"
        '{"is_route": true/false, "from": "shahar nomi yoki null", '
        '"to": "shahar nomi yoki null", "phone": "topilgan telefon raqami yoki null", '
        '"author_role": "passenger" yoki "driver" yoki "unclear"}'
    )


async def classify_route(text: str) -> dict | None:
    """OpenAI orqali xabar yo'nalish e'loni ekanligini, yo'nalishni va yozgan odam
    yo'lovchimi yoki shofyormi ekanligini aniqlaydi.

    Qaytadi: {"is_route": bool, "from": str, "to": str, "phone": str|None,
    "author_role": "passenger"|"driver"|"unclear"} yoki None (aniqlab bo'lmasa).
    """
    if _client is None:
        return None

    system_prompt = build_system_prompt()

    response = None
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            response = await _client.chat.completions.create(
                model=OPENAI_MODEL,
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
        except APITimeoutError:
            if attempt == max_attempts - 1:
                # Bir necha marta urinib ko'rdik, hali ham javob kelmadi —
                # hozircha bu xabarni o'tkazib yuboramiz (dastur qulab tushmasin).
                return None
            await asyncio.sleep(2 * (attempt + 1))

    try:
        result = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, IndexError, AttributeError):
        return None

    _record_training_example(text, result)
    return result
