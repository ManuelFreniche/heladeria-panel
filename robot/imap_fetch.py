"""
Robot de correo — revisa una bandeja de Gmail por IMAP (gratis, con
contraseña de aplicación, sin API de pago), lee los PDF adjuntos con OCR
local, y deja lo que detecta en la tabla "gastos_pendientes" para que lo
revises y apruebes tú desde la app.

Nunca escribe en la tabla "gastos" directamente.

Variables de entorno necesarias (se configuran como Secrets en GitHub Actions):
    IMAP_EMAIL           tu cuenta de Gmail (o alias dedicado a facturas)
    IMAP_APP_PASSWORD    contraseña de aplicación de 16 caracteres (no tu contraseña normal)
    DB_URL               misma cadena de conexión de Supabase que usa la app

Ejecutar manualmente:
    python3 robot/imap_fetch.py
"""

import email
import imaplib
import os
import sys
from email.header import decode_header

import psycopg2
import psycopg2.extras

sys.path.insert(0, os.path.dirname(__file__))
from lector_facturas import ocr_pdf_bytes, detectar_por_pagina, _completo  # noqa: E402

IMAP_SERVIDOR = "imap.gmail.com"
CARPETA = "INBOX"
ETIQUETA_PROCESADO = "RobotFacturas/Procesado"  # etiqueta de Gmail para marcar ya vistos


def get_conn():
    return psycopg2.connect(os.environ["DB_URL"])


def decodificar(valor):
    if not valor:
        return ""
    partes = decode_header(valor)
    return "".join(
        (p.decode(enc or "utf-8", errors="ignore") if isinstance(p, bytes) else p)
        for p, enc in partes
    )


def conectar_imap():
    email_cuenta = os.environ["IMAP_EMAIL"]
    password = os.environ["IMAP_APP_PASSWORD"]
    imap = imaplib.IMAP4_SSL(IMAP_SERVIDOR)
    imap.login(email_cuenta, password)
    return imap


def asegurar_etiqueta(imap):
    typ, carpetas = imap.list()
    nombres = [c.decode() for c in carpetas] if carpetas else []
    if not any(ETIQUETA_PROCESADO in n for n in nombres):
        imap.create(f'"{ETIQUETA_PROCESADO}"')


def buscar_correos_con_pdf(imap):
    imap.select(CARPETA)
    # Solo correos no leídos, para no reprocesar todo cada vez
    typ, datos = imap.search(None, "UNSEEN")
    return datos[0].split() if datos and datos[0] else []


def extraer_adjuntos_pdf(msg):
    adjuntos = []
    for parte in msg.walk():
        nombre = parte.get_filename()
        if nombre and nombre.lower().endswith(".pdf"):
            adjuntos.append((decodificar(nombre), parte.get_payload(decode=True)))
    return adjuntos


def guardar_pendiente(conn, evento, asunto, remitente, nombre_archivo, pdf_bytes):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO gastos_pendientes
            (proveedor, concepto, categoria, importe, fecha,
             origen_asunto, origen_remitente, archivo_nombre, adjunto, adjunto_tipo)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            evento.get("proveedor"),
            f"Detectado automáticamente del correo: {asunto}",
            evento.get("categoria", "Otros"),
            evento.get("importe"),
            evento.get("fecha"),
            asunto,
            remitente,
            nombre_archivo,
            psycopg2.Binary(pdf_bytes),
            "application/pdf",
        ),
    )
    conn.commit()
    cur.close()


def marcar_procesado(imap, num_correo):
    imap.copy(num_correo, ETIQUETA_PROCESADO)
    imap.store(num_correo, "+FLAGS", "\\Seen")


def main():
    conn = get_conn()
    imap = conectar_imap()
    asegurar_etiqueta(imap)

    nums = buscar_correos_con_pdf(imap)
    print(f"Correos sin leer encontrados: {len(nums)}")

    total_detectados = 0
    total_parciales = 0
    for num in nums:
        typ, datos_msg = imap.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(datos_msg[0][1])
        asunto = decodificar(msg.get("Subject"))
        remitente = decodificar(msg.get("From"))
        print(f"\nCorreo: '{asunto}' (de {remitente})")

        adjuntos = extraer_adjuntos_pdf(msg)
        if not adjuntos:
            print("  Sin PDF adjunto — se deja como no leído, no se toca.")
            continue

        print(f"  {len(adjuntos)} PDF adjunto(s): {[n for n, _ in adjuntos]}")

        for nombre_archivo, pdf_bytes in adjuntos:
            try:
                textos = ocr_pdf_bytes(pdf_bytes)
                detecciones = detectar_por_pagina(textos)
            except Exception as e:
                print(f"  ! No se pudo procesar {nombre_archivo}: {e}")
                detecciones = []

            for d in detecciones:
                guardar_pendiente(conn, d, asunto, remitente, nombre_archivo, pdf_bytes)
                if _completo(d):
                    total_detectados += 1
                    print(f"  + Detectado: {d['proveedor']} · {d['importe']}€ · {d['fecha']}")
                else:
                    total_parciales += 1
                    print(f"  ~ Lectura incompleta (proveedor={d['proveedor']}, total={d['importe']}, "
                          f"fecha={d['fecha']}) — guardado en blanco para completar a mano")

        marcar_procesado(imap, num)

    print(f"\nDetecciones completas: {total_detectados}")
    print(f"Pendientes en blanco (a completar a mano): {total_parciales}")
    imap.logout()
    conn.close()


if __name__ == "__main__":
    main()
