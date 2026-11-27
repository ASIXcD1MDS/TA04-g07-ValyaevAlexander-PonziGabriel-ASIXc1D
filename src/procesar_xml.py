#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
DASHBOARD INTERACTIVO DE INCIDENCIAS XML (ASIXc TA04 - Parte 3)
==============================================================================
Archivo : src/procesar_xml.py
Estructura esperada del proyecto:

    TA04-G07-.../
    ├── data/   incidencies.xml, incidencies.csv, incidencies_netes.*
    ├── src/    procesar_xml.py  (este archivo), csv_to_xml.py, ...
    └── web/    index.html, informe.html, plantilla.html

Uso:
    python src/procesar_xml.py                 -> busca data/incidencies.xml
    python src/procesar_xml.py ruta/al.xml     -> usa el XML indicado

Descripción: Lee 'incidencies.xml' en streaming (iterparse), sanea texto
             ofuscado (Mojibake, octal, Zalgo, homóglifos, Base64, hex, HTML),
             filtra registros erróneos y ofrece un menú interactivo con
             tablas y gráficos de barras en la terminal.
==============================================================================
"""

import base64
import html
import os
import re
import statistics
import sys
import unicodedata
import webbrowser
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# Activa los colores ANSI también en la consola de Windows (cmd / PowerShell)
if os.name == "nt":
    os.system("")

# Fuerza UTF-8 en la salida para que las cajas Unicode se vean bien
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# ----------------------------------------------------------------------------
# CONSTANTES
# ----------------------------------------------------------------------------
URL_WEB = "https://asixcd1mds.github.io/TA04-g07-ValyaevAlexander-PonziGabriel-ASIXc1D/"

# Códigos de color ANSI
VERDE = "\033[92m"
ROJO = "\033[91m"
AMARILLO = "\033[93m"
AZUL = "\033[94m"
CIAN = "\033[96m"
MAGENTA = "\033[95m"
BLANCO = "\033[97m"
NEGRITA = "\033[1m"
GRIS = "\033[90m"
RESET = "\033[0m"

# Parámetros de validación
ANIO_MINIMO = 2020
HOY = datetime.now()
MAX_USUARIOS_AFECTADOS = 500
ANCHO_CAJA = 81  # Ancho uniforme de todas las tablas y tarjetas

VALORES_BASURA = {
    "test", "prova", "prueba", "asdf", "qwerty",
    "xxx", "none", "null", "nan", "n/a", "na", "ni", "s/n"
}

# Mapa de homóglifos cirílicos y griegos que imitan letras latinas
HOMOGLIFOS = str.maketrans({
    "А": "A", "а": "a", "В": "B", "Е": "E", "е": "e", "Ё": "E", "ё": "e",
    "З": "3", "І": "I", "і": "i", "Ї": "I", "ї": "i", "К": "K", "к": "k",
    "М": "M", "м": "m", "Н": "H", "О": "O", "о": "o", "Р": "P", "р": "p",
    "С": "C", "с": "c", "Т": "T", "т": "t", "У": "Y", "у": "y", "Х": "X",
    "х": "x", "Ѕ": "S", "ѕ": "s", "Ј": "J", "ј": "j",
    "Α": "A", "α": "a", "Β": "B", "Ε": "E", "ε": "e", "Ζ": "Z", "Η": "H",
    "Ι": "I", "ι": "i", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O", "ο": "o",
    "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X"
})

ESCAPES_RESIDUALES = {
    "xf3": "ó", "xe0": "à", "xe8": "è", "xe9": "é", "xed": "í",
    "xf2": "ò", "xfa": "ú", "xe7": "ç", "xf1": "ñ", "xe1": "á"
}

MAPA_DEP = {
    "administració": "Administració", "administracio": "Administració",
    "administración": "Administració", "administracion": "Administració",
    "docència": "Docència", "docencia": "Docència",
    "direcció": "Direcció", "direccio": "Direcció",
    "dirección": "Direcció", "direccion": "Direcció",
    "biblioteca": "Biblioteca",
    "secretaria": "Secretaria", "secretaría": "Secretaria",
    "manteniment": "Manteniment", "mantenimiento": "Manteniment",
    "it": "IT",
    "orientació": "Orientació", "orientacio": "Orientació",
    "orientación": "Orientació", "orientacion": "Orientació",
    "comunicació": "Comunicació", "comunicacio": "Comunicació",
    "comunicación": "Comunicació", "comunicacion": "Comunicació",
    "cuina": "Cuina", "cocina": "Cuina",
    "consergeria": "Consergeria", "conserjería": "Consergeria", "conserjeria": "Consergeria",
    "altres": "Altres", "otros": "Altres"
}

MAPA_EQUIP = {
    "ordinador": "Ordinador", "ordenador": "Ordinador", "pc": "Ordinador",
    "impressora": "Impressora", "impresora": "Impressora",
    "monitor": "Monitor",
    "projector": "Projector", "proyector": "Projector",
    "webcam": "Webcam",
    "altaveus": "Altaveus", "altavoces": "Altaveus",
    "tauleta": "Tauleta", "tablet": "Tauleta",
    "escàner": "Escàner", "escaner": "Escàner", "escáner": "Escàner",
    "pissarra digital": "Pissarra digital", "pizarra digital": "Pissarra digital",
    "altres": "Altres", "otros": "Altres"
}

MAPA_CAT = {
    "hardware": "Hardware",
    "software": "Software",
    "xarxa": "Xarxa", "red": "Xarxa",
    "perifèrics": "Perifèrics", "periferics": "Perifèrics",
    "periféricos": "Perifèrics", "perifericos": "Perifèrics",
    "no identificat": "No identificat", "no identificado": "No identificat",
    "configuració": "Configuració", "configuracio": "Configuració",
    "configuración": "Configuració", "configuracion": "Configuració",
    "llicències": "Llicències", "llicencies": "Llicències",
    "licencias": "Llicències",
    "alimentació elèctrica": "Alimentació elèctrica",
    "alimentacio electrica": "Alimentació elèctrica",
    "alimentación eléctrica": "Alimentació elèctrica",
    "cablejat": "Cablejat", "cableado": "Cablejat",
    "altres": "Altres", "otros": "Altres"
}


# ----------------------------------------------------------------------------
# SANEAMIENTO DE TEXTO
# ----------------------------------------------------------------------------
def arreglar_mojibake(texto):
    """Repara UTF-8 mal interpretado como Latin-1/Windows-1252 (ej. AlimentaciÃ³)."""
    for enc in ("latin-1", "cp1252"):
        try:
            candidato = texto.encode(enc).decode("utf-8")
            if candidato != texto:
                return candidato
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return texto


def limpiar_unicode_raro(texto):
    """Normaliza fuentes matemáticas (NFKC) y elimina Zalgo, invisibles y emojis."""
    texto = unicodedata.normalize("NFKC", texto)
    return "".join(
        ch for ch in texto
        if unicodedata.category(ch) not in ("Mn", "Mc", "Me", "Cf", "Cc", "So")
    )


def arreglar_homoglifos_mixtos(texto):
    """Unifica homóglifos cirílicos/griegos en palabras con letras latinas."""
    palabras = []
    for tok in texto.split(" "):
        tiene_latin = any("LATIN" in unicodedata.name(c, "") for c in tok if c.isalpha())
        palabras.append(tok.translate(HOMOGLIFOS) if tiene_latin else tok)
    return " ".join(palabras)


def limpiar_texto(valor, decodificar=True):
    """Decodifica texto ofuscado y elimina caracteres de ruido."""
    if not valor:
        return "", False
    original = valor.strip()
    texto = original

    if decodificar:
        # 1. Entidades HTML (ej: &#73;&#78;&#86;...)
        if "&#" in texto or "&amp;" in texto:
            texto = html.unescape(html.unescape(texto))

        # 2. Escapes Unicode \uXXXX y hexadecimales \xXX
        if "\\u" in texto:
            texto = re.sub(
                r'\\u([0-9a-fA-F]{4})',
                lambda m: chr(int(m.group(1), 16)),
                texto
            )
        if "\\x" in texto:
            try:
                if re.search(r'(?:\\x[0-9a-fA-F]{2}){2,}', texto):
                    texto = re.sub(
                        r'(?:\\x[0-9a-fA-F]{2})+',
                        lambda m: bytes.fromhex(m.group(0).replace("\\x", "")).decode(
                            "utf-8", errors="replace"
                        ),
                        texto
                    )
                else:
                    texto = re.sub(
                        r'\\x([0-9a-fA-F]{2})',
                        lambda m: chr(int(m.group(1), 16)),
                        texto
                    )
            except Exception:
                pass

        # 3. Binario de 8 bits separado por espacios
        if re.fullmatch(r'(?:[01]{8}\s*){3,}', texto):
            try:
                text_bits = texto.replace(" ", "")
                dec = bytes(
                    int(text_bits[i:i + 8], 2) for i in range(0, len(text_bits), 8)
                ).decode("utf-8", errors="ignore")
                if dec and any(c.isalnum() for c in dec):
                    texto = dec
            except Exception:
                pass
        # 4. Hexadecimal separado por espacios (ej: 41 75 6c 61)
        elif re.fullmatch(r'(?:[0-9a-fA-F]{2}\s+){2,}[0-9a-fA-F]{2}', texto):
            try:
                dec = bytes.fromhex(texto.replace(" ", "")).decode("utf-8", errors="ignore")
                if dec and any(c.isalnum() for c in dec):
                    texto = dec
            except Exception:
                pass
        # 5. Octal separado por espacios (ej: 103 141 142 154 145 152 141 164 -> Cablejat)
        elif re.fullmatch(r'(?:[0-3][0-7]{2}\s+){2,}[0-3][0-7]{2}', texto):
            try:
                vals = [int(tok, 8) for tok in texto.split()]
                if all(0 <= v <= 255 for v in vals):
                    dec = bytes(vals).decode("utf-8", errors="ignore")
                    if dec and any(c.isalnum() for c in dec):
                        texto = dec
            except Exception:
                pass
        # 6. Base64 (ej: U2FsYSAwLjEx -> Sala 0.11)
        elif (
            len(texto) % 4 == 0
            and re.fullmatch(r'[A-Za-z0-9+/]{8,}={0,2}', texto)
            and " " not in texto
            and not texto.upper().startswith(("INV", "EQ"))
        ):
            try:
                dec = base64.b64decode(texto, validate=True).decode("utf-8")
                if dec and dec.isprintable() and any(c.isalpha() for c in dec):
                    texto = dec
            except Exception:
                pass

        # 7. Reparación de Mojibake, Unicode raro y homóglifos
        texto = arreglar_mojibake(texto)
        texto = limpiar_unicode_raro(texto)
        texto = arreglar_homoglifos_mixtos(texto)
        texto = re.sub(
            r'\b([A-Za-zÀ-ÿ]+)\s+(x(?:f3|e0|e8|e9|ed|f2|fa|e7|f1|e1))(?=\s|$)',
            lambda m: m.group(1) + ESCAPES_RESIDUALES[m.group(2).lower()],
            texto
        )

    # 8. Limpieza final de puntuación sobrante
    texto = re.sub(r'["«»]+', '', texto)
    texto = re.sub(r'[;\\<>]+', ' ', texto)
    texto = re.sub(r'!{2,}', '', texto)
    texto = re.sub(r'\s+', ' ', texto).strip(" ,.-")
    return texto, (texto != original)


def es_basura(texto):
    """Detecta campos vacíos, solo con símbolos/emojis o valores de prueba."""
    if not texto or not any(c.isalnum() for c in texto):
        return True
    return texto.lower() in VALORES_BASURA


def parsear_fecha(texto_fecha):
    """Convierte texto a datetime aceptando formatos comunes."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texto_fecha.strip(), fmt)
        except ValueError:
            continue
    return None


