"""tools/make_readme_banner.py — La bannière du README GitHub (docs/readme/).

Demande Matthieu (27/10/2026) : « mettre le nouveau logo avec en dessous le titre
PANDORA avec la police utilisée au démarrage de PANDORA ». La page de démarrage
(ui/start_page.py) écrit « P A N D O R A » sans police imposée — la police du
système, Segoe UI sous Windows — à 30 px, graisse normale, espacement 7 px, puis
« by 22eme ARKANE » et un trait. On reproduit exactement cette composition, sur
le fond noir aux circuits dorés de la même page, en grand (×3) pour GitHub.

    python tools/make_readme_banner.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QImage, QLinearGradient, QPainter, \
    QRadialGradient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "readme", "pandora_banner.png")
K = 3                                   # échelle : 1 px de la page = 3 px ici
W, H = 1600, 760


def main() -> int:
    app = QGuiApplication(sys.argv)     # noqa: F841 — les polices en ont besoin
    img = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(8, 8, 8))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    bg = QImage(os.path.join(ROOT, "assets", "start_background_v4.jpg"))
    if not bg.isNull():
        scale = max(W / bg.width(), H / bg.height())
        sw, sh = W / scale, H / scale
        p.drawImage(QRectF(0, 0, W, H), bg,
                    QRectF((bg.width() - sw) / 2, (bg.height() - sh) / 2, sw, sh))
    veil = QLinearGradient(0, 0, 0, H)
    veil.setColorAt(0.0, QColor(6, 6, 6, 70))
    veil.setColorAt(1.0, QColor(5, 5, 5, 110))
    p.fillRect(QRectF(0, 0, W, H), veil)
    halo = QRadialGradient(W / 2, H * 0.52, W * 0.34)
    halo.setColorAt(0.0, QColor(5, 5, 5, 200))
    halo.setColorAt(0.6, QColor(5, 5, 5, 120))
    halo.setColorAt(1.0, QColor(5, 5, 5, 0))
    p.fillRect(QRectF(0, 0, W, H), halo)

    logo = QImage(os.path.join(ROOT, "assets", "app_icon.png"))
    size = 72 * K
    top = 120
    if not logo.isNull():
        p.drawImage(QRectF((W - size) / 2, top, size, size), logo)

    family = "Segoe UI" if sys.platform.startswith("win") else QFont().family()
    title = QFont(family)
    title.setPixelSize(30 * K)
    title.setWeight(QFont.Weight.Normal)
    title.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 7 * K)
    p.setFont(title)
    p.setPen(QColor("#e6ecf5"))
    y = top + size + 8 * K
    p.drawText(QRectF(0, y, W, 44 * K), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
               "P A N D O R A")
    y += 44 * K
    by = QFont(family)
    by.setPixelSize(10 * K)
    by.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2 * K)
    p.setFont(by)
    p.setPen(QColor("#8a93ac"))
    p.drawText(QRectF(0, y, W, 16 * K), Qt.AlignmentFlag.AlignHCenter, "by 22eme ARKANE")
    y += 16 * K + 6 * K
    p.fillRect(QRectF((W - 28 * K) / 2, y, 28 * K, K), QColor("#7c6bff"))
    p.end()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if not img.save(OUT):
        print("Écriture impossible :", OUT)
        return 1
    print("Bannière :", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
