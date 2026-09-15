import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError
import os
import time
import random
import json
from utils import get_asset_path, read_android_content_uri

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']


class GoogleSheetsClient:
    def __init__(self):
        self.client = None

    def configure_from_service_account(self, creds_path):
        if not creds_path:
            raise ValueError('Ruta de credenciales no proporcionada')
        # Resolve the credential path (handles Android internal storage)
        resolved_path = get_asset_path(creds_path)
        if resolved_path.startswith('content://'):
            try:
                content = read_android_content_uri(resolved_path)
                creds_info = json.loads(content)
                creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
                self.client = gspread.authorize(creds)
                return
            except Exception as e:
                raise RuntimeError(
                    f'No se pudieron leer credenciales desde el selector de Android.\n'
                    f'Ruta usada: {resolved_path}\n'
                    f'Error original: {e}'
                ) from e

        if not os.path.exists(resolved_path):
            raise FileNotFoundError(
                f'No se encontraron credenciales en: {resolved_path}\n'
                f'Ruta original: {creds_path}\n\n'
                'En Android, copia service_account.json a la carpeta de la app '
                'o usa "Configuración" para apuntar a la ruta correcta.'
            )
        try:
            creds = Credentials.from_service_account_file(resolved_path, scopes=SCOPES)
            self.client = gspread.authorize(creds)
        except Exception as e:
            err_str = str(e).lower()
            if 'invalid_grant' in err_str or 'invalid jwt signature' in err_str:
                raise RuntimeError(
                    "Error de autenticación: 'Invalid JWT Signature'.\n\n"
                    "Esto significa que el archivo de credenciales (service_account.json) no es válido.\n"
                    "Posibles causas:\n"
                    "1. El archivo no es un Service Account JSON de Google Cloud (podría ser un OAuth client ID).\n"
                    "2. El archivo está corrupto o mal formado.\n"
                    "3. La clave privada ('private_key') tiene un formato incorrecto (debe contener saltos de línea reales).\n"
                    "4. El service account fue eliminado o desactivado en Google Cloud.\n\n"
                    "Solución:\n"
                    "- Descarga un nuevo service_account.json desde Google Cloud Console (IAM > Service Accounts).\n"
                    "- Asegúrate de seleccionar 'JSON' y copia el archivo completo sin modificaciones.\n"
                    "- Reemplaza el archivo en tu proyecto y reconstruye la APK.\n"
                    f"Ruta usada: {resolved_path}\n"
                    f"Error original: {e}"
                ) from e
            else:
                raise

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
        """Fill the existing day template without replacing its layout."""
        if self.client is None:
            raise RuntimeError('Cliente no configurado. Llama a configure_from_service_account() primero.')

        try:
            sh = self.client.open(spreadsheet_title)
        except Exception as exc:
            raise RuntimeError(
                f'No se encontró el Spreadsheet existente "{spreadsheet_title}". '
                'Crea o comparte la plantilla con la cuenta de servicio antes de enviar.'
            ) from exc
        ws = sh.sheet1

        header_row, columns = self._find_template_header(ws)
        data_start = header_row + 1
        capacity = self._template_capacity(sh, ws, data_start)
        if len(rows) > capacity:
            raise ValueError(
                f'La plantilla tiene {capacity} filas disponibles y la sesión necesita {len(rows)}. '
                'Añade más filas al cuadro existente conservando su formato.'
            )

        merged_ranges = self._merged_ranges(ws)
        requests = []
        for row_offset, row in enumerate(rows):
            sheet_row = data_start + row_offset
            for source_column, value in enumerate(row):
                target_column = columns[source_column]
                if self._is_merged_non_top_left(merged_ranges, sheet_row, target_column):
                    continue
                requests.append({
                    'updateCells': {
                        'range': {
                            'sheetId': ws._properties.get('sheetId'),
                            'startRowIndex': sheet_row - 1,
                            'endRowIndex': sheet_row,
                            'startColumnIndex': target_column,
                            'endColumnIndex': target_column + 1,
                        },
                        'rows': [{'values': [{'userEnteredValue': {'stringValue': str(value or '')}}]}],
                        'fields': 'userEnteredValue',
                    }
                })

        for key, address in {'Mesociclo': 'H1', 'Microciclo': 'J1'}.items():
            if session_meta.get(key):
                ws.update(address, [[session_meta[key]]], value_input_option='RAW')
        if requests:
            sh.batch_update({'requests': requests})

    @staticmethod
    def _normalise_header(value):
        import unicodedata
        value = unicodedata.normalize('NFKD', str(value or ''))
        value = ''.join(char for char in value if not unicodedata.combining(char))
        return ' '.join(value.lower().replace('\n', ' ').split())

    def _find_template_header(self, ws):
        expected = [
            'dia', 'ejercicio', 'series', 'margen de repeticiones', 'metodo',
            'tempo', 'tiempo de descanso', 'repeticiones anterior mesociclo',
            'repeticiones', 'peso utilizado', 'rir', 'rpe 1 a 10', 'anotaciones',
        ]
        aliases = {
            'margen de repeticiones': {'margen de repeticiones', 'margen reps'},
            'repeticiones anterior mesociclo': {
                'repeticiones anterior mesociclo', 'repeticiones semana anterior',
            },
            'rpe 1 a 10': {'rpe 1 a 10', 'rpe'},
        }
        values = ws.get_all_values()
        for row_number, row in enumerate(values, start=1):
            normalised = {self._normalise_header(cell): index for index, cell in enumerate(row)}
            columns = []
            for header in expected:
                accepted = aliases.get(header, {header})
                match = next((normalised[name] for name in accepted if name in normalised), None)
                if match is None:
                    break
                columns.append(match)
            if len(columns) == len(expected):
                return row_number, columns
        raise ValueError(
            'No se encontró la fila de encabezados de la plantilla. '
            'La hoja debe conservar los encabezados del cuadro de la imagen.'
        )

    def _template_capacity(self, sh, ws, data_start):
        """Count formatted rows before the template's separator band."""
        try:
            metadata = sh.fetch_sheet_metadata(params={
                'includeGridData': 'true',
                'ranges': [f"'{ws.title}'!A{data_start}:M200"],
            })
            sheet_data = metadata.get('sheets', [{}])[0].get('data', [{}])[0]
            row_data = sheet_data.get('rowData', [])
            capacity = 0
            for row in row_data:
                values = row.get('values', [])
                if self._is_separator_row(values):
                    break
                if any(value.get('userEnteredFormat') or value.get('effectiveFormat') or value.get('userEnteredValue') for value in values):
                    capacity += 1
                elif capacity:
                    break
            if capacity:
                return capacity
        except Exception:
            pass

        existing = ws.get_all_values()
        return max(0, len(existing) - data_start + 1)

    @staticmethod
    def _is_separator_row(values):
        colours = []
        for value in values:
            fmt = value.get('userEnteredFormat', {})
            colour = fmt.get('backgroundColor', {})
            if colour:
                colours.append(colour)
        return bool(colours) and sum(
            colour.get('red', 0) > 0.7 and colour.get('green', 0) < 0.4
            and colour.get('blue', 0) < 0.4 for colour in colours
        ) >= max(1, len(colours) // 2)

    @staticmethod
    def _merged_ranges(ws):
        try:
            return list(ws.merged_cells.ranges)
        except Exception:
            return []

    @staticmethod
    def _is_merged_non_top_left(ranges, row, column):
        for merged in ranges:
            start_row = getattr(merged, 'start_row_index', None)
            end_row = getattr(merged, 'end_row_index', None)
            start_column = getattr(merged, 'start_column_index', None)
            end_column = getattr(merged, 'end_column_index', None)
            if None in (start_row, end_row, start_column, end_column):
                continue
            zero_based_row = row - 1
            if start_row < zero_based_row < end_row and start_column <= column < end_column:
                return True
        return False

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
