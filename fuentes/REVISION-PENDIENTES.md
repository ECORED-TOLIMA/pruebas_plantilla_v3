# Revisión pendiente — CF1_13340008

Todo lo que se **decidió** en vez de medirse, con su motivo, para que se pueda revertir.
Una entrada por hallazgo. Fecha y pantalla en cada una.

---

## Introducción (artboard `15bbf878`, página 2) — 2026-08-24

### 1. Falta el video de la introducción — MATERIAL QUE NO ESTÁ EN LAS FUENTES

El diseño dibuja el bloque de video como un **marcador**: un rect `#265D99` de 1228x580 r=10 con
la foto de una cámara, el botón de play y el rótulo «Espacio para video». No hay URL de video en
ninguna parte de `fuentes/`: lo único que hay es el **guion** (`CF1_13340008_GUION.docx`), es decir
el video todavía está por producir.

**Decidido:** se maqueta el marcador tal cual lo dibuja el diseño, exportado del XD
(`src/assets/curso/introduccion/video-placeholder.png`, correlación 0.9791 contra la pág. 2).

**Lo que hay que hacer cuando llegue la URL:** sustituir ese `figure > img` por el patrón de video
del proyecto — `figure > .video > iframe(...)`. La clase `.video` ya existe
(`src/styles/componentes/video.sass:1`, con el radio de 10px puesto en `_template.sass:65`), así
que no hay que escribir CSS nuevo.

**Ojo con `.video`:** ni `video.sass` ni `_template.sass` le ponen `overflow: hidden`, y el
`iframe` va en `position: absolute` dentro. El `border-radius: 10px` del contenedor **no recorta**
las esquinas del video. Cuando se ponga el video de verdad hay que añadir `overflow: hidden` a
`.video` o el `.r-10` al propio `iframe`, o las esquinas saldrán cuadradas y no como el diseño.

### 2. El banner interno no es el del diseño — ES GLOBAL, NO DE ESTA PANTALLA

`comparar_bloques.py introduccion 2` marca la primera franja como diferencia:

| | y | alto | ancho | fondo |
|---|---|---|---|---|
| artboard | 10 | 85 | 1300 | `#FCE8E9` (banda degradada rosa → lila) |
| mi render | 10 | 98 | 1300 | `#1C1B64` (la imagen de ciudad morada de la plantilla) |

El banner lo pinta `BannerInterno`, que sale en **todas** las vistas, y el rótulo que lleva
(«Nombre del recurso educativo») viene de `src/config/titulo.js`, que sigue con el placeholder
`Ecored Base PKG`. El diseño pone ahí el título del curso: «Manual de Componentes para Diseñadores
Instruccionales».

**No se tocó**: cambiarlo afecta a las 9 pantallas y pertenece al pase global / Portada, no a la
Introducción. `verificar_maqueta.py §1e` ya lo lista como placeholder sin rellenar.

### 3. Azul del bloque de video: manda el nodo del XD, no el PDF

El gate no empareja el bloque de video porque el color dominante no coincide:
artboard (PDF) `#4980B0` vs mi render `#5D93BC`, unos 20 puntos por canal más claro el mío.
La **geometría sí cuadra** (alto 582 vs 578, ancho 1230 vs 1224, x 184 vs 188 — todo dentro de
tolerancia), así que la diferencia es sólo de color.

El asset se exportó con `gen_asset.py` **desde los nodos del XD**, y la regla del rol es explícita:
el PDF aplana los modos de fusión y no es autoridad de color; el `fill` del nodo manda. La foto de
la cámara lleva una capa azul encima, que es justo lo que el PDF aplana.

**Decidido:** se queda el export del XD. Si en la revisión se ve demasiado claro, el sitio donde
mirar es el modo de fusión de esa capa en el artboard, no el PNG.

### 4. Padding de la caja rosa: clase medida `.p-32`, no `p-4`

