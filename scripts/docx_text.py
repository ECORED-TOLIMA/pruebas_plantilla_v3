#!/usr/bin/env python3
"""Vuelca el texto de un .docx párrafo por párrafo (y las tablas celda por celda).

El DI.docx es la FUENTE PRIMARIA DEL TEXTO del curso: trae también los estados COLAPSADOS
que el XD no dibuja (descripciones de acordeones/tabs/timeline, viñetas, código), más el
glosario, las referencias y el control del documento (créditos).

Detalles que hay que respetar:
- Un párrafo son todos los `<w:t>` hasta `</w:p>`; unirlos SIN separador (los runs cortan
  palabras por la mitad: `pyth` + `o` + `n` → hay que limpiar `pyth o n` → `python`).
- `<w:tab/>` y `<w:br/>` cuentan como espacio / salto de línea.
- Las tablas se emiten como `| celda | celda |` para poder leer los cuestionarios del AD.docx.
- Con `--negritas` marca los segmentos en negrita con **…** (sirve para los "Término: desc").

Uso: docx_text.py <archivo.docx> [--negritas] [--tablas-solo]
"""
import sys
import zipfile
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def texto_de_run(r, negritas):
    rpr = r.find(f'{W}rPr')
    bold = rpr is not None and rpr.find(f'{W}b') is not None
    ital = rpr is not None and rpr.find(f'{W}i') is not None
    out = []
    for hijo in r:
        if hijo.tag == f'{W}t':
            out.append(hijo.text or '')
        elif hijo.tag == f'{W}tab':
            out.append(' ')
        elif hijo.tag == f'{W}br':
            out.append('\n')
    s = ''.join(out)
    if negritas and s.strip():
        if bold:
            s = f'**{s}**'
        elif ital:
            s = f'_{s}_'
    return s


def texto_de_parrafo(p, negritas):
    return ''.join(texto_de_run(r, negritas) for r in p.iter(f'{W}r'))


def main():
    ruta = sys.argv[1]
    negritas = '--negritas' in sys.argv
    tablas_solo = '--tablas-solo' in sys.argv
    with zipfile.ZipFile(ruta) as z:
        xml = z.read('word/document.xml')
    body = ET.fromstring(xml).find(f'{W}body')
    if body is None:
        raise SystemExit('el docx no tiene <w:body>')

    for el in body:
        if el.tag == f'{W}p' and not tablas_solo:
            t = texto_de_parrafo(el, negritas).strip()
            if t:
                print(t)
        elif el.tag == f'{W}tbl':
            print('=== TABLA ===')
            for fila in el.findall(f'{W}tr'):
                celdas = []
                for c in fila.findall(f'{W}tc'):
                    ps = [texto_de_parrafo(p, negritas).strip() for p in c.findall(f'{W}p')]
                    celdas.append(' ¶ '.join(x for x in ps if x))
                print('| ' + ' | '.join(celdas) + ' |')
            print('=== /TABLA ===')


main()
