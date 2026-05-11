"""
search_api.py (v3.1 — filtrado + CLIP + imágenes reales + frontend)
------------------------------------------------------------------
API FastAPI que recibe:
  - Foto del conector
  - Filtros opcionales (nº terminales, forma, tipo M/H)

Primero filtra el catálogo por los atributos declarados por el ingeniero,
y después ordena los candidatos por similitud visual CLIP.

Uso:
    uvicorn search_api:app --port 8000

    Luego abre: http://localhost:8000

Endpoints:
    GET  /                       -> sirve el frontend (index.html)
    GET  /health
    GET  /filtros                -> valores posibles de cada filtro
    POST /search                 -> form-data: file, top_k, terminales?, forma?, tipo_mh?, debug?
    GET  /imagen/{id}            -> PNG real del conector extraído del Excel
"""

from pathlib import Path
from contextlib import asynccontextmanager
import io
import base64
from typing import Optional, List
import numpy as np
import pandas as pd
from PIL import Image
import torch
import open_clip
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from openpyxl import load_workbook
from rembg import remove, new_session

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
HERE = Path(__file__).parent
# Compatibilidad hacia atrás: si existe embeddings_b.npz usamos ese.
# Si no, usamos el antiguo embeddings.npz.
EMBEDDINGS_B_FILE = HERE / "embeddings_b.npz"
EMBEDDINGS_L_FILE = HERE / "embeddings_l.npz"
EMBEDDINGS_LEGACY = HERE / "embeddings.npz"
META_FILE = HERE / "catalogo_meta.pkl"
EXCEL_FILE = HERE / "catalogo_conectores_completo (6).xlsx"
SHEET_NAME = "Catálogo Conectores"
INDEX_HTML = HERE / "index.html"
IMG_CACHE_DIR = HERE / "img_cache"

MODEL_B_NAME = "ViT-B-32"
MODEL_B_PRETRAINED = "laion2b_s34b_b79k"
MODEL_L_NAME = "ViT-L-14"
MODEL_L_PRETRAINED = "laion2b_s32b_b82k"

DEFAULT_TOP_K = 12
RERANK_SHORTLIST = 30     # cuántos candidatos saca ViT-B para que re-rankee ViT-L

REMBG_MODEL = "u2netp"


# --------------------------------------------------------------------------
STATE: dict = {}

IMG_ORIG_DIR = HERE / "imagenes_originales"
EXT_ORDER = [".png", ".jpg", ".jpeg", ".webp", ".bmp"]


def _original_for(cid: int) -> Path | None:
    for ext in EXT_ORDER:
        p = IMG_ORIG_DIR / f"{cid}{ext}"
        if p.exists():
            return p
    return None


