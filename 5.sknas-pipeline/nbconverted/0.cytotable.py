#!/usr/bin/env python

import pathlib
import cytotable
from ome_arrow import OMEArrow

# Set paths
source_path = (pathlib.Path("~/mnt/bandicoot")
               .expanduser()
               .resolve()
               / "PCCMA_data"
               / "SK-N-AS_repo1_screen")


# Convert CSVs into Iceberg warehouse
warehouse_path = cytotable.convert(
    source_path=source_path,
    source_datatype="csv",
    dest_path="/scratch/alpine/$USER/sknas_warehouse",
    dest_backend="iceberg",
    dest_datatype="parquet",
    preset="cellprofiler_csv",
    outline_dir="./outlines",
)

print("Warehouse created:")
print(warehouse_path)

# List tables
print("\nTables:")
print(cytotable.list_tables(warehouse_path))

# Read tables
joined_profiles = cytotable.read_table(
    warehouse_path,
    "joined_profiles"
)

print("\nJoined profiles:")
print(joined_profiles[["Metadata_ObjectID"]].head())

image_crops = cytotable.read_table(
    warehouse_path,
    "image_crops"
)

print("\nImage crops:")
print(
    image_crops[
        [
            "Metadata_ObjectID",
            "Metadata_ImageCropID",
            "source_image_file",
        ]
    ].head()
)

source_images = cytotable.read_table(
    warehouse_path,
    "source_images"
)

print("\nSource images:")
print(
    source_images[
        [
            "Metadata_ImageID",
            "source_image_file",
        ]
    ].head()
)

profile_with_images = cytotable.read_table(
    warehouse_path,
    "profile_with_images"
)

print("\nProfile with images:")
print(
    profile_with_images[
        ["Metadata_ObjectID", "source_image_file"]
    ].head()
)