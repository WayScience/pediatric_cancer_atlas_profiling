#!/usr/bin/env python
# coding: utf-8

# # Generate a QC report for the preliminary data
# 
# The QC report consists of a table with the cell line, seeding density, and percentage failed single-cells

# In[1]:


import pathlib
import pandas as pd
from pycytominer import annotate
import pprint


# In[2]:


# path for platemap directory
platemap_dir = pathlib.Path("../0.download_data/metadata/platemaps")

# load in barcode platemap
barcode_platemap = pd.read_csv(
    pathlib.Path(f"{platemap_dir}/Barcode_platemap_pilot_data.csv")
)

# path for qc results (indices)
qc_results_dir = pathlib.Path("./qc_results")

# Path to dir with converted data from single-cell QC
converted_dir = pathlib.Path("./data/converted_profiles")

# output path for reports
output_dir = pathlib.Path("./qc_report")
output_dir.mkdir(parents=True, exist_ok=True)

# extract the plate names from the file name
plate_names = [file.stem.split("_")[0] for file in converted_dir.glob("*.parquet")]


# In[3]:


# create plate info dictionary
plate_info_dictionary = {
    name: {
        "converted_path": (
            str(
                pathlib.Path(
                    list(converted_dir.rglob(f"{name}_converted.parquet"))[0]
                ).resolve(strict=True)
            )
            if list(converted_dir.rglob(f"{name}_converted.parquet"))
            else None
        ),
        "qc_results_path": (
            str(
                pathlib.Path(
                    list(qc_results_dir.rglob(f"{name}_failed_qc_indices.csv.gz"))[0]
                ).resolve(strict=True)
            )
            if list(qc_results_dir.rglob(f"{name}_failed_qc_indices.csv.gz"))
            else None
        ),
        # Find the platemap file based on barcode match and append .csv
        "platemap_path": (
            str(
                pathlib.Path(
                    list(
                        platemap_dir.rglob(
                            f"{barcode_platemap.loc[barcode_platemap['barcode'] == name, 'platemap_file'].values[0]}.csv"
                        )
                    )[0]
                ).resolve(strict=True)
            )
            if name in barcode_platemap["barcode"].values
            else None
        ),
        # Get the time_point based on the barcode match
        "time_point": (
            barcode_platemap.loc[
                barcode_platemap["barcode"] == name, "time_point"
            ].values[0]
            if name in barcode_platemap["barcode"].values
            else None
        ),
    }
    for name in plate_names
}

# Display the dictionary to verify the entries
pprint.pprint(plate_info_dictionary, indent=4)


# In[4]:


# Set metadata columns to load in for the converted df
metadata_cols = [
        "Metadata_ImageNumber",
        "Image_Metadata_Plate",
        "Image_Metadata_Well",
        "Image_Metadata_Site",
        "Metadata_Nuclei_Location_Center_X",
        "Metadata_Nuclei_Location_Center_Y"
    ]

qc_report_list = []  # Initialize an empty list to store per-plate QC reports

# Generate QC report across plates
for plate, info in plate_info_dictionary.items():
    print(f"Generating QC report for {plate}")

    # Load in only the metadata columns from the converted dataframe and create a column called failed_qc
    converted_df = pd.read_parquet(info["converted_path"], columns=metadata_cols)
    converted_df["failed_qc"] = False  # Initialize all rows as False

    # Load in the qc_results_path and use the indices to change the rows that match to failing QC
    qc_failed_indices = pd.read_csv(info["qc_results_path"], compression='gzip')

    # Update failed_qc for rows matching the indices in qc_failed_indices
    converted_df.loc[qc_failed_indices["original_indices"], "failed_qc"] = True

    # Make sure that this worked by asserting that the number of True failed rows matches the number of failed indices
    num_failed_qc = converted_df["failed_qc"].sum()
    num_qc_failed_indices = len(qc_failed_indices)

    assert num_failed_qc == num_qc_failed_indices, f"Mismatch: {num_failed_qc} != {num_qc_failed_indices}"

    # Load platemap
    platemap_df = pd.read_csv(info["platemap_path"])

    # Add cell line and seeding density metadata
    annotated_df = annotate(
        profiles=converted_df,
        platemap=platemap_df,
        join_on=["Metadata_well", "Image_Metadata_Well"],
    )

    # Add 'Metadata_time_point' column based on the plate's time_point from dict
    annotated_df["Metadata_time_point"] = info["time_point"]

    # Group by cell line and seeding density
    failure_stats = (
        annotated_df.groupby(["Metadata_cell_line", "Metadata_seeding_density", "Metadata_time_point"])["failed_qc"]
        .mean()
        .reset_index()
        .rename(columns={"failed_qc": "percentage_failing_cells"})
    )

    # Convert to percentage
    failure_stats["percentage_failing_cells"] *= 100

    # Append to list
    qc_report_list.append(failure_stats)

# Concatenate all reports into a single DataFrame
qc_report_df = pd.concat(qc_report_list, ignore_index=True)

# Save QC report as parquet file
qc_report_df.to_parquet(pathlib.Path(f"{output_dir}/qc_report.parquet"))

# Display qc report info
print(qc_report_df.shape)
qc_report_df.head()

