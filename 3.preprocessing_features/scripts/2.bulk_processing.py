#!/usr/bin/env python
# coding: utf-8

# # Process bulk profiles

# ## Import libraries

# In[1]:


import pathlib
import pprint

import pandas as pd

from pycytominer import aggregate, annotate, normalize, feature_select
from pycytominer.cyto_utils import output


# ## Set paths and variables

# In[2]:


# Condition for how to normalize the plates
normalize_with_U2OS = (
    True  # Set to False if normalizing to whole plate versus just U2OS cell line
)

# Path to dir with cleaned data from single-cell QC
cleaned_dir = pathlib.Path("./data/cleaned_profiles")

# output path for bulk profiles
output_dir = pathlib.Path("./data/bulk_profiles")
output_dir.mkdir(parents=True, exist_ok=True)

# extract the plate names from the file name
plate_names = [file.stem.split("_")[0] for file in cleaned_dir.glob("*.parquet")]

# path for platemap directory
platemap_dir = pathlib.Path("../0.download_data/metadata/platemaps")

# load in barcode platemap
barcode_platemap = pd.read_csv(
    pathlib.Path(f"{platemap_dir}/Barcode_platemap_pilot_data.csv")
)

# operations to perform for feature selection
feature_select_ops = [
    "variance_threshold",
    "correlation_threshold",
    "blocklist",
    "drop_na_columns",
]

plate_names


# ## Set dictionary with plates to process

# In[3]:


# create plate info dictionary
plate_info_dictionary = {
    name: {
        "profile_path": (
            str(
                pathlib.Path(
                    list(cleaned_dir.rglob(f"{name}_cleaned.parquet"))[0]
                ).resolve(strict=True)
            )
            if list(cleaned_dir.rglob(f"{name}_cleaned.parquet"))
            else None
        ),
        # Find the platemap file based on barcode match and append .csv
        "platemap_path": (
            str(
                pathlib.Path(
                    list(
                        platemap_dir.rglob(
                            f"{barcode_platemap.loc[barcode_platemap['barcode'] == name, 'platemap_file'].values[0]}.csv"
                        )
                    )[0]
                ).resolve(strict=True)
            )
            if name in barcode_platemap["barcode"].values
            else None
        ),
        # Get the time_point based on the barcode match
        "time_point": (
            barcode_platemap.loc[
                barcode_platemap["barcode"] == name, "time_point"
            ].values[0]
            if name in barcode_platemap["barcode"].values
            else None
        ),
    }
    for name in plate_names
}

# Display the dictionary to verify the entries
pprint.pprint(plate_info_dictionary, indent=4)


# ## Process data with pycytominer

# In[4]:


# Determine suffix based on normalize_with_U2OS
u2os_suffix = "_U2OS_samples" if normalize_with_U2OS else ""

# If normalizing with U2OS, create a subfolder named 'U2OS_samples'
if normalize_with_U2OS:
    U2OS_output_dir = output_dir / "U2OS_samples"
    U2OS_output_dir.mkdir(exist_ok=True)
else:
    U2OS_output_dir = (
        output_dir  # Otherwise, use the root output_dir for whole plate normalization
    )

for plate, info in plate_info_dictionary.items():
    print(f"Now performing pycytominer pipeline for {plate}")

    # Output file paths for each file
    output_aggregated_file = str(pathlib.Path(f"{output_dir}/{plate}_bulk.parquet"))
    output_annotated_file = str(
        pathlib.Path(f"{output_dir}/{plate}_bulk_annotated.parquet")
    )

    # Save normalized and feature-selected files in U2OS_samples folder if needed
    output_normalized_file = str(
        pathlib.Path(f"{U2OS_output_dir}/{plate}_bulk_normalized{u2os_suffix}.parquet")
    )
    output_feature_select_file = str(
        pathlib.Path(
            f"{U2OS_output_dir}/{plate}_bulk_feature_selected{u2os_suffix}.parquet"
        )
    )

    # Load single-cell profiles
    single_cell_df = pd.read_parquet(info["profile_path"])

    # Load platemap
    platemap_df = pd.read_csv(info["platemap_path"])

    # Step 1: Aggregation
    aggregate(
        population_df=single_cell_df,
        operation="median",
        strata=["Image_Metadata_Plate", "Image_Metadata_Well"],
        output_file=output_aggregated_file,
        output_type="parquet",
    )

    # Step 2: Annotation
    annotated_df = annotate(
        profiles=output_aggregated_file,
        platemap=platemap_df,
        join_on=["Metadata_well", "Image_Metadata_Well"],
    )

    # Step 2.5: Add 'Metadata_time_point' column based on the plate's time_point from dict
    annotated_df["Metadata_time_point"] = info["time_point"]

    # Step 3: Output annotated DataFrame
    output(
        df=annotated_df,
        output_filename=output_annotated_file,
        output_type="parquet",
    )

    # Step 4: Normalization
    samples = (
        "Metadata_cell_line == 'U2-OS'" if normalize_with_U2OS else "all"
    )  # "all" is the default to perform on whole plate
    print(f"Normalizing using samples: {samples}")

    normalize(
        profiles=annotated_df,
        method="standardize",
        output_file=output_normalized_file,
        output_type="parquet",
        samples=samples,
    )

    # Step 5: Feature selection
    feature_select(
        output_normalized_file,
        operation=feature_select_ops,
        na_cutoff=0,
        output_file=output_feature_select_file,
        output_type="parquet",
    )


# In[5]:


# Check output file
test_df = pd.read_parquet(output_feature_select_file)

print(test_df.shape)
test_df.head(2)

