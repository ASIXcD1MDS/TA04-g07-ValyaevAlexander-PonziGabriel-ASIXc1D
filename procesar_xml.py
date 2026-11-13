#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
PROCESAMIENTO Y ANÁLISIS DE INCIDENCIAS XML (ASIXc TA04 - Parte 3)
==============================================================================
Archivo: procesar_xml.py
Descripción: Lee el archivo 'incidencies.xml' de manera eficiente (iterparse),
             filtra y limpia registros erróneos o anómalos (p. ej. año 2064),
             calcula estadísticas significativas y las muestra por pantalla
             con colores ANSI, tablas alineadas y barras visuales.
==============================================================================
"""

import base64
import html
import os
import re
import statistics
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime

# Códigos de color ANSI para la consola
VERDE = "\033[92m"
ROJO = "\033[91m"
AMARILLO = "\033[93m"
AZUL = "\033[94m"
CIAN = "\033[96m"
MAGENTA = "\033[95m"
NEGRITA = "\033[1m"
GRIS = "\033[90m"
RESET = "\033[0m"

# Parámetros de validación y calidad de datos
ANIO_MINIMO = 2020
HOY = datetime.now()
MAX_USUARIOS_AFECTADOS = 500
VALORES_BASURA = {
    "test", "prova", "prueba", "asdf", "qwerty",
    "xxx", "none", "null", "nan", "n/a", "na"
}

# Mapas de normalización basados en las opciones del formulario
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
    "altres": "Altres", "otros": "Altres"
}

MAPA_EQUIP = {
    "ordinador": "Ordinador", "ordenador": "Ordinador", "pc": "Ordinador",
    "impressora": "Impressora", "impresora": "Impressora",
    "monitor": "Monitor",
    "projector": "Projector", "proyector": "Projector",
    "altres": "Altres", "otros": "Altres"
}

MAPA_CAT = {
    "hardware": "Hardware",
    "software": "Software",
    "xarxa": "Xarxa", "red": "Xarxa",
    "perifèrics": "Perifèrics", "periferics": "Perifèrics",
    "periféricos": "Perifèrics", "perifericos": "Perifèrics",
    "no identificat": "No identificat", "no identificado": "No identificat",
    "altres": "Altres", "otros": "Altres"
}


def limpiar_texto(valor, decodificar=True):
    """Limpia ruido (comillas, signos repetidos) y decodifica texto ofuscado."""
    if not valor:
        return ""
    texto = valor.strip()

    if decodificar:
        # 1. Entidades HTML (ej: &#73;&#78;&#86;...)
        if "&#" in texto or "&amp;" in texto:
            texto = html.unescape(html.unescape(texto))

        # 2. Secuencias Unicode escapadas (ej: \u062c...)
        if "\\u" in texto:
            texto = re.sub(
                r'\\u([0-9a-fA-F]{4})',
                lambda m: chr(int(m.group(1), 16)),
                texto
            )

        # 3. Cadena binaria de 8 bits separada por espacios
        if re.fullmatch(r'(?:[01]{8}\s*){3,}', texto):
            try:
                bits = texto.replace(" ", "")
                decodificado = "".join(
                    chr(int(bits[i:i + 8], 2)) for i in range(0, len(bits), 8)
                )
                if decodificado.isprintable():
                    texto = decodificado
            except Exception:
                pass
        # 4. Hexadecimal separado por espacios (ej: 41 75 6c 61 -> Aula)
        elif re.fullmatch(r'(?:[0-9a-fA-F]{2}\s+){2,}[0-9a-fA-F]{2}', texto):
            try:
                decodificado = bytes.fromhex(texto.replace(" ", "")).decode(
                    "utf-8", errors="ignore"
                )
                if decodificado and decodificado.isprintable():
                    texto = decodificado
            except Exception:
                pass
        # 5. Base64 simple (ej: U2FsYSAwLjEx -> Sala 0.11)
        elif (
            len(texto) % 4 == 0
            and re.fullmatch(r'[A-Za-z0-9+/]{8,}={0,2}', texto)
            and " " not in texto
            and not texto.upper().startswith(("INV", "EQ"))
        ):
            try:
                decodificado = base64.b64decode(texto, validate=True).decode("utf-8")
                if decodificado and decodificado.isprintable() and any(c.isalpha() for c in decodificado):
                    texto = decodificado
            except Exception:
                pass

    texto = re.sub(r'["]+', '', texto)
    texto = re.sub(r'[;\\<>]+', ' ', texto)
    texto = re.sub(r'!{2,}', '', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto


def es_basura(texto):
    """Comprueba si un campo obligatorio está vacío, contiene solo emojis/símbolos o basura."""
    if not texto:
        return True
    if not any(c.isalnum() for c in texto):
        return True
    if texto.lower() in VALORES_BASURA:
        return True
    return False


def parsear_fecha(texto_fecha):
    """Intenta convertir una cadena a datetime probando formatos habituales."""
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texto_fecha.strip(), fmt)
        except ValueError:
            continue
    return None


def normalizar_categoria(texto, mapa):
    """Unifica mayúsculas/minúsculas y acentos según el diccionario canónico."""
    clave = texto.strip().lower()
    return mapa.get(clave, texto.strip().capitalize())


def normalizar_ubicacion(texto):
    """Normaliza ubicaciones como 'lAbOrAtOrI 1.11' a 'Laboratori 1.11'."""
    partes = texto.strip().split()
    return " ".join(
        p.capitalize() if any(c.isalpha() for c in p) else p for p in partes
    )


def normalizar_inventario(texto):
    """Estandariza códigos de inventario (ej: 'INV 86813' -> 'INV-86813')."""
    t = texto.upper().strip()
    return re.sub(r'^(INV|EQ)\s+(\d+)$', r'\1-\2', t)


def obtener_campo(elem, candidatos):
    """Busca el valor de un nodo hijo probando varios nombres de etiqueta posibles."""
    for tag in candidatos:
        nodo = elem.find(tag)
        if nodo is not None and nodo.text is not None:
            return nodo.text
    for hijo in elem:
        for cand in candidatos:
            if cand in hijo.tag.lower() and hijo.text is not None:
                return hijo.text
    return ""


def barra_progreso(valor, maximo, ancho=22, color=CIAN):
    """Genera una barra horizontal proporcional para la consola."""
    if maximo <= 0:
        return ""
    llenos = round((valor / maximo) * ancho)
    return f"{color}{'█' * llenos}{GRIS}{'░' * (ancho - llenos)}{RESET}"


def procesar_xml(ruta_xml):
    """Lee el XML en streaming, filtra errores y devuelve datos limpios y métricas."""
    total_leidos = 0
    validos = []
    motivos_descarte = Counter()
    ejemplos_descarte = []
    vistos = set()

    for _, elem in ET.iterparse(ruta_xml, events=("end",)):
        if elem.tag == "incidencia":
            total_leidos += 1
            id_reg = elem.attrib.get("id", str(total_leidos))

            data_raw = limpiar_texto(
                obtener_campo(elem, ["data_de_la_incidencia", "data"]),
                decodificar=False
            )
            usuario = limpiar_texto(obtener_campo(elem, ["usuari_afectat", "usuari"]))
            dep = limpiar_texto(obtener_campo(elem, ["departament"]))
            equip = limpiar_texto(obtener_campo(elem, ["tipus_dequip", "tipus_equip", "equip"]))
            ubicacion = limpiar_texto(obtener_campo(elem, ["ubicacio"]))
            inventario = limpiar_texto(
                obtener_campo(elem, ["numero_dinventari", "num_inventari", "inventari"])
            )
            categoria = limpiar_texto(
                obtener_campo(elem, ["categoria_de_lavaria", "categoria_avaria", "categoria"])
            )
            descripcion = limpiar_texto(
                obtener_campo(elem, ["descripcio_de_la_incidencia", "descripcio"])
            )
            afectados_raw = limpiar_texto(
                obtener_campo(elem, ["usuaris_afectats", "afectats"]),
                decodificar=False
            )
            tecnico = limpiar_texto(
                obtener_campo(elem, ["contacte_del_tecnic_assignat", "contacte_tecnic", "tecnic"])
            )

            # Fase de validación y filtrado
            dt = parsear_fecha(data_raw)
            motivo = None

            if dt is None:
                motivo = "Fecha inválida o vacía"
            elif dt.year > HOY.year:
                motivo = f"Fecha futura anómala (año {dt.year})"
            elif dt > HOY:
                motivo = "Fecha futura (posterior a hoy)"
            elif dt.year < ANIO_MINIMO:
                motivo = f"Fecha demasiado antigua (< {ANIO_MINIMO})"
            else:
                try:
                    num_afectados = int(afectados_raw)
                    if not (1 <= num_afectados <= MAX_USUARIOS_AFECTADOS):
                        raise ValueError
                except ValueError:
                    motivo = "Usuarios afectados no numérico o fuera de rango (1..500)"

            if not motivo and any(
                es_basura(c) for c in (dep, equip, ubicacion, inventario, categoria, descripcion)
            ):
                motivo = "Campos obligatorios vacíos o con ruido/emojis"

            if not motivo:
                dep_n = normalizar_categoria(dep, MAPA_DEP)
                equip_n = normalizar_categoria(equip, MAPA_EQUIP)
                cat_n = normalizar_categoria(categoria, MAPA_CAT)
                ubic_n = normalizar_ubicacion(ubicacion)
                inv_n = normalizar_inventario(inventario)

                clave = (dt.strftime("%Y-%m-%d"), inv_n, cat_n, descripcion.lower())
                if clave in vistos:
                    motivo = "Registro duplicado"
                else:
                    vistos.add(clave)

            if motivo:
                motivos_descarte[motivo] += 1
                if len(ejemplos_descarte) < 5:
                    ejemplos_descarte.append((id_reg, motivo, data_raw or "-"))
            else:
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
                    "tecnico": tecnico or "Sin asignar"
                })

            # Liberar memoria del nodo XML procesado
            elem.clear()

    return total_leidos, validos, motivos_descarte, ejemplos_descarte


def mostrar_tabla(titulo, contador, total, impacto=None, limite=None, color=CIAN):
    """Imprime una tabla formateada con porcentajes y gráfico de barras."""
    print(f"\n{NEGRITA}{AZUL}▸ {titulo}{RESET}")
    cab = f"  {'Elemento':<24} {'Incid.':>7} {'%':>7}  {'Gráfico':<22}"
    sep = f"  {'-' * 24} {'-' * 7} {'-' * 7}  {'-' * 22}"
    if impacto is not None:
        cab += f" {'Afectados':>9}"
        sep += f" {'-' * 9}"
    print(cab)
    print(sep)

    items = contador.most_common(limite)
    max_val = items[0][1] if items else 1

    for nombre, qtd in items:
        pct = (qtd / total * 100) if total else 0
        nombre_corto = (nombre[:21] + "...") if len(nombre) > 24 else nombre
        linea = (
            f"  {nombre_corto:<24} {qtd:>7} {pct:>6.1f}%  "
            f"{barra_progreso(qtd, max_val, 22, color)}"
        )
        if impacto is not None:
            linea += f" {impacto[nombre]:>9}"
        print(linea)


def mostrar_informe(total_leidos, validos, descarte, ejemplos):
    """Presenta el informe estadístico completo por pantalla."""
    t_validos = len(validos)
    t_descarte = sum(descarte.values())
    pct_validos = (t_validos / total_leidos * 100) if total_leidos else 0

    print(f"\n{NEGRITA}{CIAN}{'=' * 74}{RESET}")
    print(f"{NEGRITA}{CIAN}   INFORME DE ANÁLISIS DE INCIDENCIAS TIC Y AUDIOVISUALES (ASIXc TA04){RESET}")
    print(f"{NEGRITA}{CIAN}{'=' * 74}{RESET}")

    # 1. Resumen de calidad y filtrado
    print(f"\n{NEGRITA}{AZUL}▸ AUDITORÍA Y CALIDAD DE DATOS{RESET}")
    print(
        f"  Total registros leídos  : {NEGRITA}{total_leidos}{RESET}\n"
        f"  Registros válidos       : {VERDE}{NEGRITA}{t_validos} ({pct_validos:.1f}%){RESET}\n"
        f"  Registros descartados   : {ROJO}{NEGRITA}{t_descarte}{RESET}"
    )

    if descarte:
        print(f"\n  {AMARILLO}Motivos de descarte aplicados:{RESET}")
        for motivo, qtd in descarte.most_common():
            print(f"   • {motivo:<48} {ROJO}{qtd:>5}{RESET}")
        if ejemplos:
            print(f"  {GRIS}Muestra de registros descartados:{RESET}")
            for id_r, m, d in ejemplos:
                print(f"   {GRIS}  - ID #{id_r} | Fecha: '{d}' -> {m}{RESET}")

    if t_validos == 0:
        print(f"\n{ROJO}[!] No hay registros válidos para generar estadísticas.{RESET}\n")
        return

    # 2. Métricas de impacto en usuarios
    afectados = [r["usuarios_afectados"] for r in validos]
    print(f"\n{NEGRITA}{AZUL}▸ IMPACTO GLOBAL EN USUARIOS{RESET}")
    print(
        f"  Total usuarios afectados : {NEGRITA}{sum(afectados)}{RESET}\n"
        f"  Media por incidencia     : {statistics.mean(afectados):.2f} | "
        f"Mediana: {statistics.median(afectados):.1f} | "
        f"Mín: {min(afectados)} | Máx: {max(afectados)}"
    )

    # 3. Tablas de distribución por dimensiones principales
    cat_cnt = Counter(r["categoria"] for r in validos)
    cat_imp = defaultdict(int)
    eq_cnt = Counter(r["tipo_equipo"] for r in validos)
    eq_imp = defaultdict(int)
    dep_cnt = Counter(r["departamento"] for r in validos)
    dep_imp = defaultdict(int)

    for r in validos:
        cat_imp[r["categoria"]] += r["usuarios_afectados"]
        eq_imp[r["tipo_equipo"]] += r["usuarios_afectados"]
        dep_imp[r["departamento"]] += r["usuarios_afectados"]

    mostrar_tabla("DISTRIBUCIÓN POR CATEGORÍA DE AVERÍA", cat_cnt, t_validos, cat_imp, color=VERDE)
    mostrar_tabla("DISTRIBUCIÓN POR TIPO DE EQUIPO", eq_cnt, t_validos, eq_imp, color=CIAN)
    mostrar_tabla("INCIDENCIAS POR DEPARTAMENTO", dep_cnt, t_validos, dep_imp, color=MAGENTA)

    # 4. Top ubicaciones críticas
    ubic_cnt = Counter(r["ubicacion"] for r in validos)
    mostrar_tabla("TOP 5 UBICACIONES CON MÁS INCIDENCIAS", ubic_cnt, t_validos, limite=5, color=AMARILLO)

    # 5. Equipos reincidentes (más de una incidencia)
    inv_cnt = Counter(r["inventario"] for r in validos)
    reincidentes = [(cod, qtd) for cod, qtd in inv_cnt.most_common(5) if qtd > 1]
    print(f"\n{NEGRITA}{AZUL}▸ EQUIPOS REINCIDENTES (> 1 incidencia){RESET}")
    if reincidentes:
        for cod, qtd in reincidentes:
            print(f"   • {NEGRITA}{cod:<15}{RESET} -> {ROJO}{qtd} incidencias registradas{RESET}")
    else:
        print(f"   {GRIS}No se han detectado equipos reincidentes en el conjunto válido.{RESET}")

    # 6. Evolución mensual y carga por técnico
    mes_cnt = Counter(r["fecha"].strftime("%Y-%m") for r in validos)
    print(f"\n{NEGRITA}{AZUL}▸ EVOLUCIÓN MENSUAL DE INCIDENCIAS{RESET}")
    max_mes = max(mes_cnt.values())
    for mes, qtd in sorted(mes_cnt.items()):
        print(f"  {mes:<10} {qtd:>5} incid.  {barra_progreso(qtd, max_mes, 20, AZUL)}")

    tec_cnt = Counter(r["tecnico"] for r in validos)
    sin_asignar = tec_cnt.get("Sin asignar", 0)
    print(f"\n{NEGRITA}{AZUL}▸ GESTIÓN DE TÉCNICOS (TOP 5){RESET}")
    for nombre, qtd in tec_cnt.most_common(5):
        etiqueta = f"{AMARILLO}{nombre}{RESET}" if nombre == "Sin asignar" else nombre
        print(f"   • {etiqueta:<35} {qtd:>5} incidencias")
    print(f"  {GRIS}(Total incidencias pendientes de asignación de técnico: {sin_asignar}){RESET}")

    print(f"\n{CIAN}{'=' * 74}{RESET}\n")


if __name__ == "__main__":
    # Acepta el archivo por argumento o busca 'incidencies.xml' / 'Incidencies.xml'
    if len(sys.argv) > 1:
        archivo_xml = sys.argv[1]
    elif os.path.exists("incidencies.xml"):
        archivo_xml = "incidencies.xml"
    else:
        archivo_xml = "Incidencies.xml"

    try:
        total, registros_validos, motivos_descarte, ejemplos = procesar_xml(archivo_xml)
        mostrar_informe(total, registros_validos, motivos_descarte, ejemplos)
    except FileNotFoundError:
        print(
            f"{ROJO}[-] Error: No se ha encontrado el archivo '{archivo_xml}'. "
            f"Ejecuta primero 'csv_to_xml.py'.{RESET}"
        )
    except ET.ParseError as err:
        print(f"{ROJO}[-] Error de sintaxis en el archivo XML '{archivo_xml}': {err}{RESET}")