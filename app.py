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

from datetime import date, timedelta

import pandas as pd
import psycopg2
import psycopg2.extras
import streamlit as st

st.set_page_config(page_title="Panel Heladería", page_icon="🍦", layout="wide")

# ----------------------------------------------------------------------------
# Base de datos (Postgres en la nube — Supabase)
# ----------------------------------------------------------------------------

def get_conn():
    if "DB_URL" not in st.secrets:
        st.error(
            "Falta configurar la conexión a la base de datos.\n\n"
            "Copia `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml` "
            "y pega ahí tu cadena de conexión de Supabase (clave DB_URL). "
            "Consulta README.md para el paso a paso."
        )
        st.stop()
    return psycopg2.connect(st.secrets["DB_URL"])


def run_query(sql, params=()):
    conn = get_conn()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def execute(sql, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    cur.close()
    conn.close()


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------

def eur(n):
    try:
        return f"{float(n):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def delete_row(tabla, row_id):
    execute(f"DELETE FROM {tabla} WHERE id = %s", (row_id,))
    st.rerun()


def delete_expander(tabla, df, label_col):
    if df.empty:
        return
    with st.expander("🗑️ Eliminar un registro"):
        opciones = {f"{row[label_col]} (id {row['id']})": row["id"] for _, row in df.iterrows()}
        elegido = st.selectbox("Selecciona qué eliminar", list(opciones.keys()), key=f"del_{tabla}")
        if st.button("Eliminar", key=f"delbtn_{tabla}"):
            delete_row(tabla, opciones[elegido])


# ----------------------------------------------------------------------------
# Inicializar BD
# ----------------------------------------------------------------------------
st.title("🍦 Panel de la Heladería")
st.caption("Conectado a la base de datos en la nube — mismo dato desde el móvil, el PC de la tienda y el portátil")

tab_resumen, tab_inv, tab_gastos, tab_precios, tab_facturas, tab_ventas = st.tabs(
    ["📊 Resumen", "📦 Inventario", "🧾 Gastos", "💰 Precios y márgenes", "📄 Facturas", "🗓️ Ventas diarias"]
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

    hoy = date.today()
    mes_actual = hoy.strftime("%Y-%m")
    gasto_mes = 0.0
    if not gastos.empty:
        gasto_mes = gastos[gastos["fecha"].str.startswith(mes_actual)]["importe"].sum()

    ventas_mes = 0.0
    if not ventas.empty:
        ventas_mes = ventas[ventas["fecha"].str.startswith(mes_actual)]["importe"].sum()

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
        enviado = st.form_submit_button("Guardar")
        if enviado and nombre.strip():
            existente = run_query("SELECT id FROM inventario WHERE nombre = %s", (nombre.strip(),))
            if not existente.empty:
                execute(
                    "UPDATE inventario SET stock=%s, unidad=%s, minimo=%s, coste=%s WHERE nombre=%s",
                    (stock, unidad, minimo, coste or None, nombre.strip()),
                )
            else:
                execute(
                    "INSERT INTO inventario (nombre, stock, unidad, minimo, coste) VALUES (%s,%s,%s,%s,%s)",
                    (nombre.strip(), stock, unidad, minimo, coste or None),
                )
            st.rerun()

    delete_expander("inventario", inv, "nombre")

# ----------------------------------------------------------------------------
# GASTOS
# ----------------------------------------------------------------------------
with tab_gastos:
    st.subheader("Proveedores y gastos")
    gastos = run_query("SELECT * FROM gastos ORDER BY fecha DESC")

    if not gastos.empty:
        st.dataframe(
            gastos[["fecha", "proveedor", "concepto", "categoria", "importe"]],
            hide_index=True, use_container_width=True,
        )
    else:
        st.info("Aún no hay gastos registrados.")

    st.markdown("##### Añadir gasto")
    with st.form("form_gasto", clear_on_submit=True):
        c1, c2 = st.columns(2)
        proveedor = c1.text_input("Proveedor")
        concepto = c2.text_input("Concepto")
        c3, c4, c5 = st.columns(3)
        categoria = c3.selectbox("Categoría", ["Materia prima", "Suministros", "Alquiler", "Nóminas", "Otros"])
        importe = c4.number_input("Importe (€)", min_value=0.0, step=0.50)
        fecha = c5.date_input("Fecha", value=date.today())
        enviado = st.form_submit_button("Guardar")
        if enviado and proveedor.strip() and importe > 0:
            execute(
                "INSERT INTO gastos (proveedor, concepto, categoria, importe, fecha) VALUES (%s,%s,%s,%s,%s)",
                (proveedor.strip(), concepto.strip(), categoria, importe, fecha.isoformat()),
            )
            st.rerun()

    delete_expander("gastos", gastos, "proveedor")

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
        enviado = st.form_submit_button("Guardar")
        if enviado and producto.strip() and precio > 0:
            existente = run_query("SELECT id FROM precios WHERE producto = %s", (producto.strip(),))
            if not existente.empty:
                execute("UPDATE precios SET coste=%s, precio=%s WHERE producto=%s", (coste or None, precio, producto.strip()))
            else:
                execute("INSERT INTO precios (producto, coste, precio) VALUES (%s,%s,%s)", (producto.strip(), coste or None, precio))
            st.rerun()

    delete_expander("precios", precios, "producto")

# ----------------------------------------------------------------------------
# FACTURAS
# ----------------------------------------------------------------------------
with tab_facturas:
    st.subheader("Facturas")
    facturas = run_query("SELECT * FROM facturas ORDER BY fecha DESC")

    if not facturas.empty:
        st.dataframe(
            facturas[["fecha", "tipo", "tercero", "numero", "importe", "estado"]],
            hide_index=True, use_container_width=True,
        )
    else:
        st.info("Aún no hay facturas registradas.")

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
        enviado = st.form_submit_button("Guardar")
        if enviado and tercero.strip() and importe > 0:
            execute(
                "INSERT INTO facturas (tipo, tercero, numero, importe, fecha, estado) VALUES (%s,%s,%s,%s,%s,%s)",
                (tipo, tercero.strip(), numero.strip(), importe, fecha.isoformat(), estado),
            )
            st.rerun()

    delete_expander("facturas", facturas, "tercero")

# ----------------------------------------------------------------------------
# VENTAS DIARIAS
# ----------------------------------------------------------------------------
with tab_ventas:
    st.subheader("Ventas diarias")
    ventas = run_query("SELECT * FROM ventas ORDER BY fecha DESC")

    if not ventas.empty:
        st.dataframe(ventas[["fecha", "importe"]], hide_index=True, use_container_width=True)
    else:
        st.info("Aún no hay ventas registradas.")

    st.markdown("##### Añadir una venta")
    with st.form("form_venta", clear_on_submit=True):
        c1, c2 = st.columns(2)
        fecha_v = c1.date_input("Fecha", value=date.today(), key="fecha_venta_unica")
        importe_v = c2.number_input("Total vendido ese día (€)", min_value=0.0, step=10.0)
        enviado = st.form_submit_button("Guardar")
        if enviado and importe_v > 0:
            execute(
                "INSERT INTO ventas (fecha, importe) VALUES (%s,%s) "
                "ON CONFLICT (fecha) DO UPDATE SET importe=EXCLUDED.importe",
                (fecha_v.isoformat(), importe_v),
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

    delete_expander("ventas", ventas, "fecha")

# ----------------------------------------------------------------------------
# EXPORTAR A EXCEL
# ----------------------------------------------------------------------------
st.divider()
st.subheader("📥 Exportar todo a Excel")
if st.button("Generar Excel"):
    conn = get_conn()
    with pd.ExcelWriter("heladeria_export.xlsx", engine="openpyxl") as writer:
        for tabla in ["inventario", "gastos", "precios", "facturas", "ventas"]:
            df = pd.read_sql_query(f"SELECT * FROM {tabla}", conn)
            df.to_excel(writer, sheet_name=tabla, index=False)
    conn.close()
    with open("heladeria_export.xlsx", "rb") as f:
        st.download_button("Descargar heladeria_export.xlsx", f, file_name="heladeria_export.xlsx")
