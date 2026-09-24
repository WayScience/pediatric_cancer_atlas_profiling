"""Helpers used by build_pccma_cell_line_metadata.ipynb."""

import re
import textwrap

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


def phase_family(value):
    """Collapse a phase-of-disease code to its family.

    "Dx" (at diagnosis) and "Active treatment" are kept as they are; every other code (PD, PD-BMT, PD-PM, P-EBR,
    "Post-treatment (relapse)", ...) counts as "relapse". Returns None when the value is missing.
    """
    if pd.isna(value):
        return None
    return value if value in ("Dx", "Active treatment") else "relapse"


def indent(text):
    """Wrap text to 100 columns with a four-space indent, for the column descriptions file."""
    return textwrap.fill(text, width=100, initial_indent="    ", subsequent_indent="    ")


def resolve_row(row, normal_reference_lines, published_lookup_lines, derivative_lines, parent_lookup):
    """Consolidate the annotation of one cell line into single columns, using a fixed order of precedence.

    Each column takes the first value available in its order of precedence (see step 10 of the notebook), so a line can
    take its cancer type from one source and its age from another. Nothing is guessed: a column with no source stays empty.

    Args:
        row: A row of the merged table (one cell line and plate condition) with the per-source columns
            (``*_pedmap``, ``*_cog``, ``*_depmap``, ``*_snapshot``, ``*_catalog``, ...).
        normal_reference_lines: ATCC normal reference lines by ``cell_line_key``, with their cancer type, source, link, sex
            and age. These values take precedence over every other source, and their ``origin`` is left empty.
        published_lookup_lines: Values taken from a public catalog or paper for lines that no other file covers.
        derivative_lines: Derivative lines by ``cell_line_key`` with the ``parent_key`` and ``parent_name`` of the parental
            line, whose cancer type they take when no other source has one.
        parent_lookup: Table indexed by ``cell_line_key`` with the ``cancer_type_pedmap``, ``cancer_type_cog`` and
            ``cancer_type_depmap`` columns, used to look up a parental line's cancer type.

    Returns:
        A ``pandas.Series`` with ``cancer_type``, ``sex``, ``age``, ``subtype``, ``source``, ``origin``,
        ``approx_doubling_time_observed`` and ``cell_line_link``.
    """
    key = row["cell_line_key"]
    normal = normal_reference_lines.get(key, {})
    published = published_lookup_lines.get(key, {})
    derivative = derivative_lines.get(key)
    derived_type = derived_source = None
    if derivative is not None:
        derived_type = first_valid(*parent_lookup.loc[derivative["parent_key"]])
        derived_source = f"Derivative of {derivative['parent_name']}"
    return pd.Series(
        {
            "cancer_type": first_valid(
                normal.get("cancer_type"), row["cancer_type_pedmap"], row["cancer_type_cog"], row["cancer_type_depmap"],
                derived_type, published.get("cancer_type"),
            ),
            "sex": first_valid(normal.get("sex"), row["sex_snapshot"], row["sex_pedmap"], row["sex_depmap"], row["sex_str"]),
            "age": first_valid(normal.get("age"), row["age_snapshot"], row["age_pedmap"], row["age_cog"], row["age_catalog"], row["age_depmap"]),
            "subtype": first_valid(row["subtype_snapshot"], row["subtype_pedmap"], row["subtype_catalog"], published.get("subtype")),
            "source": first_valid(
                row["source_pedmap"], normal.get("source"), derived_source, published.get("source"),
                "COG" if row["in_cog_list"] else None, row["source_depmap"],
            ),
            "origin": None if normal else first_valid(row["origin_snapshot"], row["origin_pedmap"], row["origin_catalog"], row["origin_depmap"], row["origin_inferred"]),
            "approx_doubling_time_observed": row["doubling_time_observed_pedmap"],
            "cell_line_link": first_valid(row["cell_line_link_pedmap"], row["cell_line_link_repository"], normal.get("link"), published.get("link")),
        }
    )
