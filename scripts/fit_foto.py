#!/usr/bin/env python3
"""Ajusta el ENCUADRE de una foto por correlación contra el PDF, en vez de seguir adivinando.

Cuándo se usa: cuando `regen_fotos.py` deja una foto por debajo de ~0.88. La causa siempre es la
misma familia de problemas (el `meta.ux.scale`, el signo del `offset`, el `cover` calculado sobre
el rect del nodo en vez del de la máscara), y en vez de pelear con la semántica del XD se
resuelve numéricamente: se parte del RASTER CRUDO del recurso y se busca la combinación
(escala, x, y) que maximiza la correlación con el mismo rectángulo del PDF.

Con un error < 0.01 el encuadre es exacto. Es la herramienta de último recurso para cualquier
`pattern` con offsets raros, y también sirve para comprobar que una foto ya buena lo está.

  fit_foto.py <artboard> <pagina> <x> <y> <w> <h> <salida.png> [--grupo NOMBRE] [--espejo]

Sin `--grupo` busca el ÚNICO nodo con relleno `pattern` cuyo bbox de máscara caiga en ese rect.
"""
import glob
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402
C.pipeline()
import xd_export as X  # noqa: E402

XDDIR = C.XDDIR
RES = C.RES
CACHE = C.CACHE_PDF
Image.MAX_IMAGE_PIXELS = None
DX = float(os.environ.get('XD_DX', 0))
DY = float(os.environ.get('XD_DY', 0))


def bbox_mascara(nodo, m):
    cp = ((nodo.get('meta') or {}).get('ux') or {}).get('clipPathResources')
    if not (cp and cp.get('children')):
        return None
    forma = cp['children'][0]
    lb = X.shape_local_bbox(forma.get('shape') or {})
    if not lb:
        return None
    mm = X.mat_mul(X.mat_mul(m, X.node_transform(nodo)), X.node_transform(forma))
    return X.transform_bbox(mm, lb)


def patterns_de(nodo, m, out):
    mm = X.mat_mul(m, X.node_transform(nodo))
    fill = (nodo.get('style') or {}).get('fill') or {}
    if fill.get('type') == 'pattern':
        ux = ((fill.get('pattern') or {}).get('meta') or {}).get('ux') or {}
        out.append((nodo, mm, ux))
    for c in (nodo.get('group') or {}).get('children', []):
        patterns_de(c, mm, out)


