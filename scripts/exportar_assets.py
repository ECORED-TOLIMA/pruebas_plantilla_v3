#!/usr/bin/env python3
"""Corre el pipeline compartido (`../../scripts/export_screens.py`) sobre todos los artboards.

Aquí los nombres de capa SÍ son fiables (`Tema-1`…`Tema-6`, `Introduccion`), pero el CLI ignora
`Portada` y `Sintesis – PDF` si no se mapean, así que se llama a `export_one` directo con el mapa
verificado leyendo el `h1` de cada artboard.

Salida: `fuentes/<carpeta>/` con los assets numerados en orden visual + `manifest.txt`.

Uso: exportar_assets.py [carpeta1 carpeta2 …]   (sin argumentos: todas)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C  # noqa: E402

sys.path.insert(0, C.PIPELINE)
import export_screens as ES  # noqa: E402

SALIDA = C.FUENTES

# nombre exacto del artboard en el manifest -> carpeta de salida
MAPA = {
    'Portada': 'portada',
    'Introduccion': 'introduccion',
    'Tema-1 ': 'tema1',   # ojo: con espacio final (el CLI no puede apuntarlo: hace .strip())
    'Tema-2': 'tema2',
    'Tema-3': 'tema3',
    'Tema-4': 'tema4',
    'Tema-5': 'tema5',
    'Tema-6': 'tema6',
    'Sintesis – PDF': 'sintesis',
}


def main():
    pedidas = set(sys.argv[1:])
    extract_dir = C.descomprimir()
    boards = ES.list_artboards(ES.load_manifest(extract_dir))
    overrides = json.load(open(ES.OVERRIDES_PATH)) if os.path.exists(ES.OVERRIDES_PATH) else {}
    exclude_ids = set(overrides.get(os.path.basename(C.XD), {}).keys())

    faltan = [n for n in MAPA if n not in boards]
    if faltan:
        raise SystemExit(f'estos artboards no están en el manifest: {faltan}\n'
                         f'hay: {sorted(boards)}')

    for nombre, carpeta in MAPA.items():
        if pedidas and carpeta not in pedidas:
            continue
        subpath, bbox = boards[nombre]
        outdir = os.path.join(SALIDA, carpeta)
        ES.export_one(extract_dir, subpath, bbox, outdir, exclude_ids)
        n = len([f for f in os.listdir(outdir) if f[0].isdigit()])
        print(f'{carpeta:12} <- {nombre!r:20} {n} assets')


main()
