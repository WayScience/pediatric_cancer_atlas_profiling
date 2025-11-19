#!/usr/bin/env python
# coding: utf-8

# # Convert SQLite outputs to parquet files with cytotable

# In[1]:


# Set parameter for papermill to use for processing
plate_id = "BR00145816"


# In[2]:


# Parameters
plate_id = "BR00148746"


# ## Import libraries

# In[3]:


import pathlib
import pandas as pd

# cytotable will merge objects from SQLite file into single cells and save as parquet file
from cytotable import convert, presets

import logging

# Set the logging level to a higher level to avoid outputting unnecessary errors from config file in convert function
logging.getLogger().setLevel(logging.ERROR)


# ## Set paths and variables

# In[4]:


# preset configurations based on typical CellProfiler outputs
preset = "cellprofiler_sqlite_pycytominer"

# update preset to include both the site metadata, cell counts, and PathName columns
joins = presets.config["cellprofiler_sqlite_pycytominer"]["CONFIG_JOINS"].replace(
    "Image_Metadata_Well,",
    "Image_Metadata_Well, Image_Metadata_Site, Image_Count_Cells, Image_Metadata_Row, Image_Metadata_Col, ",
)

# Add the PathName columns separately
joins = joins.replace(
    "COLUMNS('Image_FileName_.*'),",
    "COLUMNS('Image_FileName_.*'),\n COLUMNS('Image_PathName_.*'),",
)

# type of file output from cytotable (currently only parquet)
dest_datatype = "parquet"

# set the round of data that will be processed
round_id = "Round_4_data"

# set path to directory with SQLite files
sqlite_dir = pathlib.Path(f"../2.feature_extraction/sqlite_outputs/{round_id}")

# directory for processed data
output_dir = pathlib.Path("data")
output_dir.mkdir(parents=True, exist_ok=True)

plate_names = []

for file_path in sqlite_dir.iterdir():
    plate_names.append(file_path.stem)

# print the plate names and how many plates there are (confirmation)
print(f"There are {len(plate_names)} plates in this dataset. Below are the names:")
for name in plate_names:
    print(name)


# ## Convert SQLite to parquet files

# In[5]:


file_path = sqlite_dir / plate_id
output_path = pathlib.Path(
    f"{output_dir}/converted_profiles/{round_id}/{plate_id}_converted.parquet"
)

print("Starting conversion with cytotable for plate:", plate_id)
# Merge single cells and output as parquet file
convert(
    source_path=str(file_path),
    dest_path=str(output_path),
    dest_datatype=dest_datatype,
    preset=preset,
    joins=joins,
    chunk_size=15000,
)

print(f"Plate {plate_id} has been converted with cytotable!")


# # Load in converted profiles to update

# In[6]:


# Directory with converted profiles
converted_dir = pathlib.Path(f"{output_dir}/converted_profiles/{round_id}")

# Define the list of columns to prioritize and prefix
prioritized_columns = [
    "Nuclei_Location_Center_X",
    "Nuclei_Location_Center_Y",
    "Cells_Location_Center_X",
    "Cells_Location_Center_Y",
    "Image_Count_Cells",
]

# Load the DataFrame from the Parquet file
file_path = converted_dir / f"{plate_id}_converted.parquet"
converted_df = pd.read_parquet(file_path)

# If any, drop rows where "Metadata_ImageNumber" is NaN (artifact of cytotable)
converted_df = converted_df.dropna(subset=["Metadata_ImageNumber"])

# Rearrange columns and add "Metadata" prefix in one line
converted_df = converted_df[
    prioritized_columns
    + [col for col in converted_df.columns if col not in prioritized_columns]
].rename(columns=lambda col: "Metadata_" + col if col in prioritized_columns else col)

# assert that there are column names with PathName in the dataset
assert any("PathName" in col for col in converted_df.columns)

# Assert that Metadata_Row and Metadata_Col are present for downstream QC
assert {"Image_Metadata_Row", "Image_Metadata_Col"}.issubset(
    converted_df.columns
), "Missing required Metadata columns: Row and/or Col"

# Save the processed DataFrame as Parquet in the same path
converted_df.to_parquet(file_path, index=False)

# print shape and head of dataset
print(converted_df.shape)
converted_df.head()


# **To confirm the number of single cells is correct above, please use any database browser software to see if the number of rows in the "Per_Cells" compartment matches the number of rows in the data frame.**
