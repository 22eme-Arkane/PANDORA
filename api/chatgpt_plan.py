"""
Compte ChatGPT (« Sign in with ChatGPT » + usage du forfait Plus / Pro).

Écrit d'après la documentation PUBLIQUE d'OpenAI (developers.openai.com/siwc,
lue le 04/10/2026 ; synthèse dans research_notes/Sign in with ChatGPT/
protocole_siwc.md). Aucune ligne du DevKit d'OpenAI : sa licence « Noncommercial »
est incompatible avec la GPL v3 de PANDORA.

Ce que fait ce module (tout est BLOQUANT : à appeler hors du thread de l'interface) :
  • connexion OAuth : inscription dynamique (`dynamic_agent_client` → client_id
    `oaiapp_…` émis), PKCE S256, state + nonce, retour sur
    http://127.0.0.1:<port libre>/auth/callback, ID token RS256 vérifié en
    Python pur contre le JWKS public ;
  • jetons stockés UNIQUEMENT sur ce poste, chiffrés par DPAPI sous Windows
    (fichier 0600 ailleurs), dans le dossier de données de l'utilisateur — jamais
    dans un projet ni dans config.json ;
  • rafraîchissement sérialisé (jeton rotatif), révocation à la déconnexion ;
  • inférence POST /v1/responses en flux SSE (store:false, stream:true), champs
    refusés par cette voie retirés, réponse valide seulement à `response.completed`.

Conditions OpenAI (29/09/2026) respectées : nom « PANDORA », requêtes directes
depuis le poste (aucun relais), forfait utilisé par PANDORA seulement, gratuité,
pas de rotation de comptes, et JAMAIS de bascule silencieuse vers la clé API :
le repli est un choix explicite de l'utilisateur (case dans les Paramètres).

⚠ Constat du 04/10/2026 (ticket openai/sign-in-with-chatgpt-devkit#5, sans
réponse d'OpenAI) : le rafraîchissement des jetons échoue pour tous les clients
(« refresh_token_invalidated ») → une session dure une heure, puis reconnexion.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

# ── Constantes du protocole ───────────────────────────────────────────────────
ISSUER = "https://auth.openai.com"
RESOURCE = "https://api.openai.com/v1"
API_BASE = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
REGISTRATION_CLIENT = "dynamic_agent_client"     # point d'entrée, JAMAIS sauvegardé
APP_NAME = "PANDORA"                               # agent_name_hint, identique partout
CALLBACK_PATH = "/auth/callback"
USAGE_URL = "https://chatgpt.com/settings/usage"
# Champs refusés par la voie « forfait » : retirés avant envoi.
FORBIDDEN_FIELDS = {
    "background", "conversation", "max_output_tokens", "max_tool_calls", "metadata",
    "moderation", "multi_agent", "prompt", "prompt_cache_retention", "safety_identifier",
    "temperature", "top_logprobs", "top_p", "truncation", "user", "previous_response_id",
    "service_tier",
}
TERMINAL_REFRESH = {"invalid_grant", "invalid_refresh_token", "token_expired",
                    "refresh_token_expired", "refresh_token_invalidated",
                    "refresh_token_reused"}
PAUSE_PLAN = {"subscription_sharing_usage_limit_exceeded"}
NOT_ELIGIBLE = {"subscription_sharing_user_not_eligible",
                "subscription_sharing_v2_user_not_eligible",
                "subscription_sharing_v2_client_not_enabled"}
RETRY_LATER = {"subscription_sharing_usage_unavailable", "subscription_sharing_user_unavailable",
               "subscription_sharing_v2_user_unavailable"}
RECONNECT = {"reauth_required", "account_mismatch", "subscription_sharing_invalid_user",
             "subscription_sharing_v2_invalid_user", "chatpass_v2_scope_not_authorized",
             "chatpass_v2_invalid_authorization_context"}


class SiwcError(Exception):
    def __init__(self, code, message="", status=None, request_id=None, param=None,
                 retryable=False, partial_text="", reason=None):
        super().__init__(message or code)
        self.code, self.status, self.request_id = code, status, request_id
        self.param, self.retryable, self.partial_text = param, retryable, partial_text
        self.reason = reason            # `error_reason` OAuth (ex. refresh_token_invalidated)


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def random_value() -> str:
    return b64url(secrets.token_bytes(32))         # 43 caractères : valide pour PKCE


def pkce_pair() -> tuple[str, str]:
    verifier = random_value()
    return verifier, b64url(hashlib.sha256(verifier.encode("ascii")).digest())


# ── Erreurs HTTP : OAuth (`error` chaîne), Responses (`error.code`), admission (`detail`)

def _json_or_none(resp):
    try:
        return resp.json()
    except ValueError:
        return None


def api_error(status, body, request_id=None) -> SiwcError:
    code, param, message, reason = None, None, "", None
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, str):                        # OAuth (jeton, révocation)
            code, reason = err, body.get("error_reason")
            message = str(body.get("error_description") or "")
        elif isinstance(err, dict):                     # API Responses
            code, param = err.get("code"), err.get("param")
            message = str(err.get("message") or "")
        elif "detail" in body:                          # admission : diagnostic seulement
            message = str(body["detail"])[:300]
    if not code:
        code = {401: "unauthorized", 403: "forbidden", 429: "rate_limited"}.get(
            status, "server_error" if status and status >= 500 else "api_error")
    retryable = code in RETRY_LATER or code == "server_error" or status == 503
    return SiwcError(code, message, status, request_id, param, retryable, reason=reason)


def _requests():
    import requests
    return requests


def _get(url, **kwargs):
    requests = _requests()
    try:
        return requests.get(url, timeout=kwargs.pop("timeout", 15), allow_redirects=False,
                            **kwargs)
    except requests.RequestException as exc:
        raise SiwcError("network_error", str(exc), retryable=True) from None


def _post_form(url, form):
    requests = _requests()
    try:
        r = requests.post(url, data=form, headers={"Accept": "application/json"},
                          timeout=30, allow_redirects=False)
    except requests.RequestException as exc:
        raise SiwcError("network_error", str(exc), retryable=True) from None
    body = _json_or_none(r)
    rid = r.headers.get("x-request-id") or r.headers.get("openai-request-id")
    if r.status_code != 200 or not isinstance(body, dict):
        raise api_error(r.status_code, body, rid)
    return body


# ── Découverte OIDC + JWKS + vérification RS256 en Python pur ─────────────────
_DISCOVERY: dict | None = None
_JWKS: dict = {}
_SHA256_DIGESTINFO = bytes.fromhex("3031300d060960864801650304020105000420")


def discovery() -> dict:
    global _DISCOVERY
    if _DISCOVERY is None:
        r = _get(ISSUER + "/.well-known/openid-configuration")
        doc = _json_or_none(r)
        if r.status_code != 200 or not isinstance(doc, dict) or doc.get("issuer") != ISSUER:
            raise SiwcError("discovery_failed", retryable=True)
        for key in ("authorization_endpoint", "token_endpoint", "jwks_uri", "revocation_endpoint"):
            value = doc.get(key)
            if not isinstance(value, str) or not value.startswith(ISSUER + "/"):
                raise SiwcError("discovery_failed", retryable=True)
        _DISCOVERY = doc
    return _DISCOVERY


def _jwk(kid: str) -> tuple[int, int]:
    for attempt in range(2):                            # recharger si `kid` inconnu (rotation)
        if kid not in _JWKS or attempt:
            try:
                r = _get(discovery()["jwks_uri"])
            except SiwcError:
                raise SiwcError("identity_verification_unavailable", retryable=True) from None
            keys = (_json_or_none(r) or {}).get("keys")
            if r.status_code != 200 or not isinstance(keys, list):
                raise SiwcError("identity_verification_unavailable", retryable=True)
            _JWKS.clear()
            _JWKS.update({k["kid"]: k for k in keys if k.get("kty") == "RSA" and "kid" in k})
        if kid in _JWKS:
            k = _JWKS[kid]
            return (int.from_bytes(b64url_decode(k["n"]), "big"),
                    int.from_bytes(b64url_decode(k["e"]), "big"))
    raise SiwcError("invalid_id_token", "Clé de signature inconnue.")


def rs256_verify(signing_input: bytes, signature: bytes, n: int, e: int) -> bool:
    """RSASSA-PKCS1-v1_5 + SHA-256 (RFC 8017 §8.2.2) avec pow() : aucune dépendance."""
    k = (n.bit_length() + 7) // 8
    if len(signature) != k:
        return False
    s = int.from_bytes(signature, "big")
    if s >= n:
        return False
    t = _SHA256_DIGESTINFO + hashlib.sha256(signing_input).digest()
    if k < len(t) + 11:
        return False
    expected = b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t
    return hmac.compare_digest(pow(s, e, n).to_bytes(k, "big"), expected)


def verify_id_token(id_token, client_id, nonce=None, now=None) -> dict:
    try:
        head_b64, payload_b64, sig_b64 = id_token.split(".")
        header = json.loads(b64url_decode(head_b64))
        claims = json.loads(b64url_decode(payload_b64))
    except (AttributeError, ValueError):
        raise SiwcError("invalid_id_token") from None
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise SiwcError("invalid_id_token")
    n, e = _jwk(header["kid"])
    if not rs256_verify(f"{head_b64}.{payload_b64}".encode("ascii"), b64url_decode(sig_b64), n, e):
        raise SiwcError("invalid_id_token", "Signature invalide.")
    now = time.time() if now is None else now
    aud = claims.get("aud")
    aud_ok = aud == client_id or (isinstance(aud, list) and client_id in aud
                                  and (len(aud) == 1 or claims.get("azp") == client_id))
    ok = (claims.get("iss") == discovery()["issuer"] and aud_ok
          and claims.get("azp", client_id) == client_id
          and isinstance(claims.get("exp"), (int, float)) and claims["exp"] + 5 > now
          and isinstance(claims.get("iat"), (int, float))
          and isinstance(claims.get("sub"), str) and claims["sub"]
          and (nonce is None or claims.get("nonce") == nonce))
    if not ok:
        raise SiwcError("invalid_id_token", "Identité ChatGPT non vérifiable.")
    return claims


# ── Stockage local ────────────────────────────────────────────────────────────

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _dpapi(data: bytes, protect: bool) -> bytes:
        """DPAPI (CryptProtectData) : chiffré avec la session Windows de l'utilisateur."""
        crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
        fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
        fn.argtypes = [ctypes.POINTER(_Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                       ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_Blob)]
        fn.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        buf = ctypes.create_string_buffer(data, len(data))
        blob_in = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
        blob_out = _Blob()
        if not fn(ctypes.byref(blob_in), None, None, None, None, 0x1, ctypes.byref(blob_out)):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(ctypes.cast(blob_out.pbData, ctypes.c_void_p))
