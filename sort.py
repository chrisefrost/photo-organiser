# This script converts images with CR2, RAW, TIF, HEIC and JPEG extension to JPG. It then moves the file into a yy/dd folder based on the EXIF data. If EXIF data doesnt exist it creates it based on the original creation of the file. A summary of actions is saved in log.txt

#The script in sort.py requires the following libraries:
    # os: For interacting with the operating system, such as navigating directories and handling file paths.
    # rawpy: For processing raw image files.
    # imageio: For reading and writing images.
    # PIL (or Pillow): For image processing tasks.
    # ExifTags from PIL: For handling EXIF data in images.
    # piexif: For handling EXIF data in JPEG and TIFF files.
    # datetime: For working with date and time.
    # shutil: For high-level file operations, such as moving files.
    # pillow_heif: For handling HEIC files.
    
    # To install the above libraries run the following command
    # pip install rawpy imageio pillow piexif pillow_heif

# Change line 186 to where your photos are stored and run this script from the same directory


import os
import rawpy
import imageio
from PIL import Image, ExifTags
import piexif
from datetime import datetime
from shutil import move
import pillow_heif

# Counters for logging
log_data = {
    'files_moved': 0,
    'files_converted': {
        'cr2': 0,
        'raw': 0,
        'tif': 0,
        'jpeg': 0,
        'heic': 0
    },
    'errors': []
}

# Function to copy file system dates and EXIF data
def copy_file_dates_and_exif(src, dst):
    """Copy file system dates and EXIF data from source to destination file."""
    try:
        # Copy file system dates from src to dst
        stat_info = os.stat(src)
        os.utime(dst, (stat_info.st_atime, stat_info.st_mtime))

        # Copy EXIF data from src to dst if it exists
        if src.lower().endswith(('.jpg', '.jpeg', '.tiff', '.tif')):
            original_exif = piexif.load(src)
            piexif.insert(piexif.dump(original_exif), dst)
    except Exception as e:
        error_message = f"Failed to copy EXIF data for {src}: {e}"
        log_data['errors'].append(error_message)
        print(error_message)

# Function to convert images to JPEG
def convert_to_jpg(input_path, output_path):
    """Convert image files to JPEG format, handling RAW, TIFF, and HEIC files."""
    try:
        if input_path.lower().endswith('.cr2'):
            with rawpy.imread(input_path) as raw:
                rgb = raw.postprocess()
                imageio.imwrite(output_path, rgb, format='jpeg')
                log_data['files_converted']['cr2'] += 1
        elif input_path.lower().endswith('.raw'):
            with rawpy.imread(input_path) as raw:
                rgb = raw.postprocess()
                imageio.imwrite(output_path, rgb, format='jpeg')
                log_data['files_converted']['raw'] += 1
        elif input_path.lower().endswith(('.tif', '.tiff')):
            with Image.open(input_path) as img:
                rgb_img = img.convert('RGB')
                rgb_img.save(output_path, format='JPEG', quality=95)
                log_data['files_converted']['tif'] += 1
        elif input_path.lower().endswith('.heic'):
            try:
                heif_file = pillow_heif.open_heif(input_path)
                image = Image.frombytes(
                    heif_file.mode, 
                    heif_file.size, 
                    heif_file.data,
                    "raw",
                    heif_file.mode,
                    heif_file.stride,
                )
                image.save(output_path, format='JPEG', quality=95)
                log_data['files_converted']['heic'] += 1
            except Exception as e:
                error_message = f"Failed to process HEIC file {input_path}: {e}"
                log_data['errors'].append(error_message)
                print(error_message)
                return
        else:
            print(f"Unsupported file format for {input_path}")
            return

        # Copy file dates and EXIF data
        copy_file_dates_and_exif(input_path, output_path)
    except Exception as e:
        error_message = f"Failed to process file {input_path}: {e}"
        log_data['errors'].append(error_message)
        print(error_message)

# Function to convert images in a directory
def convert_images_in_directory(directory):
    """Convert all supported image files in the given directory to JPEG format."""
    if not os.path.exists(directory):
        print(f"Error: The directory {directory} does not exist.")
        return

    for root, _, files in os.walk(directory):
        for file in files:
            input_path = os.path.join(root, file)
            output_path = os.path.splitext(input_path)[0] + '.jpg'
            if input_path.lower().endswith(('.cr2', '.raw', '.tif', '.tiff', '.heic')):
                convert_to_jpg(input_path, output_path)

# Function to extract date taken from EXIF data
def get_date_taken(exif_data):
    """Extract the date taken from EXIF data."""
    for tag, value in exif_data.items():
        decoded = ExifTags.TAGS.get(tag, tag)
        if decoded == "DateTimeOriginal":
            return value
    return None

# Function to create folders and move files
def create_folders_and_move_files(directory):
    """Organize JPEG files into folders based on the year and month of the date taken."""
    if not os.path.exists(directory):
        print(f"Error: The directory {directory} does not exist.")
        return

    files = [f for f in os.listdir(directory) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

    for file in files:
        file_path = os.path.join(directory, file)
        try:
            with Image.open(file_path) as img:
                exif_data = img._getexif() or {}
            date_taken_str = get_date_taken(exif_data)

            if date_taken_str:
                try:
                    date_taken = datetime.strptime(date_taken_str, '%Y:%m:%d %H:%M:%S')
                except ValueError as e:
                    date_taken = datetime.fromtimestamp(os.path.getmtime(file_path))
                    error_message = f"EXIF date parsing error for {file}: {e}. Used file modification date."
                    log_data['errors'].append(error_message)
                    print(error_message)
            else:
                date_taken = datetime.fromtimestamp(os.path.getmtime(file_path))

            year = date_taken.strftime('%Y')
            month = date_taken.strftime('%m')

            year_folder_path = os.path.join(directory, year)
            if not os.path.exists(year_folder_path):
                os.makedirs(year_folder_path)

            month_folder_path = os.path.join(year_folder_path, month)
            if not os.path.exists(month_folder_path):
                os.makedirs(month_folder_path)

            new_file_path = os.path.join(month_folder_path, file)
            original_base = file.rsplit('.', 1)[0]
            extension = file.rsplit('.', 1)[1]
            counter = 1
            while os.path.exists(new_file_path):
                new_file_path = os.path.join(month_folder_path, f"{original_base}_{counter}.{extension}")
                counter += 1

            move(file_path, new_file_path)
            log_data['files_moved'] += 1
            print(f"Moved '{file}' to '{new_file_path}'")

        except Exception as e:
            error_message = f"Error processing file {file}: {str(e)}"
            log_data['errors'].append(error_message)
            print(error_message)

# Example usage
directory = '/photos'  # Update this path to your images directory
convert_images_in_directory(directory)
create_folders_and_move_files(directory)

# Write log data to log.txt
with open('log.txt', 'w') as log_file:
    log_file.write(f"Files moved: {log_data['files_moved']}\n")
    log_file.write("Files converted:\n")
    for file_type, count in log_data['files_converted'].items():
        log_file.write(f"  {file_type}: {count}\n")
    log_file.write("Errors:\n")
    for error in log_data['errors']:
        log_file.write(f"  {error}\n")
