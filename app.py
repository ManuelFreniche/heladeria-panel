"""
Panel de gestión — Alpino's Heladería
Aplicación en Python (Streamlit) conectada a una base de datos en la nube
(Postgres, gratis en Supabase). Se ejecuta igual en Windows, Linux o desplegada
para el móvil — todos los sitios leen y escriben la MISMA base de datos, así
que lo que cambias en uno aparece al momento en los demás.

CONFIGURACIÓN (una sola vez, ver README.md para el paso a paso completo):
    1. Crea un proyecto gratis en https://supabase.com y copia su cadena de
       conexión (Connection string, modo "Session pooler").
    2. Pega esa cadena en .streamlit/secrets.toml (copia el archivo
       secrets.toml.example y rellénalo). NUNCA subas ese archivo a GitHub.
    3. Ejecuta una vez el SQL de esquema.sql en el "SQL Editor" de Supabase.

CÓMO EJECUTAR EN LOCAL (Windows, Linux, o donde sea):
    pip install -r requirements.txt
    streamlit run app.py

CÓMO TENERLO EN EL MÓVIL:
    Despliega este mismo código en https://share.streamlit.io (gratis, conecta
    tu cuenta de GitHub). Te da una URL fija que puedes abrir desde cualquier
    navegador de móvil. Ver README.md para el paso a paso.
"""

from datetime import date, datetime, timedelta
import base64
import json

import pandas as pd
import psycopg2
import psycopg2.extras
import psycopg2.pool
import requests
import streamlit as st

st.set_page_config(page_title="Panel Heladería", page_icon="🍦", layout="wide")

# ----------------------------------------------------------------------------
# Base de datos (Postgres en la nube — Supabase)
# ----------------------------------------------------------------------------

# Base de datos (Postgres en la nube — Supabase)
# ----------------------------------------------------------------------------

@st.cache_resource
def get_pool():
    """Un pool de conexiones reutilizables, creado una sola vez por sesión de la
    app (no una conexión nueva en cada clic — eso era gran parte de la lentitud)."""
    if "DB_URL" not in st.secrets:
        st.error(
            "Falta configurar la conexión a la base de datos.\n\n"
            "Copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` "
            "y pega ahí tu cadena de conexión de Supabase (clave DB_URL). "
            "Consulta README.md para el paso a paso."
        )
        st.stop()
    return psycopg2.pool.ThreadedConnectionPool(1, 8, st.secrets["DB_URL"])


