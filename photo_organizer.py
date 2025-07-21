import os
import shutil
from datetime import datetime
from PIL import Image, ExifTags
import piexif
import imagehash
import rawpy
import imageio
import pillow_heif # For HEIC support
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import threading
import sys
import time # For simulating work/sleep in chunk copy

# --- Global logging data ---
log_data = {
    'files_copied': 0, # Main organized photos
    'files_converted': { # Converted to JPG before being copied
        'cr2': 0,
        'raw': 0,
        'tif': 0,
        'jpeg': 0,
        'heic': 0
    },
    'videos_copied': 0, # Organized video files
    'suspect_duplicates_copied': 0, # Duplicates copied to 'Suspect Duplicates'
    'manually_checked_files': 0, # Files copied to 'Manually Check'
    'files_moved_to_errors': 0, # NEW: Files moved to 'Errors' folder
    'errors': []
}

# --- File Extensions Definitions ---
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png')
CONVERTIBLE_IMAGE_EXTENSIONS = ('.cr2', '.raw', '.tif', '.tiff', '.heic')
ALL_IMAGE_EXTENSIONS = IMAGE_EXTENSIONS + CONVERTIBLE_IMAGE_EXTENSIONS
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv') # Added common video formats

# --- Custom File Copy with Progress ---
CHUNK_SIZE = 1024 * 1024 # 1 MB chunks

def copy_file_with_progress(src, dst, current_file_progress_callback):
    """
    Copies a file from src to dst in chunks, updating a progress callback.
    Returns True on success, False on failure.
    """
    try:
        total_size = os.path.getsize(src)
        bytes_copied = 0

        with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
            while True:
                chunk = fsrc.read(CHUNK_SIZE)
                if not chunk:
                    break
                fdst.write(chunk)
                bytes_copied += len(chunk)
                
                # Calculate percentage and update GUI
                percentage = (bytes_copied / total_size) * 100
                current_file_progress_callback(percentage, os.path.basename(src))
        
        # Ensure final update is 100%
        current_file_progress_callback(100, os.path.basename(src))
        
        # Copy metadata after content is copied
        shutil.copystat(src, dst) # Copies permission bits, last access time, last modification time, and flags.
        
        # If it's an image, try to copy EXIF separately too
        if src.lower().endswith(IMAGE_EXTENSIONS) or src.lower().endswith(('.tif', '.tiff')):
            try:
                original_exif = piexif.load(src)
                piexif.insert(piexif.dump(original_exif), dst)
            except piexif.InvalidImageDataError:
                pass # No valid EXIF data found, skip
            except Exception as e:
                log_data['errors'].append(f"Unexpected error loading/inserting EXIF for {src}: {e}")

        return True

    except Exception as e:
        error_message = f"Failed to copy file {src} to {dst}: {e}"
        log_data['errors'].append(error_message)
        current_file_progress_callback(0, f"Error with {os.path.basename(src)}") # Reset or show error
        return False

# --- Helper Functions (modified to integrate with progress/error logging) ---

def convert_to_jpg(input_path, output_path, current_file_progress_callback):
    """Convert image files to JPEG format, handling RAW, TIFF, and HEIC files."""
    current_file_progress_callback(0, f"Converting: {os.path.basename(input_path)}...") # Indicate conversion start
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
                error_message = f"Failed to process HEIC file {input_path} for conversion: {e}"
                log_data['errors'].append(error_message)
                return False
        else:
            return False # Should not happen if called correctly

        # Note: copy_file_dates_and_exif logic is now largely integrated into copy_file_with_progress
        # but for conversions, we still need to ensure EXIF is transferred if the source had it
        # and the output is a JPG (which imageio.imwrite should handle by default for simple cases)
        # However, for full EXIF copy from original RAW/HEIC to new JPG, piexif is needed
        try:
            # Load EXIF from original file if possible and insert into new JPG
            if input_path.lower().endswith(CONVERTIBLE_IMAGE_EXTENSIONS):
                if piexif.is_exif(input_path): # Check if source has EXIF
                    original_exif = piexif.load(input_path)
                    piexif.insert(piexif.dump(original_exif), output_path)
        except Exception as e:
             log_data['errors'].append(f"Failed to copy EXIF data from {input_path} to {output_path} after conversion: {e}")

        return True
    except Exception as e:
        error_message = f"Failed to process file {input_path} for conversion: {e}"
        log_data['errors'].append(error_message)
        return False