def normalizar_categoria(texto, mapa):
    """Mapea valores equivalentes al nombre canónico oficial."""
    return mapa.get(texto.strip().lower(), texto.strip().capitalize())


def normalizar_ubicacio(texto):
    """Unifica capitalización de aulas/salas (ej. 'lAbOrAtOrI 1.11' -> 'Laboratori 1.11')."""
    return " ".join(
        p.capitalize() if any(c.isalpha() for c in p) else p
        for p in texto.strip().split()
    )


def normalizar_inventari(texto):
    """Estandariza códigos de inventario (ej. 'INV 86813' -> 'INV-86813')."""
    return re.sub(r'^(INV|EQ)\s+(\d+)$', r'\1-\2', texto.upper().strip())


def validar_tecnico(texto):
    """Evita que ensayos largos, Morse o cadenas binarias ensucien la salida."""
    if not texto:
        return "Sin asignar", False
    if re.fullmatch(r'[.\-/\s]{8,}', texto):
        return "Contacto inválido / corrupto", True
    if re.fullmatch(r'[01\s]{16,}', texto):
        return "Contacto inválido / corrupto", True
    if re.fullmatch(r'(?:[0-9a-fA-F]{2}\s+){6,}[0-9a-fA-F]{2}', texto):
        return "Contacto inválido / corrupto", True
    if len(texto) > 55 or len(texto.split()) > 6:
        return "Contacto inválido / corrupto", True
    if not any(c.isalnum() for c in texto) or texto.lower() in VALORES_BASURA:
        return "Contacto inválido / corrupto", True
    return texto, False


