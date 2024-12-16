#!/usr/bin/env python
# coding: utf-8

# In[15]:


import pathlib
import sys

import pandas as pd


# In[16]:


from comparators.PearsonsCorrelation import PearsonsCorrelation
from comparison_tools.PairwiseCompareManager import PairwiseCompareManager


# In[17]:


# output path for bulk profiles
output_dir = pathlib.Path("../3.preprocessing_features/data/bulk_profiles")
output_dir.mkdir(parents=True, exist_ok=True)

# extract the plate names from the file name
plate_names = [file.stem.split("_")[0] for file in output_dir.glob("*.parquet")]

for plate in plate_names:
    output_feature_select_file = str(
            pathlib.Path(f"{output_dir}/{plate}_bulk_feature_selected.parquet")
        )
    print(output_feature_select_file)


# In[18]:


results = []

for plate in plate_names:
    output_feature_select_file = str(
            pathlib.Path(f"{output_dir}/{plate}_bulk_feature_selected.parquet")
        )
    plate_df = pd.read_parquet(output_feature_select_file)
    feat_cols = plate_df.columns[~plate_df.columns.str.contains("Metadata")].tolist()

    pearsons_comparator = PearsonsCorrelation()

    comparer = PairwiseCompareManager(
        _df=plate_df.copy(),
        _comparator=pearsons_comparator,
        _same_columns=["Metadata_cell_line", "Metadata_seeding_density", "Metadata_time_point"],
        _different_columns=["Metadata_Well"],
        _feat_cols=feat_cols,
        _drop_cols=["Metadata_Concentration", "Metadata_Well"],
    )

    micdf = comparer()
    results.append(micdf)


# In[26]:


# Combine all results into a single dataframe
combined_df = pd.concat(results, ignore_index=True)


# In[ ]:


best_results = (
    combined_df.loc[
        combined_df.groupby("Metadata_cell_line__antehoc_group0")["pearsons_correlation"].idxmax(),
        [
            "Metadata_cell_line__antehoc_group0", 
            "Metadata_seeding_density__antehoc_group0", 
            "Metadata_time_point__antehoc_group0", 
            "pearsons_correlation"
        ]
    ]
)
best_results.head(50)


# In[27]:


worst_results = (
    combined_df.loc[
        combined_df.groupby("Metadata_cell_line__antehoc_group0")["pearsons_correlation"].idxmin(),
        [
            "Metadata_cell_line__antehoc_group0", 
            "Metadata_seeding_density__antehoc_group0", 
            "Metadata_time_point__antehoc_group0", 
            "pearsons_correlation"
        ]
    ]
)
worst_results.head(50)

