#!/usr/bin/env python3
"""Compara un PNG contra el mismo rectángulo de la página del PDF de diseño.

Es la verificación del método por elemento: **nunca "a ojo" y nunca la página completa**, sino
el bloque, a la misma escala y en la misma posición.

  comparar.py <pagina> <x> <y> <w> <h> <imagen.png> [salida.png]

Imprime la correlación normalizada en grises (>0.95 = el encuadre es el bueno; 0.4-0.9 suele
querer decir que el dx/dy está mal, no que la imagen esté mal) y escribe un PNG con el PDF
arriba y la imagen abajo.

Sin `<imagen.png>` recorta sólo el trozo del PDF (útil para mirar un bloque de cerca):

  comparar.py <pagina> <x> <y> <w> <h> --solo-pdf salida.png
"""
import glob
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image
import config as C

PDF = C.PDF
DPI = 144                      # 2 px por pt: los pt del PDF son 1:1 con los px del XD
Image.MAX_IMAGE_PIXELS = None
_cache = {}


CACHE = C.CACHE_PDF


def pagina_pdf(n):
    """Render de la página a 144 dpi, con CACHÉ EN DISCO.

    Sin la caché esto es el cuello de botella de todo: las páginas de los temas miden hasta
    1600x23000 pt y `pdftoppm` tarda ~25 s en cada una. `regen_fotos.py` la llama una vez por
    foto (20-30 veces por tema) en procesos distintos, así que la caché tiene que ser en disco,
    no en memoria.
    """
    if n in _cache:
        return _cache[n]
    os.makedirs(CACHE, exist_ok=True)
    destino = f'{CACHE}/p{n}.png'
    if not os.path.exists(destino):
        tmp = tempfile.mkdtemp()
        subprocess.run(['pdftoppm', '-png', '-r', str(DPI), '-f', str(n), '-l', str(n),
                        PDF, f'{tmp}/p'], check=True)
        os.replace(glob.glob(f'{tmp}/p*.png')[0], destino)
    _cache[n] = Image.open(destino).convert('RGB')
    return _cache[n]


def recorte(n, x, y, w, h):
    e = DPI / 72
    return pagina_pdf(n).crop((round(x * e), round(y * e), round((x + w) * e), round((y + h) * e)))


def main():
    n, x, y, w, h = int(sys.argv[1]), *(float(v) for v in sys.argv[2:6])
    pdf = recorte(n, x, y, w, h)
    if '--solo-pdf' in sys.argv:
        pdf.save(sys.argv[-1])
        print(f'{pdf.size} -> {sys.argv[-1]}')
        return

    img = Image.open(sys.argv[6]).convert('RGBA')
    # El PDF no tiene transparencia, así que hay que aplanar. **Si el asset va encima de un
    # panel de color, hay que pasar ese color con `--fondo`**: comparar un PNG transparente
    # sobre blanco contra un bloque que en el PDF tiene fondo oscuro baja la correlación a
    # 0.6 aunque el dibujo sea idéntico (pasó con la ilustración del pódcast).
    col = (255, 255, 255)
    if '--fondo' in sys.argv:
        h = sys.argv[sys.argv.index('--fondo') + 1].lstrip('#')
        col = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    fondo = Image.new('RGBA', img.size, col + (255,))
    fondo.alpha_composite(img)
    img = fondo.convert('RGB').resize(pdf.size, Image.LANCZOS)

    a = np.asarray(pdf.convert('L')).astype(float)
    b = np.asarray(img.convert('L')).astype(float)
    corr = np.corrcoef(a.ravel(), b.ravel())[0, 1]
    print(f'correlacion {corr:.4f}   (pdf {pdf.size})')

    if len(sys.argv) > 7 and not sys.argv[7].startswith('-'):
        comb = Image.new('RGB', (pdf.width, pdf.height * 2 + 8), 'white')
        comb.paste(pdf, (0, 0))
        comb.paste(img, (0, pdf.height + 8))
        ancho = min(1300, comb.width)
        comb = comb.resize((ancho, round(comb.height * ancho / comb.width)), Image.LANCZOS)
        comb.save(sys.argv[7])
        print('->', sys.argv[7])


main()
