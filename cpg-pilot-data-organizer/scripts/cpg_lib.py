"""
Shared helpers for reorganizing Cell Painting pilot data into the
Cell Painting Gallery (CPG) expected structure.

These functions encode the structural rules from
references/cpg_data_structure.md as executable logic, rather than leaving
them as prose someone has to remember to follow by hand. In particular:

- sanitize_name() enforces the "no whitespace, only _ and -" rule.
- build_batch_name() enforces the "no double nesting, concatenate instead"
  rule that was a repeated correction in the pccma deposit discussion.
- derive_plate_name() enforces the "<plate-name> must be an obvious,
  deterministic short form of <full-plate-name>" rule.

Nothing in this module touches the filesystem — it's pure string/path logic,
which makes it easy to unit test and easy to reuse from reorganize.py,
generate_load_data_csv.py, and validate_structure.py without duplicating the
rules three times.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ALLOWED_EXTRA_CHARS = {"_", "-"}


def sanitize_name(name: str) -> str:
    """Strip whitespace and any character other than alphanumerics, _, and -.

    CPG's contributing guide requires folder names to have no whitespace and
    no special characters other than `_` and `-`. This collapses runs of
    whitespace to nothing (not to an underscore) because that matches how
    the pccma discussion actually cleaned up names like
    "...-Measurement 2" -> "...-Measurement2", not "...-Measurement_2".
    """
    # Drop whitespace entirely first (matches the "Measurement 2" -> "Measurement2" precedent).
    no_space = re.sub(r"\s+", "", name)
    cleaned = "".join(
        ch for ch in no_space if ch.isalnum() or ch in ALLOWED_EXTRA_CHARS
    )
    if not cleaned:
        raise ValueError(f"Name {name!r} sanitized to an empty string")
    return cleaned


def sanitize_project_id(project_id: str) -> str:
    """Project ids are lowercase with digits, underscores, and hyphens.

    Real examples (cpg0041-pccma, cpg0000-jump-pilot) use hyphens, so the
    allowed charset here matches the general folder-naming rule (letters,
    digits, `_`, `-`) rather than excluding hyphens.
    """
    lowered = project_id.lower()
    if not re.fullmatch(r"[a-z0-9_-]+", lowered):
        raise ValueError(
            f"Project id {project_id!r} must contain only lowercase letters, "
            f"digits, '_', and '-' once lowercased (got {lowered!r})"
        )
    return lowered


def build_batch_name(
    round_label: Optional[str],
    plate_label: Optional[str] = None,
    cell_line: Optional[str] = None,
    variant: Optional[str] = None,
) -> str:
    """Build a single, flat batch-folder name from its logical parts.

    This is the function that enforces "no double nesting": instead of a
    directory tree like Round2/Plate3_A673_Reimage/, everything gets
    concatenated with underscores into one folder name,
    e.g. Round2_Plate3_A673_Reimage, matching the structure the CPG
    maintainer approved for cpg0041-pccma. Any part that's None/empty is
    skipped rather than leaving a stray underscore.
    """
    parts = [p for p in (round_label, plate_label, cell_line, variant) if p]
    if not parts:
        raise ValueError("build_batch_name() needs at least one non-empty part")
    return sanitize_name("_".join(parts))


_MEASUREMENT_SPLIT_RE = re.compile(r"__|-Measurement", re.IGNORECASE)


def derive_plate_name(full_plate_name: str) -> str:
    """Derive the short <plate-name> from a raw <full-plate-name> folder.

    Follows the documented example: 'BR00117035__2021-05-02T16_02_51-Measurement1'
    -> 'BR00117035'. The rule applied here is: take everything before the
    first '__' (Opera Phenix/Harmony's separator between the plate barcode
    and the acquisition timestamp/measurement suffix). If there's no '__' in
    the name, fall back to the sanitized full name unchanged (nothing to
    truncate) and it's on the caller to confirm uniqueness.

    Deliberately simple and deterministic: the CPG docs require the
    relationship between full-plate-name and plate-name to be "immediately
    obvious", so this should never be doing anything cleverer than "split at
    the first known separator".
    """
    sanitized_full = sanitize_name(full_plate_name)
    if "__" in sanitized_full:
        return sanitized_full.split("__", 1)[0]
    return sanitized_full


def well_from_opera_phenix(row: int, col: int) -> str:
    """Convert Opera Phenix row/col (1-indexed) to a well id like 'A01'."""
    if row < 1 or row > 26:
        raise ValueError(f"Row {row} out of A-Z range")
    letter = string.ascii_uppercase[row - 1]
    return f"{letter}{col:02d}"


# Typical Opera Phenix / Harmony export filename, e.g.:
#   r01c01f01p01-ch1sk1fk1fl1.tiff
# r=row, c=column, f=field/site, p=plane(z), ch=channel, sk=timepoint,
# fk=? , fl=flim. We only need row/col/field/channel for load_data_csv.
OPERA_PHENIX_FILENAME_RE = re.compile(
    r"r(?P<row>\d{2})c(?P<col>\d{2})f(?P<field>\d{2})p(?P<plane>\d{2})"
    r"-ch(?P<channel>\d+)",
    re.IGNORECASE,
)


@dataclass
class ParsedImage:
    path: Path
    well: str
    site: str
    channel: str


def parse_opera_phenix_filename(path: Path) -> Optional[ParsedImage]:
    """Pull well/site/channel out of a Harmony-exported filename, or None
    if the filename doesn't match the expected pattern (caller should flag
    unmatched files rather than silently skipping them).
    """
    m = OPERA_PHENIX_FILENAME_RE.search(path.name)
    if not m:
        return None
    well = well_from_opera_phenix(int(m.group("row")), int(m.group("col")))
    site = str(int(m.group("field")))
    channel = m.group("channel")
    return ParsedImage(path=path, well=well, site=site, channel=channel)


@dataclass
class PlateEntry:
    """One raw plate folder to be relocated, from the manifest."""

    raw_source: str
    full_plate_name: Optional[str] = None  # defaults to sanitize_name(basename(raw_source))
    plate_name: Optional[str] = None  # defaults to derive_plate_name(full_plate_name)


@dataclass
class BatchEntry:
    """One target batch (one flat folder under images/), from the manifest."""

    round_label: Optional[str] = None
    plate_label: Optional[str] = None
    cell_line: Optional[str] = None
    variant: Optional[str] = None
    batch_name: Optional[str] = None  # overrides the built name if given
    plates: list = field(default_factory=list)  # list[PlateEntry]

    def resolved_batch_name(self) -> str:
        if self.batch_name:
            return sanitize_name(self.batch_name)
        return build_batch_name(
            self.round_label, self.plate_label, self.cell_line, self.variant
        )


def load_manifest(manifest: dict) -> tuple[str, str, list[BatchEntry]]:
    """Parse a loaded YAML/JSON manifest dict into (project_id, source_id, batches).

    See assets/manifest.example.yaml for the schema this expects.
    """
    project_id = sanitize_project_id(manifest["project_id"])
    source_id = sanitize_name(manifest["source_id"])
    batches = []
    for b in manifest.get("batches", []):
        plates = [
            PlateEntry(
                raw_source=p["raw_source"],
                full_plate_name=p.get("full_plate_name"),
                plate_name=p.get("plate_name"),
            )
            for p in b.get("plates", [])
        ]
        batches.append(
            BatchEntry(
                round_label=b.get("round_label"),
                plate_label=b.get("plate_label"),
                cell_line=b.get("cell_line"),
                variant=b.get("variant"),
                batch_name=b.get("batch_name"),
                plates=plates,
            )
        )
    return project_id, source_id, batches
