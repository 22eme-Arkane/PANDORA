import os
import subprocess


def extract_first_frame(video_path: str, output_path: str) -> bool:
    """Extracts the first frame of video_path and saves it to output_path.
    Returns True on success. Tries FFmpeg → cv2 → imageio."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-vframes", "1", "-q:v", "2", output_path],
            capture_output=True,
            timeout=30,
        )
        if r.returncode == 0 and os.path.isfile(output_path):
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

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
    except Exception:
        pass

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
    except Exception:
        pass

    return False


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
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0",
             video_path],
            capture_output=True, text=True, timeout=10,
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
            ["ffmpeg", "-y", "-i", video_path, "-vf", vf,
             "-c:v", "libx264", "-preset", "fast", "-crf", "18",
             "-c:a", "copy", output_path],
            capture_output=True, timeout=180,
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
            ["ffmpeg", "-y", "-sseof", "-3", "-i", video_path,
             "-update", "1", "-q:v", "2", output_path],
            capture_output=True,
            timeout=30,
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
