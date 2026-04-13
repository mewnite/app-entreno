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
        """Append a training block: one metadata row (fecha, rutina, meso, micro) and multiple exercise rows.

        Applies basic formatting: bold metadata row and header, freezes header row.
        """
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

        # Prepare metadata row: first 4 columns filled, rest empty to match total columns
        meta_row = [session_meta.get('Fecha',''), session_meta.get('Rutina',''), session_meta.get('Mesociclo',''), session_meta.get('Microciclo','')]
        total_columns = 15
        meta_row += [''] * (total_columns - len(meta_row))

        # Get current number of rows to know where metadata will be
        existing = ws.get_all_values()
        start_index = len(existing) + 1

        # Append metadata and exercise rows in bulk to reduce API calls
        try:
            ws.append_row(meta_row)
            # rows is list of lists
            if rows:
                ws.append_rows(rows, value_input_option='RAW')
        except Exception as e:
            raise

        # Formatting: make metadata row bold and header row (row 1) bold, freeze header
        try:
            # Bold metadata row
            meta_range = f'A{start_index}:O{start_index}'
            ws.format(meta_range, {
                'textFormat': {'bold': True}
            })
            # Bold header rows (first two)
            ws.format('A1:O2', {'textFormat': {'bold': True}})
            # Freeze first two rows
            try:
                ws.freeze(rows=2)
            except Exception:
                pass
        except Exception:
            # non-fatal
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

        # Define headers (15 columns A..O)
        header1 = ['Fecha', 'Rutina', 'Mesociclo', 'Microciclo'] + [''] * 11
        header2 = ['Dia', 'Ejercicio', 'Series', 'Método', 'TEMPO', 'Tiempo descanso', 'Reps Semana Anterior', 'Reps', 'Peso', 'RIR', 'Anotaciones']
        # pad header2 to 15
        if len(header2) < 15:
            header2 += [''] * (15 - len(header2))

        # Update values for first two rows
        ws.update('A1:O2', [header1, header2])

        sheet_id = ws._properties.get('sheetId')
        requests = []

        # Merges to approximate layout
        # Merge A1:A2 (Fecha)
        requests.append({'mergeCells': {'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 2, 'startColumnIndex': 0, 'endColumnIndex': 1}, 'mergeType': 'MERGE_ALL'}})
        # Merge B1:E1 for Rutina
        requests.append({'mergeCells': {'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 1, 'endColumnIndex': 5}, 'mergeType': 'MERGE_ALL'}})
        # Merge C1:C2 (Mesociclo) -> column index 2
        requests.append({'mergeCells': {'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 2, 'startColumnIndex': 2, 'endColumnIndex': 3}, 'mergeType': 'MERGE_ALL'}})
        # Merge D1:D2 (Microciclo) -> column index 3
        requests.append({'mergeCells': {'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 2, 'startColumnIndex': 3, 'endColumnIndex': 4}, 'mergeType': 'MERGE_ALL'}})

        # Set column widths (approx)
        widths = [120, 220, 100, 100, 200, 200, 90, 120, 80, 120, 120, 80, 80, 60, 260]
        for idx, w in enumerate(widths):
            requests.append({'updateDimensionProperties': {
                'range': {'sheetId': sheet_id, 'dimension': 'COLUMNS', 'startIndex': idx, 'endIndex': idx+1},
                'properties': {'pixelSize': w},
                'fields': 'pixelSize'
            }})

        # Header formatting: grey background and bold for rows 1-2
        requests.append({'repeatCell': {
            'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 2, 'startColumnIndex': 0, 'endColumnIndex': 15},
            'cell': {'userEnteredFormat': {'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}, 'horizontalAlignment': 'CENTER', 'textFormat': {'bold': True}}},
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
