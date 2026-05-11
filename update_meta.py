"""
update_meta.py
--------------
Actualiza `catalogo_meta.pkl` con los datos del Excel más reciente,
SIN tocar los embeddings (embeddings_b.npz / embeddings_l.npz).

Uso:
    python update_meta.py

Lee los IDs que hay en embeddings_b.npz y se queda con las filas del Excel
correspondientes, preservando el mismo orden que los embeddings.
Así los índices del pickle y del .npz siguen alineados después del update.
"""

from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).parent

# ─── CONFIG ──────────────────────────────────────────────────
# Ajusta esta ruta al Excel más reciente que tengas
EXCEL_PATH = HERE / "catalogo_conectores_completo (8).xlsx"
SHEET_NAME = "Catálogo Conectores"
ID_COLUMN = "ID - Conector catálogo"

EMBEDDINGS_B = HERE / "embeddings_b.npz"
OUT_META = HERE / "catalogo_meta.pkl"
BACKUP_META = HERE / "catalogo_meta.backup.pkl"


def main():
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(
            f"No se encuentra {EXCEL_PATH.name} en {HERE}"
        )
    if not EMBEDDINGS_B.exists():
        raise FileNotFoundError(
            f"No se encuentra {EMBEDDINGS_B.name}. "
            "Lanza build_embeddings.py primero."
        )

    # 1) Backup del pickle anterior (por si acaso)
    if OUT_META.exists():
        import shutil
        shutil.copy(OUT_META, BACKUP_META)
        print(f"✓ Backup creado: {BACKUP_META.name}")

    # 2) Leer los IDs que existen en embeddings (orden fijo)
    data = np.load(EMBEDDINGS_B, allow_pickle=False)
    ids_emb = data["ids"].tolist()
    print(f"✓ IDs en embeddings_b.npz: {len(ids_emb)}")

    # 3) Leer Excel nuevo
    print(f"✓ Leyendo Excel: {EXCEL_PATH.name}")
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME)
    print(f"  filas en Excel: {len(df)}")
    print(f"  columnas: {list(df.columns)}")

    # Filtrar/ordenar según los IDs de embeddings
    df[ID_COLUMN] = pd.to_numeric(df[ID_COLUMN], errors="coerce")
    df = df.dropna(subset=[ID_COLUMN])
    df[ID_COLUMN] = df[ID_COLUMN].astype(int)

    # Construir diccionario ID → fila del Excel
    rows_by_id = {int(row[ID_COLUMN]): row for _, row in df.iterrows()}

    # Montar el DataFrame final en el mismo orden que los embeddings
    aligned_rows = []
    missing = []
    for cid in ids_emb:
        if cid in rows_by_id:
            aligned_rows.append(rows_by_id[cid])
        else:
            missing.append(cid)

    if missing:
        print(
            f"⚠ {len(missing)} IDs que están en embeddings pero NO en el Excel nuevo."
        )
        print(f"  primeros 10: {missing[:10]}")
        print(
            "  Esto es raro: revisa que el Excel nuevo tenga todos los IDs que ya existían."
        )
        return

    meta = pd.DataFrame(aligned_rows).reset_index(drop=True)

    # 4) Guardar
    meta.to_pickle(OUT_META)
    print(f"\n✓ Actualizado: {OUT_META.name} ({len(meta)} filas)")
    print("\nSiguiente paso:")
    print("  1. Reinicia el backend (para que recargue el pickle)")
    print("  2. Abre un conector en el identificador y verifica que sale el color")


if __name__ == "__main__":
    main()