else:
    def _dpapi(data: bytes, protect: bool) -> bytes:
        return data          # macOS / Linux : fichier 0600 (Trousseau : à faire)


def default_store_dir() -> Path:
    """Dossier de données de l'UTILISATEUR (jamais un projet, jamais le dépôt).
    PANDORA_CHATGPT_DIR le remplace : les harnais l'envoient dans un dossier
    temporaire, aucun test ne touche les vrais jetons."""
    override = os.environ.get("PANDORA_CHATGPT_DIR")
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"),
                                                                "AppData", "Local")
        return Path(base) / "PANDORA" / "chatgpt"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "PANDORA" / "chatgpt"
    return Path.home() / ".local" / "share" / "PANDORA" / "chatgpt"


class CredentialStore:
    """host.json (identifiant d'hôte, non secret) + auth.bin (jetons, chiffrés sous Windows)."""

    def __init__(self, directory: Path | None = None):
        self.dir = Path(directory) if directory else default_store_dir()
        self.lock = threading.RLock()
        self._depth = 0

    def _ensure_dir(self):
        """Créé à la PREMIÈRE écriture seulement : lire l'état d'un poste jamais
        connecté (Paramètres, harnais) ne laisse aucun dossier derrière soi."""
        if not self.dir.is_dir():
            self.dir.mkdir(parents=True, exist_ok=True)
            with contextlib.suppress(OSError):
                os.chmod(self.dir, 0o700)

    def has_data(self) -> bool:
        return (self.dir / "auth.bin").exists()

    @contextlib.contextmanager
    def process_lock(self):
        """Verrou inter-processus réentrant (Cinéma et Live peuvent tourner ensemble) :
        un jeton rotatif ne doit être rafraîchi que par un seul processus à la fois."""
        with self.lock:
            if self._depth:
                self._depth += 1
                try:
                    yield
                finally:
                    self._depth -= 1
                return
            self._ensure_dir()
            with open(self.dir / ".lock", "a+b") as fh:
                if sys.platform == "win32":
                    import msvcrt
                    while True:
                        try:
                            fh.seek(0)
                            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                            break
                        except OSError:
                            time.sleep(0.05)
                else:
                    import fcntl
                    fcntl.flock(fh, fcntl.LOCK_EX)
                self._depth = 1
                try:
                    yield
                finally:
                    self._depth = 0
                    if sys.platform == "win32":
                        fh.seek(0)
                        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(fh, fcntl.LOCK_UN)

    def _write_atomic(self, name: str, data: bytes):
        self._ensure_dir()
        tmp = self.dir / f".{name}.{uuid.uuid4().hex}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.dir / name)

    def host_id(self) -> str:
        """ext_agent_host_id : créé UNE fois, avant toute connexion, puis réutilisé."""
        path = self.dir / "host.json"
        with self.process_lock():
            if path.exists():
                value = json.loads(path.read_text("utf-8"))["ext_agent_host_id"]
                if re.fullmatch(r"urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}"
                                r"-[0-9a-f]{12}", value):
                    return value
                raise SiwcError("host_identity_invalid", "host.json illisible : ne pas l'écraser.")
            value = f"urn:uuid:{uuid.uuid4()}"
            self._write_atomic("host.json", json.dumps({"version": 1,
                                                        "ext_agent_host_id": value}).encode())
            return value

    def read(self) -> dict:
        path = self.dir / "auth.bin"
        if not path.exists():
            return {"version": 1, "active": None, "profiles": {}}
        return json.loads(_dpapi(path.read_bytes(), protect=False).decode("utf-8"))

    def write(self, state: dict):
        self._write_atomic("auth.bin", _dpapi(json.dumps(state).encode("utf-8"), protect=True))

    def flag(self, name: str) -> bool:
        return (self.dir / f"{name}.flag").exists()

    def set_flag(self, name: str):
        self._write_atomic(f"{name}.flag", b"1")


