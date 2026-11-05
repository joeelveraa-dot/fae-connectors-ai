"""
xlsx_direct_writer.py
----------------------
Escribe celdas y filas en catalogo_conectores_completo.xlsx editando
directamente el XML interno del .xlsx (sin Excel/COM y sin pasar por el
ciclo completo de carga/guardado de openpyxl).

Motivo: la columna "Foto" usa la función de Excel "imagen en celda"
(Rich Value / richData). openpyxl no la entiende y la borra al volver a
guardar el archivo completo; Excel-COM sí la respeta, pero requiere
Windows + Excel instalado + sesión de escritorio, lo que no está
disponible en un servidor en la nube.

Este módulo solo lee y reescribe xl/worksheets/sheet1.xml dentro del
.zip; todas las demás partes (incluidas xl/richData/ y xl/media/, donde
viven esas fotos) se copian tal cual, byte a byte, sin abrirlas nunca.
Así es imposible que esta escritura las dañe.

También puede CREAR una foto en celda nueva (add_foto_in_cell), montando
a mano las mismas piezas que usa Excel para "Insertar imagen > Colocar en
celda": un archivo en xl/media/, una relación en richData/richValueRel,
una entrada en rdrichvalue.xml y otra en metadata.xml, enlazadas por la
celda vía su atributo vm=.

Limitaciones deliberadas:
- No toca xl/sharedStrings.xml: todo lo que escribe usa "inline strings"
  (t="inlineStr"), que Excel admite mezclado con el resto de celdas sin
  ningún problema.
- No reordena ni borra filas; solo actualiza celdas de una fila existente
  o añade una fila nueva al final de los datos.
"""

from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path
from typing import Optional


NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _col_index(letters: str) -> int:
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch) - 64)
    return idx


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _xml_unescape(text: str) -> str:
    return (
        text.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
        .replace("&amp;", "&")
    )


def _resolve_sheet_path(zf: zipfile.ZipFile, sheet_name: str) -> str:
    import xml.etree.ElementTree as ET

    NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    wb_xml = ET.fromstring(zf.read("xl/workbook.xml"))
    rels_xml = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {rel.get("Id"): rel.get("Target") for rel in rels_xml}
    for sheet in wb_xml.find("m:sheets", NS):
        if sheet.get("name") == sheet_name:
            target = rid_to_target[sheet.get(f"{NS_R}id")]
            return target if target.startswith("xl/") else "xl/" + target
    raise ValueError(f"Hoja no encontrada: {sheet_name}")


def _resolve_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        ss_xml = zf.read("xl/sharedStrings.xml").decode("utf-8")
    except KeyError:
        return []
    out = []
    for si_match in re.finditer(r"<si>(.*?)</si>", ss_xml, re.DOTALL):
        texts = re.findall(r"<t[^>]*>(.*?)</t>", si_match.group(1), re.DOTALL)
        out.append(_xml_unescape("".join(texts)))
    return out


def _cell_text_value(attrs: str, inner: Optional[str], shared: list[str]) -> Optional[str]:
    """Valor de texto de una celda ya parseada (attrs + contenido interior)."""
    if inner is None:
        return None
    if 't="s"' in attrs:
        m = re.search(r"<v>(.*?)</v>", inner)
        if not m:
            return None
        try:
            return shared[int(m.group(1))]
        except (IndexError, ValueError):
            return None
    if 't="inlineStr"' in attrs:
        m = re.search(r"<t[^>]*>(.*?)</t>", inner, re.DOTALL)
        return _xml_unescape(m.group(1)) if m else ""
    if 't="str"' in attrs or 't="e"' in attrs or "t=" not in attrs:
        m = re.search(r"<v>(.*?)</v>", inner)
        return m.group(1) if m else None
    return None


def _resolve_headers(sheet_xml: str, shared: list[str]) -> dict[str, str]:
    """{nombre_columna: letra} leyendo la fila de cabecera (fila 1)."""
    m = re.search(r'<row r="1"[^>]*>(.*?)</row>', sheet_xml, re.DOTALL)
    if not m:
        return {}
    headers: dict[str, str] = {}
    for cm in re.finditer(
        r'<c r="([A-Z]+)1"([^>]*?)(?:/>|>(.*?)</c>)', m.group(1), re.DOTALL
    ):
        col_letters, attrs, inner = cm.groups()
        name = _cell_text_value(attrs, inner, shared)
        if name:
            headers[name.strip()] = col_letters
    return headers


def _find_row_span(sheet_xml: str, row_num: int):
    m = re.search(rf'<row r="{row_num}"[^>]*>', sheet_xml)
    if not m:
        return None
    close = sheet_xml.find("</row>", m.end())
    if close == -1:
        return None
    return m.start(), close + len("</row>")


