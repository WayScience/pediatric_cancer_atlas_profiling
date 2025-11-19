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

# In[ ]:


# Set round to be processed
round_id = "Round_4_data"

# Path to dir with cleaned data from single-cell QC
cleaned_dir = pathlib.Path(f"./data/cleaned_profiles/{round_id}")

# output path for bulk profiles
output_dir = pathlib.Path(f"./data/bulk_profiles/{round_id}")
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

# In[ ]:


# Process plates with pycytominer (U2-OS specific normalization removed)
for plate, info in plate_info_dictionary.items():
    print(f"Now performing pycytominer pipeline for {plate}")

    # Output file paths for each file
    output_aggregated_file = str(pathlib.Path(f"{output_dir}/{plate}_bulk.parquet"))
    output_annotated_file = str(
        pathlib.Path(f"{output_dir}/{plate}_bulk_annotated.parquet")
    )

    # Normalized and feature-selected files (whole-plate normalization)
    output_normalized_file = str(
        pathlib.Path(f"{output_dir}/{plate}_bulk_normalized.parquet")
    )
    output_feature_select_file = str(
        pathlib.Path(f"{output_dir}/{plate}_bulk_feature_selected.parquet")
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

    # Add 'Metadata_time_point' column based on the plate's time_point from dict
    annotated_df["Metadata_time_point"] = info["time_point"]

    # Step 3: Output annotated DataFrame
    output(
        df=annotated_df,
        output_filename=output_annotated_file,
        output_type="parquet",
    )

    # Step 4: Normalization (always whole-plate)
    samples = "all"
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