@st.cache_data(ttl=20, show_spinner=False)
def run_query(sql, params=()):
    """Lecturas cacheadas 20s: si dos pestañas piden lo mismo en ese rato, no
    se repite el viaje a Supabase. Se invalida sola en cuanto se guarda algo
    (ver execute más abajo), así nunca se ve un dato desactualizado tras
    guardar."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        df = pd.read_sql_query(sql, conn, params=params)
    finally:
        pool.putconn(conn)
    # Postgres devuelve las columnas DATE como objetos date/Timestamp, no texto.
    # Las normalizamos a texto "YYYY-MM-DD" para que el resto del código
    # (comparaciones, .str.startswith, etc.) funcione siempre igual.
    if "fecha" in df.columns:
        df["fecha"] = df["fecha"].astype(str)
    return df


def execute(sql, params=()):
    pool = get_pool()
    conn = pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        filas_afectadas = cur.rowcount
        conn.commit()
        cur.close()
    finally:
        pool.putconn(conn)
    run_query.clear()  # cualquier guardado invalida la caché de lecturas
    return filas_afectadas


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------

def eur(n):
    try:
        return f"{float(n):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def parsear_fecha_segura(valor, por_defecto=None):
    """Intenta convertir un valor de fecha (string 'YYYY-MM-DD', None, 'NaT', 'nan', etc.)
    en un date de Python. Si no se puede, devuelve por_defecto (hoy si no se indica otro)."""
    try:
        return datetime.strptime(str(valor), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return por_defecto if por_defecto is not None else date.today()


def nombre_mes(m):
    y, mm = m.split("-")
    nombres = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
               "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    return f"{nombres[int(mm)]} {y}"


def selector_mes(df, key, con_todos=True):
    """Desplegable de mes a partir de las fechas presentes en df. Se abre por
    defecto en el mes actual (o el más reciente con datos si el actual está
    vacío). Devuelve 'YYYY-MM', o None si se elige 'Todos los meses'."""
    meses_con_datos = sorted(
        set(df["fecha"].str[:7]) if not df.empty else set(), reverse=True
    )
    mes_actual = date.today().strftime("%Y-%m")
    opciones = meses_con_datos if meses_con_datos else [mes_actual]
    if mes_actual not in opciones:
        opciones = [mes_actual] + opciones
    etiquetas = {m: nombre_mes(m) for m in opciones}
    if con_todos:
        opciones = ["__todos__"] + opciones
        etiquetas["__todos__"] = "Todos los meses"
    elegido = st.selectbox(
        "Mes a consultar", opciones, format_func=lambda m: etiquetas[m], key=key,
    )
    return None if elegido == "__todos__" else elegido


def filtrar_por_mes(df, mes):
    if mes is None or df.empty:
        return df
    return df[df["fecha"].str.startswith(mes)]


def borrar_multiple(tabla, df, hacer_etiqueta):
    """Expander con selección múltiple para borrar tantos registros como se quiera de golpe."""
    if df.empty:
        return
    with st.expander(f"🗑️ Eliminar registros ({len(df)} en total)"):
        opciones = {f"{hacer_etiqueta(row)} (id {row['id']})": row["id"] for _, row in df.iterrows()}
        elegidos = st.multiselect(
            "Selecciona uno o varios para eliminar", list(opciones.keys()), key=f"delmulti_{tabla}"
        )
        if elegidos and st.button(f"🗑️ Eliminar {len(elegidos)} seleccionado(s)", key=f"delmultibtn_{tabla}"):
            ids = [opciones[e] for e in elegidos]
            execute(f"DELETE FROM {tabla} WHERE id = ANY(%s)", (ids,))
            st.success(f"Eliminados {len(ids)} registros.")
            st.rerun()


def subir_adjunto_widget(key):
    """Muestra el selector de archivo y devuelve (bytes, nombre, tipo_mime) o (None, None, None)."""
    archivo = st.file_uploader(
        "📎 Adjuntar foto o archivo (opcional)",
        type=["jpg", "jpeg", "png", "webp", "pdf"],
        key=key,
    )
    if archivo:
        return archivo.getvalue(), archivo.name, (archivo.type or "application/octet-stream")
    return None, None, None


def mostrar_adjuntos(tabla, label_col):
    """Expander para ver/descargar los adjuntos guardados en una tabla."""
    dfa = run_query(
        f"SELECT id, {label_col} AS etiqueta, adjunto, adjunto_nombre, adjunto_tipo "
        f"FROM {tabla} WHERE adjunto IS NOT NULL ORDER BY id DESC"
    )
    if dfa.empty:
        return
    with st.expander(f"📎 Ver archivos adjuntos ({len(dfa)})"):
        opciones = {f"{row['etiqueta']} (id {row['id']})": i for i, row in dfa.iterrows()}
        elegido = st.selectbox("Elige un registro", list(opciones.keys()), key=f"ver_adj_{tabla}")
        fila = dfa.iloc[opciones[elegido]]
        contenido = bytes(fila["adjunto"])
        tipo = fila["adjunto_tipo"] or ""
        nombre = fila["adjunto_nombre"] or "adjunto"
        if tipo.startswith("image/"):
            st.image(contenido, caption=nombre, use_container_width=True)
        else:
            st.info(f"Archivo: {nombre} ({tipo})")
        st.download_button("⬇️ Descargar", contenido, file_name=nombre, key=f"dl_{tabla}_{fila['id']}")


# ----------------------------------------------------------------------------
# Lectura de facturas con IA (visión)
# ----------------------------------------------------------------------------

FACTURA_SYSTEM_PROMPT = """Eres el motor de lectura de documentos de una heladería en España. \
Te paso la foto de un ticket, factura, albarán, ticket Z de caja, o una nota manuscrita con \
el total vendido en un día. Léelo y devuelve un array JSON con uno o varios eventos, cada uno \
con un campo "tipo": "gasto", "factura" o "venta".

- gasto: {{ "proveedor", "concepto", "categoria" ("Materia prima"|"Suministros"|"Alquiler"|"Nóminas"|"Otros"), "importe" (número), "fecha" (YYYY-MM-DD) }}
- factura: {{ "tipo_factura" ("Emitida"|"Recibida"), "tercero", "numero" (opcional), "importe" (número), "fecha" (YYYY-MM-DD), "estado" ("Pendiente"|"Pagada") }}
- venta: {{ "fecha" (YYYY-MM-DD), "importe" (número) }} — usa esto para tickets Z, cierres de caja, \
resúmenes de TPV, o cualquier nota que indique el total vendido/facturado en un día concreto.