def es_inventario_valido_reincidencia(inv):
    """Descarta códigos falsos cortos como 'N1' del ranking de reincidentes."""
    return len(inv) >= 4 and sum(c.isdigit() for c in inv) >= 2


def obtener_campo(elem, candidatos):
    """Obtiene texto del primer nodo XML coincidente."""
    for tag in candidatos:
        nodo = elem.find(tag)
        if nodo is not None and nodo.text is not None:
            return nodo.text
    for hijo in elem:
        for cand in candidatos:
            if cand in hijo.tag.lower() and hijo.text is not None:
                return hijo.text
    return ""


# ----------------------------------------------------------------------------
# UTILIDADES DE PRESENTACIÓN
# ----------------------------------------------------------------------------
def ancho_visual(texto):
    """Calcula el ancho real en terminal teniendo en cuenta caracteres anchos."""
    w = 0
    for ch in str(texto):
        if unicodedata.combining(ch):
            continue
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w


def ajustar_col(texto, ancho, alinear="izq"):
    """Trunca de forma segura según ancho visual y rellena con espacios."""
    s = str(texto)
    if ancho_visual(s) > ancho:
        rec = ""
        w = 0
        limite = ancho if ancho <= 3 else ancho - 3
        for ch in s:
            cw = 0 if unicodedata.combining(ch) else (
                2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
            )
            if w + cw > limite:
                break
            rec += ch
            w += cw
        s = rec if ancho <= 3 else rec + "..."
    faltan = max(0, ancho - ancho_visual(s))
    return (s + " " * faltan) if alinear == "izq" else (" " * faltan + s)


def barra_coloreada(valor, maximo, ancho, color):
    """Construye una barra de progreso con ancho exacto sin romper bordes."""
    if maximo <= 0 or valor <= 0:
        return f"{GRIS}{'░' * ancho}{RESET}"
    llenos = max(1, round((valor / maximo) * ancho))
    llenos = min(llenos, ancho)
    return f"{color}{'█' * llenos}{GRIS}{'░' * (ancho - llenos)}{RESET}"


def titulo_seccion(num, texto):
    """Imprime un encabezado de sección limpio y uniforme."""
    print(f"\n  {NEGRITA}{CIAN}[{num}] {texto}{RESET}")


def limpiar_pantalla():
    os.system("cls" if os.name == "nt" else "clear")


def pausa():
    try:
        input(f"\n  {GRIS}Pulsa ENTER para volver al menú...{RESET}")
    except EOFError:
        pass


def banner(subtitulo=None):
    """Cabecera principal del panel (81 chars)."""
    borde_doble = "═" * (ANCHO_CAJA - 2)
    print(f"\n  {CIAN}╔{borde_doble}╗{RESET}")
    print(f"  {CIAN}║{RESET} {NEGRITA}{BLANCO}{ajustar_col('PANEL DE ANÁLISIS DE INCIDENCIAS TIC Y AUDIOVISUALES (ASIXc TA04)', ANCHO_CAJA - 4)}{RESET} {CIAN}║{RESET}")
    if subtitulo:
        print(f"  {CIAN}║{RESET} {GRIS}{ajustar_col(subtitulo, ANCHO_CAJA - 4)}{RESET} {CIAN}║{RESET}")
    print(f"  {CIAN}╚{borde_doble}╝{RESET}")


# ----------------------------------------------------------------------------
# LECTURA Y PROCESADO DEL XML
# ----------------------------------------------------------------------------
def procesar_xml(ruta_xml):
    """Procesa el XML en streaming aplicando saneamiento, filtrado y deduplicación."""
    total_leidos = 0
    saneados = 0
    tecnicos_corruptos = 0
    validos = []
    motivos_descarte = Counter()
    ejemplos_descarte = []
    vistos = set()

    for _, elem in ET.iterparse(ruta_xml, events=("end",)):
        if elem.tag == "incidencia":
            total_leidos += 1
            id_reg = elem.attrib.get("id", str(total_leidos))

            data_raw, _ = limpiar_texto(
                obtener_campo(elem, ["data_de_la_incidencia", "data"]),
                decodificar=False
            )
            usuario, s_usr = limpiar_texto(obtener_campo(elem, ["usuari_afectat", "usuari"]))
            dep, s_dep = limpiar_texto(obtener_campo(elem, ["departament"]))
            equip, s_eq = limpiar_texto(obtener_campo(elem, ["tipus_dequip", "tipus_equip", "equip"]))
            ubicacion, s_ub = limpiar_texto(obtener_campo(elem, ["ubicacio"]))
            inventario, s_inv = limpiar_texto(
                obtener_campo(elem, ["numero_dinventari", "num_inventari", "inventari"])
            )
            categoria, s_cat = limpiar_texto(
                obtener_campo(elem, ["categoria_de_lavaria", "categoria_avaria", "categoria"])
            )
            descripcion, s_desc = limpiar_texto(
                obtener_campo(elem, ["descripcio_de_la_incidencia", "descripcio"])
            )
            afectados_raw, _ = limpiar_texto(
                obtener_campo(elem, ["usuaris_afectats", "afectats"]),
                decodificar=False
            )
            tec_raw, s_tec = limpiar_texto(
                obtener_campo(elem, ["contacte_del_tecnic_assignat", "contacte_tecnic", "tecnic"])
            )

            dt = parsear_fecha(data_raw)
            motiu = None
            num_afectados = 0

            if dt is None:
                motiu = "Fecha inválida o vacía"
            elif dt.year > HOY.year:
                motiu = f"Fecha futura anómala (año {dt.year})"
            elif dt > HOY:
                motiu = "Fecha futura (posterior a hoy)"
            elif dt.year < ANIO_MINIMO:
                motiu = f"Fecha demasiado antigua (< {ANIO_MINIMO})"
            else:
                try:
                    num_afectados = int(afectados_raw)
                    if not (1 <= num_afectados <= MAX_USUARIOS_AFECTADOS):
                        raise ValueError
                except ValueError:
                    motiu = "Usuarios afectados no numérico o fuera de rango"

            if not motiu and any(
                es_basura(c) for c in (dep, equip, ubicacion, inventario, categoria, descripcion)
            ):
                motiu = "Campos obligatorios vacíos o con ruido/emojis"

            if not motiu:
                dep_n = normalizar_categoria(dep, MAPA_DEP)
                equip_n = normalizar_categoria(equip, MAPA_EQUIP)
                cat_n = normalizar_categoria(categoria, MAPA_CAT)
                ubic_n = normalizar_ubicacio(ubicacion)
                inv_n = normalizar_inventari(inventario)
                tec_n, es_tec_corrupto = validar_tecnico(tec_raw)

                clave = (dt.strftime("%Y-%m-%d"), inv_n, cat_n, descripcion.lower())
                if clave in vistos:
                    motiu = "Registro duplicado"
                else:
                    vistos.add(clave)

            if motiu:
                motivos_descarte[motiu] += 1
                if len(ejemplos_descarte) < 5:
                    ejemplos_descarte.append((id_reg, motiu, data_raw or "-"))
            else:
                if any((s_usr, s_dep, s_eq, s_ub, s_inv, s_cat, s_desc, s_tec)):
                    saneados += 1
                if es_tec_corrupto:
                    tecnicos_corruptos += 1

                validos.append({
                    "id": id_reg,
                    "fecha": dt,
                    "usuario": usuario or "Anónimo",
                    "departamento": dep_n,
                    "tipo_equipo": equip_n,
                    "ubicacion": ubic_n,
                    "inventario": inv_n,
                    "categoria": cat_n,
                    "descripcion": descripcion,
                    "usuarios_afectados": num_afectados,
                    "tecnico": tec_n
                })

            elem.clear()

    return {
        "total_leidos": total_leidos,
        "saneados": saneados,
        "tecnicos_corruptos": tecnicos_corruptos,
        "validos": validos,
        "motivos_descarte": motivos_descarte,
        "ejemplos_descarte": ejemplos_descarte
    }


