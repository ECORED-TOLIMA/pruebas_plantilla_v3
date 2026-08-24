#!/usr/bin/env python3
"""Ajusta por correlación una foto RECORTADA dentro de una COMPOSICIÓN (adornos + foto).

Cuándo se usa: cuando el bloque del diseño no es una foto ni un grupo que el pipeline saque
entero, sino una composición de hermanos (una forma de color detrás, la foto recortada encima y
un adorno delante) y el encuadre de la foto sale mal. `fit_foto.py` no sirve porque compara el
rectángulo COMPLETO contra el PDF y las zonas transparentes de la foto (que en el diseño dejan
ver el color de detrás) hunden la correlación.

Aquí se renderizan las capas de adorno con `render_svg_multi` (seleccionadas por NOMBRE, porque
sus bboxes están anidados y `--rect` no las puede separar), y se busca la (escala, dx, dy) de la
foto que maximiza la correlación de la COMPOSICIÓN contra el mismo rectángulo del PDF.

  fit_composicion.py <artboard> <pagina> <x> <y> <w> <h> <salida.png>
      --detras NOMBRE[,NOMBRE...] --foto NOMBRE_DEL_GRUPO [--delante NOMBRE[,...]]
      [--escala N]
"""
import glob
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
C.pipeline()
import xd_export as X  # noqa: E402
import xd_patches  # noqa: E402
import xd_patches as P  # noqa: E402

XDDIR = C.XDDIR
RES = C.RES
CACHE = C.CACHE_PDF
Image.MAX_IMAGE_PIXELS = None
DX = float(os.environ.get('XD_DX', 0))
DY = float(os.environ.get('XD_DY', 0))


def arg(nombre, defecto=None):
    return sys.argv[sys.argv.index(nombre) + 1] if nombre in sys.argv else defecto


def buscar(raiz, nombres):
    """(nodo, matriz_acumulada_del_padre) para cada nombre pedido, en orden de árbol."""
    out = []

    def walk(ns, m):
        for n in ns:
            if n.get('name') in nombres:
                out.append((n, m))
            if n.get('type') == 'group':
                walk((n.get('group') or {}).get('children', []),
                     X.mat_mul(m, X.node_transform(n)))
    walk(raiz, X.IDENTITY)
    return out


def rasterizar(svg, w, h, escala):
    svg = P.remapear_paleta(svg)   # paleta vieja del arte -> hoja de spec
    tmp = tempfile.mkdtemp()
    open(f'{tmp}/a.svg', 'w').write(svg)
    W, H = round(w * escala), round(h * escala)
    open(f'{tmp}/a.html', 'w').write(
        f'<html><body style="margin:0;background:transparent">'
        f'<img src="a.svg" style="width:{W}px;height:{H}px"></body></html>')
    subprocess.run(['google-chrome', '--headless=new', '--disable-gpu', '--no-sandbox',
                    '--hide-scrollbars', '--default-background-color=00000000',
                    '--virtual-time-budget=4000', f'--window-size={W},{H + 200}',
                    f'--screenshot={tmp}/a.png', f'{tmp}/a.html'],
                   capture_output=True)
    return Image.open(f'{tmp}/a.png').convert('RGBA').crop((0, 0, W, H))


def capa(raiz, nombres, bb, w, h, escala):
    """Una capa PNG (RGBA) con sólo esos nodos, en el rectángulo pedido."""
    if not nombres:
        return Image.new('RGBA', (round(w * escala), round(h * escala)), (0, 0, 0, 0))
    items = [(n, X.mat_mul(m, X.node_transform(n))) for n, m in buscar(raiz, set(nombres))]
    svg = X.render_svg_multi(items, bb, resources_dir=RES)
    return rasterizar(svg, w, h, escala)


