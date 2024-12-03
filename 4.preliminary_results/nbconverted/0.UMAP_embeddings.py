#!/usr/bin/env python
# coding: utf-8

# # Generate UMAP embeddings using the single-cell morphology space and plot
# 
# Due to the large population of single-cells across each plate, we take a subsample of ~10,000 single-cells where we get equal number of samples per cell line that is stratified by seeding density.
# 
# We then plot the UMAP embeddings per plate labelling by cell line.
# `U2-OS` cells are colored magenta across all plates to ensure consistency.

# ## Import libraries

# In[1]:


import umap
import pathlib
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


# ## Define paths to feature-selected single-cell profiles

# In[2]:


# directory to the single-cell data
data_dir = pathlib.Path("../3.preprocessing_features/data/single_cell_profiles")

# create a list of paths to each feature-selected profile
feature_selected_files = list(data_dir.rglob("*_feature_selected.parquet"))

# print paths to validate
for file in feature_selected_files:
    print(file)


# ## Collect subsample of single-cells from each plate
# 
# NOTE: We are collecting approximately equal number of cells per cell line and stratified by the seeding density. By not using the whole datasets, we speed up computational expense as this code cell takes ~2 minutes to run.

# In[3]:


# set constants 
total_samples = 10000
random_seed = 0

# dictionary to store sampled data
sampled_data_dict = {}

# process each plate file
for file_path in feature_selected_files:
    # identify plate name from file path
    plate_name = file_path.stem.split("_")[0]
    
    # read in only cell line column to determine sampling split (number of sample per cell line)
    unique_cell_lines = pd.read_parquet(file_path, columns=["Metadata_cell_line"])["Metadata_cell_line"].unique()
    samples_per_cell_line = total_samples // len(unique_cell_lines)
    
    all_samples = []
    
    # process each cell line
    for cell_line in unique_cell_lines:
        # load only rows for the current cell line
        cell_line_data = pd.read_parquet(
            file_path,
            filters=[("Metadata_cell_line", "==", cell_line)]
        )
        
        # perform stratified sampling within the cell line
        stratified_samples = cell_line_data.groupby("Metadata_seeding_density", group_keys=False).apply(
            lambda group: group.sample(
                n=min(samples_per_cell_line // len(cell_line_data["Metadata_seeding_density"].unique()), len(group)),
                random_state=random_seed
            ),
            include_groups=False  # Explicitly exclude grouping columns in the output
        ).reset_index(drop=True)
        
        # add the stratified sampled data to list
        all_samples.append(stratified_samples)
    
    # combine all samples for the current plate
    combined_samples = pd.concat(all_samples, ignore_index=True)
    
    # adjust total number of samples
    sampled_df = combined_samples.sample(
        n=min(total_samples, len(combined_samples)),
        random_state=random_seed,
        replace=False
    )
    
    # store results
    sampled_data_dict[plate_name] = sampled_df
    print(f"Processed plate: {plate_name} | Sampled data shape: {sampled_df.shape}")


# ## Generate UMAP embeddings per plate

# In[4]:


# UMAP configuration
umap_components = 2
random_seed = 0

# dictionary to store UMAP results
umap_results_dict = {}

# process sampled data from the sampled_data dictionary
for plate_name, sampled_df in sampled_data_dict.items():
    # separate metadata and feature columns
    metadata_columns = [col for col in sampled_df.columns if col.startswith("Metadata_")]
    feature_columns = [col for col in sampled_df.columns if not col.startswith("Metadata_")]
    
    # drop rows with NaN values in feature columns
    cleaned_df = sampled_df.dropna(subset=feature_columns)
    
    # perform UMAP embedding on the cleaned feature data
    umap_model = umap.UMAP(n_components=umap_components, random_state=random_seed, n_jobs=1)
    umap_embeddings = umap_model.fit_transform(cleaned_df[feature_columns])
    
    # create a DataFrame for embeddings
    umap_df = pd.DataFrame(
        umap_embeddings,
        columns=[f"UMAP{i}" for i in range(umap_components)],
        index=cleaned_df.index
    )
    
    # combine UMAP embeddings with metadata
    final_df = pd.concat([cleaned_df[metadata_columns], umap_df], axis=1)
    
    # store the result in the dictionary to use for outputting results
    umap_results_dict[plate_name] = final_df
    
    print(f"UMAP embeddings generated for plate: {plate_name}")
    print(f"Cleaned samples shape: {cleaned_df.shape}")
    print(f"Final shape with embeddings: {final_df.shape}")


# ## Create UMAP plots per plate labelling by the cell line

# In[5]:


# Define consistent color for U2-OS
u2os_color = "#9b0068"  # Darker magenta color
custom_palette = {}

# Create the directory for saving figures
figures_dir = pathlib.Path("./figures")
figures_dir.mkdir(exist_ok=True)

# Create scatterplots for each plate
for plate_name, final_df in umap_results_dict.items():
    # Get unique cell lines in the current DataFrame
    cell_lines = final_df["Metadata_cell_line"].unique()
    
    # Get colors for non-U2-OS cell lines from the tab10 palette
    remaining_colors = sns.color_palette("tab10", n_colors=len(cell_lines) - 1)

    # Assign pink to U2-OS
    if "U2-OS" in cell_lines:
        custom_palette["U2-OS"] = u2os_color

    # Assign the rest of the colors to the other cell lines
    color_idx = 0
    for cell_line in cell_lines:
        if cell_line != "U2-OS":
            custom_palette[cell_line] = remaining_colors[color_idx]
            color_idx += 1
    
    # Plot
    plt.figure(figsize=(12, 8))
    sns.scatterplot(
        data=final_df,
        x="UMAP0",
        y="UMAP1",
        hue="Metadata_cell_line",
        palette=custom_palette,  # Use custom palette
        s=35,
        alpha=0.4
    )
    
    # Customize the plot
    plt.title(f"UMAP Embedding for Plate: {plate_name}", fontsize=16, weight='bold')
    plt.xlabel("UMAP0", fontsize=14)
    plt.ylabel("UMAP1", fontsize=14)
    
    # Customize and reposition the legend
    plt.legend(
        title="Cell Line",
        fontsize=10,
        title_fontsize=12,
        loc='center left',
        bbox_to_anchor=(1.05, 0.5),
        ncol=2
    )
    
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    
    # Save the plot
    file_path = figures_dir / f"{plate_name}_UMAP.png"
    plt.savefig(file_path, dpi=600)
    plt.close()  # Close the plot to free memory
    
    print(f"Saved plot for {plate_name} as {file_path}")

