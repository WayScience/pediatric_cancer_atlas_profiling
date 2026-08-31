#!/usr/bin/env python3
"""
Relocate a LoadData CSV produced by pe2loaddata (config.yml, channel-NAME
based -- see references/pccma_project_notes.md) into the CPG workspace
structure, rewriting its local PathName/FileName columns into
URL_<ChannelName> columns that point at the plate's new location(s) under
the CPG images/ tree.

This is deliberately NOT a replacement for pe2loaddata or for
0.create_loaddata_csvs.py's reimage-merge logic (dedup by Well/Site,
preferring Metadata_Reimaged==True, forcing Metadata_Plate to the bare
barcode). That logic already runs correctly upstream and produces one
"<barcode>_concatenated.csv" per analyzed plate -- see the docstring at the
bottom of this file for a walk-through of why it's correct, including the
one real edge case (a plate reimaged more than once) it depends on.

What this script adds: a merged CSV like that mixes rows whose images
physically live in TWO different CPG batch folders -- e.g. some wells'
images are under the "Round1" batch (the original scan) and others are
under "Round1_A673_Reimage" (the targeted re-image), even though every row
shares one Metadata_Plate (the barcode). load_data_csv rows can reference
different URLs per row, so this is not a problem -- it just means the
rewrite has to be done PER ROW, by matching each row's existing local path
against the manifest (which already records exactly which raw folder maps
to which CPG batch/full-plate-name), not by trusting Metadata_Reimaged as a
proxy for "which folder its images are in" (that flag says whether the ROW
won the dedup, not which raw folder it physically came from -- the two
usually agree but the path match is the actual ground truth).

Usage:
    python relocate_load_data_csv.py \\
        --manifest manifest.yaml \\
        --csv ./loaddata_csvs/Round_4_data/BR00143976_concatenated.csv \\
        --batch-name Round1 --plate-name BR00143976 \\
        --target ./local_cpg_mirror \\
        --s3-base s3://cellpainting-gallery \\
        --out ./local_cpg_mirror/cpg0041-pccma/alexslemonade/workspace/load_data_csv/Round1/BR00143976/load_data.csv

--batch-name is the batch that "owns" this plate's workspace entry -- for a
plate whose reimaged wells got merged back into the original barcode's
analysis, that's the ORIGINAL batch (e.g. "Round1", not "Round1_A673_Reimage"),
matching where its illum/backend/analysis/profiles outputs are filed with
organize_workspace.py. Pass it explicitly; it's a judgment call (which
physical plate identity this workspace entry represents), not something to
infer from the CSV.
"""

from __future__ import annotations

import argparse
import csv as csv_module
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

from cpg_lib import load_manifest, sanitize_name, sanitize_project_id


def read_manifest_file(path: Path) -> dict:
    text = path.read_text()
    if path.suffix.lower() in (".yaml", ".yml"):
        if yaml is None:
            sys.exit(
                "PyYAML is required to read .yaml manifests. Install it with "
                "'pip install pyyaml --break-system-packages', or convert your "
                "manifest to .json."
            )
        return yaml.safe_load(text)
    return json.loads(text)


def build_path_lookup(project_id: str, source_id: str, batches, s3_base: str):
    """Return [(raw_source_abs, s3_image_dir, batch_name, full_plate_name), ...],
    longest raw_source first so a nested match never loses to a shorter,
    unrelated prefix.
    """
    lookup = []
    for batch in batches:
        batch_name = batch.resolved_batch_name()
        for plate in batch.plates:
            raw_source = Path(plate.raw_source).resolve()
            full_plate_name = sanitize_name(plate.full_plate_name or Path(plate.raw_source).name)
            s3_dir = (
                f"{s3_base.rstrip('/')}/{project_id}/{source_id}/images/"
                f"{batch_name}/images/{full_plate_name}"
            )
            lookup.append((str(raw_source), s3_dir, batch_name, full_plate_name))
    lookup.sort(key=lambda t: -len(t[0]))
    return lookup


