"""core/net_diag.py — Diagnostic réseau du poste, pour des messages d'erreur utiles.

Constat Matthieu du 05/10/2026 : BytePlus et Runware coupaient la connexion de
PANDORA (« ConnectionResetError 10054 — Une connexion existante a dû être
fermée par l'hôte distant ») tant que NordVPN était actif ; VPN coupé, tout est
passé. Le message brut ne laissait rien deviner, et l'on a d'abord cherché du
côté du compte BytePlus.

`active_vpn()` nomme la carte réseau d'un VPN EN SERVICE sur le poste — Windows
seulement, sans appel réseau ni processus externe (iphlpapi.GetAdaptersAddresses).
`advice()` en tire la phrase à ajouter aux erreurs de connexion coupée.
Module NEUTRE (aucune dépendance Qt) : distributeurs, workers et IA texte.
"""
from __future__ import annotations

import sys

#: Ce qui signe une carte réseau de VPN (nom ou description, en minuscules).
#: Les réseaux maillés (Tailscale, ZeroTier…) sont exclus : ils ne font pas
#: passer le trafic Internet par défaut.
_VPN_MARKERS = (
    "nordlynx", "nordvpn", "wireguard", "wintun", "tap-windows", "openvpn", "proton",
    "mullvad", "surfshark", "expressvpn", "lightway", "windscribe", "cyberghost",
    "private internet access", "ipvanish", "hotspot shield", "tunnelbear", "vyprvpn",
    "anyconnect", "forticlient", "fortinet", "globalprotect", "pangp", "zscaler",
    "cloudflare warp", "vpn",
)

#: Ce qui signe une connexion COUPÉE en cours de route (pas un refus, pas un
#: serveur éteint) : réinitialisation TCP, fermeture par l'hôte distant.
_CUT_MARKERS = (
    "10054", "connectionreseterror", "connection reset", "connection aborted",
    "remotedisconnected", "remote end closed", "server disconnected",
    "remoteprotocolerror", "forcibly closed", "fermée par l'hôte distant",
    "fermée par l’hôte distant",
)

VPN_ADVICE = ("Un VPN est actif sur ce poste ({vpn}) : c'est la cause la plus probable. "
              "Désactive-le le temps de la génération, ou exclus PANDORA du VPN (réglage "
              "« split tunneling » / tunnel fractionné), puis relance.")
NO_VPN_ADVICE = ("Causes les plus fréquentes : un VPN ou un pare-feu qui filtre PANDORA "
                 "(désactive-le, ou exclus PANDORA du VPN), ou une coupure réseau "
                 "passagère — relance.")


def _windows_adapters() -> list[tuple[str, str, bool]]:
    """[(nom, description, en service)] des cartes réseau Windows."""
    import ctypes
    from ctypes import wintypes

    class _Adapter(ctypes.Structure):
        pass
    # IP_ADAPTER_ADDRESSES, jusqu'au champ OperStatus (le reste n'est pas lu).
    _Adapter._fields_ = [
        ("Length", wintypes.ULONG), ("IfIndex", wintypes.DWORD),
        ("Next", ctypes.POINTER(_Adapter)), ("AdapterName", ctypes.c_char_p),
        ("FirstUnicastAddress", ctypes.c_void_p), ("FirstAnycastAddress", ctypes.c_void_p),
        ("FirstMulticastAddress", ctypes.c_void_p), ("FirstDnsServerAddress", ctypes.c_void_p),
        ("DnsSuffix", ctypes.c_wchar_p), ("Description", ctypes.c_wchar_p),
        ("FriendlyName", ctypes.c_wchar_p), ("PhysicalAddress", ctypes.c_ubyte * 8),
        ("PhysicalAddressLength", wintypes.ULONG), ("Flags", wintypes.ULONG),
        ("Mtu", wintypes.ULONG), ("IfType", wintypes.DWORD), ("OperStatus", ctypes.c_int),
    ]
    fn = ctypes.windll.iphlpapi.GetAdaptersAddresses
    fn.argtypes = [wintypes.ULONG, wintypes.ULONG, ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.POINTER(wintypes.ULONG)]
    fn.restype = wintypes.ULONG
    size = wintypes.ULONG(16 * 1024)
    buf = None
    for _ in range(4):
        buf = ctypes.create_string_buffer(size.value)
        # AF_UNSPEC, et sans les listes d'adresses (0x0F) : seuls les noms servent.
        rc = fn(0, 0x0F, None, buf, ctypes.byref(size))
        if rc == 0:
            break
        if rc != 111:                       # autre chose que ERROR_BUFFER_OVERFLOW
            return []
    else:
        return []
    out = []
    p = ctypes.cast(buf, ctypes.POINTER(_Adapter))
    while p:
        a = p.contents
        out.append((a.FriendlyName or "", a.Description or "", a.OperStatus == 1))
        p = a.Next
    return out


def active_vpn() -> str:
    """Nom de la carte d'un VPN en service sur ce poste ("" sinon, ou hors Windows)."""
    if sys.platform != "win32":
        return ""
    try:
        adapters = _windows_adapters()
    except Exception:
        return ""
    for name, desc, up in adapters:
        if not up:
            continue
        if any(m in name.lower() for m in _VPN_MARKERS):
            return name
        # « Connexion au réseau local » ne dit rien : la description, oui
        # (« TAP-NordVPN Windows Adapter V9 »).
        if any(m in desc.lower() for m in _VPN_MARKERS):
            return desc
    return ""


def is_connection_cut(text: str) -> bool:
    """L'erreur dit-elle une connexion COUPÉE en cours de route ?"""
    low = (text or "").lower()
    return any(m in low for m in _CUT_MARKERS)


def advice(translate=None) -> str:
    """Phrase à ajouter à une connexion coupée : le VPN actif s'il y en a un.
    `translate` (core.i18n.translate) traduit le modèle de phrase AVANT d'y
    placer le nom de la carte."""
    tr = translate or (lambda s: s)
    vpn = active_vpn()
    return tr(VPN_ADVICE).format(vpn=vpn) if vpn else tr(NO_VPN_ADVICE)
