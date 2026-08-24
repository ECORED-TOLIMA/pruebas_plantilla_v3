#!/usr/bin/env python3
"""Convierte un .md a PDF con Chrome (`--print-to-pdf`), sin pandoc ni wkhtmltopdf.

Se usa para entregar `REVISION-PENDIENTES.md` también en PDF, que es como lo pide el equipo.
Se le pone una hoja de estilo mínima con la tipografía y los colores del curso para que no
parezca un volcado de texto.

Uso: md_a_pdf.py <archivo.md> [salida.pdf]
"""
import os
import subprocess
import sys
import tempfile

import markdown

CSS = """
@page { size: Letter; margin: 20mm 18mm; }
body { font-family: Roboto, Arial, sans-serif; color: #12263F; font-size: 10.5pt;
       line-height: 1.5; max-width: 100%; }
h1 { color: #12263F; font-size: 20pt; border-bottom: 4px solid #FE9841;
     padding-bottom: 6px; margin: 0 0 4px; }
h2 { color: #12263F; font-size: 13pt; background: #FFF9E2; border-left: 5px solid #FFDE74;
     padding: 6px 10px; margin: 22px 0 10px; page-break-after: avoid; }
h3 { font-size: 11pt; margin: 14px 0 4px; }
p, li { margin: 4px 0; }
strong { color: #7C3F10; }
code { background: #F6F9F4; padding: 1px 4px; border-radius: 3px; font-size: 9.5pt; }
pre { background: #F6F9F4; border-left: 3px solid #C0FEA6; padding: 8px 10px;
      overflow-x: auto; font-size: 9pt; }
pre code { background: none; padding: 0; }
em { color: #555; }
hr { border: none; border-top: 1px solid #DBDADA; margin: 18px 0; }
blockquote { border-left: 3px solid #87FCE8; margin: 8px 0; padding-left: 10px; color: #444; }
"""


def main():
    entrada = os.path.abspath(sys.argv[1])
    salida = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else entrada[:-3] + '.pdf'
    cuerpo = markdown.markdown(open(entrada, encoding='utf-8').read(),
                               extensions=['tables', 'fenced_code'])
    tmp = tempfile.mkdtemp()
    html = f'<!doctype html><meta charset="utf-8"><style>{CSS}</style>{cuerpo}'
    open(f'{tmp}/a.html', 'w', encoding='utf-8').write(html)
    subprocess.run(['google-chrome', '--headless=new', '--disable-gpu', '--no-sandbox',
                    '--no-pdf-header-footer', f'--print-to-pdf={salida}', f'{tmp}/a.html'],
                   check=True, capture_output=True)
    print(f'{salida}  ({os.path.getsize(salida) / 1024:.0f} KB)')


main()
