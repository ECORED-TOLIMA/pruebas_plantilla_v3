#!/usr/bin/env python3
"""Genera un MP3 SILENCIOSO con una duración dada, sin ffmpeg.

Por qué: **el audio de los pódcast no viene ni en el XD ni en los DOCX** — el XD sólo dibuja el
reproductor y el DI.docx da el NOMBRE del archivo. Se deja un MP3 mudo con ese nombre exacto
como marcador (y se anota en REVISION-PENDIENTES.md) para que el componente `TarjetaAudio`
funcione y muestre la duración correcta.

Cómo: se repite un frame MPEG-1 Layer III de 32 kbps mono 44.1 kHz (cabecera `FF FB 10 C4` +
ceros = 104 bytes, 1152 muestras por frame). Chrome lo lee sin problema; la duración se
comprueba con `--dump-dom`.

Uso: gen_mp3_silencio.py <segundos> <salida.mp3>
"""
import sys

CABECERA = bytes([0xFF, 0xFB, 0x10, 0xC4])
FRAME = CABECERA + bytes(100)          # 104 B = 32 kbps @ 44.1 kHz
MUESTRAS_POR_FRAME = 1152


def main():
    segundos = float(sys.argv[1])
    salida = sys.argv[2]
    n = round(segundos * 44100 / MUESTRAS_POR_FRAME)
    with open(salida, 'wb') as f:
        f.write(FRAME * n)
    print(f'{salida}: {n} frames, {n * MUESTRAS_POR_FRAME / 44100:.1f} s, {n * len(FRAME)} B')


main()
