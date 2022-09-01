from __future__ import unicode_literals
import yt_dlp as youtube_dl
import os, validators, collections, pathlib
import mutagen
from enum import Enum

import format_display


#options for downloading the youtube video
ydl_opts = {}

download_progress = "Beginning Download..."
file_download_type = ""
download_no = 1






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
video_filetypes = {"mp4":"mp4", "gp3":"gp3", "flv":"flv", "avi":"avi", "mkv":"mkv", "webm":"webm"}
audio_filetypes = {"mp3":"mp3", "wav":"wav", "aac":"aac", "ogg":"vorbis", "m4a":"m4a"}



#codes for the different download options
code_display = {YtDownloadFormat.mp4_144p.value: "mp4 144p", YtDownloadFormat.mp4_240p.value: "mp4 240p",
                YtDownloadFormat.mp4_360p.value:"mp4 360p", YtDownloadFormat.mp4_480p.value:"mp4 480p",
                YtDownloadFormat.mp4_720p.value:"mp4 720p", YtDownloadFormat.mp4_1080p.value:"mp4 1080p",
                YtDownloadFormat.mp4_640x360.value:"mp4 640x360", YtDownloadFormat.mp4_1280x720.value:"mp4 1280x720",
                YtDownloadFormat.gp3_176x144.value:"gp3 176x144", YtDownloadFormat.gp3_320x240.value:"gp3 320x240",
                YtDownloadFormat.flv.value:"flv"}

#extensions for the different download options
extension_display = {YtDownloadFormat.mp4_144p.value: video_filetypes["mp4"], YtDownloadFormat.mp4_240p.value: video_filetypes["mp4"],
                     YtDownloadFormat.mp4_360p.value:video_filetypes["mp4"], YtDownloadFormat.mp4_480p.value:video_filetypes["mp4"],
                     YtDownloadFormat.mp4_720p.value:video_filetypes["mp4"], YtDownloadFormat.mp4_1080p.value:video_filetypes["mp4"],
                     YtDownloadFormat.mp4_640x360.value:video_filetypes["mp4"], YtDownloadFormat.mp4_1280x720.value:video_filetypes["mp4"],
                     YtDownloadFormat.gp3_176x144.value:video_filetypes["gp3"], YtDownloadFormat.gp3_320x240.value:video_filetypes["gp3"],
                     YtDownloadFormat.flv.value:video_filetypes["flv"]}


#prepare the data for downloading the video
def prepare_download(video, options, folder):
    global download_progress

    download_progress = "Beginning Download..."

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


    global file_download_type
    file_download_type = file_type

    #download the video
    return download_video(video, format, download_type,file_type, folder)


#returns the progress of the download
def download_hook(d):
    global download_progress
    global download_no

    #type of download being downloaded
    if (file_download_type == "video"):
        file_type = "Video"
    elif (file_download_type == "audio"):
        file_type = "Audio"

    elif (file_download_type == "video+audio"):
        if (download_no == 1):
            file_type = "Video Part"

        elif (download_no == 2):
            file_type = "Audio Part"

    else:
        file_type = ""

    #when the downloaded portion finished downloading
    if d['status'] == 'finished':
        if (file_download_type == "video+audio"):
            download_progress = f"{file_type} Finished Downloading, "

            if (download_no == 1):
                download_no += 1
                download_progress += "Now Downloading Audio..."
            elif (download_no == 2):
                download_no -= 1
                download_progress += "Now Converting..."

        else:
            download_progress = f"{file_type} Finished Downloading, Now Converting..."

    #when the video is still downloading, display the progress
    if d['status'] == 'downloading':
        current_size = format_display.remove_ansi_codes(d['_downloaded_bytes_str'])
        total_size = format_display.remove_ansi_codes(d['_total_bytes_str'])

        eta = format_display.remove_ansi_codes(d['_eta_str'])
        percent = format_display.remove_ansi_codes(d['_percent_str'])
        speed = format_display.remove_ansi_codes(d["_speed_str"])


        download_progress = f"Downloading {file_type}...    Progress: {percent} ({current_size} / {total_size}), ETA: {eta}, Speed: {speed}"