def get_file_date(file_path):
    """
    Extracts date taken for images (preferring EXIF) or uses file modification date for others.
    Returns a datetime object.
    """
    try:
        if file_path.lower().endswith(ALL_IMAGE_EXTENSIONS):
            try:
                with Image.open(file_path) as img:
                    exif_data = img._getexif() or {}
                date_taken_str = None
                for tag, value in exif_data.items():
                    decoded = ExifTags.TAGS.get(tag, tag)
                    if decoded == "DateTimeOriginal":
                        date_taken_str = value
                        break

                if date_taken_str:
                    try:
                        return datetime.strptime(date_taken_str, '%Y:%m:%d %H:%M:%S')
                    except ValueError:
                        return datetime.fromtimestamp(os.path.getmtime(file_path))
            except Exception as e:
                return datetime.fromtimestamp(os.path.getmtime(file_path))
        
        return datetime.fromtimestamp(os.path.getmtime(file_path))
    except Exception as e:
        error_message = f"Error getting date for {file_path}: {e}. Using current time as fallback."
        log_data['errors'].append(error_message)
        return datetime.now()

def calculate_image_hash(image_path):
    """Calculate the perceptual hash of an image."""
    try:
        with Image.open(image_path) as img:
            if img.mode not in ('RGB', 'RGBA', 'L'):
                img = img.convert('RGB')
            return imagehash.average_hash(img)
    except Exception as e:
        log_data['errors'].append(f"Error calculating hash for {image_path}: {e}")
        return None

