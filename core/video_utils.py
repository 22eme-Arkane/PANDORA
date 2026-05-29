import os
import subprocess
import sys

_ffmpeg_exe_cache: str | None = None
_ffprobe_exe_cache: str | None = None

# Suppress console window for ffmpeg/ffprobe on Windows GUI builds
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _find_davinci_ffmpeg() -> str | None:
    """Cherche ffmpeg.exe bundlé avec DaVinci Resolve (registre + chemins communs)."""
    # 1. Registre Windows — chemin d'installation officiel
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for key_path in (
                r"SOFTWARE\Blackmagic Design\DaVinci Resolve",
                r"SOFTWARE\WOW6432Node\Blackmagic Design\DaVinci Resolve",
            ):
                try:
                    with winreg.OpenKey(hive, key_path) as k:
                        install_path, _ = winreg.QueryValueEx(k, "InstallPath")
                        candidate = os.path.join(str(install_path), "ffmpeg.exe")
                        if os.path.isfile(candidate):
                            return candidate
                except (FileNotFoundError, OSError):
                    continue
    except ImportError:
        pass

    # 2. Chemins communs sur plusieurs lettres de disque
    for drive in ("C", "D", "E", "F"):
        for sub in (
            "Program Files\\Blackmagic Design\\DaVinci Resolve",
            "Program Files (x86)\\Blackmagic Design\\DaVinci Resolve",
        ):
            candidate = f"{drive}:\\{sub}\\ffmpeg.exe"
            if os.path.isfile(candidate):
                return candidate

    return None


def get_ffmpeg_exe() -> str:
    """Retourne le chemin vers ffmpeg — bundlé (PyInstaller) → imageio-ffmpeg → DaVinci → PATH."""
    global _ffmpeg_exe_cache
    if _ffmpeg_exe_cache is not None:
        return _ffmpeg_exe_cache

    # 1. Bundlé avec l'EXE PyInstaller
    if getattr(sys, "frozen", False):
        bundled = os.path.join(os.path.dirname(sys.executable), "ffmpeg.exe")
        if os.path.isfile(bundled):
            _ffmpeg_exe_cache = bundled
            return bundled

    # 2. imageio-ffmpeg — ce package embarque son propre binaire
    try:
        import imageio_ffmpeg as _iio_ffmpeg  # type: ignore
        exe = _iio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            _ffmpeg_exe_cache = exe
            return exe
    except Exception:
        pass

    # 3. DaVinci Resolve
    dvr = _find_davinci_ffmpeg()
    if dvr:
        _ffmpeg_exe_cache = dvr
        return dvr

    # 4. PATH système
    _ffmpeg_exe_cache = "ffmpeg"
    return "ffmpeg"


def get_ffprobe_exe() -> str:
    """Retourne le chemin vers ffprobe — bundlé si frozen (PyInstaller), sinon PATH."""
    global _ffprobe_exe_cache
    if _ffprobe_exe_cache is not None:
        return _ffprobe_exe_cache

    if getattr(sys, "frozen", False):
        bundled = os.path.join(os.path.dirname(sys.executable), "ffprobe.exe")
        if os.path.isfile(bundled):
            _ffprobe_exe_cache = bundled
            return bundled

    # DaVinci Resolve a ffprobe au même emplacement que ffmpeg
    dvr_dir = os.path.dirname(_find_davinci_ffmpeg() or "")
    if dvr_dir:
        candidate = os.path.join(dvr_dir, "ffprobe.exe")
        if os.path.isfile(candidate):
            _ffprobe_exe_cache = candidate
            return candidate

    _ffprobe_exe_cache = "ffprobe"
    return "ffprobe"


