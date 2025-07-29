#!/usr/bin/env python
# coding: utf-8

# # Perform single-cell quality control
# 
# In this notebook, we perform single-cell quality control using coSMicQC. We filter the single cells by identifying outliers with z-scores, and use either combinations of features or one feature for each condition. We use features from the AreaShape and Intensity modules to assess the quality of the segmented single-cells:
# 
# ### Assessing poor nuclei segmentation
# 
# Due to high confluence with various seeding densities, sometimes nuclei overlap on top of each other, creating highly intense clusters within the Hoechst channel. 
# To identify these nuclei, we use:
# 
# - **Nuclei mass displacement:** This metric quantifies how different the segmentation versus intensity based centeroids are, which can reflect multiple nuclei within one segmentation. 
# - **Nuclei intensity:** This metric quantifies the total intensity of all pixels in a nucleus segmentation. 
# In combination with abnormally high mass displacement, we detect nuclei that are also highly intense, likely indicating that this a group of overlapped nuclei.
# 
# For the preliminary dataset, we are working with cells that have not been treated so we do not expect any crazy phenotypes. Given that context, we can use a feature called Solidity. From ChatGPT, the simple explanation is that this features compares the area of the object to its convex hull, which measures compactness in relation to convexity. High solidity implies few indentations, while lower solidity indicates more irregularity.
# 
# - **Nuclei solidity:** This metric quantifies the compactness of the nuclei shape.
# When a nuclei is mis-segmented, we see more protrusions or harsh outlines around the segmentations, which we expect this is what this feature will detect.
# 
# ### Assessing poor cell segmentation
# 
# Also due to high confluence, overlapping nuclei can lead to the CellProfiler segmentation algorithm to sometimes keep bad segmentations (which is why we have coSMicQC) but can also detect these segmentations as being "too large" based on the parameters. 
# This leads to poor cell segmentations because CellProfiler will remove the context of the nuclei it couldn't segment, leading to segmenting multiple cells as one cell and assigning it to one nuclei.
# To identify these cells, we use:
# 
# - **Cell intensity in the nuclei channel:** This metric quantifies the total intensity of all pixels of a cell segmentation in the nuclei channel. We would expect fairly low total intensity in the nuclei channel for whole cells as there is only one 
# 
# 

# In[1]:


import pathlib
import re
import time

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from cytodataframe import CytoDataFrame
from cosmicqc import find_outliers

# Ignore FutureWarnings from cytodataframe due to skimage deprecation (does not affect functionality)
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)


# # Set functions for plotting

# ### Function to plot scatterplot

# In[2]:


