#!/usr/bin/env python
# coding: utf-8

# # Perform segmentation and feature extraction using CellProfiler

# ## Import libraries

# In[1]:


import argparse
import pathlib
import pprint

import sys

sys.path.append("../utils")
import cp_parallel

# check if in a jupyter notebook
try:
    cfg = get_ipython().config
    in_notebook = True
except NameError:
    in_notebook = False


# ## Set paths and variables

# In[2]:


# set the run type for the parallelization
run_name = "analysis"

# set path for CellProfiler pipeline
path_to_pipeline = pathlib.Path("./analysis.cppipe").resolve(strict=True)

# set main output dir for all plates if it doesn't exist
output_dir = pathlib.Path("./sqlite_outputs")
output_dir.mkdir(exist_ok=True)

# directory where loaddata CSVs are located within the folder
loaddata_dir = pathlib.Path("./loaddata_csvs").resolve(strict=True)

# Extract plate names and include as list
plate_names = [file.stem.split("_")[0] for file in loaddata_dir.glob("*.csv")]

# Print the number of plates and their names
print(f"Total number of plates: {len(plate_names)}")
print("Plate Names:")
for name in plate_names:
    print(name)


# ## Create dictionary to process data

# In[3]:


# create plate info dictionary with all parts of the CellProfiler CLI command to run in parallel
plate_info_dictionary = {
    name: {
        "path_to_loaddata": next(loaddata_dir.glob(f"{name}*.csv"), None),
        "path_to_output": output_dir / name,
        "path_to_pipeline": path_to_pipeline,
    }
    for name in plate_names
    if name == "BR00143976" and next(loaddata_dir.glob(f"{name}*.csv"), None)
}

# view the dictionary to assess that all info is added correctly
pprint.pprint(plate_info_dictionary, indent=4)


# ## Perform segmentation and feature extraction (analysis)
# 
# Note: This code cell was not ran as we prefer to perform CellProfiler processing tasks via `sh` file (bash script) which is more stable.

# In[4]:


cp_parallel.run_cellprofiler_parallel(
    plate_info_dictionary=plate_info_dictionary, run_name=run_name
)

