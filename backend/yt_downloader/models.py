from __future__ import unicode_literals
import yt_dlp as youtube_dl
from yt_dlp.postprocessor import EmbedThumbnailPP
import os, validators
from django.http import FileResponse
from threading import Thread
import uuid
import shutil
import os
import errno
import json
import stat
import subprocess
from enum import Enum
from typing import Dict, Any, Optional, List

from .tools.format_display import FormatUtils
from .secrets import Download_Folder


#options for downloading the youtube video
Download_Progress = {}
File_Download_Type = {}
Download_No = {}
Finished_Download = {}
Sending_Download = set()

#downloads that died on their worker thread, keyed by download id. download_stream
#  watches this so a failed download ends the stream instead of streaming forever
Download_Error = {}

Extractor_Args = {'youtubepot-bgutilhttp': {'base_url': ['http://127.0.0.1:9002']}}


#bounds for the remix (pitch/tempo) edits.
#
#   These are NOT arbitrary. ffmpeg's atempo filter only accepts 0.5-2.0 per instance,
#   and the pitch correction below is 1/pitch. At -/+12 half steps pitch is 0.5/2.0, so
#   1/pitch lands exactly on atempo's limits. Widening either range means emitting
#   several chained atempo filters instead of one.
HALF_STEPS_PER_OCTAVE = 12
HALF_STEPS = {"MIN": -12.0, "DEFAULT": 0.0, "MAX": 12.0}
SPEED = {"MIN": 0.5, "DEFAULT": 1.0, "MAX": 2.0}
DEFAULT_SAMPLE_RATE = 44100


#keeps 'value' inside the MIN/MAX of 'bounds'
def clamp(value: float, bounds: Dict[str, float]) -> float:
    return max(bounds["MIN"], min(bounds["MAX"], value))


'''
Pitch and tempo edits to apply to a finished download.

The filter chain follows the jukebox in Haku_Bot's search/music.py:

    asetrate = rate * pitch     shifts pitch AND speed together by 'pitch'
    atempo   = 1 / pitch        cancels that speed change, leaving a pure pitch shift
    atempo   = speed            then applies the tempo the user actually asked for

where pitch = 2 ** (half_steps / 12), i.e. equal temperament.
'''
class RemixOptions():
    def __init__(self, half_steps: float = HALF_STEPS["DEFAULT"], speed: float = SPEED["DEFAULT"]):
        self.half_steps = clamp(half_steps, HALF_STEPS)
        self.speed = clamp(speed, SPEED)


    #builds the options from the raw json sent by the frontend, or None when there is
    #  nothing to do. Bad input degrades to "no remix" rather than failing the download
    @classmethod
    def from_request(cls, raw: Optional[Dict[str, Any]]) -> Optional["RemixOptions"]:
        if (not raw):
            return None

        try:
            result = cls(float(raw.get("half_steps", HALF_STEPS["DEFAULT"])),
                         float(raw.get("speed", SPEED["DEFAULT"])))
        except (AttributeError, TypeError, ValueError):
            return None

        return None if (result.is_noop()) else result


    #whether the options would leave the file unchanged
    def is_noop(self) -> bool:
        return (self.half_steps == HALF_STEPS["DEFAULT"] and self.speed == SPEED["DEFAULT"])


    #whether the tempo differs from normal, which is what forces a video re-encode
    def changes_tempo(self) -> bool:
        return self.speed != SPEED["DEFAULT"]


    # get_pitch(): the frequency multiplier for the chosen number of half steps
    def get_pitch(self) -> float:
        return (2 ** (self.half_steps / HALF_STEPS_PER_OCTAVE))


    # get_pitch_speed(): the tempo needed to undo the speed change asetrate caused
    def get_pitch_speed(self) -> float:
        return (1 / self.get_pitch())


    # audio_filter(sample_rate): the -filter:a chain
    def audio_filter(self, sample_rate: int = DEFAULT_SAMPLE_RATE) -> str:
        #the trailing aresample is not in the Haku_Bot version, which streams to discord
        #  and lets it resample. Writing to a file, it keeps the output's declared rate
        #  equal to the input's instead of the asetrate-inflated one
        return (f"asetrate={sample_rate}*{self.get_pitch():.6f},"
                f"atempo={self.get_pitch_speed():.6f},"
                f"atempo={self.speed:.6f},"
                f"aresample={sample_rate}")


    # video_filter(): the -filter:v chain, needed only when the tempo changes
    def video_filter(self) -> str:
        return f"setpts={(1 / self.speed):.6f}*PTS"


