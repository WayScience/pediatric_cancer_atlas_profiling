"""Helpers used by build_pccma_cell_line_metadata.ipynb."""

import re

import pandas as pd


def normalize_name(name) -> str:
    """Join key for cell line names: uppercase, letters and digits only (CHLA-10 -> CHLA10)."""
    return re.sub(r"[^A-Z0-9]", "", str(name).upper())


def merge_one_to_one(left, right, **kwargs):
    """Left join that fails loudly if it changes the number of rows."""
    n_rows = len(left)
    merged = left.merge(right, how="left", **kwargs)
    assert len(merged) == n_rows, "merge changed the number of rows"
    return merged


_TEXT_REPLACEMENTS = {
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    " ": " ", "™": "", "®": "", "©": "",
}


def clean_text(value):
    """ASCII-friendly text: drop trademark symbols, straighten dashes and quotes, join line breaks."""
    if not isinstance(value, str):
        return value
    for old, new in _TEXT_REPLACEMENTS.items():
        value = value.replace(old, new)
    return re.sub(r"\s+", " ", value).strip()


def first_valid(*values):
    """First value that is not missing, in the order given (None if all are missing)."""
    for value in values:
        if pd.notna(value):
            return value
    return None
