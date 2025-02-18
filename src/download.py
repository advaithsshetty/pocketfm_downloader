from os import path, makedirs, remove, getcwd
from requests import RequestException, get
from json import load
from tqdm import tqdm

from pocketfm import get_show_image_url, get_show_name, get_author_name,determine_download_range
from metadata_parser import add_metadata, check_ffmpeg_installed, convert_webp_to_jpeg

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BLUE = "\033[94m"
RESET = "\033[0m"

def download_file_with_progress(url, filepath):
    response = get(url, stream=True)
    response.raise_for_status()
    total_size = int(response.headers.get('content-length', 0))
    block_size = 1024
    with open(filepath, 'wb') as file, tqdm(
        total=total_size, unit='B', unit_scale=True, 
        desc=f"{GREEN}{path.basename(filepath)}{RESET}"
    ) as progress_bar:
        for data in response.iter_content(block_size):
            file.write(data)
            progress_bar.update(len(data))

def download_episodes(json_filename, pattern, download_folder, show_id,meta=False):
    try:
        if meta:
            ffmpeg_path = getcwd()
            if check_ffmpeg_installed(ffmpeg_path):
                meta = True
                image_name = f"{show_id}.webp"
                image_url = get_show_image_url(show_id)
                if not image_url:
                    print(f"{RED}Could not fetch image for show_id: {show_id}{RESET}")
                    return
                try:
                    image_data = get(image_url).content
                    image_path = path.join(download_folder, image_name)
                    with open(image_path, 'wb') as img_file:
                        img_file.write(image_data)
                    jpeg_path = image_path.replace(".webp", ".jpeg")
                    convert_webp_to_jpeg(image_path, jpeg_path)
                    remove(image_path)
                    author = get_author_name(show_id)
                    album_name = get_show_name(show_id)
                except RequestException as e:
                    print(f"{RED}Failed to download image: {e}{RESET}")
                    return
            else:
                meta = False
                print(f"{YELLOW}FFmpeg not found. Metadata embedding is not possible.{RESET}")
        with open(json_filename, 'r', encoding='utf-8') as f:
            stories = load(f)
        download_range = determine_download_range(pattern, len(stories))
        for i in download_range:
            if i < len(stories):
                story = stories[i]
                story_title = story.get("story_title", f"episode_{i}")
                media_url = story.get("media_url")
                if media_url:
                    try:
                        try:
                            response = get(media_url.replace("low", "high"))
                            if response.status_code in [403, 404, 400, 500]:
                                raise RequestException
                        except RequestException:
                            response = get(media_url)
                        response.raise_for_status()
                        filename = f"{sanitize_filename(story_title)}.mp3"
                        filepath = path.join(download_folder, filename)
                        download_file_with_progress(media_url, filepath)
                        if meta:
                            add_metadata(filepath, story_title, author, album_name, jpeg_path)
                    except RequestException as e:
                        print(f"{RED}Failed to download '{story_title}': {e}{RESET}")
                else:
                    print(f"{YELLOW}Looks like you haven't unlocked '{story_title}'. Skipping...{RESET}")
            else:
                print(f"{YELLOW}Story index {i+1} out of range. Skipping...{RESET}")
        if meta:
            remove(jpeg_path)
        print(f"{CYAN}Download complete.{RESET}")
    except Exception as e:
        print(f"{RED}An error occurred: {e}{RESET}")

def sanitize_filename(filename):
    return "".join([c for c in filename if c.isalnum() or c in "._- "]).rstrip().replace("   ", " ").replace("  ", " ")