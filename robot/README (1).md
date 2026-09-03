# Robot de correo — puesta en marcha

El robot revisa tu correo cada día, lee los PDF adjuntos con OCR gratuito, y
deja lo que detecta en la pestaña **🤖 Revisión del robot** de la app. Nunca
guarda nada él solo — siempre lo apruebas o corriges tú.

## Recomendación antes de empezar

Si puedes, usa un **alias o cuenta de correo dedicada solo a facturas**
(por ejemplo, reenvía ahí las facturas de tus proveedores, o pide que te las
manden directamente a esa dirección) en vez de tu correo personal. Así el
robot solo ve facturas, nunca correo personal, y es más fácil de gestionar.
Si no quieres crear una nueva, puedes usar tu Gmail normal sin problema.

## Paso 1 — Crear la base de datos del robot (una vez)

En Supabase → **SQL Editor** → pega el contenido de `robot/esquema_robot.sql`
→ **Run**. Esto crea la tabla `gastos_pendientes` donde el robot deja sus
detecciones.

## Paso 2 — Generar la contraseña de aplicación de Gmail

1. Ve a tu cuenta de Google → **Seguridad**.
2. Activa la **verificación en dos pasos** si no la tienes ya (obligatorio
   para poder crear contraseñas de aplicación).
3. Busca **Contraseñas de aplicaciones** (puedes escribirlo en el buscador
   de ajustes si no lo encuentras a simple vista).
4. Crea una nueva, ponle un nombre como "Robot heladería", y copia el
   código de 16 caracteres que te da. Esa es tu `IMAP_APP_PASSWORD` — no es
   tu contraseña normal de Gmail, y solo sirve para esto.

## Paso 3 — Añadir los secretos en GitHub

En tu repositorio de GitHub (`heladeria-panel`) → **Settings** → **Secrets
and variables** → **Actions** → **New repository secret**. Crea estos tres:

| Nombre | Valor |
|---|---|
| `IMAP_EMAIL` | Tu correo de Gmail (o el alias dedicado) |
| `IMAP_APP_PASSWORD` | El código de 16 caracteres del Paso 2 |
| `DB_URL` | La misma cadena de conexión de Supabase que ya usas en la app |

## Paso 4 — Subir los archivos del robot

```bash
cd ~/heladeria-panel
git add robot/ .github/workflows/robot-facturas.yml
git commit -m "Añadir robot de lectura de correo"
git push
```

## Paso 5 — Probarlo

En GitHub, ve a la pestaña **Actions** de tu repositorio → selecciona
"Robot de facturas por correo" → **Run workflow** → **Run workflow** (botón
verde). Tarda 1-2 minutos. Cuando termine, revisa la pestaña **🤖 Revisión
del robot** en tu app — si tenías algún correo sin leer con un PDF adjunto,
debería aparecer ahí.

A partir de aquí, se ejecuta solo cada día a las 6:00 UTC (sobre las 8:00 de
la mañana en España en verano), sin que tengas que hacer nada.

## Notas importantes

- El robot solo mira correos **sin leer**. Los que ya proceses, márcalos
  como leídos para que no se repitan cada día.
- Cada correo procesado se copia a una carpeta nueva de Gmail llamada
  **RobotFacturas/Procesado**, así tienes un archivo aparte de lo que el
  robot ya ha visto.
- El OCR gratuito no es perfecto (te enseñé ejemplos reales donde se
  equivoca). Por eso **siempre** hay que repasar la pestaña de revisión
  antes de aprobar — revisa sobre todo el importe, que es lo que más falla.
- Si añades un proveedor nuevo que el robot no reconoce, dímelo con un
  ejemplo de factura suya y le añado sus reglas al lector
  (`robot/lector_facturas.py`).
