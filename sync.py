import os
import hashlib
import sqlite3
import boto3
from botocore.exceptions import ClientError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


# Wasabi configuration
wasabi_access_key = 'KEY'
wasabi_secret_key = 'KEY'
wasabi_endpoint = 'https://s3.wasabisys.com'
wasabi_bucket = 'BUCKET'

# Local folder to watch
documents_folder = '/users/FOLDER'

# SQLite database file
db_file = 'file_tracking.db'

# Create a Wasabi S3 client
session = boto3.Session(
    aws_access_key_id=wasabi_access_key,
    aws_secret_access_key=wasabi_secret_key
)
s3 = session.client('s3', endpoint_url=wasabi_endpoint)

# Enable versioning on the Wasabi bucket (if not already enabled)
try:
    print("Enabling versioning on the Wasabi bucket...")
    s3.put_bucket_versioning(
        Bucket=wasabi_bucket,
        VersioningConfiguration={'Status': 'Enabled'}
    )
    print("Versioning enabled successfully.")
except ClientError as e:
    print(f"Error enabling versioning: {e}")

# Create a connection to the SQLite database
conn = sqlite3.connect(db_file)
cursor = conn.cursor()
print("Connected to SQLite database.")

# Create the files table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS files (
        object_key TEXT PRIMARY KEY,
        file_hash TEXT,
        modified_time REAL
    )
''')
conn.commit()
print("Files table created or already exists.")


# Function to calculate the SHA-256 hash of a file
def calculate_hash(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


# Function to check if a file needs to be uploaded based on modification time
def should_upload(file_path):
    file_name = os.path.basename(file_path)
    object_key = file_name
    modified_time = os.path.getmtime(file_path)

    cursor.execute('SELECT modified_time FROM files WHERE object_key = ?', (object_key,))
    result = cursor.fetchone()

    if result is None or result[0] < modified_time:
        print(f"File '{file_path}' needs to be uploaded.")
        return True
    else:
        print(f"File '{file_path}' is already up to date.")
        return False


# Function to upload a file to Wasabi with versioning
def upload_file(file_path):
    try:
        file_name = os.path.basename(file_path)
        object_key = file_name
        file_hash = calculate_hash(file_path)
        modified_time = os.path.getmtime(file_path)

        print(f"Uploading file '{file_path}' to Wasabi...")
        s3.upload_file(file_path, wasabi_bucket, object_key)
        print(f"File '{file_path}' uploaded successfully.")

        # Create a new SQLite connection and cursor within the thread
        thread_conn = sqlite3.connect(db_file)
        thread_cursor = thread_conn.cursor()

        thread_cursor.execute('REPLACE INTO files (object_key, file_hash, modified_time) VALUES (?, ?, ?)',
                              (object_key, file_hash, modified_time))
        thread_conn.commit()

        # Close the thread-specific connection
        thread_conn.close()
    except ClientError as e:
        print(f"Error uploading file '{file_path}': {e}")


# Function to delete a file from Wasabi, local disk, and the database
def delete_file(file_path):
    try:
        file_name = os.path.basename(file_path)
        object_key = file_name

        print(f"Deleting file '{object_key}' from Wasabi...")
        s3.delete_object(Bucket=wasabi_bucket, Key=object_key)
        print(f"File '{object_key}' deleted successfully from Wasabi.")

        # Delete the file from the local disk
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"File '{file_path}' deleted successfully from the local disk.")

        # Create a new SQLite connection and cursor within the thread
        thread_conn = sqlite3.connect(db_file)
        thread_cursor = thread_conn.cursor()

        thread_cursor.execute('DELETE FROM files WHERE object_key = ?', (object_key,))
        thread_conn.commit()

        # Close the thread-specific connection
        thread_conn.close()
        print(f"File '{object_key}' deleted successfully from the database.")
    except ClientError as e:
        print(f"Error deleting file '{object_key}': {e}")


# Function to download a file from Wasabi to the local disk
def download_file(object_key, modified_time):
    try:
        local_file_path = os.path.join(documents_folder, object_key)
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

        print(f"Downloading file '{object_key}' from Wasabi...")
        s3.download_file(wasabi_bucket, object_key, local_file_path)
        print(f"File '{object_key}' downloaded successfully to '{local_file_path}'.")

        # Update the file modification time
        os.utime(local_file_path, (modified_time, modified_time))

        # Create a new SQLite connection and cursor within the thread
        thread_conn = sqlite3.connect(db_file)
        thread_cursor = thread_conn.cursor()

        file_hash = calculate_hash(local_file_path)
        thread_cursor.execute('REPLACE INTO files (object_key, file_hash, modified_time) VALUES (?, ?, ?)',
                              (object_key, file_hash, modified_time))
        thread_conn.commit()

        # Close the thread-specific connection
        thread_conn.close()
    except ClientError as e:
        print(f"Error downloading file '{object_key}': {e}")


# Function to sync changes from Wasabi to the local folder
def sync_from_wasabi():
    print("Syncing changes from Wasabi to the local folder...")

    # Get the list of objects in the Wasabi bucket
    wasabi_objects = []
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=wasabi_bucket):
        for obj in page.get('Contents', []):
            wasabi_objects.append((obj['Key'], obj['LastModified'].timestamp()))

    # Get the list of files in the local folder
    local_files = set()
    for root, dirs, files in os.walk(documents_folder):
        for file in files:
            file_path = os.path.relpath(os.path.join(root, file), documents_folder)
            local_files.add(file_path.replace('\\', '/'))

    # Compare the lists and sync the changes
    for object_key, modified_time in wasabi_objects:
        if object_key not in local_files:
            download_file(object_key, modified_time)
        else:
            local_files.remove(object_key)

    # Delete files that exist locally but not in Wasabi
    for file_path in local_files:
        delete_file(os.path.join(documents_folder, file_path))

    print("Sync from Wasabi completed.")


# Function to handle file system events
def on_modified(event):
    if not event.is_directory:
        file_path = event.src_path
        print(f"File modified: {file_path}")
        if os.path.exists(file_path):
            upload_file(file_path)
        else:
            print(f"File '{file_path}' not found. Skipping upload.")


def on_deleted(event):
    if not event.is_directory:
        file_path = event.src_path
        print(f"File deleted: {file_path}")
        delete_file(file_path)


# Create an event handler and observer
event_handler = FileSystemEventHandler()
event_handler.on_modified = on_modified
event_handler.on_deleted = on_deleted
observer = Observer()
observer.schedule(event_handler, documents_folder, recursive=True)

# Start the observer
print("Starting the file system observer...")
observer.start()

# Perform an initial sync
print("Performing initial sync...")
sync_from_wasabi()
print("Initial sync completed.")

# Keep the script running
print("Watching for file changes. Press Ctrl+C to stop.")
try:
    while True:
        pass
except KeyboardInterrupt:
    print("Stopping the file system observer...")
    observer.stop()

    # Clean up
    observer.join()
    conn.close()
    print("Script execution completed.")
