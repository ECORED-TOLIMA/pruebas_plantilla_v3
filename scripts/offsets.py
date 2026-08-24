#!/usr/bin/env python3
"""Calcula el offset (dx, dy) que lleva las coordenadas del XD a las de la PÁGINA del PDF.

Las coordenadas del XD son negativas y distintas en cada artboard, así que para comparar un
render contra el PDF hace falta un desplazamiento. **El ancla es la TARJETA BLANCA**: en todos
los artboards hay un `rect` de **1328** de ancho, relleno `#FFFFFF` y `r=20`, que es la tarjeta
de contenido. En la página siempre arranca en **x=136** (1600 de ancho de página − 1328, /2).

  dx = 136 − x_tarjeta
  dy = y_tarjeta_en_el_PDF − y_tarjeta_en_el_XD   (la y se MIDE en el PNG del PDF)

La `y` hay que medirla porque la franja que va encima de la tarjeta no mide lo mismo en cada
tipo de pantalla: en los temas la tarjeta empieza en ~160 y en la hoja de la síntesis en 96.
Se localiza barriendo una columna del PNG hasta el primer blanco puro que dura >200px.

Es más fiable que anclar en el banner de encabezado o en el `h1`: la tarjeta está en TODAS las
pantallas, mide siempre lo mismo y no la desplaza el badge del número del tema.

Uso: offsets.py <prefijo_artboard> <pagina_pdf>
"""
import glob
import json
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image
import config as C

XDDIR = C.XDDIR
PDF = C.PDF
DPI = 144           # los pt del PDF son 1:1 con los px del XD -> 144 dpi = factor 2 exacto
Image.MAX_IMAGE_PIXELS = None


def tarjeta_en_xd(prefijo):
    """El rect blanco de 1328 de ancho con r=20: devuelve (x, y, alto)."""
    agc = glob.glob(f'{XDDIR}/artwork/artboard-{prefijo}*/graphics/graphicContent.agc')[0]
    hits = []

    def walk(n, ox, oy):
        t = n.get('transform') or {}
        x, y = ox + t.get('tx', 0), oy + t.get('ty', 0)
        if 'group' in n:
            for c in n['group'].get('children', []):
                walk(c, x, y)
            return
        shp = n.get('shape') or {}
        fill = (n.get('style') or {}).get('fill') or {}
        col = (fill.get('color') or {}).get('value')
        blanco = isinstance(col, dict) and col.get('r') == 255 and col.get('g') == 255 and col.get('b') == 255
        if shp.get('type') == 'rect' and blanco and (shp.get('width') or 0) >= 1200:
            hits.append((x + (shp.get('x') or 0), y + (shp.get('y') or 0),
                         shp.get('height'), shp.get('width')))

    for c in json.load(open(agc))['children'][0]['artboard'].get('children', []):
        walk(c, 0, 0)
    if not hits:
        raise SystemExit('no encontré la tarjeta blanca (rect blanco >=1200) en ' + prefijo)
    # OJO: la barra de navegación superior también es un rect BLANCO y es MÁS ANCHA que la
    # tarjeta (1600x70, `Rectángulo 451`). Por eso no vale "la más ancha": se elige la más
    # ALTA (la tarjeta de contenido mide miles de px de alto; la barra, 70).
    return sorted(hits, key=lambda h: -h[2])[0]


def render_pagina(pagina):
    tmp = tempfile.mkdtemp()
    subprocess.run(['pdftoppm', '-png', '-r', str(DPI), '-f', str(pagina), '-l', str(pagina),
                    PDF, f'{tmp}/p'], check=True)
    return Image.open(glob.glob(f'{tmp}/p*.png')[0]).convert('RGB')


def tarjeta_en_pdf(im, xcard):
    """y del borde superior de la tarjeta.

    Se barre una columna en el MARGEN IZQUIERDO de la tarjeta (unos 10pt dentro de su borde,
    o sea a la izquierda del contenido, que arranca 48pt más adentro). Ahí la tarjeta es blanca
    de arriba abajo, así que el primer tramo largo de blanco puro ES su borde superior.
    Barrer por el centro de la página NO sirve: se engancha con cualquier bloque blanco del
    contenido y da un dy corrido cientos de px (fallaba en los temas 1, 3 y 6).

    OJO CON EL RADIO: la tarjeta tiene `r=20`, así que a 10pt del borde la esquina redondeada
    baja el borde detectado ~8pt (dio 170 en vez de 162 en el Tema 1). Se barren varias
    columnas ENTRE el radio y el contenido (xcard+25 … xcard+45) y se toma el mínimo, que es
    el borde recto de verdad."""
    a = np.asarray(im).astype(int)
    esc = DPI / 72                      # px por pt
    tops = []
    for off in (25, 30, 35, 40, 45):
        x = int((xcard + off) * esc)
        col = a[:, x, :]
        blanco = (col == 255).all(axis=1)
        i = 0
        while i < len(blanco):
            if blanco[i]:
                j = i
                while j < len(blanco) and blanco[j]:
                    j += 1
                if j - i > 300 * esc:
                    tops.append(i / esc)
                    break
                i = j
            else:
                i += 1
    if not tops:
        raise SystemExit('no encontré el borde superior de la tarjeta en el PDF')
    return min(tops)


def main():
    prefijo, pagina = sys.argv[1], int(sys.argv[2])
    xt = tarjeta_en_xd(prefijo)
    xcard = (1600 - xt[3]) / 2      # la tarjeta va centrada en la página de 1600pt
    im = render_pagina(pagina)
    ypdf = tarjeta_en_pdf(im, xcard)
    dx = xcard - xt[0]
    dy = ypdf - xt[1]
    print(f'artboard {prefijo}  pag {pagina}  pagina={im.width/(DPI/72):.0f}x{im.height/(DPI/72):.0f} pt')
    print(f'  tarjeta XD : x={xt[0]:.0f} y={xt[1]:.0f} {xt[3]:.0f}x{xt[2]:.0f}  -> pagina x={xcard:.0f}')
    print(f'  tarjeta PDF: y={ypdf:.0f}')
    print(f'  XD_DX={dx:.0f} XD_DY={dy:.0f}')


main()
