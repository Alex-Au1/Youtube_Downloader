import requests
import re
import sseclient
import json
import time
from .format_display import FormatUtils
from .download_video import Last_Progress_Time, Last_Progress, VideoMetadata, DLUtils, Fetch_Progress
from typing import Optional, Dict, Any


Download_Id = None

#The progress stream stays open for the whole download, so a long one can have its
#  connection closed by whatever sits in between -- IIS ends a FastCGI request at
#  requestTimeout, 90 seconds by default. Reconnecting is normal, not a failure.
STREAM_RECONNECT_LIMIT = 60
STREAM_RECONNECT_DELAY = 1

#the finished file is streamed to disk in pieces, so a large download never has to fit
#  in memory all at once
DOWNLOAD_CHUNK_SIZE = 1024 * 1024


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
    
    '''
    Follows the progress stream until the download really has finished.

    The stream ending is NOT the same as the download finishing. It also ends whenever
    the connection is closed, which a long download invites: IIS terminates a FastCGI
    request at requestTimeout, 90 seconds by default. Treating that as "done" meant
    asking for the file too early, and the reply is json rather than a file -- which
    surfaced as a KeyError on 'content-disposition'.

    So a stream that stops without saying 'done' is reconnected to, and only 'done' or
    'error' ends the wait.
    '''
    @classmethod
    def stream_until_finished(cls, download_id):
        global Last_Progress

        for attempt in range(STREAM_RECONNECT_LIMIT):
            try:
                with requests.get(f"{Host_Url}/download_stream/",
                                  params = {"download_id": download_id}, stream = True) as resp:
                    client = sseclient.SSEClient(resp)

                    for event in client.events():
                        msg = json.loads(event.data)

                        if (msg["type"] == "progress"):
                            Last_Progress = msg["data"]

                        elif (msg["type"] == "done"):
                            return

                        #the download died on the server. Raising here surfaces the reason
                        #  in the error dialog instead of failing on a missing file later
                        elif (msg["type"] == "error"):
                            raise RuntimeError(f"The server could not complete the download:\n\n{msg['data']}")

            except requests.RequestException:
                #a dropped connection is expected on long downloads, so it is retried
                pass

            Last_Progress = "Lost the progress connection, reconnecting to the server..."
            time.sleep(STREAM_RECONNECT_DELAY)

        raise RuntimeError("Lost contact with the server while waiting for the download "
                           f"to finish, and it did not recover after {STREAM_RECONNECT_LIMIT} "
                           "attempts.\n\nThe download may still be running on the server.")


    @classmethod
    def prepare_download(cls, video, options, folder, remix = None):
        global Download_Id, Last_Progress, Last_Progress_Time, VideoMetadata, Fetch_Progress

        Last_Progress = "Sending Request to Server..."
        Download_Id = None

        #'remix' is sent as its own field on purpose. 'options' is a positional format
        #  the backend indexes by hand, so appending to it would shift every index
        result = requests.post(f"{Host_Url}/prepare_download/", json = {"video": video, "options": options, "folder": folder, "remix": remix})
        result = result.json()

        Fetch_Progress = True
        VideoMetadata = result["video"]
        Download_Id = result["download_id"]

        file_name = ""

        cls.stream_until_finished(Download_Id)

        Fetch_Progress = False
        Last_Progress_Time = None
        Last_Progress = "Writing Video from Server to Disk..."

        with requests.get(f"{Host_Url}/get_download/", params={"download_id": Download_Id}, stream=True) as fileRequest:
            content_disposition = fileRequest.headers.get("content-disposition")

            #the backend answers with json rather than the file when the download is not
            #  finished. Reading the header blindly turned that into a bare KeyError
            if (content_disposition is None):
                detail = fileRequest.text[:300].strip()
                raise RuntimeError("The server did not send the finished file, which usually "
                                   "means the download did not finish.\n\n"
                                   f"Server replied ({fileRequest.status_code}): {detail}")

            file_ext = content_disposition.rsplit(".", 1)[1]
            file_ext_match = re.match("[A-Za-z0-9]*", file_ext)
            if (file_ext_match):
                file_ext = file_ext_match.group()

            video_name = video["title"]
            video_id = video["id"]
            file_name = FormatUtils.format_filename(f"{video_name} - {video_id}.{file_ext}")

            #written in chunks so the whole file is never held in memory at once
            with open(file_name, 'wb') as f:
                for chunk in fileRequest.iter_content(chunk_size = DOWNLOAD_CHUNK_SIZE):
                    if (chunk):
                        f.write(chunk)

        result = DLUtils.move_video(file_name, folder, VideoMetadata)

        requests.get(f"{Host_Url}/clean_download/", params = {"download_id": Download_Id})
        Fetch_Progress = True
        return result
