"""
This file contains functions to create different LoadData csvs (w/ or w/o illum functions) 
for specific CellProfiler pipelines.
"""


import os
import subprocess
import pathlib


def create_loaddata_csv(
    index_directory: pathlib.Path,
    config_path: pathlib.Path,
    path_to_output: pathlib.Path,
):
    """
    Create LoadData csv for CellProfiler

    Parameters
    ----------
    index_directory : pathlib.Path
        path to the `Index.idx.xml` file for the plate (normally located in the /Images folder)
    config_path : pathlib.Path
        path to the `config.yml' file for pe2loaddata to process the csv
    path_to_output : pathlib.Path
        path to the `wave1_loaddata.csv' file used for generating the illumination correction functions for each channel
    """
    command = [
        "pe2loaddata",
        "--index-directory",
        str(index_directory),
        str(config_path),
        str(path_to_output),
    ]
    subprocess.run(command, check=True)
    print(f"{path_to_output.name} is created!")


def create_loaddata_illum_csv(
    index_directory: pathlib.Path,
    config_path: pathlib.Path,
    path_to_output: pathlib.Path,
    illum_directory: pathlib.Path,
    plate_id: str,
    illum_output_path: pathlib.Path,
):
    """
    Create LoadData csv with illum correction functions for CellProfiler (used for analysis pipelines)

    Parameters
    ----------
    index_directory : pathlib.Path
        path to the `Index.idx.xml` file for the plate (normally located in the /Images folder)
    config_path : pathlib.Path
        path to the `config.yml' file for pe2loaddata to process the csv
    path_to_output : pathlib.Path
        path to the `wave1_loaddata.csv' file used for generating the illumination correction functions for each channel
    illum_directory : pathlib.Path
        path to folder where the illumination correction functions (.npy files) are located
    plate_id : str
        string of the name of the plate to create the csv
    illum_output_path : pathlib.Path
        path to where the new csv will be created along with the name (e.g. path/to/wave1_loaddata_with_illum.csv)
    """
    command = [
        "pe2loaddata",
        "--index-directory",
        str(index_directory),
        str(config_path),
        str(path_to_output),
        "--illum",
        "--illum-directory",
        str(illum_directory),
        "--plate-id",
        plate_id,
        "--illum-output",
        str(illum_output_path),
    ]
    subprocess.run(command, check=True)
    print(f"{illum_output_path.name} is created!")

    # remove the LoadData CSV that is created without the illum functions as it is not needed
    os.remove(path_to_output)
    print(f"The {path_to_output.name} CSV file has been removed as it does not contain the IC functions.")
