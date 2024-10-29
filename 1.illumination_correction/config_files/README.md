# Configuration files for pe2loaddata

Due to some cell lines having non-optimal Cell Painting parameters which lead to poor imaging, many plates were re-imaged only for wells for these cell lines.
This led to an issue where the `ChannelID` for each channel was different for each set of plates re-imaged per cell line.
To avoid this problem, we had to create a config file per cell line and [one main config file](./config.yml) for all of the main plates (`BR00` prefix).

During the LoadData CSV creation, we use these config files to make a CSV file per plate or per cell line and plate.
We then merge the re-imaged per cell line back to their original plates' CSVs (3 plates per cell line) and removed the old rows in the original plate CSV file.
