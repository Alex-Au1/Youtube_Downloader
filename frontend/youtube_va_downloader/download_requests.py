import requests
import time
from timeit import default_timer as timer
from .format_display import FormatUtils
from .download_video import Last_Progress_Time, Last_Progress, VideoMetadata, DLUtils, Fetch_Progress
from typing import Optional, Dict, Any


Host_Url = r"http://192.168.1.72:9001"
Download_Id = None


class DownloadRequests():
    @classmethod
    def get_metadata(cls, link: str, opts: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = requests.get(f"{Host_Url}/get_metadata/", params = {"link": link, "opts": opts})
        return result.json()
    
    @classmethod
    def get_cached_progress(cls):
        global Last_Progress_Time, Last_Progress, Fetch_Progress

        current_progress_time = timer()

        if (Fetch_Progress and (Last_Progress_Time is None or current_progress_time - Last_Progress_Time > 5)):
            Last_Progress_Time = current_progress_time
            Last_Progress = cls.get_progress()
            return Last_Progress
        
        return Last_Progress
    
    @classmethod
    def get_progress(cls):
        result = requests.get(f"{Host_Url}/get_progress/", params = {"download_id": Download_Id})
        return result.json()["progress"]
    
    @classmethod
    def prepare_download(cls, video, options, folder):
        global Download_Id, Last_Progress, Last_Progress_Time, VideoMetadata, Fetch_Progress

        Last_Progress = "Sending Request to Server..."

        result = requests.post(f"{Host_Url}/prepare_download/", json = {"video": video, "options": options, "folder": folder})
        result = result.json()

        Fetch_Progress = True
        VideoMetadata = result["video"]
        Download_Id = result["download_id"]

        downloadComplete = False
        file_name = ""

        while (not downloadComplete):
            fileRequest = requests.get(f"{Host_Url}/get_download/", params = {"download_id": Download_Id})

            try:
                fileRequest = fileRequest.json()
            except:
                Fetch_Progress = False
                downloadComplete = True
                Last_Progress_Time = None
                Last_Progress = "Writing Video from Server to Disk..."

                content_disposition = fileRequest.headers['content-disposition']

                file_ext = content_disposition.rsplit(".", 1)[1]
                video_name = video["title"]
                video_id = video["id"]
                file_name = FormatUtils.format_filename(f"{video_name} - {video_id}.{file_ext}")

                break
            
            time.sleep(5)

        with open(file_name, 'wb') as f:
            f.write(fileRequest.content)

        requests.get(f"{Host_Url}/clean_download/", params = {"download_id": Download_Id})
        result = DLUtils.move_video(file_name, folder, VideoMetadata)

        Fetch_Progress = True
        return result