#returns the download progress to the main app
def get_progress():
    return download_progress


#downloads the selected video
def download_video(video ,format, download_type,file_type, folder):
    video_file_name = f"{video['title']}-{video['id']}"
    video_file_name = format_display.format_filename(video_file_name)

    #options for downloading the video
    ydl_opts = {'outtmpl': f'{video_file_name}.%(ext)s',
                'noplaylist' : True,
                'nocheckcertificate':True,
                'writethumbnail':True,
                'progress_hooks': [download_hook]}

    #if downloading only audio format
    if (("audio" in download_type.keys()) and ("video" not in download_type.keys())):
        if (not (download_type["audio"] == YtDownloadFormat.best_audio_download.value or download_type["audio"] == YtDownloadFormat.worst_audio_download.value)):
            ydl_opts["extractaudio"] = True
            ydl_opts["postprocessors"] = [{'key': 'FFmpegExtractAudio',
                                           'preferredcodec': download_type["audio"],
                                           'preferredquality': '192', }]

    #if downloading any video type format
    else:
        if (not (download_type["video"] == YtDownloadFormat.best_video.value or download_type["video"] == YtDownloadFormat.worst_video.value)):
            if (download_type["video"] in extension_display.keys()):
                download_type["video"] = extension_display[download_type["video"]]

            ydl_opts["postprocessors"] = [{'key': 'FFmpegVideoConvertor',
                                           'preferedformat':download_type["video"]}]

    ydl_opts["postprocessors"] += [{"key": "FFmpegMetadata", 'add_metadata': True},
                                   {"key": "EmbedThumbnail", 'already_have_thumbnail': False}]


    #format for downloading
    ydl_opts['format'] = format

    #download the video
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video["link"]])

    return move_video(video_file_name, file_type, folder, video)


#move the video to the desired file location
def move_video(video_file_name,file_type, folder, video):
    global download_progress
    download_progress = "Moving File to Selected Directory..."

    #get the downloaded file
    for filename in os.listdir(f"."):
        if filename.startswith(video_file_name):
            basefile = os.path.basename(filename)

    #create the folder for the audio or video
    if (file_type == "audio"):
        tmp_folder = 'downloaded_audio'
    else:
        tmp_folder = 'downloaded_video'


    #move the file to the downloaded folder
    path = os.getcwd()
    old_path = f"{path}/{basefile}"
    new_path = f"{folder}/{basefile}"


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
        download_progress = f"Cannot Move File to Selected Directory,\nMoving File to Default Directory Location at {new_path}"
        os.rename(old_path, new_path)

    return fill_metadata(new_path, video_file_name, video, existing_file_no)


# fill_metadata(path, video_file_name, video, track_no): Fills in extra meta data needed for the
#   downloaded files
def fill_metadata(path, video_file_name, video, track_no):
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
    if (is_m4a or extension == ".mp4"):
        audio = mutagen.File(path, easy=False)
        audio['\xa9day'] = audio['\xa9day'][0][:4]

        audio.save(path)

    return path


#retrieves the meta data from the selected video
def get_metadata(link):
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        meta = ydl.extract_info(link, download=False)

    return meta


#retrieves all the available formats for download for the video
def get_available_formats(download_formats):
    available_formats = []

    for d in download_formats:
        available_formats.append(d["format_id"])

    return available_formats


#convert the download code format to its file type extension
def format_filetype(file_download_codes):
    display_format = {}

    for c in file_download_codes:
        if (c in code_display.keys()):
            display_format[c] = code_display[c]

    return display_format


#determines when the link is a valid youtube video link
def valid_yt_link(link):
    valid_link = validators.url(link)

    if (valid_link and (link.startswith("https://www.youtube.com/watch?v=") or link.startswith("https://youtu.be/"))):
        return True
    else:
        return False