def calcular_agregaciones(res):
    """Calcula una sola vez todos los contadores que usan las secciones."""
    validos = res["validos"]
    agg = {
        "afectados": [r["usuarios_afectados"] for r in validos],
        "cat_cnt": Counter(), "cat_imp": defaultdict(int),
        "eq_cnt": Counter(), "eq_imp": defaultdict(int),
        "dep_cnt": Counter(), "dep_imp": defaultdict(int),
        "ubic_cnt": Counter(), "ubic_imp": defaultdict(int),
        "mes_cnt": Counter(), "mes_imp": defaultdict(int),
        "tec_cnt": Counter(), "tec_imp": defaultdict(int),
        "inv_cnt": Counter(),
        "inv_eq": defaultdict(Counter), "inv_ub": defaultdict(Counter),
        "inv_afe": defaultdict(int),
        "sin_asignar": 0,
    }
    for r in validos:
        af = r["usuarios_afectados"]
        agg["cat_cnt"][r["categoria"]] += 1
        agg["cat_imp"][r["categoria"]] += af
        agg["eq_cnt"][r["tipo_equipo"]] += 1
        agg["eq_imp"][r["tipo_equipo"]] += af
        agg["dep_cnt"][r["departamento"]] += 1
        agg["dep_imp"][r["departamento"]] += af
        agg["ubic_cnt"][r["ubicacion"]] += 1
        agg["ubic_imp"][r["ubicacion"]] += af
        mes = r["fecha"].strftime("%Y-%m")
        agg["mes_cnt"][mes] += 1
        agg["mes_imp"][mes] += af

        if es_inventario_valido_reincidencia(r["inventario"]):
            inv = r["inventario"]
            agg["inv_cnt"][inv] += 1
            agg["inv_eq"][inv][r["tipo_equipo"]] += 1
            agg["inv_ub"][inv][r["ubicacion"]] += 1
            agg["inv_afe"][inv] += af

        if r["tecnico"] == "Sin asignar":
            agg["sin_asignar"] += 1
        elif r["tecnico"] != "Contacto inválido / corrupto":
            agg["tec_cnt"][r["tecnico"]] += 1
            agg["tec_imp"][r["tecnico"]] += af
    return agg


# ----------------------------------------------------------------------------
# SECCIONES DEL INFORME (cada una se puede mostrar por separado desde el menú)
# ----------------------------------------------------------------------------
def agrupar_items(contador, impacto, max_filas=9):
    """Agrupa las categorías minoritarias en 'Otros' si superan el máximo de filas."""
    ordenados = contador.most_common()
    if len(ordenados) <= max_filas:
        return [(k, v, impacto[k]) for k, v in ordenados]
    top = [(k, v, impacto[k]) for k, v in ordenados[:max_filas - 1]]
    resto_cnt = sum(v for _, v in ordenados[max_filas - 1:])
    resto_imp = sum(impacto[k] for k, _ in ordenados[max_filas - 1:])
    n_tipos = len(ordenados) - (max_filas - 1)
    top.append((f"Otros ({n_tipos} tipos)", resto_cnt, resto_imp))
    return top


def render_tabla_distribucion(titulo, num_sec, contador, impacto, total, color=CIAN, max_filas=9):
    """Renderiza una tabla de 6 columnas (81 chars) con distribución y media."""
    filas = agrupar_items(contador, impacto, max_filas=max_filas)
    max_val = max((v for _, v, _ in filas), default=1)
    W_NOM, W_NUM, W_PCT, W_BAR, W_AFE, W_MED = 22, 6, 6, 16, 7, 5

    b_top = f"┌{'─'*(W_NOM+2)}┬{'─'*(W_NUM+2)}┬{'─'*(W_PCT+2)}┬{'─'*(W_BAR+2)}┬{'─'*(W_AFE+2)}┬{'─'*(W_MED+2)}┐"
    b_mid = f"├{'─'*(W_NOM+2)}┼{'─'*(W_NUM+2)}┼{'─'*(W_PCT+2)}┼{'─'*(W_BAR+2)}┼{'─'*(W_AFE+2)}┼{'─'*(W_MED+2)}┤"
    b_bot = f"└{'─'*(W_NOM+2)}┴{'─'*(W_NUM+2)}┴{'─'*(W_PCT+2)}┴{'─'*(W_BAR+2)}┴{'─'*(W_AFE+2)}┴{'─'*(W_MED+2)}┘"

    titulo_seccion(num_sec, titulo)
    print(f"  {GRIS}{b_top}{RESET}")
    print(
        f"  {GRIS}│{RESET} {NEGRITA}{ajustar_col('Categoría / Elemento', W_NOM)}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Incid.', W_NUM, 'der')}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('%', W_PCT, 'der')}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Distribución', W_BAR)}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Afect.', W_AFE, 'der')}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Media', W_MED, 'der')}{RESET} {GRIS}│{RESET}"
    )
    print(f"  {GRIS}{b_mid}{RESET}")

    for nom, cnt, afe in filas:
        pct = (cnt / total * 100) if total else 0
        med = (afe / cnt) if cnt else 0
        bar = barra_coloreada(cnt, max_val, W_BAR, color)
        print(
            f"  {GRIS}│{RESET} {ajustar_col(nom, W_NOM)} "
            f"{GRIS}│{RESET} {ajustar_col(cnt, W_NUM, 'der')} "
            f"{GRIS}│{RESET} {ajustar_col(f'{pct:.1f}%', W_PCT, 'der')} "
            f"{GRIS}│{RESET} {bar} "
            f"{GRIS}│{RESET} {ajustar_col(afe, W_AFE, 'der')} "
            f"{GRIS}│{RESET} {ajustar_col(f'{med:.1f}', W_MED, 'der')} {GRIS}│{RESET}"
        )

    print(f"  {GRIS}{b_bot}{RESET}")


