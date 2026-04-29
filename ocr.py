import base64
import json
import os
import re

import requests
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials

from utils import get_asset_path, read_android_content_uri

# NOTE:
# On Android/iOS, `opencv-python` and `pytesseract` are typically unavailable unless you
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


VISION_SCOPES = ['https://www.googleapis.com/auth/cloud-platform']
VISION_URL = 'https://vision.googleapis.com/v1/images:annotate'


def extract_text_with_cloud_vision(path: str, creds_path: str) -> str:
    if not creds_path:
        raise RuntimeError(
            'No hay credenciales configuradas para OCR móvil. '
            'Importá primero el JSON de Google en Configuración.'
        )

    resolved_creds = get_asset_path(creds_path)
    if resolved_creds.startswith('content://'):
        creds_info = json.loads(read_android_content_uri(resolved_creds))
        creds = Credentials.from_service_account_info(creds_info, scopes=VISION_SCOPES)
    else:
        creds = Credentials.from_service_account_file(resolved_creds, scopes=VISION_SCOPES)

    creds.refresh(Request())

    with open(path, 'rb') as file_obj:
        image_content = base64.b64encode(file_obj.read()).decode('utf-8')

    response = requests.post(
        VISION_URL,
        headers={'Authorization': f'Bearer {creds.token}'},
        json={
            'requests': [
                {
                    'image': {'content': image_content},
                    'features': [{'type': 'DOCUMENT_TEXT_DETECTION'}],
                }
            ]
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    data = (payload.get('responses') or [{}])[0]

    if data.get('error'):
        message = data['error'].get('message', 'Error desconocido en OCR cloud.')
        if 'vision.googleapis.com' in message.lower():
            raise RuntimeError(
                'Google Vision API no está habilitada para este proyecto. '
                'Activala en Google Cloud Console y volvé a probar.'
            )
        raise RuntimeError(message)

    text = (
        data.get('fullTextAnnotation', {}).get('text')
        or ((data.get('textAnnotations') or [{}])[0].get('description', ''))
    )
    if not text.strip():
        raise RuntimeError('No se detectó texto en la imagen.')
    return text


def extract_text_from_image(path: str, creds_path: str = '', prefer_cloud: bool = False) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    if prefer_cloud:
        return extract_text_with_cloud_vision(path, creds_path)

    if cv2 is None or pytesseract is None or Image is None:
        if creds_path:
            return extract_text_with_cloud_vision(path, creds_path)
        raise RuntimeError(
            'OCR no disponible en este dispositivo/build. '
            'Configurá credenciales de Google para usar OCR cloud desde mobile.'
        )

    img = cv2.imread(path)
    if img is None:
        raise ValueError('No se pudo leer la imagen')
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
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
