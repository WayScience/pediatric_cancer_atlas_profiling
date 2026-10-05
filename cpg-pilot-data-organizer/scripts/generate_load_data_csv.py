#!/usr/bin/env python3
"""
Generate a CPG-compliant load_data.csv for one already-reorganized plate
folder, by parsing Opera Phenix / Harmony style filenames
(e.g. r01c01f01p01-ch1sk1fk1fl1.tiff).

This is intentionally scoped to ONE plate at a time (images/<batch>/images/
<full-plate-name>/) rather than trying to walk the whole dataset, so you can
spot-check each plate's CSV before moving on -- and so a filename-pattern
mismatch on one weird plate doesn't block the rest.

If your images don't follow the Opera Phenix pattern in cpg_lib.py
(OPERA_PHENIX_FILENAME_RE), that regex is the one place to adjust -- everything
downstream (well/site/channel extraction) flows from it.

Usage:
    python generate_load_data_csv.py \\
        --plate-dir /path/to/local/cpg0041-pccma/alexslemonade/images/Round2_Plate3_A673_Reimage/images/BR00143976__2024-07-04T16_04_45-Measurement2 \\
        --plate-name BR00143976 \\
        --s3-prefix s3://cellpainting-gallery/cpg0041-pccma/alexslemonade/images/Round2_Plate3_A673_Reimage/images/BR00143976__2024-07-04T16_04_45-Measurement2 \\
        --channel-map 1=OrigDNA --channel-map 2=OrigER --channel-map 3=OrigMito \\
        --out load_data.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

from cpg_lib import parse_opera_phenix_filename


def parse_channel_map(pairs: list[str]) -> dict[str, str]:
    mapping = {}
    for pair in pairs:
        if "=" not in pair:
            sys.exit(f"--channel-map entries must look like 1=OrigDNA (got {pair!r})")
        ch, name = pair.split("=", 1)
        mapping[ch.strip()] = name.strip()
    return mapping


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plate-dir", type=Path, required=True, help="Local folder containing this plate's image files")
    ap.add_argument("--plate-name", required=True, help="Short <plate-name>, e.g. BR00143976")
    ap.add_argument(
        "--s3-prefix",
        required=True,
        help="s3://cellpainting-gallery/... prefix this plate's images will live "
        "under in production (used to build URL_<Channel> values even before "
        "the data is actually public)",
    )
    ap.add_argument(
        "--channel-map",
        action="append",
        default=[],
        metavar="N=NAME",
        help="Map a channel number to a stain name, e.g. 1=OrigDNA. Repeat for each channel. "
        "Required -- CPG load_data_csv columns must be named URL_<ChannelName>, not URL_ch1.",
    )
    ap.add_argument("--out", type=Path, required=True, help="Output CSV path")
    args = ap.parse_args()

    if not args.channel_map:
        sys.exit("At least one --channel-map N=NAME is required (see --help).")
    channel_map = parse_channel_map(args.channel_map)

    if not args.plate_dir.is_dir():
        sys.exit(f"--plate-dir {args.plate_dir} does not exist or is not a directory")

    # rows[(well, site)][channel_name] = url
    rows: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    unmatched = []
    unmapped_channels = set()

    # Search recursively, not just the top level: real Harmony/Opera Phenix
    # exports nest the actual tiffs one level down inside an "Images/"
    # subfolder (alongside instrument metadata folders like "Assaylayout"
    # and "FFC_Profile"), rather than putting them directly in the
    # Measurement folder. Skip those non-image folders' contents by only
    # matching the expected filename pattern -- Assaylayout/FFC_Profile
    # files won't match it and land in `unmatched` instead, which is fine.
    for f in sorted(args.plate_dir.rglob("*")):
        if not f.is_file():
            continue
        parsed = parse_opera_phenix_filename(f)
        if parsed is None:
            unmatched.append(str(f.relative_to(args.plate_dir)))
            continue
        channel_name = channel_map.get(parsed.channel)
        if channel_name is None:
            unmapped_channels.add(parsed.channel)
            continue
        # Preserve the file's path relative to the plate folder (e.g. the
        # "Images/" prefix) in the URL, since reorganize.py copies the raw
        # plate folder's internal structure through unchanged.
        rel_path = f.relative_to(args.plate_dir).as_posix()
        url = f"{args.s3_prefix.rstrip('/')}/{rel_path}"
        rows[(parsed.well, parsed.site)][f"URL_{channel_name}"] = url

    if unmatched:
        print(f"Warning: {len(unmatched)} file(s) didn't match the expected Opera Phenix "
              f"filename pattern and were skipped, e.g.: {unmatched[:5]}", file=sys.stderr)
    if unmapped_channels:
        sys.exit(
            f"Found channel number(s) {sorted(unmapped_channels)} with no --channel-map entry. "
            "Add a --channel-map for each, e.g. --channel-map 4=OrigAGP"
        )
    if not rows:
        sys.exit("No matching image files found -- nothing to write.")

    channel_columns = sorted({col for cols in rows.values() for col in cols})
    fieldnames = ["Metadata_Plate", "Metadata_Well", "Metadata_Site"] + channel_columns

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for (well, site), cols in sorted(rows.items()):
            row = {"Metadata_Plate": args.plate_name, "Metadata_Well": well, "Metadata_Site": site}
            row.update(cols)
            writer.writerow(row)

    print(f"Wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
