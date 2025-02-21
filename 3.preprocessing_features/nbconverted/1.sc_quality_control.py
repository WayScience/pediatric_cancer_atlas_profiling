#!/usr/bin/env python
# coding: utf-8

# # Perform single-cell quality control
# 
# In this notebook, we perform single-cell quality control using coSMicQC. We filter the single cells by identifying outliers with z-scores, and use either combinations of features or one feature for each condition. We use features from the AreaShape and Intensity modules to assess the quality of the segmented single-cells:
# 
# ### Assessing poor nuclei segmentation
# 
# Due to high confluence with various seeding densities, sometimes nuclei overlap on top of each other, creating highly intense clusters within the Hoechst channel. To identify these nuclei, we use:
# 
# - **Nuclei Area:** This metric quantifies the number of pixels in a nucleus segmentation. 
# We detect nuclei that are abnormally large, which likely indicates poor nucleus segmentation where overlapping nuclei are merged into one segmentation. 
# - **Nuclei Intensity:** This metric quantifies the total intensity of all pixels in a nucleus segmentation. 
# In combination with abnormally large nuclei, we detect nuclei that are also highly intense, likely indicating that this a group of overlapped nuclei.
# 
# For the preliminary dataset, we are working with cells that have not been treated so we do not expect any crazy phenotypes. Given that context, we can use a feature called Solidity. From ChatGPT, the simple explanation is that this features compares the area of the object to its convex hull, which measures compactness in relation to convexity. High solidity implies few indentations, while lower solidity indicates more irregularity.
# 
# - **Nuclei Solidity:** This metric quantifies the compactness of the nuclei shape.
# When a nuclei is mis-segmented, we see more protrusions or harsh outlines around the segmentations, which we expect this is what this feature will detect.

# In[1]:


import dask.dataframe as dd
import pathlib
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

import time

from cosmicqc import find_outliers


# # Set functions for plotting

# ### Function to plot scatterplot

# In[2]:


def plot_large_nuclei_outliers(
    plate_df: pd.DataFrame,
    outliers_df: pd.DataFrame,
    plate_name: str,
    qc_fig_dir: pathlib.Path,
) -> None:
    """Plot scatterplot of the large nuclei outliers.

    Args:
        plate_df (pd.DataFrame): Dataframe of the CytoTable output with the morphology profiles.
        outliers_df (pd.DataFrame): Dataframe of the coSMicQC output which includes the identified outliers.
        plate_name (str): String of the plate's name or ID.
        qc_fig_dir (pathlib.Path): Path to the directory to save the plot.
    """
    # Create a copy of plate_df to avoid modifying the original
    plate_df = plate_df.copy()

    # Set the default 'Outlier_Status' to 'Single-cell passed QC'
    plate_df["Outlier_Status"] = "Single-cell passed QC"

    # Update 'Outlier_Status' for cells that failed QC
    plate_df.loc[plate_df.index.isin(outliers_df.index), "Outlier_Status"] = (
        "Single-cell failed QC"
    )

    # Create scatter plot
    plt.figure(figsize=(10, 6))
    sns.scatterplot(
        data=plate_df,
        x="Nuclei_AreaShape_Area",
        y="Nuclei_Intensity_IntegratedIntensity_CorrDNA",
        hue="Outlier_Status",
        palette={
            "Single-cell passed QC": "#006400",
            "Single-cell failed QC": "#990090",
        },
        alpha=0.2,
    )

    # Add threshold lines
    plt.axvline(
        x=outliers_df["Nuclei_AreaShape_Area"].min(),
        color="r",
        linestyle="--",
        label="Min. threshold for Nuclei Area",
    )
    plt.axhline(
        y=outliers_df["Nuclei_Intensity_IntegratedIntensity_CorrDNA"].min(),
        color="b",
        linestyle="--",
        label="Min. threshold for Nuclei Intensity",
    )

    # Customize plot
    plt.title(f"Nuclei Area vs. Nuclei Integrated Intensity for plate {plate_name}")
    plt.xlabel("Nuclei Area")
    plt.ylabel("Nuclei Integrated Intensity (Hoechst)")
    plt.tight_layout()

    # Show legend
    plt.legend(loc="upper left", bbox_to_anchor=(0, 1.0), prop={"size": 10})

    # Save figure without showing it
    plt.savefig(
        pathlib.Path(f"{qc_fig_dir}/{plate_name}_large_nuclei_outliers.png"), dpi=500
    )
    plt.close()  # Close the plot to prevent it from displaying


