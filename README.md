# Wasabi File Sync Script

## Overview

This script provides a complete solution for synchronizing files between a local folder and Wasabi S3 storage. It utilizes the `boto3` library to interact with Wasabi S3 services, `sqlite3` for local file tracking, and `watchdog` to monitor file system changes. Features include uploading new or modified files, deleting files, downloading updates from Wasabi, and initial synchronization.

## Requirements

- Python 3.6+
- `boto3`
- `watchdog`
- Wasabi S3 account

## Setup

1. Install the required Python packages:
   ```
   pip install boto3 watchdog
   ```

2. Configure the script with your Wasabi credentials and target folder:
   - `wasabi_access_key`: Your Wasabi access key.
   - `wasabi_secret_key`: Your Wasabi secret key.
   - `wasabi_endpoint`: The Wasabi endpoint URL.
   - `wasabi_bucket`: The name of your Wasabi bucket.
   - `documents_folder`: The local folder you wish to synchronize with Wasabi.

3. Ensure the Wasabi bucket exists and versioning is enabled.

4. Run the script in a Python environment.

## Functionality

- **File Upload:** Detects new or modified files in the specified local folder and uploads them to Wasabi.
- **File Deletion:** Deletes files from Wasabi, the local disk, and the local database when removed from the local folder.
- **File Download:** Downloads updates from Wasabi to the local folder during synchronization.
- **Initial Synchronization:** Performs an initial sync between Wasabi and the local folder at startup.
- **Continuous Monitoring:** Uses `watchdog` to monitor the local folder for changes and synchronize in real-time.

## How It Works

1. **Database Initialization:** Creates a SQLite database for tracking file states (hashes, modification times).
2. **Versioning Configuration:** Enables versioning on the specified Wasabi bucket to maintain file history.
3. **Event Handling:** Responds to file modifications and deletions in the local folder by updating Wasabi and the local database.
4. **Synchronization:** Compares the local folder's state to Wasabi's, downloading missing files or updates and removing extraneous files.

## Limitations

- The script assumes all files in the local directory should be synced with Wasabi. There's no mechanism for ignoring specific files or directories.
- It requires manual setup of Wasabi credentials and target directories within the script.
- Error handling is minimal, focusing on printing errors rather than recovering from them.
