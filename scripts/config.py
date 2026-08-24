#!/usr/bin/env python3
"""Rutas del entregable, resueltas SOLAS. Lo importan todas las herramientas del XD.

Existe porque en CF01 las 12 herramientas tenían las rutas fijas (`/home/…/xds/1/CF01_…`) y al
pasar a un repo por entregable —con las fuentes en `fuentes/`— había que editarlas una por una.
Aquí se deducen del propio árbol:

  ENTREGABLE  la carpeta que contiene a `scripts/`
  FUENTES     `<ENTREGABLE>/fuentes`
  XD          el único `.xd` de `fuentes/`
  XDDIR       la carpeta con el `.xd` descomprimido (se descomprime la primera vez)
  PDF         el único `.pdf` de `fuentes/`
  RES         `<XDDIR>/resources`
  PIPELINE    el `scripts/` compartido del repo padre (`xd_export.py`, `export_screens.py`)

`XD_DX` / `XD_DY` siguen viniendo del entorno (los da `offsets.py`, y cambian por pantalla).
"""
import glob
import os
import shutil
import sys
import zipfile

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ENTREGABLE = os.path.dirname(SCRIPTS)
FUENTES = os.path.join(ENTREGABLE, 'fuentes')


def _uno(patron, que, hermano=None):
    """El archivo fuente del curso. Si hay varios, gana el que se llama como su hermano.

    ⚠️ `fuentes/` no contiene sólo las fuentes: ahí vive también el `REVISION-PENDIENTES.pdf` que se
    entrega con el curso. Con un glob a secas, `*.pdf` devolvía dos y **todas las herramientas
    morían de golpe** con un error que no dice de dónde viene. El `.xd` da el nombre bueno.
    """
    hits = sorted(glob.glob(os.path.join(FUENTES, patron)))
    if not hits:
        raise SystemExit(f'no encontré ningún {que} en {FUENTES}')
    if len(hits) > 1 and hermano:
        base = os.path.splitext(os.path.basename(hermano))[0]
        propios = [h for h in hits if os.path.splitext(os.path.basename(h))[0] == base]
        if len(propios) == 1:
            return propios[0]
    if len(hits) > 1:
        raise SystemExit(f'hay más de un {que} en {FUENTES}: {[os.path.basename(h) for h in hits]}')
    return hits[0]


XD = _uno('*.xd', '.xd')
PDF = _uno('*.pdf', '.pdf', hermano=XD)
XDDIR = XD[:-3]
RES = os.path.join(XDDIR, 'resources')

# El `scripts/` compartido del repo padre: `xd_export.py` es de la sesión del pipeline y NO se
# copia (hay que regresionar CF2 al tocarlo). Si el entregable se mueve a otra máquina sin ese
# repo, se puede apuntar con la variable XD_PIPELINE.
PIPELINE = os.environ.get(
    'XD_PIPELINE',
    os.path.abspath(os.path.join(ENTREGABLE, '..', '..', 'scripts')))

# Caché del render del PDF a 144 dpi (sin ella, cada comparación vuelve a rasterizar una página
# de hasta 1600x23000 pt: ~25 s).
# ⚠️ VA POR CURSO: con una caché común, `comparar.py` de un curso leería la `p3.png` del otro y
# daría correlaciones sin sentido sin avisar de nada.
CACHE_PDF = os.environ.get(
    'XD_CACHE', os.path.join('/tmp/xd-pdf-144dpi', os.path.basename(ENTREGABLE)))


def descomprimir():
    """Descomprime el `.xd` (es un zip) si hace falta.

    ⚠️ Antes la condición era sólo `if not os.path.isdir(XDDIR)`. Eso NO es idempotente cuando el
    `.xd` CAMBIA: si el diseñador manda una versión nueva, la carpeta ya existe y todas las
    herramientas siguen leyendo la vieja **sin avisar de nada**. Pasó de verdad — el `.xd` del
    2026-08-05 traía el artboard del Tema 2 y el pasteboard modificados (+448 KB) y se estuvo
    trabajando una mañana entera contra el descomprimido del día anterior.
    Ahora se compara la fecha del zip con la del descomprimido y se rehace si el zip es más nuevo.
    """
    marca = os.path.join(XDDIR, '.mtime-xd')
    actual = str(os.path.getmtime(XD))
    if os.path.isdir(XDDIR):
        anterior = open(marca).read() if os.path.exists(marca) else None
        if anterior == actual:
            return XDDIR
        shutil.rmtree(XDDIR)
        print(f'· el .xd cambió: se rehace {XDDIR}', file=sys.stderr)
    with zipfile.ZipFile(XD) as z:
        z.extractall(XDDIR)
    open(marca, 'w').write(actual)
    return XDDIR


def agc(prefijo):
    """El `graphicContent.agc` de un artboard por prefijo de id, o del pasteboard."""
    descomprimir()
    if prefijo == 'pasteboard':
        return f'{XDDIR}/artwork/pasteboard/graphics/graphicContent.agc'
    hits = glob.glob(f'{XDDIR}/artwork/artboard-{prefijo}*/graphics/graphicContent.agc')
    if not hits:
        hits = glob.glob(f'{XDDIR}/artwork/*{prefijo}*/graphics/graphicContent.agc')
    if not hits:
        raise SystemExit(f'no existe el artboard {prefijo!r} en {XDDIR}')
    return hits[0]


def pipeline():
    """Deja `xd_export.py` importable y lo devuelve."""
    if PIPELINE not in sys.path:
        sys.path.insert(0, PIPELINE)
    import xd_export
    return xd_export


def uno_docx(sufijo):
    """El único docx de `fuentes/` que acaba en ese sufijo (p. ej. `_AD.docx`)."""
    return _uno(f'*{sufijo}', f'docx {sufijo}')


DX = float(os.environ.get('XD_DX', 0))
DY = float(os.environ.get('XD_DY', 0))

if __name__ == '__main__':
    descomprimir()
    for k in ('ENTREGABLE', 'FUENTES', 'XD', 'XDDIR', 'PDF', 'PIPELINE', 'CACHE_PDF'):
        print(f'{k:11} {globals()[k]}')
