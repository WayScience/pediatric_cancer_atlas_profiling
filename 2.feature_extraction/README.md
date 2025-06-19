# Feature extraction

In this module, we create LoadData CSVs with paths to IC functions per channel to use in CellProfiler and segment and extract features from single-cell compartments.
We also include thresholds for determining good versus poor quality images as calculated in the previous module to avoid processing poor quality images.

## Local processing

It took approximately **5 days** to segment and extract morphology features from single-cell compartments for all six Round_1_data pilot plates, where there were approximately 1,200-2,000 image sets per plate to process.
We are using a Linux-based machine running Pop_OS! LTS 22.04 with an AMD Ryzen 7 3700X 8-Core Processor with 16 CPUs and 125 GB of MEM.

## High computer cluster processing

To process all six plates from Round_2_data pilot plates, the amount of time it took to run each plate varied by size.
The smallest plate took approximately **12 hours** to run and the largest look **2 days and 6 hours** to run.
Each plate is ran in parallel but as independent `sbatch` processes.
We see a significant decrease in computational time when processing as whole plates on HPC.

## Create LoadData CSVs with IC functions and run CellProfiler analysis

It only takes about **30 seconds** to run generate LoadData CSVs with illum paths.

To generate LoadData CSVs and run the CellProfiler segmentation and feature extraction pipeline, use the command below:

### Local processing script

```bash
# Make sure you are in the 2.feature_extraction directory
source cp_analysis_local.sh
```

### HPC processing scripts

When running on an HPC, you will only need to call the parent script.
The parent script will call `sbatch` processes per plate.

```slurm
sbatch cp_analysis_local.sh
```
