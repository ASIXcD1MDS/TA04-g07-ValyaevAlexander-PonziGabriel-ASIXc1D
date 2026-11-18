import requests
# El comando para actualizar la hoja de incidencias: python3 src/descargar_csv.py
# Sustituye TU_ID_DE_HOJA por el ID real extraído de la URL de tu Google Sheet
SHEET_ID = "13k_wY1b8MiIIC0bMz8VGKAokrbbImtXmp7UYrDhnrHM"
url_csv = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

response = requests.get(url_csv)

if response.status_code == 200:
    with open("data/incidencies.csv", "wb") as f:
        f.write(response.content)
    print("[+] Archivo 'data/incidencies.csv' descargado con éxito desde Google Sheets.")
else:
    print(f"[-] Error HTTP {response.status_code}: No se pudo descargar la hoja.")