def build_image_cache():
    """
    Cachea las imágenes que servirá /imagen/{id}.
    Prioridad: imagenes_originales/ (alta resolución), luego Excel (70px).
    Guarda siempre como PNG en img_cache/{id}.png.
    """
    IMG_CACHE_DIR.mkdir(exist_ok=True)
    existentes = {int(p.stem) for p in IMG_CACHE_DIR.glob("*.png") if p.stem.isdigit()}
    print(f"  cache previo: {len(existentes)} archivos")

    # Siempre sobrescribimos desde imagenes_originales/ (fuente más fiable)
    n_orig = 0
    if IMG_ORIG_DIR.exists():
        for src in IMG_ORIG_DIR.iterdir():
            if src.suffix.lower() not in EXT_ORDER:
                continue
            if not src.stem.isdigit():
                continue
            cid = int(src.stem)
            dst = IMG_CACHE_DIR / f"{cid}.png"
            try:
                pil = Image.open(src).convert("RGB")
                pil.save(dst, format="PNG", optimize=True)
                n_orig += 1
            except Exception as e:
                print(f"    ! {src.name}: {e}")
    print(f"  desde imagenes_originales/: {n_orig}")

    # Fallback: los IDs que no estén en originales se sacan del Excel
    if not EXCEL_FILE.exists():
        print(f"  ⚠  {EXCEL_FILE.name} no encontrado; sin fallback")
        return

    cached_now = {int(p.stem) for p in IMG_CACHE_DIR.glob("*.png") if p.stem.isdigit()}

    wb = load_workbook(EXCEL_FILE)
    ws = wb[SHEET_NAME]
    df = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)

    n_fb = 0
    for img in ws._images:
        excel_row = img.anchor._from.row + 1
        df_idx = excel_row - 2
        if not (0 <= df_idx < len(df)):
            continue
        cid = df.iloc[df_idx]["ID - Conector catálogo"]
        if pd.isna(cid):
            continue
        cid = int(cid)
        if cid in cached_now:
            continue
        out = IMG_CACHE_DIR / f"{cid}.png"
        try:
            pil = Image.open(io.BytesIO(img._data())).convert("RGB")
            pil.save(out, format="PNG", optimize=True)
            n_fb += 1
        except Exception as e:
            print(f"    ! fila {excel_row}: {e}")
    print(f"  desde Excel (fallback): {n_fb}")
    print(f"  total en cache: {len(list(IMG_CACHE_DIR.glob('*.png')))}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Cargando modelo CLIP ViT-B (shortlist)...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_b, _, preprocess_b = open_clip.create_model_and_transforms(
        MODEL_B_NAME, pretrained=MODEL_B_PRETRAINED
    )
    model_b = model_b.to(device).eval()

    # Cargar embeddings ViT-B (o el legacy si todavía existe)
    emb_b_path = EMBEDDINGS_B_FILE if EMBEDDINGS_B_FILE.exists() else EMBEDDINGS_LEGACY
    if not emb_b_path.exists():
        raise RuntimeError(
            f"No existe embeddings_b.npz ni embeddings.npz. "
            f"Ejecuta antes build_embeddings.py"
        )
    data_b = np.load(emb_b_path)
    embeddings_b = data_b["embeddings"]
    ids = data_b["ids"]
    print(f"  embeddings_b: {embeddings_b.shape}  (de {emb_b_path.name})")

    # Opcional: ViT-L para re-ranking
    model_l = None
    preprocess_l = None
    embeddings_l = None
    if EMBEDDINGS_L_FILE.exists():
        print("Cargando modelo CLIP ViT-L (re-ranking preciso)...")
        model_l, _, preprocess_l = open_clip.create_model_and_transforms(
            MODEL_L_NAME, pretrained=MODEL_L_PRETRAINED
        )
        model_l = model_l.to(device).eval()
        data_l = np.load(EMBEDDINGS_L_FILE)
        embeddings_l = data_l["embeddings"]
        ids_l = data_l["ids"]
        if not np.array_equal(ids, ids_l):
            print("  ⚠  IDs de B y L no coinciden; se ignora L para evitar errores")
            model_l = None
            embeddings_l = None
        else:
            print(f"  embeddings_l: {embeddings_l.shape}")
    else:
        print(f"  (sin ViT-L; genera embeddings_l.npz si quieres re-ranking)")

    meta = pd.read_pickle(META_FILE)
    id_to_idx = {int(cid): i for i, cid in enumerate(ids)}

    print("Preparando cache de imágenes...")
    build_image_cache()

    print(f"Cargando modelo rembg ({REMBG_MODEL})...")
    rembg_session = new_session(REMBG_MODEL)

    STATE.update(
        model_b=model_b,
        preprocess_b=preprocess_b,
        model_l=model_l,
        preprocess_l=preprocess_l,
        device=device,
        embeddings_b=embeddings_b,
        embeddings_l=embeddings_l,
        ids=ids,
        id_to_idx=id_to_idx,
        meta=meta,
        rembg_session=rembg_session,
        has_rerank=(model_l is not None),
    )
    modo = "B+L (re-ranking)" if model_l is not None else "B (rápido)"
    print(f"✓ {len(ids)} conectores cargados · modo: {modo} · device: {device}")
    print(f"✓ abre http://localhost:8000 en el navegador")
    yield
    STATE.clear()


app = FastAPI(title="FAE Conector Visual Search v3.1", lifespan=lifespan)

