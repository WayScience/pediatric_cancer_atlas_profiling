# Illumination correction

In this module, we create LoadData CSVs to use in CellProfiler and generate illumination correction functions per channel to apply in the next pipeline.
We also extract whole image quality metrics per plate as CSVs to use in the next module to determine thresholds for determining good versus poor quality images.

It took approximately **two hours** in total across 6 plates to generate IC functions as `npy` files and extract spreadsheets of the image quality control measurements.
We are using a Linux-based machine running Pop_OS! LTS 22.04 with an AMD Ryzen 7 3700X 8-Core Processor. There is a total of 16 CPUs with 125 GB of MEM.

## Create LoadData CSVs and perform IC

Before running the bash script, we will need to create the LoadData CSVs using [the Jupyter notebook](./0.create_loaddata_csvs.ipynb).
It only takes about **30 seconds** to run just this notebook.
There is a weird error that occurs when trying to process via the Python script that does not occur if using the notebook.
See [issue #34](https://github.com/broadinstitute/pe2loaddata/issues/34) for further details.

Once you run the create LoadData CSVs using [the first notebook](./0.create_loaddata_csvs.ipynb), you can use the bash script to run the IC CellProfiler pipeline to extract image quality metrics and IC functions using the command below:

```bash
# Make sure you are in the 1.illumination_correction directory
source loaddata_and_illum.sh
```
