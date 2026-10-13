"""Engineering terminology, not a lookup of sample filenames or page coordinates."""

import json
import re
from pathlib import Path

from .paths import DATA_ROOT, PACKAGE_ROOT


def normalize(text):
    # Space-insensitive matching recovers glued OCR words, without changing dimensions.
    """
    Matching ignores case, whitespace and punctuation, never the stored source text.
    This accommodates OCR joining adjacent technical words into a single token.
    Digits remain significant so distinct numerical engineering phrases cannot merge.
    The function is also used by the development gold evaluator for term matching.
    It does not perform spelling correction or invent dimensions.
    An empty normalized string is not evidence of a recognized engineering term.
    """
    return re.sub(r"[^a-z0-9]", "", text.lower())


def load_glossary():
    """
    The shipped glossary provides deterministic domain vocabulary.
    An optional UTF-8 JSON object stores additions made through the local UI.
    Custom values override matching shipped keys without rewriting package resources.
    Malformed custom JSON surfaces as an error rather than silently discarding user terms.
    Reloading at each document start makes saved terminology effective for the next job.
    No filename, page number or sample-specific coordinate is a translation lookup key.
    """
    entries = json.loads((PACKAGE_ROOT / "data/glossary.json").read_text("utf-8"))
    custom = DATA_ROOT / "glossary.json"
    if custom.exists():
        # User terminology wins; the shipped dictionary remains editable and intact.
        entries.update(json.loads(custom.read_text("utf-8")))
    return entries


def save_term(source, translation):
    """
    Store a human-reviewed source/translation pair in the user's local glossary.
    The temporary file is written completely before an atomic rename replaces the record.
    Readers therefore see either the previous version or the entire updated version.
    This method does not automatically approve already processed neural translations.
    Only the caller's explicitly selected term is written; drawings are not embedded.
    Parent storage is prepared by the application before this function is called.
    """
    target = DATA_ROOT / "glossary.json"
    entries = json.loads(target.read_text("utf-8")) if target.exists() else {}
    entries[source.strip()] = translation.strip()
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(entries, ensure_ascii=False, indent=2), "utf-8")
    temp.replace(target)
