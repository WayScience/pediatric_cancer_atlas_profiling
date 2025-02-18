#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pathlib
import numpy as np
import pandas as pd


# In[2]:


from comparators.PearsonsCorrelation import PearsonsCorrelation
from comparison_tools.PairwiseCompareManager import PairwiseCompareManager


# In[3]:


# output path for bulk profiles
output_dir = pathlib.Path("../3.preprocessing_features/data/bulk_profiles")
output_dir.mkdir(parents=True, exist_ok=True)

# extract the plate names from the file name
plate_names = set([file.stem.split("_")[0] for file in output_dir.glob("*.parquet")])

for plate in plate_names:
    output_feature_select_file = str(
            pathlib.Path(f"{output_dir}/{plate}_bulk_feature_selected.parquet")
        )
    print(output_feature_select_file)


# In[4]:


combined_results = []

for plate in plate_names:
    output_feature_select_file = str(
        pathlib.Path(f"{output_dir}/{plate}_bulk_feature_selected.parquet")
    )
    plate_df = pd.read_parquet(output_feature_select_file)
    feat_cols = plate_df.columns[~plate_df.columns.str.contains("Metadata")].tolist()
    
    # Create a shuffled copy of the data
    shuffled_plate_df = plate_df.copy()
    unique_time_points = plate_df["Metadata_time_point"].unique()

    # Shuffle feature columns within each time point
    for time_point in unique_time_points:
        mask = plate_df["Metadata_time_point"] == time_point
        for col in feat_cols:
            shuffled_plate_df.loc[mask, col] = (
                plate_df.loc[mask, col]
                .sample(frac=1, random_state=42)  # Add `random_state` for reproducibility
                .values
            )

    # Add a column to indicate shuffled/unshuffled
    plate_df["Shuffled"] = "False"
    shuffled_plate_df["Shuffled"] = "True"

    # Include Metadata_seeding_density in both datasets
    plate_df["Metadata_seeding_density"] = plate_df["Metadata_seeding_density"]
    shuffled_plate_df["Metadata_seeding_density"] = shuffled_plate_df["Metadata_seeding_density"]

    # Combine original and shuffled data
    combined_plate_df = pd.concat([plate_df, shuffled_plate_df], ignore_index=True)
    
    # Perform pairwise comparison on the combined data
    pearsons_comparator = PearsonsCorrelation()

    comparer = PairwiseCompareManager(
        _df=combined_plate_df.copy(),
        _comparator=pearsons_comparator,
        _same_columns=["Metadata_cell_line", "Metadata_seeding_density", "Metadata_time_point", "Shuffled"],
        _different_columns=["Metadata_Well"],
        _feat_cols=feat_cols,
        _drop_cols=["Metadata_Concentration", "Metadata_Well"],
    )

    micdf = comparer()
    combined_results.append(micdf)

# Combine all results into a single dataframe
final_combined_df = pd.concat(combined_results, axis=0)


# In[5]:


#Save dataframe
save_dir = pathlib.Path("./results/pairwise_compare.parquet")
final_combined_df.to_parquet(save_dir)


# In[6]:


avg_results = (
    final_combined_df.groupby(
        ["Metadata_cell_line__antehoc_group0", 
         "Metadata_seeding_density__antehoc_group0", 
         "Metadata_time_point__antehoc_group0",
         "Shuffled__antehoc_group0"
         ]
    )["pearsons_correlation"]
    .mean()
    .reset_index()
)

top_avg_results = (
    avg_results.loc[
        avg_results.groupby("Metadata_cell_line__antehoc_group0")["pearsons_correlation"].idxmax(),
        [
            "Metadata_cell_line__antehoc_group0", 
            "Metadata_seeding_density__antehoc_group0", 
            "Metadata_time_point__antehoc_group0", 
            "pearsons_correlation",
            "Shuffled__antehoc_group0"
        ]
    ]
)
print(top_avg_results)

# Step 2: Separate unshuffled and shuffled averages
unshuffled_avg = avg_results[avg_results["Shuffled__antehoc_group0"] == "False"]
shuffled_avg = avg_results[avg_results["Shuffled__antehoc_group0"] == "True"]

# Step 3: Merge the data to calculate the difference
difference_df = pd.merge(
    unshuffled_avg,
    shuffled_avg,
    on=[
        "Metadata_cell_line__antehoc_group0", 
        "Metadata_seeding_density__antehoc_group0", 
        "Metadata_time_point__antehoc_group0"
    ],
    suffixes=("_unshuffled", "_shuffled")
)

difference_df["correlation_difference"] = (
    difference_df["pearsons_correlation_unshuffled"] - 
    difference_df["pearsons_correlation_shuffled"]
)

# Step 4: Identify the top results by the largest difference
top_difference_results = (
    difference_df.groupby("Metadata_cell_line__antehoc_group0")
    .apply(lambda group: group.nlargest(1, "correlation_difference"))
    .reset_index(drop=True)
)

# Select relevant columns to display
top_difference_results = top_difference_results[
    [
        "Metadata_cell_line__antehoc_group0", 
        "Metadata_seeding_density__antehoc_group0", 
        "Metadata_time_point__antehoc_group0", 
        "correlation_difference"
    ]
]

# Display the results
top_difference_results.head(18)


# In[7]:


controlled_results = []

for plate in plate_names:
    output_feature_select_file = str(
        pathlib.Path(f"{output_dir}/{plate}_bulk_feature_selected.parquet")
    )
    plate_df = pd.read_parquet(output_feature_select_file)
    feat_cols = plate_df.columns[~plate_df.columns.str.contains("Metadata")].tolist()

    # Include Metadata_seeding_density in both datasets
    plate_df["Metadata_seeding_density"] = plate_df["Metadata_seeding_density"]

    # Define the control cell line
    control_cell_line = "U2OS"

    # Get unique cell lines excluding the control
    cell_lines = plate_df["Metadata_cell_line"].unique()
    cell_lines = [cl for cl in cell_lines if cl != control_cell_line]

    for cell_line in cell_lines:

        # Subset data for the target cell line and U2OS
        subset_df = plate_df[plate_df["Metadata_cell_line"].isin([cell_line, control_cell_line])]
        # Perform pairwise comparison on the combined data
        pearsons_comparator = PearsonsCorrelation()

        comparer = PairwiseCompareManager(
            _df=subset_df.copy(),
            _comparator=pearsons_comparator,
            _same_columns=[],
            _different_columns=["Metadata_cell_line", "Metadata_seeding_density", "Metadata_time_point", "Metadata_Well"],
            _feat_cols=feat_cols,
            _drop_cols=["Metadata_Concentration", "Metadata_Well"],
        )

        micdf = comparer()
        controlled_results.append(micdf)

# Combine all results into a single dataframe
final_control_df = pd.concat(controlled_results, axis=0)


# In[8]:


final_control_df.head()

