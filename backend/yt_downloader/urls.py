from django.urls import path
from .views import DownloaderView


urlpatterns = [
    path('prepare_download/', DownloaderView.prepare_download, name='prepare_download'),
    path('get_progress/', DownloaderView.get_progress, name='get_progress'),
    path('download_stream/', DownloaderView.download_stream, name='download_stream'),
    path('get_metadata/', DownloaderView.get_metadata, name='get_metadata'),
    path('get_youtube_search/', DownloaderView.get_youtube_search, name='get_youtube_search'),
    path('get_download/', DownloaderView.get_download, name='get_download'),
    path('clean_download/', DownloaderView.clean_download, name = 'clean_download')
]