# ### Function to plot KDE

# In[3]:


def plot_nuclei_solidity_histogram(
    plate_df: pd.DataFrame,
    outliers_df: pd.DataFrame,
    plate_name: str,
    qc_fig_dir: pathlib.Path,
) -> None:
    """Plot histogram of the nuclei solidity outliers.

    Args:
        plate_df (pd.DataFrame): Dataframe of the CytoTable output with the morphology profiles.
        outliers_df (pd.DataFrame): Dataframe of the coSMicQC output which includes the identified outliers.
        plate_name (str): String of the plate's name or ID.
        qc_fig_dir (pathlib.Path): Path to the directory to save the plot.
    """
    # Create a copy of plate_df to avoid modifying the original
    plate_df = plate_df.copy()

    # Set the default 'Outlier_Status' to 'Single-cell passed QC'
    plate_df["Outlier_Status"] = "Single-cell passed QC"

    # Update 'Outlier_Status' for cells that failed QC
    plate_df.loc[plate_df.index.isin(outliers_df.index), "Outlier_Status"] = (
        "Single-cell failed QC"
    )

    # Create histogram
    plt.figure(figsize=(10, 6))
    sns.histplot(
        data=plate_df,
        x="Nuclei_AreaShape_Solidity",
        hue="Outlier_Status",
        palette={
            "Single-cell passed QC": "#006400",
            "Single-cell failed QC": "#990090",
        },
        multiple="stack",  # Stacks bars based on hue
        bins=50,  # Number of bins
        kde=False,
    )

    # Add threshold line
    max_threshold = outliers_df["Nuclei_AreaShape_Solidity"].max()
    plt.axvline(
        x=max_threshold,
        color="r",
        linestyle="--",
        label=f"Threshold for Outliers: < {max_threshold}",
    )

    # Customize plot
    plt.ylabel("Count")
    plt.xlabel("Nuclei Solidity")
    plt.title(f"Distribution of Nuclei Solidity for plate {plate_name}")
    plt.legend()
    plt.tight_layout()

    # Save figure without showing it
    plt.savefig(
        pathlib.Path(
            f"{qc_fig_dir}/{plate_name}_nuclei_solidity_outliers_histogram.png"
        ),
        dpi=500,
    )
    plt.close()  # Close the plot to prevent it from displaying


# ## Set paths and variables

# In[4]:


# Set parameter for papermill to use for processing
plate_id = "BR00143976"


# In[5]:


# Parameters
plate_id = "BR00143978"


# In[6]:


# Directory with data
data_dir = pathlib.Path("./data/converted_profiles/")

# Directory to save cleaned data
cleaned_dir = pathlib.Path("./data/cleaned_profiles/")
cleaned_dir.mkdir(exist_ok=True)

# Directory to save qc figures
qc_fig_dir = pathlib.Path("./qc_figures")
qc_fig_dir.mkdir(exist_ok=True)

# Directory to save qc results
qc_results_dir = pathlib.Path("./qc_results")
qc_results_dir.mkdir(exist_ok=True)

# Create an empty dictionary to store data frames for each plate
all_qc_data_frames = {}

# metadata columns to include in output data frame
metadata_columns = [
    "Image_Metadata_Plate",
    "Image_Metadata_Well",
    "Image_Metadata_Site",
    "Metadata_Nuclei_Location_Center_X",
    "Metadata_Nuclei_Location_Center_Y",
]


# ## Load in plate to perform QC on

# In[7]:


# Construct the file path for the given plate_id
file_path = data_dir / f"{plate_id}_converted.parquet"

if file_path.exists():
    start_time = time.time()  # Start timer for loading

    # Load and compute the DataFrame
    plate_df = dd.read_parquet(file_path, engine="pyarrow").compute()

    end_time = time.time()  # End timer for loading
    print(
        f"Loaded plate: {plate_id}, Shape: {plate_df.shape}, Time taken: {end_time - start_time:.2f} seconds"
    )
