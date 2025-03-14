from __future__ import unicode_literals
from enum import Enum
import validators
import mutagen
import os, validators, pathlib


VideoMetadata = None
Last_Progress_Time = None
Last_Progress = ""


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


# DLUtils: A set of tools for downloading videos
class DLUtils():
    #move the video to the desired file location
    @classmethod
    def move_video(cls, video_file_name, folder, video):
        global Last_Progress
        Last_Progress = "Moving File to Selected Directory..."

        tmp_folder = "downloads"

        #move the file to the downloaded folder
        path = os.getcwd()
        old_path = f"{path}/{video_file_name}"
        new_path = f"{folder}/{video_file_name}"

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

            #find the position of the dot in the file extension
            for i in range (len(basefile)):
                if (basefile[len(basefile) - 1 - i] == "."):
                    dot_pos = len(basefile) - 1 - i
                    break

            if(copy_no > 1):
                basefile = basefile[:dot_pos - 4] + basefile[dot_pos:]
                dot_pos -= 4

            basefile = basefile[:dot_pos] + f" ({copy_no})" + basefile[dot_pos:]


            new_path = f"{folder}/{basefile}"

        #try to move the file into the new folder, else move it to a folder in the current directory of the program
        try:
            os.rename(old_path, new_path)
        except:
            if not os.path.exists(tmp_folder):
                os.makedirs(tmp_folder)

            new_path = f"{path}/{tmp_folder}/{basefile}"
            Last_Progress = f"Cannot Move File to Selected Directory,\nMoving File to Default Directory Location at {new_path}"
            os.rename(old_path, new_path)

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