# --- Core Photo Organization Logic ---
def organize_photos_core(source_dir, destination_dir, structure_choice, 
                          overall_progress_callback, status_callback, 
                          current_file_progress_callback, summary_update_callback):
    """Core logic to organize photos and videos, runs in a separate thread."""
    global log_data
    log_data = { # Reset log data for each run
        'files_copied': 0,
        'files_converted': {
            'cr2': 0, 'raw': 0, 'tif': 0, 'jpeg': 0, 'heic': 0
        },
        'videos_copied': 0,
        'suspect_duplicates_copied': 0,
        'manually_checked_files': 0,
        'files_moved_to_errors': 0, # NEW: Reset for errors folder
        'errors': []
    }
    summary_update_callback() # Initial clear/update of summary

    status_callback("Starting photo and video organization...")

    if not os.path.isdir(source_dir):
        status_callback("Error: Invalid source directory provided.")
        return False

    if not os.path.exists(destination_dir):
        try:
            os.makedirs(destination_dir)
        except OSError as e:
            status_callback(f"Error creating destination directory {destination_dir}: {e}")
            return False
    elif not os.path.isdir(destination_dir):
        status_callback("Error: Destination path exists but is not a directory.")
        return False

    # Create special directories
    suspect_duplicates_dir = os.path.join(destination_dir, "Suspect Duplicates")
    if not os.path.exists(suspect_duplicates_dir):
        os.makedirs(suspect_duplicates_dir)

    videos_base_dir = os.path.join(destination_dir, "Videos")
    if not os.path.exists(videos_base_dir):
        os.makedirs(videos_base_dir)

    manually_check_dir = os.path.join(destination_dir, "Manually Check")
    if not os.path.exists(manually_check_dir):
        os.makedirs(manually_check_dir)

    errors_dir = os.path.join(destination_dir, "Errors") # NEW: Create Errors directory
    if not os.path.exists(errors_dir):
        os.makedirs(errors_dir)

    # Pre-scan for total files
    total_files = 0
    for root, _, files in os.walk(source_dir):
        total_files += len(files)

    status_callback(f"Found {total_files} files to process.")
    overall_progress_callback(0, total_files) # Initialize overall progress bar

    copied_file_hashes = set() # To track hashes of non-duplicate images
    processed_files_count = 0

    for root, _, files in os.walk(source_dir):
        for file in files:
            file_path = os.path.join(root, file)
            original_file_extension = os.path.splitext(file_path)[1].lower()
            temp_jpg_path = None # Used for converted files

            processed_files_count += 1
            overall_progress_callback(processed_files_count, total_files) # Update overall progress
            
            try:
                # Determine which path to process (original or temp_jpg_path after conversion)
                file_to_process_path = file_path 

                if original_file_extension in ALL_IMAGE_EXTENSIONS:
                    # --- Handle Image Files ---
                    if original_file_extension in CONVERTIBLE_IMAGE_EXTENSIONS:
                        temp_jpg_path = os.path.splitext(file_path)[0] + '.jpg'
                        if not convert_to_jpg(file_path, temp_jpg_path, current_file_progress_callback):
                            raise Exception(f"Conversion failed for {file_path}") # Raise to move to error handling
                        file_to_process_path = temp_jpg_path # Use the converted file for hashing/copying
                    
                    # Image Hashing and Duplicate Check
                    image_hash = calculate_image_hash(file_to_process_path)
                    if not image_hash: # If hash calculation failed
                         raise Exception(f"Failed to calculate hash for {file_to_process_path}") # Raise to move to error handling

                    if image_hash in copied_file_hashes:
                        # Suspect duplicate found, copy to 'Suspect Duplicates'
                        dup_filename = os.path.basename(file_to_process_path)
                        suspect_dup_path = os.path.join(suspect_duplicates_dir, dup_filename)
                        
                        base, ext = os.path.splitext(dup_filename)
                        counter = 1
                        while os.path.exists(suspect_dup_path):
                            dup_filename = f"{base}_{counter}{ext}"
                            suspect_dup_path = os.path.join(suspect_duplicates_dir, dup_filename)
                            counter += 1
                        
                        if copy_file_with_progress(file_to_process_path, suspect_dup_path, current_file_progress_callback):
                            log_data['suspect_duplicates_copied'] += 1
                            summary_update_callback()
                        continue # Skip to next file after copying duplicate

                    copied_file_hashes.add(image_hash) # Add hash for non-duplicates

                    # Organize image by date
                    file_date = get_file_date(file_to_process_path)
                    year = file_date.strftime('%Y')
                    month = file_date.strftime('%m')

                    if structure_choice == 'YYYY':
                        target_folder_path = os.path.join(destination_dir, year)
                    else:
                        target_folder_path = os.path.join(destination_dir, year, month)

                    if not os.path.exists(target_folder_path):
                        os.makedirs(target_folder_path)

                    filename_to_copy = os.path.basename(file_to_process_path)
                    new_file_path = os.path.join(target_folder_path, filename_to_copy)
                    original_base, extension = os.path.splitext(filename_to_copy)
                    counter = 1
                    while os.path.exists(new_file_path):
                        new_filename = f"{original_base}_{counter}{extension}"
                        new_file_path = os.path.join(target_folder_path, new_filename)
                        counter += 1

                    if copy_file_with_progress(file_to_process_path, new_file_path, current_file_progress_callback):
                        log_data['files_copied'] += 1
                        summary_update_callback()

                elif original_file_extension in VIDEO_EXTENSIONS:
                    # --- Handle Video Files ---
                    file_date = get_file_date(file_path)
                    year = file_date.strftime('%Y')
                    month = file_date.strftime('%m')

                    if structure_choice == 'YYYY':
                        video_target_folder_path = os.path.join(videos_base_dir, year)
                    else:
                        video_target_folder_path = os.path.join(videos_base_dir, year, month)

                    if not os.path.exists(video_target_folder_path):
                        os.makedirs(video_target_folder_path)

                    filename_to_copy = os.path.basename(file_path)
                    new_file_path = os.path.join(video_target_folder_path, filename_to_copy)
                    original_base, extension = os.path.splitext(filename_to_copy)
                    counter = 1
                    while os.path.exists(new_file_path):
                        new_filename = f"{original_base}_{counter}{extension}"
                        new_file_path = os.path.join(video_target_folder_path, new_filename)
                        counter += 1

                    if copy_file_with_progress(file_path, new_file_path, current_file_progress_callback):
                        log_data['videos_copied'] += 1
                        summary_update_callback()

                else:
                    # --- Handle Other Files (Manually Check) ---
                    misc_filename = os.path.basename(file_path)
                    misc_target_path = os.path.join(manually_check_dir, misc_filename)
                    
                    base, ext = os.path.splitext(misc_filename)
                    counter = 1
                    while os.path.exists(misc_target_path):
                        misc_filename = f"{base}_{counter}{ext}"
                        misc_target_path = os.path.join(manually_check_dir, misc_filename)
                        counter += 1

                    if copy_file_with_progress(file_path, misc_target_path, current_file_progress_callback):
                        log_data['manually_checked_files'] += 1
                        summary_update_callback()

            except Exception as e:
                # NEW: Copy problematic file to 'Errors' folder
                error_filename = os.path.basename(file_path)
                error_target_path = os.path.join(errors_dir, error_filename)
                
                base, ext = os.path.splitext(error_filename)
                counter = 1
                while os.path.exists(error_target_path):
                    error_filename = f"{base}_{counter}{ext}"
                    error_target_path = os.path.join(errors_dir, error_filename)
                    counter += 1

                try:
                    if copy_file_with_progress(file_path, error_target_path, current_file_progress_callback):
                        error_message = f"Error processing file {file_path}: {e}. Copied to 'Errors' folder: {os.path.basename(error_target_path)}"
                        log_data['files_moved_to_errors'] += 1
                    else:
                        error_message = f"Error processing file {file_path}: {e}. Failed to copy to 'Errors' folder."
                except Exception as copy_e:
                    error_message = f"Error processing file {file_path}: {e}. Also failed to copy to 'Errors' folder due to: {copy_e}"

                log_data['errors'].append(error_message)
                summary_update_callback() # Update summary to show new error

            finally:
                if temp_jpg_path and os.path.exists(temp_jpg_path):
                    try:
                        os.remove(temp_jpg_path)
                    except Exception as e:
                        log_data['errors'].append(f"Error removing temporary file {temp_jpg_path}: {e}")
                        summary_update_callback()

            current_file_progress_callback(100, "Done.") # Ensure current file bar is 100% after each file

    # Final progress update
    overall_progress_callback(total_files, total_files)
    current_file_progress_callback(100, "All files processed.")

    # Write summary to a log file in the destination directory
    log_file_path = os.path.join(destination_dir, 'photo_organizer_log.txt')
    with open(log_file_path, 'w') as log_file:
        log_file.write(f"Photo and Video Organization Summary ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
        log_file.write("=" * 60 + "\n\n")
        log_file.write(f"Source Directory: {source_dir}\n")
        log_file.write(f"Destination Directory: {destination_dir}\n")
        log_file.write(f"Organization Structure: {structure_choice}\n\n")

        log_file.write(f"--- Summary of Processed Files ---\n")
        log_file.write(f"Photos Copied to Organized Folders: {log_data['files_copied']}\n")
        log_file.write(f"Videos Copied to Organized Folders: {log_data['videos_copied']}\n")
        log_file.write(f"Suspect Duplicates Copied (Photos only): {log_data['suspect_duplicates_copied']}\n")
        log_file.write(f"Other Files Copied to 'Manually Check': {log_data['manually_checked_files']}\n")
        log_file.write(f"Files Moved to 'Errors' Folder: {log_data['files_moved_to_errors']}\n") # NEW: Add errors count
        
        log_file.write("\nFiles Converted (to JPG):\n")
        converted_count_total = sum(log_data['files_converted'].values())
        if converted_count_total > 0:
            for file_type, count in log_data['files_converted'].items():
                if count > 0:
                    log_file.write(f"  {file_type.upper()}: {count}\n")
        else:
            log_file.write("  None\n")

        log_file.write("\n--- Errors Encountered ---\n")
        if log_data['errors']:
            for error in log_data['errors']:
                log_file.write(f"- {error}\n")
        else:
            log_file.write("None\n")

    status_callback("\nPhoto and video organization complete!")
    messagebox.showinfo("Complete", f"Photo and video organization finished.\nA summary of actions has been saved to: {log_file_path}")
    return True

# --- GUI Application Class ---
class PhotoOrganizerGUI:
    def __init__(self, master):
        self.master = master
        master.title("Photo & Video Organizer")
        master.geometry("700x800") # Adjust size for new layout
        master.resizable(False, False)

        # Frame for input fields
        input_frame = tk.LabelFrame(master, text="Directories and Options", padx=15, pady=15)
        input_frame.pack(pady=10, padx=20, fill="x")

        # Source Directory
        tk.Label(input_frame, text="Source Directory:").grid(row=0, column=0, sticky="w", pady=5, padx=5)
        self.source_entry = tk.Entry(input_frame, width=50)
        self.source_entry.grid(row=0, column=1, pady=5, padx=5)
        tk.Button(input_frame, text="Browse", command=self.browse_source).grid(row=0, column=2, pady=5, padx=5)

        # Destination Directory
        tk.Label(input_frame, text="Destination Directory:").grid(row=1, column=0, sticky="w", pady=5, padx=5)
        self.destination_entry = tk.Entry(input_frame, width=50)
        self.destination_entry.grid(row=1, column=1, pady=5, padx=5)
        tk.Button(input_frame, text="Browse", command=self.browse_destination).grid(row=1, column=2, pady=5, padx=5)

        # Organization Structure
        tk.Label(input_frame, text="Organize by:").grid(row=2, column=0, sticky="w", pady=5, padx=5)
        self.structure_choice = tk.StringVar(value="YYYY/MM") # Default choice
        tk.Radiobutton(input_frame, text="Year (YYYY)", variable=self.structure_choice, value="YYYY").grid(row=2, column=1, sticky="w", pady=5, padx=5)
        tk.Radiobutton(input_frame, text="Year/Month (YYYY/MM)", variable=self.structure_choice, value="YYYY/MM").grid(row=3, column=1, sticky="w", pady=5, padx=5)

        # Start Button
        self.start_button = tk.Button(master, text="Start Organizing", command=self.start_organization_thread, height=2, width=30)
        self.start_button.pack(pady=15)

        # Current File Progress
        self.current_file_label_text = tk.StringVar(value="Current file progress: ")
        tk.Label(master, textvariable=self.current_file_label_text, wraplength=650).pack(pady=(0, 5))
        self.current_file_progress_bar = ttk.Progressbar(master, orient="horizontal", length=600, mode="determinate")
        self.current_file_progress_bar.pack(pady=(0, 10))

        # Overall Progress
        self.overall_progress_label_text = tk.StringVar(value="Overall progress: Ready to start...")
        tk.Label(master, textvariable=self.overall_progress_label_text, wraplength=650).pack(pady=(0, 5))
        self.overall_progress_bar = ttk.Progressbar(master, orient="horizontal", length=600, mode="determinate")
        self.overall_progress_bar.pack(pady=(0, 10))
        
        # Summary Output Area
        summary_frame = tk.LabelFrame(master, text="Summary", padx=10, pady=10)
        summary_frame.pack(pady=5, padx=20, fill="both", expand=True)

        self.photos_copied_text = tk.StringVar(value="Photos Copied: 0")
        tk.Label(summary_frame, textvariable=self.photos_copied_text, anchor='w').pack(fill='x')
        self.suspect_duplicates_text = tk.StringVar(value="Suspect Photo Duplicates: 0")
        tk.Label(summary_frame, textvariable=self.suspect_duplicates_text, anchor='w').pack(fill='x')
        self.videos_copied_text = tk.StringVar(value="Videos Copied: 0")
        tk.Label(summary_frame, textvariable=self.videos_copied_text, anchor='w').pack(fill='x')
        self.manually_checked_text = tk.StringVar(value="Other Files (Manually Check): 0")
        tk.Label(summary_frame, textvariable=self.manually_checked_text, anchor='w').pack(fill='x')
        self.files_moved_to_errors_text = tk.StringVar(value="Files Moved to Errors: 0") # NEW: Label for errors
        tk.Label(summary_frame, textvariable=self.files_moved_to_errors_text, anchor='w').pack(fill='x')
        self.converted_text = tk.StringVar(value="Files Converted: None")
        tk.Label(summary_frame, textvariable=self.converted_text, anchor='w').pack(fill='x')

        tk.Label(summary_frame, text="Errors:", anchor='w').pack(fill='x', pady=(10, 0))
        self.error_log_text = scrolledtext.ScrolledText(summary_frame, wrap=tk.WORD, width=70, height=5, font=("TkFixedFont", 10))
        self.error_log_text.pack(expand=True, fill="both")
        self.error_log_text.config(state='disabled') # Make read-only initially


    def browse_source(self):
        directory = filedialog.askdirectory()
        if directory:
            self.source_entry.delete(0, tk.END)
            self.source_entry.insert(0, directory)

    def browse_destination(self):
        directory = filedialog.askdirectory()
        if directory:
            self.destination_entry.delete(0, tk.END)
            self.destination_entry.insert(0, directory)

    def update_overall_progress_bar(self, current, total):
        """Updates the overall progress bar and percentage label."""
        if total > 0:
            percentage = (current / total) * 100
            self.overall_progress_bar['value'] = percentage
            self.overall_progress_label_text.set(f"Overall progress: {current}/{total} files processed ({percentage:.1f}%)")
        else:
            self.overall_progress_bar['value'] = 0
            self.overall_progress_label_text.set("Overall progress: No files to process.")

    def update_current_file_progress_bar(self, percentage, filename):
        """Updates the current file progress bar and label."""
        # Schedule update on the main Tkinter thread
        self.master.after(0, self._update_current_file_gui, percentage, filename)

    def _update_current_file_gui(self, percentage, filename):
        if filename.startswith("Converting:"):
            self.current_file_progress_bar.config(mode="indeterminate")
            self.current_file_progress_bar.start(10)
            self.current_file_label_text.set(f"Current file progress: {filename}")
        elif filename.startswith("Error"):
            self.current_file_progress_bar.stop()
            self.current_file_progress_bar['value'] = 0
            self.current_file_label_text.set(f"Current file progress: {filename}")
        elif percentage == 100 and filename == "Done.":
            self.current_file_progress_bar.stop()
            self.current_file_progress_bar['value'] = 100
            self.current_file_label_text.set(f"Current file progress: Done processing current file.")
        elif percentage == 100 and filename == "All files processed.":
            self.current_file_progress_bar.stop()
            self.current_file_progress_bar['value'] = 100
            self.current_file_label_text.set(f"Current file progress: All files processed.")
        else:
            self.current_file_progress_bar.config(mode="determinate")
            self.current_file_progress_bar.stop() # Stop indeterminate if it was running
            self.current_file_progress_bar['value'] = percentage
            self.current_file_label_text.set(f"Current file progress: Copying {filename} ({percentage:.1f}%)")

    def update_status_label(self, message):
        """Updates the main status label (now overall_progress_label_text)."""
        self.overall_progress_label_text.set(message)

    def update_summary_labels(self):
        """Dynamically updates the summary counts and errors."""
        self.master.after(0, self._update_summary_gui)

    def _update_summary_gui(self):
        self.photos_copied_text.set(f"Photos Copied: {log_data['files_copied']}")
        self.suspect_duplicates_text.set(f"Suspect Photo Duplicates: {log_data['suspect_duplicates_copied']}")
        self.videos_copied_text.set(f"Videos Copied: {log_data['videos_copied']}")
        self.manually_checked_text.set(f"Other Files (Manually Check): {log_data['manually_checked_files']}")
        self.files_moved_to_errors_text.set(f"Files Moved to Errors: {log_data['files_moved_to_errors']}") # NEW: Update errors count

        converted_details = []
        converted_total = 0
        for file_type, count in log_data['files_converted'].items():
            if count > 0:
                converted_details.append(f"{file_type.upper()}: {count}")
                converted_total += count
        
        if converted_total > 0:
            self.converted_text.set(f"Files Converted: {', '.join(converted_details)} (Total: {converted_total})")
        else:
            self.converted_text.set("Files Converted: None")

        self.error_log_text.config(state='normal')
        self.error_log_text.delete(1.0, tk.END)
        if log_data['errors']:
            for error in log_data['errors']:
                self.error_log_text.insert(tk.END, f"- {error}\n")
        else:
            self.error_log_text.insert(tk.END, "No errors reported during processing.\n")
        self.error_log_text.config(state='disabled')


    def start_organization_thread(self):
        source_dir = self.source_entry.get()
        destination_dir = self.destination_entry.get()
        structure_choice = self.structure_choice.get()

        if not source_dir or not destination_dir:
            messagebox.showerror("Input Error", "Please select both source and destination directories.")
            return

        # Clear previous summary and reset progress bars
        self.update_summary_labels() # Initial call to clear/reset summary labels
        self.error_log_text.config(state='normal')
        self.error_log_text.delete(1.0, tk.END)
        self.error_log_text.config(state='disabled')

        self.update_overall_progress_bar(0, 0)
        self.update_current_file_progress_bar(0, "Ready.") # Reset current file bar
        self.update_status_label("Starting...")

        # Disable buttons during processing
        self.start_button.config(state='disabled')
        self.source_entry.config(state='disabled')
        self.destination_entry.config(state='disabled')

        # Run the core logic in a separate thread to keep GUI responsive
        thread = threading.Thread(target=self.run_organizer, args=(source_dir, destination_dir, structure_choice))
        thread.start()

    def run_organizer(self, source_dir, destination_dir, structure_choice):
        try:
            organize_photos_core(source_dir, destination_dir, structure_choice, 
                                 self.update_overall_progress_bar, 
                                 self.update_status_label,
                                 self.update_current_file_progress_bar,
                                 self.update_summary_labels)
        finally:
            # Re-enable buttons after processing, scheduled on the main thread
            self.master.after(0, self.enable_gui_elements)

    def enable_gui_elements(self):
        self.start_button.config(state='normal')
        self.source_entry.config(state='normal')
        self.destination_entry.config(state='normal')
        self.overall_progress_label_text.set("Finished.")


# --- Main execution ---
if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoOrganizerGUI(root)
    root.mainloop()