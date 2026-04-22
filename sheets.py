import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError
import os
import time
import random

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']


class GoogleSheetsClient:
    def __init__(self):
        self.client = None

    def configure_from_service_account(self, creds_path):
        if not creds_path:
            raise ValueError('Ruta de credenciales no proporcionada')
        if not os.path.exists(creds_path):
            raise FileNotFoundError(f'No se encontró: {creds_path}')
        creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        self.client = gspread.authorize(creds)

    def _open_or_create_spreadsheet(self, title):
        # Try to open; if fails, try to create. Implement simple retry/backoff for rate limits.
        attempts = 0
        while True:
            try:
                sh = self.client.open(title)
                return sh
            except APIError as e:
                attempts += 1
                msg = str(e)
                if 'rateLimitExceeded' in msg or 'User rate limit exceeded' in msg or '403' in msg:
                    if attempts <= 5:
                        wait = (2 ** (attempts - 1)) + random.random()
                        time.sleep(wait)
                        continue
                    else:
                        raise RuntimeError(
                            'Google API rate limit exceeded. Espera unos minutos antes de reintentar, ' 
                            'o reduce la frecuencia de solicitudes. Si el problema persiste, solicita aumento de cuota en Cloud Console. '
                            f'Error original: {msg}'
                        )
                # Other API errors fall through to creation attempt
                break
            except Exception:
                # If open fails for other reasons, attempt to create below
                break

        # Try creating the spreadsheet (requires Drive API enabled)
        attempts = 0
        while True:
            try:
                sh = self.client.create(title)
                # Ensure at least one worksheet and set headers
                try:
                    ws = sh.sheet1
                    headers = ['Ejercicio', 'Series', 'Método', 'Tiempo', 'Reps Semana Anterior', 'Reps', 'Peso', 'RIR', 'Anotaciones']
                    ws.append_row(headers)
                except Exception:
                    pass
                return sh
            except APIError as e:
                attempts += 1
                msg = str(e)
                if 'rateLimitExceeded' in msg or 'User rate limit exceeded' in msg:
                    if attempts <= 5:
                        wait = (2 ** (attempts - 1)) + random.random()
                        time.sleep(wait)
                        continue
                    else:
                        raise RuntimeError(
                            'Google API rate limit exceeded while creating spreadsheet. Espera unos minutos antes de reintentar, ' 
                            'o crea el Spreadsheet manualmente y comparte con la cuenta de servicio. '
                            f'Error original: {msg}'
                        )
                if 'Drive API has not been used' in msg or 'drive.googleapis.com' in msg or '403' in msg:
                    raise RuntimeError(
                        'Google Drive API appears disabled for your project or access is forbidden. '
                        'Enable the Google Drive API and Google Sheets API for your project in the Cloud Console: '
                        'https://console.developers.google.com/apis/library/drive.googleapis.com and '
                        'https://console.developers.google.com/apis/library/sheets.googleapis.com .\n'
                        'Alternativa: crea manualmente el Spreadsheet en tu cuenta, comparte el documento con el email de la cuenta de servicio (campo `client_email` en el JSON de credenciales) y usa ese nombre aquí. '
                        f'Error original: {msg}'
                    )
                # otherwise, re-raise
                raise

    def append_row(self, spreadsheet_title, row):
        if self.client is None:
            raise RuntimeError('Cliente no configurado. Llama a configure_from_service_account() primero.')

        sh = self._open_or_create_spreadsheet(spreadsheet_title)
        ws = sh.sheet1

        attempts = 0
        while True:
            try:
                ws.append_row(row)
                return
            except APIError as e:
                attempts += 1
                msg = str(e)
                if 'rateLimitExceeded' in msg or 'User rate limit exceeded' in msg:
                    if attempts <= 5:
                        wait = (2 ** (attempts - 1)) + random.random()
                        time.sleep(wait)
                        continue
                    else:
                        raise RuntimeError(
                            'Google API rate limit exceeded while appending row. Espera unos minutos antes de reintentar, '
                            'reduce la frecuencia de envíos o solicita aumento de cuota en Cloud Console. '
                            f'Error original: {msg}'
                        )
                else:
                    raise

    def append_training(self, spreadsheet_title: str, session_meta: dict, rows: list):
        """Append a training block (exercise rows) using the template layout."""
        if self.client is None:
            raise RuntimeError('Cliente no configurado. Llama a configure_from_service_account() primero.')

        sh = self._open_or_create_spreadsheet(spreadsheet_title)
        ws = sh.sheet1

        # Ensure template/layout exists (merges, headers, formats)
        try:
            self._ensure_template(sh)
        except Exception:
            # non-fatal, continue
            pass

        # Update top meta values (like the reference image: Mesociclo=2, Microciclo=2/3, etc.)
        # Layout:
        # - A1:A2 merged -> "Fecha"
        # - G1 -> "Mesociclo", H1 -> value
        # - I1 -> "Microciclo (semana)", J1 -> value
        try:
            ws.update('H1', [[session_meta.get('Mesociclo', '')]])
            ws.update('J1', [[session_meta.get('Microciclo', '')]])
        except Exception:
            pass

        if not rows:
            return

        # Append exercise rows (data begins on row 3)
        existing = ws.get_all_values()
        start_index = len(existing) + 1
        try:
            ws.append_rows(rows, value_input_option='RAW')
        except Exception:
            raise

        # Add a red separator row (like the screenshot bottom band)
        try:
            sep_row = [''] * 11  # A..K
            ws.append_row(sep_row)
            sep_idx = start_index + len(rows)
            ws.format(f'A{sep_idx}:K{sep_idx}', {'backgroundColor': {'red': 0.85, 'green': 0.2, 'blue': 0.2}})
        except Exception:
            pass

    def _ensure_template(self, sh):
        """Create/update spreadsheet template to match desired layout (merges, headers, widths, colors)."""
        ws = sh.sheet1
        # If header already present, skip
        try:
            val = ws.acell('A1').value
            if val and val.strip().lower() == 'fecha':
                return
        except Exception:
            pass

        # Template columns (A..K)
        # Row 1 contains merged headers (like the reference image)
        row1 = ['Fecha', 'Rutina fuerza', '', '', '', '', 'Mesociclo', '', 'Microciclo (semana)', '', '']
        row2 = ['Dia', 'Ejercicio', 'Series', 'Metodo', 'TEMPO', 'Tiempo de descanso',
                'Repeticiones semana anterior', 'Repeticiones', 'Peso utilizado', 'RIR', 'Anotaciones']
        ws.update('A1:K2', [row1, row2])

        sheet_id = ws._properties.get('sheetId')
        requests = []

        # Merges (approximate the screenshot)
        # A1:A2 = Fecha
        requests.append({'mergeCells': {'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 2, 'startColumnIndex': 0, 'endColumnIndex': 1}, 'mergeType': 'MERGE_ALL'}})
        # B1:F1 = Rutina fuerza
        requests.append({'mergeCells': {'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 1, 'endColumnIndex': 6}, 'mergeType': 'MERGE_ALL'}})
        # G1:G2 = Mesociclo label
        requests.append({'mergeCells': {'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 2, 'startColumnIndex': 6, 'endColumnIndex': 7}, 'mergeType': 'MERGE_ALL'}})
        # I1:I2 = Microciclo label
        requests.append({'mergeCells': {'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 2, 'startColumnIndex': 8, 'endColumnIndex': 9}, 'mergeType': 'MERGE_ALL'}})

        # Set column widths (approx)
        widths = [140, 240, 90, 120, 190, 190, 170, 120, 120, 80, 260]
        for idx, w in enumerate(widths):
            requests.append({'updateDimensionProperties': {
                'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': idx, 'endIndex': idx+1},
                'properties': {'pixelSize': w},
                'fields': 'pixelSize'
            }})

        # Header formatting: grey background and bold for rows 1-2
        requests.append({'repeatCell': {
            'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 2, 'startColumnIndex': 0, 'endColumnIndex': 11},
            'cell': {'userEnteredFormat': {'backgroundColor': {'red': 0.75, 'green': 0.75, 'blue': 0.75}, 'horizontalAlignment': 'CENTER', 'textFormat': {'bold': True}}},
            'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)'
        }})

        # Red background for "Repeticiones semana anterior" header cell (G2) like the screenshot
        requests.append({'repeatCell': {
            'range': {'sheetId': sheet_id, 'startRowIndex': 1, 'endRowIndex': 2, 'startColumnIndex': 6, 'endColumnIndex': 7},
            'cell': {'userEnteredFormat': {'backgroundColor': {'red': 0.85, 'green': 0.2, 'blue': 0.2}, 'textFormat': {'bold': True}, 'horizontalAlignment': 'CENTER'}},
            'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)'
        }})

        # Blue band on the far right (K1:K2) like the screenshot edge
        requests.append({'repeatCell': {
            'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 2, 'startColumnIndex': 10, 'endColumnIndex': 11},
            'cell': {'userEnteredFormat': {'backgroundColor': {'red': 0.1, 'green': 0.25, 'blue': 0.95}, 'textFormat': {'bold': True}, 'horizontalAlignment': 'CENTER'}},
            'fields': 'userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)'
        }})

        # Freeze first two rows
        requests.append({'updateSheetProperties': {'properties': {'sheetId': sheet_id, 'gridProperties': {'frozenRowCount': 2}}, 'fields': 'gridProperties.frozenRowCount'}})

        body = {'requests': requests}
        try:
            sh.batch_update(body)
        except Exception:
            # if batch update fails, ignore (non-fatal)
            pass
