#!/usr/bin/env python3
"""Compara el entregable ANTES y DESPUÉS de las correcciones manuales de otra persona, y prepara el
material para deducir POR QUÉ cambió cada cosa.

Existe porque el acuerdo con Luis (2026-07-30) es: alguien del equipo corrige a mano, yo comparo y
**de cada cambio saco una regla** para `errores_recurrentes.json`. Un cambio del que no salga una
regla se volverá a repetir.

Antes de las correcciones ya quedó guardado:
  · tag `antes-correcciones-manuales`
  · `sena/snapshots/CF1_63720048-antes-manual.bundle` (historia completa, sobrevive a un force-push)
  · `sena/snapshots/CF1_63720048-antes-manual/` (copia plana + MD5-antes.txt)

Uso:  comparar_correcciones.py [--tag antes-correcciones-manuales] [--sin-pull]
"""
import json
import os
import re
import subprocess
import sys

TAG = sys.argv[sys.argv.index('--tag') + 1] if '--tag' in sys.argv else 'antes-correcciones-manuales'
SNAP = '/home/betterway/Proyectos/Flaco/sena/snapshots/CF1_63720048-antes-manual'


def sh(*c):
    return subprocess.run(c, capture_output=True, text=True).stdout.strip()


def paso(t):
    print(f'\n{"="*78}\n{t}\n{"="*78}')


paso('0. comprobaciones previas')
if not sh('git', 'tag', '-l', TAG):
    sys.exit(f'✘ no existe el tag {TAG}: no hay punto de partida con el que comparar')
print(f'  tag {TAG} -> {sh("git","rev-parse","--short",TAG)}')
print(f'  bundle: {"sí" if os.path.exists(SNAP + ".bundle") else "NO"} | copia plana: '
      f'{"sí" if os.path.isdir(SNAP) else "NO"}')

if '--sin-pull' not in sys.argv:
    paso('1. pull')
    print(sh('git', 'pull') or '  (sin cambios)')

paso('2. qué cambió respecto al ANTES')
stat = sh('git', 'diff', '--stat', f'{TAG}..HEAD', '--', 'src', 'BITACORA.md', 'REVISION-PENDIENTES.md')
print(stat or '  nada')
autores = sh('git', 'log', '--format=  %h %an: %s', f'{TAG}..HEAD')
print('\n  commits nuevos:\n' + (autores or '  ninguno'))

paso('3. cambios línea a línea en las vistas y los estilos')
diff = sh('git', 'diff', '-U1', f'{TAG}..HEAD', '--', 'src/views', 'src/styles', 'src/config')
print(diff[:14000] or '  nada')

paso('4. pistas del XD para explicar cada cambio')
print("""  Por cada línea que cambió, buscar el POR QUÉ (no quedarse en el qué):
   · cambió un `col-lg-N`  -> medir el ancho del rect en el inventario (§1) y deducir la regla
   · cambió un `.bg-N`     -> comparar con el `(fill, r)` del inventario (§1)
   · cambió un radio       -> `r=[...]` del rect, o el de la máscara si es una foto (§2)
   · cambió un padding/alto-> posición del primer texto menos la del rect; alto del rect
   · quitó una negrilla    -> el run del DOCX (`<w:b/>` en word/document.xml)
   · cambió un componente  -> buscar el rótulo en el pasteboard (§4b) y el catálogo
   · añadió un `br`        -> el `rawText` del XD lleva `\\n`
  Los inventarios están en `docs/inventario-<tema>.txt` (los regenera preparar_curso.py).""")
ficheros = re.findall(r'^\+\+\+ b/(\S+)', diff, re.M)
temas = sorted({m.group(1) for f in ficheros if (m := re.search(r'Tema(\d)', f))})
if temas:
    print('\n  temas tocados:', ', '.join(temas))
    for t in temas:
        inv = [f for f in os.listdir('docs') if f.startswith(f'inventario-Tema-{t}')] if os.path.isdir('docs') else []
        print(f'   Tema {t} -> docs/{inv[0] if inv else "(falta: correr preparar_curso.py)"}')

paso('5. QUÉ HACER CON ESTO')
print("""  1. Por cada cambio, escribir el por qué en `BITACORA.md`.
  2. Cada por qué que sea generalizable -> entrada nueva en
     `scripts/errores_recurrentes.json` (id, sintoma, causa, regla, detecta) y, si se puede
     automatizar, su `check` en `verificar_maqueta.py`.
  3. `cp scripts/*.py scripts/*.json ../../herramientas-xd/` y push al repo PADRE.
  4. `verificar_maqueta.py` y push del entregable.""")
