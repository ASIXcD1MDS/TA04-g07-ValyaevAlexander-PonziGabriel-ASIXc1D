#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
CONVERSOR DE CSV A XML - INCIDÈNCIES TIC (ASIXcD TA04 - Part 2)
==============================================================================
Fitxer: csv_to_xml.py
Descripció: Llegeix el fitxer 'incidencies.csv' i genera un document XML
            estructurat i formatat 'incidencies.xml'.
==============================================================================
"""

import csv
import xml.etree.ElementTree as ET
from xml.dom import minidom


def netejar_nom_etiqueta(text):
    """
    Normalitza els títols de les columnes del CSV per convertir-los
    en etiquetes XML vàlides.
    """
    mapa_caracters = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'à': 'a', 'è': 'e', 'ò': 'o', 'ç': 'c', 'ñ': 'n',
        ' ': '_', '.': '', '/': '_', "'": '', '(': '', ')': '', '*': ''
    }
    text_net = text.strip().lower()
    for origen, desti in mapa_caracters.items():
        text_net = text_net.replace(origen, desti)
    
    # Mantenir només caràcters alfanumèrics i guions baixos
    text_net = ''.join(c for c in text_net if c.isalnum() or c == '_')
    return text_net if text_net else "camp"


def csv_a_xml(fitxer_csv, fitxer_xml):
    arrel = ET.Element("incidencies")

    try:
        with open(fitxer_csv, mode='r', encoding='utf-8') as f_csv:
            lector = csv.DictReader(f_csv)

            for idx, fila in enumerate(lector, start=1):
                incidencia = ET.SubElement(arrel, "incidencia", id=str(idx))

                for clau, valor in fila.items():
                    if clau:
                        etiqueta = netejar_nom_etiqueta(clau)
                        sub_element = ET.SubElement(incidencia, etiqueta)
                        sub_element.text = valor.strip() if valor else ""

        # Generar XML amb indentació (Pretty Print)
        xml_brut = ET.tostring(arrel, encoding='utf-8')
        xml_parsed = minidom.parseString(xml_brut)
        xml_formatat = xml_parsed.toprettyxml(indent="  ")

        with open(fitxer_xml, "w", encoding="utf-8") as f_xml:
            f_xml.write(xml_formatat)

        print(f"[+] Conversió finalitzada amb èxit. Fitxer '{fitxer_xml}' generat correctament.")

    except FileNotFoundError:
        print(f"[-] Error: No s'ha trobat el fitxer '{fitxer_csv}'. Assegura't que està al mateix directori.")
    except Exception as e:
        print(f"[-] Error durant la conversió a XML: {e}")


if __name__ == "__main__":
    csv_a_xml("incidencies.csv", "incidencies.xml")