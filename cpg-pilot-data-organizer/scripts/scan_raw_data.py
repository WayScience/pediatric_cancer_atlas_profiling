#!/usr/bin/env python3
"""
Scan a raw pilot-round folder and auto-generate manifest entries for
reorganize.py, instead of hand-typing every plate/cell-line/variant
combination.

This exists because the raw folder naming already encodes almost everything
the manifest needs -- it just uses two different conventions depending on
the round:

  Round 2/3/4 style (folders directly under e.g. .../Round_2_data/):
    "Plate 3 All Cell Lines"        -> the original full-plate scan
    "Plate 3 A673 Reimage"          -> a targeted re-image of one cell line
  Each such folder can contain MULTIPLE plate-barcode subfolders (e.g. one
  "All Cell Lines" folder held 3 separate barcodes) -- every barcode
  subfolder becomes its own plate entry under the same batch.

  Round 1 style (folders directly under the SN0313537-identified folder):
    Bare barcode folders (e.g. "BR00143976__...-Measurement 2") are the
    original plates.
    "20240717_A-673_Re-imaged" style folders (DATE_CELLLINE_Re-imaged) are
    targeted re-images, dated rather than tied to a "Plate N" label.

Both styles are auto-detected from the folder names actually present, so
you don't need to specify which one -- but ALWAYS look at the printed
output before trusting it, especially for cell-line names, which get
title-cased and de-hyphenated for the batch name but kept verbatim in
comments so you can sanity check them against what the raw folder said.

Usage:
    python scan_raw_data.py --raw-dir "/path/to/Round_2_data" --round-label Round2 --out manifest_round2.yaml
    python scan_raw_data.py --raw-dir "/path/to/SN0313537" --round-label Round1 --out manifest_round1.yaml

Then review/edit the generated YAML, and merge the batches you want into
your main manifest (or pass --out - to print to stdout and copy by hand).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from cpg_lib import sanitize_name

PLATE_ALL_CELL_LINES_RE = re.compile(r"^Plate\s+(\d+)\s+All\s+Cell\s+Lines$", re.IGNORECASE)
PLATE_REIMAGE_RE = re.compile(r"^Plate\s+(\d+)\s+(.+?)\s+Reimage$", re.IGNORECASE)
DATED_REIMAGE_RE = re.compile(r"^(\d{8})_(.+?)_Re-?imaged?$", re.IGNORECASE)


def looks_like_plate_n_style(names: list[str]) -> bool:
    return any(PLATE_ALL_CELL_LINES_RE.match(n) or PLATE_REIMAGE_RE.match(n) for n in names)


def looks_like_round1_style(names: list[str]) -> bool:
    return any(DATED_REIMAGE_RE.match(n) for n in names)


def scan_plate_n_style(raw_dir: Path, round_label: str) -> list[dict]:
    """Handle 'Plate 3 All Cell Lines' / 'Plate 3 A673 Reimage' folders."""
    batches = []
    for entry in sorted(p for p in raw_dir.iterdir() if p.is_dir()):
        name = entry.name
        m_all = PLATE_ALL_CELL_LINES_RE.match(name)
        m_reimage = PLATE_REIMAGE_RE.match(name)

        if m_all:
            plate_num = m_all.group(1)
            batch = {
                "round_label": round_label,
                "plate_label": f"Plate{plate_num}",
                "cell_line": None,
                "variant": None,
                "_comment": f"from raw folder: {name!r} (base/original scan)",
                "plates": [],
            }
        elif m_reimage:
            plate_num = m_reimage.group(1)
            cell_line_raw = m_reimage.group(2).strip()
            batch = {
                "round_label": round_label,
                "plate_label": f"Plate{plate_num}",
                "cell_line": sanitize_name(cell_line_raw.replace(" ", "")),
                "variant": "Reimage",
                "_comment": f"from raw folder: {name!r} (cell_line as-found: {cell_line_raw!r})",
                "plates": [],
            }
        else:
            print(f"  SKIPPED (unrecognized folder name): {name}", file=sys.stderr)
            continue

        barcode_dirs = sorted(p for p in entry.iterdir() if p.is_dir())
        if not barcode_dirs:
            print(f"  WARNING: {name} has no plate subfolders", file=sys.stderr)
        for bc in barcode_dirs:
            batch["plates"].append({"raw_source": str(bc)})
        batches.append(batch)
    return batches


def scan_round1_style(raw_dir: Path, round_label: str) -> list[dict]:
    """Handle SN0313537-style: bare barcode dirs + DATE_CELLLINE_Re-imaged dirs."""
    batches = []
    base_plates = []
    for entry in sorted(p for p in raw_dir.iterdir() if p.is_dir()):
        name = entry.name
        m_dated = DATED_REIMAGE_RE.match(name)
        if m_dated:
            date_str, cell_line_raw = m_dated.groups()
            # Like the Plate-N-style Reimage folders, these wrap one or more
            # barcode/Measurement subfolders rather than being the plate
            # folder themselves -- confirmed against real data (each dated
            # folder held 2-3 "<barcode>__<timestamp>-MeasurementN" dirs).
            barcode_dirs = sorted(p for p in entry.iterdir() if p.is_dir())
            if not barcode_dirs:
                print(f"  WARNING: {name} has no plate subfolders", file=sys.stderr)
            batches.append(
                {
                    "round_label": round_label,
                    "plate_label": None,
                    "cell_line": sanitize_name(cell_line_raw.replace(" ", "")),
                    "variant": f"Reimage{date_str}",
                    "_comment": f"from raw folder: {name!r} (cell_line as-found: {cell_line_raw!r}, imaged {date_str})",
                    "plates": [{"raw_source": str(bc)} for bc in barcode_dirs],
                }
            )
        elif "__" in name:
            # A bare acquisition folder, e.g. BR00143976__...-Measurement2 --
            # this IS the plate folder itself, not a parent of barcode dirs.
            base_plates.append(entry)
        else:
            print(f"  SKIPPED (unrecognized folder name): {name}", file=sys.stderr)

    if base_plates:
        batches.insert(
            0,
            {
                "round_label": round_label,
                "plate_label": None,
                "cell_line": None,
                "variant": None,
                "_comment": f"{len(base_plates)} original plate(s) found directly under {raw_dir.name}/",
                "plates": [{"raw_source": str(p)} for p in base_plates],
            },
        )
    return batches


def to_yaml(batches: list[dict]) -> str:
    lines = ["batches:"]
    for b in batches:
        lines.append(f"  # {b['_comment']}")
        if b.get("plate_label") or b.get("cell_line") or b.get("variant"):
            lines.append(f"  - round_label: {b['round_label']}")
            if b.get("plate_label"):
                lines.append(f"    plate_label: {b['plate_label']}")
            if b.get("cell_line"):
                lines.append(f"    cell_line: {b['cell_line']}")
            if b.get("variant"):
                lines.append(f"    variant: {b['variant']}")
        else:
            lines.append(f"  - round_label: {b['round_label']}")
        lines.append("    plates:")
        for p in b["plates"]:
            lines.append(f"      - raw_source: \"{p['raw_source']}\"")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", type=Path, required=True, help="Path to one round's raw folder, e.g. Round_2_data or SN0313537")
    ap.add_argument("--round-label", required=True, help="e.g. Round1, Round2, Round3, Round4")
    ap.add_argument("--out", required=True, help="Output YAML fragment path, or '-' for stdout")
    args = ap.parse_args()

    if not args.raw_dir.is_dir():
        sys.exit(f"--raw-dir {args.raw_dir} does not exist or is not a directory")

    names = [p.name for p in args.raw_dir.iterdir() if p.is_dir()]
    is_plate_n = looks_like_plate_n_style(names)
    is_round1 = looks_like_round1_style(names)

    if is_plate_n and not is_round1:
        print(f"Detected 'Plate N ...' style folder naming under {args.raw_dir}", file=sys.stderr)
        batches = scan_plate_n_style(args.raw_dir, args.round_label)
    elif is_round1:
        print(f"Detected Round-1 style folder naming (dated reimages + bare barcodes) under {args.raw_dir}", file=sys.stderr)
        batches = scan_round1_style(args.raw_dir, args.round_label)
    else:
        sys.exit(
            f"Could not detect a known naming convention under {args.raw_dir}. "
            "Folders seen: " + ", ".join(sorted(names)[:20])
        )

    yaml_text = to_yaml(batches)
    n_plates = sum(len(b["plates"]) for b in batches)
    print(f"Found {len(batches)} batch(es), {n_plates} plate folder(s) total.", file=sys.stderr)

    if args.out == "-":
        print(yaml_text)
    else:
        Path(args.out).write_text(yaml_text)
        print(f"Wrote {args.out} -- review it, then merge the batches you want into your manifest.", file=sys.stderr)


if __name__ == "__main__":
    main()
