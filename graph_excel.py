"""
graph_excel.py
---------------
Sincroniza el Excel real de conectores con SharePoint/OneDrive vía Microsoft
Graph, para cuando la app corre fuera del PC de jnunezv (p.ej. en Azure) y no
tiene montada la carpeta de OneDrive local.

Reutiliza la misma aplicación de Microsoft Entra ID ya registrada y con
consentimiento de administrador concedido para copilot-fae (GRAPH_TENANT_ID /
GRAPH_CLIENT_ID / GRAPH_CLIENT_SECRET), así que no hace falta pedir nada
nuevo a IT.

El resto de la app sigue trabajando siempre sobre una copia LOCAL del Excel
(mismo código de xlsx_direct_writer.py de siempre); este módulo solo se
encarga de traer la copia más reciente antes de leer, y de subir la copia
modificada después de escribir.
"""
import os
import time
from pathlib import Path

import requests
from msal import ConfidentialClientApplication

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 5

GRAPH_UPN = os.getenv("GRAPH_EXCEL_UPN", "j.nunez@fae.es")
GRAPH_EXCEL_PATH = os.getenv(
    "GRAPH_EXCEL_PATH", "Documentos/catalogo_conectores_completo.xlsx"
)

_CONTENT_URL = (
    f"https://graph.microsoft.com/v1.0/users/{GRAPH_UPN}"
    f"/drive/root:/{GRAPH_EXCEL_PATH}:/content"
)
_UPLOAD_SESSION_URL = (
    f"https://graph.microsoft.com/v1.0/users/{GRAPH_UPN}"
    f"/drive/root:/{GRAPH_EXCEL_PATH}:/createUploadSession"
)

_CHUNK_SIZE = 10 * 1024 * 1024  # múltiplo de 320 KiB, recomendado por Graph

_token_cache = {"token": None, "exp": 0.0}


def enabled() -> bool:
    """True si hay credenciales de Graph configuradas (vía variables de entorno)."""
    return all(
        os.getenv(k) for k in ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET")
    )


def _token() -> str:
    now = time.time()
    if _token_cache["token"] and _token_cache["exp"] - 60 > now:
        return _token_cache["token"]

    app = ConfidentialClientApplication(
        client_id=os.environ["GRAPH_CLIENT_ID"],
        authority=f"https://login.microsoftonline.com/{os.environ['GRAPH_TENANT_ID']}",
        client_credential=os.environ["GRAPH_CLIENT_SECRET"],
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        raise RuntimeError(f"Graph auth error: {result}")

    _token_cache["token"] = result["access_token"]
    _token_cache["exp"] = now + float(result.get("expires_in", 3600))
    return _token_cache["token"]


def download(dest_path: Path) -> None:
    """Descarga la última versión del Excel real a `dest_path` (sobrescribe).

    La red saliente de Azure hacia Graph corta la conexión a media descarga
    de vez en cuando (nos pasó: "Connection broken: IncompleteRead"), así
    que se reintenta unas pocas veces antes de rendirse."""
    headers = {"Authorization": f"Bearer {_token()}"}
    last_err = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            r = requests.get(_CONTENT_URL, headers=headers, timeout=60)
            r.raise_for_status()
            dest_path.write_bytes(r.content)
            return
        except Exception as e:
            last_err = e
            if attempt < RETRY_ATTEMPTS:
                print(f"  ! descarga de Graph falló (intento {attempt}/{RETRY_ATTEMPTS}): {e}")
                time.sleep(RETRY_BACKOFF_SECONDS)
    raise last_err


def upload(src_path: Path) -> None:
    """Sube `src_path` como nueva versión del Excel real (createUploadSession,
    porque el fichero pesa más de los 4 MB que admite un PUT simple)."""
    headers = {"Authorization": f"Bearer {_token()}"}
    r = requests.post(
        _UPLOAD_SESSION_URL,
        headers=headers,
        json={"item": {"@microsoft.graph.conflictBehavior": "replace"}},
        timeout=30,
    )
    r.raise_for_status()
    upload_url = r.json()["uploadUrl"]

    data = src_path.read_bytes()
    size = len(data)
    for start in range(0, size, _CHUNK_SIZE):
        end = min(start + _CHUNK_SIZE, size)
        chunk = data[start:end]
        chunk_headers = {
            "Content-Length": str(len(chunk)),
            "Content-Range": f"bytes {start}-{end - 1}/{size}",
        }
        last_err = None
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                resp = requests.put(upload_url, headers=chunk_headers, data=chunk, timeout=120)
                resp.raise_for_status()
                last_err = None
                break
            except Exception as e:
                last_err = e
                if attempt < RETRY_ATTEMPTS:
                    print(f"  ! subida de bloque a Graph falló (intento {attempt}/{RETRY_ATTEMPTS}): {e}")
                    time.sleep(RETRY_BACKOFF_SECONDS)
        if last_err:
            raise last_err
