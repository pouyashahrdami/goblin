import logging
import os
import time
import psutil
import telebot
from pathlib import Path
import rarfile  # For RAR handling (make sure you have `rarfile` installed: `pip install rarfile`)

# App Name : goblin
# Author : Pouya Shahrdami


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
MOVIE_EXTENSIONS = {".mp4"}
ARCHIVE_EXTENSIONS = {".zip", ".rar"}
# you can Create env file or paste the token here
API_TOKEN = os.getenv("TELEGRAM_API_TOKEN") or 'PASTE YOUR TOKEN HERE'
bot = telebot.TeleBot(API_TOKEN)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CHAT_ID = None
PROCESS_NAME = "python.exe"


# --- Command Handlers ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    global CHAT_ID
    CHAT_ID = message.chat.id
    start_message = """
    **Welcome goblin**

    Here are the commands you can use:

    * `/status` - Check if the required process is running.
    * `/giveme` - Send up to 10,000 images from a folder.
    * `/sendall` - Send ALL images from a folder (use with caution!).
    * `/goto` - Navigate and list subfolders.
    * `/movies` - Send movies from a specified folder.
    * `/sendfile` - Send a specific file by its full path.
    * `/files` - List files in a folder.
    * `/zip` - Send ZIP or RAR archives from a folder (recursively).

    **Important:**
    Always provide FULL paths (e.g., `D:\\Images\\Company`).
        """
    bot.reply_to(message, start_message, parse_mode="Markdown")


@bot.message_handler(commands=['status'])
def handle_status(message):
    bot.reply_to(message, "Process is running!" if check_process_status() else "Process not found.")


@bot.message_handler(commands=['giveme', 'sendall'])
def handle_send_images(message):
    if not check_process_status():
        bot.send_message(message.chat.id, "⚠️ Process not found.")
        return

    bot.send_message(message.chat.id, "Please enter the FULL path to the folder (e.g., D:\\Images\\Company):")
    bot.register_next_step_handler(message, lambda m: send_images_from_folder(m, message.text == "/sendall"))


def send_images_from_folder(message, send_all=False):
    folder_path = message.text.strip()
    images = find_images(folder_path)

    if images:
        num_sent = 0
        for image_path in images:
            try:
                bot.send_photo(message.chat.id, open(image_path, 'rb'))
                num_sent += 1
                time.sleep(1)  # Adjust delay as needed
                if not send_all and num_sent >= 10000:  # Limit to 10000 if not using /sendall
                    break
            except Exception as e:
                logger.error(f"Error sending '{image_path}': {e}")
        bot.send_message(message.chat.id, "✅ Done.")
    else:
        bot.send_message(message.chat.id, "⚠️ No images found in the specified folder.")


@bot.message_handler(commands=['goto'])
def handle_goto(message):
    bot.send_message(message.chat.id, "Please enter the FULL path to the folder or drive (e.g., D:\\Images or D:\\):")
    bot.register_next_step_handler(message, list_subfolders)


def list_subfolders(message):
    path = message.text.strip()
    if os.path.exists(path):
        subfolders = [f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))]
        if subfolders:
            bot.send_message(message.chat.id, "📁 \n".join(subfolders))
        else:
            bot.send_message(message.chat.id, "️️️️⚠️ No subfolders found.")
    else:
        bot.send_message(message.chat.id, "⚠️ Invalid path.")
    bot.send_message(message.chat.id, "✅ Done.")


@bot.message_handler(commands=['movies'])
def handle_send_movies(message):
    if not check_process_status():
        bot.send_message(message.chat.id, "⚠️ Process not found.")
        return

    bot.send_message(message.chat.id, "Please enter the FULL path to the folder containing movies:")
    bot.register_next_step_handler(message, lambda m: send_movies_from_folder(m))


@bot.message_handler(commands=['sendfile'])
def handle_send_file(message):
    if not check_process_status():
        bot.send_message(message.chat.id, "⚠️ Process not found.")
        return

    bot.send_message(message.chat.id, "Please enter the FULL path and filename to send:")
    bot.register_next_step_handler(message, send_specific_file)


