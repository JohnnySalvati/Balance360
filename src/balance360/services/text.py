import re
import unicodedata


def normalize_pattern(text: str) -> str:
    result = text.lower()
    result = "".join(
        c for c in unicodedata.normalize("NFKD", result) if not unicodedata.combining(c)
    )
    result = re.sub(r"\$\s*[\d.,]+", " ", result)
    result = re.sub(r"\d+", " ", result)
    result = re.sub(r"[^\w\s]", " ", result)
    result = re.sub(r"\s+", " ", result).strip()
    return result


def digits_only(string: str | None) -> str:
    return "".join([c for c in string if c.isdigit()]) if string else ""


def format_cuit(cuit: str | None) -> str:
    if not cuit:
        return ""
    if len(cuit) != 11:
        return cuit
    return f"{cuit[:2]}-{cuit[2:10]}-{cuit[10:]}"
