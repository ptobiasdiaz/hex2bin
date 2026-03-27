# hex2bin / mot2bin — Python port

> Port a Python de **hex2bin/mot2bin 2.0**
> Copyright (C) 2015 Jacques Pelletier & contributors
> Python port by Tobias Diaz

El código fuente original en C se conserva en [`src/`](src/) para referencia.

---

## Descripción

**hex2bin** y **mot2bin** son herramientas para convertir ficheros hexadecimales
a binario puro, habituales en el desarrollo de firmware y programación de
memorias EPROM/Flash.

- **hex2bin** — convierte ficheros en formato Intel HEX (`.hex`)
- **mot2bin** — convierte ficheros en formato Motorola S-record (`.s19`, `.srec`, …)

Ambos comandos son idénticos en opciones; la diferencia es únicamente el
formato de entrada, que se detecta automáticamente por extensión.

Características:
- Soporta Intel HEX extendido (direccionamiento segmentado y lineal)
- Soporta Motorola S-record S1/S2/S3
- Byte de relleno configurable (por defecto `0xFF`)
- Cálculo e inserción de checksum 8/16 bits y CRC-8/16/32 en el binario
- Parámetros CRC completamente configurables (polinomio, init, refIn, xorOut)
- Forzado de valores en direcciones concretas
- Byte-swap por palabras (`-w`)
- Longitud máxima y tamaño mínimo de bloque configurables

---

## Requisitos

- Python **3.6** o superior
- [`bincopy`](https://pypi.org/project/bincopy/) — parsing de Intel HEX y S-record
- [`crcmod`](https://pypi.org/project/crcmod/) — cálculo genérico de CRC

```bash
pip install bincopy crcmod
```

---

## Instalación

### Desde PyPI (cuando esté publicado)

```bash
pip install hex2bin
```

### Desde el código fuente

```bash
pip install .
```

### Sin instalar

```bash
python hex2bin.py [opciones] fichero.hex
python hex2bin.py [opciones] fichero.s19
```

---

## Uso

```
hex2bin [opciones] <fichero_entrada>
mot2bin [opciones] <fichero_entrada>
```

El fichero de salida se genera en el mismo directorio con extensión `.bin`
(configurable con `-e`).

### Opciones

| Opción | Descripción |
|--------|-------------|
| `-c` | Verificar checksum de cada registro (activo por defecto con bincopy) |
| `-C POLY INIT REFIN REFOUT XOROUT` | Parámetros CRC en hex; RefIn/RefOut: `t`/`f` |
| `-d` | Mostrar métodos de check disponibles y salir |
| `-e EXT` | Extensión del fichero de salida (defecto: `bin`) |
| `-E 0\|1` | Endian para checksum/CRC: `0`=little (defecto), `1`=big |
| `-f ADDR` | Dirección donde escribir el resultado del check (hex) |
| `-F ADDR VAL` | Forzar valor concreto en dirección (ambos en hex) |
| `-k 0-4` | Método de check: `0`=CHK8, `1`=CHK16, `2`=CRC8, `3`=CRC16, `4`=CRC32 |
| `-l LEN` | Longitud máxima del binario en hex (rellena con pad byte) |
| `-m SIZE` | Tamaño mínimo de bloque en hex (potencia de 2) |
| `-p HEX` | Byte de relleno en hex (defecto: `FF`) |
| `-r START END` | Rango de direcciones para calcular el check (hex hex) |
| `-s ADDR` | Dirección de inicio del binario (hex) |
| `-w` | Byte-swap por palabras (intercambia pares de bytes) |

### Métodos de check (`-k`)

| Valor | Método |
|-------|--------|
| `0` | Checksum 8-bit (suma de bytes) |
| `1` | Checksum 16-bit (suma de palabras) |
| `2` | CRC-8 |
| `3` | CRC-16 |
| `4` | CRC-32 |

---

## Ejemplos

### Conversión simple

```bash
hex2bin programa.hex          # genera programa.bin
mot2bin firmware.s19          # genera firmware.bin
```

### Con dirección de inicio y longitud fija

```bash
hex2bin -s 0 -l 8000 -p FF programa.hex
```

### CRC-16 XMODEM en dirección 0x7FFE

```bash
hex2bin -k 3 -C 1021 0000 f f 0000 -f 7FFE -r 0 7FFD programa.hex
```

### CRC-16 MODBUS (reflected)

```bash
hex2bin -k 3 -C 8005 FFFF t t 0000 -f 7FFE -r 0 7FFD programa.hex
```

### CRC-32 estándar (PKZIP)

```bash
hex2bin -k 4 -C 04C11DB7 FFFFFFFF t t FFFFFFFF -f 7FFC -r 0 7FFB programa.hex
```

### Forzar valor en dirección

```bash
hex2bin -F 7FFF A5 programa.hex
```

### Byte-swap y extensión personalizada

```bash
hex2bin -w -e rom programa.hex    # genera programa.rom con bytes intercambiados
```

### Tamaño mínimo de bloque (múltiplo de 4 KB)

```bash
hex2bin -m 1000 programa.hex
```

---

## Parámetros CRC (`-C`)

El modelo de parámetros sigue la especificación Rocksoft:

```
-C <POLY> <INIT> <REFIN> <REFOUT> <XOROUT>
```

| Campo | Descripción |
|-------|-------------|
| `POLY` | Polinomio generador (sin el bit implícito superior), en hex |
| `INIT` | Valor inicial del registro CRC, en hex |
| `REFIN` | Reflexión de bits de entrada: `t`=sí, `f`=no |
| `REFOUT` | Reflexión de bits de salida: `t`=sí, `f`=no |
| `XOROUT` | XOR aplicado al resultado final, en hex |

> **Nota:** `crcmod` vincula `REFIN` y `REFOUT` juntos. Para CRCs estándar
> ambos valores son siempre iguales, por lo que esto no supone limitación práctica.

Algunos ejemplos de parámetros estándar:

| Algoritmo | POLY | INIT | REFIN | REFOUT | XOROUT |
|-----------|------|------|-------|--------|--------|
| CRC-16/XMODEM | `1021` | `0000` | `f` | `f` | `0000` |
| CRC-16/MODBUS | `8005` | `FFFF` | `t` | `t` | `0000` |
| CRC-16/KERMIT | `1021` | `0000` | `t` | `t` | `0000` |
| CRC-32/PKZIP  | `04C11DB7` | `FFFFFFFF` | `t` | `t` | `FFFFFFFF` |
| CRC-32C/iSCSI | `1EDC6F41` | `FFFFFFFF` | `t` | `t` | `FFFFFFFF` |

---

## Licencia

GNU General Public License v3 — ver [LICENSE](LICENSE).
