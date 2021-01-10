import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="Youtube_Video_Audio_Downloader",
    version="0.1.2",
    author="Alex Au",
    author_email="AlexXianZhenYuAu@gmail.com",
    description="A Simple GUI interface to help download videos and audio files from Youtube using Youtube-dl and FFMPEG",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Alex-Au1/Youtube_Downloader",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "Pillow",
        "pyperclip",
        "youtube_dl",
        "youtube-search-python",
        "requests",
        "validators"
    ],
    python_requires='>=3.6',
)
