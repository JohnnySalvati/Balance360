import re
import unicodedata    

def normalize_pattern(text: str) -> str:
    result = text.lower()
    result = "".join(c for c in unicodedata.normalize("NFKD", result) if not unicodedata.combining(c))
    result = re.sub(r"\$\s*[\d.,]+", " ", result)
    result = re.sub(r"\d+", " ", result)
    result = re.sub(r"[^\w\s]", " ", result)
    result = re.sub(r"\s+", " ", result).strip()
    return result