def main():
    prefijo, pagina = sys.argv[1], int(sys.argv[2])
    x, y, w, h = (float(v) for v in sys.argv[3:7])
    salida = sys.argv[7]
    escala = float(arg('--escala', 1))
    detras = [s for s in (arg('--detras', '') or '').split(',') if s]
    delante = [s for s in (arg('--delante', '') or '').split(',') if s]
    nombre_foto = arg('--foto')

    xd_patches.apply()
    agc = glob.glob(f'{XDDIR}/artwork/artboard-{prefijo}*/graphics/graphicContent.agc')[0]
    raiz = json.load(open(agc))['children'][0]['artboard']['children']
    bb = (x - DX, y - DY, x - DX + w, y - DY + h)

    # 1. las capas de adorno, a la escala pedida
    cap_detras = capa(raiz, detras, bb, w, h, escala)
    cap_delante = capa(raiz, delante, bb, w, h, escala)

    # 2. el raster CRUDO de la foto (con su alfa: es un recorte sin fondo)
    hit = buscar(raiz, {nombre_foto})
    if not hit:
        raise SystemExit(f'no encontré {nombre_foto!r}')
    pats = []

    def patterns(n, m):
        mm = X.mat_mul(m, X.node_transform(n))
        f = (n.get('style') or {}).get('fill') or {}
        if f.get('type') == 'pattern':
            pats.append(((f.get('pattern') or {}).get('meta', {}).get('ux') or {}))
        for c in (n.get('group') or {}).get('children', []):
            patterns(c, mm)
    patterns(hit[0][0], hit[0][1])
    if not pats:
        raise SystemExit('el grupo de la foto no tiene ningún relleno pattern')
    ux = pats[0]
    cruda = Image.open(f'{RES}/{ux["uid"]}').convert('RGBA')
    if ux.get('flipX'):
        cruda = cruda.transpose(Image.FLIP_LEFT_RIGHT)
    if ux.get('flipY'):
        cruda = cruda.transpose(Image.FLIP_TOP_BOTTOM)

    # 3. el trozo del PDF con el que hay que casar
    pdf = Image.open(f'{CACHE}/p{pagina}.png').convert('RGB')
    obj = pdf.crop((round(x * 2), round(y * 2), round((x + w) * 2), round((y + h) * 2)))
    ow, oh = 80, round(80 * h / w)
    o = np.asarray(obj.convert('L').resize((ow, oh), Image.LANCZOS)).astype(float)
    o = (o - o.mean()) / (o.std() + 1e-6)

    W, H = round(w * escala), round(h * escala)

    def componer(s, dx, dy):
        base = Image.new('RGBA', (W, H), (255, 255, 255, 255))
        base.alpha_composite(cap_detras)
        fw, fh = max(1, round(cruda.width * s)), max(1, round(cruda.height * s))
        base.alpha_composite(cruda.resize((fw, fh), Image.LANCZOS), (round(dx), round(dy)))
        base.alpha_composite(cap_delante)
        return base.convert('RGB')

    def corr(s, dx, dy):
        a = np.asarray(componer(s, dx, dy).convert('L').resize((ow, oh), Image.LANCZOS)).astype(float)
        a = (a - a.mean()) / (a.std() + 1e-6)
        return float((a * o).mean())

    # 4. búsqueda: rejilla gruesa (la escala de referencia es la del nodo) y refinamiento
    s0 = (w * escala) / cruda.width
    mejor = (-1, s0, 0, 0)
    for k in np.arange(0.55, 1.45, 0.05):
        s = s0 * k
        for fx in np.arange(-0.35, 0.36, 0.07):
            for fy in np.arange(-0.35, 0.36, 0.07):
                c = corr(s, fx * W, fy * H)
                if c > mejor[0]:
                    mejor = (c, s, fx * W, fy * H)
    c0, s, dx, dy = mejor
    ps, pp = 0.04 * s0, 0.05 * W
    for _ in range(6):
        for ds in (-ps, 0, ps):
            for ddx in (-pp, 0, pp):
                for ddy in (-pp, 0, pp):
                    c = corr(s + ds, dx + ddx, dy + ddy)
                    if c > c0:
                        c0, s, dx, dy = c, s + ds, dx + ddx, dy + ddy
        ps /= 2
        pp /= 2

    print(f'foto {cruda.size} escala={s:.4f} ({s / s0:.3f}x del nodo) '
          f'offset=({dx:.0f},{dy:.0f}) corr={c0:.4f}')
    componer(s, dx, dy).save(salida)
    print(f'{(W, H)} -> {salida}')


main()
