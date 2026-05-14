import json
import os
import uuid
from datetime import datetime

from core.paths import APP_ROOT as _ROOT


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
        return json.load(f)


def _save_index(index: list[dict]):
    _ensure()
    with open(os.path.join(_sce_dir(), "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def list_scenarios() -> list[dict]:
    from core.context import get_project_id
    pid = get_project_id()
    index = _load_index()
    if pid:
        return [s for s in index if s.get("project_id") == pid]
    return index


def get_scenario(scenario_id: str) -> dict | None:
    index = _load_index()
    for scenario in index:
        if scenario.get("id") == scenario_id:
            return scenario
    return None


def save_scenario(data: dict) -> dict:
    from core.context import get_project_id
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
