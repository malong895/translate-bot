"""Translation engine + language direction detection.

Primary backend is MyMemory (free, no API key). If it fails and the optional
``deep-translator`` package is available, Google Translate is used as a fallback.
"""

import logging
import os
import re
import time

import requests

try:
    from langdetect import detect as _ld_detect
    from langdetect import DetectorFactory as _DetectorFactory
    _DetectorFactory.seed = 0
except Exception:  # pragma: no cover - langdetect is optional
    _ld_detect = None

try:
    from deep_translator import GoogleTranslator
except Exception:  # pragma: no cover - optional fallback
    GoogleTranslator = None

logger = logging.getLogger(__name__)

MYMEMORY_URL = "https://api.mymemory.translated.net/get"

# DeepL API key (Free keys end in ":fx"). Set via env or config.
DEEPL_KEY = os.environ.get("DEEPL_API_KEY") or None
DEEPL_FREE_URL = "https://api-free.deepl.com/v2/translate"
DEEPL_PRO_URL = "https://api.deepl.com/v2/translate"

_session = requests.Session()

# DeepL supports a fixed set of languages with special target codes.
_DEEPL_SOURCE = {
    "zh-CN": "ZH", "zh-TW": "ZH", "zh": "ZH",
    "en": "EN", "pt": "PT", "nb": "NB", "no": "NB",
}
_DEEPL_TARGET = {
    "zh-CN": "ZH-HANS", "zh-TW": "ZH-HANT", "zh": "ZH-HANS",
    "en": "EN-US", "pt": "PT-PT", "nb": "NB", "no": "NB",
}
_DEEPL_LANGS = {
    "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr", "hu", "id",
    "it", "ja", "ko", "lt", "lv", "nb", "no", "nl", "pl", "pt", "ro", "ru",
    "sk", "sl", "sv", "tr", "uk", "zh", "zh-CN", "zh-TW",
}


def _deepl_code(code, table):
    if code in table:
        return table[code]
    return code.upper() if code else code

MAX_CHUNK_BYTES = 450


