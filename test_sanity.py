"""
test_sanity.py
--------------
Extrae una imagen aleatoria del Excel, la guarda como PNG y la envía
al endpoint /search para verificar que el sistema funciona.

La imagen extraída DEBERÍA salir como primer resultado con similitud ~1.0
(o muy cerca, dependiendo de compresión/conversión).
"""

import io
import random
import requests
from pathlib import Path
from openpyxl import load_workbook
import pandas as pd

EXCEL = Path("catalogo_conectores_completo (6).xlsx")
API = "http://localhost:8000/search"

wb = load_workbook(EXCEL)
ws = wb["Catálogo Conectores"]
df = pd.read_excel(EXCEL, sheet_name="Catálogo Conectores")

# coger una imagen aleatoria del catálogo
img = random.choice(ws._images)
excel_row = img.anchor._from.row + 1
df_idx = excel_row - 2
conector_id_real = int(df.iloc[df_idx]["ID - Conector catálogo"])

print(f"→ Probando con imagen del conector ID = {conector_id_real}")

# guardar como test_img.png
test_path = Path("test_img.png")
with open(test_path, "wb") as f:
    f.write(img._data())
print(f"→ Imagen guardada en {test_path}")

# enviar al API
with open(test_path, "rb") as f:
    r = requests.post(
        API,
        files={"file": ("test_img.png", f, "image/png")},
        data={"top_k": 5},
    )

print(f"\nStatus: {r.status_code}\n")
data = r.json()
print(f"Query: {data['query_filename']}")
print("-" * 70)
for i, hit in enumerate(data["results"], 1):
    marker = " ← ¡ESTE ES EL REAL!" if hit["id_conector"] == conector_id_real else ""
    ref = hit["meta"].get("Referencia Comercial", "—")
    prov = hit["meta"].get("Proveedor", "—")
    print(f"{i}. ID={hit['id_conector']:5d}  sim={hit['similitud']:.4f}  "
          f"ref={ref!s:20s} prov={prov!s:30s}{marker}")