# ── Connexion : autorisation + callback loopback + échange du code ────────────

class _CallbackServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def _handler(expected_state: str, outcome: dict, done: threading.Event):
    class Handler(BaseHTTPRequestHandler):
        timeout = 10

        def log_message(self, *args):        # ne JAMAIS journaliser l'URL (code d'autorisation)
            pass

        def _reply(self, status: int, text: str):
            body = (f"<!doctype html><meta charset='utf-8'><title>PANDORA</title>"
                    f"<p style='font:16px system-ui;margin:20vh auto;max-width:30rem'>{text}</p>"
                    "<script>history.replaceState(null,'','/')</script>").encode("utf-8")
            self.send_response(status)
            for key, value in (("Content-Type", "text/html; charset=utf-8"),
                               ("Cache-Control", "no-store"), ("Referrer-Policy", "no-referrer"),
                               ("Content-Length", str(len(body)))):
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            port = self.server.server_address[1]
            parts = urlsplit(self.path)
            if (self.headers.get("Host") != f"127.0.0.1:{port}" or parts.path != CALLBACK_PATH
                    or done.is_set()):
                return self._reply(404, "Introuvable.")
            query = parse_qs(parts.query, keep_blank_values=True)
            states = query.get("state", [])
            if len(states) != 1 or not hmac.compare_digest(states[0].encode(),
                                                            expected_state.encode()):
                return self._reply(400, "État de connexion invalide : revenez à l'onglet "
                                        "ouvert par PANDORA.")
            outcome["query"] = query
            done.set()
            if "error" in query:
                return self._reply(200, "Connexion annulée. Vous pouvez fermer cet onglet.")
            return self._reply(200, "Connexion terminée. Vous pouvez fermer cet onglet "
                                    "et revenir dans PANDORA.")

    return Handler


