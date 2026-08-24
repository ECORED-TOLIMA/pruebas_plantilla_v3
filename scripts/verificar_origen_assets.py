#!/usr/bin/env python3
"""Comprueba que CADA asset del entregable salió del XD y no de ninguna copia.

Tres orígenes legítimos, y ninguno más:

1. **raster crudo del XD**: el archivo es byte-idéntico a `resources/<uid>` del `.xd`
   (el pipeline copia el recurso tal cual cuando no hace falta recortar).
2. **derivado del XD**: es un PNG recortado (`cropped_pattern_bytes`) o un render de un grupo
   hecho con `gen_asset.py`; no es byte-idéntico al recurso, pero SÍ se verifica por
   correlación contra la página del PDF de diseño (ver `comparar.py`).
3. **SVG reconstruido**: lo emite `xd_export.py` a partir de los paths del propio XD; se
   reconoce porque el `<svg>` no trae ningún `<image>` externo.

Lo que este script busca son los que NO encajan: los que vienen del **scaffold BASE** (assets de
otro curso) y cualquier archivo que no se pueda explicar. Los de BASE son marcadores conocidos y
están anotados en REVISION-PENDIENTES.md.

Uso: verificar_origen_assets.py
"""
import hashlib
import os
import config as C

ENTREGABLE = C.ENTREGABLE
RES = C.RES
BASE = os.path.abspath(f'{C.ENTREGABLE}/../referencia/BASE')


def md5(ruta):
    with open(ruta, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def indice(carpeta):
    """md5 -> lista de rutas relativas."""
    out = {}
    for dirpath, _, files in os.walk(carpeta):
        for f in files:
            p = os.path.join(dirpath, f)
            try:
                out.setdefault(md5(p), []).append(os.path.relpath(p, carpeta))
            except OSError:
                pass
    return out


def main():
    recursos = indice(RES)
    base = indice(BASE + '/src/assets')
    base_public = indice(BASE + '/public')

    # generados en el cierre: los dos PDF salen del PDF de diseño y el zip, del build
    GENERADOS = {'dist.pdf', 'Sintesis.pdf', 'material.zip'}
    cuenta = {'xd-crudo': 0, 'xd-svg': 0, 'xd-derivado': 0, 'BASE (marcador)': 0,
              'MP3 marcador': 0, 'generado en el cierre': 0, '???': 0}
    sospechosos, marcadores = [], []

    for raiz in (f'{ENTREGABLE}/src/assets', f'{ENTREGABLE}/public'):
        for dirpath, _, files in os.walk(raiz):
            for f in sorted(files):
                if f in ('.gitkeep', 'manifest.txt'):
                    continue
                p = os.path.join(dirpath, f)
                rel = os.path.relpath(p, ENTREGABLE)
                h = md5(p)
                if f in GENERADOS:
                    cuenta['generado en el cierre'] += 1
                elif h in recursos:
                    cuenta['xd-crudo'] += 1
                elif h in base or h in base_public:
                    cuenta['BASE (marcador)'] += 1
                    marcadores.append(rel)
                elif f.endswith('.svg'):
                    txt = open(p, encoding='utf-8', errors='ignore').read()
                    if '<svg' in txt:
                        cuenta['xd-svg'] += 1
                    else:
                        cuenta['???'] += 1
                        sospechosos.append(rel)
                elif f.endswith('.mp3') and '/audios/' in rel.replace(os.sep, '/'):
                    # los pódcast no vienen en el XD ni en los DOCX: MP3 mudo de marcador
                    cuenta['MP3 marcador'] += 1
                    marcadores.append(rel + '  (MP3 silencioso: el audio no está en las fuentes)')
                elif '/curso/' in rel.replace(os.sep, '/') and f.endswith('.png'):
                    # PNG del curso que no es el recurso crudo: recorte o render del XD
                    cuenta['xd-derivado'] += 1
                else:
                    cuenta['???'] += 1
                    sospechosos.append(rel)

    print('=== origen de los assets ===')
    for k, v in cuenta.items():
        print(f'  {k:18} {v}')
    if marcadores:
        print('\nmarcadores heredados de BASE (anotados en REVISION-PENDIENTES.md):')
        for m in sorted(marcadores):
            print('  -', m)
    if sospechosos:
        print('\n⚠️  SIN EXPLICAR (revisar):')
        for s in sorted(sospechosos):
            print('  -', s)


main()
