#!/usr/bin/env python3
"""
Reorganize raw pilot-round plate folders into the Cell Painting Gallery
images/ structure, driven by a manifest file (see
assets/manifest.example.yaml).

Defaults to a dry run that only prints the planned mapping — nothing is
copied until you pass --execute. This is deliberate: these are irreplaceable
research images, and the CPG structure rules (concatenated batch names,
sanitized folder names, full-plate-name vs plate-name) are exactly the kind
of thing worth double-checking in a dry run before touching real data.

Usage:
    python reorganize.py MANIFEST.yaml --target /path/to/local_cpg_mirror
    python reorganize.py MANIFEST.yaml --target /path/to/local_cpg_mirror --execute
    python reorganize.py MANIFEST.yaml --target /path/to/local_cpg_mirror --execute --hardlink
    python reorganize.py MANIFEST.yaml --target /path/to/local_cpg_mirror --execute --move

By default files are copied (originals kept). If --target is on the SAME
drive/filesystem as your raw data and disk space is tight, use --hardlink
instead: it builds the whole CPG-structured tree with zero extra disk usage
(new directory entries pointing at the same underlying data), rather than
duplicating potentially hundreds of GB per round. Pass --move only once
you've confirmed the dry run output looks right and you have a backup
elsewhere -- --move and --hardlink are mutually exclusive with each other.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

from cpg_lib import BatchEntry, derive_plate_name, load_manifest, sanitize_name


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


def _hardlink_or_skip(src, dst) -> None:
    """Like os.link, but tolerant of re-running a partial pass (e.g. after an
    earlier run stopped partway through a big round): if dst already exists
    as the same hardlinked file, or as a same-size file (likely placed by an
    earlier non-hardlink run), skip instead of failing. Only raises for a
    genuine conflict -- an existing file with a DIFFERENT size -- or lets a
    real cross-device error propagate as OSError for the caller to report.
    Used as shutil.copytree's copy_function, so the signature is (src, dst).
    """
    src_path, dst_path = Path(src), Path(dst)
    if dst_path.exists():
        if dst_path.samefile(src_path) or dst_path.stat().st_size == src_path.stat().st_size:
            return
        raise OSError(
            errno.EEXIST,
            f"{dst_path} already exists with a DIFFERENT SIZE than {src_path} -- looks like "
            "stale/wrong content, not just an earlier copy. Remove it yourself first if you "
            "want to re-relocate it.",
        )
    os.link(src_path, dst_path)


def plan_batch(batch: BatchEntry, target_root: Path):
    """Yield (raw_source_path, dest_path, full_plate_name, plate_name) for
    every plate in this batch, without touching the filesystem.
    """
    batch_name = batch.resolved_batch_name()
    for plate in batch.plates:
        raw_source = Path(plate.raw_source)
        full_plate_name = sanitize_name(
            plate.full_plate_name or raw_source.name
        )
        plate_name = plate.plate_name or derive_plate_name(full_plate_name)
        dest = target_root / "images" / batch_name / "images" / full_plate_name
        yield raw_source, dest, full_plate_name, plate_name, batch_name


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest", type=Path, help="Path to manifest.yaml or manifest.json")
    ap.add_argument(
        "--target",
        type=Path,
        required=True,
        help="Local root to mirror the gallery under, e.g. ./local_cpg_mirror "
        "(both the project_id and source_id folders are created under this, "
        "e.g. ./local_cpg_mirror/cpg0041-pccma/alexslemonade/...)",
    )
    ap.add_argument("--execute", action="store_true", help="Actually copy/move/hardlink files (default: dry run only)")
    ap.add_argument(
        "--emit-batch-map",
        type=Path,
        help="Write a JSON file mapping {plate_name: [batch_name, ...]} for EVERY plate-name in this "
        "manifest -- a plate reimaged into several batches gets all of them (sorted; batches[0] is "
        "always the base/original batch -- see relocate_illum_and_profiles.py), and a plate never "
        "reimaged gets a single-element list. This is exactly the input organize_workspace.py illum "
        "needs for its multiple --batch-name values, generated from the manifest itself instead of "
        "hand-transcribed per round (error-prone -- see pccma_project_notes.md for how the Round 1 "
        "version of this was built by hand first). Works in dry-run mode too (no --execute needed) "
        "since it's derived purely from the manifest.",
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--move", action="store_true", help="Move instead of copy (only meaningful with --execute)")
    mode.add_argument(
        "--hardlink",
        action="store_true",
        help="Hardlink instead of copy (only meaningful with --execute). Builds the CPG-structured "
        "tree with ZERO extra disk space -- use this when --target is on the SAME filesystem/drive "
        "as your raw data and disk space is tight. Originals are untouched (same as --copy), but "
        "editing a file through either path edits the same underlying data, and hardlinks only work "
        "within one filesystem -- if --target is on a different drive, this will fail per-file and "
        "you'll need --move or plain copy instead.",
    )
    args = ap.parse_args()

    manifest = read_manifest_file(args.manifest)
    project_id, source_id, batches = load_manifest(manifest)
    source_root = args.target / project_id / source_id

    print(f"Project: {project_id}  Source: {source_id}")
    print(f"Target root: {source_root}\n")

    # plate_name uniqueness only needs to hold WITHIN a batch -- workspace
    # paths are backend/<batch>/<plate>/, profiles/<batch>/<plate>/, etc, so
    # two different batches can legitimately reuse the same short plate-name.
    # This matters in practice: a plate barcode gets reused when it's
    # re-imaged later (same barcode, new Measurement-folder timestamp), so
    # e.g. BR00145439 can appear in both a "...AllCellLines" batch and a
    # later "..._Reimage" batch. That's expected, not a collision -- only
    # flag it as a hard problem if the SAME batch maps one plate_name to two
    # different full_plate_names (that would be a real bug).
    plate_names_seen_in_batch: dict[tuple, str] = {}
    plate_names_seen_globally: dict[str, set] = {}
    problems = []
    notes = []
    plan = []

    for batch in batches:
        for raw_source, dest, full_plate_name, plate_name, batch_name in plan_batch(batch, source_root):
            plan.append((raw_source, dest, full_plate_name, plate_name, batch_name))
            if not raw_source.exists():
                problems.append(f"  MISSING raw source: {raw_source}")

            key = (batch_name, plate_name)
            if key in plate_names_seen_in_batch and plate_names_seen_in_batch[key] != full_plate_name:
                problems.append(
                    f"  DUPLICATE plate_name '{plate_name}' within batch '{batch_name}' used by both "
                    f"{plate_names_seen_in_batch[key]!r} and {full_plate_name!r} "
                    "-- plate-name must be unique within a batch"
                )
            plate_names_seen_in_batch[key] = full_plate_name

            plate_names_seen_globally.setdefault(plate_name, set()).add(batch_name)

    for plate_name, batch_names in plate_names_seen_globally.items():
        if len(batch_names) > 1:
            notes.append(
                f"  NOTE: plate-name '{plate_name}' is reused across batches {sorted(batch_names)} "
                "-- normal if this barcode was re-imaged later, but double check it's not a mistake"
            )

    for raw_source, dest, full_plate_name, plate_name, batch_name in plan:
        print(f"[{batch_name}]")
        print(f"  raw source : {raw_source}")
        print(f"  full-plate-name : {full_plate_name}")
        print(f"  plate-name : {plate_name}")
        print(f"  -> {dest}")
        print()

    if notes:
        print("Notes (informational, not blocking):")
        for n in notes:
            print(n)
        print()

    if problems:
        print("Problems found (fix these before running --execute):")
        for p in problems:
            print(p)
        if not args.execute:
            sys.exit(1)

    if args.emit_batch_map is not None:
        batch_map = {
            plate_name: sorted(batch_names)
            for plate_name, batch_names in plate_names_seen_globally.items()
        }
        n_multi = sum(1 for v in batch_map.values() if len(v) > 1)
        args.emit_batch_map.write_text(json.dumps(batch_map, indent=2, sort_keys=True) + "\n")
        print(
            f"Wrote batch map for {len(batch_map)} plate(s) ({n_multi} multi-batch, "
            f"{len(batch_map) - n_multi} single-batch) to {args.emit_batch_map} -- feed this to "
            "organize_workspace.py illum (see relocate scripts) instead of hand-typing "
            "--batch-name lists.\n"
        )

    if not args.execute:
        print("Dry run only -- no files were touched. Re-run with --execute to copy the files above.")
        return

    if problems:
        sys.exit("Refusing to --execute while problems remain (see above).")

    verb = "Moving" if args.move else "Hardlinking" if args.hardlink else "Copying"
    for raw_source, dest, full_plate_name, plate_name, batch_name in plan:
        print(f"{verb} {raw_source} -> {dest}")
        dest.mkdir(parents=True, exist_ok=True)
        for item in raw_source.iterdir():
            dest_item = dest / item.name
            if args.move:
                shutil.move(str(item), str(dest_item))
            elif args.hardlink:
                try:
                    if item.is_dir():
                        shutil.copytree(item, dest_item, dirs_exist_ok=True, copy_function=_hardlink_or_skip)
                    else:
                        _hardlink_or_skip(item, dest_item)
                except OSError as e:
                    if e.errno == errno.EXDEV:
                        sys.exit(
                            f"Hardlinking failed for {item} -> {dest_item}: {e}\n"
                            "This means --target is on a different filesystem/drive than the "
                            "raw source -- hardlinks only work within one filesystem. Use plain copy "
                            "(drop --hardlink) or --move instead."
                        )
                    sys.exit(f"Hardlinking failed for {item} -> {dest_item}: {e}")
            elif item.is_dir():
                shutil.copytree(item, dest_item, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest_item)

    print("\nDone. Next: run generate_load_data_csv.py, then validate_structure.py.")


if __name__ == "__main__":
    main()
