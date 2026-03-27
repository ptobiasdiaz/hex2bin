#!/usr/bin/env python3
"""
hex2bin / mot2bin — Convierte Intel HEX y Motorola S-record a binario
Port Python de hex2bin/mot2bin 2.0
Copyright (C) 2015 Jacques Pelletier & contributors

Dependencias (pip install):
  bincopy  — parsing de Intel HEX y Motorola S-record
  crcmod   — cálculo genérico de CRC-8/16/32
"""

import argparse
import os
import struct
import sys

try:
    import bincopy
except ImportError:
    sys.exit("Falta 'bincopy'. Instala con: pip install bincopy")

try:
    import crcmod
except ImportError:
    sys.exit("Falta 'crcmod'. Instala con: pip install crcmod")

VERSION = "2.0"

# ── Extensiones de formato ────────────────────────────────────────────────────

_SREC_EXT = {'.s19', '.s28', '.s37', '.srec', '.mot', '.sx', '.s'}


# ── Carga de fichero ──────────────────────────────────────────────────────────

def _load(filename):
    """
    Carga un fichero Intel HEX o Motorola S-record.
    La detección es automática: por extensión primero, luego por contenido.
    Retorna un bincopy.BinaryFile con los datos cargados.
    """
    try:
        with open(filename, 'r', errors='replace') as f:
            content = f.read()
    except OSError as e:
        sys.exit(f"No se puede abrir '{filename}': {e}")

    ext = os.path.splitext(filename)[1].lower()
    bf  = bincopy.BinaryFile()

    try:
        if ext in _SREC_EXT:
            bf.add_srec(content)
        else:
            # Intel HEX por defecto; si falla, intenta S-record
            try:
                bf.add_ihex(content)
            except Exception:
                bf = bincopy.BinaryFile()
                bf.add_srec(content)
    except bincopy.AddressOverlapError as e:
        sys.exit(f"Registros solapados en '{filename}': {e}")
    except Exception as e:
        sys.exit(f"Error al leer '{filename}': {e}")

    return bf


# ── Checksum / CRC ────────────────────────────────────────────────────────────

def _chk8(data: bytes) -> int:
    return sum(data) & 0xFF


def _chk16(data: bytes, big_endian: bool) -> int:
    """Suma de palabras de 16 bits (con padding par si hace falta)."""
    if len(data) % 2:
        data = data + b'\x00'
    total = 0
    for i in range(0, len(data), 2):
        w = (data[i] << 8) | data[i + 1] if big_endian else data[i] | (data[i + 1] << 8)
        total = (total + w) & 0xFFFF
    return total


def _crc(data: bytes, width: int, poly: int, init: int,
         ref_in: bool, xor_out: int) -> int:
    """
    CRC genérico via crcmod.
    crcmod necesita el polinomio con el bit implícito de orden superior incluido.
    ref_in=True activa modo reflected (equiv. RefIn=RefOut=True en el modelo Rocksoft).
    """
    try:
        fn = crcmod.mkCrcFun(poly | (1 << width),
                             initCrc=init, rev=ref_in, xorOut=xor_out)
    except ValueError as e:
        sys.exit(f"Parámetros CRC inválidos: {e}")
    return fn(data)


# ── Escritura en buffer ───────────────────────────────────────────────────────

def _w16(buf: bytearray, off: int, v: int, big_endian: bool) -> None:
    if big_endian:
        buf[off], buf[off + 1] = (v >> 8) & 0xFF, v & 0xFF
    else:
        buf[off], buf[off + 1] = v & 0xFF, (v >> 8) & 0xFF


def _w32(buf: bytearray, off: int, v: int, big_endian: bool) -> None:
    struct.pack_into('>I' if big_endian else '<I', buf, off, v & 0xFFFFFFFF)


# ── Lógica principal ──────────────────────────────────────────────────────────

