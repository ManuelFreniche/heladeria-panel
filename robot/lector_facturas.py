"""
Lector de facturas para el robot de correo — 100% gratis, sin IA de pago.
Usa OCR local (Tesseract) + reglas de texto para sacar proveedor, fecha e
importe de los formatos de los proveedores habituales de la heladería.
"""

import re
import unicodedata
from datetime import datetime

import pytesseract
from pdf2image import convert_from_path, convert_from_bytes


def sin_acentos(txt):
    """Quita tildes/diéresis para que las comparaciones no dependan del OCR acertando el acento."""
    return "".join(
        c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn"
    )

# ----------------------------------------------------------------------------
# Proveedores conocidos: palabra clave a buscar en el texto -> nombre limpio
# y categoría por defecto. Se añaden fácilmente más líneas si aparece un
# proveedor nuevo.
# ----------------------------------------------------------------------------
PROVEEDORES_CONOCIDOS = [
    (r"cafes?\s+salvador", "Cafés Salvador e Hijos", "Materia prima"),
    (r"disbesa|ramilo\s*1985", "Disbesa", "Materia prima"),
    (r"supermercados?\s+champion", "Supermercados Champion", "Materia prima"),
    (r"elisabel", "Elisabel Frutos Secos y Golosinas", "Materia prima"),
    (r"ferreteria\s+dial|diaz\s+hernandez", "Ferretería Dial", "Otros"),
    (r"ferreteria\s+la\s+cadena", "Ferretería La Cadena Centro", "Otros"),
    (r"recambios\s+indalo|electro\s+recambios", "Electro Recambios Indalo", "Otros"),
    (r"indalpesa", "Indalpesa", "Materia prima"),
    (r"indalques", "Indalques", "Materia prima"),
    (r"leroy\s*merlin", "Leroy Merlín", "Suministros"),
    (r"panaderia\s+del\s+rosal", "Panadería del Rosal", "Materia prima"),
    (r"comercial\s+dragon", "Comercial Dragon", "Suministros"),
    (r"master\s+gift\s+import|\bmgi\b", "MGI Tiendas", "Suministros"),
    (r"brico\s*depot", "Brico Depot", "Otros"),
    (r"relindas|albiceleste\s+foods", "Relindas / Albiceleste Foods", "Materia prima"),
    (r"gimenez\s+asnar", "Pablo M. Giménez Asnar", "Materia prima"),
    (r"euromania", "Euromania", "Materia prima"),
    (r"sercodi", "Sercodi", "Materia prima"),
    (r"gm\s*cash", "GM Cash", "Materia prima"),
    (r"hogar\s*hotel|hoalve", "Hogar Hotel", "Suministros"),
    (r"barema", "Barema Almería", "Otros"),
]

# Patrones de "total", en orden de prioridad (el primero que aparezca gana)
PATRONES_TOTAL = [
    r"total\s+a\s+pagar[:\s]*([\d.,]+)",
    r"total\s+impuestos\s+inclu[ií]dos[:\s]*([\d.,]+)",
    r"total\s+factura[:\s]*([\d.,]+)",
    r"total\s+eur(?:os)?[:\s]*([\d.,]+)",
    r"total\s+t[il]i?\s*\(eur\)[:\s]*([\d.,]+)",
    r"total[:\s]+([\d.,]+)\s*€",
    r"importe\s+total[:\s]*([\d.,]+)",
]

# Fecha: dd/mm/aaaa, dd-mm-aaaa (con o sin "Fecha:" delante)
PATRON_FECHA = r"fecha\D{0,20}?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"


def ocr_pdf(ruta_pdf, dpi=300):
    """Convierte cada página del PDF (desde un archivo) a imagen y le pasa el OCR."""
    paginas = convert_from_path(ruta_pdf, dpi=dpi)
    return [pytesseract.image_to_string(p, lang="spa") for p in paginas]