else:
    print(f"Parquet file for plate {plate_id} not found.")


# ## Filter down plate data to detect outliers to improve speed

# In[8]:


# Define the QC features
qc_features = [
    "Nuclei_AreaShape_Area",
    "Nuclei_Intensity_IntegratedIntensity_CorrDNA",
    "Nuclei_AreaShape_Solidity",
]

# Filter plate_df to only include metadata columns and QC features
filtered_plate_df = plate_df[metadata_columns + qc_features]


# ## Detect segmentations of large clusters of nuclei

# In[9]:


# Find large nuclei outliers for the current plate
large_nuclei_high_int_outliers = find_outliers(
    df=filtered_plate_df,
    metadata_columns=metadata_columns,
    feature_thresholds={
        "Nuclei_AreaShape_Area": 2,
        "Nuclei_Intensity_IntegratedIntensity_CorrDNA": 3,
    },
)


# ### Plot the outliers

# In[10]:


# Save large nuclei scatterplot
plot_large_nuclei_outliers(
    plate_df=plate_df,
    outliers_df=large_nuclei_high_int_outliers,
    plate_name=plate_id,
    qc_fig_dir=qc_fig_dir,
)


# ## Detect very irregular shaped nuclei, likely indicating mis-segmentation
# 
# NOTE: These datasets are meant for optimization so all cells should be in normal, control cell states. This mean there are likely to be not as interesting phenotypes to be mistaken as poor quality segmentations.

# In[11]:


# Find low nuclei solidity outliers for the current plate
solidity_nuclei_outliers = find_outliers(
    df=filtered_plate_df,
    metadata_columns=metadata_columns,
    feature_thresholds={
        "Nuclei_AreaShape_Solidity": -2,
    },
)


# ### Plot the outliers

# In[12]:


# Save low nuclei solidity histogram
plot_nuclei_solidity_histogram(
    plate_df=plate_df,
    outliers_df=solidity_nuclei_outliers,
    plate_name=plate_id,
    qc_fig_dir=qc_fig_dir,
)


# ## Save the outlier indices to use for reporting

# In[13]:


# Identify failing indices from both outlier dataframes
outlier_indices = pd.concat(
    [large_nuclei_high_int_outliers, solidity_nuclei_outliers]
).index.unique()

# Create a new dataframe with only the failing rows
failing_df = plate_df.loc[outlier_indices, metadata_columns].copy()

# Add failure condition columns, marking all rows as True for each condition they failed
failing_df["Failed_LargeNuclei_HighInt"] = failing_df.index.isin(
    large_nuclei_high_int_outliers.index
)
failing_df["Failed_SolidityNuclei"] = failing_df.index.isin(
    solidity_nuclei_outliers.index
)

# Ensure boolean dtype
failing_df = failing_df.astype(
    {"Failed_LargeNuclei_HighInt": bool, "Failed_SolidityNuclei": bool}
)

# Keep original indices for later
failing_df = failing_df.reset_index().rename(columns={"index": "original_indices"})

# Save the indices dataframe as CSV
failing_df.to_csv(
    pathlib.Path(f"{qc_results_dir}/{plate_id}_failed_qc_indices.csv.gz"),
    compression="gzip",
    index=False,
)

# Calculate percentage failed
total_rows = plate_df.shape[0]
failed_percentage = (failing_df.shape[0] / total_rows) * 100

# Print summary with percentage
print(f"Total failing single cells: {failing_df.shape[0]} ({failed_percentage:.2f}%)")


# ## Clean and save the data

# In[14]:


# Remove rows with outlier indices
plate_df_cleaned = plate_df.drop(outlier_indices)

# Save cleaned data for this plate
plate_df_cleaned.to_parquet(f"{cleaned_dir}/{plate_id}_cleaned.parquet")

# Calculate the number of outliers and the total number of cells
num_outliers = len(plate_df) - len(
    plate_df_cleaned
)  # The number of outliers is the difference
total_cells = len(plate_df)

# Calculate the percentage of cells that failed QC
percent_failed_qc = (num_outliers / total_cells) * 100

# Print the plate name, the shape of the cleaned data, and the percentage of cells that failed QC
print(
    f"{plate_id} has been cleaned and saved with the shape: {plate_df_cleaned.shape}."
)