# CORS abierto (solo uso interno en local)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------
def is_line_drawing(pil_img: Image.Image) -> bool:
    """
    Heurística ligera para distinguir dibujo técnico (line art / plano)
    de foto real.

    Señales de dibujo:
      - alta fracción de píxeles casi-blancos (fondo)
      - baja saturación media (apenas hay color)
      - histograma muy bimodal (blanco + tinta)
    """
    small = pil_img.convert("RGB").resize((128, 128), Image.LANCZOS)
    arr = np.asarray(small, dtype=np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    sat = np.where(maxc > 0, (maxc - minc) / (maxc + 1e-6), 0)
    luma = 0.299 * r + 0.587 * g + 0.114 * b

    frac_casi_blanco = float((luma > 0.90).mean())
    saturacion_media = float(sat.mean())

    # bimodalidad: peso en los extremos del histograma de luma
    hist, _ = np.histogram(luma, bins=10, range=(0, 1))
    hist = hist / hist.sum()
    peso_extremos = float(hist[0] + hist[-1])

    # umbrales empíricos: dibujo técnico suele tener
    # >55% fondo blanco, saturación < 0.10, y >65% del peso en extremos
    return (
        frac_casi_blanco > 0.55
        and saturacion_media < 0.10
        and peso_extremos > 0.65
    )


def _to_square_white(pil_img: Image.Image, size: int = 224) -> Image.Image:
    """Centra sobre lienzo blanco cuadrado y escala a `size`."""
    rgb = pil_img.convert("RGB")
    w, h = rgb.size
    side = max(w, h)
    square = Image.new("RGB", (side, side), (255, 255, 255))
    square.paste(rgb, ((side - w) // 2, (side - h) // 2))
    return square.resize((size, size), Image.LANCZOS)


def preprocess_photo(pil_img: Image.Image) -> tuple[Image.Image, str]:
    """
    Devuelve (imagen_224x224, modo) donde modo ∈ {'foto', 'dibujo'}.
    - foto:    rembg + recorte + fondo blanco + cuadrado 224
    - dibujo:  saltamos rembg (lo estropearía); solo cuadrado 224
    """
    if is_line_drawing(pil_img):
        return _to_square_white(pil_img), "dibujo"

    out = remove(pil_img, session=STATE["rembg_session"])
    alpha = out.split()[-1]
    bbox = alpha.getbbox()
    if bbox is None:
        return _to_square_white(pil_img), "foto_sin_recorte"

    cropped = out.crop(bbox)
    white = Image.new("RGB", cropped.size, (255, 255, 255))
    white.paste(cropped, mask=cropped.split()[-1])
    return _to_square_white(white), "foto"


def _embed_with(pil_img: Image.Image, model, preprocess) -> np.ndarray:
    tensor = preprocess(pil_img).unsqueeze(0).to(STATE["device"])
    with torch.no_grad():
        feats = model.encode_image(tensor)
        feats = feats / feats.norm(dim=-1, keepdim=True)
    return feats.cpu().numpy()[0].astype(np.float32)


def embed_image_b(pil_img: Image.Image) -> np.ndarray:
    return _embed_with(pil_img, STATE["model_b"], STATE["preprocess_b"])


def embed_image_l(pil_img: Image.Image) -> np.ndarray:
    return _embed_with(pil_img, STATE["model_l"], STATE["preprocess_l"])


def apply_filters(
    meta: pd.DataFrame,
    terminales: Optional[int],
    forma: Optional[str],
    tipo_mh: Optional[str],
) -> pd.DataFrame:
    """Subset de meta que cumple los filtros. None/vacío = no filtrar."""
    df = meta.copy()

    if terminales is not None:
        # terminales=5 significa "5 o más"
        if terminales >= 5:
            df = df[df["Terminales"] >= 5.0]
        else:
            df = df[df["Terminales"] == float(terminales)]

    if forma:
        # "Varios" es comodín: si el ingeniero dice Redondo/Cuadrado,
        # incluimos también los marcados como "Varios" por si están
        # mal etiquetados
        if forma.lower() in ("redondo", "cuadrado"):
            df = df[df["Formas"].isin([forma.capitalize(), "Varios"])]
        else:
            df = df[df["Formas"].str.lower() == forma.lower()]

    if tipo_mh:
        df = df[df["Tipo (M/H)"].str.lower() == tipo_mh.lower()]

    return df


def meta_row_to_dict(row: pd.Series) -> dict:
    d = row.to_dict()
    return {k: (None if pd.isna(v) else v) for k, v in d.items()}


def pil_to_base64(pil_img: Image.Image) -> str:
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
@app.get("/")
def root():
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)
    return {"msg": "index.html no encontrado; pon el frontend junto a search_api.py"}


@app.get("/health")
def health():
    has_rerank = bool(STATE.get("has_rerank"))
    model_info = MODEL_B_NAME
    if has_rerank:
        model_info = f"{MODEL_B_NAME} + {MODEL_L_NAME} (rerank top {RERANK_SHORTLIST})"
    return {
        "status": "ok",
        "conectores": int(len(STATE.get("ids", []))),
        "device": STATE.get("device"),
        "model": model_info,
        "has_rerank": has_rerank,
        "preprocessing": "rembg + crop + white background",
        "filtering": "terminales, forma, tipo_mh",
    }


@app.get("/filtros")
def filtros():
    """Valores posibles para poblar dropdowns en el frontend."""
    meta = STATE["meta"]
    return {
        "terminales": sorted(
            int(t) for t in meta["Terminales"].dropna().unique()
        ),
        "forma": sorted(
            str(f) for f in meta["Formas"].dropna().unique()
        ),
        "tipo_mh": sorted(
            str(t) for t in meta["Tipo (M/H)"].dropna().unique()
            if t not in ("¿?", "-")
        ),
    }


@app.get("/imagen/{conector_id}")
def imagen(conector_id: int):
    """Devuelve el PNG real del conector."""
    path = IMG_CACHE_DIR / f"{conector_id}.png"
    if not path.exists():
        raise HTTPException(404, f"No hay imagen para el conector {conector_id}")
    return FileResponse(path, media_type="image/png")

@app.get("/by_id")
def by_id(q: str, include_similar: int = 1, max_similar: int = 12):
    """
    Búsqueda directa por ID de conector catálogo o Referencia FAE.
    No usa embeddings: consulta solo los metadatos.
    """
    meta = STATE["meta"]
    q_str = (q or "").strip()
    if not q_str:
        raise HTTPException(400, "Query vacía")

    match_row = None
    match_type = None

    # 1) Intentar como ID entero
    try:
        q_int = int(q_str)
        found = meta[meta["ID - Conector catálogo"] == q_int]
        if len(found) > 0:
            match_row = found.iloc[0]
            match_type = "id"
    except ValueError:
        pass

    # 2) Intentar como Referencia FAE (string, coincidencia exacta)
    if match_row is None and "Referencia FAE" in meta.columns:
        ref_col = meta["Referencia FAE"].astype(str).str.strip()
        found = meta[ref_col == q_str]
        if len(found) > 0:
            match_row = found.iloc[0]
            match_type = "ref_fae"

    # 3) Intentar como Referencia Comercial (exacta)
    if match_row is None and "Referencia Comercial" in meta.columns:
        ref_col = meta["Referencia Comercial"].astype(str).str.strip()
        found = meta[ref_col == q_str]
        if len(found) > 0:
            match_row = found.iloc[0]
            match_type = "ref_comercial"

    if match_row is None:
        return JSONResponse({
            "match": None,
            "match_type": None,
            "similares": [],
            "n_similares": 0,
            "aviso": f"No se encontró ningún conector con '{q_str}'",
        })

    match_id = int(match_row["ID - Conector catálogo"])
    match_dict = {
        "id_conector": match_id,
        "similitud": 1.0,
        "meta": meta_row_to_dict(match_row),
    }

    similares = []
    if include_similar:
        forma = match_row.get("Formas")
        terms = match_row.get("Terminales")

        sim_df = meta.copy()
        sim_df = sim_df[sim_df["ID - Conector catálogo"] != match_id]

        if forma is not None and not (isinstance(forma, float) and pd.isna(forma)):
            sim_df = sim_df[sim_df["Formas"] == forma]
        if terms is not None and not (isinstance(terms, float) and pd.isna(terms)):
            sim_df = sim_df[sim_df["Terminales"] == terms]

        sim_df = sim_df.head(max_similar)

        for _, row in sim_df.iterrows():
            similares.append({
                "id_conector": int(row["ID - Conector catálogo"]),
                "similitud": None,
                "meta": meta_row_to_dict(row),
            })

    return JSONResponse({
        "match": match_dict,
        "match_type": match_type,
        "similares": similares,
        "n_similares": len(similares),
    })
    
@app.post("/search")
async def search(
    files: List[UploadFile] = File(...),    # acepta 1..N imágenes bajo el nombre 'files'
    top_k: int = Form(DEFAULT_TOP_K),
    terminales: Optional[int] = Form(None),
    forma: Optional[str] = Form(None),
    tipo_mh: Optional[str] = Form(None),
    rerank: int = Form(1),
    debug: int = Form(0),
):
    if not files:
        raise HTTPException(400, "No se ha recibido ninguna imagen")
    if len(files) > 8:
        raise HTTPException(400, "Máximo 8 imágenes por búsqueda")

    # ── Leer y preprocesar cada imagen ───────────────────────────────────
    processed_images = []
    filenames = []
    modos = []
    for f in files:
        try:
            raw = await f.read()
            pil = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as e:
            raise HTTPException(400, f"Imagen '{f.filename}' inválida: {e}")
        try:
            proc, modo = preprocess_photo(pil)
        except Exception as e:
            raise HTTPException(500, f"Error en preprocesado de '{f.filename}': {e}")
        processed_images.append(proc)
        filenames.append(f.filename)
        modos.append(modo)

    n_imgs = len(processed_images)

    # ── Filtrar candidatos por atributos ─────────────────────────────────
    meta = STATE["meta"]
    filtered = apply_filters(meta, terminales, forma, tipo_mh)
    n_candidatos = len(filtered)

    if n_candidatos == 0:
        return JSONResponse({
            "query_filenames": filenames,
            "n_imagenes": n_imgs,
            "modos": modos,
            "filtros_aplicados": {
                "terminales": terminales, "forma": forma, "tipo_mh": tipo_mh
            },
            "n_candidatos": 0,
            "results": [],
            "aviso": "Ningún conector del catálogo cumple esos filtros. "
                     "Prueba a relajarlos.",
        })

    id_to_idx = STATE["id_to_idx"]
    cand_ids = filtered["ID - Conector catálogo"].astype(int).tolist()
    cand_ids_aligned = [cid for cid in cand_ids if cid in id_to_idx]
    cand_positions = np.array(
        [id_to_idx[cid] for cid in cand_ids_aligned],
        dtype=np.int64,
    )

    # ── Embeddings de cada imagen (ViT-B) ────────────────────────────────
    q_b_list = [embed_image_b(p) for p in processed_images]       # cada uno (512,)
    q_b_stack = np.stack(q_b_list, axis=0)                        # (n_imgs, 512)

    cand_emb_b = STATE["embeddings_b"][cand_positions]            # (N, 512)

    # sims[i, j] = similitud entre imagen i y candidato j
    sims_matrix = cand_emb_b @ q_b_stack.T                        # (N, n_imgs)

    # Combinamos: 70% promedio + 30% máximo
    if n_imgs == 1:
        sims_b = sims_matrix[:, 0]
        combinacion = "única imagen"
    else:
        sims_avg = sims_matrix.mean(axis=1)
        sims_max = sims_matrix.max(axis=1)
        sims_b = 0.7 * sims_avg + 0.3 * sims_max
        combinacion = f"{n_imgs} imágenes · 0.7·avg + 0.3·max"

    # ── Re-ranking opcional con ViT-L ────────────────────────────────────
    use_rerank = (
        bool(rerank)
        and STATE.get("has_rerank")
        and STATE.get("embeddings_l") is not None
    )

    if use_rerank:
        shortlist_n = min(RERANK_SHORTLIST, len(sims_b))
        shortlist_local = np.argsort(-sims_b)[:shortlist_n]
        shortlist_positions = cand_positions[shortlist_local]

        q_l_list = [embed_image_l(p) for p in processed_images]   # (n_imgs,)·(768,)
        q_l_stack = np.stack(q_l_list, axis=0)                    # (n_imgs, 768)
        cand_emb_l = STATE["embeddings_l"][shortlist_positions]   # (K, 768)
        sims_l_matrix = cand_emb_l @ q_l_stack.T                  # (K, n_imgs)

        if n_imgs == 1:
            sims_l = sims_l_matrix[:, 0]
        else:
            sims_l = 0.7 * sims_l_matrix.mean(axis=1) + 0.3 * sims_l_matrix.max(axis=1)

        top_n = min(top_k, shortlist_n)
        order_in_shortlist = np.argsort(-sims_l)[:top_n]
        final_local = shortlist_local[order_in_shortlist]
        final_scores = sims_l[order_in_shortlist]
        scoring = f"ViT-L (rerank top {shortlist_n}) · {combinacion}"
    else:
        top_n = min(top_k, len(sims_b))
        final_local = np.argsort(-sims_b)[:top_n]
        final_scores = sims_b[final_local]
        scoring = f"ViT-B · {combinacion}"

    results = []
    for local_idx, score in zip(final_local, final_scores):
        cid = int(cand_ids_aligned[local_idx])
        row = meta[meta["ID - Conector catálogo"] == cid].iloc[0]
        results.append({
            "id_conector": cid,
            "similitud": round(float(score), 4),
            "meta": meta_row_to_dict(row),
        })

    response = {
        "query_filenames": filenames,
        "n_imagenes": n_imgs,
        "modos": modos,
        "scoring": scoring,
        "filtros_aplicados": {
            "terminales": terminales, "forma": forma, "tipo_mh": tipo_mh
        },
        "n_candidatos": int(n_candidatos),
        "results": results,
    }
    if debug:
        response["debug_processed_images_b64"] = [pil_to_base64(p) for p in processed_images]

    return JSONResponse(response)