Medido en la pág. 2 sobre el rect `#FBDED8` de 916x220: el texto entra a **32 pt** del borde
(izq 34 / arr 32 / der 44 / abj 28 — der y abj bailan porque las líneas acaban en desigual).
La escala de Bootstrap no tiene ese paso: `p-4` son 24 px y `p-5` son 48. Poner `p-4` habría sido
el error `medir-a-ojo` del diccionario, que ya va por 5 veces.

**Decidido:** se añadió `.p-32` a `src/styles/_custom.sass`, documentada, en el mismo bloque y por
la misma razón por la que en este curso family existen los `.r-N`: la utilidad de Bootstrap no da
la medida del XD. Es una clase que define padding, así que la vista **no** le añade ningún `.p-N`.

### 5. Paleta del curso: `$color-acento-contenido` cambiado de `#FF4A69` a `#FF984A`

`src/styles/_variables.sass:61` tenía el rosa de la plantilla. La insignia del título de la pág. 2
es naranja: muestreado en el PNG del diseño da `#FF984A` (6766 px del recuadro, dominante).

**Decidido:** se cambió la variable. Es una variable de plantilla, y la regla del rol dice que la
hoja de spec manda en las variables de plantilla. **Afecta a las 9 pantallas** (botones, diálogos,
líneas de tiempo…), así que si el pase global de paleta decide otra cosa, este es el sitio.

Las otras variables de curso (`$color-primario: #88dff5`, `$color-secundario: #ba59e7`) siguen con
el valor de la plantilla: **no** se tocaron porque no se han medido todavía en el diseño.

### 6. Colores nuevos en `_custom.sass` (`.bg-1/.bg-2/.bg-3`)

`#FBDED8`, `#CFA9E6` y `#265D99` no existían en ninguna parte del árbol de `entregables/`.
Se añadieron como `.bg-1`, `.bg-2` y `.bg-3` siguiendo el patrón ya documentado de
`CF1_63720048/src/styles/_custom.sass:102` (color solo, sin radio; el radio va en su `.r-N`).
No es clase inventada: es el sistema por curso que ya usan los entregables hermanos.

### 7. Alto del bloque: cuadra

`comparar_bloques.py` da el final del contenido en **1497** (mi render) contra **1498** (artboard),
tomando como origen el borde de la tarjeta blanca. 1 pt de diferencia, 0.07 %.

### 8. Identidad de los commits

El repo **no** tiene identidad local configurada (`git config --local user.*` vacío), así que
hereda la global (`luisgomezatl <luis@cornercloud.io>`). Los commits anteriores del repo son de
`manuelechavarria` y `mafechoSena`. **No se configuró ninguna identidad nueva**: la regla del rol
es usar la que esté configurada en el repo, y ponerle el usuario de otra persona no me corresponde.
Si los commits del entregable tienen que ir con la cuenta `mafechoSena`, hay que configurarla en
el repo (`git -C … config user.name/user.email`).

---

## Avisos que NO son de esta pantalla pero salieron al verificar

- **`.bgs` y `.brad` son clases muertas.** Se usan en `src/views/Sintesis.vue:9`
  (`.col-lg-10.mb-5.bgs.p-4.brad`) y no están definidas en ningún sitio — ni en este repo, ni en
  el CATALOGO, ni en el kit. Quien haga la Síntesis (tarea #9) no debe construir sobre ellas.
- **El kit no trae CSS.** `node_modules/@ecored-sena/boulder-kit/plugin/` son sólo componentes Vue:
  todas las clases de este sistema se definen en el `src/styles/` del propio entregable.
- **`verificar_maqueta.py` es un gate de CURSO, no de pantalla.** Sale con 1 mientras queden
  pendientes de otras pantallas (placeholders de `global.js`/`titulo.js`/`vite.config.js`, el
  Lorem ipsum de `Sintesis.vue`, la Actividad contra el `_AD.docx`, las imágenes repetidas de la
  actividad y los `.cajon` de Tema-1/2/3). De la Introducción no marca nada.
- **`verificar_maqueta.py §4c` está sin implementar** («altos contra el XD — PENDIENTE»). El alto
  hay que sacarlo a mano de `comparar_bloques.py`, como en el punto 7.
