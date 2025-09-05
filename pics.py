import os
import shutil
from datetime import datetime
from PIL import Image, ExifTags
import piexif
import imagehash
import rawpy
import imageio
import pillow_heif # For HEIC support
import streamlit as st
import tempfile

# --- File Extensions Definitions ---
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png')
CONVERTIBLE_IMAGE_EXTENSIONS = ('.cr2', '.raw', '.tif', '.tiff', '.heic')
ALL_IMAGE_EXTENSIONS = IMAGE_EXTENSIONS + CONVERTIBLE_IMAGE_EXTENSIONS
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv') # Added common video formats

# --- Helper Functions (modified for Streamlit) ---

def convert_to_jpg(input_path, output_path):
    """Convert image files to JPEG format, handling RAW, TIFF, and HEIC files."""
    try:
        if input_path.lower().endswith(('.cr2', '.raw')):
            with rawpy.imread(input_path) as raw:
                rgb = raw.postprocess()
                imageio.imwrite(output_path, rgb, format='jpeg')
        elif input_path.lower().endswith(('.tif', '.tiff')):
            with Image.open(input_path) as img:
                rgb_img = img.convert('RGB')
                rgb_img.save(output_path, format='JPEG', quality=95)
        elif input_path.lower().endswith('.heic'):
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
        
        # Copy EXIF data from original to new JPG
        try:
            if input_path.lower().endswith(CONVERTIBLE_IMAGE_EXTENSIONS):
                original_exif = piexif.load(input_path)
                piexif.insert(piexif.dump(original_exif), output_path)
        except Exception:
            pass # Ignore if no EXIF data is found or an error occurs

        return True
    except Exception as e:
        st.session_state['log_data']['errors'].append(f"Failed to process file {os.path.basename(input_path)} for conversion: {e}")
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
                    return datetime.strptime(date_taken_str, '%Y:%m:%d %H:%M:%S')
            except Exception:
                pass # Fallback to modification date if EXIF fails
        return datetime.fromtimestamp(os.path.getmtime(file_path))
    except Exception as e:
        st.session_state['log_data']['errors'].append(f"Error getting date for {os.path.basename(file_path)}: {e}. Using current time.")
        return datetime.now()

def calculate_image_hash(image_path):
    """Calculate the perceptual hash of an image."""
    try:
        with Image.open(image_path) as img:
            if img.mode not in ('RGB', 'RGBA', 'L'):
                img = img.convert('RGB')
            return imagehash.average_hash(img)
    except Exception as e:
        st.session_state['log_data']['errors'].append(f"Error calculating hash for {os.path.basename(image_path)}: {e}")
        return None

