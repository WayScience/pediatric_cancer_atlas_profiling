#!/usr/bin/env python
# coding: utf-8

# # Create LoadData CSVs to use for illumination correction
# 
# In this notebook, we create a LoadData CSV that contains paths to each channel per image set for CellProfiler to process. 
# We can use this LoadData CSV to run illumination correction (IC) pipeline that saves IC functions in `npy` file format and extract image quality metrics.

# ## Import libraries

# In[1]:


import pathlib
import pandas as pd
import re

import sys

sys.path.append("../utils")
import loaddata_utils as ld_utils


# ## Set paths

# In[2]:


# Paths for parameters to make loaddata csv
batch_name = "Round_3_data"
index_directory = pathlib.Path(f"/media/18tbdrive/ALSF_pilot_data/{batch_name}/")
config_dir_path = pathlib.Path("./config_files").absolute()
output_csv_dir = pathlib.Path(f"./loaddata_csvs/{batch_name}")
output_csv_dir.mkdir(parents=True, exist_ok=True)

# Find all 'Images' folders within the directory
images_folders = list(index_directory.rglob("Images"))


# ## Create LoadData CSVs for all data

# In[3]:


# Define the one config path to use
config_path = config_dir_path / "config.yml"

# Find all Plate folders
plate_folders = list(index_directory.glob("Plate *"))

# Build mapping of BR00 IDs to plate number
br00_to_plate = {}

# First parse "All Cell Lines" folders to get BR00 IDs
for plate_folder in plate_folders:
    if "All Cell Lines" in plate_folder.name:
        for subfolder in plate_folder.iterdir():
            if subfolder.is_dir():
                br00_id = subfolder.name.split("__")[0]
                plate_num = plate_folder.name.split()[1]
                br00_to_plate[br00_id] = plate_num

# Now process everything
for plate_folder in plate_folders:
    for subfolder in plate_folder.iterdir():
        if not subfolder.is_dir():
            continue

        br00_id = subfolder.name.split("__")[0]

        if "All Cell Lines" in plate_folder.name:
            # Original run
            plate_name = f"{br00_id}"
        else:
            # Reimaged
            parts = plate_folder.name.split()
            plate_num = parts[1]
            cell_line = (
                " ".join(parts[2:]).replace("Reimage", "").strip().replace(" ", "_")
            )
            plate_name = f"{br00_id}_{cell_line}_Reimage"

        path_to_output_csv = (
            output_csv_dir / f"{plate_name}_loaddata_original.csv"
        ).absolute()

        ld_utils.create_loaddata_csv(
            index_directory=subfolder / "Images",
            config_path=config_path,
            path_to_output=path_to_output_csv,
        )
        print(f"Created LoadData CSV for {plate_name} at {path_to_output_csv}")


# ## Concat the re-imaged data back to their original plate and remove the original poor quality data paths

# ### Collect a list of original CSVs and identify unique plate IDs

# In[4]:


# Step 1: Find all CSV files in the output directory
csv_files = list(output_csv_dir.glob("*.csv"))

# Step 2: Extract unique BR00 IDs from filenames
br00_pattern = re.compile(r"(BR00\d+)")  # Regex to match 'BR00' followed by digits

# Collect all matching BR00 IDs from filenames
br00_ids = {
    br00_pattern.search(csv_file.stem).group(1)
    for csv_file in csv_files
    if br00_pattern.search(csv_file.stem)
}

# Sort BR00 IDs numerically to be consistent in ordering
br00_ids = sorted(
    br00_ids, key=lambda x: int(x[4:])
)  # Convert digits part to integer for numerical sorting

print(f"Found {len(br00_ids)} BR00 IDs: {br00_ids}")


# ### Track/store files and add a metadata column for if a row is re-imaged or not

# In[5]:


# Step 3: Initialize storage to track used files and find proper column order
br00_dataframes = {br_id: [] for br_id in br00_ids}
used_files = set()  # Store filenames used in the process
concat_files = []  # Track new concatenated CSV files

# Load one BR00 starting CSV that will have the correct column order
column_order = pd.read_csv(
    pathlib.Path(f"{output_csv_dir}/{list(br00_ids)[0]}_loaddata_original.csv"), nrows=0
).columns.tolist()

# Step 4: Add 'Metadata_Reimaged' column and group by BR00 ID
for csv_file in csv_files:
    filename = csv_file.stem
    match = br00_pattern.search(filename)

    if match:
        br_id = match.group(1)

        # Read the CSV file into a DataFrame
        loaddata_df = pd.read_csv(csv_file)

        # Reorder DataFrame columns to match the correct column order
        loaddata_df = loaddata_df[
            column_order
        ]  # Ensure the columns are in the correct order

        # Add 'Metadata_Reimaged' column based on filename
        loaddata_df["Metadata_Reimaged"] = any(
            sub in filename for sub in ["Reimage", "Re-imaged", "Reimaged", "Re-image"]
        )

        # Append the DataFrame to the corresponding BR00 group
        br00_dataframes[br_id].append(loaddata_df)

        # Track this file as used
        used_files.add(csv_file.name)

# Print an example DataFrame (first BR00 group)
example_id = next(iter(br00_dataframes))  # Get the first BR00 ID
example_df = pd.concat(br00_dataframes[example_id], ignore_index=True)
print(f"\nExample DataFrame for BR00 ID: {example_id}")
example_df.iloc[:, [0, 1, -1]]  # Display only the first two and last column


# ### Concat the re-imaged and original data for the same plate and remove any duplicate wells that come from the original data
# 
# We remove the duplicates that aren't re-imaged since they are of poor quality. We want to analyze the re-imaged data from those same wells.

# In[6]:


# Step 5: Concatenate DataFrames, drop duplicates, and save per BR00 ID
for br_id, dfs in br00_dataframes.items():
    if dfs:  # Only process if there are matching files
        concatenated_df = pd.concat(dfs, ignore_index=True)

        # Drop duplicates, prioritizing rows with 'Metadata_Reimaged' == True
        deduplicated_df = concatenated_df.sort_values(
            "Metadata_Reimaged", ascending=False
        ).drop_duplicates(subset=["Metadata_Well", "Metadata_Site"], keep="first")

        # Sort by 'Metadata_Col', 'Metadata_Row', and 'Metadata_Site
        sorted_df = deduplicated_df.sort_values(
            ["Metadata_Col", "Metadata_Row", "Metadata_Site"], ascending=True
        )

        # Enforce correct plate ID for all rows
        sorted_df["Metadata_Plate"] = br_id

        # Save the cleaned, concatenated, and sorted DataFrame to a new CSV file
        output_path = output_csv_dir / f"{br_id}_concatenated.csv"
        sorted_df.to_csv(output_path, index=False)

        print(f"Saved: {output_path}")
        concat_files.append(output_path)  # Track new concatenated files
    else:
        print(f"No files found for {br_id}")


# ### Confirm that all LoadData CSV files were included in previous concat (avoid data loss)

# In[7]:


# Step 6: Verify all files were used
unused_files = set(csv_file.name for csv_file in csv_files) - used_files

if unused_files:
    print("Warning: Some files were not used in the concatenation!")
    for file in unused_files:
        print(f"Unused: {file}")
else:
    print("All files were successfully used.")


# ### Remove the original CSV files to prevent CellProfiler from using them

# In[8]:


# Step 7: Remove all non-concatenated CSVs to avoid confusion
for csv_file in csv_files:
    if csv_file not in concat_files:  # Keep only new concatenated files
        csv_file.unlink()  # Delete the file
        print(f"Removed: {csv_file}")

