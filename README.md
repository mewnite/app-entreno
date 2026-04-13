# Gim Routine — Registro de entrenamientos con Google Sheets y OCR

Proyecto en Python (Kivy) para registrar entrenamientos y exportarlos a Google Sheets. Incluye extracción de texto (OCR) desde imágenes.

Requisitos
- Python 3.8+
- Tesseract OCR instalado (sistema):
  - Windows: instalar desde https://github.com/tesseract-ocr/tesseract
  - Asegurarse de que `tesseract.exe` esté en el PATH o configurar `pytesseract.pytesseract.tesseract_cmd`.

Dependencias (instalar):

```bash
pip install -r requirements.txt
```

Ejecución local
1. Coloca tu archivo de credenciales de servicio (JSON) en una ruta conocida.
2. Ejecuta el app:

```bash
python main.py
```

Configuración de Google Sheets
- En [Google Cloud Console](https://console.cloud.google.com) crea un proyecto y habilita la API de Google Sheets y Drive.
- Crea una cuenta de servicio y descarga el JSON.
- En la app, ve a `Configuración` y pega la ruta al JSON y el nombre del Spreadsheet.
- Si la hoja no existe, la app la creará automáticamente (la creará en el Drive de la cuenta de servicio).

Problema común: Error 403 relacionado con Google Drive API

- Mensaje típico: "Google Drive API has not been used in project ... before or it is disabled. Enable it by visiting https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=..."

Soluciones:

- Habilitar APIs en Cloud Console:
  1. Abrir https://console.developers.google.com/apis/library/drive.googleapis.com y hacer clic en "Enable".
  2. Abrir https://console.developers.google.com/apis/library/sheets.googleapis.com y hacer clic en "Enable".
  3. Esperar 1-5 minutos y volver a probar la app.

- Usar gcloud (si tienes Cloud SDK instalado):

```bash
gcloud services enable drive.googleapis.com sheets.googleapis.com --project=YOUR_PROJECT_ID
```

- Alternativa manual (evita que la app tenga que crear la hoja):
  1. Crea un nuevo Spreadsheet en Google Drive con el nombre deseado.
  2. Comparte el documento con la cuenta de servicio (abre el JSON de credenciales y copia el valor de `client_email`, p. ej. `my-service@project.iam.gserviceaccount.com`). Dale permisos de edición.
  3. En la app, configura ese nombre de Spreadsheet en `Configuración`.

Estas opciones permiten resolver el error 403 y asegurar que la app pueda crear o escribir en el Spreadsheet.

OCR
- Debes instalar Tesseract en el sistema.
- La app usa `pytesseract` y `opencv-python` para preprocesar la imagen y extraer texto.

Empaquetado
- APK (Android):
  - Recomendado: usar Buildozer en una máquina Linux. En Windows usa WSL2 (Ubuntu) o una máquina virtual Linux.
  - Consideraciones importantes sobre OCR:
    - `pytesseract` depende del binario Tesseract del sistema; no funcionará directamente en Android sin integrar `tess-two` o una solución nativa (compleja).
    - Recomendaciones:
      1. Opción simple: mantener OCR en el dispositivo sólo como selección de imagen y enviar la imagen a un servicio (tu servidor o Google Vision API) para procesar el OCR en la nube.
      2. Opción nativa: integrar `tess-two` (requiere crear una receta/paquete NDK y configurar Java/Kotlin; trabajo avanzado).

  - Pasos resumidos para crear APK (WSL2 / Linux):
    1. Instala dependencias del sistema (Ubuntu ejemplo):

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv git build-essential openjdk-11-jdk unzip
sudo apt install -y zlib1g-dev libncurses5 libncurses5-dev libgstreamer1.0-dev
```

    2. Instala Buildozer y dependencias de Python en un virtualenv:

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install buildozer
pip install cython
```

    3. En tu proyecto (en WSL2): copia `buildozer.spec` (ya incluido) y ajusta campos como `package.domain`, `package.name`, `android.permissions` y `requirements`.

    4. Ejecuta la compilación (esto descargará SDK/NDK y puede tardar bastante):

```bash
buildozer -v android debug
```

    5. Instala el APK en el dispositivo conectado via ADB:

```bash
buildozer android deploy run
```

  - Notas sobre dependencias incompatibles:
    - `opencv-python` y `pytesseract` no están disponibles por pip en Android sin recetas; si quieres OCR totalmente offline en Android necesitarás integrar `tess-two` y recetas para OpenCV (trabajo avanzado). Para una versión rápida en Android usa OCR en la nube.

- EXE (Windows):
  - Usar PyInstaller:

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed main.py
```

Limitaciones y notas
- Empaquetado para Android requiere ajuste (plyer para cámara, permisos y pruebas en dispositivo).
- La cuenta de servicio crea el Spreadsheet en su Drive; para usar con una cuenta personal, comparte el documento con tu usuario.
- En móviles la captura de cámara idealmente se realiza con Plyer; en este ejemplo mostramos la selección de imagen como método universal.

Archivos principales
- `main.py` — App Kivy y pantallas
- `sheets.py` — Integración con Google Sheets (gspread)
- `ocr.py` — Funciones OCR y mapeo de texto
- `utils.py` — Configuración (config.json)
- `requirements.txt` — Dependencias