# --- Core Photo Organization Logic (modified for Streamlit) ---
def organize_photos_core(source_dir, destination_dir, structure_choice):
    """Core logic to organize photos and videos, designed to be called by Streamlit."""
    
    # Initialize session state for logging if it's not already
    if 'log_data' not in st.session_state:
        st.session_state['log_data'] = {
            'files_copied': 0,
            'files_converted': {'cr2': 0, 'raw': 0, 'tif': 0, 'jpeg': 0, 'heic': 0},
            'videos_copied': 0,
            'suspect_duplicates_copied': 0,
            'manually_checked_files': 0,
            'files_moved_to_errors': 0,
            'errors': []
        }

    log_data = st.session_state['log_data']
    copied_file_hashes = set()

    # Pre-scan for total files
    all_files = []
    for root, _, files in os.walk(source_dir):
        all_files.extend([os.path.join(root, f) for f in files])
    total_files = len(all_files)

    st.write(f"Found {total_files} files to process.")
    
    # Create progress bars and status text
    overall_progress_bar = st.progress(0, text="Overall progress: 0/0 files processed (0.0%)")
    status_text = st.empty()
    
    # Create special directories
    suspect_duplicates_dir = os.path.join(destination_dir, "Suspect Duplicates")
    os.makedirs(suspect_duplicates_dir, exist_ok=True)
    videos_base_dir = os.path.join(destination_dir, "Videos")
    os.makedirs(videos_base_dir, exist_ok=True)
    manually_check_dir = os.path.join(destination_dir, "Manually Check")
    os.makedirs(manually_check_dir, exist_ok=True)
    errors_dir = os.path.join(destination_dir, "Errors")
    os.makedirs(errors_dir, exist_ok=True)

    processed_files_count = 0
    for file_path in all_files:
        original_file_extension = os.path.splitext(file_path)[1].lower()
        temp_jpg_path = None
        
        status_text.info(f"Processing: {os.path.basename(file_path)}")

        try:
            file_to_process_path = file_path 
            
            if original_file_extension in ALL_IMAGE_EXTENSIONS:
                if original_file_extension in CONVERTIBLE_IMAGE_EXTENSIONS:
                    temp_jpg_path = os.path.join(tempfile.gettempdir(), os.path.basename(file_path) + '.jpg')
                    if not convert_to_jpg(file_path, temp_jpg_path):
                        raise Exception(f"Conversion failed for {file_path}")
                    file_to_process_path = temp_jpg_path
                
                image_hash = calculate_image_hash(file_to_process_path)
                if image_hash in copied_file_hashes:
                    dup_filename = os.path.basename(file_to_process_path)
                    suspect_dup_path = os.path.join(suspect_duplicates_dir, dup_filename)
                    shutil.copy2(file_to_process_path, suspect_dup_path)
                    log_data['suspect_duplicates_copied'] += 1
                    continue
                
                copied_file_hashes.add(image_hash)
                
                file_date = get_file_date(file_to_process_path)
                year = file_date.strftime('%Y')
                month = file_date.strftime('%m')
                target_folder_path = os.path.join(destination_dir, year, month) if structure_choice == 'YYYY/MM' else os.path.join(destination_dir, year)
                os.makedirs(target_folder_path, exist_ok=True)
                
                new_file_path = os.path.join(target_folder_path, os.path.basename(file_to_process_path))
                shutil.copy2(file_to_process_path, new_file_path)
                log_data['files_copied'] += 1
            
            elif original_file_extension in VIDEO_EXTENSIONS:
                file_date = get_file_date(file_path)
                year = file_date.strftime('%Y')
                month = file_date.strftime('%m')
                video_target_folder_path = os.path.join(videos_base_dir, year, month) if structure_choice == 'YYYY/MM' else os.path.join(videos_base_dir, year)
                os.makedirs(video_target_folder_path, exist_ok=True)
                
                new_file_path = os.path.join(video_target_folder_path, os.path.basename(file_path))
                shutil.copy2(file_path, new_file_path)
                log_data['videos_copied'] += 1
            
            else:
                misc_target_path = os.path.join(manually_check_dir, os.path.basename(file_path))
                shutil.copy2(file_path, misc_target_path)
                log_data['manually_checked_files'] += 1
        
        except Exception as e:
            error_target_path = os.path.join(errors_dir, os.path.basename(file_path))
            try:
                shutil.copy2(file_path, error_target_path)
                log_data['errors'].append(f"Error processing {os.path.basename(file_path)}: {e}. Copied to 'Errors' folder.")
                log_data['files_moved_to_errors'] += 1
            except Exception as copy_e:
                log_data['errors'].append(f"Error processing {os.path.basename(file_path)}: {e}. Failed to copy to 'Errors' folder due to: {copy_e}")
        
        finally:
            if temp_jpg_path and os.path.exists(temp_jpg_path):
                os.remove(temp_jpg_path)

        processed_files_count += 1
        overall_progress_bar.progress(processed_files_count / total_files, text=f"Overall progress: {processed_files_count}/{total_files} files processed ({processed_files_count/total_files*100:.1f}%)")

    status_text.success("Organization complete!")
    overall_progress_bar.progress(1.0, text="Organization complete!")

# --- Streamlit GUI ---
st.set_page_config(page_title="Photo & Video Organizer", layout="wide")

st.title("📸 Photo & Video Organizer")
st.write("A robust tool to organize your digital media collection.")

# --- Input Section ---
st.header("1. Enter Directories")
source_dir = st.text_input("Source Directory", help="Enter the full path to the folder containing your photos and videos.")
destination_dir = st.text_input("Destination Directory", help="Enter the full path to the folder where you want to save the organized files.")

# --- Options Section ---
st.header("2. Choose Organization Structure")
structure_choice = st.radio("Organize files by:", ("Year (YYYY)", "Year/Month (YYYY/MM)"))
structure_choice = "YYYY" if structure_choice == "Year (YYYY)" else "YYYY/MM"

# --- Start Button ---
if st.button("🚀 Start Organizing"):
    if not source_dir or not destination_dir:
        st.error("Please enter both source and destination directories.")
    elif not os.path.isdir(source_dir):
        st.error(f"Source directory not found: {source_dir}")
    else:
        st.success("Starting organization... Please wait.")
        with st.spinner('Organizing files...'):
            organize_photos_core(source_dir, destination_dir, structure_choice)

# --- Summary and Logs Section ---
st.header("3. Summary and Logs")
if 'log_data' in st.session_state:
    log_data = st.session_state['log_data']
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📁 Processed Files")
        st.metric(label="Photos Copied", value=log_data['files_copied'])
        st.metric(label="Videos Copied", value=log_data['videos_copied'])
        st.metric(label="Suspect Duplicates", value=log_data['suspect_duplicates_copied'])
    
    with col2:
        st.subheader("⚠️ Problem Files")
        st.metric(label="Manually Check Files", value=log_data['manually_checked_files'])
        st.metric(label="Files Moved to Errors", value=log_data['files_moved_to_errors'])
    
    st.subheader("🔄 Files Converted to JPG")
    converted_details = [f"{ext.upper()}: {count}" for ext, count in log_data['files_converted'].items() if count > 0]
    st.write(f"Total: {sum(log_data['files_converted'].values())}")
    st.write(", ".join(converted_details) if converted_details else "None")

    if log_data['errors']:
        st.subheader("❌ Errors Encountered")
        for error in log_data['errors']:
            st.error(error)
    else:
        st.success("No errors reported during the process.")