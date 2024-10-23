"""
This collection of functions runs CellProfiler in parallel and can convert the results into log files
for each process.
"""

import logging
import multiprocessing
import pathlib
import subprocess
from concurrent.futures import ProcessPoolExecutor, Future
from typing import List

from errors.exceptions import MaxWorkerError


def results_to_log(
    results: List[subprocess.CompletedProcess], log_dir: pathlib.Path, run_name: str
) -> None:
    """
    This function converts the list of subprocess results from a CellProfiler parallelization run
    into a separate log file for each process.

    Args:
        results (List[subprocess.CompletedProcess]): Outputs from subprocess.run
        log_dir (pathlib.Path): Directory for log files
        run_name (str): Name for the type of CellProfiler run (e.g., whole image features)
    """
    for result in results:
        # Extract plate name and decoded output
        plate_name = result.args[6].name
        output_string = result.stderr.decode("utf-8")

        # Set the log file path
        log_file_path = log_dir / f"{plate_name}_{run_name}_run.log"

        # Create a new logger instance for each plate
        logger = logging.getLogger(plate_name)
        logger.setLevel(logging.INFO)

        # Create a file handler for the logger
        handler = logging.FileHandler(log_file_path)
        formatter = logging.Formatter(
            "[%(asctime)s] [Process ID: %(process)d] %(message)s"
        )
        handler.setFormatter(formatter)

        # Add the handler to the logger
        logger.addHandler(handler)

        # Log the output
        logger.info(f"Plate Name: {plate_name}")
        logger.info(f"Output String: {output_string}")

        # Close the handler after logging to avoid resource leaks
        handler.close()
        logger.removeHandler(handler)


def run_cellprofiler_parallel(
    plate_info_dictionary: dict,
    run_name: str,
) -> None:
    """
    This function utilizes multi-processing to run CellProfiler pipelines in parallel.

    Args:
        plate_info_dictionary (dict): dictionary with all paths for CellProfiler to run a pipeline
        run_name (str): a given name for the type of CellProfiler run being done on the plates (example: whole image features)

    Raises:
        FileNotFoundError: if paths to pipeline and images do not exist
    """
    # create a list of commands for each plate with their respective log file
    commands = []

    # make logs directory
    log_dir = pathlib.Path("./logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # iterate through each plate in the dictionary
    for _, info in plate_info_dictionary.items():
        # set paths for CellProfiler
        path_to_pipeline = info["path_to_pipeline"]
        path_to_output = info["path_to_output"]

        # make output directory if it is not already created
        pathlib.Path(path_to_output).mkdir(exist_ok=True)

        # check to make sure paths to pipeline are correct before running the pipeline
        if not pathlib.Path(path_to_pipeline).resolve(strict=True):
            raise FileNotFoundError(
                f"The file '{pathlib.Path(path_to_pipeline).name}' does not exist"
            )

        # set the correct CellProfiler command for if using images or a LoadData CSV
        if "path_to_loaddata" in info:
            # assign path to loaddata csv as variable
            path_to_loaddata = info["path_to_loaddata"]

            # set command up to use for a loaddata csv
            command = [
                "cellprofiler",
                "-c",
                "-r",
                "-p",
                path_to_pipeline,
                "-o",
                path_to_output,
                "--data-file",
                path_to_loaddata,
            ]
        else:
            # assign path to images as variable
            path_to_images = info["path_to_images"]

            # check to make sure path to images is a directory and exists
            if not pathlib.Path(path_to_images).is_dir():
                raise FileNotFoundError(
                    f"Directory '{pathlib.Path(path_to_images).name}' does not exist or is not a directory"
                )
            # set command up to use for a path to images
            command = [
                "cellprofiler",
                "-c",
                "-r",
                "-p",
                path_to_pipeline,
                "-o",
                path_to_output,
                "-i",
                path_to_images,
            ]

        # Append the commands for as many plates being processed
        commands.append(command)

    # set the number of CPUs/workers as the number of commands
    num_processes = len(commands)

    # make sure that the number of workers does not exceed the maximum number of workers for the machine
    if num_processes > multiprocessing.cpu_count():
        raise MaxWorkerError(
            "Exception occurred: The number of commands exceeds the number of CPUs/workers. Please reduce the number of commands."
        )

    # set parallelization executer to the number of commands
    executor = ProcessPoolExecutor(max_workers=num_processes)

    # creates a list of futures that are each CellProfiler process for each plate
    futures: List[Future] = [
        executor.submit(
            subprocess.run,
            args=command,
            capture_output=True,
        )
        for command in commands
    ]

    # the list of CompletedProcesses holds all the information from the CellProfiler run
    results: List[subprocess.CompletedProcess] = [future.result() for future in futures]

    print("All processes have been completed!")

    # for each process, confirm that the process completed successfully and return a log file
    for result in results:
        plate_name = result.args[6].name
        # convert the results into log files
        results_to_log(results=results, log_dir=log_dir, run_name=run_name)
        if result.returncode == 1:
            print(
                f"A return code of {result.returncode} was returned for {plate_name}, which means there was an error in the CellProfiler run."
            )

    # to avoid having multiple print statements due to for loop, confirmation that logs are converted is printed here
    print("All results have been converted to log files!")