def run(prog: str) -> None:
    ap = argparse.ArgumentParser(
        prog=prog,
        description=f'{prog} v{VERSION} — Intel HEX / Motorola S-record a binario',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Métodos de check (-k):\n"
            "  0  Checksum  8-bit\n"
            "  1  Checksum 16-bit\n"
            "  2  CRC8\n"
            "  3  CRC16\n"
            "  4  CRC32\n\n"
            "Ejemplos:\n"
            f"  {prog} archivo.hex\n"
            f"  {prog} -s 0 -l 8000 -p FF archivo.hex\n"
            f"  {prog} -k 3 -C 1021 0000 f f 0000 -f 7FFE -r 0 7FFD archivo.hex\n"
            f"  {prog} firmware.s19\n"
        ),
    )
    ap.add_argument('filename')
    ap.add_argument('-c', dest='check', action='store_true',
                    help='Verificar checksum de registros (siempre activo con bincopy)')
    ap.add_argument('-C', nargs=5, dest='crc_params',
                    metavar=('POLY', 'INIT', 'REFIN', 'REFOUT', 'XOROUT'),
                    help='Parámetros CRC en hex; RefIn/RefOut: t/f')
    ap.add_argument('-d', dest='show_methods', action='store_true',
                    help='Mostrar métodos de check y salir')
    ap.add_argument('-e', dest='ext', default='bin', metavar='EXT',
                    help='Extensión del fichero de salida (defecto: bin)')
    ap.add_argument('-E', dest='endian', type=int, choices=[0, 1], default=0,
                    metavar='0|1', help='Endian: 0=little (defecto), 1=big')
    ap.add_argument('-f', dest='cks_addr', metavar='ADDR',
                    help='Dirección donde escribir el resultado del check (hex)')
    ap.add_argument('-F', nargs=2, dest='force', metavar=('ADDR', 'VAL'),
                    help='Forzar valor en dirección (ambos en hex)')
    ap.add_argument('-k', dest='cks_type', metavar='0-4',
                    type=lambda x: int(x, 16),
                    help='Método: 0=CHK8 1=CHK16 2=CRC8 3=CRC16 4=CRC32')
    ap.add_argument('-l', dest='max_len', metavar='LEN',
                    help='Longitud máxima en hex')
    ap.add_argument('-m', dest='min_block', metavar='SIZE',
                    help='Tamaño mínimo de bloque en hex (potencia de 2)')
    ap.add_argument('-p', dest='pad', default='FF', metavar='HEX',
                    help='Byte de relleno en hex (defecto: FF)')
    ap.add_argument('-r', nargs=2, dest='cks_range', metavar=('START', 'END'),
                    help='Rango de direcciones para el check (hex hex)')
    ap.add_argument('-s', dest='start', metavar='ADDR',
                    help='Dirección de inicio del binario (hex)')
    ap.add_argument('-w', dest='swap', action='store_true',
                    help='Byte-swap por palabras (intercambia pares de bytes)')

    args = ap.parse_args()

    if args.show_methods:
        print("Métodos de check:\n"
              "  0  Checksum  8-bit\n"
              "  1  Checksum 16-bit\n"
              "  2  CRC8\n"
              "  3  CRC16\n"
              "  4  CRC32")
        sys.exit(0)

    # ── Parámetros básicos ────────────────────────────────────────────────────

    pad        = int(args.pad, 16) & 0xFF
    big_endian = args.endian == 1

    start_set = args.start is not None
    start     = int(args.start, 16) if start_set else 0

    maxlen_set = args.max_len is not None
    max_len    = int(args.max_len, 16) if maxlen_set else 0
    if maxlen_set and max_len > 0x800000:
        sys.exit(f"Max_Length demasiado grande: {max_len:#x}")

    minblk_set = args.min_block is not None
    min_block  = int(args.min_block, 16) if minblk_set else 0x1000

    # ── Parámetros CRC ────────────────────────────────────────────────────────

    crc_poly, crc_init, crc_refin, crc_xorout = 0x07, 0x00, False, 0x00
    if args.crc_params:
        crc_poly   = int(args.crc_params[0], 16)
        crc_init   = int(args.crc_params[1], 16)
        crc_refin  = args.crc_params[2].strip().lower() == 't'
        # [3] = RefOut: crcmod vincula RefIn y RefOut; se ignora si difieren
        crc_xorout = int(args.crc_params[4], 16)

    # ── Cargar fichero ────────────────────────────────────────────────────────

    bf = _load(args.filename)

    if not list(bf.segments):
        sys.exit("El fichero no contiene datos.")

    raw_low  = bf.minimum_address
    raw_high = bf.maximum_address      # dirección inclusiva del último byte

    records_start = raw_low
    low = start if start_set else raw_low
    if not start_set:
        start = raw_low

    if maxlen_set:
        high    = low + max_len - 1
    else:
        high    = raw_high
        max_len = raw_high - low + 1

    # ── Construir buffer de memoria ───────────────────────────────────────────

    buf = bytearray([pad] * max_len)

    for seg in bf.segments:
        for i, byte_val in enumerate(seg.data):
            offset = seg.minimum_address + i - low
            if 0 <= offset < max_len:
                buf[offset] = byte_val

    # ── Byte-swap ─────────────────────────────────────────────────────────────

    if args.swap:
        for i in range(0, len(buf) - 1, 2):
            buf[i], buf[i + 1] = buf[i + 1], buf[i]

    print(f"Binary file start = {low:08X}")
    print(f"Records start     = {records_start:08X}")
    print(f"Highest address   = {high:08X}")
    print(f"Pad Byte          = {pad:X}")

    # ── Check / Force ─────────────────────────────────────────────────────────

    force_value  = args.force is not None
    cks_addr_set = args.cks_addr is not None or force_value

    cks_addr = 0
    if force_value:
        cks_addr  = int(args.force[0], 16)
        cks_value = int(args.force[1], 16)
    elif cks_addr_set:
        cks_addr = int(args.cks_addr, 16)

    if args.cks_range:
        cks_start = int(args.cks_range[0], 16)
        cks_end   = int(args.cks_range[1], 16)
    else:
        cks_start = low
        cks_end   = high

    if cks_addr_set:
        if not (low <= cks_addr <= high):
            print("Dirección de check/forzado fuera del rango de memoria",
                  file=sys.stderr)
        else:
            off = cks_addr - low

            # Ajustar rango al buffer disponible
            if cks_start < low:
                print(f"Ajustando inicio de rango: {cks_start:X} → {low:X}")
                cks_start = low
            if cks_end > high:
                print(f"Ajustando fin de rango:    {cks_end:X} → {high:X}")
                cks_end = high

            region = bytes(buf[cks_start - low : cks_end - low + 1])

            if force_value:
                t = args.cks_type if args.cks_type is not None else 0
                if t == 0:
                    buf[off] = cks_value & 0xFF
                    print(f"Addr {cks_addr:08X} set to {cks_value & 0xFF:02X}")
                elif t == 1:
                    _w16(buf, off, cks_value, big_endian)
                    print(f"Addr {cks_addr:08X} set to {cks_value & 0xFFFF:04X}")
                else:
                    _w32(buf, off, cks_value, big_endian)
                    print(f"Addr {cks_addr:08X} set to {cks_value & 0xFFFFFFFF:08X}")

            elif args.cks_type is not None:
                t = args.cks_type

                if t == 0:                            # CHK8
                    v = _chk8(region)
                    print(f"8-bit Checksum = {v:02X}")
                    buf[off] = v
                    print(f"Addr {cks_addr:08X} set to {v:02X}")

                elif t == 1:                          # CHK16
                    v = _chk16(region, big_endian)
                    print(f"16-bit Checksum = {v:04X}")
                    _w16(buf, off, v, big_endian)
                    print(f"Addr {cks_addr:08X} set to {v:04X}")

                elif t == 2:                          # CRC8
                    v = _crc(region, 8,
                             crc_poly & 0xFF, crc_init & 0xFF,
                             crc_refin, crc_xorout & 0xFF)
                    buf[off] = v & 0xFF
                    print(f"Addr {cks_addr:08X} set to {v:02X}")

                elif t == 3:                          # CRC16
                    v = _crc(region, 16,
                             crc_poly & 0xFFFF, crc_init & 0xFFFF,
                             crc_refin, crc_xorout & 0xFFFF)
                    _w16(buf, off, v, big_endian)
                    print(f"Addr {cks_addr:08X} set to {v:04X}")

                elif t == 4:                          # CRC32
                    v = _crc(region, 32,
                             crc_poly, crc_init,
                             crc_refin, crc_xorout)
                    _w32(buf, off, v, big_endian)
                    print(f"Addr {cks_addr:08X} set to {v:08X}")

    # ── Fichero de salida ─────────────────────────────────────────────────────

    base = os.path.splitext(args.filename)[0]
    out  = f"{base}.{args.ext}"
    if os.path.abspath(out) == os.path.abspath(args.filename):
        sys.exit(f"El fichero de entrada y salida son el mismo: {out}")

    with open(out, 'wb') as f:
        f.write(buf)
        if minblk_set:
            rem = len(buf) % min_block
            if rem:
                f.write(bytes([pad] * (min_block - rem)))
                if maxlen_set:
                    print("Atención: Max Length modificado por Minimum Block Size")

    print(f"Escrito: {out}")


# ── Entry points ──────────────────────────────────────────────────────────────

def hex2bin_main() -> None:
    run('hex2bin')


def mot2bin_main() -> None:
    run('mot2bin')


if __name__ == '__main__':
    run(os.path.splitext(os.path.basename(sys.argv[0]))[0] or 'hex2bin')
