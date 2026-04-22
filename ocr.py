import os
import re

# NOTE:
# On Android (Buildozer), `opencv-python` and `pytesseract` are typically unavailable unless you
# add custom recipes/native integration. Import them lazily so the app can start without OCR.
try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None

try:
    import pytesseract  # type: ignore
except Exception:  # pragma: no cover
    pytesseract = None

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


def extract_text_from_image(path: str) -> str:
    if cv2 is None or pytesseract is None or Image is None:
        raise RuntimeError(
            "OCR no disponible en este dispositivo/build. "
            "En Android, `opencv-python` y `pytesseract` no vienen incluidos por defecto: "
            "usa OCR en la nube o integra una solución nativa (ML Kit / tess-two)."
        )
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    # Read with OpenCV
    img = cv2.imread(path)
    if img is None:
        raise ValueError('No se pudo leer la imagen')
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # simple preprocessing
    gray = cv2.medianBlur(gray, 3)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Save temp image for pytesseract
    tmp = path + '.ocr.png'
    cv2.imwrite(tmp, th)
    try:
        text = pytesseract.image_to_string(Image.open(tmp), lang='spa+eng')
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass
    return text


def parse_ocr_to_fields(text: str) -> dict:
    # Try to parse text in simple key: value lines
    fields = {
        'Ejercicio': '', 'Series': '', 'Método': '', 'Tiempo': '', 'Reps Semana Anterior': '',
        'Reps': '', 'Peso': '', 'RIR': '', 'Anotaciones': ''
    }
    if not text:
        return fields
    # Normalize
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        # key: value
        m = re.match(r'^(Ejercicio|Exercise|Ejer):\s*(.+)$', line, re.I)
        if m:
            fields['Ejercicio'] = m.group(2)
            continue
        m = re.match(r'^(Series|Series:|Sets):\s*(.+)$', line, re.I)
        if m:
            fields['Series'] = m.group(2)
            continue
        m = re.match(r'^(Método|Metodo|Method):\s*(.+)$', line, re.I)
        if m:
            fields['Método'] = m.group(2)
            continue
        m = re.match(r'^(Tiempo|Time):\s*(.+)$', line, re.I)
        if m:
            fields['Tiempo'] = m.group(2)
            continue
        m = re.match(r'^(Reps Semana Anterior|Prev Reps|Prev):\s*(.+)$', line, re.I)
        if m:
            fields['Reps Semana Anterior'] = m.group(2)
            continue
        m = re.match(r'^(Reps|Repeticiones|Reps:):\s*(.+)$', line, re.I)
        if m:
            fields['Reps'] = m.group(2)
            continue
        m = re.match(r'^(Peso|Weight):\s*(.+)$', line, re.I)
        if m:
            fields['Peso'] = m.group(2)
            continue
        m = re.match(r'^(RIR):\s*(.+)$', line, re.I)
        if m:
            fields['RIR'] = m.group(2)
            continue
    # If obvious mapping not found, populate first lines heuristically
    if not fields['Ejercicio'] and lines:
        fields['Ejercicio'] = lines[0]
    # Find numbers for series/reps/peso if missing
    nums = re.findall(r"\d+", text)
    if not fields['Series'] and nums:
        fields['Series'] = nums[0]
    if not fields['Reps'] and len(nums) > 1:
        fields['Reps'] = nums[1]
    if not fields['Peso'] and len(nums) > 2:
        fields['Peso'] = nums[2]
    # Anotaciones: remaining lines
    if len(lines) > 1 and not fields['Anotaciones']:
        fields['Anotaciones'] = '\n'.join(lines[1:])

    return fields
