"""
build_embeddings.py (v3 — ViT-B + ViT-L para re-ranking)
--------------------------------------------------------
Genera DOS archivos de embeddings:
  - embeddings_b.npz  con ViT-B-32  (rápido, shortlist)
  - embeddings_l.npz  con ViT-L-14  (preciso, re-ranking)

Los dos comparten los mismos IDs (se generan a partir de las mismas imágenes).

Orden de búsqueda de imagen para cada ID:
  1. imagenes_originales/{id}.png|.jpg|.jpeg
  2. Imagen embebida en el Excel (fallback)
  3. Se salta ese ID

Uso:
    python build_embeddings.py

Aviso: la primera vez descargará el modelo ViT-L (~1.7 GB).
En CPU, generar los 1024 embeddings con ViT-L tarda ~15-20 min.
"""

from pathlib import Path
import io
import time
import numpy as np
import pandas as pd
from PIL import Image
from openpyxl import load_workbook
import torch
import open_clip

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
HERE = Path(__file__).parent
EXCEL_PATH = HERE / "catalogo_conectores_completo (8).xlsx"
SHEET_NAME = "Catálogo Conectores"
IMG_ORIG_DIR = HERE / "imagenes_originales"

OUT_EMBEDDINGS_B = HERE / "embeddings_b.npz"
OUT_EMBEDDINGS_L = HERE / "embeddings_l.npz"
OUT_META = HERE / "catalogo_meta.pkl"

MODELS = [
    (OUT_EMBEDDINGS_B, "ViT-B-32", "laion2b_s34b_b79k", 16),
    (OUT_EMBEDDINGS_L, "ViT-L-14", "laion2b_s32b_b82k", 4),
]

EXT_ORDER = [".png", ".jpg", ".jpeg", ".webp", ".bmp"]


def load_original_image(cid: int):
    for ext in EXT_ORDER:
        p = IMG_ORIG_DIR / f"{cid}{ext}"
        if p.exists():
            try:
                return Image.open(p).convert("RGB")
            except Exception as e:
                print(f"  ! Error abriendo {p.name}: {e}")
                return None
    return None


def extract_images_from_excel(xlsx_path: Path, sheet: str) -> dict:
    wb = load_workbook(xlsx_path)
    ws = wb[sheet]
    df = pd.read_excel(xlsx_path, sheet_name=sheet)

    out = {}
    for img in ws._images:
        excel_row = img.anchor._from.row + 1
        df_idx = excel_row - 2
        if not (0 <= df_idx < len(df)):
            continue
        cid = df.iloc[df_idx]["ID - Conector catálogo"]
        if pd.isna(cid):
            continue
        cid = int(cid)
        if cid in out:
            continue
        try:
            out[cid] = Image.open(io.BytesIO(img._data())).convert("RGB")
        except Exception:
            pass
    return out


def resolver_imagenes(df: pd.DataFrame, excel_imgs: dict):
    items = []
    stats = {"originales": 0, "excel": 0, "sin_imagen": 0}

    for df_idx, row in df.iterrows():
        cid_val = row["ID - Conector catálogo"]
        if pd.isna(cid_val):
            continue
        cid = int(cid_val)

        pil = load_original_image(cid)
        if pil is not None:
            items.append((cid, pil, df_idx))
            stats["originales"] += 1
            continue

        pil = excel_imgs.get(cid)
        if pil is not None:
            items.append((cid, pil, df_idx))
            stats["excel"] += 1
            continue

        stats["sin_imagen"] += 1

    return items, stats


def compute_embeddings(items, model_name, pretrained, batch_size, device):
    print(f"\n=== {model_name} ({pretrained}) ===")
    print("Cargando modelo... (primera vez descarga el modelo)")

    model, _, preprocess = open_clip.create_model_and_transforms(
        model_name, pretrained=pretrained
    )
    model = model.to(device).eval()

    ids, df_idxs, embs = [], [], []
    t0 = time.time()

    with torch.no_grad():
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            tensors = torch.stack(
                [preprocess(pil) for (_, pil, _) in batch]
            ).to(device)
            feats = model.encode_image(tensors)
            feats = feats / feats.norm(dim=-1, keepdim=True)
            embs.append(feats.cpu().numpy().astype(np.float32))

            for (cid, _, df_idx) in batch:
                ids.append(cid)
                df_idxs.append(df_idx)

            done = min(i + batch_size, len(items))
            dt = time.time() - t0
            eta = (dt / done) * (len(items) - done) if done else 0
            print(f"   {done}/{len(items)}  ({dt:.0f}s, ETA {eta:.0f}s)")

    del model
    if device == "cuda":
        torch.cuda.empty_cache()

    return np.vstack(embs), np.array(ids, dtype=np.int64), df_idxs


def main():
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"No se encuentra {EXCEL_PATH.name}.")

    print(f"[1/3] Leyendo Excel: {EXCEL_PATH.name}")
    df = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_NAME)
    print(f"   Filas del catálogo: {len(df)}")

    print(f"[2/3] Resolviendo imagen por cada ID...")
    print(f"   carpeta originales: {IMG_ORIG_DIR}/  "
          f"({'existe' if IMG_ORIG_DIR.exists() else 'NO EXISTE'})")

    excel_imgs = extract_images_from_excel(EXCEL_PATH, SHEET_NAME)
    print(f"   imágenes en Excel: {len(excel_imgs)}")

    items, stats = resolver_imagenes(df, excel_imgs)
    print(f"   ✓ originales: {stats['originales']}")
    print(f"   · fallback Excel: {stats['excel']}")
    print(f"   · sin imagen: {stats['sin_imagen']}")
    print(f"   → total a procesar: {len(items)}")

    if not items:
        raise RuntimeError("No hay ninguna imagen para procesar.")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\n[3/3] Generando embeddings (device: {device})")

    df_idxs_ref = None
    for out_path, model_name, pretrained, bs in MODELS:
        if out_path.exists():
            print(f"\n--- {out_path.name} ya existe, saltando ---")
            print(f"    (bórralo si quieres regenerar)")
            continue

        emb, ids, df_idxs = compute_embeddings(
            items, model_name, pretrained, bs, device
        )
        np.savez_compressed(out_path, embeddings=emb, ids=ids)
        print(f"\n✓ Guardado: {out_path.name}  shape={emb.shape}")

        if df_idxs_ref is None:
            df_idxs_ref = df_idxs

    if df_idxs_ref is not None:
        meta = df.iloc[df_idxs_ref].copy().reset_index(drop=True)
        meta.to_pickle(OUT_META)
        print(f"✓ Metadatos: {OUT_META.name}  ({len(meta)} filas)")

    print(f"\nListo. Ahora borra img_cache/ (Remove-Item -Recurse img_cache) y arranca uvicorn.")


if __name__ == "__main__":
    main()