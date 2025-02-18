from os import _exit as exit
from json import dump
from requests import Session, get, RequestException
from configparser import ConfigParser, NoSectionError, NoOptionError

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def load_access_token():
    config = ConfigParser()
    default_token = 'your_pocketfm_access_token'
    try:
        if not config.read('config.ini'):
            raise FileNotFoundError
        config.read('config.ini')
        token = config.get('pocketfm', 'access_token')
        if token == default_token:
            raise LookupError
        else:
            return token
    except LookupError:
        print(f"{YELLOW}Please provide an access token in config.ini file to fetch all the episodes you have unlocked!{RESET}")
        return None
    except FileNotFoundError:
        print(f"{YELLOW}Configuration file 'config.ini' not found.{RESET}")
        print(f"{YELLOW}Please login to PocketFM and provide your access token in the 'config.ini' file to fetch all the episodes you have unlocked!{RESET}")
        return None

access_token = load_access_token() #Using a global variable to store the access token so that  the function is not called again and again.

def base_url():
    return "https://web.pocketfm.com/v2/content_api/show.get_details"

def headers(access_token=None):
    headers = {
        'accept':'application/json, text/plain, */*',
        'accept-language':'en-RO,en;q=0.9,zh-RO;q=0.8,zh;q=0.7,en-GB;q=0.6,en-US;q=0.5',
        'app-client':'consumer-web',
        'app-version':'180',
        'cache-control':'no-cache',
        'device-id':'mobile-web',
        'dnt':'1',
        'locale':'CA',
        'origin':'https://pocketfm.com',
        'platform':'web',
        'pragma':'no-cache',
        'priority':'u=1, i',
        'referer':'https://pocketfm.com/',
        'sec-ch-ua':'Google Chrome;v=131, Chromium;v=131, Not_A Brand;v=24',
        'sec-ch-ua-mobile':'?1',
        'sec-ch-ua-platform':'Android',
        'sec-fetch-dest':'empty',
        'sec-fetch-mode':'cors',
        'sec-fetch-site':'same-site',
        'user-agent':'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36'
    }
    if access_token==None:
        headers['auth-token'] = 'web-auth'
    else:    
        headers['access-token'] = access_token
    return headers

