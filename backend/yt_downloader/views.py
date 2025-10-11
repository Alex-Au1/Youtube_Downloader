from .models import YoutubeDownload
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
import json


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

        download = YoutubeDownload()
        Downloads[download.id] = download

        result = download.prepare_download(video, options, folder)
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
    def get_metadata(cls, request: HttpRequest)  -> JsonResponse:
        link = request.GET["link"]
        opts = request.GET.get("opts", {})
        
        result = YoutubeDownload.get_metadata(link, opts)
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