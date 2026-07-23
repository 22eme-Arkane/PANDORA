import json
import os
import uuid
from datetime import datetime

from core.paths import APP_ROOT as _ROOT


def normalize_scenario(data: dict | None) -> dict:
    """Migration douce Scénario → Note de réalisation → Découpage.

    ``layout_content`` reste écrit comme alias pour les versions 1.3.x, tandis que
    ``decoupage_content`` devient le nom canonique. Aucun ancien projet n'est perdu.
    """
    out = dict(data or {})
    decoupage = out.get("decoupage_content")
    if decoupage is None:
        decoupage = out.get("layout_content", "")
    try:
        from core.decoupage_layout import canonicalize_layout
        decoupage = canonicalize_layout(str(decoupage or ""))
    except Exception:
        decoupage = str(decoupage or "")
    out["decoupage_content"] = decoupage
    out["layout_content"] = out["decoupage_content"]
    try:
        from core.decoupage_document import is_v2_document
        out["decoupage_format_version"] = 2 if is_v2_document(decoupage) else (0 if not decoupage else 1)
    except Exception:
        out["decoupage_format_version"] = int(out.get("decoupage_format_version") or 0)
    from core.direction_note import normalize_note
    out["direction_note"] = normalize_note(out.get("direction_note", ""))
    out.setdefault("workflow_version", 2)
    from core.editorial_pipeline import ensure_metadata
    return ensure_metadata(out)


def mark_storyboard_synced(scenario_id: str) -> dict | None:
    """Mémorise que le storyboard courant provient du découpage courant."""
    scenario = get_scenario(scenario_id)
    if not scenario:
        return None
    from core.editorial_pipeline import mark_storyboard_built
    return save_scenario(mark_storyboard_built(scenario))


def _sce_dir() -> str:
    from core.context import get_data_root
    return os.path.join(get_data_root(), "scenarios")


def _ensure():
    os.makedirs(_sce_dir(), exist_ok=True)


def _load_index() -> list[dict]:
    _ensure()
    index_file = os.path.join(_sce_dir(), "index.json")
    if not os.path.exists(index_file):
        return []
    with open(index_file, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save_index(index: list[dict]):
    _ensure()
    with open(os.path.join(_sce_dir(), "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def list_scenarios() -> list[dict]:
    from core.context import get_project_id
    pid = get_project_id()
    index = _load_index()
    if pid:
        return [normalize_scenario(s) for s in index if s.get("project_id") == pid]
    return [normalize_scenario(s) for s in index]


def get_scenario(scenario_id: str) -> dict | None:
    index = _load_index()
    for scenario in index:
        if scenario.get("id") == scenario_id:
            return normalize_scenario(scenario)
    return None


def save_scenario(data: dict) -> dict:
    from core.context import get_project_id
    data = normalize_scenario(data)
    _ensure()
    index = _load_index()
    now = datetime.now().isoformat()
    pid = get_project_id()
    if pid and not data.get("project_id"):
        data["project_id"] = pid

    if not data.get("id"):
        data["id"] = str(uuid.uuid4())
        data["created_at"] = now
        data["updated_at"] = now
        data.setdefault("title", "")
        data.setdefault("raw_content", "")
        data.setdefault("formatted_content", "")
        data.setdefault("direction_note", "")
        data.setdefault("decoupage_content", "")
        data.setdefault("layout_content", "")
        data.setdefault("file_path", "")
        index.insert(0, data)
    else:
        data["updated_at"] = now
        replaced = False
        for i, scenario in enumerate(index):
            if scenario.get("id") == data["id"]:
                index[i] = data
                replaced = True
                break
        if not replaced:
            data.setdefault("created_at", now)
            index.insert(0, data)

    _save_index(index)
    _export_txt(data)
    return data


def _export_txt(data: dict):
    """Sauvegarde le contenu du scénario en .txt dans le dossier scenarios/."""
    content = (data.get("formatted_content") or data.get("raw_content", "")).strip()
    if not content:
        return
    title = data.get("title", "scenario") or "scenario"
    safe = "".join(c for c in title if c.isalnum() or c in " -_").strip() or "scenario"
    sid = (data.get("id", "") or "")[:8]
    filename = f"{safe}_{sid}.txt" if sid else f"{safe}.txt"
    try:
        path = os.path.join(_sce_dir(), filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        data["saved_file"] = path
    except Exception:
        pass


def delete_scenario(scenario_id: str):
    index = _load_index()
    index = [s for s in index if s.get("id") != scenario_id]
    _save_index(index)


# ── Sauvegarde / ouverture PHYSIQUE (fichiers nommés, dossier « Scénario ») ─────
# Le scénario est déjà dans le dossier du projet → pas de sous-dossier projet.

def _saves_dir() -> str:
    from core.context import get_data_root
    d = os.path.join(get_data_root(), "Scénario")
    os.makedirs(d, exist_ok=True)
    return d


def _safe_name(name: str) -> str:
    s = "".join(c for c in (name or "") if c.isalnum() or c in " -_").strip()
    return s[:80] or "scenario"


def list_saved() -> list[str]:
    """Noms des scénarios sauvegardés (fichiers .json du dossier Scénario)."""
    try:
        return sorted(f[:-5] for f in os.listdir(_saves_dir()) if f.endswith(".json"))
    except Exception:
        return []


def export_scenario_file(name: str, data: dict) -> str:
    """Sauvegarde physique du scénario sous <projet>/data/Scénario/<nom>.json."""
    payload = normalize_scenario(data)
    payload["saved_name"] = name
    payload["saved_at"] = datetime.now().isoformat(timespec="seconds")
    path = os.path.join(_saves_dir(), _safe_name(name) + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def import_scenario_file(name: str) -> dict | None:
    """Recharge un scénario sauvegardé par son nom."""
    path = os.path.join(_saves_dir(), _safe_name(name) + ".json")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return normalize_scenario(json.load(f))


def saves_dir() -> str:
    """Dossier par défaut des scénarios sauvegardés (pour la boîte de dialogue)."""
    return _saves_dir()


def export_scenario_to(path: str, data: dict) -> str:
    """Sauvegarde le scénario vers un fichier CHOISI par l'utilisateur (boîte de
    dialogue Windows). Chargeable depuis n'importe quel projet."""
    payload = normalize_scenario(data)
    payload.setdefault("saved_name", os.path.splitext(os.path.basename(path))[0])
    payload["saved_at"] = datetime.now().isoformat(timespec="seconds")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def import_scenario_from(path: str) -> dict | None:
    """Recharge un scénario depuis un fichier CHOISI (boîte de dialogue Windows)."""
    if not path or not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return normalize_scenario(json.load(f))


def read_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()

    if ext == ".txt":
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    if ext == ".docx":
        try:
            import docx
        except ImportError:
            raise ImportError(
                "python-docx est requis pour lire les fichiers .docx. "
                "Installez-le avec : pip install python-docx"
            )
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs)

    if ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                pages = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
            return "\n".join(pages)
        except ImportError:
            pass
        except Exception:
            pass

        try:
            import PyPDF2
        except ImportError:
            raise ImportError(
                "pdfplumber ou PyPDF2 est requis pour lire les fichiers .pdf. "
                "Installez-les avec : pip install pdfplumber PyPDF2"
            )
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n".join(pages)

    raise ValueError(f"Format de fichier non supporté : {ext}. Utilisez .txt, .docx ou .pdf.")
