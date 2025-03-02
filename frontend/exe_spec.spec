# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(['exe_main.py'],
             pathex=[],
             binaries=[],
             datas=[('youtube_va_downloader/icon.ico', 'youtube_va_downloader'),
                    ('ffmpeg.exe', '.'),
                    ('ffplay.exe', '.'),
                    ('ffprobe.exe', '.')],
             hiddenimports=['youtube_va_downloader'],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='youtube_downloader',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None , icon='youtube_va_downloader\\icon.ico')
