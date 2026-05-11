"""
PARCHE para search_api.py
=========================
Añade un endpoint /by_id que busca un conector por su ID de catálogo
o por su Referencia FAE, y devuelve el conector + hasta N similares
(misma forma + mismo número de terminales).

INSTRUCCIONES:
  1. Abre search_api.py en tu editor.
  2. Pega el bloque de abajo justo ANTES del endpoint @app.post("/search").
  3. Guarda.
  4. Reinicia uvicorn.

No requiere tocar nada más. No rompe ningún endpoint existente.
"""

# ════════════════════════════════════════════════════════════════════════
# AÑADIR ESTE BLOQUE COMPLETO A search_api.py
# (antes de "@app.post('/search')")
# ════════════════════════════════════════════════════════════════════════

@app.get("/by_id")
def by_id(q: str, include_similar: int = 1, max_similar: int = 12):
    """
    Búsqueda directa por ID de conector catálogo o Referencia FAE.
    No usa embeddings: consulta solo los metadatos.

    Query params:
      q                 -> texto a buscar (ID numérico o Referencia FAE)
      include_similar   -> 1 para devolver también conectores similares (por forma + terminales)
      max_similar       -> máximo de similares a devolver

    Respuesta:
      {
        "match": { "id_conector": 955, "meta": {...} } | null,
        "match_type": "id" | "ref_fae" | null,
        "similares": [ { "id_conector": 936, "meta": {...} }, ... ],
        "n_similares": 12
      }
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
        # Filtrar: misma Forma y mismos Terminales
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