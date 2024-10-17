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
index_directory = pathlib.Path("/media/18tbdrive/ALSF_pilot_data/SN0313537/")
config_path = pathlib.Path("./config.yml").absolute()
output_csv_dir = pathlib.Path("./loaddata_csvs")
output_csv_dir.mkdir(parents=True, exist_ok=True)

# Find all 'Images' folders within the directory
images_folders = list(index_directory.rglob('Images'))


# ## Create LoadData CSVs for all data

# In[3]:


# Loop through each folder and create a LoadData CSV
for folder in images_folders:
    # Get the first folder directly under the index_directory
    relative_path = folder.relative_to(index_directory)
    first_folder = relative_path.parts[0]  # First-level folder

    # Generate the plate name based on folder structure
    if first_folder.startswith('BR00'):
        plate_name = first_folder.split('_')[0]  # Take the first part

    elif first_folder.startswith('2024'):
        second_folder = relative_path.parts[1]  # Second-level folder
        part1 = '_'.join(first_folder.split('_')[-2:])  # Last two parts of first folder
        part2 = second_folder.split('_')[0]  # First part of second folder
        plate_name = f"{part1}_{part2}"  # Combine them

    else:
        print(f"Unexpected folder pattern: {folder}")
        continue  # Skip if not matching patterns

    # Create LoadData output path per plate
    path_to_output_csv = (output_csv_dir / f"{plate_name}_loaddata_original.csv").absolute()

    # Call the function to create the LoadData CSV
    ld_utils.create_loaddata_csv(
        index_directory=folder,
        config_path=config_path,
        path_to_output=path_to_output_csv,
    )


# ## Concat the re-imaged data back to their original plate and remove the original poor quality data paths

# ### Collect a list of original CSVs and identify unique plate IDs

# In[4]:


# Step 1: Find all CSV files in the output directory
csv_files = list(output_csv_dir.glob("*.csv"))

# Step 2: Extract unique BR00 IDs from filenames
br00_pattern = re.compile(r"(BR00\d+)")  # Regex to match 'BR00' followed by digits

# Collect all matching BR00 IDs from filenames
br00_ids = {br00_pattern.search(csv_file.stem).group(1) 
            for csv_file in csv_files 
            if br00_pattern.search(csv_file.stem)}

print(f"Found {len(br00_ids)} BR00 IDs: {br00_ids}")


# ### Track/store files and add a metadata column for if a row is re-imaged or not

# In[5]:


# Step 3: Initialize storage to track used files
br00_dataframes = {br_id: [] for br_id in br00_ids}
used_files = set()  # Store filenames used in the process
concat_files = []  # Track new concatenated CSV files

# Step 4: Add 'Metadata_Reimaged' column and group by BR00 ID
for csv_file in csv_files:
    filename = csv_file.stem
    match = br00_pattern.search(filename)

    if match:
        br_id = match.group(1)

        # Read the CSV file into a DataFrame
        df = pd.read_csv(csv_file)

        # Add 'Metadata_Reimaged' column based on filename
        df['Metadata_Reimaged'] = 'Re-imaged' in filename

        # Append the DataFrame to the corresponding BR00 group
        br00_dataframes[br_id].append(df)

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
            'Metadata_Reimaged', ascending=False
        ).drop_duplicates(subset=['Metadata_Well', 'Metadata_Site'], keep='first')

        # Save the cleaned and concatenated DataFrame to a new CSV file
        output_path = output_csv_dir / f"{br_id}_concatenated.csv"
        deduplicated_df.to_csv(output_path, index=False)

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