def sec_auditoria(res, agg=None):
    total_leidos = res["total_leidos"]
    validos = res["validos"]
    descarte = res["motivos_descarte"]
    ejemplos = res["ejemplos_descarte"]
    t_validos = len(validos)
    t_descarte = sum(descarte.values())
    pct_val = (t_validos / total_leidos * 100) if total_leidos else 0
    pct_san = (res["saneados"] / t_validos * 100) if t_validos else 0

    titulo_seccion(1, "AUDITORÍA DE CALIDAD Y LIMPIEZA DE DATOS")
    print(f"  {GRIS}┌{'─'*39}┬{'─'*39}┐{RESET}")
    print(
        f"  {GRIS}│{RESET} {NEGRITA}{ajustar_col('Resumen de Ingesta XML', 37)}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Desglose de Descartes', 37)}{RESET} {GRIS}│{RESET}"
    )
    print(f"  {GRIS}├{'─'*39}┼{'─'*39}┤{RESET}")

    col_izq = [
        ("Registros leídos", f"{total_leidos}", BLANCO),
        ("Válidos para análisis", f"{t_validos} ({pct_val:.1f}%)", VERDE),
        ("Saneados/decodificados", f"{res['saneados']} ({pct_san:.1f}%)", CIAN),
        ("Descartados (inválidos)", f"{t_descarte}", ROJO),
        ("Téc. corruptos aislados", f"{res['tecnicos_corruptos']}", AMARILLO),
    ]
    col_der = [(m, f"{q}", ROJO) for m, q in descarte.most_common(5)]
    if not col_der:
        col_der = [("Sin registros descartados", "0", VERDE)]

    for i in range(max(len(col_izq), len(col_der))):
        if i < len(col_izq):
            lbl, val, col = col_izq[i]
            txt_i = f"{ajustar_col(lbl + ':', 25)} {col}{ajustar_col(val, 11, 'der')}{RESET}"
        else:
            txt_i = " " * 37
        if i < len(col_der):
            lbl_d, val_d, col_d = col_der[i]
            txt_d = f"{ajustar_col(lbl_d, 30)} {col_d}{ajustar_col(val_d, 6, 'der')}{RESET}"
        else:
            txt_d = " " * 37
        print(f"  {GRIS}│{RESET} {txt_i} {GRIS}│{RESET} {txt_d} {GRIS}│{RESET}")
    print(f"  {GRIS}└{'─'*39}┴{'─'*39}┘{RESET}")

    if ejemplos:
        print(f"  {GRIS}  Muestra descartada: " + " | ".join(
            f"#{id_r} ({d}: {m})" for id_r, m, d in ejemplos[:3]
        ) + RESET)


def sec_kpis(res, agg):
    validos = res["validos"]
    t_validos = len(validos)
    afectados = agg["afectados"]
    top_cat, top_cat_n = agg["cat_cnt"].most_common(1)[0]
    top_eq, top_eq_n = agg["eq_cnt"].most_common(1)[0]
    top_dep, top_dep_n = agg["dep_cnt"].most_common(1)[0]

    titulo_seccion(2, "RESUMEN EJECUTIVO DE IMPACTO (KPIs)")
    print(f"  {GRIS}┌{'─'*39}┬{'─'*39}┐{RESET}")
    kpis_izq = [
        ("Usuarios afectados", f"{sum(afectados)} pers."),
        ("Media por incidencia", f"{statistics.mean(afectados):.2f} pers."),
        ("Mediana | Rango", f"{statistics.median(afectados):.1f} | [{min(afectados)}..{max(afectados)}]")
    ]
    kpis_der = [
        ("Avería principal", f"{top_cat} ({top_cat_n/t_validos*100:.1f}%)"),
        ("Equipo crítico", f"{top_eq} ({top_eq_n/t_validos*100:.1f}%)"),
        ("Depto. afectado", f"{top_dep} ({top_dep_n/t_validos*100:.1f}%)")
    ]
    for (li, vi), (ld, vd) in zip(kpis_izq, kpis_der):
        t_i = f"{ajustar_col(li + ':', 24)} {VERDE}{ajustar_col(vi, 12, 'der')}{RESET}"
        t_d = f"{ajustar_col(ld + ':', 17)} {CIAN}{ajustar_col(vd, 19, 'der')}{RESET}"
        print(f"  {GRIS}│{RESET} {t_i} {GRIS}│{RESET} {t_d} {GRIS}│{RESET}")
    print(f"  {GRIS}└{'─'*39}┴{'─'*39}┘{RESET}")


def sec_categorias(res, agg):
    render_tabla_distribucion("DISTRIBUCIÓN POR CATEGORÍA DE AVERÍA", 3,
                              agg["cat_cnt"], agg["cat_imp"], len(res["validos"]), color=VERDE)


def sec_equipos(res, agg):
    render_tabla_distribucion("DISTRIBUCIÓN POR TIPO DE EQUIPO", 4,
                              agg["eq_cnt"], agg["eq_imp"], len(res["validos"]), color=CIAN)


def sec_departamentos(res, agg):
    render_tabla_distribucion("INCIDENCIAS POR DEPARTAMENTO", 5,
                              agg["dep_cnt"], agg["dep_imp"], len(res["validos"]), color=MAGENTA)


def sec_ubicaciones(res, agg):
    t_validos = len(res["validos"])
    W_RK, W_UB, W_NU, W_PC, W_BR, W_AF = 2, 25, 7, 7, 14, 7
    titulo_seccion(6, "TOP 5 UBICACIONES CON MÁS INCIDENCIAS")
    print(f"  {GRIS}┌{'─'*(W_RK+2)}┬{'─'*(W_UB+2)}┬{'─'*(W_NU+2)}┬{'─'*(W_PC+2)}┬{'─'*(W_BR+2)}┬{'─'*(W_AF+2)}┐{RESET}")
    print(
        f"  {GRIS}│{RESET} {NEGRITA}{ajustar_col('#', W_RK, 'der')}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Ubicación', W_UB)}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Incid.', W_NU, 'der')}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('%', W_PC, 'der')}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Gráfico', W_BR)}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Afect.', W_AF, 'der')}{RESET} {GRIS}│{RESET}"
    )
    print(f"  {GRIS}├{'─'*(W_RK+2)}┼{'─'*(W_UB+2)}┼{'─'*(W_NU+2)}┼{'─'*(W_PC+2)}┼{'─'*(W_BR+2)}┼{'─'*(W_AF+2)}┤{RESET}")
    top_ub = agg["ubic_cnt"].most_common(5)
    max_ub = top_ub[0][1] if top_ub else 1
    for idx, (ub, cnt) in enumerate(top_ub, start=1):
        pct = cnt / t_validos * 100
        bar = barra_coloreada(cnt, max_ub, W_BR, AMARILLO)
        print(
            f"  {GRIS}│{RESET} {ajustar_col(idx, W_RK, 'der')} "
            f"{GRIS}│{RESET} {ajustar_col(ub, W_UB)} "
            f"{GRIS}│{RESET} {ajustar_col(cnt, W_NU, 'der')} "
            f"{GRIS}│{RESET} {ajustar_col(f'{pct:.1f}%', W_PC, 'der')} "
            f"{GRIS}│{RESET} {bar} "
            f"{GRIS}│{RESET} {ajustar_col(agg['ubic_imp'][ub], W_AF, 'der')} {GRIS}│{RESET}"
        )
    print(f"  {GRIS}└{'─'*(W_RK+2)}┴{'─'*(W_UB+2)}┴{'─'*(W_NU+2)}┴{'─'*(W_PC+2)}┴{'─'*(W_BR+2)}┴{'─'*(W_AF+2)}┘{RESET}")


