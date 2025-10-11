from __future__ import unicode_literals
from enum import Enum
import validators
import mutagen
import shutil
from enum import Enum
from typing import List, Dict, Optional
import os, validators, pathlib


VideoMetadata = None
Fetch_Progress = False
Last_Progress_Time = None
Last_Progress = ""


#formats for downloading the video from Youtube
# https://gist.github.com/MartinEesmaa/2f4b261cb90a47e9c41ba115a011a4aa
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

    m4a_dup = "234"
    mp4_144p_dup = "269"
    mp4_240p_dup = "229"
    mp4_360p_dup = "230"
    mp4_480p_dup = "231"
    mp4_720p_dup = "232"
    mp4_1080p_dup = "270"
    mp4_1280x720_dup = "298"
    mp4_1280x720_dup2 = "311"


#file type extensions
video_filetypes = {"mp4":"mp4", "gp3":"3gp", "flv":"flv", "avi":"avi", "mkv":"mkv", "webm":"webm"}
audio_filetypes = {"mp3":"mp3", "wav":"wav", "aac":"aac", "ogg":"vorbis", "m4a":"m4a", "opus": "opus", "flac": "flac"}


class VideoCodes(Enum):
    mp4_144p = ["160", "269"]
    mp4_240p = ["133", "229"]
    mp4_360p = ["134", "230"]
    mp4_480p = ["135", "231"]
    mp4_720p = ["136", "232"]
    mp4_1080p = ["137", "270"]
    mp4_256x144 = ["602", "269", "603"]
    mp4_426x240 = ["229", "604"]
    mp4_640x360 = ["230", "605"]
    mp4_854x480 = ["231", "606"]
    mp4_1280x720 = ["232", "609", "311"]
    mp4_1920x1080 = ["270", "614", "617", "312"]
    mp4_2560x1440 = ["620", "623"]
    mp4_3840x2160 = ["625", "628"]

    @classmethod
    def get_all_codes(cls) -> List[str]:
        result = []
        for code in cls:
            result += code.value

        return result
    
    @classmethod
    def get_code_displays(cls, result: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        if (result is None):
            result = {}

        displays = {
            "mp4_144p": "mp4 144p",
            "mp4_240p": "mp4 240p",
            "mp4_360p": "mp4 360p",
            "mp4_480p": "mp4 480p",
            "mp4_720p": "mp4 720p",
            "mp4_1080p": "mp4 1080p",
            "mp4_256x144": "mp4 256x144",
            "mp4_426x240": "mp4 426x240",
            "mp4_640x360": "mp4 640x360",
            "mp4_854x480": "mp4 854x480",
            "mp4_1280x720": "mp4 1280x720",
            "mp4_1920x1080": "mp4 1920x1080",
            "mp4_2560x1440": "mp4 2560x1440",
            "mp4_3840x2160": "mp4_3840x2160"
        }

        for key in displays:
            current_enum = getattr(cls, key)
            current_val = displays[key]

            for code in current_enum.value:
                result[code] = current_val

        return result
    
    @classmethod
    def get_extensions(cls, result: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        if (result is None):
            result = {}

        displays = {
            "mp4_144p": video_filetypes["mp4"],
            "mp4_240p": video_filetypes["mp4"],
            "mp4_360p": video_filetypes["mp4"],
            "mp4_480p": video_filetypes["mp4"],
            "mp4_720p": video_filetypes["mp4"],
            "mp4_1080p": video_filetypes["mp4"],
            "mp4_256x144": video_filetypes["mp4"],
            "mp4_426x240": video_filetypes["mp4"],
            "mp4_640x360": video_filetypes["mp4"],
            "mp4_854x480": video_filetypes["mp4"],
            "mp4_1280x720": video_filetypes["mp4"],
            "mp4_1920x1080": video_filetypes["mp4"],
            "mp4_2560x1440": video_filetypes["mp4"],
            "mp4_3840x2160": video_filetypes["mp4"]
        }

        for key in displays:
            current_enum = getattr(cls, key)
            current_val = displays[key]

            for code in current_enum.value:
                result[code] = current_val

        return result



#codes for the different download options
code_display = {YtDownloadFormat.gp3_176x144.value:"3gp 176x144", YtDownloadFormat.gp3_320x240.value:"3gp 320x240",
                YtDownloadFormat.flv.value:"flv"}

code_display = VideoCodes.get_code_displays(result = code_display)

#extensions for the different download options
extension_display = {YtDownloadFormat.gp3_176x144.value:video_filetypes["gp3"], YtDownloadFormat.gp3_320x240.value:video_filetypes["gp3"],
                     YtDownloadFormat.flv.value:video_filetypes["flv"]}

extension_display = VideoCodes.get_extensions(result = extension_display)


# Extensions that support embeding of thumbnails
THUMBNAIL_EMBED_FORMATS = [audio_filetypes["mp3"], video_filetypes["mkv"], audio_filetypes["ogg"], audio_filetypes["m4a"], video_filetypes["mp4"]]


# DLUtils: A set of tools for downloading videos
class DLUtils():
    #move the video to the desired file location
    @classmethod
    def move_video(cls, video_file_name: str, folder: str, video):
        global Last_Progress
        Last_Progress = "Moving File to Selected Directory..."

        tmp_folder = "downloads"

        #move the file to the downloaded folder
        path = os.getcwd()
        old_path = os.path.join(path, video_file_name)
        new_path = os.path.join(folder, video_file_name)

        video_basename_parts = video_file_name.rsplit(".", 1)
        video_basename = video_basename_parts[0]
        video_ext = "" if (len(video_basename_parts) == 1) else video_basename_parts[1]

        # get the number of existing file names in the new folder
        existing_file_no = 0
        copy_no = 0

        #get the downloaded file
        for filename in os.listdir(f"{folder}"):
            if (filename.startswith(video_file_name)):
                existing_file_no += 1

        #rename the file if the file already exists
        while (os.path.exists(new_path)):
            copy_no += 1
            video_basename = f"{video_basename} ({copy_no})"

            new_path = os.path.join(folder, video_basename)
            if (video_ext):
                new_path += f".{video_ext}"

        #try to move the file into the new folder, else move it to a folder in the current directory of the program
        try:
            shutil.move(old_path, new_path)
        except:
            if not os.path.exists(tmp_folder):
                os.makedirs(tmp_folder)

            new_path = f"{path}/{tmp_folder}/{video_basename}"
            if (video_ext):
                new_path += f".{video_ext}"

            Last_Progress = f"Cannot Move File to Selected Directory,\nMoving File to Default Directory Location at {new_path}"
            shutil.move(old_path, new_path)

        return cls.fill_metadata(new_path, video_file_name, video, existing_file_no)
    
    # fill_metadata(path, video_file_name, video, track_no): Fills in extra meta data needed for the
    #   downloaded files
    @classmethod
    def fill_metadata(cls, path, video_file_name, video, track_no):
        extension = pathlib.Path(f'{path}').suffix
        is_m4a = bool(extension == ".m4a")

        # fill in the meta data for audio only files
        if (extension == ".mp3" or is_m4a):
            album_name = video["title"]
            uploader = video["channel"]["name"]

            audio = mutagen.File(path, easy=True)

            if ('albumartist' not in audio):
                audio['albumartist'] = uploader

            audio['album'] = album_name
            audio['albumartist'] = uploader
            audio['tracknumber'] = f"{track_no + 1}"

            audio.save(path)

        # correct the year
        if (is_m4a):
            audio = mutagen.File(path, easy=False)
            audio['\xa9day'] = audio['\xa9day'][0][:4]

            audio.save(path)

        return path

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
