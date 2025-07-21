
# Photo & Video Organizer

A robust graphical user interface (GUI) application designed to help you organize your digital photo and video collection effortlessly. This tool automatically sorts your media files into a structured folder system based on their date, identifies potential duplicates, handles various file formats, and isolates problematic files for your review.

---

## Features

* **Intelligent Organization:**
    * **Date-Based Sorting:** Automatically organizes your photos and videos into a `YYYY` (Year) or `YYYY/MM` (Year/Month) folder structure based on the date the media was taken (preferring EXIF data for images, or file modification date as a fallback).
    * **Dedicated Video Folder:** All video files are neatly separated and organized into their own `Videos` directory, using the same date-based structure.
* **Comprehensive File Support:**
    * **Directly Supported Image Formats:** Handles `.jpg`, `.jpeg`, and `.png` files directly.
    * **Convertible Image Formats:** Converts common RAW formats (`.cr2`, `.raw`), `.tif`/`.tiff`, and `.heic` (High-Efficiency Image Container) files into `.jpg` format before organization, ensuring wider compatibility and smaller file sizes.
* **Duplicate Detection:**
    * Utilizes perceptual hashing to identify "suspect" duplicate images, even if they've been resized or slightly modified.
    * Moves these potential duplicates to a designated `Suspect Duplicates` folder for your manual review, preventing unnecessary clutter in your main organized folders.
* **Error Handling & Problem Isolation:**
    * If a file causes an error during processing (e.g., corrupted file, unreadable data), it will be **copied** to a dedicated `Errors` folder. This ensures that no original files are lost or left unhandled, and you have a centralized place to review and address any issues.
* **Unrecognized File Handling:**
    * Any files that are not identified as standard image or video formats are copied to a `Manually Check` folder, allowing you to review and categorize them yourself.
* **Real-time Progress & Logging:**
    * Features a user-friendly GUI with progress bars for the current file being processed and the overall task completion.
    * Provides a detailed summary log (`photo_organizer_log.txt`) in the destination directory upon completion, outlining all actions taken, including files copied, converted, duplicates found, and any errors encountered.

---

## Requirements

* **Python 3.x:** The application is built with Python.
* **Libraries:** The following Python libraries are required:
    * `Pillow` (PIL)
    * `rawpy`
    * `imageio`
    * `piexif`
    * `pillow-heif`
    * `imagehash`
    * `Tkinter` (usually included with standard Python installations)

---

## Installation

1.  **Install Python:** If you don't have Python installed, download and install the latest version from [python.org](https://www.python.org/downloads/). Ensure you check the "Add Python to PATH" option during installation.
2.  **Install Required Libraries:** Open your terminal or command prompt and run the following command:
    ```bash
    pip install pillow rawpy imageio piexif pillow-heif imagehash
    ```
    *(Tkinter is typically included with Python; no separate installation is usually needed.)*
3.  **Download the Script:** Save the provided `photo_organizer.py` (or similar name if you've renamed it) file to your desired location.

---

## Usage

1.  **Run the Application:**
    Open your terminal or command prompt, navigate to the directory where you saved the script, and run it using:
    ```bash
    python photo_organizer.py
    ```
    A "Photo & Video Organizer" GUI window will appear.

2.  **Select Source Directory:**
    Click the "Browse" button next to "Source Directory" and select the folder containing all the photos and videos you wish to organize.

3.  **Select Destination Directory:**
    Click the "Browse" button next to "Destination Directory" and choose an empty (or existing) folder where you want your organized files to be placed. The script will create subfolders within this directory.

4.  **Choose Organization Structure:**
    Select your preferred folder structure:
    * **Year (YYYY):** Files will be organized into folders named after the year (e.g., `2023`).
    * **Year/Month (YYYY/MM):** Files will be organized into subfolders by month within each year (e.g., `2023/01`).

5.  **Start Organizing:**
    Click the "Start Organizing" button.
    * The GUI will update with progress bars and a live summary of files being processed, converted, copied, and any errors encountered.
    * The script will scan your source directory, process files, and copy them to the appropriate folders in your destination.
    * Upon completion, a summary log file (`photo_organizer_log.txt`) will be created in your destination directory, providing a detailed breakdown of the operation.

---

## Acknowledgments

* This application leverages several open-source Python libraries for image processing, hashing, and GUI development.

---

## License

This project is licensed under the MIT License.
````
