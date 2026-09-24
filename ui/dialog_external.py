"""ui/dialog_external.py — « Ce module n'est pas installé sur cet ordinateur. »

UNE fenêtre pour tout ce qui est externe à PANDORA (core/externals) : ComfyUI
Desktop et ses modèles H3, le serveur MiniMax H3 local, Ollama. Elle dit où
en est le module (installé ? en marche ? modèles ?), la marche à suivre, et
propose ce que PANDORA sait faire lui-même — télécharger l'installeur officiel
et le lancer, déposer les modèles, démarrer le serveur — dans un thread, avec
progression et annulation (api/external_install). Un téléchargement interrompu
reprend là où il s'est arrêté.

Ouverte depuis le bandeau sous le choix du moteur, au clic « Générer » quand
le module ne répond pas, et depuis la section « Modules externes » des
Paramètres. Composant NEUTRE (Cinéma et Live).

`is_ready()` : le module répond maintenant — c'est ce que les onglets
vérifient après `exec()`.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QFrame,
    QProgressBar,
)

from core import externals as _ex
from core import local_llm as _ll
from core.i18n import translate
from ui.styles import CP
from ui.widgets import disable_default_buttons, section_label

_AMBER = "#f0b429"


def _btn(text: str, accent: str, strong: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(38)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    r, g, bl = int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16)
    if strong:
        b.setStyleSheet(
            f"QPushButton{{background:{accent};border:none;border-radius:8px;"
            f"color:#0c0e1a;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:rgba({r},{g},{bl},0.85);}}"
            f"QPushButton:disabled{{background:rgba({r},{g},{bl},0.35);}}")
    else:
        b.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid {accent};"
            f"border-radius:8px;color:{accent};font-size:12px;padding:0 18px;}}"
            f"QPushButton:hover{{background:rgba({r},{g},{bl},0.12);}}")
    return b


class ExternalDialog(QDialog):
    def __init__(self, key: str, parent=None, status: _ex.Status | None = None):
        super().__init__(parent)
        self._ext = _ex.EXTERNALS[key]
        self._status: _ex.Status | None = None
        self._worker = None
        self._status_worker = None
        ext = self._ext
        self.setWindowTitle(f"{ext.name} — " + translate("installation"))
        self.setMinimumWidth(680)
        self.setStyleSheet(f"QDialog{{background:{CP['bg1']};}}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(12)

        self._title = QLabel(ext.name)
        self._title.setWordWrap(True)
        self._title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:17px;font-weight:700;background:transparent;")
        lay.addWidget(self._title)

        intro = QLabel(translate(ext.purpose))
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color:{CP['text_secondary']};font-size:12px;background:transparent;")
        lay.addWidget(intro)

        self._state = QLabel(translate("Vérification…"))
        self._state.setWordWrap(True)
        self._state.setStyleSheet(f"color:{CP['text_dim']};font-size:11px;background:transparent;")
        lay.addWidget(self._state)

        lay.addWidget(section_label("Étapes"))
        box = QFrame()
        box.setStyleSheet(f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};border-radius:8px;}}")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(16, 12, 16, 12)
        bl.setSpacing(6)
        for i, step in enumerate(ext.steps, 1):
            l = QLabel(f"{i}.  " + translate(step))
            l.setWordWrap(True)
            l.setStyleSheet(f"color:{CP['text_primary']};font-size:12px;background:transparent;border:none;")
            bl.addWidget(l)
        lay.addWidget(box)

        # Adresse du serveur (modules qui en ont une) + Tester
        self._url = None
        if ext.url_config_key:
            row = QHBoxLayout()
            row.setSpacing(8)
            self._url = QLineEdit()
            self._url.setFixedHeight(36)
            self._url.setPlaceholderText(translate("Adresse du serveur") + " (" + translate("vide = détection automatique") + ")")
            self._url.setStyleSheet(
                f"QLineEdit{{background:{CP['bg3']};border:1px solid {CP['border']};border-radius:6px;"
                f"color:{CP['text_primary']};font-size:11px;font-family:'Consolas',monospace;padding:0 12px;}}")
            row.addWidget(self._url, 1)
            b_test = _btn(translate("Tester"), CP["accent"], strong=True)
            b_test.clicked.connect(self._test)
            row.addWidget(b_test)
            lay.addLayout(row)

        # Progression d'une action
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setFixedHeight(10)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:5px;}}"
            f"QProgressBar::chunk{{background:{CP['accent']};border-radius:5px;}}")
        self._bar.setVisible(False)
        lay.addWidget(self._bar)
        self._prog = QLabel("")
        self._prog.setWordWrap(True)
        self._prog.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        self._prog.setVisible(False)
        lay.addWidget(self._prog)

        # ComfyUI : les modèles d'un gabarit d'IMAGE (catalogue lu chez le
        # serveur, core/comfy_catalog) — tous les moteurs, jusqu'aux plus lourds.
        self._tpl_combo = None
        if ext.key == "comfyui":
            from PyQt6.QtWidgets import QComboBox
            from core import comfy_catalog as _cc
            entries = _cc.load_cached()
            videos = _cc.load_cached_video()
            if entries or videos:
                trow = QHBoxLayout()
                trow.setSpacing(8)
                self._tpl_combo = QComboBox()
                self._tpl_combo.setFixedHeight(36)
                for e in entries:
                    self._tpl_combo.addItem(
                        f"{e.get('title') or e['name']}  ·  {'édition' if e.get('edit') else 'texte → image'}"
                        f"  ·  {_cc.gb(int(e.get('size') or 0))}", e["name"])
                # Gabarits VIDÉO à entrée vidéo (« Modifier un clip » en local).
                for e in videos:
                    self._tpl_combo.addItem(
                        f"🎞 {e.get('title') or e['name']}  ·  vidéo · {_cc._KIND_LABEL.get(e.get('kind'), 'outil')}"
                        f"  ·  {_cc.gb(int(e.get('size') or 0))}", e["name"])
                trow.addWidget(self._tpl_combo, 1)
                b_tpl = _btn("⬇  " + translate("Télécharger les modèles de ce gabarit"), CP["accent"])
                b_tpl.clicked.connect(self._template_models)
                trow.addWidget(b_tpl)
                lay.addWidget(section_label("Moteurs d'images ComfyUI"))
                lay.addLayout(trow)

        # Ollama : modèles recommandés (core/local_llm.OLLAMA_MODELS — jusqu'aux
        # plus lourds, décision Matthieu) à télécharger puis « Utiliser », et le
        # plafond de la fenêtre de contexte que PANDORA demande au serveur.
        self._model_combo = None
        self._ctx_spin = None
        if ext.key == "ollama":
            from PyQt6.QtWidgets import QComboBox, QSpinBox
            lay.addWidget(section_label("Modèles recommandés"))
            mrow = QHBoxLayout()
            mrow.setSpacing(8)
            self._model_combo = QComboBox()
            self._model_combo.setEditable(True)
            self._model_combo.setFixedHeight(36)
            for m in _ll.OLLAMA_MODELS:
                self._model_combo.addItem(_ll.model_label(m), m["name"])
            self._model_combo.setToolTip("\n".join(f"{m['name']} — {m['note']}" for m in _ll.OLLAMA_MODELS))
            mrow.addWidget(self._model_combo, 1)
            b_get = _btn("⬇  " + translate("Télécharger ce modèle"), CP["accent"])
            b_get.clicked.connect(self._pull_chosen)
            mrow.addWidget(b_get)
            b_use = _btn("✓  " + translate("Utiliser ce modèle"), CP["accent2"])
            b_use.clicked.connect(self._use_chosen)
            mrow.addWidget(b_use)
            lay.addLayout(mrow)
            crow = QHBoxLayout()
            crow.setSpacing(8)
            clbl = QLabel(translate("Fenêtre de contexte maxi (jetons)"))
            clbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
            crow.addWidget(clbl)
            self._ctx_spin = QSpinBox()
            self._ctx_spin.setRange(_ll.OLLAMA_CTX_FLOOR, _ll.OLLAMA_CTX_MAX)
            self._ctx_spin.setSingleStep(4096)
            self._ctx_spin.setFixedHeight(32)
            self._ctx_spin.setStyleSheet(
                f"QSpinBox{{background:{CP['bg3']};border:1px solid {CP['border']};border-radius:6px;"
                f"color:{CP['text_primary']};font-size:11px;padding:0 8px;}}")
            self._ctx_spin.setValue(self._cfg_int("ollama_num_ctx", _ll.OLLAMA_CTX_DEFAULT))
            self._ctx_spin.valueChanged.connect(self._save_ctx)
            crow.addWidget(self._ctx_spin)
            chint = QLabel(translate("PANDORA dimensionne la fenêtre sur chaque appel (scénario + sortie) sans dépasser ce plafond."))
            chint.setWordWrap(True)
            chint.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
            crow.addWidget(chint, 1)
            lay.addLayout(crow)
        # llama.cpp : le modèle GGUF (Hugging Face) que « Lancer » servira.
        if ext.key == "llamacpp":
            from PyQt6.QtWidgets import QComboBox
            lay.addWidget(section_label("Modèle GGUF à servir"))
            grow = QHBoxLayout()
            grow.setSpacing(8)
            self._model_combo = QComboBox()
            self._model_combo.setEditable(True)
            self._model_combo.setFixedHeight(36)
            for m in _ll.GGUF_MODELS:
                self._model_combo.addItem(f"{m['note']}  ·  carte {m['vram']} Go  ·  {m['hf']}", m["hf"])
            cur = self._cfg_str("llamacpp_model")
            if cur:
                i = self._model_combo.findData(cur)
                self._model_combo.setCurrentIndex(i) if i >= 0 else self._model_combo.setEditText(cur)
            grow.addWidget(self._model_combo, 1)
            lay.addLayout(grow)

        if ext.license_note:
            note = QLabel("⚠  " + translate(ext.license_note))
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{_AMBER};font-size:10px;background:transparent;")
            lay.addWidget(note)

        # Actions de PANDORA (affichées selon l'état)
        acts = QHBoxLayout()
        acts.setSpacing(8)
        self._b_install = _btn("⬇  " + translate("Installer automatiquement"), CP["accent"], strong=True)
        self._b_install.clicked.connect(self._install)
        self._b_models = _btn("⬇  " + translate("Télécharger les modèles H3") + f" (~{_ex.H3_MODELS_TOTAL_GB} Go)",
                              CP["accent"], strong=True)
        self._b_models.clicked.connect(self._models)
        self._b_pull = _btn("⬇  " + translate("Télécharger le modèle"), CP["accent"], strong=True)
        self._b_pull.clicked.connect(self._pull)
        self._b_launch = _btn("▶  " + translate("Lancer"), CP["accent2"])
        self._b_launch.clicked.connect(self._launch)
        self._b_cancel = _btn(translate("Annuler le téléchargement"), CP["text_dim"])
        self._b_cancel.clicked.connect(self._cancel)
        for b in (self._b_install, self._b_models, self._b_pull, self._b_launch, self._b_cancel):
            b.setVisible(False)
            acts.addWidget(b)
        acts.addStretch()
        lay.addLayout(acts)

        btns = QHBoxLayout()
        b_close = _btn(translate("Plus tard"), CP["text_dim"])
        b_close.clicked.connect(self.reject)
        btns.addWidget(b_close)
        btns.addStretch()
        b_check = _btn(translate("Vérifier à nouveau"), CP["text_secondary"])
        b_check.clicked.connect(self._refresh)
        btns.addWidget(b_check)
        b_docs = _btn(translate("Guide"), CP["accent2"])
        b_docs.clicked.connect(self._open_docs)
        btns.addWidget(b_docs)
        b_page = _btn(translate("Page de téléchargement"), CP["accent"])
        b_page.clicked.connect(self._open_download)
        btns.addWidget(b_page)
        lay.addLayout(btns)

        disable_default_buttons(self)
        if status is not None:
            self._apply(status)
        else:
            self._refresh()

    # ── État ─────────────────────────────────────────────────────────────────

    def _refresh(self):
        if self._status_worker is not None and self._status_worker.isRunning():
            return
        from api.external_install import ExternalStatusWorker
        self._state.setText(translate("Vérification…"))
        self._status_worker = ExternalStatusWorker([self._ext.key], self)
        self._status_worker.result.connect(self._on_status)
        self._status_worker.start()

    def _on_status(self, key: str, st):
        if key == self._ext.key:
            self._apply(st)

    def _apply(self, st: _ex.Status):
        self._status = st
        ext = self._ext
        if not st.installed:
            head = translate("n'est pas installé sur cet ordinateur")
        elif not st.running:
            head = translate("est installé mais ne tourne pas")
        elif st.missing:
            head = translate("tourne — il manque des fichiers de modèle")
        else:
            head = translate("est prêt")
        self._title.setText(f"{ext.name} {head}")
        self._state.setText(translate(st.detail) if st.detail else "")
        self._state.setStyleSheet(
            f"color:{CP['accent'] if st.ready else _AMBER};font-size:11px;background:transparent;")
        busy = self._worker is not None and self._worker.isRunning()
        self._b_install.setVisible(ext.auto_install and not st.installed and not busy)
        self._b_launch.setVisible(st.installed and not st.running and not busy)
        self._b_models.setVisible(ext.key == "comfyui" and st.installed and bool(st.missing) and not busy)
        self._b_pull.setVisible(ext.key == "ollama" and st.running and bool(st.missing) and not busy)
        # llama.cpp : « Lancer » sert aussi à changer de modèle (le serveur recharge).
        if ext.key == "llamacpp":
            self._b_launch.setVisible(st.installed and not busy)
        self._b_cancel.setVisible(busy)

    def is_ready(self) -> bool:
        return bool(self._status and self._status.running)

    # ── Actions (méthodes liées) ────────────────────────────────────────────

    def _run(self, action: str, params: dict | None = None):
        if self._worker is not None and self._worker.isRunning():
            return
        from api.external_install import ExternalInstallWorker
        self._worker = ExternalInstallWorker(self._ext.key, action, params, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._bar.setValue(0)
        self._bar.setVisible(True)
        self._prog.setText(translate("Téléchargement en cours — vous pouvez fermer cette fenêtre, il reprendra là où il s'est arrêté."))
        self._prog.setVisible(True)
        for b in (self._b_install, self._b_models, self._b_pull, self._b_launch):
            b.setVisible(False)
        self._b_cancel.setVisible(True)
        self._worker.start()

    def _install(self):
        self._run("install")

    def _models(self):
        self._run("models")

    def _template_models(self):
        if self._tpl_combo is None or not self._tpl_combo.currentData():
            return
        self._run("models", {"templates": [self._tpl_combo.currentData()]})

    def _pull(self):
        self._run("pull", {"model": self._cfg_str("ollama_model") or _ex.OLLAMA_DEFAULT_MODEL})

    def _chosen_model(self) -> str:
        if self._model_combo is None:
            return ""
        data = self._model_combo.currentData()
        text = self._model_combo.currentText().strip()
        # Saisie libre : le texte ; choix de la liste : l'identifiant porté par l'item.
        i = self._model_combo.findText(text)
        return str(self._model_combo.itemData(i) or text) if i >= 0 else (text or str(data or ""))

    def _pull_chosen(self):
        m = self._chosen_model()
        if m:
            self._run("pull", {"model": m})

    def _use_chosen(self):
        m = self._chosen_model()
        if m:
            self._save_cfg({"ollama_model": m})
            self._state.setText("✓  " + translate("Modèle Ollama de PANDORA :") + f" {m}")
            self._state.setStyleSheet(f"color:{CP['accent']};font-size:11px;background:transparent;")

    def _save_ctx(self, value: int):
        self._save_cfg({"ollama_num_ctx": int(value)})

    def _launch(self):
        params = None
        if self._ext.key == "llamacpp" and self._model_combo is not None:
            hf = self._chosen_model()
            if hf:
                self._save_cfg({"llamacpp_model": hf})
                params = {"hf": hf}
        self._run("launch", params)

    # Lecture / écriture de la config : une clé à la fois, sur un clic explicite
    # (jamais à la construction — les harnais instancient cette fenêtre).
    @staticmethod
    def _cfg_str(key: str) -> str:
        try:
            from core.config import load_config
            return str(load_config().get(key) or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _cfg_int(key: str, default: int) -> int:
        try:
            from core.config import load_config
            return int(load_config().get(key) or default)
        except Exception:
            return default

    @staticmethod
    def _save_cfg(values: dict):
        try:
            from core.config import load_config, save_config
            cfg = load_config()
            cfg.update(values)
            save_config(cfg)
        except Exception:
            pass

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()

    def _on_progress(self, pct: int, msg: str):
        self._bar.setValue(max(0, min(100, pct)))
        self._prog.setText(msg)

    def _on_done(self, result: dict):
        self._bar.setVisible(False)
        self._prog.setVisible(False)
        self._b_cancel.setVisible(False)
        self._refresh()

    def _on_failed(self, msg: str):
        self._bar.setVisible(False)
        self._prog.setVisible(False)
        self._b_cancel.setVisible(False)
        self._state.setText(translate(msg))
        self._state.setStyleSheet(f"color:{_AMBER};font-size:11px;background:transparent;")
        if self._status is not None:
            self._apply(self._status)

    def _test(self):
        typed = self._url.text().strip() if self._url is not None else ""
        if typed:
            try:
                key = self._ext.key
                if key == "comfyui":
                    from core import comfy as _cf
                    _cf.set_url(typed)
                elif key == "h3_local":
                    from core import h3_local as _h3l
                    _h3l.set_url(typed)
                else:
                    from core.config import load_config, save_config
                    cfg = load_config()
                    cfg[self._ext.url_config_key] = typed
                    save_config(cfg)
            except Exception:
                pass
        self._refresh()

    def _open_download(self):
        QDesktopServices.openUrl(QUrl(self._ext.download_url))

    def _open_docs(self):
        QDesktopServices.openUrl(QUrl(self._ext.docs_url))

    def closeEvent(self, event):
        # Un téléchargement en cours s'arrête proprement (le .part reste,
        # la reprise repartira de là) — jamais de terminate().
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
        super().closeEvent(event)