def sec_reincidentes(res, agg):
    reincidentes = [(cod, q) for cod, q in agg["inv_cnt"].most_common(5) if q > 1]
    titulo_seccion(7, "EQUIPOS REINCIDENTES (INVENTARIOS CON > 1 INCIDENCIA)")
    W_COD, W_TEQ, W_UBH, W_INC, W_AFP = 14, 17, 22, 6, 6
    print(f"  {GRIS}┌{'─'*(W_COD+2)}┬{'─'*(W_TEQ+2)}┬{'─'*(W_UBH+2)}┬{'─'*(W_INC+2)}┬{'─'*(W_AFP+2)}┐{RESET}")
    print(
        f"  {GRIS}│{RESET} {NEGRITA}{ajustar_col('Código Inv.', W_COD)}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Tipo de Equipo', W_TEQ)}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Ubicación Principal', W_UBH)}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Incid.', W_INC, 'der')}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Afect.', W_AFP, 'der')}{RESET} {GRIS}│{RESET}"
    )
    print(f"  {GRIS}├{'─'*(W_COD+2)}┼{'─'*(W_TEQ+2)}┼{'─'*(W_UBH+2)}┼{'─'*(W_INC+2)}┼{'─'*(W_AFP+2)}┤{RESET}")
    if reincidentes:
        for cod, q in reincidentes:
            eq_p = agg["inv_eq"][cod].most_common(1)[0][0]
            ub_p = agg["inv_ub"][cod].most_common(1)[0][0]
            print(
                f"  {GRIS}│{RESET} {ROJO}{ajustar_col(cod, W_COD)}{RESET} "
                f"{GRIS}│{RESET} {ajustar_col(eq_p, W_TEQ)} "
                f"{GRIS}│{RESET} {ajustar_col(ub_p, W_UBH)} "
                f"{GRIS}│{RESET} {ROJO}{ajustar_col(q, W_INC, 'der')}{RESET} "
                f"{GRIS}│{RESET} {ajustar_col(agg['inv_afe'][cod], W_AFP, 'der')} {GRIS}│{RESET}"
            )
    else:
        print(f"  {GRIS}│{RESET} {GRIS}{ajustar_col('No se han detectado códigos de inventario reincidentes.', ANCHO_CAJA - 4)}{RESET} {GRIS}│{RESET}")
    print(f"  {GRIS}└{'─'*(W_COD+2)}┴{'─'*(W_TEQ+2)}┴{'─'*(W_UBH+2)}┴{'─'*(W_INC+2)}┴{'─'*(W_AFP+2)}┘{RESET}")


def sec_mensual(res, agg):
    t_validos = len(res["validos"])
    mes_cnt, mes_imp = agg["mes_cnt"], agg["mes_imp"]
    W_MS, W_MI, W_MP, W_MB, W_MA = 10, 7, 7, 33, 8
    titulo_seccion(8, "EVOLUCIÓN MENSUAL DE INCIDENCIAS")
    print(f"  {GRIS}┌{'─'*(W_MS+2)}┬{'─'*(W_MI+2)}┬{'─'*(W_MP+2)}┬{'─'*(W_MB+2)}┬{'─'*(W_MA+2)}┐{RESET}")
    print(
        f"  {GRIS}│{RESET} {NEGRITA}{ajustar_col('Mes', W_MS)}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Incid.', W_MI, 'der')}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('%', W_MP, 'der')}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Tendencia Temporal', W_MB)}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Afect.', W_MA, 'der')}{RESET} {GRIS}│{RESET}"
    )
    print(f"  {GRIS}├{'─'*(W_MS+2)}┼{'─'*(W_MI+2)}┼{'─'*(W_MP+2)}┼{'─'*(W_MB+2)}┼{'─'*(W_MA+2)}┤{RESET}")
    max_mes = max(mes_cnt.values()) if mes_cnt else 1
    for mes, cnt in sorted(mes_cnt.items()):
        pct = cnt / t_validos * 100
        bar = barra_coloreada(cnt, max_mes, W_MB, AZUL)
        print(
            f"  {GRIS}│{RESET} {ajustar_col(mes, W_MS)} "
            f"{GRIS}│{RESET} {ajustar_col(cnt, W_MI, 'der')} "
            f"{GRIS}│{RESET} {ajustar_col(f'{pct:.1f}%', W_MP, 'der')} "
            f"{GRIS}│{RESET} {bar} "
            f"{GRIS}│{RESET} {ajustar_col(mes_imp[mes], W_MA, 'der')} {GRIS}│{RESET}"
        )
    print(f"  {GRIS}└{'─'*(W_MS+2)}┴{'─'*(W_MI+2)}┴{'─'*(W_MP+2)}┴{'─'*(W_MB+2)}┴{'─'*(W_MA+2)}┘{RESET}")


