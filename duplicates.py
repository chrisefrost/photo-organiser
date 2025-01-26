# This script checks the hash of an image to determine if its likely to be an duplicate. It will still identiy duplicates if they have been resized, and move them into a folder called duplicates

# The script in duplicates.py requires the following libraries:
    # os: For interacting with the operating system, such as navigating directories and handling file paths.
    # PIL (or Pillow): For image processing tasks.
    # imagehash: For calculating perceptual hashes of images.
    # shutil: For high-level file operations, such as moving files.
    
    # To install the above libraries run the following command
    # pip install pillow imagehash

# Change line 88 to where your photos are stored and run this script from the same directory    
    
import os
from PIL import Image
import imagehash
import shutil
from datetime import datetime

def get_image_files(directory):
    """ Get a list of jpg image files in the given directory and its subdirectories. """
    image_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('jpg'):
                image_files.append(os.path.join(root, file))
    return image_files

def calculate_image_hash(image_path):
    """ Calculate the perceptual hash of a jpg image. """
    try:
        with Image.open(image_path) as img:
            return imagehash.average_hash(img)
    except Exception as e:
        print(f"Error calculating hash for {image_path}: {e}")
        return None

def create_duplicates_directory(directory):
    """ Create a duplicates directory within the given directory. """
    duplicates_dir = os.path.join(directory, "duplicates")
    if not os.path.exists(duplicates_dir):
        os.makedirs(duplicates_dir)
    return duplicates_dir

def move_file_to_duplicates(original_path, duplicates_dir):
    """ Move a file to the duplicates directory, renaming it if necessary to avoid conflicts. """
    filename = os.path.basename(original_path)
    new_path = os.path.join(duplicates_dir, filename)
    if os.path.exists(new_path):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(new_path):
            new_filename = f"{base}_{counter}{ext}"
            new_path = os.path.join(duplicates_dir, new_filename)
            counter += 1
    shutil.move(original_path, new_path)
    return new_path

def find_and_move_duplicates(directory):
    """ Find and move duplicate jpg images in the given directory. """
    image_files = get_image_files(directory)
    hashes = {}
    duplicates = []

    duplicates_dir = create_duplicates_directory(directory)

    for image_path in image_files:
        image_hash = calculate_image_hash(image_path)
        if image_hash:
            if image_hash in hashes:
                # Compare the creation times
                existing_path = hashes[image_hash]
                if os.path.getctime(image_path) > os.path.getctime(existing_path):
                    duplicate_path = move_file_to_duplicates(image_path, duplicates_dir)
                    duplicates.append((image_path, existing_path, duplicate_path))
                else:
                    duplicate_path = move_file_to_duplicates(existing_path, duplicates_dir)
                    duplicates.append((existing_path, image_path, duplicate_path))
                    hashes[image_hash] = image_path  # Update to keep the earlier file
            else:
                hashes[image_hash] = image_path

    return duplicates

def create_summary(duplicates):
    """ Create a summary of actions taken, listing the original and new paths of moved duplicates. """
    summary = []
    if duplicates:
        summary.append("Summary of duplicate images moved:")
        for original, duplicate, new_path in duplicates:
            summary.append(f"{original} is a duplicate of {duplicate} and was moved to {new_path}")
    else:
        summary.append("No duplicate images found.")
    return summary

def main():
    directory = '/photos'
    duplicates = find_and_move_duplicates(directory)

    summary = create_summary(duplicates)
    for line in summary:
        print(line)

    # Save summary to a file
    summary_file = os.path.join(directory, "duplicates_summary.txt")
    with open(summary_file, "w") as f:
        for line in summary:
            f.write(line + "\n")

    print(f"\nSummary of actions has been saved to {summary_file}")

if __name__ == "__main__":
    main()
