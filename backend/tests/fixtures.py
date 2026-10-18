"""Builds small PDFs for tests (text lecture, text booklet, scanned booklet)."""
import pymupdf

LECTURE_PAGES = [
    """Chapitre 2 : Dynamique des fluides parfaits

Equation de Bernoulli
Pour un fluide parfait incompressible en ecoulement permanent, le long d'une ligne de courant :
p + 1/2 rho v^2 + rho g z = constante
ou p est la pression statique (Pa), v la vitesse (m/s) et z l'altitude (m).

Tube de Pitot
La difference entre pression totale et pression statique donne la vitesse : v = sqrt(2 (p0 - p) / rho).""",
    """Pertes de charge
Dans une conduite reelle, la perte de charge reguliere s'ecrit avec la formule de Darcy-Weisbach :
Delta p = lambda (L / D) (rho v^2 / 2)
Le coefficient lambda depend du nombre de Reynolds Re = rho v D / mu et de la rugosite relative.
En regime laminaire (Re < 2000), lambda = 64 / Re.""",
]

BOOKLET_PAGES = [
    """TD Mecanique des fluides

Chapitre 1 : Statique des fluides

Exercice 1 : Manometre en U
Un manometre en U contient du mercure. On mesure une denivellation h = 12 cm.
Donnees : rho_Hg = 13600 kg/m3 ; g = 9,81 m/s2
a) Exprimer la difference de pression entre les deux branches.
b) Calculer cette difference en Pa.
Correction
a) Delta p = rho_Hg g h
b) Delta p = 13600 x 9,81 x 0,12 = 16 010 Pa

Exercice 2 : Barrage
Un barrage vertical de largeur L = 50 m retient une hauteur d'eau H = 20 m.
1) Calculer la force de pression totale exercee sur le barrage.
2) Determiner le point d'application de cette force.""",
    """Chapitre 2 : Dynamique des fluides parfaits

Exercice 3 : Venturi
De l'eau s'ecoule dans un tube de Venturi. Section d'entree S1 = 20 cm2, col S2 = 5 cm2.
La difference de pression mesuree est 15 kPa.
a) Calculer la vitesse au col.
b) En deduire le debit volumique.

Corriges

Exercice 2
1) F = rho g L H^2 / 2 = 98,1 MN
2) Le point d'application est a H/3 du fond.""",
]


def _write_pages(path, pages):
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 545, 800), text, fontsize=10, fontname="helv")
    doc.save(path)
    doc.close()
    return path


def make_lecture(path):
    return _write_pages(path, LECTURE_PAGES)


def make_booklet(path):
    return _write_pages(path, BOOKLET_PAGES)


def make_scanned(path, source_pages=BOOKLET_PAGES[:1]):
    """Render text pages to images and build an image-only PDF, like a scanner would."""
    text_doc = pymupdf.open()
    for text in source_pages:
        page = text_doc.new_page()
        page.insert_textbox(pymupdf.Rect(50, 50, 545, 800), text, fontsize=12, fontname="helv")
    out = pymupdf.open()
    for page in text_doc:
        pix = page.get_pixmap(dpi=200)
        img_page = out.new_page(width=page.rect.width, height=page.rect.height)
        img_page.insert_image(img_page.rect, pixmap=pix)
    out.save(path)
    return path
