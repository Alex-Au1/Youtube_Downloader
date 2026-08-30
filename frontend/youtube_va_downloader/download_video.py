from __future__ import unicode_literals
from enum import Enum
import validators
import mutagen
import shutil
from enum import Enum
from typing import List, Dict, Optional
import os, re, validators, pathlib


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

    #the individual itags that used to live here were never referenced, and most named
    #  formats YouTube no longer serves. Explicit format codes live in
    #  VIDEO_FORMAT_CODES below; this enum is only the yt-dlp format *selectors*


#file type extensions
video_filetypes = {"mp4":"mp4", "gp3":"3gp", "flv":"flv", "avi":"avi", "mkv":"mkv", "webm":"webm"}
audio_filetypes = {"mp3":"mp3", "wav":"wav", "aac":"aac", "ogg":"vorbis", "m4a":"m4a", "opus": "opus", "flac": "flac"}


'''
YouTube format codes (itags) offered as an explicit video download choice, each mapped
to (label shown to the user, resulting file extension).

Taken from yt-dlp's own _formats table, which is the closest thing to an authoritative
list. Worth knowing before extending this: current yt-dlp has DELETED that table and now
reads height/codec/ext straight out of YouTube's response rather than mapping itags.
Doing the same here would remove the need for this list entirely, and would pick up new
formats automatically -- see AI Agent Help/backend/CLAUDE.md.

Deliberately ONE table rather than three parallel ones. The previous layout zipped codes
against labels by position, so inserting a code silently shifted every label after it.

Discontinued itags are intentionally absent: 22 (720p muxed) and 17 (3gp) were dropped by
YouTube in 2024, and 5 (flv), 43 (VP8 webm) and 36 (3gp) before that.

KEEP IN SYNC with the copy in backend/yt_downloader/models.py.
'''
VIDEO_FORMAT_CODES = {
    # DASH mp4, H.264. The most widely available video-only formats
    "160": ("mp4 144p (H.264)", "mp4"),
    "133": ("mp4 240p (H.264)", "mp4"),
    "134": ("mp4 360p (H.264)", "mp4"),
    "135": ("mp4 480p (H.264)", "mp4"),
    "136": ("mp4 720p (H.264)", "mp4"),
    "298": ("mp4 720p60 (H.264)", "mp4"),
    "137": ("mp4 1080p (H.264)", "mp4"),
    "299": ("mp4 1080p60 (H.264)", "mp4"),
    "264": ("mp4 1440p (H.264)", "mp4"),
    "266": ("mp4 2160p (H.264)", "mp4"),

    # DASH webm, VP9. Smaller than H.264 at equivalent quality, and on most videos the
    #   only way to get 1440p or 2160p at all
    "278": ("webm 144p (VP9)", "webm"),
    "242": ("webm 240p (VP9)", "webm"),
    "243": ("webm 360p (VP9)", "webm"),
    "244": ("webm 480p (VP9)", "webm"),
    "247": ("webm 720p (VP9)", "webm"),
    "302": ("webm 720p60 (VP9)", "webm"),
    "248": ("webm 1080p (VP9)", "webm"),
    "303": ("webm 1080p60 (VP9)", "webm"),
    "271": ("webm 1440p (VP9)", "webm"),
    "308": ("webm 1440p60 (VP9)", "webm"),
    "313": ("webm 2160p (VP9)", "webm"),
    "315": ("webm 2160p60 (VP9)", "webm"),

    # DASH mp4, AV1
    "394": ("mp4 144p (AV1)", "mp4"),
    "395": ("mp4 240p (AV1)", "mp4"),
    "396": ("mp4 360p (AV1)", "mp4"),
    "397": ("mp4 480p (AV1)", "mp4"),
    "398": ("mp4 720p (AV1)", "mp4"),
    "399": ("mp4 1080p (AV1)", "mp4"),
    "400": ("mp4 1440p (AV1)", "mp4"),
    "401": ("mp4 2160p (AV1)", "mp4"),

    # HLS (m3u8), served for some videos instead of DASH. Not part of yt-dlp's table --
    #   these were collected from `yt-dlp -F` output
    "269": ("mp4 144p (H.264, HLS)", "mp4"),
    "229": ("mp4 240p (H.264, HLS)", "mp4"),
    "230": ("mp4 360p (H.264, HLS)", "mp4"),
    "231": ("mp4 480p (H.264, HLS)", "mp4"),
    "232": ("mp4 720p (H.264, HLS)", "mp4"),
    "311": ("mp4 720p60 (H.264, HLS)", "mp4"),
    "270": ("mp4 1080p (H.264, HLS)", "mp4"),
    "312": ("mp4 1080p60 (H.264, HLS)", "mp4"),
    "602": ("mp4 144p (VP9 low, HLS)", "mp4"),
    "603": ("mp4 144p (VP9, HLS)", "mp4"),
    "604": ("mp4 240p (VP9, HLS)", "mp4"),
    "605": ("mp4 360p (VP9, HLS)", "mp4"),
    "606": ("mp4 480p (VP9, HLS)", "mp4"),
    "609": ("mp4 720p (VP9, HLS)", "mp4"),
    "614": ("mp4 1080p (VP9, HLS)", "mp4"),
    "617": ("mp4 1080p60 (VP9, HLS)", "mp4"),
    "620": ("mp4 1440p (VP9, HLS)", "mp4"),
    "623": ("mp4 1440p60 (VP9, HLS)", "mp4"),
    "625": ("mp4 2160p (VP9, HLS)", "mp4"),
    "628": ("mp4 2160p60 (VP9, HLS)", "mp4"),
}


