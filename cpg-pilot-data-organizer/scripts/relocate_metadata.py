#!/usr/bin/env python3
"""
Build workspace/metadata/platemaps/<batch>/ from this project's raw
platemap records, per CPG's documented structure
(https://broadinstitute.github.io/cellpainting-gallery/data_structure.html,
confirmed 2026-08-28):

    workspace/metadata/platemaps/<batch>/barcode_platemap.csv
    workspace/metadata/platemaps/<batch>/platemap/<Plate_Map_Name>.txt

Per CPG's docs:
  - barcode_platemap.csv is comma-separated with exactly two columns:
    Assay_Plate_Barcode (must match the <plate-name> used elsewhere, i.e.
    the barcode) and Plate_Map_Name (references a file in platemap/).
    Many-to-one Assay_Plate_Barcode -> Plate_Map_Name is expected/normal.
  - platemap/<NAME>.txt is TAB-separated with at minimum plate_map_name
    (matches Plate_Map_Name above) and well_position (matches the well
    names load_data_csv/CellProfiler use) columns, plus whatever other
    metadata columns are useful.

This project's raw records (0.download_data/metadata/, NOT yet in CPG's
shape):
  - Barcode_platemap_pilot_data.csv: barcode,time_point,platemap_file --
    maps every barcode across all 4 rounds to which plate-design CSV it
    uses. NOTE: time_point (24/48/72h) has no slot in CPG's platemap
    schema (it's a per-barcode fact, not a per-well one) -- it's dropped
    from barcode_platemap.csv here rather than silently reshaped into
    something CPG doesn't ask for. Flag for Erin/Shantanu whether it
    should go somewhere else (e.g. an extra load_data_csv column).
  - platemaps/Assay_Plate<N>_platemap.csv: cell_line,row,column,well,
    seeding_density,condition -- one physical plate DESIGN (there are 13
    of these for cpg0041-pccma's 12 batches, because Round 1's single
    "Round1" batch actually covers TWO plate designs, Assay_Plate1 and
    Assay_Plate2, split across its 6 barcodes -- confirmed against
    Barcode_platemap_pilot_data.csv, not assumed).

Which batch each barcode's metadata belongs to: metadata describes a
physical plate's design, which doesn't change on reimaging -- so, like
profiles/backend/analysis, it belongs ONLY in the base/original batch, never
duplicated into reimage batches. This script reuses reorganize.py
--emit-batch-map's output (batches[0] per plate_name) for exactly this,
the same convention relocate_illum_and_profiles.py uses for profiles.

Usage:
    python relocate_metadata.py \\
        --batch-map /tmp/round1_batch_map.json \\
        --barcode-platemap-csv "/path/to/0.download_data/metadata/platemaps/Barcode_platemap_pilot_data.csv" \\
        --platemap-source-dir "/path/to/0.download_data/metadata/platemaps" \\
        --target ./local_cpg_mirror --project-id cpg0041-pccma --source-id alexslemonade \\
        --execute

Unlike the images/illum/profiles scripts, this one is small enough (a few KB
per batch) that it doesn't need --hardlink -- it always writes small new
files directly.

Defaults to a dry run (prints what it would write); pass --execute to
actually write. Rerun-safe: an existing destination file with identical
content is left alone; different content raises rather than silently
overwriting (these are hand-curated plate records, not regenerable data).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def load_barcode_to_platemap(path: Path) -> dict[str, str]:
    rows = list(csv.DictReader(path.open()))
    for col in ("barcode", "platemap_file"):
        if col not in rows[0]:
            sys.exit(f"{path} is missing expected column {col!r} (found: {list(rows[0])})")
    mapping = {}
    for r in rows:
        mapping[r["barcode"]] = r["platemap_file"]
    return mapping


def write_or_check(dest: Path, content: str, execute: bool, results: list[str]) -> None:
    if dest.exists():
        if dest.read_text() == content:
            results.append(f"  (already correct, skipping) {dest}")
            return
        sys.exit(
            f"{dest} already exists with DIFFERENT content than what this run would write -- "
            "these are hand-curated plate records, not regenerable data, so refusing to overwrite. "
            "Remove it yourself first if you're sure you want to replace it."
        )
    results.append(f"  {'WROTE' if execute else 'would write'} {dest} ({len(content)} bytes)")
    if execute:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)


def build_platemap_txt(source_csv: Path, plate_map_name: str) -> str:
    rows = list(csv.DictReader(source_csv.open()))
    if "well" not in rows[0]:
        sys.exit(f"{source_csv} has no 'well' column to rename to 'well_position' (found: {list(rows[0])})")
    fieldnames = ["plate_map_name", "well_position"] + [
        c for c in rows[0] if c != "well"
    ]
    import io

    buf = io.StringIO()
    # lineterminator="\n": csv's default dialect terminates rows with "\r\n"
    # regardless of platform, which would embed a literal \r in every line of
    # a plain-text .txt file (confusing to open, and it breaks the
    # rerun-safety comparison below since Path.read_text()'s universal-
    # newline translation strips \r\n back to \n on read, making a
    # just-written file look "different" from itself on the next run).
    writer = csv.DictWriter(buf, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    for r in rows:
        out = {"plate_map_name": plate_map_name, "well_position": r["well"]}
        for c in fieldnames:
            if c not in ("plate_map_name", "well_position"):
                out[c] = r[c]
        writer.writerow(out)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch-map", type=Path, required=True, help="JSON from reorganize.py --emit-batch-map")
    ap.add_argument("--barcode-platemap-csv", type=Path, required=True)
    ap.add_argument("--platemap-source-dir", type=Path, required=True, help="Dir containing Assay_Plate<N>_platemap.csv files")
    ap.add_argument("--target", type=Path, required=True)
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--source-id", required=True)
    ap.add_argument("--execute", action="store_true", help="Actually write (default: dry run only)")
    args = ap.parse_args()

    batch_map: dict[str, list[str]] = json.loads(args.batch_map.read_text())
    barcode_to_platemap = load_barcode_to_platemap(args.barcode_platemap_csv)

    # Group plate_names by their base batch (batches[0], same convention as
    # relocate_illum_and_profiles.py's profiles handling).
    by_base_batch: dict[str, list[str]] = {}
    problems = []
    for plate_name, batches in batch_map.items():
        base_batch = batches[0]
        if plate_name not in barcode_to_platemap:
            problems.append(f"  no platemap mapping found for plate/barcode {plate_name!r}")
            continue
        by_base_batch.setdefault(base_batch, []).append(plate_name)

    if problems:
        print("Problems found (fix before --execute):")
        for p in problems:
            print(p)
        if not args.execute:
            sys.exit(1)

    metadata_root = args.target / args.project_id / args.source_id / "workspace" / "metadata" / "platemaps"
    results: list[str] = []
    written_platemap_txt: set[tuple[str, str]] = set()  # (batch, plate_map_name) already handled this run

    for base_batch, plate_names in sorted(by_base_batch.items()):
        plate_names = sorted(plate_names)
        # barcode_platemap.csv -- one row per barcode in this batch.
        lines = ["Assay_Plate_Barcode,Plate_Map_Name"]
        needed_platemaps = set()
        for pn in plate_names:
            pmap = barcode_to_platemap[pn]
            lines.append(f"{pn},{pmap}")
            needed_platemaps.add(pmap)
        barcode_csv_content = "\n".join(lines) + "\n"

        print(f"=== {base_batch}: {len(plate_names)} barcode(s), {len(needed_platemaps)} platemap(s) ===")
        write_or_check(
            metadata_root / base_batch / "barcode_platemap.csv",
            barcode_csv_content,
            args.execute,
            results,
        )

        for pmap in sorted(needed_platemaps):
            key = (base_batch, pmap)
            if key in written_platemap_txt:
                continue
            written_platemap_txt.add(key)
            source_csv = args.platemap_source_dir / f"{pmap}.csv"
            if not source_csv.is_file():
                sys.exit(f"Expected platemap source {source_csv} does not exist")
            txt_content = build_platemap_txt(source_csv, pmap)
            write_or_check(
                metadata_root / base_batch / "platemap" / f"{pmap}.txt",
                txt_content,
                args.execute,
                results,
            )

        for line in results:
            print(line)
        results.clear()
        print()

    if not args.execute:
        print("Dry run only -- no files were written. Re-run with --execute to write the files above.")
    else:
        print(f"Done -- wrote metadata for {len(by_base_batch)} batch(es).")

    print(
        "\nNOTE: time_point (24h/48h/72h per barcode, from Barcode_platemap_pilot_data.csv) is NOT "
        "carried into barcode_platemap.csv -- CPG's schema has no slot for a per-barcode fact there. "
        "Flag for Erin/Shantanu whether it belongs somewhere else (e.g. an extra load_data_csv column)."
    )


if __name__ == "__main__":
    main()