def resolve_url(local_dir: str, filename: str, lookup) -> tuple[str, str, str] | None:
    """Match local_dir against the manifest's raw sources and return
    (url, batch_name, full_plate_name), or None if nothing matches.
    """
    local_dir_resolved = str(Path(local_dir))
    for raw_source, s3_dir, batch_name, full_plate_name in lookup:
        if local_dir_resolved == raw_source or local_dir_resolved.startswith(raw_source + "/"):
            rel = Path(local_dir_resolved).relative_to(raw_source)
            rel_str = rel.as_posix()
            url = f"{s3_dir}/{rel_str}/{filename}" if rel_str != "." else f"{s3_dir}/{filename}"
            return url, batch_name, full_plate_name
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, required=True, help="Manifest used to build the CPG images/ tree (reorganize.py's input)")
    ap.add_argument("--csv", type=Path, required=True, help="A pe2loaddata-generated LoadData CSV, e.g. <barcode>_concatenated.csv")
    ap.add_argument("--batch-name", required=True, help="Batch that owns this plate's workspace entry, e.g. Round1 (see docstring)")
    ap.add_argument("--plate-name", required=True, help="Short plate-name / barcode, e.g. BR00143976 -- must match Metadata_Plate in the CSV")
    ap.add_argument("--target", type=Path, required=True, help="Local root the CPG tree was built under (same --target you gave reorganize.py)")
    ap.add_argument(
        "--s3-base",
        default="s3://cellpainting-gallery",
        help="Production S3 bucket root (default: s3://cellpainting-gallery). URLs are built even "
        "though the data initially goes to the maintainer's staging bucket -- see "
        "references/pccma_project_notes.md.",
    )
    ap.add_argument("--out", type=Path, required=True, help="Output path, e.g. .../workspace/load_data_csv/<batch>/<plate>/load_data.csv")
    args = ap.parse_args()

    manifest = read_manifest_file(args.manifest)
    project_id, source_id, batches = load_manifest(manifest)
    batch_name = sanitize_name(args.batch_name)
    plate_name = sanitize_name(args.plate_name)

    lookup = build_path_lookup(project_id, source_id, batches, args.s3_base)

    with args.csv.open(newline="") as fh:
        reader = csv_module.DictReader(fh)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            sys.exit(f"{args.csv} has no header row -- nothing to relocate.")

        pathname_cols = sorted(c for c in fieldnames if c.startswith("PathName_"))
        if not pathname_cols:
            sys.exit(
                f"No PathName_<Channel> columns found in {args.csv} (found: {fieldnames}). "
                "This doesn't look like a pe2loaddata LoadData CSV."
            )

        rows_out = []
        unresolved = []
        batches_touched: dict[str, int] = {}

        for i, row in enumerate(reader):
            if row.get("Metadata_Plate") != plate_name:
                sys.exit(
                    f"Row {i} has Metadata_Plate={row.get('Metadata_Plate')!r}, expected "
                    f"{plate_name!r} (--plate-name). Is this the right CSV for this plate?"
                )
            for pcol in pathname_cols:
                channel = pcol[len("PathName_"):]
                fcol = f"FileName_{channel}"
                if fcol not in row:
                    sys.exit(f"{args.csv} has {pcol} but no matching {fcol} -- can't build a URL for it.")
                local_dir = row[pcol]
                filename = row[fcol]
                resolved = resolve_url(local_dir, filename, lookup)
                if resolved is None:
                    unresolved.append((i, pcol, local_dir))
                    continue
                url, row_batch_name, _full_plate_name = resolved
                row[f"URL_{channel}"] = url
                batches_touched[row_batch_name] = batches_touched.get(row_batch_name, 0) + 1
            rows_out.append(row)

    if unresolved:
        print(
            f"ERROR: {len(unresolved)} row/column value(s) didn't match any raw_source in "
            f"{args.manifest} -- refusing to write a load_data_csv with unresolved image "
            "locations. First few:",
            file=sys.stderr,
        )
        for i, col, local_dir in unresolved[:10]:
            print(f"  row {i}, {col}: {local_dir}", file=sys.stderr)
        sys.exit(
            "Check that --manifest is the same one reorganize.py used for these raw folders, "
            "and that the plate wasn't reorganized from a different raw_source path since."
        )

    url_cols = sorted({c for row in rows_out for c in row if c.startswith("URL_")})
    out_fieldnames = list(dict.fromkeys(list(fieldnames) + url_cols))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        writer = csv_module.DictWriter(fh, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"Wrote {len(rows_out)} rows to {args.out}")
    print(f"URL_<Channel> columns added: {url_cols}")
    if len(batches_touched) > 1:
        print(
            f"\nNOTE: this plate's images span {len(batches_touched)} CPG batches "
            f"({sorted(batches_touched)}) -- expected for a plate with merged reimaged wells. "
            f"The load_data_csv itself is filed under batch {batch_name!r} (--batch-name), "
            "which should be the ORIGINAL batch, matching where illum/backend/analysis/profiles "
            "for this plate are filed with organize_workspace.py."
        )


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Why 0.create_loaddata_csvs.py's merge/dedup logic is correct
# ---------------------------------------------------------------------------
# (For the model/user reading this script, not executed -- documentation.)
#
# Per plate barcode, it:
#   1. Runs pe2loaddata (channel-NAME based, via config.yml) once per raw
#      Measurement folder that barcode appears in -- once for the original
#      scan, once more for each later targeted re-image -- producing one
#      "<plate_name>_loaddata_original.csv" per folder.
#   2. Concatenates all of those folders' CSVs for one barcode, tagging each
#      row with Metadata_Reimaged (True if the source filename contains
#      "Reimage"/"Re-imaged"/etc).
#   3. Sorts Metadata_Reimaged descending (True first) then
#      drop_duplicates(subset=[Well, Site], keep="first") -- so whenever the
#      SAME well+site appears in both an original and a reimage folder, the
#      reimaged row wins and the poor-quality original row is dropped.
#      Wells that were never reimaged only exist in the original folder's
#      rows, so they have no duplicate to lose to and pass through
#      unchanged. This is correct AS LONG AS no single well+site pair is
#      covered by two *different* reimage folders for the same barcode --
#      true here because a reimage folder targets one cell line's wells,
#      and each well belongs to exactly one cell line.
#   4. Forces Metadata_Plate = the barcode for every surviving row, so the
#      merged CSV is keyed by the physical plate identity, not by which
#      folder each row happened to come from.
#
# The one thing this literal script (0.create_loaddata_csvs.py) doesn't
# handle: it discovers plates via `index_directory.glob("Plate *")`, which
# only matches the Round2/3/4-style naming convention. Round 1 (SN0313537)
# uses bare-barcode + dated-reimage folder names instead (see
# references/pccma_project_notes.md), so this exact script won't find any
# plates there -- confirm with the user whether a Round-1-specific variant
# of this script exists, or whether Round 1 hasn't been run through
# illum/analysis yet, before assuming Round 1 plates have a
# "<barcode>_concatenated.csv" to relocate.