# --------------------------------------------------------------------------- #
# Language catalogue (code -> display name). Codes are MyMemory compatible.
# Common languages first, then the long tail.
# --------------------------------------------------------------------------- #
LANGUAGES = [
    ("zh-CN", "Chinese Simplified"),
    ("zh-TW", "Chinese Traditional"),
    ("en", "English"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("de", "German"),
    ("ru", "Russian"),
    ("ar", "Arabic"),
    ("pt", "Portuguese"),
    ("it", "Italian"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("hi", "Hindi"),
    ("bn", "Bengali"),
    ("id", "Indonesian"),
    ("ms", "Malay"),
    ("vi", "Vietnamese"),
    ("th", "Thai"),
    ("tr", "Turkish"),
    ("fa", "Persian"),
    ("ur", "Urdu"),
    ("tl", "Filipino"),
    ("my", "Burmese"),
    ("km", "Khmer"),
    ("lo", "Lao"),
    ("ne", "Nepali"),
    ("si", "Sinhala"),
    ("ta", "Tamil"),
    ("te", "Telugu"),
    ("ml", "Malayalam"),
    ("mr", "Marathi"),
    ("gu", "Gujarati"),
    ("kn", "Kannada"),
    ("pa", "Punjabi"),
    ("sw", "Swahili"),
    ("am", "Amharic"),
    ("ha", "Hausa"),
    ("yo", "Yoruba"),
    ("ig", "Igbo"),
    ("zu", "Zulu"),
    ("af", "Afrikaans"),
    ("nl", "Dutch"),
    ("sv", "Swedish"),
    ("no", "Norwegian"),
    ("da", "Danish"),
    ("fi", "Finnish"),
    ("pl", "Polish"),
    ("cs", "Czech"),
    ("sk", "Slovak"),
    ("hu", "Hungarian"),
    ("ro", "Romanian"),
    ("bg", "Bulgarian"),
    ("el", "Greek"),
    ("uk", "Ukrainian"),
    ("sr", "Serbian"),
    ("hr", "Croatian"),
    ("sl", "Slovenian"),
    ("lt", "Lithuanian"),
    ("lv", "Latvian"),
    ("et", "Estonian"),
    ("he", "Hebrew"),
    ("az", "Azerbaijani"),
    ("kk", "Kazakh"),
    ("uz", "Uzbek"),
    ("ky", "Kyrgyz"),
    ("tg", "Tajik"),
    ("mn", "Mongolian"),
    ("hy", "Armenian"),
    ("ka", "Georgian"),
    ("sq", "Albanian"),
    ("mk", "Macedonian"),
    ("bs", "Bosnian"),
    ("is", "Icelandic"),
    ("ga", "Irish"),
    ("cy", "Welsh"),
    ("mt", "Maltese"),
    ("eo", "Esperanto"),
    ("la", "Latin"),
    ("jw", "Javanese"),
    ("su", "Sundanese"),
    ("ceb", "Cebuano"),
    ("hmn", "Hmong"),
    ("haw", "Hawaiian"),
    ("mi", "Maori"),
    ("sm", "Samoan"),
    ("gd", "Scottish Gaelic"),
    ("ny", "Chichewa"),
    ("co", "Corsican"),
    ("fy", "Frisian"),
    ("lb", "Luxembourgish"),
    ("rw", "Kinyarwanda"),
    ("sn", "Shona"),
    ("st", "Sesotho"),
    ("sd", "Sindhi"),
    ("ps", "Pashto"),
    ("ku", "Kurdish"),
    ("ug", "Uyghur"),
    ("yi", "Yiddish"),
    ("or", "Odia"),
]

LANG_NAME = dict(LANGUAGES)

# Representative country/region flag per language (shown on the picker buttons).
FLAGS = {
    "zh-CN": "🇨🇳", "zh-TW": "🇹🇼", "en": "🇬🇧", "es": "🇪🇸", "fr": "🇫🇷",
    "de": "🇩🇪", "ru": "🇷🇺", "ar": "🇸🇦", "pt": "🇵🇹", "it": "🇮🇹",
    "ja": "🇯🇵", "ko": "🇰🇷", "hi": "🇮🇳", "bn": "🇧🇩", "id": "🇮🇩",
    "ms": "🇲🇾", "vi": "🇻🇳", "th": "🇹🇭", "tr": "🇹🇷", "fa": "🇮🇷",
    "ur": "🇵🇰", "tl": "🇵🇭", "my": "🇲🇲", "km": "🇰🇭", "lo": "🇱🇦",
    "ne": "🇳🇵", "si": "🇱🇰", "ta": "🇮🇳", "te": "🇮🇳", "ml": "🇮🇳",
    "mr": "🇮🇳", "gu": "🇮🇳", "kn": "🇮🇳", "pa": "🇮🇳", "sw": "🇰🇪",
    "am": "🇪🇹", "ha": "🇳🇬", "yo": "🇳🇬", "ig": "🇳🇬", "zu": "🇿🇦",
    "af": "🇿🇦", "nl": "🇳🇱", "sv": "🇸🇪", "no": "🇳🇴", "da": "🇩🇰",
    "fi": "🇫🇮", "pl": "🇵🇱", "cs": "🇨🇿", "sk": "🇸🇰", "hu": "🇭🇺",
    "ro": "🇷🇴", "bg": "🇧🇬", "el": "🇬🇷", "uk": "🇺🇦", "sr": "🇷🇸",
    "hr": "🇭🇷", "sl": "🇸🇮", "lt": "🇱🇹", "lv": "🇱🇻", "et": "🇪🇪",
    "he": "🇮🇱", "az": "🇦🇿", "kk": "🇰🇿", "uz": "🇺🇿", "ky": "🇰🇬",
    "tg": "🇹🇯", "mn": "🇲🇳", "hy": "🇦🇲", "ka": "🇬🇪", "sq": "🇦🇱",
    "mk": "🇲🇰", "bs": "🇧🇦", "is": "🇮🇸", "ga": "🇮🇪", "cy": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
    "mt": "🇲🇹", "eo": "🏳️", "la": "🏛️", "jw": "🇮🇩", "su": "🇮🇩",
    "ceb": "🇵🇭", "hmn": "🌏", "haw": "🇺🇸", "mi": "🇳🇿", "sm": "🇼🇸",
    "gd": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "ny": "🇲🇼", "co": "🇫🇷", "fy": "🇳🇱", "lb": "🇱🇺",
    "rw": "🇷🇼", "sn": "🇿🇼", "st": "🇱🇸", "sd": "🇵🇰", "ps": "🇦🇫",
    "ku": "🇮🇶", "ug": "🇨🇳", "yi": "🇮🇱", "or": "🇮🇳",
}


def flag_of(code):
    return FLAGS.get(code, "🌐")


# --------------------------------------------------------------------------- #
# Script based direction detection
# --------------------------------------------------------------------------- #
LANG_SCRIPTS = {
    "zh-CN": {"han"},
    "zh-TW": {"han"},
    "ja": {"han", "kana"},
    "ko": {"hangul", "han"},
    "ru": {"cyrillic"},
    "uk": {"cyrillic"},
    "bg": {"cyrillic"},
    "sr": {"cyrillic", "latin"},
    "mk": {"cyrillic"},
    "be": {"cyrillic"},
    "kk": {"cyrillic"},
    "ky": {"cyrillic"},
    "tg": {"cyrillic"},
    "mn": {"cyrillic"},
    "ar": {"arabic"},
    "fa": {"arabic"},
    "ur": {"arabic"},
    "ps": {"arabic"},
    "sd": {"arabic"},
    "ug": {"arabic"},
    "he": {"hebrew"},
    "el": {"greek"},
    "hi": {"devanagari"},
    "mr": {"devanagari"},
    "ne": {"devanagari"},
    "bn": {"bengali"},
    "pa": {"gurmukhi"},
    "gu": {"gujarati"},
    "or": {"oriya"},
    "ta": {"tamil"},
    "te": {"telugu"},
    "kn": {"kannada"},
    "ml": {"malayalam"},
    "si": {"sinhala"},
    "th": {"thai"},
    "lo": {"lao"},
    "km": {"khmer"},
    "my": {"myanmar"},
    "ka": {"georgian"},
    "hy": {"armenian"},
    "am": {"ethiopic"},
}


def _char_script(ch):
    o = ord(ch)
    if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0xF900 <= o <= 0xFAFF:
        return "han"
    if 0x3040 <= o <= 0x30FF:
        return "kana"
    if 0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF:
        return "hangul"
    if 0x0400 <= o <= 0x052F:
        return "cyrillic"
    if 0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F or 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF:
        return "arabic"
    if 0x0590 <= o <= 0x05FF:
        return "hebrew"
    if 0x0370 <= o <= 0x03FF:
        return "greek"
    if 0x0900 <= o <= 0x097F:
        return "devanagari"
    if 0x0980 <= o <= 0x09FF:
        return "bengali"
    if 0x0A00 <= o <= 0x0A7F:
        return "gurmukhi"
    if 0x0A80 <= o <= 0x0AFF:
        return "gujarati"
    if 0x0B00 <= o <= 0x0B7F:
        return "oriya"
    if 0x0B80 <= o <= 0x0BFF:
        return "tamil"
    if 0x0C00 <= o <= 0x0C7F:
        return "telugu"
    if 0x0C80 <= o <= 0x0CFF:
        return "kannada"
    if 0x0D00 <= o <= 0x0D7F:
        return "malayalam"
    if 0x0D80 <= o <= 0x0DFF:
        return "sinhala"
    if 0x0E00 <= o <= 0x0E7F:
        return "thai"
    if 0x0E80 <= o <= 0x0EFF:
        return "lao"
    if 0x1780 <= o <= 0x17FF:
        return "khmer"
    if 0x1000 <= o <= 0x109F:
        return "myanmar"
    if 0x10A0 <= o <= 0x10FF:
        return "georgian"
    if 0x0530 <= o <= 0x058F:
        return "armenian"
    if 0x1200 <= o <= 0x137F:
        return "ethiopic"
    if 0x0041 <= o <= 0x005A or 0x0061 <= o <= 0x007A or 0x00C0 <= o <= 0x024F:
        return "latin"
    return None


def script_of(code):
    return LANG_SCRIPTS.get(code, {"latin"})


def _text_scripts(text):
    counts = {}
    for ch in text:
        s = _char_script(ch)
        if s:
            counts[s] = counts.get(s, 0) + 1
    return counts


def _lang_matches(code, detected):
    code = code.lower()
    detected = detected.lower()
    if code == detected:
        return True
    if code.startswith("zh") and detected.startswith("zh"):
        return True
    if code == "he" and detected in ("he", "iw"):
        return True
    return False


def _ld(text):
    if _ld_detect is None:
        return None
    try:
        return _ld_detect(text)
    except Exception:
        return None


def choose_source(text, a, b):
    """Return which of the two configured languages the text is written in.

    Uses Unicode script analysis first (reliable for Latin vs CJK/Cyrillic/etc.)
    and falls back to statistical detection for same-script pairs.
    """
    counts = _text_scripts(text)
    if not counts:
        return None

    ca, cb = script_of(a), script_of(b)
    if ca != cb:
        dom = max(counts, key=counts.get)
        in_a, in_b = dom in ca, dom in cb
        if in_a and not in_b:
            return a
        if in_b and not in_a:
            return b

    detected = _ld(text)
    if detected:
        if _lang_matches(b, detected) and not _lang_matches(a, detected):
            return b
        if _lang_matches(a, detected) and not _lang_matches(b, detected):
            return a

    return a


def _split_chunks(text, max_bytes=MAX_CHUNK_BYTES):
    if len(text.encode("utf-8")) <= max_bytes:
        return [text]
    parts = re.split(r"(?<=[.!?。！？\n])\s*", text)
    chunks, cur = [], ""
    for part in parts:
        if not part:
            continue
        cand = (cur + " " + part).strip() if cur else part
        if len(cand.encode("utf-8")) <= max_bytes:
            cur = cand
            continue
        if cur:
            chunks.append(cur)
        while len(part.encode("utf-8")) > max_bytes:
            cut = len(part)
            while cut > 0 and len(part[:cut].encode("utf-8")) > max_bytes:
                cut -= 1
            chunks.append(part[:cut])
            part = part[cut:]
        cur = part
    if cur:
        chunks.append(cur)
    return chunks


def _deepl_chunk(chunk, source, target):
    key = DEEPL_KEY
    if not key:
        raise RuntimeError("no DeepL key")
    if source not in _DEEPL_LANGS or target not in _DEEPL_LANGS:
        raise RuntimeError(f"DeepL does not support {source}->{target}")
    url = DEEPL_FREE_URL if key.endswith(":fx") else DEEPL_PRO_URL
    data = {
        "text": chunk,
        "target_lang": _deepl_code(target, _DEEPL_TARGET),
    }
    if source:
        data["source_lang"] = _deepl_code(source, _DEEPL_SOURCE)
    last_err = None
    for attempt in range(3):
        try:
            resp = _session.post(
                url,
                data=data,
                headers={"Authorization": f"DeepL-Auth-Key {key}"},
                timeout=25,
            )
            if resp.status_code == 456:
                raise RuntimeError("DeepL quota exceeded")
            resp.raise_for_status()
            js = resp.json()
            text = (js.get("translations") or [{}])[0].get("text")
            if text:
                return text
            raise RuntimeError("empty translation")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"DeepL failed: {last_err}")


def _translate_chunk(chunk, source, target, email=None):
    params = {"q": chunk, "langpair": f"{source}|{target}"}
    if email:
        params["de"] = email
    last_err = None
    for attempt in range(4):
        try:
            resp = _session.get(MYMEMORY_URL, params=params, timeout=25)
            resp.raise_for_status()
            data = resp.json()
            if data.get("responseStatus") != 200:
                raise RuntimeError(data.get("responseDetails") or f"status {data.get('responseStatus')}")
            text = (data.get("responseData") or {}).get("translatedText")
            if text:
                return text
            raise RuntimeError("empty translation")
        except Exception as exc:  # noqa: BLE001 - retry any failure
            last_err = exc
            time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"MyMemory failed: {last_err}")


def _google(text, source, target):
    if GoogleTranslator is None:
        raise RuntimeError("google fallback unavailable")
    src = "auto" if source in (None, "auto") else source
    return GoogleTranslator(source=src, target=target).translate(text)


def translate(text, source, target, email=None):
    """Translate ``text`` from ``source`` to ``target`` language code."""
    pieces = _split_chunks(text)

    if DEEPL_KEY:
        try:
            return " ".join(_deepl_chunk(p, source, target) for p in pieces)
        except Exception as deepl_err:  # noqa: BLE001
            logger.warning("DeepL failed (%s), trying MyMemory", deepl_err)

    try:
        return " ".join(_translate_chunk(p, source, target, email) for p in pieces)
    except Exception as mymemory_err:  # noqa: BLE001
        logger.warning("MyMemory failed (%s), trying fallback", mymemory_err)
        try:
            return " ".join(_google(p, source, target) or "" for p in pieces)
        except Exception as google_err:  # noqa: BLE001
            logger.error("All translation backends failed: %s / %s", mymemory_err, google_err)
            raise RuntimeError(
                f"translation service unavailable (MyMemory: {mymemory_err}; Google: {google_err})"
            ) from google_err
