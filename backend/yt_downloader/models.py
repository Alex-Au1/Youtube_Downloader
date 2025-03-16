from __future__ import unicode_literals
import yt_dlp as youtube_dl
import os, validators
from django.http import FileResponse
from threading import Thread
import uuid
import shutil
import os
import errno
import stat
from enum import Enum
from typing import Dict, Any, Optional

from .tools.format_display import FormatUtils
from .secrets import Download_Folder


#options for downloading the youtube video
Download_Progress = {}
File_Download_Type = {}
Download_No = {}
Finished_Download = {}

BG_Utils_Generate_Paths = r"C:/Dependencies/bgutil-ytdlp-pot-provider/server/build/generate_once.js"
Extractor_Args = {'youtube': {'getpot_bgutil_script': [BG_Utils_Generate_Paths]}}


#formats for downloading the video from Youtube
class YtDownloadFormat(Enum):
    only_best = "best"
    only_worst = "worst"
    best_audio = "bestaudio"
    worst_audio = "worstaudio"
    best_video = "bestvideo"
    worst_video = "worstvideo"
    best_audio_download = best_audio + "/" + only_best
    worst_audio_download = worst_audio + "/" + only_worst
    best_video_download = best_video + "/" + only_best
    worst_video_download = worst_video + "/" + only_worst

    m4a = "140"
    webm = "43"
    mp4_144p = "160"
    mp4_240p = "133"
    mp4_360p = "134"
    mp4_480p = "135"
    mp4_720p = "136"
    mp4_1080p = "137"
    mp4_640x360 = "18"
    mp4_1280x720 = "22"
    gp3_176x144 = "17"
    gp3_320x240 = "36"
    flv = "5"


#file type extensions
video_filetypes = {"mp4":"mp4", "gp3":"3gp", "flv":"flv", "avi":"avi", "mkv":"mkv", "webm":"webm"}
audio_filetypes = {"mp3":"mp3", "wav":"wav", "aac":"aac", "ogg":"vorbis", "m4a":"m4a", "opus": "opus", "flac": "flac"}



#codes for the different download options
code_display = {YtDownloadFormat.mp4_144p.value: "mp4 144p", YtDownloadFormat.mp4_240p.value: "mp4 240p",
                YtDownloadFormat.mp4_360p.value:"mp4 360p", YtDownloadFormat.mp4_480p.value:"mp4 480p",
                YtDownloadFormat.mp4_720p.value:"mp4 720p", YtDownloadFormat.mp4_1080p.value:"mp4 1080p",
                YtDownloadFormat.mp4_640x360.value:"mp4 640x360", YtDownloadFormat.mp4_1280x720.value:"mp4 1280x720",
                YtDownloadFormat.gp3_176x144.value:"3gp 176x144", YtDownloadFormat.gp3_320x240.value:"3gp 320x240",
                YtDownloadFormat.flv.value:"flv"}

#extensions for the different download options
extension_display = {YtDownloadFormat.mp4_144p.value: video_filetypes["mp4"], YtDownloadFormat.mp4_240p.value: video_filetypes["mp4"],
                     YtDownloadFormat.mp4_360p.value:video_filetypes["mp4"], YtDownloadFormat.mp4_480p.value:video_filetypes["mp4"],
                     YtDownloadFormat.mp4_720p.value:video_filetypes["mp4"], YtDownloadFormat.mp4_1080p.value:video_filetypes["mp4"],
                     YtDownloadFormat.mp4_640x360.value:video_filetypes["mp4"], YtDownloadFormat.mp4_1280x720.value:video_filetypes["mp4"],
                     YtDownloadFormat.gp3_176x144.value:video_filetypes["gp3"], YtDownloadFormat.gp3_320x240.value:video_filetypes["gp3"],
                     YtDownloadFormat.flv.value:video_filetypes["flv"]}


# Extensions that support embeding of thumbnails
THUMBNAIL_EMBED_FORMATS = [audio_filetypes["mp3"], video_filetypes["mkv"], audio_filetypes["ogg"], audio_filetypes["m4a"], video_filetypes["mp4"]]