Usa "factura" solo si el documento es claramente una factura formal con número de factura. \
Para tickets de compra normales (algo que la heladería COMPRA a un proveedor), usa "gasto". \
Para un documento que muestra lo que la heladería VENDIÓ o INGRESÓ en un día, usa "venta". \
Si la foto trae varios días (por ejemplo una lista de importes con fechas, o una tabla), \
genera un evento "venta" por cada día distinto. \
Si no se ve la fecha con claridad, usa {today}. \
Devuelve SOLO el array JSON, sin texto ni bloques de código markdown alrededor."""


def analizar_imagen_factura(image_bytes, media_type, today):
    if "ANTHROPIC_API_KEY" not in st.secrets:
        raise RuntimeError(
            "Falta configurar ANTHROPIC_API_KEY en secrets.toml. "
            "Consigue una clave gratuita en https://console.anthropic.com/settings/keys"
        )
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    headers = {
        "x-api-key": st.secrets["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    es_pdf = media_type == "application/pdf"
    bloque_documento = (
        {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}}
        if es_pdf
        else {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}}
    )
    payload = {
        "model": "claude-sonnet-5",
        "max_tokens": 1024,
        "system": FACTURA_SYSTEM_PROMPT.format(today=today),
        "messages": [
            {
                "role": "user",
                "content": [
                    bloque_documento,
                    {"type": "text", "text": "Extrae los datos de este ticket o factura."},
                ],
            }
        ],
    }
    r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    texto = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text")
    limpio = texto.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(limpio)
    if not isinstance(parsed, list):
        parsed = [parsed]
    return parsed


# ----------------------------------------------------------------------------
st.title("🍦 Panel de la Heladería")
st.caption("Conectado a la base de datos en la nube — mismo dato desde el móvil, el PC de la tienda y el portátil")

tab_resumen, tab_inv, tab_gastos, tab_precios, tab_facturas, tab_ventas, tab_subir, tab_robot = st.tabs(
    ["📊 Resumen", "📦 Inventario", "🧾 Gastos", "💰 Precios y márgenes", "📄 Facturas", "🗓️ Ventas diarias", "📸 Subir factura", "🤖 Revisión del robot"]
)

# ----------------------------------------------------------------------------
# RESUMEN
# ----------------------------------------------------------------------------
with tab_resumen:
    inv = run_query("SELECT * FROM inventario")
    gastos = run_query("SELECT * FROM gastos")
    precios = run_query("SELECT * FROM precios")
    facturas = run_query("SELECT * FROM facturas")
    ventas = run_query("SELECT * FROM ventas ORDER BY fecha")

    stock_bajo = inv[inv["stock"] <= inv["minimo"]] if not inv.empty else inv

    # Meses disponibles según gastos y ventas juntos, para poder mirar cualquiera
    # (no solo el mes en curso, que casi siempre estará vacío al empezar).
    df_para_meses = pd.concat([gastos[["fecha"]], ventas[["fecha"]]]) if not gastos.empty or not ventas.empty else gastos
    mes_elegido = selector_mes(df_para_meses, key="mes_resumen", con_todos=False)

    gasto_mes = 0.0
    if not gastos.empty:
        gasto_mes = gastos[gastos["fecha"].str.startswith(mes_elegido)]["importe"].sum()

    ventas_mes = 0.0
    if not ventas.empty:
        ventas_mes = ventas[ventas["fecha"].str.startswith(mes_elegido)]["importe"].sum()

    con_coste = precios[(precios["coste"].notna()) & (precios["coste"] > 0)] if not precios.empty else precios
    margen_medio = None
    if not con_coste.empty:
        margen_medio = (((con_coste["precio"] - con_coste["coste"]) / con_coste["precio"]) * 100).mean()

    pendientes = facturas[facturas["estado"] == "Pendiente"] if not facturas.empty else facturas

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Ventas del mes", eur(ventas_mes))
    c2.metric("Gasto del mes", eur(gasto_mes))
    c3.metric("Beneficio bruto mes", eur(ventas_mes - gasto_mes))
    c4.metric("Margen medio", f"{margen_medio:.0f} %" if margen_medio is not None else "—")
    c5.metric("Facturas pendientes", len(pendientes) if not pendientes.empty else 0)

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("⚠️ Stock por debajo del mínimo")
        if stock_bajo is not None and not stock_bajo.empty:
            st.dataframe(
                stock_bajo[["nombre", "stock", "unidad", "minimo"]],
                hide_index=True, use_container_width=True,
            )
        else:
            st.success("Todo el inventario está en orden.")

    with col_b:
        st.subheader("📈 Ventas últimos 14 días")
        if not ventas.empty:
            v = ventas.copy()
            v["fecha"] = pd.to_datetime(v["fecha"])
            v = v.set_index("fecha").sort_index().tail(14)
            st.bar_chart(v["importe"])
        else:
            st.info("Aún no hay ventas registradas.")

# ----------------------------------------------------------------------------
# INVENTARIO
# ----------------------------------------------------------------------------
with tab_inv:
    st.subheader("Inventario")
    inv = run_query("SELECT * FROM inventario ORDER BY nombre")

    if not inv.empty:
        show = inv.copy()
        show["⚠️"] = show.apply(lambda r: "🔴" if r["stock"] <= r["minimo"] else "", axis=1)
        st.dataframe(
            show[["⚠️", "nombre", "stock", "unidad", "minimo", "coste"]],
            hide_index=True, use_container_width=True,
        )
    else:
        st.info("Aún no hay artículos en el inventario.")

    st.markdown("##### Añadir o actualizar artículo")
    st.caption("Si el nombre ya existe, se actualiza su stock en vez de duplicarlo.")
    with st.form("form_inv", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        nombre = c1.text_input("Producto")
        stock = c2.number_input("Stock actual", min_value=0.0, step=1.0)
        unidad = c3.selectbox("Unidad", ["kg", "L", "ud"])
        minimo = c4.number_input("Mínimo", min_value=0.0, step=1.0)
        coste = st.number_input("Coste unitario (€, opcional)", min_value=0.0, step=0.10)
        adj_bytes, adj_nombre, adj_tipo = subir_adjunto_widget("adj_inv")
        enviado = st.form_submit_button("Guardar")
        if enviado and nombre.strip():
            existente = run_query("SELECT id FROM inventario WHERE nombre = %s", (nombre.strip(),))
            if not existente.empty:
                execute(
                    "UPDATE inventario SET stock=%s, unidad=%s, minimo=%s, coste=%s WHERE nombre=%s",
                    (stock, unidad, minimo, coste or None, nombre.strip()),
                )
                if adj_bytes:
                    execute(
                        "UPDATE inventario SET adjunto=%s, adjunto_nombre=%s, adjunto_tipo=%s WHERE nombre=%s",
                        (psycopg2.Binary(adj_bytes), adj_nombre, adj_tipo, nombre.strip()),
                    )
            else:
                execute(
                    "INSERT INTO inventario (nombre, stock, unidad, minimo, coste, adjunto, adjunto_nombre, adjunto_tipo) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        nombre.strip(), stock, unidad, minimo, coste or None,
                        psycopg2.Binary(adj_bytes) if adj_bytes else None, adj_nombre, adj_tipo,
                    ),
                )
            st.rerun()

    borrar_multiple("inventario", inv, lambda r: f"{r['nombre']} · {r['stock']} {r['unidad']}")
    mostrar_adjuntos("inventario", "nombre")

# ----------------------------------------------------------------------------
# GASTOS
# ----------------------------------------------------------------------------
with tab_gastos:
    st.subheader("Proveedores y gastos")
    gastos = run_query("SELECT * FROM gastos ORDER BY fecha DESC")

    mes_gastos = selector_mes(gastos, key="mes_gastos")
    gastos_vista = filtrar_por_mes(gastos, mes_gastos)

    if not gastos_vista.empty:
        st.caption(f"Total {nombre_mes(mes_gastos) if mes_gastos else 'de todos los meses'}: "
                   f"{eur(gastos_vista['importe'].sum())} ({len(gastos_vista)} gastos)")
        st.dataframe(
            gastos_vista[["fecha", "proveedor", "concepto", "categoria", "importe"]],
            hide_index=True, use_container_width=True,
        )
    else:
        st.info("No hay gastos en este mes." if mes_gastos else "Aún no hay gastos registrados.")

    st.markdown("##### Añadir gasto")
    with st.form("form_gasto", clear_on_submit=True):
        c1, c2 = st.columns(2)
        proveedor = c1.text_input("Proveedor")
        concepto = c2.text_input("Concepto")
        c3, c4, c5 = st.columns(3)
        categoria = c3.selectbox("Categoría", ["Materia prima", "Suministros", "Alquiler", "Nóminas", "Otros"])
        importe = c4.number_input("Importe (€)", min_value=0.0, step=0.50)
        fecha = c5.date_input("Fecha", value=date.today())
        adj_bytes, adj_nombre, adj_tipo = subir_adjunto_widget("adj_gasto")
        enviado = st.form_submit_button("Guardar")
        if enviado and proveedor.strip() and importe > 0:
            filas = execute(
                "INSERT INTO gastos (proveedor, concepto, categoria, importe, fecha, adjunto, adjunto_nombre, adjunto_tipo) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (proveedor, importe, fecha) DO NOTHING",
                (
                    proveedor.strip(), concepto.strip(), categoria, importe, fecha.isoformat(),
                    psycopg2.Binary(adj_bytes) if adj_bytes else None, adj_nombre, adj_tipo,
                ),
            )
            if filas == 0:
                st.warning("Ya existe un gasto igual (mismo proveedor, importe y fecha) — no se ha duplicado.")
            else:
                st.rerun()

    borrar_multiple("gastos", gastos, lambda r: f"{r['proveedor']} · {eur(r['importe'])} · {r['fecha']}")
    mostrar_adjuntos("gastos", "proveedor")

# ----------------------------------------------------------------------------
# PRECIOS Y MÁRGENES
# ----------------------------------------------------------------------------
with tab_precios:
    st.subheader("Márgenes y precios")
    precios = run_query("SELECT * FROM precios ORDER BY producto")

    if not precios.empty:
        show = precios.copy()
        def calc_margen(r):
            if r["coste"] and r["coste"] > 0 and r["precio"] > 0:
                return round(((r["precio"] - r["coste"]) / r["precio"]) * 100, 1)
            return None
        show["margen %"] = show.apply(calc_margen, axis=1)
        st.dataframe(
            show[["producto", "coste", "precio", "margen %"]],
            hide_index=True, use_container_width=True,
        )
    else:
        st.info("Aún no hay productos con precio.")

    st.markdown("##### Añadir o actualizar producto")
    with st.form("form_precio", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        producto = c1.text_input("Producto")
        coste = c2.number_input("Coste (€, opcional)", min_value=0.0, step=0.10)
        precio = c3.number_input("Precio de venta (€)", min_value=0.0, step=0.10)
        adj_bytes, adj_nombre, adj_tipo = subir_adjunto_widget("adj_precio")
        enviado = st.form_submit_button("Guardar")
        if enviado and producto.strip() and precio > 0:
            existente = run_query("SELECT id FROM precios WHERE producto = %s", (producto.strip(),))
            if not existente.empty:
                execute("UPDATE precios SET coste=%s, precio=%s WHERE producto=%s", (coste or None, precio, producto.strip()))
                if adj_bytes:
                    execute(
                        "UPDATE precios SET adjunto=%s, adjunto_nombre=%s, adjunto_tipo=%s WHERE producto=%s",
                        (psycopg2.Binary(adj_bytes), adj_nombre, adj_tipo, producto.strip()),
                    )
            else:
                execute(
                    "INSERT INTO precios (producto, coste, precio, adjunto, adjunto_nombre, adjunto_tipo) VALUES (%s,%s,%s,%s,%s,%s)",
                    (producto.strip(), coste or None, precio, psycopg2.Binary(adj_bytes) if adj_bytes else None, adj_nombre, adj_tipo),
                )
            st.rerun()

    borrar_multiple("precios", precios, lambda r: f"{r['producto']} · {eur(r['precio'])}")
    mostrar_adjuntos("precios", "producto")

# ----------------------------------------------------------------------------
# FACTURAS
# ----------------------------------------------------------------------------
with tab_facturas:
    st.subheader("Facturas")
    facturas = run_query("SELECT * FROM facturas ORDER BY fecha DESC")

    mes_facturas = selector_mes(facturas, key="mes_facturas")
    facturas_vista = filtrar_por_mes(facturas, mes_facturas)

    if not facturas_vista.empty:
        st.caption(f"Total {nombre_mes(mes_facturas) if mes_facturas else 'de todos los meses'}: "
                   f"{eur(facturas_vista['importe'].sum())} ({len(facturas_vista)} facturas)")
        st.dataframe(
            facturas_vista[["fecha", "tipo", "tercero", "numero", "importe", "estado"]],
            hide_index=True, use_container_width=True,
        )
    else:
        st.info("No hay facturas en este mes." if mes_facturas else "Aún no hay facturas registradas.")

    st.markdown("##### Añadir factura")
    with st.form("form_factura", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        tipo = c1.selectbox("Tipo", ["Emitida", "Recibida"])
        tercero = c2.text_input("Cliente / Proveedor")
        numero = c3.text_input("Nº factura (opcional)")
        c4, c5, c6 = st.columns(3)
        importe = c4.number_input("Importe (€)", min_value=0.0, step=0.50)
        fecha = c5.date_input("Fecha", value=date.today())
        estado = c6.selectbox("Estado", ["Pendiente", "Pagada"])
        adj_bytes, adj_nombre, adj_tipo = subir_adjunto_widget("adj_factura")
        enviado = st.form_submit_button("Guardar")
        if enviado and tercero.strip() and importe > 0:
            filas = execute(
                "INSERT INTO facturas (tipo, tercero, numero, importe, fecha, estado, adjunto, adjunto_nombre, adjunto_tipo) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (tercero, importe, fecha) DO NOTHING",
                (
                    tipo, tercero.strip(), numero.strip(), importe, fecha.isoformat(), estado,
                    psycopg2.Binary(adj_bytes) if adj_bytes else None, adj_nombre, adj_tipo,
                ),
            )
            if filas == 0:
                st.warning("Ya existe una factura igual (mismo cliente/proveedor, importe y fecha) — no se ha duplicado.")
            else:
                st.rerun()

    borrar_multiple("facturas", facturas, lambda r: f"{r['tercero']} · {eur(r['importe'])} · {r['fecha']}")
    mostrar_adjuntos("facturas", "tercero")

# ----------------------------------------------------------------------------
# VENTAS DIARIAS
# ----------------------------------------------------------------------------
with tab_ventas:
    st.subheader("Ventas diarias")
    ventas = run_query("SELECT * FROM ventas ORDER BY fecha DESC")

    mes_ventas = selector_mes(ventas, key="mes_ventas")
    ventas_vista = filtrar_por_mes(ventas, mes_ventas)

    if not ventas_vista.empty:
        st.caption(f"Total {nombre_mes(mes_ventas) if mes_ventas else 'de todos los meses'}: "
                   f"{eur(ventas_vista['importe'].sum())} ({len(ventas_vista)} días)")
        st.dataframe(ventas_vista[["fecha", "importe"]], hide_index=True, use_container_width=True)
    else:
        st.info("No hay ventas en este mes." if mes_ventas else "Aún no hay ventas registradas.")

    st.markdown("##### Añadir una venta")
    with st.form("form_venta", clear_on_submit=True):
        c1, c2 = st.columns(2)
        fecha_v = c1.date_input("Fecha", value=date.today(), key="fecha_venta_unica")
        importe_v = c2.number_input("Total vendido ese día (€)", min_value=0.0, step=10.0)
        adj_bytes, adj_nombre, adj_tipo = subir_adjunto_widget("adj_venta")
        enviado = st.form_submit_button("Guardar")
        if enviado and importe_v > 0:
            execute(
                "INSERT INTO ventas (fecha, importe, adjunto, adjunto_nombre, adjunto_tipo) VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT (fecha) DO UPDATE SET importe=EXCLUDED.importe, "
                "adjunto=COALESCE(EXCLUDED.adjunto, ventas.adjunto), "
                "adjunto_nombre=COALESCE(EXCLUDED.adjunto_nombre, ventas.adjunto_nombre), "
                "adjunto_tipo=COALESCE(EXCLUDED.adjunto_tipo, ventas.adjunto_tipo)",
                (
                    fecha_v.isoformat(), importe_v,
                    psycopg2.Binary(adj_bytes) if adj_bytes else None, adj_nombre, adj_tipo,
                ),
            )
            st.rerun()

    st.markdown("##### Cargar varios días de golpe")
    st.caption("Útil para poner al día varios días seguidos. Escribe un importe por línea, empezando por el más antiguo, terminando hoy.")
    with st.form("form_ventas_lote", clear_on_submit=True):
        fecha_inicio = st.date_input("Fecha del primer importe de la lista", value=date.today() - timedelta(days=5))
        texto = st.text_area("Importes, uno por línea", placeholder="900\n800\n900\n1300\n1200\n900")
        enviado = st.form_submit_button("Guardar lote")
        if enviado and texto.strip():
            lineas = [l.strip().replace(",", ".") for l in texto.strip().splitlines() if l.strip()]
            f = fecha_inicio
            guardadas = 0
            for l in lineas:
                try:
                    importe = float(l)
                except ValueError:
                    continue
                execute(
                    "INSERT INTO ventas (fecha, importe) VALUES (%s,%s) "
                    "ON CONFLICT (fecha) DO UPDATE SET importe=EXCLUDED.importe",
                    (f.isoformat(), importe),
                )
                f += timedelta(days=1)
                guardadas += 1
            st.success(f"Guardadas {guardadas} ventas, del {fecha_inicio.isoformat()} en adelante.")
            st.rerun()

    borrar_multiple("ventas", ventas, lambda r: f"{r['fecha']} · {eur(r['importe'])}")
    mostrar_adjuntos("ventas", "fecha")

# ----------------------------------------------------------------------------
# SUBIR FACTURA (lectura con IA)
# ----------------------------------------------------------------------------
with tab_subir:
    st.subheader("Subir foto de ticket, factura o cierre de caja")
    st.caption(
        "Sube una o varias fotos. Una IA las lee y prepara gastos, facturas o ventas del día — "
        "revisas la vista previa y confirmas antes de que se guarde nada."
    )

    if "revision_facturas" not in st.session_state:
        st.session_state.revision_facturas = []

    archivos = st.file_uploader(
        "Fotos o PDFs (puedes seleccionar varios a la vez)",
        type=["jpg", "jpeg", "png", "webp", "pdf"],
        accept_multiple_files=True,
    )

    if archivos and st.button("🔍 Analizar fotos", type="primary"):
        hoy = date.today().isoformat()
        nuevos = []
        errores = []
        barra = st.progress(0.0, text="Leyendo fotos…")
        for i, archivo in enumerate(archivos):
            media_type = archivo.type or "image/jpeg"
            try:
                items = analizar_imagen_factura(archivo.getvalue(), media_type, hoy)
                for it in items:
                    it["_origen"] = archivo.name
                    it["_keep"] = True
                    nuevos.append(it)
            except Exception as e:
                errores.append(f"{archivo.name}: {e}")
            barra.progress((i + 1) / len(archivos), text=f"Leyendo fotos… ({i + 1}/{len(archivos)})")
        barra.empty()
        st.session_state.revision_facturas = nuevos
        for err in errores:
            st.error(f"No se pudo leer {err}")

    if st.session_state.revision_facturas:
        st.markdown("##### Revisa antes de guardar")
        for idx, it in enumerate(st.session_state.revision_facturas):
            c1, c2 = st.columns([5, 1])
            with c1:
                if it.get("tipo") == "factura":
                    titulo = it.get("tercero", "—")
                    detalle = f"Factura {it.get('tipo_factura', '')} · nº {it.get('numero', '—')} · {it.get('estado', '')} · {eur(it.get('importe'))} · {it.get('fecha', '—')}"
                elif it.get("tipo") == "venta":
                    titulo = f"Venta del {it.get('fecha', '—')}"
                    detalle = f"Ingreso del día · {eur(it.get('importe'))}"
                else:
                    titulo = it.get("proveedor", "—")
                    detalle = f"Gasto · {it.get('concepto', '')} · {it.get('categoria', '')} · {eur(it.get('importe'))} · {it.get('fecha', '—')}"
                st.markdown(f"**{titulo}** — {it.get('_origen', '')}")
                st.caption(detalle)
            with c2:
                it["_keep"] = st.checkbox("Guardar", value=it.get("_keep", True), key=f"keep_{idx}")

        colb1, colb2 = st.columns(2)
        if colb1.button("✅ Confirmar y guardar todo", type="primary"):
            guardados = 0
            duplicados = 0
            for it in st.session_state.revision_facturas:
                if not it.get("_keep"):
                    continue
                if it.get("tipo") == "factura":
                    filas = execute(
                        "INSERT INTO facturas (tipo, tercero, numero, importe, fecha, estado) VALUES (%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT (tercero, importe, fecha) DO NOTHING",
                        (
                            it.get("tipo_factura", "Recibida"),
                            it.get("tercero", ""),
                            it.get("numero", ""),
                            it.get("importe", 0),
                            it.get("fecha", date.today().isoformat()),
                            it.get("estado", "Pendiente"),
                        ),
                    )
                elif it.get("tipo") == "venta":
                    filas = execute(
                        "INSERT INTO ventas (fecha, importe) VALUES (%s,%s) "
                        "ON CONFLICT (fecha) DO UPDATE SET importe=EXCLUDED.importe",
                        (it.get("fecha", date.today().isoformat()), it.get("importe", 0)),
                    )
                else:
                    filas = execute(
                        "INSERT INTO gastos (proveedor, concepto, categoria, importe, fecha) VALUES (%s,%s,%s,%s,%s) "
                        "ON CONFLICT (proveedor, importe, fecha) DO NOTHING",
                        (
                            it.get("proveedor", ""),
                            it.get("concepto", ""),
                            it.get("categoria", "Otros"),
                            it.get("importe", 0),
                            it.get("fecha", date.today().isoformat()),
                        ),
                    )
                if filas and filas > 0:
                    guardados += 1
                else:
                    duplicados += 1
            st.session_state.revision_facturas = []
            if guardados:
                st.success(f"Guardados {guardados} registros nuevos.")
            if duplicados:
                st.warning(f"{duplicados} ya existían (mismo importe y fecha) y no se han duplicado.")
            st.rerun()
        if colb2.button("Descartar todo"):
            st.session_state.revision_facturas = []
            st.rerun()

# ----------------------------------------------------------------------------
# REVISIÓN DEL ROBOT DE CORREO
# ----------------------------------------------------------------------------
with tab_robot:
    st.subheader("Detecciones del robot de correo")
    st.caption(
        "El robot lee tu correo y deja aquí lo que detecta en cada PDF. Nunca guarda nada "
        "solo en Gastos — revisa cada uno, corrige si hace falta, y aprueba o descarta."
    )

    pendientes = run_query(
        "SELECT * FROM gastos_pendientes WHERE estado = 'Pendiente' ORDER BY detectado_en DESC"
    )

    if pendientes.empty:
        st.info("No hay detecciones pendientes de revisar ahora mismo.")
    else:
        st.caption(f"{len(pendientes)} pendientes de revisar")
        for _, fila in pendientes.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 2])
                with c1:
                    st.markdown(f"📎 **{fila['archivo_nombre'] or 'archivo'}**")
                    st.caption(f"De: {fila['origen_remitente'] or '—'}")
                    st.caption(f"Asunto: {fila['origen_asunto'] or '—'}")
                    if fila["adjunto"] is not None:
                        st.download_button(
                            "⬇️ Ver PDF original", bytes(fila["adjunto"]),
                            file_name=fila["archivo_nombre"] or "factura.pdf",
                            key=f"ver_pdf_{fila['id']}",
                        )
                with c2:
                    proveedor_ed = st.text_input("Proveedor", value=fila["proveedor"] or "", key=f"prov_{fila['id']}")
                    categoria_ed = st.selectbox(
                        "Categoría", ["Materia prima", "Suministros", "Alquiler", "Nóminas", "Otros"],
                        index=["Materia prima", "Suministros", "Alquiler", "Nóminas", "Otros"].index(fila["categoria"])
                        if fila["categoria"] in ["Materia prima", "Suministros", "Alquiler", "Nóminas", "Otros"] else 0,
                        key=f"cat_{fila['id']}",
                    )
                    importe_ed = st.number_input(
                        "Importe (€)", min_value=0.0, step=0.10,
                        value=float(fila["importe"]) if pd.notna(fila["importe"]) else 0.0,
                        key=f"imp_{fila['id']}",
                    )
                    fecha_ed = st.date_input(
                        "Fecha",
                        value=parsear_fecha_segura(fila["fecha"]),
                        key=f"fecha_{fila['id']}",
                    )

                colb1, colb2 = st.columns(2)
                if colb1.button("✅ Aprobar y guardar en Gastos", key=f"aprobar_{fila['id']}", type="primary"):
                    execute(
                        "INSERT INTO gastos (proveedor, concepto, categoria, importe, fecha, adjunto, adjunto_tipo) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (proveedor, importe, fecha) DO NOTHING",
                        (
                            proveedor_ed.strip(), fila["concepto"], categoria_ed, importe_ed, fecha_ed.isoformat(),
                            fila["adjunto"], fila["adjunto_tipo"],
                        ),
                    )
                    execute("UPDATE gastos_pendientes SET estado='Aprobado' WHERE id=%s", (fila["id"],))
                    st.rerun()
                if colb2.button("❌ Descartar", key=f"descartar_{fila['id']}"):
                    execute("UPDATE gastos_pendientes SET estado='Rechazado' WHERE id=%s", (fila["id"],))
                    st.rerun()

# ----------------------------------------------------------------------------
# EXPORTAR A EXCEL
# ----------------------------------------------------------------------------
st.divider()
st.subheader("📥 Exportar todo a Excel")
if st.button("Generar Excel"):
    pool = get_pool()
    conn = pool.getconn()
    try:
        with pd.ExcelWriter("heladeria_export.xlsx", engine="openpyxl") as writer:
            for tabla in ["inventario", "gastos", "precios", "facturas", "ventas"]:
                df = pd.read_sql_query(f"SELECT * FROM {tabla}", conn)
                df.to_excel(writer, sheet_name=tabla, index=False)
    finally:
        pool.putconn(conn)
    with open("heladeria_export.xlsx", "rb") as f:
        st.download_button("Descargar heladeria_export.xlsx", f, file_name="heladeria_export.xlsx")
