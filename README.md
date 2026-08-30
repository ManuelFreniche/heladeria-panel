# Panel Heladería — puesta en marcha (una sola vez)

Al terminar esto tendrás: el PC de la tienda (Windows), tu portátil (Linux) y
tu móvil, los tres viendo y editando la MISMA información, en tiempo real,
estés donde estés.

---

## Paso 1 — Crear la base de datos en la nube (gratis, ~5 min)

1. Ve a https://supabase.com y crea una cuenta gratis (puedes usar tu Google).
2. "New project". Ponle nombre, por ejemplo `heladeria`. Elige una contraseña
   para la base de datos y **guárdala**, la necesitas luego.
3. Espera 1-2 minutos a que se cree el proyecto.
4. Menú izquierdo → **SQL Editor** → "New query". Abre el archivo
   `esquema.sql` de esta carpeta, copia todo su contenido, pégalo ahí y
   pulsa **Run**. Esto crea las tablas (solo hace falta hacerlo una vez).
5. Menú izquierdo → **Project Settings** → **Database** → busca
   "Connection string" → pestaña **Session pooler** → copia esa cadena.
   Sustituye `[YOUR-PASSWORD]` por la contraseña que pusiste en el paso 2.

Esa cadena (`postgresql://...`) es la que conecta la app a tu base de datos.

## Paso 2 — Probarlo en tu portátil (Linux) o en el PC de Windows

1. Copia toda esta carpeta al ordenador.
2. Dentro de la carpeta `.streamlit`, copia `secrets.toml.example` y
   renómbralo a `secrets.toml`.
3. Abre `secrets.toml` y pega tu cadena de conexión real del Paso 1.
4. Abre una terminal (o PowerShell/CMD en Windows) en la carpeta del proyecto:
   ```
   pip install -r requirements.txt
   streamlit run app.py
   ```
5. Se abre solo en el navegador. Añade algo de prueba.

Repite el Paso 2 en el otro ordenador (mismo `secrets.toml`, misma cadena) y
comprueba que ves ahí lo que acabas de añadir. Eso confirma que ya están
sincronizados.

## Paso 3 — Tenerlo también en el móvil (URL fija, sin instalar nada)

1. Crea una cuenta gratis en https://github.com si no tienes.
2. Crea un repositorio nuevo, por ejemplo `heladeria-panel`, y sube esta
   carpeta **sin el archivo `secrets.toml`** (el `.gitignore` ya se encarga
   de que no se suba por error).
3. Ve a https://share.streamlit.io, entra con tu cuenta de GitHub.
4. "New app" → elige tu repositorio `heladeria-panel` → archivo principal
   `app.py` → **Deploy**.
5. Antes de que termine de arrancar (o después, en "Settings" → "Secrets"),
   pega el contenido de tu `secrets.toml` real (la línea `DB_URL = "..."`).
6. Te da una URL tipo `https://tu-app.streamlit.app`. Ábrela desde el
   navegador del móvil y guárdala como acceso directo en la pantalla de
   inicio — así se comporta casi como una app.

A partir de aquí: cualquier cosa que añadas desde el móvil, el PC de la
tienda, o tu portátil, aparece en los otros dos porque los tres leen y
escriben la misma base de datos en Supabase.

---

### Notas
- El plan gratuito de Supabase es más que suficiente para el volumen de datos
  de una heladería.
- Si algún día quieres dejar de depender de internet en la tienda, el mismo
  `app.py` puede seguir corriendo en local — solo cambiaría de dónde saca los
  datos si en el futuro quieres una copia offline.
- `Exportar todo a Excel` (dentro de la app) te da un `.xlsx` con las 5 tablas
  siempre que lo necesites.