def plot_cluster_nuclei_outliers(
    plate_df: pd.DataFrame,
    outliers_df: pd.DataFrame,
    plate_name: str,
    qc_fig_dir: pathlib.Path,
) -> None:
    """Plot scatterplot of the cluster nuclei outliers.

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
        x="Nuclei_Intensity_MassDisplacement_CorrDNA",
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
        x=outliers_df["Nuclei_Intensity_MassDisplacement_CorrDNA"].min(),
        color="r",
        linestyle="--",
        label="Min. threshold for Nuclei Mass Displacement",
    )
    plt.axhline(
        y=outliers_df["Nuclei_Intensity_IntegratedIntensity_CorrDNA"].min(),
        color="b",
        linestyle="--",
        label="Min. threshold for Nuclei Intensity",
    )

    # Customize plot
    plt.title(
        f"Nuclei Mass Displacement vs. Nuclei Integrated Intensity for plate {plate_name}"
    )
    plt.xlabel("Nuclei Mass Displacement (Hoechst)")
    plt.ylabel("Nuclei Integrated Intensity (Hoechst)")
    plt.tight_layout()

    # Show legend
    plt.legend(loc="upper right", bbox_to_anchor=(1.0, 1.0), prop={"size": 10})

    # Save figure without showing it
    plt.savefig(
        pathlib.Path(f"{qc_fig_dir}/{plate_name}_cluster_nuclei_outliers.png"), dpi=500
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
plate_id = "BR00145816"


# In[5]:


# Parameters
plate_id = "BR00147495"


# ## Injected parameter from papermill that updates for every plate being processed

# In[6]:


# Set the round of data being processed
round_id = "Round_3_data"

# Directory containing the converted profiles
data_dir = pathlib.Path(f"./data/converted_profiles/{round_id}")

# Directory to save cleaned data
cleaned_dir = pathlib.Path(f"./data/cleaned_profiles/{round_id}")
cleaned_dir.mkdir(exist_ok=True)

# Directory to save qc figures
qc_fig_dir = pathlib.Path(f"./qc_figures/{round_id}")
qc_fig_dir.mkdir(exist_ok=True)

# Directory to save qc results
qc_results_dir = pathlib.Path(f"./qc_results/{round_id}")
qc_results_dir.mkdir(exist_ok=True)

# Create an empty dictionary to store data frames for each plate
all_qc_data_frames = {}

# Set the compartment of choice to perform QC at the start (will change later)
compartment = "Nuclei"


# ## Load in plate to perform QC on

# In[7]:


# Construct the file path for the given plate_id
file_path = data_dir / f"{plate_id}_converted.parquet"

if file_path.exists():
    start_time = time.time()  # Start timer for loading

    # Load the DataFrame with pandas
    plate_df = pd.read_parquet(file_path, engine="pyarrow")

    end_time = time.time()  # End timer for loading
    print(
        f"Loaded plate: {plate_id}, Shape: {plate_df.shape}, Time taken: {end_time - start_time:.2f} seconds"
    )
else:
    print(f"Parquet file for plate {plate_id} not found.")


# ## Correct all columns with PathName to have the correct parent path
# 
# When ran on HPC, the path will reflect that of the HPC and not local when we are processing this data.

# In[8]:


correct_parent = "/media/18tbdrive/ALSF_pilot_data"

for col in plate_df.columns:
    if "PathName" in col and "Illum" not in col:
        plate_df[col] = plate_df[col].apply(
            lambda x: (
                re.sub(r"^.*ALSF_pilot_data/", correct_parent + "/", x)
                if isinstance(x, str)
                else x
            )
        )

# Print example image path after fix
print(plate_df["Image_PathName_OrigDNA"].dropna().iloc[0])


# ## Reduce down the plate columns to the features to be used for QC and metadata (improves speed)

# In[9]:


# metadata columns to include in output data frame
metadata_columns = [
    "Image_Metadata_Plate",
    "Image_Metadata_Well",
    "Image_Metadata_Site",
    f"Metadata_{compartment}_Location_Center_X",
    f"Metadata_{compartment}_Location_Center_Y",
    "Image_FileName_OrigDNA",
    "Image_FileName_OrigAGP",
    "Image_PathName_OrigDNA",
    "Image_PathName_OrigAGP",
    f"{compartment}_AreaShape_BoundingBoxMaximum_X",
    f"{compartment}_AreaShape_BoundingBoxMaximum_Y",
    f"{compartment}_AreaShape_BoundingBoxMinimum_X",
    f"{compartment}_AreaShape_BoundingBoxMinimum_Y",
]

# Define the QC features
qc_features = [
    "Nuclei_Intensity_IntegratedIntensity_CorrDNA",
    "Nuclei_AreaShape_Solidity",
    "Nuclei_Intensity_MassDisplacement_CorrDNA",
]

# Filter plate_df to only include metadata columns and QC features
filtered_plate_df = plate_df[metadata_columns + qc_features]


# In[10]:


# Print example image path after fix
print(filtered_plate_df["Image_PathName_OrigDNA"].dropna().iloc[0])


# ## Set mapping for outlines

# In[11]:


# create an outline and orig mapping dictionary to map original images to outlines
# note: we turn off formatting here to avoid the key-value pairing definition
# from being reformatted by black, which is normally preferred.
# fmt: off
outline_to_orig_mapping = {
    rf"{compartment}Outlines_{record['Image_Metadata_Plate']}_{record['Image_Metadata_Well']}_{record['Image_Metadata_Site']}.tiff": 
    rf"r{int(record['Image_Metadata_Row']):02d}c{int(record['Image_Metadata_Col']):02d}f{int(record['Image_Metadata_Site']):02d}p(\d{{2}})-ch\d+sk\d+fk\d+fl\d+\.tiff"
    for record in plate_df[
        [
            "Image_Metadata_Plate",
            "Image_Metadata_Well",
            "Image_Metadata_Site",
            "Image_Metadata_Row",
            "Image_Metadata_Col",
        ]
    ].to_dict(orient="records")
}
# fmt: on

next(iter(outline_to_orig_mapping.items()))


# ## Detect segmentations of clustered nuclei

# In[12]:


# Find large nuclei outliers for the current plate
nuclei_clustered_outliers = find_outliers(
    df=filtered_plate_df,
    metadata_columns=metadata_columns,
    feature_thresholds={
        "Nuclei_Intensity_MassDisplacement_CorrDNA": 0.05,  # Set very low as to detect all instances of clustering nuclei
        "Nuclei_Intensity_IntegratedIntensity_CorrDNA": 1.5,  # Set higher than displacement to avoid false positives
    },
)

# MUST SET DATA AS DATAFRAME FOR OUTLINE DIR TO WORK
nuclei_clustered_outliers_cdf = CytoDataFrame(
    data=pd.DataFrame(nuclei_clustered_outliers),
    data_outline_context_dir=f"../2.feature_extraction/sqlite_outputs/{round_id}/{plate_id}",
    segmentation_file_regex=outline_to_orig_mapping,
)[
    [
        "Nuclei_Intensity_MassDisplacement_CorrDNA",
        "Nuclei_Intensity_IntegratedIntensity_CorrDNA",
        "Image_FileName_OrigDNA",
    ]
]


print(nuclei_clustered_outliers_cdf.shape)
nuclei_clustered_outliers_cdf.sort_values(
    by="Nuclei_Intensity_MassDisplacement_CorrDNA", ascending=True
).head(2)


# In[13]:


nuclei_clustered_outliers_cdf.sample(n=2, random_state=0)


# ### Plot the outliers

# In[14]:


# Save cluster nuclei scatterplot
plot_cluster_nuclei_outliers(
    plate_df=plate_df,
    outliers_df=nuclei_clustered_outliers_cdf,
    plate_name=plate_id,
    qc_fig_dir=qc_fig_dir,
)


# ## Detect very irregular shaped nuclei, likely indicating mis-segmentation
# 
# **NOTE:** For the pilot data, we are determining optimal conditions (seeding density and time point). This means all cells are not treated and should be in a "healthy" state. Given that `solidity` measures how irregular the shape of a nuclei is, we would expect that cells treated with a drug/compound could yield interesting shapes or phenotypes. Since we are not working with drug treatments at this time, we can use this feature to identify technically incorrect segmentations.

# In[15]:


# Find low nuclei solidity outliers for the current plate
solidity_nuclei_outliers = find_outliers(
    df=filtered_plate_df,
    metadata_columns=metadata_columns,
    feature_thresholds={
        "Nuclei_AreaShape_Solidity": -1.6,  # Set at this point where it looks like it starts to detect good quality nuclei
    },
)

# MUST SET DATA AS DATAFRAME FOR OUTLINE DIR TO WORK
solidity_nuclei_outliers_cdf = CytoDataFrame(
    data=pd.DataFrame(solidity_nuclei_outliers),
    data_outline_context_dir=f"../2.feature_extraction/sqlite_outputs/{round_id}/{plate_id}",
    segmentation_file_regex=outline_to_orig_mapping,
)[
    [
        "Nuclei_AreaShape_Solidity",
        "Image_FileName_OrigDNA",
    ]
]


print(solidity_nuclei_outliers_cdf.shape)
solidity_nuclei_outliers_cdf.sort_values(
    by="Nuclei_AreaShape_Solidity", ascending=False
).head(2)


# In[16]:


solidity_nuclei_outliers_cdf.sample(n=2, random_state=0)


# ### Plot the outliers

# In[17]:


# Save low nuclei solidity histogram
plot_nuclei_solidity_histogram(
    plate_df=plate_df,
    outliers_df=solidity_nuclei_outliers,
    plate_name=plate_id,
    qc_fig_dir=qc_fig_dir,
)


# ## Detect cells that contain multiple nuclei due to segmentation issues
# 
# When CellProfiler segments a cluster of nuclei and decides that it is over the diameter range as specified in the parameters, it will not include that segmentation when segmenting whole cells. 
# This can lead to a whole cell segmentation based on one nuclei including the adjacent nuclei that was not included as a segmentation.
# 
# This description requires prior knowledge of the `IdentifyPrimaryObjects` and `IdentifySecondaryObjects` modules.
# 
# As a metaphor, we can think of it as three apples on a plate.
# One apple is detected correctly as one apple, but the other two were two close together, detected as one apple, and then removed from the plate because of it.
# Now, it looks like the whole plate belongs to the one correct apple, but in reality the plate should be split between three apples.
# This is the problem we want to avoid for a single-cell segmentation, we don't want to have a whole cell segmentation be assigned to one nuclei when it actually contains multiple nuclei.
# 

# In[18]:


# change compartment to cells
compartment = "Cells"

# metadata columns to include in output data frame
metadata_columns = [
    "Image_Metadata_Plate",
    "Image_Metadata_Well",
    "Image_Metadata_Site",
    f"Metadata_{compartment}_Location_Center_X",
    f"Metadata_{compartment}_Location_Center_Y",
    "Image_FileName_OrigDNA",
    "Image_FileName_OrigAGP",
    "Image_PathName_OrigDNA",
    "Image_PathName_OrigAGP",
    f"{compartment}_AreaShape_BoundingBoxMaximum_X",
    f"{compartment}_AreaShape_BoundingBoxMaximum_Y",
    f"{compartment}_AreaShape_BoundingBoxMinimum_X",
    f"{compartment}_AreaShape_BoundingBoxMinimum_Y",
]

# create an outline and orig mapping dictionary to map original images to outlines
# note: we turn off formatting here to avoid the key-value pairing definition
# from being reformatted by black, which is normally preferred.
# fmt: off
outline_to_orig_mapping = {
    rf"{compartment}Outlines_{record['Image_Metadata_Plate']}_{record['Image_Metadata_Well']}_{record['Image_Metadata_Site']}.tiff": 
    rf"r{int(record['Image_Metadata_Row']):02d}c{int(record['Image_Metadata_Col']):02d}f{int(record['Image_Metadata_Site']):02d}p(\d{{2}})-ch\d+sk\d+fk\d+fl\d+\.tiff"
    for record in plate_df[
        [
            "Image_Metadata_Plate",
            "Image_Metadata_Well",
            "Image_Metadata_Site",
            "Image_Metadata_Row",
            "Image_Metadata_Col",
        ]
    ].to_dict(orient="records")
}
# fmt: on

next(iter(outline_to_orig_mapping.items()))


# ### Filter down plate data to detect cells outliers (improves speed)

# In[19]:


# Define the QC features
qc_features = ["Cells_Intensity_IntegratedIntensity_CorrDNA"]

# Filter plate_df to only include metadata columns and QC features
filtered_plate_df = plate_df[metadata_columns + qc_features]


# ### Detect cell outliers

# In[20]:


# Find cell outliers for the current plate
cell_outliers = find_outliers(
    df=filtered_plate_df,
    metadata_columns=metadata_columns,
    feature_thresholds={
        # Set low to attempt to detect all instances of abnormally high int in nuclei for whole cells
        "Cells_Intensity_IntegratedIntensity_CorrDNA": 0.5,
    },
)

# MUST SET DATA AS DATAFRAME FOR OUTLINE DIR TO WORK
cell_outliers_cdf = CytoDataFrame(
    data=pd.DataFrame(cell_outliers),
    data_outline_context_dir=f"../2.feature_extraction/sqlite_outputs/{round_id}/{plate_id}",
    segmentation_file_regex=outline_to_orig_mapping,
)[
    [
        "Cells_Intensity_IntegratedIntensity_CorrDNA",
        "Image_FileName_OrigDNA",
    ]
]


print(cell_outliers_cdf.shape)
cell_outliers_cdf.sort_values(
    by="Cells_Intensity_IntegratedIntensity_CorrDNA", ascending=True
).head(2)


# In[21]:


cell_outliers_cdf.sample(n=2, random_state=0)


# ## Save the outlier indices to use for reporting

# In[22]:


# Identify failing indices from both outlier dataframes
outlier_indices = pd.concat(
    [nuclei_clustered_outliers, solidity_nuclei_outliers, cell_outliers]
).index.unique()

# Create a new dataframe with only the failing rows
failing_df = plate_df.loc[outlier_indices, metadata_columns].copy()

# Add failure condition columns, marking all rows as True for each condition they failed
failing_df["Failed_ClusteredNuclei"] = failing_df.index.isin(
    nuclei_clustered_outliers.index
)
failing_df["Failed_SolidityNuclei"] = failing_df.index.isin(
    solidity_nuclei_outliers.index
)
failing_df["Failed_CellsMultipleNuclei"] = failing_df.index.isin(cell_outliers.index)

# Ensure boolean dtype
failing_df = failing_df.astype(
    {
        "Failed_ClusteredNuclei": bool,
        "Failed_SolidityNuclei": bool,
        "Failed_CellsMultipleNuclei": bool,
    }
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

# In[23]:


# Remove rows with outlier indices
plate_df_cleaned = plate_df.drop(outlier_indices)

# Save cleaned data for this plate
plate_df_cleaned.to_parquet(f"{cleaned_dir}/{plate_id}_cleaned.parquet")

# Print the plate name and the shape of the cleaned data
print(
    f"{plate_id} has been cleaned and saved with the shape: {plate_df_cleaned.shape}."
)