def _log_thumb_error(msg: str) -> None:
    """Écrit les erreurs d'extraction dans un fichier log dans %TEMP% pour diagnostic."""
    try:
        import tempfile as _tf
        log = os.path.join(_tf.gettempdir(), "pandora_thumb_errors.txt")
        with open(log, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def _win_shell_thumbnail(video_path: str, output_path: str, size: int = 200) -> bool:
    """Windows only: uses IShellItemImageFactory (same as Explorer) — no external dep."""
    try:
        import ctypes
        import ctypes.wintypes as wt
        from ctypes import windll, POINTER, byref, c_void_p, c_int, c_uint, c_wchar_p, c_ushort, c_ubyte

        # COM on this thread (STA)
        windll.ole32.CoInitializeEx(None, 0)

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", c_uint), ("Data2", c_ushort),
                        ("Data3", c_ushort), ("Data4", c_ubyte * 8)]

        class SIZE(ctypes.Structure):
            _fields_ = [("cx", c_int), ("cy", c_int)]

        # {43826D1E-E718-42EE-BC55-A1E261C37BFE} IShellItem
        IID_ISI = GUID(0x43826D1E, 0xE718, 0x42EE,
                       (c_ubyte * 8)(0xBC, 0x55, 0xA1, 0xE2, 0x61, 0xC3, 0x7B, 0xFE))
        # {BCC18B79-BA16-442F-80C4-8A59C30C463B} IShellItemImageFactory
        IID_ISIF = GUID(0xBCC18B79, 0xBA16, 0x442F,
                        (c_ubyte * 8)(0x80, 0xC4, 0x8A, 0x59, 0xC3, 0x0C, 0x46, 0x3B))

        psi = c_void_p()
        hr = windll.shell32.SHCreateItemFromParsingName(
            c_wchar_p(os.path.abspath(video_path)), None, byref(IID_ISI), byref(psi))
        if hr < 0 or not psi:
            windll.ole32.CoUninitialize()
            return False

        # QueryInterface → IShellItemImageFactory
        vtbl = ctypes.cast(psi, POINTER(POINTER(c_void_p)))
        QI      = ctypes.WINFUNCTYPE(c_int, c_void_p, POINTER(GUID), POINTER(c_void_p))(vtbl[0][0])
        Release = ctypes.WINFUNCTYPE(c_uint, c_void_p)(vtbl[0][2])
        fac = c_void_p()
        hr = QI(psi, byref(IID_ISIF), byref(fac))
        Release(psi)

        if hr < 0 or not fac:
            windll.ole32.CoUninitialize()
            return False

        fvtbl   = ctypes.cast(fac, POINTER(POINTER(c_void_p)))
        GetImage = ctypes.WINFUNCTYPE(c_int, c_void_p, SIZE, c_uint, POINTER(wt.HBITMAP))(fvtbl[0][3])
        FRelease = ctypes.WINFUNCTYPE(c_uint, c_void_p)(fvtbl[0][2])

        SIIGBF_BIGGERSIZEOK = 0x1
        hbm = wt.HBITMAP()
        hr  = GetImage(fac, SIZE(size, size), SIIGBF_BIGGERSIZEOK, byref(hbm))
        FRelease(fac)
        windll.ole32.CoUninitialize()

        if hr < 0 or not hbm:
            return False

        # HBITMAP → PIL → JPEG
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize",          c_uint),  ("biWidth",        c_int),
                ("biHeight",        c_int),   ("biPlanes",       c_ushort),
                ("biBitCount",      c_ushort),("biCompression",  c_uint),
                ("biSizeImage",     c_uint),  ("biXPelsPerMeter",c_int),
                ("biYPelsPerMeter", c_int),   ("biClrUsed",      c_uint),
                ("biClrImportant",  c_uint),
            ]

        gdi32 = windll.gdi32
        user32 = windll.user32
        hdc = user32.GetDC(None)

        bmi = BITMAPINFOHEADER()
        bmi.biSize     = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biBitCount = 32
        bmi.biPlanes   = 1
        gdi32.GetDIBits(hdc, hbm, 0, 0, None, byref(bmi), 0)

        w, h = bmi.biWidth, abs(bmi.biHeight)
        if w <= 0 or h <= 0:
            user32.ReleaseDC(None, hdc)
            gdi32.DeleteObject(hbm)
            return False

        bmi.biHeight      = -h   # top-down DIB
        bmi.biCompression = 0    # BI_RGB
        buf = (c_ubyte * (w * h * 4))()
        gdi32.GetDIBits(hdc, hbm, 0, h, buf, byref(bmi), 0)
        user32.ReleaseDC(None, hdc)
        gdi32.DeleteObject(hbm)

        from PIL import Image
        img = Image.frombuffer("RGBA", (w, h), bytes(buf), "raw", "BGRA", 0, 1)
        img.convert("RGB").save(output_path, "JPEG", quality=85)
        return os.path.isfile(output_path)

    except Exception as e:
        _log_thumb_error(f"[win_shell_thumb] erreur: {e} | {video_path}")
        return False