def main():
    prefijo, pagina = sys.argv[1], int(sys.argv[2])
    x, y, w, h = (float(v) for v in sys.argv[3:7])
    salida = sys.argv[7]
    nombre = sys.argv[sys.argv.index('--grupo') + 1] if '--grupo' in sys.argv else None

    agc = glob.glob(f'{XDDIR}/artwork/artboard-{prefijo}*/graphics/graphicContent.agc')[0]
    raiz = json.load(open(agc))['children'][0]['artboard']['children']

    # 1. localizar el nodo con el pattern dentro del rect pedido
    candidatos = []

    def walk(ns, m):
        for n in ns:
            mm = X.mat_mul(m, X.node_transform(n))
            bb = bbox_mascara(n, m)
            if bb:
                px, py = bb[0] + DX, bb[1] + DY
                if abs(px - x) < 30 and abs(py - y) < 30 and (nombre is None or n.get('name') == nombre):
                    pats = []
                    patterns_de(n, m, pats)
                    if pats:
                        candidatos.append(pats[0])
                    continue
            if n.get('type') == 'group':
                walk((n.get('group') or {}).get('children', []), mm)

    walk(raiz, X.IDENTITY)
    if not candidatos:
        # Segunda pasada: patterns SIN máscara (una foto puede ser un `shape` suelto con
        # relleno de patrón, como la de la Introducción de CF1_63720048). Se busca el que
        # tenga el bbox del propio nodo en ese sitio.
        sueltos = []

        def walk2(ns, m):
            for n in ns:
                mm = X.mat_mul(m, X.node_transform(n))
                fill = (n.get('style') or {}).get('fill') or {}
                if fill.get('type') == 'pattern':
                    lb = X.shape_local_bbox(n.get('shape') or {})
                    if lb:
                        bb = X.transform_bbox(mm, lb)
                        if abs(bb[0] + DX - x) < 30 and abs(bb[1] + DY - y) < 30:
                            ux = ((fill.get('pattern') or {}).get('meta') or {}).get('ux') or {}
                            sueltos.append((n, mm, ux))
                if n.get('type') == 'group':
                    walk2((n.get('group') or {}).get('children', []), mm)

        walk2(raiz, X.IDENTITY)
        candidatos = sueltos
    if not candidatos:
        raise SystemExit(f'no encontré ningún pattern en ({x:.0f},{y:.0f})')
    nodo, _, ux = candidatos[0]
    uid = ux.get('uid')
    cruda = Image.open(f'{RES}/{uid}').convert('RGB')
    if ux.get('flipX') or '--espejo' in sys.argv:
        cruda = cruda.transpose(Image.FLIP_LEFT_RIGHT)
    if ux.get('flipY'):
        cruda = cruda.transpose(Image.FLIP_TOP_BOTTOM)

    # 2. el trozo del PDF con el que hay que casar
    pdf = Image.open(f'{CACHE}/p{pagina}.png').convert('L')
    e = 2.0                                     # 144 dpi = 2 px por pt
    objetivo = pdf.crop((round(x * e), round(y * e), round((x + w) * e), round((y + h) * e)))
    ow, oh = 66, 73                             # downsample: basta para la correlación y es rápido
    obj = np.asarray(objetivo.resize((ow, oh), Image.LANCZOS)).astype(float)
    obj = (obj - obj.mean()) / (obj.std() + 1e-6)

    gris = cruda.convert('L')

    def corr(escala, ox, oy):
        sw, sh = max(1, round(cruda.width * escala)), max(1, round(cruda.height * escala))
        if sw < w or sh < h:
            return -1
        red = gris.resize((sw, sh), Image.BILINEAR)
        cx, cy = round(ox), round(oy)
        if cx < 0 or cy < 0 or cx + w > sw or cy + h > sh:
            return -1
        rec = red.crop((cx, cy, cx + round(w), cy + round(h))).resize((ow, oh), Image.LANCZOS)
        a = np.asarray(rec).astype(float)
        a = (a - a.mean()) / (a.std() + 1e-6)
        return float((a * obj).mean())

    # 3. búsqueda: primero rejilla gruesa sobre la escala de `cover`, luego refinamiento
    base = max(w / cruda.width, h / cruda.height)
    mejor = (-1, base, 0, 0)
    for k in np.arange(0.90, 1.60, 0.05):
        esc = base * k
        sw, sh = cruda.width * esc, cruda.height * esc
        for fx in np.arange(0, 1.01, 0.1):
            for fy in np.arange(0, 1.01, 0.1):
                c = corr(esc, (sw - w) * fx, (sh - h) * fy)
                if c > mejor[0]:
                    mejor = (c, esc, (sw - w) * fx, (sh - h) * fy)
    c0, esc, ox, oy = mejor
    paso_e, paso_p = 0.02 * base, 12
    for _ in range(5):
        for de in (-paso_e, 0, paso_e):
            for dox in (-paso_p, 0, paso_p):
                for doy in (-paso_p, 0, paso_p):
                    c = corr(esc + de, ox + dox, oy + doy)
                    if c > c0:
                        c0, esc, ox, oy = c, esc + de, ox + dox, oy + doy
        paso_e /= 2
        paso_p /= 2

    print(f'uid={uid} cruda={cruda.size} cover={base:.4f} -> escala={esc:.4f} '
          f'({esc / base:.3f}x) offset=({ox:.0f},{oy:.0f}) corr={c0:.4f}')

    sw, sh = round(cruda.width * esc), round(cruda.height * esc)
    final = cruda.resize((sw, sh), Image.LANCZOS).crop(
        (round(ox), round(oy), round(ox) + round(w), round(oy) + round(h)))
    final.save(salida)
    print(f'{final.size} -> {salida}')


main()
