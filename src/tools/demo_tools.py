"""
NoAPI demo tools (pure-Python helpers) that we can later expose to ADK as
FunctionTools. For now, they are plain functions to avoid ungrounded imports.
"""
from collections import Counter
import math
import re
from typing import List


def math_eval(expr: str) -> str:
    """Evaluate a very limited arithmetic expression safely.

    Supports digits, + - * / ( ) and whitespace. Returns result as string.
    """
    if not re.fullmatch(r"[\d\s+\-*/().]+", expr):
        return "Unsupported expression."
    try:
        # Evaluate in a restricted namespace
        val = eval(expr, {"__builtins__": {}}, {"math": math})
    except Exception as e:
        return f"Error: {e}"
    return str(val)


def summarize(text: str, max_sentences: int = 3) -> str:
    """Very naive summarizer that returns the first N sentences."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sentences[: max(1, max_sentences)])


def keyword_extract(text: str, top_k: int = 5) -> List[str]:
    """Simple frequency-based keyword extraction (lowercased words)."""
    words = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    common = Counter(words).most_common(top_k)
    return [w for w, _ in common]