def extract_first_frame(video_path: str, output_path: str) -> bool:
    """Extracts the first frame of video_path and saves it to output_path.
    Returns True on success. Tries Windows Shell API → FFmpeg → cv2 → imageio."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # ── Windows Shell API (IShellItemImageFactory — même que l'Explorateur) ──
    if sys.platform == "win32":
        if _win_shell_thumbnail(video_path, output_path):
            return True

    ffmpeg = get_ffmpeg_exe()
    try:
        r = subprocess.run(
            [ffmpeg, "-y", "-i", video_path, "-vframes", "1", "-q:v", "2", output_path],
            capture_output=True,
            timeout=30,
            creationflags=_NO_WINDOW,
        )
        if r.returncode == 0 and os.path.isfile(output_path):
            return True
        # Échec ffmpeg — log pour diagnostic
        _log_thumb_error(
            f"[ffmpeg:{ffmpeg}] returncode={r.returncode} | {video_path}\n"
            f"  stderr: {r.stderr[-300:].decode('utf-8', errors='replace')}"
        )
    except FileNotFoundError:
        _log_thumb_error(f"[ffmpeg] introuvable: {ffmpeg} | vidéo: {video_path}")
    except (subprocess.TimeoutExpired, OSError) as e:
        _log_thumb_error(f"[ffmpeg] erreur: {e} | vidéo: {video_path}")

    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret:
                cv2.imwrite(output_path, frame)
                return os.path.isfile(output_path)
    except ImportError:
        pass
    except Exception as e:
        _log_thumb_error(f"[cv2] erreur: {e}")

    try:
        import imageio
        vid = imageio.get_reader(video_path)
        first = vid.get_data(0)
        vid.close()
        if first is not None:
            imageio.imwrite(output_path, first)
            return os.path.isfile(output_path)
    except ImportError:
        pass
    except Exception as e:
        _log_thumb_error(f"[imageio] erreur: {e}")

    _log_thumb_error(f"[extract_first_frame] TOUTES les méthodes ont échoué pour: {video_path}")
    return False


def get_thumb_cache_path(video_path: str) -> str:
    """Returns a persistent cache path for the thumbnail of video_path.

    The path encodes the video file path + mtime so the cache is automatically
    invalidated if the video is replaced or modified.
    """
    import hashlib
    import tempfile
    try:
        mtime = int(os.path.getmtime(video_path))
    except OSError:
        mtime = 0
    path_hash = hashlib.sha256(video_path.encode("utf-8", errors="replace")).hexdigest()[:20]
    cache_dir = os.path.join(tempfile.gettempdir(), "pandora_thumbs")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"{path_hash}_{mtime}.jpg")


def add_letterbox(video_path: str, output_path: str, scope_ratio_str: str) -> bool:
    """Overlays black letterbox bars to simulate scope aspect ratio (e.g. '2.39:1').
    Returns True on success. Requires FFmpeg."""
    try:
        parts = scope_ratio_str.split(":")
        ratio = float(parts[0]) / float(parts[1]) if len(parts) >= 2 else float(parts[0])
    except (ValueError, ZeroDivisionError, IndexError):
        return False

    try:
        r = subprocess.run(
            [get_ffprobe_exe(), "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0",
             video_path],
            capture_output=True, text=True, timeout=10,
            creationflags=_NO_WINDOW,
        )
        if r.returncode != 0:
            return False
        w, h = (int(x) for x in r.stdout.strip().split(",")[:2])
    except Exception:
        return False

    bar_h = (h - int(w / ratio)) // 2
    if bar_h <= 0:
        return False

    vf = (
        f"drawbox=x=0:y=0:w={w}:h={bar_h}:color=black:t=fill,"
        f"drawbox=x=0:y={h - bar_h}:w={w}:h={bar_h}:color=black:t=fill"
    )
    try:
        r = subprocess.run(
            [get_ffmpeg_exe(), "-y", "-i", video_path, "-vf", vf,
             "-c:v", "libx264", "-preset", "fast", "-crf", "18",
             "-c:a", "copy", output_path],
            capture_output=True, timeout=180,
            creationflags=_NO_WINDOW,
        )
        return r.returncode == 0 and os.path.isfile(output_path)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def extract_last_frame(video_path: str, output_path: str) -> bool:
    """Extracts the last frame of video_path and saves it to output_path.
    Returns True on success. Tries FFmpeg → cv2 → imageio."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # ── FFmpeg ────────────────────────────────────────────────────────────────
    try:
        r = subprocess.run(
            [get_ffmpeg_exe(), "-y", "-sseof", "-3", "-i", video_path,
             "-update", "1", "-q:v", "2", output_path],
            capture_output=True,
            timeout=30,
            creationflags=_NO_WINDOW,
        )
        if r.returncode == 0 and os.path.isfile(output_path):
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # ── OpenCV ────────────────────────────────────────────────────────────────
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total > 1:
                cap.set(cv2.CAP_PROP_POS_FRAMES, total - 1)
            ret, frame = cap.read()
            cap.release()
            if ret:
                cv2.imwrite(output_path, frame)
                return os.path.isfile(output_path)
    except ImportError:
        pass
    except Exception:
        pass

    # ── imageio ───────────────────────────────────────────────────────────────
    try:
        import imageio
        vid = imageio.get_reader(video_path)
        last = None
        for last in vid:
            pass
        vid.close()
        if last is not None:
            imageio.imwrite(output_path, last)
            return os.path.isfile(output_path)
    except ImportError:
        pass
    except Exception:
        pass

    return False