def fetch_pocketfm_data(show_id, pattern='*', headers=headers(access_token), base_url=base_url()):
    episode_count = get_show_episodecount(show_id)
    ptr, ptr_2 = determine_fetch_range(pattern, episode_count)
    ptr -= ptr % 10
    ptr_2 -= ptr_2 % 10
    session = Session()
    curr_ptr = ptr
    end_ptr = ptr_2
    curr_ptr_prev = ''
    all_stories = []
    print(f"{BLUE}Fetching data for show: {get_show_name(show_id)}")
    while True:
        if curr_ptr > end_ptr:
            break
        params = {
            'show_id': show_id,
            'curr_ptr': curr_ptr,
            'info_level': 'max'
        }
        try:
            response = session.get(base_url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                result = data.get('result')
                if result:
                    first_result = result[0][0] if isinstance(result[0], list) else result[0]
                    stories = first_result.get('stories', [])
                    for story in stories:
                        if story.get("media_url"):
                            filtered_stories = [
                                {
                                    "story_title": story.get("story_title"),
                                    "story_id": story.get("story_id"),
                                    "media_url": story.get("media_url"),
                                }
                            ]
                            all_stories.extend(filtered_stories)
                        else:
                            print(f"{RED}Media URL not found for story: {story.get('story_title')}\n Maybe try using an account with the story unlocked?{RESET}")
                            session.close()
                            return all_stories
                    curr_ptr_prev = curr_ptr
                    curr_ptr = first_result.get('next_ptr')
                    if str(curr_ptr_prev) < str(episode_count) and curr_ptr == -1:
                        print(f"{YELLOW}Server returned -1 for 'next_ptr' even though there is still more data. Retrying...{RESET}")
                        curr_ptr = str(int(curr_ptr_prev) + 10) # Manually incrementing the pointer by 10 to fetch the next set of episodes
                        continue
                    if not curr_ptr or curr_ptr == -1:
                        print(f"{YELLOW}Reached the end of the episode list. Exiting...{RESET}")
                        break # Break the loop if there are no more episodes to fetch
                elif str(curr_ptr) >= str(episode_count):
                    print(f"{YELLOW}Reached the end of the episode list. Exiting...{RESET}")
                    break # Break the loop if the current pointer is greater than or equal to the total episode count
                else:
                    print(f"{RED}The 'result' field is not present in the response. Retrying...{RESET}") # Retry fetching data if the 'result' field is not present. PocketFM API is known to return empty responses sometimes.
                    continue
            else:
                print(f"{RED}Failed to fetch data. Status code: {response.status_code}{RESET}") 
                break
        except Exception as e:
            print(f"{RED}An error occurred: {e}{RESET}")
            break
    session.close()
    return all_stories

def response_json(show_id):
    params = {'show_id': show_id}
    try:
        response = get(base_url(), headers=headers(access_token), params=params)
        response.raise_for_status()
        return response.json()
    except RequestException as e:
        print(f"{RED}Error fetching data for show_id {show_id}: {e}{RESET}")
        return {}

def save_data_to_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        dump(data, f, ensure_ascii=False, indent=4)
    print(f"{GREEN}Data successfully saved{RESET}")

def get_show_image_url(show_id):
    try:
        data = response_json(show_id)
        result = data.get('result', [])
        if result:
            first_result = result[0] if isinstance(result[0], dict) else {}
            img_url = first_result.get('image_url')
            if img_url:
                return img_url
        return None
    except Exception as e:
        print(f"{RED}Error fetching image URL for show_id {show_id}: {e}{RESET}")
        return None

def get_show_name(show_id):
    try:    
        data = response_json(show_id)
        result = data.get('result', [])
        if result:
            return result[0].get('show_title', 'Unknown Show Title')
    except Exception as e:
        print(f"{RED}Error fetching show name for show_id {show_id}: {e}{RESET}")
        return 'Unknown Show Title'

def get_author_name(show_id):
    try:
        data = response_json(show_id)
        result = data.get('result', [])
        if result:
            if result:
                first_result = result[0][0] if isinstance(result[0], list) else result[0]   
                user_info = first_result.get('user_info', [])
                if user_info:
                    author = user_info.get('fullname', 'Unknown Author Name')
                    return author
    except Exception as e:
        print(f"{RED}Error fetching author name for show_id {show_id}: {e}{RESET}")
        return 'Unknown Author Name'

def get_show_episodecount(show_id):
    count = 0
    try:
        for _ in range(3):
            data = response_json(show_id)
            result = data.get('result', [])
            if result and count < int(result[0].get('episodes_count')):
                count = result[0].get('episodes_count')
            else:
                continue
    except Exception as e:
        print(f"{RED}Error fetching episode count for show_id {show_id}: {e}{RESET}")
    return count

def determine_fetch_range(pattern, total_stories):
    try:
        if pattern == '*':
            return 0, total_stories
        elif pattern.startswith('*'):
            num = int(pattern[1:])
            return 0, num
        elif pattern.endswith('*'):
            num = int(pattern[:-1])
            return num - 1, total_stories
        elif '*' in pattern:
            parts = pattern.split('*')
            if len(parts) != 2:
                raise ValueError("Invalid range pattern")
            start, end = map(int, parts)
            return start - 1, end
        elif pattern.isdigit():
            start = int(pattern) - 1
            return start, start + 1
        else:
            raise ValueError(f"Invalid pattern format: {pattern}")
    except ValueError as e:
        print(f"{RED}Invalid pattern: {pattern}. Error: {e}{RESET}")
        return 0, total_stories
    
def determine_download_range(pattern, total_stories):
    try:
        if pattern == '*':
            return range(total_stories)
        elif pattern.startswith('*'):
            num = int(pattern[1:])
            return range(num)
        elif pattern.endswith('*'):
            num = int(pattern[:-1])
            return range(num - 1, total_stories)
        elif '*' in pattern:
            start, end = map(int, pattern.split('*'))
            starter = (start // 10)*10
            start = start - starter 
            end = end - starter
            return range(start - 1, end)
        elif pattern.isdigit():
            start = int(pattern) - 1
            return range(start, start + 1)
        else:
            raise ValueError
    except ValueError:
        print(f"{RED}Invalid pattern: {pattern}{RESET}")
        return range(0)