def sec_tecnicos(res, agg):
    t_validos = len(res["validos"])
    W_TR, W_TN, W_TI, W_TP, W_TA = 2, 38, 7, 7, 11
    titulo_seccion(9, "TÉCNICOS CON MAYOR CARGA (CONTACTOS VÁLIDOS)")
    print(f"  {GRIS}┌{'─'*(W_TR+2)}┬{'─'*(W_TN+2)}┬{'─'*(W_TI+2)}┬{'─'*(W_TP+2)}┬{'─'*(W_TA+2)}┐{RESET}")
    print(
        f"  {GRIS}│{RESET} {NEGRITA}{ajustar_col('#', W_TR, 'der')}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Técnico / Contacto', W_TN)}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Incid.', W_TI, 'der')}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('%', W_TP, 'der')}{RESET} "
        f"{GRIS}│{RESET} {NEGRITA}{ajustar_col('Afectados', W_TA, 'der')}{RESET} {GRIS}│{RESET}"
    )
    print(f"  {GRIS}├{'─'*(W_TR+2)}┼{'─'*(W_TN+2)}┼{'─'*(W_TI+2)}┼{'─'*(W_TP+2)}┼{'─'*(W_TA+2)}┤{RESET}")
    for idx, (nom, cnt) in enumerate(agg["tec_cnt"].most_common(5), start=1):
        pct = cnt / t_validos * 100
        print(
            f"  {GRIS}│{RESET} {ajustar_col(idx, W_TR, 'der')} "
            f"{GRIS}│{RESET} {ajustar_col(nom, W_TN)} "
            f"{GRIS}│{RESET} {ajustar_col(cnt, W_TI, 'der')} "
            f"{GRIS}│{RESET} {ajustar_col(f'{pct:.1f}%', W_TP, 'der')} "
            f"{GRIS}│{RESET} {ajustar_col(agg['tec_imp'][nom], W_TA, 'der')} {GRIS}│{RESET}"
        )
    print(f"  {GRIS}└{'─'*(W_TR+2)}┴{'─'*(W_TN+2)}┴{'─'*(W_TI+2)}┴{'─'*(W_TP+2)}┴{'─'*(W_TA+2)}┘{RESET}")
    print(
        f"  {GRIS}  Estado de asignación -> Sin asignar: {AMARILLO}{agg['sin_asignar']}{GRIS} | "
        f"Contactos corruptos/ilegibles filtrados: {ROJO}{res['tecnicos_corruptos']}{RESET}"
    )


def informe_completo(res, agg):
    sec_auditoria(res, agg)
    sec_kpis(res, agg)
    sec_categorias(res, agg)
    sec_equipos(res, agg)
    sec_departamentos(res, agg)
    sec_ubicaciones(res, agg)
    sec_reincidentes(res, agg)
    sec_mensual(res, agg)
    sec_tecnicos(res, agg)


# ----------------------------------------------------------------------------
# LOCALIZACIÓN DEL XML (según la estructura data/ + src/)
# ----------------------------------------------------------------------------
def localizar_xml():
    """
    Localiza incidencies.xml usando la ubicación de este script, no el
    directorio actual de la terminal.

    Prioridad:
    1. Ruta indicada como argumento.
    2. data/incidencies.xml en la raíz del proyecto (carpeta padre de src/).
    3. incidencies.xml en la raíz del proyecto o junto al script.
    """
    carpeta_script = Path(__file__).resolve().parent
    raiz_proyecto = carpeta_script.parent
    carpeta_data = raiz_proyecto / "data"

    if len(sys.argv) > 1:
        ruta_argumento = Path(sys.argv[1]).expanduser()
        if ruta_argumento.is_file():
            return ruta_argumento.resolve()
        desde_proyecto = raiz_proyecto / ruta_argumento
        if desde_proyecto.is_file():
            return desde_proyecto.resolve()
        nombre = ruta_argumento.name
        for candidato in (carpeta_data / nombre, raiz_proyecto / nombre, carpeta_script / nombre):
            if candidato.is_file():
                return candidato.resolve()
        raise FileNotFoundError(f"No se encuentra la ruta indicada: {sys.argv[1]}")

    nombres = ("incidencies.xml", "Incidencies.xml", "incidencias.xml", "Incidencias.xml")
    candidatos = [carpeta_data / n for n in nombres]
    candidatos += [raiz_proyecto / n for n in nombres]
    candidatos += [carpeta_script / n for n in nombres]

    for candidato in candidatos:
        if candidato.is_file():
            return candidato.resolve()

    rutas_probadas = "\n".join(f"  - {ruta}" for ruta in candidatos[:4])
    raise FileNotFoundError(
        "No se ha encontrado el archivo XML. Rutas comprobadas:\n"
        f"{rutas_probadas}\n"
        "Comprueba que data/incidencies.xml existe o ejecuta primero csv_to_xml.py."
    )


# ----------------------------------------------------------------------------
# MENÚ INTERACTIVO
# ----------------------------------------------------------------------------
def generar_matriz_qr(url):
    """Devuelve la matriz del QR (lista de listas de bool, True = módulo oscuro).
    Requiere la librería 'qrcode':  pip install qrcode"""
    import qrcode  # import perezoso: el resto del programa funciona sin ella
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        border=0,
    )
    qr.add_data(url)
    qr.make(fit=True)
    return qr.get_matrix()


def renderizar_qr(matriz, borde=2):
    """Convierte la matriz en líneas de texto usando medios bloques (▀ ▄ █).
    Cada carácter equivale a 2 filas del QR, así queda cuadrado en consola.
    Se pinta negro sobre fondo blanco (con zona de silencio) para que sea
    legible también en terminales con tema oscuro."""
    n = len(matriz)
    total = n + 2 * borde
    # Matriz con borde blanco (False = claro)
    g = [[False] * total for _ in range(total)]
    for y in range(n):
        for x in range(n):
            g[y + borde][x + borde] = bool(matriz[y][x])
    if total % 2:                      # número par de filas para emparejar
        g.append([False] * total)

    lineas = []
    for y in range(0, len(g), 2):
        fila = ""
        for x in range(total):
            arriba, abajo = g[y][x], g[y + 1][x]
            if arriba and abajo:
                fila += "█"
            elif arriba:
                fila += "▀"
            elif abajo:
                fila += "▄"
            else:
                fila += " "
        lineas.append(f"\033[30;107m{fila}{RESET}")
    return lineas


def mostrar_qr(url=URL_WEB):
    """Muestra en consola el código QR de la web del proyecto."""
    try:
        matriz = generar_matriz_qr(url)
    except ImportError:
        print(f"\n  {AMARILLO}[!] Falta la librería 'qrcode'. Instálala con:{RESET}")
        print(f"      {BLANCO}pip install qrcode{RESET}")
        print(f"  {GRIS}    (o: python -m pip install qrcode){RESET}")
        return
    except Exception as err:
        print(f"\n  {ROJO}[-] No se pudo generar el QR: {err}{RESET}")
        return

    lineas = renderizar_qr(matriz)
    print(f"\n  {NEGRITA}{CIAN}CÓDIGO QR DE LA WEB DEL PROYECTO{RESET}\n")
    for ln in lineas:
        print(f"      {ln}")
    print(f"\n  {GRIS}Escanéalo con el móvil  ->  {url}{RESET}")


def abrir_qr(*_):
    """Opción de menú: solo muestra el QR."""
    mostrar_qr()