# YoutubeDownload: Class to deal with downloading Youtube videos
class YoutubeDownload():
    def __init__(self):
        self._id = str(uuid.uuid4().hex)
        self._folder: Optional[str] = None

    @property
    def id(self):
        return self._id

    #prepare the data for downloading the video
    def prepare_download(self, video, options, folder):
        Finished_Download[self._id] = None
        Download_Progress[self._id] = "Beginning Download..."

        #if the user is only downloading  audio
        if (options[0] == "Audio"):
            file_type = "audio"

            #best/worst audio options fort he download
            if (options[1] == "best quality"):
                format = YtDownloadFormat.best_audio_download.value
            elif(options[1] == "worst quality"):
                format = YtDownloadFormat.worst_audio_download.value

            #file type for the audio download
            download_type = {"audio":options[2]}

            if (options[2] == "ogg"):
                download_type["audio"] = audio_filetypes["ogg"]

            elif (options[2] == "don't care"):
                download_type["audio"] = format


        #if the user is downloading video
        elif (options[0] == "Video"):
            file_type = "video"
            audio_type = ""
            download_type = {}

            #best/worst quality for the video portion of the download
            if (options[1] == "best quality"):
                backup_format = YtDownloadFormat.only_best.value
                video_type = YtDownloadFormat.best_video.value
            elif(options[1] == "worst quality"):
                backup_format = YtDownloadFormat.only_worst.value
                video_type = YtDownloadFormat.worst_video.value

            #if the user is downloading video with audio
            if (options[2] == "Yes! Download video with audio."):
                file_type += "+audio"

                #best/worst quality for the audio portion of the download
                if (options[3] == "best quality"):
                    audio_type = YtDownloadFormat.best_audio.value
                elif(options[3] == "worst quality"):
                    audio_type = YtDownloadFormat.worst_audio.value

                #video type desired for the download
                if (not(options[4] == "don't care")):
                    for c in code_display:
                        if (code_display[c] == options[4]):
                            video_type = c

                download_type["video"] = video_type
                audio_type = "+" + audio_type

            else:
                #video type desired for the download
                if (not(options[3] == "don't care")):
                    for c in code_display:
                        if (code_display[c] == options[3]):
                            video_type = c

                download_type["video"] = video_type

            try:
                desired_type = options[4]
            except:
                desired_type = options[3]

            if (desired_type == "avi" or desired_type == "webm" or desired_type == "mkv"):
                format = video_type + audio_type + "/" + backup_format
                download_type["video"] = desired_type
                video_type = desired_type
            else:
                format = video_type + audio_type + "/" + backup_format

            #audio for the video download
            if (not(audio_type == "")):
                if (audio_type[0] == "+"):
                    audio_type = audio_type[1:]

                download_type["audio"] = audio_type

        File_Download_Type[self._id] = file_type
        Download_No[self._id] = 1

        #download the video
        return self.download_video(video, format, download_type,file_type, folder)


    #returns the progress of the download
    def download_hook(self, d):
        #type of download being downloaded
        if (File_Download_Type[self._id] == "video"):
            file_type = "Video"
        elif (File_Download_Type[self._id] == "audio"):
            file_type = "Audio"

        elif (File_Download_Type[self._id] == "video+audio"):
            if (Download_No[self._id] == 1):
                file_type = "Video Part"

            elif (Download_No[self._id] == 2):
                file_type = "Audio Part"

        else:
            file_type = ""

        #when the downloaded portion finished downloading
        if d['status'] == 'finished':
            if (File_Download_Type[self._id] == "video+audio"):
                Download_Progress[self._id] = f"{file_type} Finished Downloading, "

                if (Download_No[self._id] == 1):
                    Download_No[self._id] += 1
                    Download_Progress[self._id] += "Now Downloading Audio..."
                elif (Download_No[self._id] == 2):
                    Download_No[self._id] -= 1
                    Download_Progress[self._id] += "Now Converting..."

            else:
                Download_Progress[self._id] = f"{file_type} Finished Downloading, Now Converting..."

        #when the video is still downloading, display the progress
        if d['status'] == 'downloading':
            current_size = FormatUtils.remove_ansi_codes(d['_downloaded_bytes_str'])
            total_size = FormatUtils.remove_ansi_codes(d['_total_bytes_str'])

            eta = FormatUtils.remove_ansi_codes(d['_eta_str'])
            percent = FormatUtils.remove_ansi_codes(d['_percent_str'])
            speed = FormatUtils.remove_ansi_codes(d["_speed_str"])


            Download_Progress[self._id] = f"Downloading {file_type}...    Progress: {percent} ({current_size} / {total_size}), ETA: {eta}, Speed: {speed}"


    #returns the download progress to the main app
    def get_progress(self):
        return Download_Progress.get(self._id, "")
    
    # get_download(): Retrieves the downloaded file
    def get_download(self):
        result = Finished_Download.get(self._id)
        if (result is None):
            return result
        
        Finished_Download.pop(self._id, None)

        result = FileResponse(open(result, "rb"), as_attachment = True, filename = os.path.basename(result))
        return result


    # add_po_token_provder(): Adds the provider for the PO token
    @classmethod
    def add_po_token_provider(cls, ydl_opts: Dict[str, Any]):
        ydl_opts["extractor_args"] = Extractor_Args

    def _download_video(self, ydl_opts: Dict[str, Any], video: Dict[str, Any], video_file_name: str):
        try:
            self.__download_video(ydl_opts, video)

        # don't write the thumbnail if not possible
        except:
            ydl_opts.pop('writethumbnail')
            ydl_opts["postprocessors"].pop()

            self.__download_video(ydl_opts, video)

        Download_Progress.pop(self._id, None)
        File_Download_Type.pop(self._id, None)
        Download_No.pop(self._id, None)

        for filename in os.listdir(self._folder):
            if filename.startswith(video_file_name):
                basefile = os.path.basename(filename)
                break

        Finished_Download[self._id] = os.path.join(self._folder, basefile)

    # _download_video(ydl_opts, link): Downloads a video
    @classmethod
    def __download_video(cls, ydl_opts: Dict[str, Any], video: Dict[str, Any]):
        cls.add_po_token_provider(ydl_opts)
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video["link"]])


    # __get_prefered_format(download_format): Retrieves the prefered format
    #   chosen to download the file
    @classmethod
    def __get_prefered_format(cls, download_format: str) -> str:
        prefered_format = download_format

        if (prefered_format in extension_display.keys()):
            prefered_format = extension_display[prefered_format]

        return prefered_format


    #downloads the selected video
    def download_video(self, video ,format, download_type,file_type, folder):
        video_file_name = f"{video['title']}-{video['id']}"
        video_file_name = FormatUtils.format_filename(video_file_name)
        prefered_format = None

        #options for downloading the video
        ydl_opts = {'outtmpl': f'{video_file_name}.%(ext)s',
                    'noplaylist' : True,
                    'nocheckcertificate':True,
                    'progress_hooks': [self.download_hook]}

        #if downloading only audio format
        if (("audio" in download_type.keys()) and ("video" not in download_type.keys())):

            if (not (download_type["audio"] == YtDownloadFormat.best_audio_download.value or download_type["audio"] == YtDownloadFormat.worst_audio_download.value)):
                prefered_format = self.__get_prefered_format(download_type["audio"])
                download_type["audio"] = prefered_format

                ydl_opts["extractaudio"] = True
                ydl_opts["postprocessors"] = [{'key': 'FFmpegExtractAudio',
                                               'preferredcodec': download_type["audio"],
                                               'preferredquality': '192', }]

        #if downloading any video type format
        else:
            if (not (download_type["video"] == YtDownloadFormat.best_video.value or download_type["video"] == YtDownloadFormat.worst_video.value)):
                prefered_format = self.__get_prefered_format(download_type["video"])
                download_type["video"] = prefered_format

                ydl_opts["postprocessors"] = [{'key': 'FFmpegVideoConvertor',
                                               'preferedformat':download_type["video"]}]

        # retrieve the expected prefered format if we want to get only best/worst quality
        if (prefered_format is None):
            meta = self.get_metadata(video["link"], opts = {"format": format})
            prefered_format = self.__get_prefered_format(meta["ext"])

        # whether we are able to embed the thumbnail to the downloaded file
        if (prefered_format in THUMBNAIL_EMBED_FORMATS):
            ydl_opts['writethumbnail'] = True

        # add the necessary post processors
        post_processors = [{"key": "FFmpegMetadata", 'add_metadata': True},
                           {"key": "EmbedThumbnail", 'already_have_thumbnail': False}]

        try:
            ydl_opts["postprocessors"] += post_processors
        except:
            ydl_opts["postprocessors"] = post_processors


        #format for downloading
        ydl_opts['format'] = format

        # folder to hold the downloaded video
        self._folder = os.path.join(Download_Folder, self._id)

        try:
            os.mkdir(self._folder)
        except FileExistsError:
            self.remove_folder_tree(self._folder)
            os.mkdir(self._folder)

        ydl_opts["paths"] = {"home": self._folder, 
                             "temp": self._folder}

        #download the video
        downloadThread = Thread(target = self._download_video, args = [ydl_opts, video, video_file_name], daemon = True)
        downloadThread.start()
        
        return {"video_file_name": video_file_name, 
                "file_type": file_type,
                "folder": folder,
                "video": video,
                "download_id": self._id}
    

    # clean_download(): Removes all the files/folders related to a specific download
    def clean_download(self):
        self.remove_folder_tree(self._folder)

    # removeFolderTree(folder): Recursively removes a folder and its content
    @classmethod
    def remove_folder_tree(cls, folder: str):
        shutil.rmtree(folder, onexc=cls.remove_readonly)

    # handleRemoveReadonly(func, path, exc): Changes the permission of some file/folder to not be readonly
    #   then remove it
    @classmethod
    def remove_readonly(cls, func, path, excinfo):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    #retrieves the meta data from the selected video
    @classmethod
    def get_metadata(cls, link: str, opts: Optional[Dict[str, Any]] = None):
        if (opts is None):
            opts = {}

        cls.add_po_token_provider(opts)
        with youtube_dl.YoutubeDL(opts) as ydl:
            meta = ydl.extract_info(link, download=False)

        return meta


    #retrieves all the available formats for download for the video
    @classmethod
    def get_available_formats(cls, download_formats):
        available_formats = []

        for d in download_formats:
            available_formats.append(d["format_id"])

        return available_formats


    #convert the download code format to its file type extension
    @classmethod
    def format_filetype(cls, file_download_codes):
        display_format = {}

        for c in file_download_codes:
            if (c in code_display.keys()):
                display_format[c] = code_display[c]

        return display_format


    #determines when the link is a valid youtube video link
    @classmethod
    def valid_yt_link(cls, link):
        valid_link = validators.url(link)

        if (valid_link and (link.startswith("https://www.youtube.com/watch?v=") or link.startswith("https://youtu.be/"))):
            return True
        else:
            return False
