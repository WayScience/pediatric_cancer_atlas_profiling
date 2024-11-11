# Feature extraction

In this module, we create LoadData CSVs with paths to IC functions per channel to use in CellProfiler and segment and extract features from single-cell compartments.
We also include thresholds for determining good versus poor quality images as calculated in the previous module to avoid processing poor quality images.

It took approximately **5 days** to segment and extract morphology features from single-cell compartments for all 6 pilot plates, where there were approximately 1,200-2,000 image sets per plate to process.
We are using a Linux-based machine running Pop_OS! LTS 22.04 with an AMD Ryzen 7 3700X 8-Core Processor with 16 CPUs and 125 GB of MEM.

## Create LoadData CSVs with IC functions and run CellProfiler analysis

Before running the bash script, we will need to create the LoadData CSVs using [the Jupyter notebook](./0.create_loaddata_csvs.ipynb).
It only takes about **30 seconds** to run just this notebook.
There is an error that occurs when processing via the Python script, which does not occur if using the notebook.
See [issue #34](https://github.com/broadinstitute/pe2loaddata/issues/34) for further details.

Once you run the create LoadData CSVs using [the first notebook](./0.create_loaddata_csvs.ipynb), you can run the CellProfiler segmentation and feature extraction pipeline using using the command below:

```bash
# Make sure you are in the 2.feature_extraction directory
source cp_analysis.sh
```