def _row_cells(row_xml: str, shared: list[str]) -> dict[str, dict]:
    """{letra_columna: {"style":..., "value":...}} de una fila ya extraída."""
    cells: dict[str, dict] = {}
    for cm in re.finditer(
        r'<c r="([A-Z]+)(\d+)"([^>]*?)(?:/>|>(.*?)</c>)', row_xml, re.DOTALL
    ):
        col_letters, _row, attrs, inner = cm.groups()
        style_m = re.search(r's="(\d+)"', attrs)
        cells[col_letters] = {
            "style": style_m.group(1) if style_m else None,
            "value": _cell_text_value(attrs, inner, shared),
            "attrs": attrs,
        }
    return cells


def _cell_xml(cell_ref: str, value, style: Optional[str]) -> str:
    s_attr = f' s="{style}"' if style else ""
    if isinstance(value, tuple) and len(value) == 2 and value[0] == "__raw__":
        # Celda ya formada del todo (p.ej. la referencia rich-value de una
        # foto en celda): se usa tal cual, sin pasar por el resto de reglas.
        return value[1]
    if value is None or value == "":
        return f'<c r="{cell_ref}"{s_attr}/>'
    if isinstance(value, bool):
        value = "Sí" if value else "No"
    if isinstance(value, (int, float)):
        return f'<c r="{cell_ref}"{s_attr}><v>{value}</v></c>'
    text = _xml_escape(str(value))
    preserve = ' xml:space="preserve"' if text != text.strip() else ""
    return f'<c r="{cell_ref}"{s_attr} t="inlineStr"><is><t{preserve}>{text}</t></is></c>'


def find_row_for_id(sheet_xml: str, shared: list[str], id_conector: int) -> Optional[int]:
    """Busca en la columna A la fila cuyo valor sea `id_conector`."""
    for m in re.finditer(
        r'<c r="A(\d+)"([^>]*?)(?:/>|>(.*?)</c>)', sheet_xml, re.DOTALL
    ):
        row_num, attrs, inner = m.groups()
        if row_num == "1":
            continue
        val = _cell_text_value(attrs, inner, shared)
        if val is None:
            continue
        try:
            if int(float(val)) == id_conector:
                return int(row_num)
        except ValueError:
            continue
    return None


def last_data_row(sheet_xml: str) -> int:
    """Última fila (de verdad, no el 'used range' inflado) con datos en A."""
    last = 1
    for m in re.finditer(r'<c r="A(\d+)"[^>]*?(?:/>|>.*?</c>)', sheet_xml):
        last = max(last, int(m.group(1)))
    return last


def _write_zip_atomic(path: Path, order: list[str], contents: dict[str, bytes], compress: dict[str, int]):
    tmp_path = path.with_name(path.name + ".tmp")
    with zipfile.ZipFile(tmp_path, "w") as zout:
        for name in order:
            zout.writestr(name, contents[name], compress_type=compress.get(name, zipfile.ZIP_DEFLATED))
    os.replace(tmp_path, path)


