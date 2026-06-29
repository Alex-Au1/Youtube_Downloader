import requests
import re
import sseclient
import json
from .format_display import FormatUtils
from .download_video import Last_Progress_Time, Last_Progress, VideoMetadata, DLUtils, Fetch_Progress
from typing import Optional, Dict, Any


Download_Id = None


class DownloadRequests():
    @classmethod
    def changeHostUrl(cls, newUrl: str):
        global Host_Url
        Host_Url = newUrl

    @classmethod
    def get_metadata(cls, link: str, opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = requests.get(f"{Host_Url}/get_metadata/", params = {"link": link, "opts": opts})
        return result.json()
    
    @classmethod
    def search_youtube_video(cls, search_query: str, no_of_searches: int):
        result = requests.get(f"{Host_Url}/get_youtube_search/", params = {"search_query": search_query, "no_of_searches": no_of_searches})
        result = result.json()
        result = result["result"]
        return result
    
    @classmethod
    def get_cached_progress(cls):
        global Last_Progress_Time, Last_Progress, Fetch_Progress
        return Last_Progress
    
    @classmethod
    def get_progress(cls):
        global Download_Id
        result = requests.get(f"{Host_Url}/get_progress/", params = {"download_id": Download_Id})
        
        result = result.json()["progress"]
        return result
    
    @classmethod
    def prepare_download(cls, video, options, folder):
        global Download_Id, Last_Progress, Last_Progress_Time, VideoMetadata, Fetch_Progress

        Last_Progress = "Sending Request to Server..."
        Download_Id = None

        result = requests.post(f"{Host_Url}/prepare_download/", json = {"video": video, "options": options, "folder": folder})
        result = result.json()

        Fetch_Progress = True
        VideoMetadata = result["video"]
        Download_Id = result["download_id"]

        file_name = ""

        with requests.get(f"{Host_Url}/download_stream/", params={"download_id": Download_Id}, stream=True) as resp:
            client = sseclient.SSEClient(resp)
            for event in client.events():
                msg = json.loads(event.data)
                if msg["type"] == "progress":
                    Last_Progress = msg["data"]
                elif msg["type"] == "done":
                    break

        fileRequest = requests.get(f"{Host_Url}/get_download/", params={"download_id": Download_Id})

        Fetch_Progress = False
        Last_Progress_Time = None
        Last_Progress = "Writing Video from Server to Disk..."

        content_disposition = fileRequest.headers['content-disposition']

        file_ext = content_disposition.rsplit(".", 1)[1]
        file_ext_match = re.match("[A-Za-z0-9]*", file_ext)
        if (file_ext_match):
            file_ext = file_ext_match.group()

        video_name = video["title"]
        video_id = video["id"]
        file_name = FormatUtils.format_filename(f"{video_name} - {video_id}.{file_ext}")

        with open(file_name, 'wb') as f:
            f.write(fileRequest.content)

        result = DLUtils.move_video(file_name, folder, VideoMetadata)

        requests.get(f"{Host_Url}/clean_download/", params = {"download_id": Download_Id})
        Fetch_Progress = True
        return result
