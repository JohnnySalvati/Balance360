import re

STOPWORDS = {
    "u$s", "usd", "$", "ars",
    "c/u", "cu",
    "=", "+",
}

def normalize_pattern(text: str) -> str:
    if not text:
        return ""

    text = text.lower()

    # eliminar importes
    text = re.sub(r"\d+[.,]?\d*", " ", text)

    # eliminar símbolos
    text = re.sub(r"[^\w\s]", " ", text)

    words = []
    for w in text.split():
        if w in STOPWORDS:
            continue
        if len(w) <= 2:
            continue
        words.append(w)

    return " ".join(words).strip()