def set_row_values(
    path: Path,
    sheet_name: str,
    id_conector: int,
    values: dict,
    create_if_missing: bool = False,
) -> tuple[bool, str]:
    """
    Escribe `values` ({"Referencia FAE": "...", "Terminales": 4, ...}) en
    la fila del conector `id_conector`. Si no existe y `create_if_missing`
    es True, añade una fila nueva al final (con el ID incluido).

    Nunca toca la columna "Foto" (ni ninguna otra parte del archivo que
    no sea el texto de sheet1.xml).

    Devuelve (ok, mensaje).
    """
    try:
        with zipfile.ZipFile(path) as zf:
            order = zf.namelist()
            compress = {i.filename: i.compress_type for i in zf.infolist()}
            contents = {n: zf.read(n) for n in order}
            sheet_path = _resolve_sheet_path(zf, sheet_name)
            shared = _resolve_shared_strings(zf)

        sheet_xml = contents[sheet_path].decode("utf-8")
        headers = _resolve_headers(sheet_xml, shared)
        id_header = next(
            (h for h in headers if h.strip().lower().startswith("id") and "conector" in h.lower()
             and "contraconector" not in h.lower()),
            None,
        )
        id_col = headers.get(id_header) if id_header else "A"

        row_num = find_row_for_id(sheet_xml, shared, id_conector)
        if row_num is None and not create_if_missing:
            return False, f"No se encontró el conector #{id_conector} en el Excel"

        if row_num is None:
            prev_row = last_data_row(sheet_xml)
            row_num = prev_row + 1
            existing_cells: dict[str, dict] = {}
            row_attrs = ' spans="1:17"'
            row_exists = False
            values = {**values}
            values.setdefault(id_header or "ID - Conector catálogo", id_conector)
        else:
            span = _find_row_span(sheet_xml, row_num)
            row_xml_old = sheet_xml[span[0]: span[1]]
            row_open_m = re.match(r'(<row r="\d+")([^>]*)>', row_xml_old)
            row_attrs = row_open_m.group(2) if row_open_m else ' spans="1:17"'
            existing_cells = _row_cells(row_xml_old, shared)
            row_exists = True

        for field_name, value in values.items():
            col = headers.get(field_name)
            if col is None:
                continue
            if col == id_col and row_exists:
                # No pisar el ID de una fila que ya existe.
                continue
            style = existing_cells.get(col, {}).get("style")
            existing_cells[col] = {"style": style, "value": value}

        all_cols = sorted(existing_cells.keys(), key=_col_index)
        row_inner = "".join(
            _cell_xml(f"{c}{row_num}", existing_cells[c]["value"], existing_cells[c]["style"])
            for c in all_cols
        )
        new_row_xml = f'<row r="{row_num}"{row_attrs}>{row_inner}</row>'

        if row_exists:
            start, end = _find_row_span(sheet_xml, row_num)
            new_sheet_xml = sheet_xml[:start] + new_row_xml + sheet_xml[end:]
        else:
            # Insertar justo después de la última fila con datos reales
            # (nunca al final absoluto: filas vacías del "used range"
            # inflado pueden llegar hasta la 1048576 y romperían el orden
            # ascendente de <row> que Excel/openpyxl esperan).
            prev_span = _find_row_span(sheet_xml, prev_row)
            if prev_span is not None:
                insert_at = prev_span[1]
            else:
                insert_at = sheet_xml.index("</sheetData>")
            new_sheet_xml = sheet_xml[:insert_at] + new_row_xml + sheet_xml[insert_at:]

        contents[sheet_path] = new_sheet_xml.encode("utf-8")
        _write_zip_atomic(path, order, contents, compress)
        return True, "Excel actualizado"
    except Exception as e:
        return False, f"No se pudo actualizar el Excel: {e}"


