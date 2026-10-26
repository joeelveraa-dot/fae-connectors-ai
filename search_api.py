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
    POST /registrar               -> form-data: file, referencia_fae?, forma?, terminales?, ...
                                      registra un conector nuevo (foto + metadatos + embedding)
    POST /editar_conector         -> form-data: id_conector, file?, referencia_fae?, ...
                                      edita un conector existente y sincroniza el Excel real
"""

from pathlib import Path
from contextlib import asynccontextmanager
import io
import base64
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from typing import Optional, List
import numpy as np
import pandas as pd
from PIL import Image
import torch
import open_clip
from fastapi import FastAPI, UploadFile, File, HTTPException, Form

try:
    import win32com.client as win32com_client
    import pywintypes
    EXCEL_COM_AVAILABLE = True
except ImportError:
    win32com_client = None
    pywintypes = None
    EXCEL_COM_AVAILABLE = False
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from openpyxl import load_workbook
#from rembg import remove, new_session

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
# El Excel "fuente de verdad" vive en la carpeta de OneDrive del usuario
# (se sincroniza sola con SharePoint); así cualquier alta/edición desde la
# app se sube automáticamente. Si esa ruta no existe (p.ej. otra máquina sin
# ese OneDrive), se cae a la copia local del proyecto.
_EXCEL_ONEDRIVE = Path(
    r"C:\Users\jnunezv\OneDrive - FRANCISCO ALBERO S.A.U\Documentos\catalogo_conectores_completo.xlsx"
)
EXCEL_FILE = _EXCEL_ONEDRIVE if _EXCEL_ONEDRIVE.exists() else HERE / "catalogo_conectores_completo.xlsx"
SHEET_NAME = "Catálogo Conectores"
INDEX_HTML = HERE / "index.html"
IMG_CACHE_DIR = HERE / "img_cache"

MODEL_B_NAME = "ViT-B-32"
MODEL_B_PRETRAINED = "laion2b_s34b_b79k"
MODEL_L_NAME = "ViT-L-14"
MODEL_L_PRETRAINED = "laion2b_s32b_b82k"

DEFAULT_TOP_K = 12
RERANK_SHORTLIST = 30     # cuántos candidatos saca ViT-B para que re-rankee ViT-L

#REMBG_MODEL = "u2netp"


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


_OOXML_NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "xlrd": "http://schemas.microsoft.com/office/spreadsheetml/2017/richdata",
}
_OOXML_R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _resolve_sheet_xml_path(zf: "zipfile.ZipFile", sheet_name: str) -> str:
    wb_xml = ET.fromstring(zf.read("xl/workbook.xml"))
    rels_xml = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {rel.get("Id"): rel.get("Target") for rel in rels_xml}
    for sheet in wb_xml.find("m:sheets", _OOXML_NS):
        if sheet.get("name") == sheet_name:
            target = rid_to_target[sheet.get(f"{_OOXML_R_NS}id")]
            return target if target.startswith("xl/") else "xl/" + target
    raise ValueError(f"Hoja no encontrada: {sheet_name}")


def extract_foto_column_photos(excel_path: Path, sheet_name: str, foto_col_letter: str) -> dict:
    """
    Extrae las fotos insertadas "en celda" (función moderna de Excel 365,
    Insertar > Imágenes > Colocar en celda) de la columna `foto_col_letter`.
    openpyxl no soporta este tipo de dato (Rich Value / xl/richData), así que
    hay que leer el XML interno del .xlsx directamente.

    Devuelve {id_conector: bytes_imagen}. Si el archivo no usa esta función
    de Excel, devuelve {} sin fallar.
    """
    try:
        zf = zipfile.ZipFile(excel_path)
        names = set(zf.namelist())
        required = {
            "xl/metadata.xml", "xl/richData/rdrichvalue.xml",
            "xl/richData/richValueRel.xml", "xl/richData/_rels/richValueRel.xml.rels",
        }
        if not required.issubset(names):
            return {}

        sheet_xml_path = _resolve_sheet_xml_path(zf, sheet_name)

        meta_root = ET.fromstring(zf.read("xl/metadata.xml"))
        vm_to_v = [
            int(bk.find("m:rc", _OOXML_NS).get("v"))
            for bk in meta_root.find("m:valueMetadata", _OOXML_NS).findall("m:bk", _OOXML_NS)
        ]
        future_meta = next(
            fm for fm in meta_root.findall("m:futureMetadata", _OOXML_NS)
            if fm.get("name") == "XLRICHVALUE"
        )
        fm_to_rvidx = [
            int(bk.find(".//xlrd:rvb", _OOXML_NS).get("i"))
            for bk in future_meta.findall("m:bk", _OOXML_NS)
        ]

        rv_root = ET.fromstring(zf.read("xl/richData/rdrichvalue.xml"))
        rv_list = [int(rv.findall("xlrd:v", _OOXML_NS)[0].text) for rv in rv_root.findall("xlrd:rv", _OOXML_NS)]

        rvrel_root = ET.fromstring(zf.read("xl/richData/richValueRel.xml"))
        rel_ids = [rel.get(f"{_OOXML_R_NS}id") for rel in rvrel_root]

        rels_root = ET.fromstring(zf.read("xl/richData/_rels/richValueRel.xml.rels"))
        rid_to_target = {rel.get("Id"): rel.get("Target") for rel in rels_root}

        def vm_to_media(vm: int) -> str:
            v = vm_to_v[vm - 1]
            idx_in_rel = rv_list[fm_to_rvidx[v]]
            return rid_to_target[rel_ids[idx_in_rel]]

        sheet_xml = zf.read(sheet_xml_path).decode("utf-8")
        row_to_vm = {
            int(m.group(1)): int(m.group(2))
            for m in re.finditer(rf'<c r="{foto_col_letter}(\d+)"[^>]*\bvm="(\d+)"', sheet_xml)
        }
        if not row_to_vm:
            return {}

        wb = load_workbook(excel_path, data_only=True)
        ws = wb[sheet_name]

        out = {}
        for row, vm in row_to_vm.items():
            cid = ws.cell(row=row, column=1).value
            if cid is None:
                continue
            try:
                media_target = vm_to_media(vm)
            except (IndexError, KeyError):
                continue
            media_path = "xl/" + media_target.replace("../", "")
            try:
                out[int(cid)] = zf.read(media_path)
            except KeyError:
                continue
        return out
    except Exception as e:
        print(f"  ! extract_foto_column_photos: {e}")
        return {}


def write_fields_to_excel(
    excel_path: Path,
    sheet_name: str,
    id_conector: int,
    field_updates: dict,
    create_if_missing: bool = False,
) -> tuple[bool, str]:
    """
    Escribe cambios de campos en el Excel real para la fila de `id_conector`,
    usando Excel vía COM (nunca openpyxl: este archivo usa "imagen en celda"
    / richData en la columna Foto, que openpyxl destruye al volver a guardar).

    Si `create_if_missing` es True y el ID no existe todavía, añade una fila
    nueva al final de los datos (usado al registrar un conector nuevo).

    Si Excel ya tiene el archivo abierto, reutiliza esa misma ventana en vez
    de abrir una segunda copia (y no la cierra al terminar). Si no, lanza una
    instancia oculta, la cierra al terminar.

    Devuelve (ok, mensaje).
    """
    if not EXCEL_COM_AVAILABLE:
        return False, "Automatización de Excel no disponible en este servidor"

    excel_path_str = str(excel_path.resolve())
    excel = None
    wb = None
    we_launched_excel = False
    we_opened_wb = False

    try:
        try:
            excel = win32com_client.GetActiveObject("Excel.Application")
            for open_wb in excel.Workbooks:
                if open_wb.FullName.lower() == excel_path_str.lower():
                    wb = open_wb
                    break
        except Exception:
            excel = None

        if excel is None:
            excel = win32com_client.gencache.EnsureDispatch("Excel.Application")
            excel.Visible = False
            we_launched_excel = True

        if wb is None:
            excel.DisplayAlerts = False
            wb = excel.Workbooks.Open(excel_path_str)
            we_opened_wb = True

        ws = wb.Sheets(sheet_name)

        headers = {}
        for c in range(1, 25):
            v = ws.Cells(1, c).Value
            if v:
                headers[str(v).strip()] = c

        # Leer la columna de IDs de una sola vez (mucho más rápido que
        # celda a celda, y evita depender del "used range" de Excel, que
        # puede estar inflado por formato aplicado a filas vacías).
        id_rows = ws.Range("A2:A3000").Value
        target_row = None
        for i, row_tuple in enumerate(id_rows):
            v = row_tuple[0] if row_tuple else None
            if v is None:
                continue
            try:
                if int(v) == id_conector:
                    target_row = i + 2
                    break
            except (ValueError, TypeError):
                continue

        if target_row is None:
            if not create_if_missing:
                return False, f"No se encontró el conector #{id_conector} en el Excel"
            last_row = 1  # fila de cabecera
            for i, row_tuple in enumerate(id_rows):
                v = row_tuple[0] if row_tuple else None
                if v is not None:
                    last_row = i + 2
            target_row = last_row + 1

        for field_name, value in field_updates.items():
            col = headers.get(field_name)
            if col is None:
                continue
            ws.Cells(target_row, col).Value = value

        wb.Save()
        return True, "Excel actualizado"
    except Exception as e:
        return False, f"No se pudo actualizar el Excel: {e}"
    finally:
        if wb is not None and we_opened_wb:
            try:
                wb.Close(False)
            except Exception:
                pass
        if excel is not None and we_launched_excel:
            try:
                excel.Quit()
            except Exception:
                pass


def build_image_cache():
    """
    Cachea las imágenes que servirá /imagen/{id}.
    Prioridad: imagenes_originales/ (alta resolución) > columna "Foto" del
    Excel (foto real insertada en celda) > columna "Imagen" del Excel
    (dibujo técnico, último recurso).
    Guarda siempre como PNG en img_cache/{id}.png.
    """
    IMG_CACHE_DIR.mkdir(exist_ok=True)
    existentes = {int(p.stem) for p in IMG_CACHE_DIR.glob("*.png") if p.stem.isdigit()}
    print(f"  cache previo: {len(existentes)} archivos")

    # Siempre sobrescribimos desde imagenes_originales/ (fuente más fiable).
    # Algunos archivos de esa carpeta son en realidad dibujos técnicos, no
    # fotos reales, así que los detectamos para poder cederles el puesto a
    # una foto real de la columna "Foto" del Excel si existe.
    n_orig = 0
    ids_originales = set()
    ids_originales_dibujo = set()
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
                ids_originales.add(cid)
                if is_line_drawing(pil):
                    ids_originales_dibujo.add(cid)
            except Exception as e:
                print(f"    ! {src.name}: {e}")
    print(f"  desde imagenes_originales/: {n_orig} (de ellos, dibujo técnico: {len(ids_originales_dibujo)})")

    if not EXCEL_FILE.exists():
        print(f"  ⚠  {EXCEL_FILE.name} no encontrado; sin fallback")
        return

    # Fotos reales insertadas "en celda" en la columna Foto (prioridad 2):
    # mejor que cualquier dibujo técnico, venga este de imagenes_originales/
    # o del Excel. Solo respeta una foto real ya existente en originales/.
    foto_photos = extract_foto_column_photos(EXCEL_FILE, SHEET_NAME, "M")
    ids_foto = set()
    n_foto = 0
    for cid, raw in foto_photos.items():
        if cid in ids_originales and cid not in ids_originales_dibujo:
            continue
        try:
            pil = Image.open(io.BytesIO(raw)).convert("RGB")
            pil.save(IMG_CACHE_DIR / f"{cid}.png", format="PNG", optimize=True)
            n_foto += 1
            ids_foto.add(cid)
        except Exception as e:
            print(f"    ! foto en celda id {cid}: {e}")
    print(f"  desde columna Foto (en celda): {n_foto}")

    # Fallback final: los IDs que todavía no tengan ninguna imagen cacheada
    # (ni original, ni sustituida por una foto de la columna Foto) se sacan
    # del dibujo técnico del Excel como último recurso.
    cached_now = ids_originales | ids_foto

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
    #if EMBEDDINGS_L_FILE.exists():
     #   print("Cargando modelo CLIP ViT-L (re-ranking preciso)...")
       # model_l, _, preprocess_l = open_clip.create_model_and_transforms(
        #    MODEL_L_NAME, pretrained=MODEL_L_PRETRAINED
        #)
        #model_l = model_l.to(device).eval()
        #data_l = np.load(EMBEDDINGS_L_FILE)
        #embeddings_l = data_l["embeddings"]
        #ids_l = data_l["ids"]
        #if not np.array_equal(ids, ids_l):
            #print("  ⚠  IDs de B y L no coinciden; se ignora L para evitar errores")
            #model_l = None
            #embeddings_l = None
        #else:
            #print(f"  embeddings_l: {embeddings_l.shape}")
    #else:
        #print(f"  (sin ViT-L; genera embeddings_l.npz si quieres re-ranking)")

    meta = pd.read_pickle(META_FILE)
    id_to_idx = {int(cid): i for i, cid in enumerate(ids)}

    print("Preparando cache de imágenes...")
    build_image_cache()

    #print(f"Cargando modelo rembg ({REMBG_MODEL})...")
    #rembg_session = new_session(REMBG_MODEL)

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
        #rembg_session=rembg_session,
        has_rerank=(model_l is not None),
    )
    modo = "B+L (re-ranking)" if model_l is not None else "B (rápido)"
    print(f"OK: {len(ids)} conectores cargados - modo: {modo} - device: {device}")
    print("OK: abre http://localhost:8000 en el navegador")
    yield
    STATE.clear()


app = FastAPI(
    title="FAE Conector Visual Search v3.1",
    lifespan=lifespan,
    servers=[
        {
            "url": "https://copilot-fae-c0d4huf8hsd7ghbt.westeurope-01.azurewebsites.net",
            "description": "Production"
        }
    ]
)

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


def preprocess_photo(pil_img: Image.Image):
    return _to_square_white(pil_img), "simple"


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

    # 3) Intentar como Referencia Proveedor (exacta)
    if match_row is None and "Referencia Proveedor" in meta.columns:
        ref_col = meta["Referencia Proveedor"].astype(str).str.strip()
        found = meta[ref_col == q_str]
        if len(found) > 0:
            match_row = found.iloc[0]
            match_type = "ref_proveedor"

    # 4) Sin coincidencia exacta de ID/Referencia: buscar el texto en
    #    cualquier otro campo (Contraconector, Proveedor, Descripción, ...)
    #    y devolver TODOS los conectores asociados a ese valor.
    GENERIC_SEARCH_COLUMNS = [
        "Contraconector", "Plano que contiene el contraconector",
        "Proveedor", "Descripción", "Colores", "Formas", "Tipo (M/H)",
        "Fabricación Interna", "Caja", "Referencia FAE", "Referencia Proveedor",
        "Ref. Acabado",
    ]
    if match_row is None:
        q_lower = q_str.lower()
        mask = pd.Series(False, index=meta.index)
        campos_con_match = []
        for col in GENERIC_SEARCH_COLUMNS:
            if col not in meta.columns:
                continue
            col_mask = meta[col].astype(str).str.lower().str.contains(
                q_lower, regex=False, na=False
            )
            if col_mask.any():
                campos_con_match.append(col)
            mask = mask | col_mask

        found = meta[mask]
        if len(found) > 0:
            resultados = [
                {
                    "id_conector": int(row["ID - Conector catálogo"]),
                    "similitud": None,
                    "meta": meta_row_to_dict(row),
                }
                for _, row in found.iterrows()
            ]
            return JSONResponse({
                "match": None,
                "match_type": "campo_generico",
                "similares": [],
                "n_similares": 0,
                "resultados": resultados,
                "n_resultados": len(resultados),
                "campos_con_match": campos_con_match,
                "aviso": f"'{q_str}' no es un ID ni una referencia, pero aparece en: "
                         f"{', '.join(campos_con_match)}",
            })

    if match_row is None:
        return JSONResponse({
            "match": None,
            "match_type": None,
            "similares": [],
            "n_similares": 0,
            "resultados": [],
            "n_resultados": 0,
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
        "resultados": [],
        "n_resultados": 0,
    })


@app.post("/registrar")
async def registrar_conector(
    file: UploadFile = File(...),
    referencia_fae: Optional[str] = Form(None),
    referencia_proveedor: Optional[str] = Form(None),
    proveedor: Optional[str] = Form(None),
    descripcion: Optional[str] = Form(None),
    terminales: Optional[int] = Form(None),
    forma: Optional[str] = Form(None),
    tipo_mh: Optional[str] = Form(None),
    colores: Optional[str] = Form(None),
    caja: Optional[str] = Form(None),
    contraconector: Optional[str] = Form(None),
    plano_contraconector: Optional[str] = Form(None),
):
    """
    Registra un conector que todavía no está en el catálogo: guarda su foto,
    calcula su embedding CLIP y añade una fila a los metadatos, en caliente
    (sin reiniciar el servidor), para que sea buscable inmediatamente.
    """
    try:
        raw = await file.read()
        pil = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as e:
        raise HTTPException(400, f"Imagen inválida: {e}")

    ids = STATE["ids"]
    meta = STATE["meta"]
    new_id = int(max(
        int(ids.max()) if len(ids) else 0,
        int(meta["ID - Conector catálogo"].max()) if len(meta) else 0,
    )) + 1

    # 1) Guardar imagen original (fuente para futuros build_embeddings.py)
    IMG_ORIG_DIR.mkdir(exist_ok=True)
    pil.save(IMG_ORIG_DIR / f"{new_id}.png", format="PNG")

    # 2) Cache para que /imagen/{id} la sirva ya mismo
    IMG_CACHE_DIR.mkdir(exist_ok=True)
    pil.save(IMG_CACHE_DIR / f"{new_id}.png", format="PNG", optimize=True)

    # 3) Embedding ViT-B, mismo preprocesado que el resto del catálogo
    #    (imagen tal cual, sin el recuadro blanco que se usa solo para queries)
    tensor = STATE["preprocess_b"](pil).unsqueeze(0).to(STATE["device"])
    with torch.no_grad():
        feats = STATE["model_b"].encode_image(tensor)
        feats = feats / feats.norm(dim=-1, keepdim=True)
    new_emb = feats.cpu().numpy()[0].astype(np.float32)

    embeddings_b = np.vstack([STATE["embeddings_b"], new_emb[None, :]])
    new_ids = np.append(ids, np.int64(new_id))
    np.savez_compressed(EMBEDDINGS_B_FILE, embeddings=embeddings_b, ids=new_ids)
    STATE["embeddings_b"] = embeddings_b
    STATE["ids"] = new_ids
    STATE["id_to_idx"][new_id] = len(new_ids) - 1

    # 4) Fila de metadatos
    new_row = {
        "ID - Conector catálogo": new_id,
        "Imagen": None,
        "Contraconector": contraconector,
        "Plano que contiene el contraconector": plano_contraconector,
        "Referencia FAE": referencia_fae,
        "Conector aereo": None,
        "Terminales": float(terminales) if terminales is not None else None,
        "Formas": forma,
        "Referencia Proveedor": referencia_proveedor,
        "Proveedor": proveedor,
        "Descripción": descripcion,
        "Tipo (M/H)": tipo_mh,
        "Colores": colores,
        "Caja": caja,
    }
    new_row = {k: v for k, v in new_row.items() if k in meta.columns}
    meta_updated = pd.concat([meta, pd.DataFrame([new_row])], ignore_index=True)

    if META_FILE.exists():
        shutil.copy(META_FILE, HERE / "catalogo_meta.backup.pkl")
    meta_updated.to_pickle(META_FILE)
    STATE["meta"] = meta_updated

    # 5) Añadir la misma fila al Excel real (fila nueva al final)
    excel_ok, excel_msg = write_fields_to_excel(
        EXCEL_FILE, SHEET_NAME, new_id, new_row, create_if_missing=True
    )

    mensaje = f"Conector #{new_id} registrado correctamente."
    if not excel_ok:
        mensaje += f" Aviso: no se pudo añadir al Excel ({excel_msg})."

    return JSONResponse({
        "ok": True,
        "id_conector": new_id,
        "excel_sincronizado": excel_ok,
        "excel_mensaje": excel_msg,
        "mensaje": mensaje,
    })


@app.post("/editar_conector")
async def editar_conector(
    id_conector: int = Form(...),
    file: Optional[UploadFile] = File(None),
    referencia_fae: Optional[str] = Form(None),
    referencia_proveedor: Optional[str] = Form(None),
    proveedor: Optional[str] = Form(None),
    descripcion: Optional[str] = Form(None),
    terminales: Optional[int] = Form(None),
    forma: Optional[str] = Form(None),
    tipo_mh: Optional[str] = Form(None),
    colores: Optional[str] = Form(None),
    caja: Optional[str] = Form(None),
    contraconector: Optional[str] = Form(None),
    plano_contraconector: Optional[str] = Form(None),
):
    """
    Edita un conector que ya existe en el catálogo: actualiza sus metadatos
    (y opcionalmente su foto) en caliente, y sincroniza los mismos cambios
    en el Excel real (vía Excel COM, no openpyxl).
    """
    meta = STATE["meta"]
    id_col = "ID - Conector catálogo"
    mask = meta[id_col] == id_conector
    if not mask.any():
        raise HTTPException(404, f"No existe el conector #{id_conector}")
    idx = meta.index[mask][0]

    campo_valor = {
        "Referencia FAE": referencia_fae,
        "Referencia Proveedor": referencia_proveedor,
        "Proveedor": proveedor,
        "Descripción": descripcion,
        "Terminales": float(terminales) if terminales is not None else None,
        "Formas": forma,
        "Tipo (M/H)": tipo_mh,
        "Colores": colores,
        "Caja": caja,
        "Contraconector": contraconector,
        "Plano que contiene el contraconector": plano_contraconector,
    }

    # 1) Metadatos en memoria + pkl (solo columnas que existan en el esquema)
    for campo, valor in campo_valor.items():
        if campo in meta.columns:
            meta.at[idx, campo] = None if valor == "" else valor

    if META_FILE.exists():
        shutil.copy(META_FILE, HERE / "catalogo_meta.backup.pkl")
    meta.to_pickle(META_FILE)
    STATE["meta"] = meta

    # 2) Foto nueva (opcional): actualizar original + caché + embedding
    foto_actualizada = False
    if file is not None and file.filename:
        try:
            raw = await file.read()
            pil = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception as e:
            raise HTTPException(400, f"Imagen inválida: {e}")

        IMG_ORIG_DIR.mkdir(exist_ok=True)
        pil.save(IMG_ORIG_DIR / f"{id_conector}.png", format="PNG")
        IMG_CACHE_DIR.mkdir(exist_ok=True)
        pil.save(IMG_CACHE_DIR / f"{id_conector}.png", format="PNG", optimize=True)

        tensor = STATE["preprocess_b"](pil).unsqueeze(0).to(STATE["device"])
        with torch.no_grad():
            feats = STATE["model_b"].encode_image(tensor)
            feats = feats / feats.norm(dim=-1, keepdim=True)
        new_emb = feats.cpu().numpy()[0].astype(np.float32)

        if id_conector in STATE["id_to_idx"]:
            pos = STATE["id_to_idx"][id_conector]
            STATE["embeddings_b"][pos] = new_emb
        else:
            STATE["embeddings_b"] = np.vstack([STATE["embeddings_b"], new_emb[None, :]])
            STATE["ids"] = np.append(STATE["ids"], np.int64(id_conector))
            STATE["id_to_idx"][id_conector] = len(STATE["ids"]) - 1
        np.savez_compressed(
            EMBEDDINGS_B_FILE, embeddings=STATE["embeddings_b"], ids=STATE["ids"]
        )
        foto_actualizada = True

    # 3) Sincronizar los mismos cambios con el Excel real
    excel_fields = {k: (None if v == "" else v) for k, v in campo_valor.items()}
    excel_ok, excel_msg = write_fields_to_excel(
        EXCEL_FILE, SHEET_NAME, id_conector, excel_fields
    )

    mensaje = f"Conector #{id_conector} actualizado."
    if not excel_ok:
        mensaje += f" Aviso: no se pudo sincronizar con el Excel ({excel_msg})."

    return JSONResponse({
        "ok": True,
        "id_conector": id_conector,
        "foto_actualizada": foto_actualizada,
        "excel_sincronizado": excel_ok,
        "excel_mensaje": excel_msg,
        "mensaje": mensaje,
    })


@app.post("/search")
async def search(
    files: List[UploadFile] = File(default=[]),    # acepta 0..N imágenes bajo el nombre 'files'
    top_k: int = Form(DEFAULT_TOP_K),
    terminales: Optional[int] = Form(None),
    forma: Optional[str] = Form(None),
    tipo_mh: Optional[str] = Form(None),
    rerank: int = Form(1),
    debug: int = Form(0),
):
    # Quitar archivos vacíos que a veces manda el navegador cuando no hay foto
    files = [f for f in files if f.filename]

    if not files and not (terminales or forma or tipo_mh):
        raise HTTPException(
            400, "Sube una foto o aplica al menos un filtro para buscar"
        )
    if len(files) > 8:
        raise HTTPException(400, "Máximo 8 imágenes por búsqueda")

    # ── Búsqueda solo por filtros (sin foto): sin similitud CLIP ─────────
    if not files:
        meta = STATE["meta"]
        filtered = apply_filters(meta, terminales, forma, tipo_mh)
        n_candidatos = len(filtered)

        filtered = filtered.sort_values("ID - Conector catálogo").head(top_k)
        results = [
            {
                "id_conector": int(row["ID - Conector catálogo"]),
                "similitud": None,
                "meta": meta_row_to_dict(row),
            }
            for _, row in filtered.iterrows()
        ]

        return JSONResponse({
            "query_filenames": [],
            "n_imagenes": 0,
            "modos": [],
            "scoring": "solo filtros (sin foto)",
            "filtros_aplicados": {
                "terminales": terminales, "forma": forma, "tipo_mh": tipo_mh
            },
            "n_candidatos": int(n_candidatos),
            "results": results,
            "aviso": None if n_candidatos else (
                "Ningún conector del catálogo cumple esos filtros. Prueba a relajarlos."
            ),
        })

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