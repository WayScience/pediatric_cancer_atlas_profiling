#!/usr/bin/env python
# coding: utf-8

# In[1]:


import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages


# In[2]:


qc_df = pd.read_parquet("../3.preprocessing_features/qc_report/qc_report.parquet")
pearson_df = pd.read_parquet("../5.optimization/results/pearson_correlation.parquet")


# In[3]:


pearson_df.head()


# In[4]:


qc_df_sorted = qc_df.sort_values(by="Metadata_cell_line")
qc_df_sorted.head(50)


# In[5]:


pearson_df.columns = pearson_df.columns.str.strip()
qc_df.columns = qc_df.columns.str.strip()
print("Columns in pearson_df:", pearson_df.columns)
print("Columns in qc_df:", qc_df.columns)

# Check data types of the columns we want to merge on
print("Data types in pearson_df:\n", pearson_df.dtypes)
print("Data types in qc_df:\n", qc_df.dtypes)


# In[6]:


# Merge pearson_df and qc_df
merged_df = pd.merge(
    pearson_df[pearson_df["Shuffled"] == "False"],
    qc_df,
    on=["Metadata_cell_line", "Metadata_seeding_density", "Metadata_time_point"],
    how="inner"
)

# save df
merged_df.to_parquet("../5.optimization/results/merged_pearson_qc_data.parquet")
print("Merged dataframe saved to results/merged_pearson_qc_data.parquet")


# In[7]:


merged_df.head()


# In[8]:


custom_palette = sns.color_palette("Set1", n_colors=5)
# Create a PdfPages object to save all plots in a single PDF
with PdfPages('../5.optimization/results/pearson_vs_percentage_failing_cells.pdf') as pdf:
    # Plot for each cell line
    for cell_line in merged_df["Metadata_cell_line"].unique():
        # Filter data for the current cell line
        cell_line_df = merged_df[merged_df["Metadata_cell_line"] == cell_line]
        
        # Generate the scatter plot
        plt.figure(figsize=(8, 6))
        scatter = sns.scatterplot(
            data=cell_line_df,
            x="pearsons_correlation",
            y="percentage_failing_cells",
            hue="Metadata_seeding_density",
            palette=custom_palette,  # Choose a color palette for seeding density
            style="Metadata_time_point",  # Different styles for each time point
            markers=["o", "X", "s"],  # Customize markers
            s=100,
        )
        
        # Set plot title and labels
        plt.title(f"Pearson Correlation vs Percentage Failing Cells\nCell Line: {cell_line}", fontsize=16)
        plt.xlabel("Pearson Correlation")
        plt.ylabel("Percentage Failing Cells")
        
        # Reverse the y-axis (since higher failing percentage is bad)
        plt.gca().invert_yaxis()
        
        # Move the legend outside of the plot
        plt.legend(title='Seeding Density', bbox_to_anchor=(1.05, 1), loc='upper left')
        
        # Save the plot to the PDF
        pdf.savefig(bbox_inches="tight", transparent=True)
        plt.close()  # Close the figure to avoid overlap in the next plot
    
    print("Plots saved to results/pearson_vs_percentage_failing_cells.pdf")

