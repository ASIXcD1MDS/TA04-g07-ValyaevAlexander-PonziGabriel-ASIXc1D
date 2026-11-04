import requests
#El comando para actualizar la hoja de incidencias ***python3 descargar_csv.py***#
# Sustituye TU_ID_DE_HOJA por el ID real extraído de la URL de tu Google Sheets
SHEET_ID = "TU_ID_DE_HOJA"
url_csv = f"https://docs.google.com/spreadsheets/d/13k_wY1b8MiIIC0bMz8VGKAokrbbImtXmp7UYrDhnrHM/export?format=csv"

response = requests.get(url_csv)

if response.status_code == 200:
    with open("incidencies.csv", "wb") as f:
        f.write(response.content)
    print("[+] Archivo 'incidencies.csv' descargado con éxito desde Google Drive.")
else:
    print(f"[-] Error HTTP {response.status_code}: No se pudo descargar la hoja. Revisa los permisos de enlace.")