def _credentials(tok: dict, previous_scopes=None) -> dict:
    scope = tok.get("scope") if isinstance(tok.get("scope"), str) else " ".join(previous_scopes or [])
    scopes = scope.split()
    expires_in = tok.get("expires_in")
    if (not scopes or str(tok.get("token_type", "")).lower() != "bearer"
            or not isinstance(tok.get("access_token"), str) or not tok["access_token"]
            or not isinstance(expires_in, (int, float)) or expires_in <= 0
            or ("offline_access" in scopes and not tok.get("refresh_token"))):
        raise SiwcError("invalid_token_response", "Réponse de jeton incomplète.")
    earliest = tok.get("earliest_refresh_at")
    if isinstance(earliest, str):
        with contextlib.suppress(ValueError):
            earliest = datetime.fromisoformat(earliest.replace("Z", "+00:00")).timestamp()
    received = time.time()
    return {"access_token": tok["access_token"], "refresh_token": tok.get("refresh_token"),
            "expires_at": received + expires_in, "scopes": scopes, "saved_at": received,
            "earliest_refresh_at": earliest if isinstance(earliest, (int, float)) else None}


def sign_in(store: CredentialStore, profile_id: str | None = None, reconsent: bool = False,
            open_browser=webbrowser.open, wait_s: int = 600,
            cancel: threading.Event | None = None) -> dict:
    """Nouveau compte (profile_id=None) ou reconnexion d'un profil existant.
    `cancel` : posé par le bouton Annuler de l'interface."""
    disc = discovery()
    host_id = store.host_id()                        # persisté AVANT d'ouvrir le navigateur
    with store.process_lock():
        state_doc = store.read()
    previous = state_doc["profiles"].get(profile_id) if profile_id else None
    saved_client = previous["client_id"] if previous else None
    pid = profile_id or uuid.uuid4().hex
    tok = None
    for attempt in range(2):                         # invalid_grant : 1 nouvel essai, même client_id
        state, nonce = random_value(), random_value()
        verifier, challenge = pkce_pair()
        done, outcome = threading.Event(), {}
        server = _CallbackServer(("127.0.0.1", 0), _handler(state, outcome, done))
        redirect_uri = f"http://127.0.0.1:{server.server_address[1]}{CALLBACK_PATH}"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            params = {"client_id": saved_client or REGISTRATION_CLIENT, "response_type": "code",
                      "redirect_uri": redirect_uri, "scope": SCOPES, "resource": RESOURCE,
                      "state": state, "nonce": nonce, "code_challenge": challenge,
                      "code_challenge_method": "S256", "ext_agent_host_id": host_id}
            if not saved_client:
                params["agent_name_hint"] = APP_NAME       # 1re inscription seulement
            elif previous and previous.get("email"):
                params["login_hint"] = previous["email"]   # jamais d'id_token_hint dans l'URL
            if reconsent:
                params["prompt"] = "consent"                # seulement sur choix explicite
            open_browser(disc["authorization_endpoint"] + "?" + urlencode(params))
            deadline = time.monotonic() + wait_s
            while not done.wait(0.25):
                if cancel is not None and cancel.is_set():
                    raise SiwcError("cancelled", "Connexion annulée.")
                if time.monotonic() > deadline:
                    raise SiwcError("timeout", "Connexion non terminée.")
        finally:
            server.shutdown()
            server.server_close()
        query = outcome["query"]
        if "error" in query:                                 # access_denied : rien à échanger
            raise SiwcError(query["error"][0], "Connexion refusée ou annulée.")
        codes, returned = query.get("code", []), query.get("client_id", [])
        client_id = returned[0] if len(returned) == 1 else saved_client
        if (len(codes) != 1 or len(returned) > 1 or not client_id
                or client_id == REGISTRATION_CLIENT
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", client_id)
                or (saved_client and returned and returned[0] != saved_client)):
            raise SiwcError("registration_incomplete", "Inscription ChatGPT incomplète.")
        with store.process_lock():                      # client_id émis sauvé AVANT l'échange
            state_doc = store.read()
            entry = state_doc["profiles"].setdefault(pid, {})
            entry.update(client_id=client_id, status=entry.get("status", "pending"))
            store.write(state_doc)
        saved_client = client_id
        try:
            tok = _post_form(disc["token_endpoint"], {
                "grant_type": "authorization_code", "client_id": client_id, "code": codes[0],
                "code_verifier": verifier, "redirect_uri": redirect_uri, "resource": RESOURCE})
            break
        except SiwcError as exc:
            if exc.code != "invalid_grant" or attempt:
                raise
            previous = previous or {"client_id": client_id}
    claims = verify_id_token(tok.get("id_token"), client_id, nonce)
    if previous and previous.get("subject") and claims["sub"] != previous["subject"]:
        raise SiwcError("account_mismatch", "Ce n'est pas le compte ChatGPT de ce profil.")
    creds = _credentials(tok)
    with store.process_lock():
        state_doc = store.read()
        entry = state_doc["profiles"][pid]
        entry.update(creds, client_id=client_id, subject=claims["sub"],
                     email=claims.get("email"), name=claims.get("name"),
                     id_token=tok["id_token"], status="connected",
                     plan_enabled=PLAN_SCOPE in creds["scopes"], plan_paused=False,
                     not_eligible=False)
        state_doc["active"] = pid
        store.write(state_doc)
    return entry