def send_specific_file(message):
    file_path = message.text.strip()

    try:
        if not os.path.isfile(file_path):
            bot.send_message(message.chat.id, f"⚠️ File not found: {file_path}")
            return

        file_extension = os.path.splitext(file_path)[1].lower()  # Get file extension

        # Determine how to send based on file type
        if file_extension in IMAGE_EXTENSIONS:
            bot.send_photo(message.chat.id, open(file_path, 'rb'))
        elif file_extension in MOVIE_EXTENSIONS:
            bot.send_video(message.chat.id, open(file_path, 'rb'))
        else:  # Default to sending as document
            bot.send_document(message.chat.id, open(file_path, 'rb'))

        bot.send_message(message.chat.id, "✅ File sent successfully!")

    except Exception as e:
        logger.error(f"Error sending '{file_path}': {e}")
        bot.send_message(message.chat.id, f"⚠️ Error sending file: {e}")


def send_movies_from_folder(message):
    folder_path = message.text.strip()

    try:
        movie_files = [str(p) for p in Path(folder_path).rglob("*") if p.suffix.lower() in MOVIE_EXTENSIONS]
    except FileNotFoundError:
        bot.send_message(message.chat.id, f"⚠️ Folder not found: {folder_path}")
        return

    if not movie_files:
        bot.send_message(message.chat.id, f"⚠️ No movies found in {folder_path}")
        return

    num_sent = 0
    for movie_path in movie_files:
        try:
            bot.send_video(message.chat.id, open(movie_path, 'rb'))
            num_sent += 1
            time.sleep(1)  # Adjust delay if needed
        except Exception as e:
            logger.error(f"Error sending '{movie_path}': {e}")
    bot.send_message(message.chat.id, f"✅ Done. Sent {num_sent} movies.")


@bot.message_handler(commands=['files'])
def handle_list_files(message):
    bot.send_message(message.chat.id, "Please enter the FULL path to the folder:")
    bot.register_next_step_handler(message, list_files_in_folder)


def list_files_in_folder(message):
    folder_path = message.text.strip()
    if os.path.exists(folder_path):
        try:
            files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

            # Send files one by one with a small delay
            for file in files:
                try:
                    bot.send_message(message.chat.id, f"📄 {file}")
                    time.sleep(0.5)  # Adjust delay as needed
                except telebot.apihelper.ApiTelegramException as e:
                    logging.error(f"Error sending message: {e}")

        except PermissionError:
            bot.send_message(message.chat.id, "⚠️ Permission denied. Cannot access the specified folder.")
    else:
        bot.send_message(message.chat.id, "⚠️ Invalid path.")
    bot.send_message(message.chat.id, "✅ Done.")


@bot.message_handler(commands=['zip'])
def handle_send_archives_from_path(message):
    if not check_process_status():
        bot.send_message(message.chat.id, "⚠️ Process not found.")
        return

    bot.send_message(message.chat.id,
                     "Please enter the FULL path to the folder (archives will be searched recursively):")
    bot.register_next_step_handler(message, send_archives_from_path)


def send_archives_from_path(message):
    folder_path = message.text.strip()

    try:
        archive_files = [str(p) for p in Path(folder_path).rglob("*") if p.suffix.lower() in ARCHIVE_EXTENSIONS]

        if not archive_files:
            bot.send_message(message.chat.id, f"⚠️ No archive files found in {folder_path}")
            return

        for file_path in archive_files:
            try:
                with open(file_path, 'rb') as file:
                    if file_path.endswith(".zip"):
                        bot.send_document(message.chat.id, file)
                    elif file_path.endswith(".rar"):
                        with rarfile.RarFile(file_path) as rf:
                            for f in rf.infolist():
                                if not f.isdir():
                                    with rf.open(f) as extracted_file:
                                        bot.send_document(message.chat.id, extracted_file, filename=f.filename)
                time.sleep(1)  # Adjust delay if needed
            except Exception as e:
                logger.error(f"Error sending '{file_path}': {e}")
    except FileNotFoundError:
        bot.send_message(message.chat.id, f"⚠️ Folder not found: {folder_path}")
    finally:
        bot.send_message(message.chat.id, "✅ Done.")


def find_images(folder_path):
    try:
        return [str(p) for p in Path(folder_path).rglob("*") if p.suffix.lower() in IMAGE_EXTENSIONS]
    except FileNotFoundError:
        return []


def check_process_status():
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == PROCESS_NAME:
            return True
    return False


# --- Main Loop ---

if __name__ == '__main__':
    bot.polling(none_stop=True)