'''
Runs a RemixOptions over a finished download with a single ffmpeg pass.

ffmpeg cannot edit in place, so this writes a sibling temp file and swaps it in. The
returned path is the file to hand back to the frontend -- on any failure that is the
untouched original, since a plain download is better than a dead one.
'''
class Remixer():
    #reads stream info out of 'path', or None when ffprobe is unavailable or unhappy
    @classmethod
    def probe(cls, path: str) -> Optional[Dict[str, Any]]:
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "stream=index,codec_type,codec_name,sample_rate:stream_disposition=attached_pic",
                 "-of", "json", path],
                capture_output = True, timeout = 60)
        except (OSError, subprocess.SubprocessError):
            return None

        if (probe.returncode):
            return None

        try:
            return json.loads(probe.stdout.decode("utf-8", errors = "replace"))
        except ValueError:
            return None


    # sample_rate(streams): the first audio stream's rate, falling back to the default
    @classmethod
    def sample_rate(cls, streams: List[Dict[str, Any]]) -> int:
        for stream in streams:
            if (stream.get("codec_type") == "audio" and stream.get("sample_rate")):
                try:
                    return int(stream["sample_rate"])
                except ValueError:
                    break

        return DEFAULT_SAMPLE_RATE


    # has_moving_video(streams): whether there is real video, as opposed to the still
    #   cover art that gets embedded into mp3/m4a downloads
    @classmethod
    def has_moving_video(cls, streams: List[Dict[str, Any]]) -> bool:
        for stream in streams:
            if (stream.get("codec_type") != "video"):
                continue

            if (not stream.get("disposition", {}).get("attached_pic")):
                return True

        return False


    # cover_stream(streams): the embedded cover art stream, if the file carries one
    @classmethod
    def cover_stream(cls, streams: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for stream in streams:
            if (stream.get("codec_type") == "video" and stream.get("disposition", {}).get("attached_pic")):
                return stream

        return None


    # extract_cover(path, stream): writes the embedded cover out to its own file,
    #   returning that path, or None if it could not be pulled out
    @classmethod
    def extract_cover(cls, path: str, stream: Dict[str, Any]) -> Optional[str]:
        extension = "png" if (stream.get("codec_name") == "png") else "jpg"
        cover_path = f"{os.path.splitext(path)[0]}.cover.{extension}"

        try:
            result = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", path,
                 "-map", "0:v:0", "-frames:v", "1", "-c", "copy", cover_path],
                capture_output = True, timeout = 60)
        except (OSError, subprocess.SubprocessError):
            return None

        if (result.returncode or not os.path.exists(cover_path)):
            return None

        return cover_path


    # embed_cover(path, cover_path): puts the cover back afterwards, reusing yt-dlp's own
    #   postprocessor so every container is handled exactly as it was originally
    @classmethod
    def embed_cover(cls, path: str, cover_path: str):
        info = {"filepath": path,
                "ext": os.path.splitext(path)[1].lstrip("."),
                "thumbnails": [{"filepath": cover_path, "url": ""}]}

        try:
            with youtube_dl.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                EmbedThumbnailPP(ydl, already_have_thumbnail = True).run(info)

        #a missing cover is not worth failing an otherwise finished download over
        except Exception:
            pass


    # apply(path, remix): remixes the file at 'path', returning the path to use
    @classmethod
    def apply(cls, path: str, remix: Optional[RemixOptions]) -> str:
        if (remix is None or remix.is_noop()):
            return path

        probed = cls.probe(path)
        if (probed is None):
            return path

        streams = probed.get("streams", [])
        base, ext = os.path.splitext(path)
        remixed_path = f"{base}.remixed{ext}"

        moving_video = cls.has_moving_video(streams)

        #ffmpeg can read cover art out of containers it cannot write it back into -- opus
        #  is the notable one, where the cover lives as a METADATA_BLOCK_PICTURE comment
        #  and the muxer has no video support at all. So the cover is pulled out, left out
        #  of the remix, and re-embedded afterwards
        cover = None if (moving_video) else cls.cover_stream(streams)
        cover_path = cls.extract_cover(path, cover) if (cover is not None) else None

        args = ["ffmpeg", "-y", "-v", "error", "-i", path]

        if (moving_video):
            #setpts needs a re-encode; without a tempo change the video can be copied
            if (remix.changes_tempo()):
                args += ["-filter:v", remix.video_filter()]
            else:
                args += ["-c:v", "copy"]
        else:
            #drop any cover art here; embed_cover puts it back below
            args += ["-vn"]

        #metadata carries over on its own: ffmpeg maps input 0's tags by default, and for
        #  ogg/opus the vorbis comments ride along on the audio stream
        args += ["-filter:a", remix.audio_filter(cls.sample_rate(streams)), remixed_path]

        try:
            result = subprocess.run(args, capture_output = True, timeout = 60 * 60)
        except (OSError, subprocess.SubprocessError):
            return path

        if (result.returncode or not os.path.exists(remixed_path)):
            cls.discard(remixed_path)
            cls.discard(cover_path)

            return path

        #swap the remix in under the original name so the download keeps its filename
        final_path = remixed_path
        try:
            os.replace(remixed_path, path)
            final_path = path
        except OSError:
            pass

        if (cover_path is not None):
            cls.embed_cover(final_path, cover_path)
            cls.discard(cover_path)

        return final_path


    #removes a working file, if there is one and it still exists
    @classmethod
    def discard(cls, path: Optional[str]):
        if (path is None):
            return

        try:
            os.remove(path)
        except OSError:
            pass


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