# ── Rafraîchissement sérialisé ────────────────────────────────────────────────

def access_token(store: CredentialStore, pid: str) -> str:
    with store.process_lock():                         # relire sous verrou : un autre processus
        state_doc = store.read()                       # a peut-être déjà fait la rotation
        p = state_doc["profiles"][pid]
        if p.get("status") != "connected" or not p.get("access_token"):
            raise SiwcError("reauth_required", "Reconnectez votre compte ChatGPT.")
        if not p.get("plan_enabled"):
            raise SiwcError("plan_not_enabled", "Usage du forfait non autorisé pour ce compte.")
        now = time.time()
        if p["expires_at"] - now > 60:
            return p["access_token"]
        earliest = p.get("earliest_refresh_at")
        if earliest and earliest > now:
            if p["expires_at"] > now:
                return p["access_token"]
            raise SiwcError("refresh_not_ready", retryable=True)
        try:
            tok = _post_form(discovery()["token_endpoint"], {
                "grant_type": "refresh_token", "client_id": p["client_id"],
                "refresh_token": p["refresh_token"], "resource": RESOURCE})   # pas de `scope`
        except SiwcError as exc:
            if exc.code in TERMINAL_REFRESH or exc.reason in TERMINAL_REFRESH:
                for key in ("access_token", "refresh_token", "id_token"):
                    p.pop(key, None)
                p["status"] = "reauth_required"           # client_id et sujet GARDÉS
                store.write(state_doc)
                raise SiwcError("reauth_required",
                                "Session ChatGPT expirée : reconnectez-vous.") from None
            raise
        creds = _credentials(tok, previous_scopes=p["scopes"])
        received = time.time()
        p.update(creds)
        store.write(state_doc)                          # persister la rotation tout de suite
        if isinstance(tok.get("id_token"), str):        # nouvel ID token : même sujet exigé
            try:
                claims = verify_id_token(tok["id_token"], p["client_id"], None, now=received)
            except SiwcError as exc:
                if exc.code != "identity_verification_unavailable":
                    p["status"] = "reauth_required"
                    store.write(state_doc)
                    raise
                claims = None
            if claims is not None:
                if claims["sub"] != p["subject"]:
                    p["status"] = "reauth_required"
                    store.write(state_doc)
                    raise SiwcError("account_mismatch")
                p["id_token"] = tok["id_token"]
        p["plan_enabled"] = PLAN_SCOPE in p["scopes"]
        store.write(state_doc)
        return p["access_token"]


