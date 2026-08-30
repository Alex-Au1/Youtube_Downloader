from .models import YoutubeDownload, Finished_Download, Download_Error
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.http import StreamingHttpResponse
import json
import time


Downloads = {}


# DownloaderView: View for downloading youtube video/audios
class DownloaderView():
    @classmethod
    @csrf_exempt
    @method_decorator(never_cache)
    def prepare_download(cls, request: HttpRequest) -> JsonResponse:
        post_data = json.loads(request.body.decode('utf-8'))
        video = post_data["video"]
        options = post_data["options"]
        folder = post_data["folder"]

        #optional, so older clients that don't send it still work
        remix = post_data.get("remix")

        download = YoutubeDownload()
        Downloads[download.id] = download

        result = download.prepare_download(video, options, folder, remix)
        return JsonResponse(result)
    
    @classmethod
    @method_decorator(never_cache)
    def get_download(cls, request: HttpRequest) -> JsonResponse:
        download_id = request.GET.get("download_id")

        download = Downloads.get(download_id)
        result = download.get_download() if (download is not None) else None

        if (result is None):
            return JsonResponse({"download_available": False})
        
        return result
    
    @classmethod
    @method_decorator(never_cache)
    def get_progress(cls, request: HttpRequest) -> JsonResponse:
        download_id = request.GET.get("download_id")

        if (download_id is None):
            return JsonResponse({"progress": "No Download Id Given"})

        download = Downloads.get(download_id)
        result = download.get_progress() if (download is not None) else f"Download Id Not Registered\nDOWNLOADS: {Downloads}\nID: {download_id}"

        return JsonResponse({"progress": result})
    
    @classmethod
    def download_stream(cls, request: HttpRequest):
        download_id = request.GET.get("download_id")
        download = Downloads.get(download_id)

        def event_stream():
            if download is None:
                yield f"data: {json.dumps({'type': 'error', 'data': 'Download not found'})}\n\n"
                return

            while True:
                progress = download.get_progress()
                yield f"data: {json.dumps({'type': 'progress', 'data': progress})}\n\n"

                #a download whose worker thread died never sets Finished_Download, so
                #  without this the stream would run forever and hang the client
                error = Download_Error.get(download.id)

                if error is not None:
                    yield f"data: {json.dumps({'type': 'error', 'data': error})}\n\n"
                    break

                value = Finished_Download.get(download.id)

                if value is not None:
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    break

                time.sleep(1)

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"

        #nginx only. IIS ignores this header entirely -- there, buffering is switched off
        #  with responseBufferLimit="0" on the handler in web.config. Without that, IIS
        #  holds these events until 4 MB accumulates or the request ends, so no progress
        #  reaches the app until the download has already finished
        response["X-Accel-Buffering"] = "no"
        return response


    @classmethod
    def get_metadata(cls, request: HttpRequest)  -> JsonResponse:
        link = request.GET["link"]
        opts = request.GET.get("opts", {})
        
        result = YoutubeDownload.get_metadata(link, opts)
        return JsonResponse(result)
    
    @classmethod
    def get_youtube_search(cls, request: HttpRequest) -> JsonResponse:
        search_query = request.GET["search_query"]
        no_of_searches = request.GET["no_of_searches"]

        result = YoutubeDownload.get_youtube_search(search_query, no_of_searches)
        result = {"result": result}
        return JsonResponse(result)
    
    @classmethod
    @method_decorator(never_cache)
    def clean_download(cls, request: HttpRequest) -> JsonResponse:
        download_id = request.GET.get("download_id")
        exists = False

        download = Downloads.get(download_id)
        if (download is None):
            return JsonResponse({"exists": exists})
        
        try:
            download.clean_download()
        except PermissionError:
            pass
        else:
            exists = True

        Downloads.pop(download_id, None)
        return JsonResponse({"exists": exists})