# VideoCodes: the accessor the rest of the app imports
class VideoCodes():
    @classmethod
    def get_all_codes(cls) -> List[str]:
        return list(VIDEO_FORMAT_CODES.keys())



#codes for the different download options
code_display = {code: display for code, (display, extension) in VIDEO_FORMAT_CODES.items()}

#extensions for the different download options
extension_display = {code: extension for code, (display, extension) in VIDEO_FORMAT_CODES.items()}


# Extensions that support embeding of thumbnails
THUMBNAIL_EMBED_FORMATS = [audio_filetypes["mp3"], video_filetypes["mkv"], audio_filetypes["ogg"], audio_filetypes["m4a"], video_filetypes["mp4"]]


# DLUtils: A set of tools for downloading videos
class DLUtils():
    # count_existing_copies(folder, basename, extension): how many copies of this
    #   download 'folder' already holds, counting both "name.ext" and "name (n).ext".
    #
    #   Matching on the whole filename matters. Testing startswith("name.ext") only ever
    #   matched the un-numbered original, so the count was 1 no matter how many copies
    #   were really there, and every later copy was tagged as track 2
    @classmethod
    def count_existing_copies(cls, folder: str, basename: str, extension: str) -> int:
        suffix = f".{extension}" if (extension) else ""

        #the name comes from a video title, so it can hold regex characters
        pattern = re.compile(rf"^{re.escape(basename)}(?: \(\d+\))?{re.escape(suffix)}$",
                             re.IGNORECASE)

        try:
            filenames = os.listdir(folder)
        except OSError:
            return 0

        return sum(1 for filename in filenames if pattern.match(filename))


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

        #how many copies are already there, which becomes this file's track number.
        #  Counted before the move, so it does not include the file being added
        existing_file_no = cls.count_existing_copies(folder, video_basename, video_ext)
        copy_no = 0

        #rename the file if the file already exists. Each attempt is built from the
        #  ORIGINAL name -- appending to the previous attempt instead gives names like
        #  "file (1) (2).mp3" once more than one copy exists
        original_basename = video_basename

        while (os.path.exists(new_path)):
            copy_no += 1
            video_basename = f"{original_basename} ({copy_no})"

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
    
    @classmethod
    def get_code_display(cls, code: str) -> Optional[str]:
        return code_display.get(code)

    #determines when the link is a valid youtube video link
    @classmethod
    def valid_yt_link(cls, link):
        valid_link = validators.url(link)

        if (valid_link and (link.startswith("https://www.youtube.com/watch?v=") or link.startswith("https://youtu.be/"))):
            return True
        else:
            return False
    
    # cleans up the link to only include the video id without any other parameters
    @classmethod
    def clean_yt_link(cls, link: str):
        queryParamSepInd = link.find("&")
        if (queryParamSepInd != -1):
            link = link[:queryParamSepInd]

        return link