def sign_out(store: CredentialStore, pid: str) -> bool:
    """Révoque le refresh token puis efface les jetons locaux. False = révocation non confirmée."""
    requests = _requests()
    with store.process_lock():
        state_doc = store.read()
        p = state_doc["profiles"][pid]
        confirmed = False
        if p.get("refresh_token"):
            for _attempt in range(2):
                try:
                    r = requests.post(discovery()["revocation_endpoint"], timeout=10,
                                      allow_redirects=False,
                                      data={"token": p["refresh_token"],
                                            "token_type_hint": "refresh_token",
                                            "client_id": p["client_id"]})
                    if r.status_code == 200:
                        confirmed = True
                        break
                    if r.status_code < 500:
                        break
                except (requests.RequestException, SiwcError):
                    pass
                time.sleep(0.3)
        for key in ("access_token", "refresh_token", "id_token", "expires_at",
                    "earliest_refresh_at"):
            p.pop(key, None)
        p.update(status="disconnected", scopes=[], plan_enabled=False)
        store.write(state_doc)
        return confirmed


# ── Modèles et inférence en flux SSE ──────────────────────────────────────────

def list_models(token: str) -> list[dict]:
    """Catalogue PROPRE AU COMPTE (tableau `models`, pas `data`) ; display_name affiché."""
    r = _get(API_BASE + "/models", timeout=30,
             headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    body = _json_or_none(r)
    if r.status_code != 200:
        raise api_error(r.status_code, body, r.headers.get("x-request-id"))
    return [{"slug": m["slug"], "display_name": m.get("display_name") or m["slug"]}
            for m in (body or {}).get("models", [])
            if m.get("visibility") == "list" and m.get("slug")]


def sse_events(chunks, max_event=4 * 1024 * 1024):
    """Découpe un flux SSE (LF, CRLF ou CR, même coupés entre deux morceaux) en objets JSON."""
    buf, data = b"", []
    for chunk in chunks:
        buf += chunk
        while True:
            i_n, i_r = buf.find(b"\n"), buf.find(b"\r")
            if i_n < 0 and i_r < 0:
                break
            if i_r >= 0 and (i_n < 0 or i_r < i_n):
                if i_r == len(buf) - 1:
                    break                                # attendre : \r\n peut être coupé
                line = buf[:i_r]
                buf = buf[i_r + (2 if buf[i_r + 1:i_r + 2] == b"\n" else 1):]
            else:
                line, buf = buf[:i_n], buf[i_n + 1:]
            if line == b"":
                if data:
                    payload, data = b"\n".join(data), []
                    if payload != b"[DONE]":
                        yield json.loads(payload)
            elif line.startswith(b"data:"):
                data.append(line[6:] if line[5:6] == b" " else line[5:])
                if sum(map(len, data)) > max_event:
                    raise SiwcError("invalid_stream", "Événement trop volumineux.")
        if len(buf) > max_event:
            raise SiwcError("invalid_stream", "Ligne trop volumineuse.")
    tail = buf.rstrip(b"\r")
    if tail.startswith(b"data:"):
        data.append(tail[6:] if tail[5:6] == b" " else tail[5:])
    if data and b"\n".join(data) != b"[DONE]":
        yield json.loads(b"\n".join(data))


def stream_response(token: str, model: str, input_items: list, instructions: str | None = None,
                    on_delta=None, extra: dict | None = None, plan_route: bool = True):
    """POST /v1/responses en flux. → (texte, objet `response` final)."""
    requests = _requests()
    body = {"model": model, "input": input_items, "store": False, "stream": True}
    if instructions:
        body["instructions"] = instructions             # jamais d'item rôle « system »
    body.update(extra or {})
    if plan_route:
        for key in FORBIDDEN_FIELDS:
            body.pop(key, None)
        body.update(store=False, stream=True)
    try:
        r = requests.post(API_BASE + "/responses", json=body, stream=True, timeout=(15, 300),
                          headers={"Authorization": f"Bearer {token}",
                                   "Accept": "text/event-stream",
                                   "User-Agent": f"{APP_NAME}"})
    except requests.RequestException as exc:
        raise SiwcError("network_error", str(exc), retryable=True) from None
    rid = r.headers.get("x-request-id")
    text: list[str] = []
    try:
        if r.status_code != 200:
            raise api_error(r.status_code, _json_or_none(r), rid)
        ctype = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if ctype and ctype != "text/event-stream":      # sans Content-Type : accepté
            raise SiwcError("invalid_stream", status=r.status_code, request_id=rid)
        for event in sse_events(r.iter_content(chunk_size=None)):
            kind = event.get("type")
            if kind == "response.output_text.delta":
                text.append(event.get("delta", ""))
                if on_delta:
                    on_delta(event.get("delta", ""))
            elif kind in ("response.failed", "error"):
                err = (event.get("response") or {}).get("error") if kind == "response.failed" else event
                exc = api_error(r.status_code, {"error": err or {}}, rid)
                exc.partial_text = "".join(text)
                raise exc
            elif kind == "response.incomplete":
                reason = ((event.get("response") or {}).get("incomplete_details") or {}).get("reason")
                raise SiwcError("response_incomplete", str(reason), request_id=rid,
                                retryable=True, partial_text="".join(text), reason=reason)
            elif kind == "response.completed":
                return "".join(text), event.get("response") or {}
    except requests.RequestException:
        pass                                             # coupure : traitée ci-dessous
    except ValueError:
        raise SiwcError("invalid_stream", "Événement SSE illisible.", request_id=rid,
                        retryable=True, partial_text="".join(text)) from None
    finally:
        r.close()
    raise SiwcError("stream_interrupted", "Flux terminé sans response.completed.",
                    request_id=rid, retryable=True, partial_text="".join(text))


# ── État du compte (pour l'interface) ─────────────────────────────────────────

_STORE: CredentialStore | None = None


def store() -> CredentialStore:
    global _STORE
    if _STORE is None or (os.environ.get("PANDORA_CHATGPT_DIR")
                          and _STORE.dir != Path(os.environ["PANDORA_CHATGPT_DIR"])):
        _STORE = CredentialStore()
    return _STORE


def active_profile(st: CredentialStore | None = None) -> tuple[str | None, dict]:
    st = st or store()
    if not st.has_data():                    # jamais connecté : rien à lire, rien à créer
        return None, {}
    try:
        with st.process_lock():
            doc = st.read()
    except Exception:
        return None, {}
    pid = doc.get("active")
    return pid, dict((doc.get("profiles") or {}).get(pid) or {})


def status(st: CredentialStore | None = None) -> dict:
    """Résumé lisible par l'interface (aucun jeton) :
    state ∈ disconnected | connected | reauth_required | paused | not_eligible | plan_off."""
    pid, p = active_profile(st)
    if not pid or not p:
        return {"state": "disconnected", "email": "", "name": "", "models": []}
    if p.get("status") == "reauth_required":
        state = "reauth_required"
    elif p.get("status") != "connected":
        state = "disconnected"
    elif not p.get("plan_enabled"):
        state = "plan_off"
    elif p.get("not_eligible"):
        state = "not_eligible"
    elif p.get("plan_paused"):
        state = "paused"
    else:
        state = "connected"
    return {"state": state, "email": p.get("email") or "", "name": p.get("name") or "",
            "models": list(p.get("models") or []),
            "expires_at": p.get("expires_at") or 0}


def set_profile_fields(st: CredentialStore | None = None, **fields) -> None:
    st = st or store()
    with st.process_lock():
        doc = st.read()
        pid = doc.get("active")
        if pid and pid in doc.get("profiles", {}):
            doc["profiles"][pid].update(fields)
            st.write(doc)


def connect(open_browser=webbrowser.open, cancel: threading.Event | None = None,
            st: CredentialStore | None = None) -> dict:
    """Connexion (ou reconnexion du profil actif) puis catalogue des modèles.
    → status() à jour."""
    st = st or store()
    pid, p = active_profile(st)
    sign_in(st, profile_id=pid if p.get("client_id") else None,
            open_browser=open_browser, cancel=cancel)
    pid, p = active_profile(st)
    if p.get("plan_enabled"):
        try:
            models = list_models(access_token(st, pid))
            set_profile_fields(st, models=models)
        except SiwcError:
            pass
    return status(st)


def disconnect(st: CredentialStore | None = None) -> bool:
    st = st or store()
    pid, p = active_profile(st)
    if not pid:
        return True
    return sign_out(st, pid)


def resume_plan(st: CredentialStore | None = None) -> None:
    """« Réessayer le forfait » : lève la pause posée par une limite atteinte."""
    set_profile_fields(st, plan_paused=False)


# ── Appel complet : forfait d'abord, clé API seulement sur choix explicite ────

def to_responses_input(messages: list) -> list:
    """Messages PANDORA (blocs façon Anthropic) → entrées de l'API Responses."""
    items = []
    for m in messages or []:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        content = m.get("content", "")
        if isinstance(content, str):
            items.append({"role": role, "content": content})
            continue
        parts = []
        for block in content or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append({"type": "input_text" if role == "user" else "output_text",
                              "text": block.get("text", "")})
            elif block.get("type") == "image" and role == "user":
                src = block.get("source") or {}
                if src.get("type") == "base64" and src.get("data"):
                    mime = src.get("media_type") or "image/jpeg"
                    parts.append({"type": "input_image",
                                  "image_url": f"data:{mime};base64,{src['data']}"})
        items.append({"role": role, "content": parts or ""})
    return items


def complete(model: str, system: str, messages: list, on_delta=None,
             st: CredentialStore | None = None) -> tuple[str, dict]:
    """Une réponse complète par le forfait ChatGPT. Lève SiwcError (code exploitable
    par l'appelant) ; met le forfait en pause sur une limite atteinte et marque un
    compte non éligible (Free / Go) — jamais de bascule silencieuse."""
    st = st or store()
    pid, p = active_profile(st)
    if not pid:
        raise SiwcError("not_connected", "Compte ChatGPT non connecté.")
    if p.get("plan_paused"):
        raise SiwcError("plan_paused", "Forfait ChatGPT en pause (limite atteinte).")
    if p.get("not_eligible"):
        raise SiwcError("subscription_sharing_user_not_eligible",
                        "Forfait ChatGPT non éligible (Plus ou Pro requis).")
    if not model:
        models = p.get("models") or []
        model = models[0]["slug"] if models else ""
    if not model:
        raise SiwcError("no_model", "Aucun modèle ChatGPT disponible pour ce compte.")
    error = None
    for attempt in range(3):
        sent = []

        def _relay(delta, _sent=sent):
            _sent.append(delta)
            if on_delta:
                on_delta(delta)
        try:
            token = access_token(st, pid)
            return stream_response(token, model, to_responses_input(messages), system or None,
                                   _relay)
        except SiwcError as exc:
            error = exc
            # Ne réessayer que si RIEN n'a encore été affiché (un texte partiel déjà
            # transmis ne peut pas être retiré de l'écran de l'appelant).
            if ((exc.code in RETRY_LATER or exc.code == "refresh_not_ready")
                    and attempt < 2 and not sent):
                time.sleep((2, 8)[attempt])
                continue
            break
    if error.code in PAUSE_PLAN:
        set_profile_fields(st, plan_paused=True)
    elif error.code in NOT_ELIGIBLE:
        set_profile_fields(st, not_eligible=True)
    raise error


def user_message(exc: SiwcError) -> str:
    """Message français (traduit par l'interface) pour une erreur du forfait."""
    code = getattr(exc, "code", "") or ""
    if code in PAUSE_PLAN or code == "plan_paused":
        return ("Limite d'utilisation de votre forfait ChatGPT atteinte. Gérer l'utilisation : "
                f"{USAGE_URL}")
    if code in NOT_ELIGIBLE:
        return ("Ce compte ChatGPT ne peut pas utiliser son forfait dans PANDORA "
                "(forfait Plus ou Pro requis).")
    if code in RECONNECT or code in ("not_connected", "plan_not_enabled"):
        return ("Session ChatGPT expirée ou non connectée : Paramètres → Assistant IA → "
                "« Continuer avec ChatGPT ».")
    if code in RETRY_LATER or code in ("network_error", "server_error", "stream_interrupted"):
        return "Service ChatGPT momentanément indisponible : réessayez dans un instant."
    if code == "response_incomplete":
        return "Réponse ChatGPT incomplète : réessayez."
    if code == "no_model":
        return "Aucun modèle ChatGPT disponible pour ce compte."
    detail = str(exc) if str(exc) and str(exc) != code else ""
    return f"Erreur ChatGPT ({code})" + (f" : {detail}" if detail else "")
