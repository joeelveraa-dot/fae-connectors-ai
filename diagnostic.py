"""
diagnostic.py
-------------
Herramienta de diagnóstico para entender qué hay en el catálogo y
dónde aparece el conector correcto en el ranking.

Uso:
    python diagnostic.py <ruta_a_foto.jpg>
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import requests
import json

META_FILE = Path("catalogo_meta.pkl")
API = "http://localhost:8000/search"

# --------------------------------------------------------------------------
# 1) Estadísticas del catálogo
# --------------------------------------------------------------------------
print("=" * 70)
print("1. ESTADÍSTICAS DEL CATÁLOGO")
print("=" * 70)

meta = pd.read_pickle(META_FILE)
print(f"Total conectores con imagen:    {len(meta)}")
print(f"Con Referencia Comercial:       {meta['Referencia Comercial'].notna().sum()}")
print(f"Con Proveedor:                  {meta['Proveedor'].notna().sum()}")
print(f"Marcados 'Es de FAE = Sí':      {(meta['Es de FAE'] == 'Sí').sum()}")
print(f"\nDistribución por número de terminales:")
print(meta["Terminales"].value_counts(dropna=False).sort_index().to_string())
print(f"\nDistribución por forma:")
print(meta["Formas"].value_counts(dropna=False).to_string())
print(f"\nConector aéreo (circular):")
print(meta["Conector aereo"].value_counts(dropna=False).to_string())

# --------------------------------------------------------------------------
# 2) Candidatos para un conector de 4 terminales redondo/aéreo
# --------------------------------------------------------------------------
print("\n" + "=" * 70)
print("2. CANDIDATOS: conectores de 4 terminales que podrían ser redondos/aéreos")
print("=" * 70)

candidatos = meta[meta["Terminales"] == 4]
print(f"Conectores con 4 terminales: {len(candidatos)}")
print("\nCon info 'Formas' o 'Conector aereo' rellenada:")
con_info = candidatos[
    candidatos["Formas"].notna() | candidatos["Conector aereo"].notna()
]
print(con_info[["ID - Conector catálogo", "Formas", "Conector aereo",
                "Referencia Comercial", "Proveedor", "Descripción"]].to_string(index=False))

# --------------------------------------------------------------------------
# 3) Si nos dan una foto, buscar y ver dónde aparece cada candidato
# --------------------------------------------------------------------------
if len(sys.argv) > 1:
    photo = sys.argv[1]
    print("\n" + "=" * 70)
    print(f"3. BÚSQUEDA con {photo}")
    print("=" * 70)

    with open(photo, "rb") as f:
        r = requests.post(API, files={"file": f}, data={"top_k": 50})
    data = r.json()

    print(f"\nTop 15 resultados:")
    print("-" * 70)
    for i, hit in enumerate(data["results"][:15], 1):
        m = hit["meta"]
        terms = m.get("Terminales")
        forma = m.get("Formas") or "—"
        aereo = m.get("Conector aereo") or "—"
        ref = m.get("Referencia Comercial") or "—"
        es_fae = m.get("Es de FAE") or "—"
        mark = " ⭐" if terms == 4 else ""
        print(f"{i:3d}. ID={hit['id_conector']:5d} sim={hit['similitud']:.4f} "
              f"term={terms!s:>4} forma={forma!s:10s} aereo={aereo!s:5s} "
              f"FAE={es_fae!s:3s} ref={ref}{mark}")

    # posición de cada candidato en el ranking
    ids_top50 = [h["id_conector"] for h in data["results"]]
    print("\nPosición en el ranking top-50 de los candidatos con 4 terminales:")
    for _, row in con_info.iterrows():
        cid = int(row["ID - Conector catálogo"])
        pos = ids_top50.index(cid) + 1 if cid in ids_top50 else None
        if pos:
            print(f"  ID {cid}: puesto #{pos}")
        else:
            print(f"  ID {cid}: fuera del top 50")