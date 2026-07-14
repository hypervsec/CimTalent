import html
import re
import unicodedata

from app.db.enums import RequirementImportance

BLOCK_TAG_RE = re.compile(
    r"</?(?:p|div|ul|ol|br|h[1-6]|section|article|tr|td|table)[^>]*>", re.IGNORECASE
)
LI_OPEN_RE = re.compile(r"<li[^>]*>", re.IGNORECASE)
LI_CLOSE_RE = re.compile(r"</li>", re.IGNORECASE)
HTML_TAG_RE = re.compile(r"<[^>]+>")
BULLET_RE = re.compile(r"^\s*(?:[-*•▪◦]|\d+[.)])\s*")
INLINE_WHITESPACE_RE = re.compile(r"[^\S\r\n]+")
BLANK_LINES_RE = re.compile(r"\n{3,}")
MATCH_WHITESPACE_RE = re.compile(r"\s+")
TURKISH_CASE_TRANSLATION = str.maketrans("İIı", "iii")

REQUIRED_SIGNALS = (
    "zorunlu",
    "şart",
    "gerekmektedir",
    "sahip olmak",
    "en az",
    "mutlaka",
    "aranmaktadır",
    "beklenmektedir",
    "required",
    "must",
    "mandatory",
    "minimum",
    "shall",
    "need to",
    "expected to",
)
PREFERRED_SIGNALS = (
    "tercihen",
    "tercih sebebidir",
    "avantajdır",
    "artı olacaktır",
    "olması tercih edilir",
    "preferred",
    "nice to have",
    "plus",
    "advantage",
    "desirable",
)
OPTIONAL_SIGNALS = ("opsiyonel", "optional", "bonus")


def clean_job_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", html.unescape(text or ""))
    normalized = LI_OPEN_RE.sub("\n- ", normalized)
    normalized = LI_CLOSE_RE.sub("\n", normalized)
    normalized = BLOCK_TAG_RE.sub("\n", normalized)
    normalized = HTML_TAG_RE.sub("", normalized)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for raw_line in normalized.split("\n"):
        line = INLINE_WHITESPACE_RE.sub(" ", raw_line).strip()
        if not line:
            lines.append("")
            continue
        if BULLET_RE.match(line):
            line = f"- {BULLET_RE.sub('', line).strip()}"
        lines.append(line)
    return BLANK_LINES_RE.sub("\n\n", "\n".join(lines)).strip()


def normalize_for_matching(text: str) -> str:
    translated = unicodedata.normalize("NFKC", text).translate(TURKISH_CASE_TRANSLATION)
    return MATCH_WHITESPACE_RE.sub(" ", translated.casefold()).strip()


def detect_importance(
    text: str,
    section_importance: RequirementImportance = RequirementImportance.OPTIONAL,
) -> RequirementImportance:
    normalized = normalize_for_matching(text)
    if any(normalize_for_matching(signal) in normalized for signal in REQUIRED_SIGNALS):
        return RequirementImportance.REQUIRED
    if any(normalize_for_matching(signal) in normalized for signal in PREFERRED_SIGNALS):
        return RequirementImportance.PREFERRED
    if any(normalize_for_matching(signal) in normalized for signal in OPTIONAL_SIGNALS):
        return RequirementImportance.OPTIONAL
    return section_importance


def deduplicate_strings(
    values: list[str] | tuple[str, ...], limit: int | None = None
) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = value.strip()
        key = normalize_for_matching(clean)
        if clean and key not in seen:
            seen.add(key)
            output.append(clean)
        if limit is not None and len(output) >= limit:
            break
    return tuple(output)
