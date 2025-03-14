import requests
import time
from timeit import default_timer as timer
import re
from .download_video import Last_Progress_Time, Last_Progress, VideoMetadata, DLUtils
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
        global Last_Progress_Time, Last_Progress

        current_progress_time = timer()
        if (Last_Progress_Time is None or current_progress_time - Last_Progress_Time > 5):
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
        global Download_Id, Last_Progress, Last_Progress_Time, VideoMetadata

        result = requests.post(f"{Host_Url}/prepare_download/", json = {"video": video, "options": options, "folder": folder})
        result = result.json()

        VideoMetadata = result["video"]
        Download_Id = result["download_id"]

        downloadComplete = False
        while (not downloadComplete):
            fileRequest = requests.get(f"{Host_Url}/get_download/", params = {"download_id": Download_Id})
            print(f"HEADERS: {fileRequest.headers}\n")

            try:
                fileRequest = fileRequest.json()
            except:
                content_disposition = fileRequest.headers['content-disposition']
                file_name = re.findall("filename=(.+)", content_disposition)[0]
                file_name = file_name[1:-1]

                with open(file_name, 'wb') as f:
                    f.write(fileRequest.content)

                result = DLUtils.move_video(file_name, folder, VideoMetadata)

                downloadComplete = True
                Last_Progress_Time = None
                Last_Progress = ""
                break
            
            time.sleep(5)

        return result
