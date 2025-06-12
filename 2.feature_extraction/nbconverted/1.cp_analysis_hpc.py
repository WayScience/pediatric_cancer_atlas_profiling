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


# Batch name to process
batch_name = "Round_1_data"

#  directory where loaddata CSVs are located within the folder
loaddata_dir = pathlib.Path(f"./loaddata_csvs/{batch_name}").resolve(strict=True)

if not in_notebook:
    print("Running as script")
    # set up arg parser
    parser = argparse.ArgumentParser(
        description="CellProfiler segmentation and feature extraction"
    )

    parser.add_argument(
        "--input_csv",
        type=str,
        help="Path to the LoadData CSV file to process images",
    )

    args = parser.parse_args()
    loaddata_csv = pathlib.Path(args.input_csv).resolve(strict=True)
else:
    print("Running in a notebook")
    loaddata_csv = pathlib.Path(
        f"{loaddata_dir}/BR00143976_concatenated_with_illum.csv"
    )

# set the run type for the parallelization
run_name = "analysis"

# set path for CellProfiler pipeline
path_to_pipeline = pathlib.Path("./analysis.cppipe").resolve(strict=True)

# set main output dir for all plates if it doesn't exist
output_dir = pathlib.Path("./sqlite_outputs")
output_dir.mkdir(exist_ok=True)


# ## Create dictionary to process data

# In[3]:


# Extract name from LoadData CSV path
name = loaddata_csv.stem.split("_")[0]

# create plate info dictionary with all parts of the CellProfiler CLI command to run in parallel
plate_info_dictionary = {
    name: {
        "path_to_loaddata": loaddata_csv,
        "path_to_output": output_dir / name,
        "path_to_pipeline": path_to_pipeline,
    }
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

