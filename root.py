# This script moves all files in all subdirectories into the a named directory
# Change line 57 to the root of your subdirectories


import os
import shutil

def move_files_to_root(root_folder):
    files_moved = 0
    files_renamed = 0
    errors = 0
    
    log_file_path = os.path.join(root_folder, "log.txt")
    
    with open(log_file_path, 'w') as log_file:
        log_file.write("Move Files to Root Folder Log\n")
        log_file.write("============================\n\n")
        
        # Iterate over all files and directories in the root folder
        for root, dirs, files in os.walk(root_folder):
            for file in files:
                file_path = os.path.join(root, file)
                # Calculate the destination path in the root folder
                destination_path = os.path.join(root_folder, file)
                try:
                    if not os.path.exists(destination_path):
                        shutil.move(file_path, destination_path)
                        files_moved += 1
                    else:
                        # If the file exists, append a number to the filename to avoid overwriting
                        base, extension = os.path.splitext(file)
                        counter = 1
                        new_destination_path = os.path.join(root_folder, f"{base}_{counter}{extension}")
                        while os.path.exists(new_destination_path):
                            counter += 1
                            new_destination_path = os.path.join(root_folder, f"{base}_{counter}{extension}")
                        shutil.move(file_path, new_destination_path)
                        files_renamed += 1
                except Exception as e:
                    errors += 1
                    log_file.write(f"Error moving file {file_path} to {destination_path}: {e}\n")

        # Delete the now empty directories
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            try:
                os.rmdir(dir_path)
            except OSError:
                pass  # Directory is not empty, skip it
        
        log_file.write(f"\nSummary:\n")
        log_file.write(f"Total files moved: {files_moved}\n")
        log_file.write(f"Total files renamed due to duplicates: {files_renamed}\n")
        log_file.write(f"Total errors: {errors}\n")

if __name__ == "__main__":
    root_folder = '/test'
    move_files_to_root(root_folder)
    print("Files moved to root folder successfully. Check log.txt for details.")