def abrir_web(*_):
    """Abre la web del proyecto en el navegador y muestra su QR."""
    print(f"\n  {CIAN}[>] Abriendo la web del proyecto...{RESET}")
    print(f"  {GRIS}    {URL_WEB}{RESET}")
    try:
        ok = webbrowser.open(URL_WEB, new=2)
    except Exception:
        ok = False
    if ok:
        print(f"  {VERDE}[✔] Web abierta en tu navegador.{RESET}")
    else:
        print(f"  {AMARILLO}[!] No se pudo abrir el navegador. Copia el enlace de arriba.{RESET}")
    mostrar_qr()


def dibujar_menu(estado, ruta_xml):
    """Dibuja el menú principal con estilo de tarjeta."""
    limpiar_pantalla()
    res = estado["res"]
    sub = f"Fuente: {os.path.basename(ruta_xml)}   |   Fecha: {HOY.strftime('%d/%m/%Y %H:%M')}"
    banner(sub)

    # Mini-resumen de estado
    t_val = len(res["validos"])
    pct = (t_val / res["total_leidos"] * 100) if res["total_leidos"] else 0
    barra = barra_coloreada(t_val, res["total_leidos"], 20, VERDE)
    print(
        f"\n  {GRIS}Datos cargados:{RESET} {BLANCO}{res['total_leidos']}{RESET} leídos  "
        f"{GRIS}|{RESET} {VERDE}{t_val}{RESET} válidos  "
        f"{GRIS}|{RESET} {ROJO}{sum(res['motivos_descarte'].values())}{RESET} descartados   {barra} {pct:.0f}%"
    )

    ancho_int = ANCHO_CAJA - 2
    print(f"\n  {GRIS}┌{'─' * ancho_int}┐{RESET}")
    print(f"  {GRIS}│{RESET} {NEGRITA}{ajustar_col('MENÚ PRINCIPAL  -  elige una opción', ancho_int - 2)}{RESET} {GRIS}│{RESET}")
    print(f"  {GRIS}├{'─' * ancho_int}┤{RESET}")
    for clave, color, nombre, desc, _ in OPCIONES:
        linea = (
            f"{color}{NEGRITA}[{clave:>2}]{RESET} "
            f"{BLANCO}{ajustar_col(nombre, 28)}{RESET} "
            f"{GRIS}{ajustar_col(desc, 43)}{RESET}"
        )
        print(f"  {GRIS}│{RESET} {linea} {GRIS}│{RESET}")
    print(f"  {GRIS}├{'─' * ancho_int}┤{RESET}")
    salir = f"{ROJO}{NEGRITA}[ 0]{RESET} {BLANCO}{ajustar_col('Salir', 28)}{RESET} {GRIS}{ajustar_col('Cerrar el panel', 43)}{RESET}"
    print(f"  {GRIS}│{RESET} {salir} {GRIS}│{RESET}")
    print(f"  {GRIS}└{'─' * ancho_int}┘{RESET}")


def recargar(estado, ruta_xml):
    """Vuelve a leer y procesar el XML."""
    print(f"\n  {CIAN}[i] Releyendo {ruta_xml.name}...{RESET}")
    estado["res"] = procesar_xml(str(ruta_xml))
    estado["agg"] = calcular_agregaciones(estado["res"]) if estado["res"]["validos"] else None
    print(f"  {VERDE}[✔] Datos recargados: {len(estado['res']['validos'])} registros válidos.{RESET}")


# (tecla, color, nombre, descripción, función)  -> la ÚLTIMA es la web
OPCIONES = [
    ("1", VERDE,    "Informe completo",          "Todas las secciones seguidas",        informe_completo),
    ("2", CIAN,     "Auditoría de calidad",      "Leídos, válidos, descartados",        sec_auditoria),
    ("3", AMARILLO, "Resumen ejecutivo (KPIs)",  "Total, media, mediana y rango",       sec_kpis),
    ("4", VERDE,    "Categorías de avería",      "Hardware, Software, Xarxa...",        sec_categorias),
    ("5", CIAN,     "Tipos de equipo",           "Ordinador, Impressora, Monitor...",   sec_equipos),
    ("6", MAGENTA,  "Departamentos",             "Incidencias por departamento",        sec_departamentos),
    ("7", AMARILLO, "Top ubicaciones",           "Aulas/salas con más problemas",       sec_ubicaciones),
    ("8", ROJO,     "Equipos reincidentes",      "Inventarios con varias incidencias",  sec_reincidentes),
    ("9", AZUL,     "Evolución mensual",         "Tendencia por mes",                   sec_mensual),
    ("10", MAGENTA, "Técnicos",                  "Carga de trabajo por técnico",        sec_tecnicos),
    ("11", GRIS,    "Recargar datos",            "Vuelve a leer el XML",                "RECARGAR"),
    ("12", CIAN,    "Código QR de la web",       "Escanéalo con el móvil",              "QR"),
    ("13", BLANCO,  "Abrir la web del proyecto", "Te lleva a la página en GitHub Pages", "WEB"),
]


def menu_interactivo(ruta_xml):
    estado = {"res": procesar_xml(str(ruta_xml)), "agg": None}
    if estado["res"]["validos"]:
        estado["agg"] = calcular_agregaciones(estado["res"])
    acciones = {clave: fn for clave, _, _, _, fn in OPCIONES}

    while True:
        dibujar_menu(estado, ruta_xml.name)
        try:
            eleccion = input(f"\n  {NEGRITA}{CIAN}Opción >{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            eleccion = "0"

        if eleccion in ("0", "q", "Q", "salir"):
            print(f"\n  {VERDE}Hasta pronto 👋{RESET}\n")
            break

        accion = acciones.get(eleccion)
        if accion is None:
            print(f"\n  {ROJO}[!] Opción no válida. Elige un número del menú.{RESET}")
            pausa()
            continue

        limpiar_pantalla()
        if accion == "WEB":
            abrir_web()
        elif accion == "QR":
            abrir_qr()
        elif accion == "RECARGAR":
            recargar(estado, ruta_xml)
        elif estado["agg"] is None:
            banner()
            print(f"\n  {ROJO}[!] No hay registros válidos para analizar.{RESET}")
            if eleccion == "2":  # la auditoría sí se puede ver sin datos válidos
                accion(estado["res"], None)
        else:
            banner()
            accion(estado["res"], estado["agg"])
        pausa()


if __name__ == "__main__":
    try:
        archivo_xml = localizar_xml()
        print(f"{GRIS}[i] Leyendo XML: {archivo_xml}{RESET}")
        menu_interactivo(archivo_xml)
    except FileNotFoundError as err:
        print(f"{ROJO}[-] Error: {err}{RESET}")
        sys.exit(1)
    except ET.ParseError as err:
        print(f"{ROJO}[-] Error de sintaxis en el XML: {err}{RESET}")
        sys.exit(1)