def add_foto_in_cell(
    path: Path,
    sheet_name: str,
    id_conector: int,
    image_bytes: bytes,
    image_ext: str = "jpeg",
) -> tuple[bool, str]:
    """
    Inserta `image_bytes` como "imagen en celda" (Rich Value) en la columna
    "Foto" de la fila de `id_conector`, construyendo a mano las mismas
    piezas que crea Excel al usar Insertar imagen > Colocar en celda:
      - un archivo nuevo en xl/media/
      - una relación nueva en xl/richData/richValueRel.xml(.rels)
      - una entrada nueva en xl/richData/rdrichvalue.xml
      - una entrada nueva en xl/metadata.xml (futureMetadata + valueMetadata)
      - la celda en sheet1.xml con el atributo vm= apuntando a esa cadena

    Si la fila ya tenía una foto, las piezas antiguas quedan huérfanas (sin
    referencia) en vez de borrarse: es el mismo comportamiento que tiene
    Excel al reemplazar una imagen así, y no corrompe nada.

    Devuelve (ok, mensaje).
    """
    try:
        with zipfile.ZipFile(path) as zf:
            order = zf.namelist()
            compress = {i.filename: i.compress_type for i in zf.infolist()}
            contents = {n: zf.read(n) for n in order}
            sheet_path = _resolve_sheet_path(zf, sheet_name)
            shared = _resolve_shared_strings(zf)

        sheet_xml = contents[sheet_path].decode("utf-8")
        headers = _resolve_headers(sheet_xml, shared)
        foto_col = headers.get("Foto")
        if foto_col is None:
            return False, "No existe la columna 'Foto' en el Excel"

        row_num = find_row_for_id(sheet_xml, shared, id_conector)
        if row_num is None:
            return False, f"No se encontró el conector #{id_conector} en el Excel"

        # 1) Nuevo archivo de imagen
        existing_nums = [
            int(m.group(1))
            for n in order
            for m in [re.search(r"xl/media/image(\d+)\.\w+", n)]
            if m
        ]
        new_num = (max(existing_nums) if existing_nums else 0) + 1
        media_name = f"xl/media/image{new_num}.{image_ext}"

        # 2) Nueva relación en richValueRel.xml.rels
        rels_path = "xl/richData/_rels/richValueRel.xml.rels"
        rels_xml = contents[rels_path].decode("utf-8")
        existing_rids = [int(m.group(1)) for m in re.finditer(r'Id="rId(\d+)"', rels_xml)]
        new_rid = f"rId{(max(existing_rids) if existing_rids else 0) + 1}"
        new_rel = (
            f'<Relationship Id="{new_rid}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            f'Target="../media/image{new_num}.{image_ext}"/>'
        )
        rels_xml = rels_xml.replace("</Relationships>", new_rel + "</Relationships>")

        # 3) Nueva entrada en richValueRel.xml (su posición es el índice
        #    que referenciará rdrichvalue.xml)
        rvr_path = "xl/richData/richValueRel.xml"
        rvr_xml = contents[rvr_path].decode("utf-8")
        new_rel_index = len(re.findall(r"<rel\b", rvr_xml))
        rvr_xml = rvr_xml.replace(
            "</richValueRels>", f'<rel r:id="{new_rid}"/></richValueRels>'
        )

        # 4) Nueva entrada en rdrichvalue.xml
        rdv_path = "xl/richData/rdrichvalue.xml"
        rdv_xml = contents[rdv_path].decode("utf-8")
        new_rv_index = len(re.findall(r"<rv\b", rdv_xml))
        rdv_xml = rdv_xml.replace(
            "</rvData>", f'<rv s="0"><v>{new_rel_index}</v><v>5</v></rv></rvData>'
        )
        rdv_xml = re.sub(
            r'(<rvData[^>]*\bcount=")(\d+)(")',
            lambda m: f"{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}",
            rdv_xml,
            count=1,
        )

        # 5) Nueva entrada en metadata.xml: futureMetadata y valueMetadata
        meta_path = "xl/metadata.xml"
        meta_xml = contents[meta_path].decode("utf-8")

        fm_match = re.search(
            r'(<futureMetadata name="XLRICHVALUE"[^>]*>)(.*?)(</futureMetadata>)',
            meta_xml,
            re.DOTALL,
        )
        fm_open, fm_body, fm_close = fm_match.groups()
        new_fm_index = len(re.findall(r"<bk>", fm_body))
        new_fm_bk = (
            '<bk><extLst><ext uri="{3e2802c4-a4d2-4d8b-9148-e3be6c30e623}">'
            f'<xlrd:rvb i="{new_rv_index}"/></ext></extLst></bk>'
        )
        fm_open_new = re.sub(r'count="\d+"', f'count="{new_fm_index + 1}"', fm_open)
        meta_xml = meta_xml.replace(
            fm_match.group(0), fm_open_new + fm_body + new_fm_bk + fm_close
        )

        vm_match = re.search(
            r"(<valueMetadata[^>]*>)(.*?)(</valueMetadata>)", meta_xml, re.DOTALL
        )
        vm_open, vm_body, vm_close = vm_match.groups()
        new_fm_bk_count = len(re.findall(r"<bk>", vm_body))
        new_vm = new_fm_bk_count + 1  # vm en las celdas es 1-indexado
        new_vm_bk = f'<bk><rc t="1" v="{new_fm_index}"/></bk>'
        vm_open_new = re.sub(r'count="\d+"', f'count="{new_fm_bk_count + 1}"', vm_open)
        meta_xml = meta_xml.replace(
            vm_match.group(0), vm_open_new + vm_body + new_vm_bk + vm_close
        )

        # 6) Celda "Foto" en sheet1.xml, apuntando al nuevo vm=
        span = _find_row_span(sheet_xml, row_num)
        row_xml_old = sheet_xml[span[0]: span[1]]
        row_open_m = re.match(r'(<row r="\d+")([^>]*)>', row_xml_old)
        row_attrs = row_open_m.group(2) if row_open_m else ' spans="1:17"'
        existing_cells = _row_cells(row_xml_old, shared)

        style = existing_cells.get(foto_col, {}).get("style")
        cell_ref = f"{foto_col}{row_num}"
        s_attr = f' s="{style}"' if style else ""
        raw_cell = f'<c r="{cell_ref}"{s_attr} t="e" vm="{new_vm}"><v>#VALUE!</v></c>'
        existing_cells[foto_col] = {"style": style, "value": ("__raw__", raw_cell)}

        all_cols = sorted(existing_cells.keys(), key=_col_index)
        row_inner = "".join(
            _cell_xml(f"{c}{row_num}", existing_cells[c]["value"], existing_cells[c]["style"])
            for c in all_cols
        )
        new_row_xml = f'<row r="{row_num}"{row_attrs}>{row_inner}</row>'
        new_sheet_xml = sheet_xml[: span[0]] + new_row_xml + sheet_xml[span[1]:]

        # Escribir todas las piezas modificadas + el archivo de imagen nuevo
        contents[sheet_path] = new_sheet_xml.encode("utf-8")
        contents[rels_path] = rels_xml.encode("utf-8")
        contents[rvr_path] = rvr_xml.encode("utf-8")
        contents[rdv_path] = rdv_xml.encode("utf-8")
        contents[meta_path] = meta_xml.encode("utf-8")
        contents[media_name] = image_bytes
        order = order + [media_name]
        compress[media_name] = zipfile.ZIP_DEFLATED

        _write_zip_atomic(path, order, contents, compress)
        return True, "Foto añadida al Excel"
    except Exception as e:
        return False, f"No se pudo añadir la foto al Excel: {e}"
