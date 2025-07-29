# Download data

In this module, we will add all relevant information for downloading the datasets (including images, XML files, platemaps, etc.) when it comes available.
All platemaps and layout figures will be included under the [metadata](./metadata/) folder of this module.

--- 

## Current Access Instructions for Miscroscopy Images (Development)

**Note:** The current method of accessing and downloading the microscopy image data is intended for development purposes only. When the data becomes publicly available, access methods will change, and this README will be updated to reflect the final public access protocol.

---

### Pre-Requisites and Dependencies
- Access to CU-Boulder Alpine compute cluster.
- Access to PetaLibrary Data storage on the Alpine compute cluster (specifically `/pl/active/koala/`).
- A registered **Globus account** with CU credentials and access to the Globus web interface.
  - *(Optional)* Installation of the `globus-cli` command-line tool for advanced users.
- Globus Connect Personal installed and configured on the local machine for data transfer.
  - Ensure that the local Globus endpoint is properly configured with allowed paths for data transfer.

---

### Instructions for Data Transfer Using Globus Web Interface
1. Log in to the [Globus web interface](https://app.globus.org/).
2. Select the **File Manager** tab from the left-hand menu.
3. Search for the source and destination endpoints in the search box:
   - Source endpoint: `CU Boulder Research Computing` for Alpine.
   - Destination endpoint: your personal Globus Connect Personal endpoint.
4. Specify the source path (`/pl/active/koala/`) and the destination path on your local machine.
   - Note: You must explicitly configure your Globus Connect Personal installation to allow access to the intended local paths.
5. Select the files to transfer and click **Start Transfer**. You can configure transfer options (e.g., email notifications, concurrency) under **Transfer & Timer Options**.
6. During the transfer, you may need to authorize access to both endpoints using your CU credentials.

### Instructions for Data Transfer Using Globus CLI
1. Log in to the Globus CLI using the command `globus login`.

2. Look up endpoint IDs:
   - For Alpine, use the command `globus endpoint search "CU Boulder Research Computing"`. 
        * As of 01/02/2025, the endpoint ID for Alpine is `4718fe94-aafd-498a-8bae-6bd430bb50a0`.
   - For your local machine, use the command `globus endpoint local-id`.

3. Initiate the transfer:
   - Use the command `globus transfer <source_endpoint_id>:/pl/active/koala/<file_or_dir> <destination_endpoint_id>:/local/path/to/destination`.
   - Replace `<source_endpoint_id>` and `<destination_endpoint_id>` with the appropriate endpoint IDs.
   - Replace `<file_or_dir>` and `/local/path/to/destination` with the specific paths.

4. Confirm the transfer:
   - You may be prompted to authorize the transfer. Follow the on-screen instructions.
   - After initiating the transfer, the console should output:  
     `Message: The transfer has been accepted and a task has been created and queued for execution`  
     `Task ID: xxxxx`

5. Monitor the transfer:
   - Use the command `globus task show <task_id>` to check the status of your transfer.

---

### Future Access Information
Once the microscopy image data is publicly released, access will no longer require CU credentials or the current development-specific setup. Instructions for public access, including any associated data repositories, will be added here upon release.

---