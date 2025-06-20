#!/usr/bin/env python
# coding: utf-8

# # Process single cell profiles

# ## Import libraries

# In[1]:


import gc
import pathlib
import pprint

import pandas as pd

from pycytominer import annotate, normalize, feature_select
from pycytominer.cyto_utils import output


# ## Set paths and variables

# In[2]:


# Set round of plates to process
round_id = "Round_2_data"

# Path to dir with cleaned data from single-cell QC
cleaned_dir = pathlib.Path(f"./data/cleaned_profiles/{round_id}")

# output path for bulk profiles
output_dir = pathlib.Path(f"./data/single_cell_profiles/{round_id}")
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


# Set up map for renaming metadata column(s)
column_name_mapping = {
    "Image_Metadata_Site": "Metadata_Site",
}

for plate, info in plate_info_dictionary.items():
    print(f"Performing pycytominer pipeline for {plate}")

    # Set output paths
    output_annotated_file = str(
        pathlib.Path(f"{output_dir}/{plate}_sc_annotated.parquet")
    )
    output_normalized_file = str(
        pathlib.Path(f"{output_dir}/{plate}_sc_normalized.parquet")
    )
    output_feature_select_file = str(
        pathlib.Path(f"{output_dir}/{plate}_sc_feature_selected.parquet")
    )

    # Load in profile and platemap
    profile_df = pd.read_parquet(info["profile_path"])
    platemap_df = pd.read_csv(info["platemap_path"])

    print("Performing annotation for", plate, "...")
    # Step 1: Annotation
    annotated_df = annotate(
        profiles=profile_df,
        platemap=platemap_df,
        join_on=["Metadata_well", "Image_Metadata_Well"],
    )

    # Add 'Metadata_time_point' column based on the plate's time_point from dict
    annotated_df["Metadata_time_point"] = info["time_point"]

    # Rename Metadata column(s) using the rename() function
    annotated_df.rename(columns=column_name_mapping, inplace=True)

    # Save the modified annotated DataFrame
    output(
        df=annotated_df,
        output_filename=output_annotated_file,
        output_type="parquet",
    )

    # Clear memory
    del profile_df, platemap_df, annotated_df
    gc.collect()

    print("Performing normalization for", plate, "...")
    # Step 2: Normalization
    normalized_df = normalize(
        profiles=output_annotated_file,
        method="standardize",
        output_file=output_normalized_file,
        output_type="parquet",
    )

    # Clear memory
    del normalized_df
    gc.collect()

    print("Performing feature selection for", plate, "...")
    # Step 3: Feature selection
    feature_select(
        profiles=output_normalized_file,
        operation=feature_select_ops,
        na_cutoff=0,
        output_file=output_feature_select_file,
        output_type="parquet",
    )

    # Clear memory
    gc.collect()

    print(f"Preprocessing features completed for {plate}!")


# In[5]:


# Check output file
test_df = pd.read_parquet(output_feature_select_file)

print(test_df.shape)
test_df.head(2)

