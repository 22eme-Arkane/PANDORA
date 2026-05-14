import time
import random
from datetime import datetime


def run_mock(params: dict, emit_progress, is_cancelled) -> dict:
    duration     = params.get("duration", 10)
    model        = params.get("model", "seedance-2.0")
    is_fast      = "fast" in model.lower()
    total_time   = random.uniform(4, 8) if is_fast else random.uniform(8, 15)
    total_frames = duration * 24

    steps = [
        (5,  "Initialisation de la requête..."),
        (12, "Envoi à l'API Seedance..."),
        (20, "Analyse du prompt..."),
        (35, "Génération des frames clés..."),
        (55, "Rendu intermédiaire..."),
        (70, f"Rendu des frames 0 / {total_frames}..."),
        (85, f"Rendu des frames {total_frames // 2} / {total_frames}..."),
        (92, f"Rendu des frames {total_frames} / {total_frames}..."),
        (96, "Encodage vidéo..."),
        (99, "Finalisation..."),
    ]
    step_time = total_time / len(steps)

    for pct, msg in steps:
        if is_cancelled():
            return {}
        emit_progress(pct, msg)
        time.sleep(step_time + random.uniform(-0.3, 0.5))

    if random.random() < 0.05:
        raise Exception("API Seedance : timeout de génération (simulé)")

    emit_progress(100, "Vidéo prête !")

    return {
        "request_id":   f"mock_{random.randint(100000, 999999)}",
        "video_url":    "https://mock.seedance.ai/output/sample.mp4",
        "duration":     duration,
        "resolution":   params.get("resolution", "720p"),
        "model":        model,
        "prompt":       params.get("prompt", ""),
        "mode":         params.get("mode", "t2v"),
        "generated_at": datetime.now().isoformat(),
        "credits_used": duration * (1.0 if is_fast else 2.0),
    }
