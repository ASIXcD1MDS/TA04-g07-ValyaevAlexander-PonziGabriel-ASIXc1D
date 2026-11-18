#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CONVERSOR DE CSV A XML - INCIDÈNCIES TIC (ASIXcD TA04 - Part 2)

Fitxer: src/csv_to_xml.py
Descripció: Llegeix el fitxer 'data/incidencies.csv' i genera un document XML
            estructurat i formatat 'data/incidencies.xml'.
"""

import csv
import os
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom


def netejar_nom_etiqueta(text):
    """
    Normalitza els títols de les columnes del CSV per convertir-los
    en etiquetes XML vàlides.
    """
    mapa_caracters = {
        'à': 'a', 'è': 'e', 'é': 'e', 'í': 'i', 'ò': 'o', 'ó': 'o', 'ú': 'u', 'ü': 'u',
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ç': 'c', 'ñ': 'n',
        ' ': '_', '.': '', '/': '_', '-': '_', '(': '', ')': '', '?': '', "'": ''
    }
    text_net = text.strip().lower()
    for origen, desti in mapa_caracters.items():
        text_net = text_net.replace(origen, desti)
    text_net = re.sub(r'[^a-z0-9_]', '', text_net)
    text_net = re.sub(r'_+', '_', text_net).strip('_')
    if not text_net or text_net[0].isdigit():
        text_net = f"camp_{text_net}"
    return text_net


def csv_a_xml(fitxer_csv, fitxer_xml):
    """Converteix les files del CSV en un document XML indentat."""
    if not os.path.exists(fitxer_csv):
        print(f"[-] Error: No s'ha trobat el fitxer '{fitxer_csv}'.")
        return

    os.makedirs(os.path.dirname(fitxer_xml) or ".", exist_ok=True)
    arrel = ET.Element("incidencies")

    with open(fitxer_csv, mode="r", encoding="utf-8-sig", newline="") as f:
        lector = csv.reader(f)
        capcaleres = next(lector, None)
        if not capcaleres:
            print(f"[-] Error: El fitxer '{fitxer_csv}' està buit.")
            return

        etiquetes = [netejar_nom_etiqueta(col) for col in capcaleres]

        for idx, fila in enumerate(lector, start=1):
            if not any(celda.strip() for celda in fila):
                continue
            incidencia = ET.SubElement(arrel, "incidencia", id=str(idx))
            for etiqueta, valor in zip(etiquetes, fila):
                node = ET.SubElement(incidencia, etiqueta)
                node.text = valor.strip()

    xml_en_brut = ET.tostring(arrel, encoding="utf-8")
    xml_formatat = minidom.parseString(xml_en_brut).toprettyxml(
        indent="    ", encoding="utf-8"
    )

    with open(fitxer_xml, mode="wb") as f_out:
        f_out.write(xml_formatat)

    print(f"[+] Conversió finalitzada amb èxit. Fitxer '{fitxer_xml}' generat correctament.")


if __name__ == "__main__":
    ruta_csv = "data/incidencies.csv" if os.path.exists("data/incidencies.csv") else "data/Incidencies.csv"
    ruta_xml = "data/incidencies.xml"
    csv_a_xml(ruta_csv, ruta_xml)