def ocr_pdf_bytes(pdf_bytes, dpi=300):
    """Igual que ocr_pdf pero a partir de los bytes del PDF (como llega un adjunto de correo)."""
    paginas = convert_from_bytes(pdf_bytes, dpi=dpi)
    return [pytesseract.image_to_string(p, lang="spa") for p in paginas]


def limpiar_importe(txt):
    """'1.234,56' o '1234.56' -> 1234.56 (float)"""
    txt = txt.strip()
    if "," in txt and "." in txt:
        txt = txt.replace(".", "").replace(",", ".")
    elif "," in txt:
        txt = txt.replace(",", ".")
    try:
        return round(float(txt), 2)
    except ValueError:
        return None


def detectar_proveedor(texto):
    texto_low = sin_acentos(texto.lower())
    for patron, nombre, categoria in PROVEEDORES_CONOCIDOS:
        if re.search(patron, texto_low):
            return nombre, categoria
    return None, "Otros"


def detectar_total(texto):
    texto_low = texto.lower()
    for patron in PATRONES_TOTAL:
        m = re.search(patron, texto_low)
        if m:
            val = limpiar_importe(m.group(1))
            if val:
                return val
    # Red de seguridad 1: número junto a "total" aunque no lleve el símbolo €
    for m in re.finditer(r"total[^\d\n]{0,15}([\d]{1,3}(?:[.,]\d{3})*[.,]\d{2})", texto_low):
        val = limpiar_importe(m.group(1))
        if val:
            return val
    # Red de seguridad 2: coger el número con € más grande de la página
    candidatos = re.findall(r"([\d]{1,3}(?:[.,]\d{3})*[.,]\d{2})\s*€", texto)
    valores = [limpiar_importe(c) for c in candidatos]
    valores = [v for v in valores if v]
    return max(valores) if valores else None


def detectar_fecha(texto):
    # 1) intento normal: "Fecha: dd/mm/aaaa" cerca uno del otro
    m = re.search(PATRON_FECHA, texto, re.IGNORECASE)
    candidatos = []
    if m:
        candidatos.append(m.group(1))
    # 2) red de seguridad: cualquier fecha con pinta válida en el documento
    #    (separador puede salir mal leído por el OCR: /, -, o incluso un espacio)
    for dia, mes, anio in re.findall(r"\b(\d{1,2})[\s/.-](\d{1,2})[\s/.-](\d{2,4})\b", texto):
        try:
            d, mo = int(dia), int(mes)
            if 1 <= d <= 31 and 1 <= mo <= 12:
                a = int(anio) if len(anio) == 4 else 2000 + int(anio)
                if 2020 <= a <= 2035:
                    candidatos.append(f"{dia}/{mes}/{anio}")
        except ValueError:
            continue
    for raw in candidatos:
        raw_norm = raw.replace(" ", "/").replace("-", "/").replace(".", "/")
        for fmt in ("%d/%m/%Y", "%d/%m/%y"):
            try:
                return datetime.strptime(raw_norm, fmt).date().isoformat()
            except ValueError:
                continue
    return None


def analizar_pdf(ruta_pdf):
    """Devuelve una lista de eventos gasto detectados en el PDF (uno por página con datos)."""
    return _eventos_desde_textos(ocr_pdf(ruta_pdf))


def analizar_pdf_bytes(pdf_bytes):
    """Igual que analizar_pdf, pero a partir de los bytes de un adjunto de correo."""
    return _eventos_desde_textos(ocr_pdf_bytes(pdf_bytes))


def _eventos_desde_textos(textos):
    eventos = []
    for texto in textos:
        proveedor, categoria = detectar_proveedor(texto)
        total = detectar_total(texto)
        fecha = detectar_fecha(texto)
        if proveedor and total and fecha:
            eventos.append({
                "proveedor": proveedor,
                "categoria": categoria,
                "importe": total,
                "fecha": fecha,
            })
    return eventos


if __name__ == "__main__":
    import sys
    for ruta in sys.argv[1:]:
        print(f"\n=== {ruta} ===")
        for ev in analizar_pdf(ruta):
            print(ev)