# Extensions that support embeding of thumbnails.
#
#   This must stay in sync with yt-dlp's EmbedThumbnailPP, which handles
#   mp3 / mkv / mka / m4a / mp4 / m4v / mov / ogg / opus / flac. A format missing from
#   here never gets 'writethumbnail' set, so no thumbnail is ever downloaded and
#   EmbedThumbnail then has nothing to embed -- the cover silently comes out empty.
#
#   'vorbis' is what this app calls an ogg download internally (audio_filetypes maps
#   ogg -> the ffmpeg codec name), so both spellings are listed.
THUMBNAIL_EMBED_FORMATS = [audio_filetypes["mp3"], audio_filetypes["m4a"], audio_filetypes["ogg"],
                           audio_filetypes["opus"], audio_filetypes["flac"],
                           video_filetypes["mkv"], video_filetypes["mp4"],
                           "ogg", "mka", "m4v", "mov"]


# YoutubeDownload: Class to deal with downloading Youtube videos
class YoutubeDownload():
    def __init__(self):
        self._id = str(uuid.uuid4().hex)
        self._folder: Optional[str] = None
        self._remix: Optional[RemixOptions] = None

    @property
    def id(self):
        return self._id

    #prepare the data for downloading the video
    def prepare_download(self, video, options, folder, remix = None):
        Finished_Download[self._id] = None
        Download_Progress[self._id] = "Beginning Download..."

        Download_Error.pop(self._id, None)

        #the remix travels as its own field rather than inside 'options', which is a
        #  positional format the branches below index by hand
        self._remix = RemixOptions.from_request(remix)

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
                    video_type = options[4]

                download_type["video"] = video_type
                audio_type = "+" + audio_type

            else:
                #video type desired for the download
                if (not(options[3] == "don't care")):
                    video_type = options[3]

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
        elif d['status'] == 'downloading':
            current_size = FormatUtils.remove_ansi_codes(d['_downloaded_bytes_str'])
            total_size = FormatUtils.remove_ansi_codes(d['_total_bytes_str'])

            eta = FormatUtils.remove_ansi_codes(d['_eta_str'])
            percent = FormatUtils.remove_ansi_codes(d['_percent_str'])
            speed = FormatUtils.remove_ansi_codes(d["_speed_str"])


            Download_Progress[self._id] = f"Downloading {file_type}...    Progress: {percent} ({current_size} / {total_size}), ETA: {eta}, Speed: {speed}"

        elif (self._id in Sending_Download):
            Download_Progress[self._id] = f"Sending and Compiling File..."


    #returns the download progress to the main app
    def get_progress(self):
        return Download_Progress.get(self._id, "")
    
    # get_download(): Retrieves the downloaded file
    def get_download(self):
        result = Finished_Download.pop(self._id, None)
        if (result is None):
            return result

        result = FileResponse(open(result, "rb"), as_attachment = True, filename = os.path.basename(result))
        return result


    # add_po_token_provder(): Adds the provider for the PO token
    @classmethod
    def add_po_token_provider(cls, ydl_opts: Dict[str, Any]):
        ydl_opts["extractor_args"] = Extractor_Args
        ydl_opts["js_runtimes"] = {"node": {}}
        ydl_opts["remote_components"] = ["ejs:github"]

    def _download_video(self, ydl_opts: Dict[str, Any], video: Dict[str, Any], video_file_name: str):
        try:
            self._download_with_thumbnail_fallback(ydl_opts, video)

        # this runs on its own thread, and download_stream waits on Finished_Download.
        #   Letting an exception escape would leave that stream running forever, so the
        #   failure is recorded instead and reported to the frontend
        except Exception as e:
            Download_Error[self._id] = f"{type(e).__name__}: {e}"
            File_Download_Type.pop(self._id, None)
            Download_No.pop(self._id, None)
            return

        File_Download_Type.pop(self._id, None)
        Download_No.pop(self._id, None)

        for filename in os.listdir(self._folder):
            if filename.startswith(video_file_name):
                basefile = os.path.basename(filename)
                break

        downloaded_path = os.path.join(self._folder, basefile)

        #apply the pitch/tempo edits before the file is offered for download
        if (self._remix is not None):
            Download_Progress[self._id] = "Remixing..."
            downloaded_path = Remixer.apply(downloaded_path, self._remix)

        Finished_Download[self._id] = downloaded_path
        Sending_Download.add(self._id)

    # _download_with_thumbnail_fallback(ydl_opts, video): Downloads the video, retrying
    #   once without the thumbnail since embedding fails for some videos
    def _download_with_thumbnail_fallback(self, ydl_opts: Dict[str, Any], video: Dict[str, Any]):
        try:
            self.__download_video(ydl_opts, video)
            return
        except Exception:
            #only worth retrying when a thumbnail was actually asked for. Otherwise the
            #  retry would be identical, so re-raise and report the real error
            if (not ydl_opts.pop("writethumbnail", False)):
                raise

        #drop the thumbnail postprocessor by key rather than by position -- it is not
        #  always the last one in the list
        ydl_opts["postprocessors"] = [pp for pp in ydl_opts.get("postprocessors", [])
                                      if pp.get("key") != "EmbedThumbnail"]

        self.__download_video(ydl_opts, video)


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
        Sending_Download.remove(self._id)
        Download_Progress.pop(self._id, None)

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
    
    @classmethod
    def _format_short_views(cls, view_count: int) -> str:
        if view_count >= 1_000_000_000:
            return f"{view_count / 1_000_000_000:.1f}B views"
        elif view_count >= 1_000_000:
            return f"{view_count / 1_000_000:.1f}M views"
        elif view_count >= 1_000:
            return f"{view_count / 1_000:.1f}K views"
        else:
            return f"{view_count} views"
    
    @classmethod
    def get_youtube_search(cls, search_query: str, no_of_searches: int):
        opts = {
            "quiet": True,
            "extract_flat": True,  # don't download, just get metadata
        }

        cls.add_po_token_provider(opts)
        with youtube_dl.YoutubeDL(opts) as ydl:
            search_results = ydl.extract_info(f"ytsearch{no_of_searches}:{search_query}", download=False)

        results = []
        for entry in search_results.get("entries", []):
            if entry is None:
                continue

            duration_secs = entry.get("duration") or 0
            duration_str = f"{int(duration_secs // 60)}:{int(duration_secs % 60):02d}"

            view_count = entry.get("view_count") or 0
            view_text = f"{view_count:,} views"
            view_short = cls._format_short_views(view_count)

            video_id = entry.get("id", "")

            # prefer the thumbnails yt-dlp actually reported, and only construct a URL
            #   as a last resort. hq720/maxresdefault do not exist for videos without a
            #   720p rendition, and i.ytimg.com serves those 404s with a valid 120x90
            #   grey placeholder JPEG, so a bad guess shows up as a blurred grey box
            #   rather than as an error. hqdefault exists for every video
            thumbnail_url = entry.get("thumbnail")

            if (not thumbnail_url):
                candidates = [t for t in (entry.get("thumbnails") or []) if t.get("url")]
                candidates.sort(key = lambda t: (t.get("width") or 0) * (t.get("height") or 0))

                if (candidates):
                    thumbnail_url = candidates[-1]["url"]

            if (not thumbnail_url):
                thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

            result = {
                "type": "video",
                "id": video_id,
                "title": entry.get("title", ""),
                "publishedTime": entry.get("upload_date") or "",
                "duration": duration_str,
                "viewCount": {
                    "text": view_text,
                    "short": view_short,
                },
                "thumbnails": [
                    {"url": thumbnail_url, "width": 360, "height": 202}
                ],
                "richThumbnail": None,
                "descriptionSnippet": [
                    {"text": entry.get("description") or ""}
                ],
                "channel": {
                    "name": entry.get("channel") or entry.get("uploader") or "",
                    "id": entry.get("channel_id") or "",
                    "thumbnails": [],
                    "link": entry.get("channel_url") or "",
                },
                "accessibility": {
                    "title": entry.get("title", ""),
                    "duration": duration_str,
                },
                "link": entry.get("url") or f"https://www.youtube.com/watch?v={video_id}",
                "shelfTitle": None,
            }
            results.append(result)

        return results


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
