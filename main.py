import os
import logging
import traceback

from kivy.utils import platform

# Logger primero, siempre
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("Starting app initialization...")

# Configuración segura de Android
if platform == 'android':
    try:
        os.environ['KIVY_NO_ARGS'] = '1'
        os.environ['KIVY_NO_FILELOG'] = '1'

        try:
            from android.storage import app_storage_path

            base_path = app_storage_path()
            kivy_home = os.path.join(base_path, '.kivy')
            os.makedirs(kivy_home, exist_ok=True)
            os.environ['KIVY_HOME'] = kivy_home
            logger.info(f"Set KIVY_HOME to: {kivy_home}")

        except Exception as e:
            logger.warning(f"Could not set internal KIVY_HOME: {e}")

        try:
            kivy_home = os.environ.get('KIVY_HOME', os.path.expanduser('~/.kivy'))
            kivy_icon_dir = os.path.join(kivy_home, 'icon')
            os.makedirs(kivy_icon_dir, exist_ok=True)
            logger.info(f"Created Kivy data directory: {kivy_icon_dir}")
        except Exception as e:
            logger.warning(f"Could not create Kivy data directory: {e}")

    except Exception as e:
        logger.warning(f"Error configuring Kivy for Android: {e}")

# Imports del proyecto, después de configurar lo anterior
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import ObjectProperty, StringProperty
from kivy.metrics import dp

from ocr import parse_ocr_to_fields, extract_text_from_image
from utils import Config, ensure_any_asset_in_app_storage, find_existing_asset, get_asset_path


GOOGLE_CREDS_CANDIDATES = [
    'service_account.json',
    'gimrutine-493121-84a3decf76ac.json',
]


def create_sheets_client():
    """Import Google Sheets dependencies lazily so Android can boot even if they fail."""
    from sheets import GoogleSheetsClient

    return GoogleSheetsClient()


def ensure_default_google_creds():
    """Persist bundled credentials into a stable writable path and store it in config."""
    cfg = Config.load()
    current_path = cfg.get('creds_path', '').strip()
    if current_path and os.path.exists(current_path):
        return current_path

    stable_path = ensure_any_asset_in_app_storage(
        GOOGLE_CREDS_CANDIDATES,
        target_name='service_account.json',
        debug=True,
    )
    if os.path.exists(stable_path):
        cfg['creds_path'] = stable_path
        Config.save(cfg)
        logger.info(f"Default service account configured at: {stable_path}")
        return stable_path

    logger.warning("No bundled Google credentials JSON was found in assets or app storage")
    return current_path

# Logging a archivo, usando ruta segura
try:
    if platform == 'android':
        try:
            from android.storage import app_storage_path
            log_path = os.path.join(app_storage_path(), 'gimroutine_debug.log')
        except Exception:
            log_path = '/sdcard/gimroutine_debug.log'
    else:
        log_path = 'gimroutine_debug.log'

    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(file_handler)
    logger.info(f"Logging configured successfully at: {log_path}")

except Exception as e:
    print(f"Error configuring logging: {e}")
    logger.error(f"Error configuring logging: {e}")

KV = """
<SectionCard@BoxLayout>:
    orientation: 'vertical'
    spacing: dp(8)
    padding: dp(12)
    size_hint_y: None
    height: self.minimum_height
    canvas.before:
        Color:
            rgba: 0.08, 0.11, 0.16, 0.95
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [18, 18, 18, 18]

<SectionTitle@Label>:
    size_hint_y: None
    height: dp(28)
    bold: True
    color: 0.93, 0.95, 0.98, 1
    font_size: '18sp'
    halign: 'left'
    text_size: self.size

<FieldInput@TextInput>:
    size_hint_y: None
    height: dp(44)
    multiline: False
    padding: [dp(12), dp(12), dp(12), dp(12)]
    background_normal: ''
    background_active: ''
    background_color: 0.14, 0.18, 0.25, 1
    foreground_color: 0.95, 0.97, 1, 1
    hint_text_color: 0.65, 0.72, 0.82, 1
    cursor_color: 0.36, 0.78, 0.69, 1

<AppButton@Button>:
    size_hint_y: None
    height: dp(46)
    bold: True
    background_normal: ''
    background_down: ''
    background_color: 0.18, 0.55, 0.49, 1
    color: 1, 1, 1, 1

ScreenManager:
    ManualScreen:
    OCRScreen:
    SettingsScreen:

<ManualScreen>:
    name: 'manual'
    ejercicio: ejercicio
    series: series
    metodo: metodo
    tiempo: tiempo
    reps_prev: reps_prev
    reps: reps
    peso: peso
    rir: rir
    anotaciones: anotaciones
    fecha: fecha
    rutina: rutina
    mesociclo: mesociclo
    microciclo: microciclo
    reps_default: reps_default
    rir_default: rir_default
    BoxLayout:
        orientation: 'vertical'
        spacing: dp(10)
        padding: dp(10)
        canvas.before:
            Color:
                rgba: 0.04, 0.06, 0.10, 1
            Rectangle:
                pos: self.pos
                size: self.size
        SectionCard:
            Label:
                text: 'GimRoutine'
                size_hint_y: None
                height: dp(34)
                color: 0.96, 0.98, 1, 1
                bold: True
                font_size: '28sp'
                halign: 'left'
                text_size: self.size
            Label:
                text: 'Carga tu rutina y envia la sesion a Google Sheets sin salir del celu.'
                size_hint_y: None
                height: dp(42)
                color: 0.70, 0.78, 0.88, 1
                halign: 'left'
                text_size: self.width, None
        SectionCard:
            SectionTitle:
                text: 'Resumen'
            GridLayout:
                cols:2
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(8)
                FieldInput:
                    id: fecha
                    hint_text: 'Fecha (YYYY-MM-DD)'
                FieldInput:
                    id: rutina
                    hint_text: 'Rutina (ej: Pierna fuerza)'
                FieldInput:
                    id: mesociclo
                    hint_text: 'Mesociclo'
                FieldInput:
                    id: microciclo
                    hint_text: 'Microciclo'
                FieldInput:
                    id: reps_default
                    hint_text: 'Reps por defecto'
                FieldInput:
                    id: rir_default
                    hint_text: 'RIR por defecto'
        SectionCard:
            SectionTitle:
                text: 'Ejercicio'
            GridLayout:
                cols:1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(8)
                FieldInput:
                    id: ejercicio
                    hint_text: 'Ejercicio'
                FieldInput:
                    id: series
                    hint_text: 'Series'
                FieldInput:
                    id: metodo
                    hint_text: 'Metodo'
                FieldInput:
                    id: tiempo
                    hint_text: 'Tiempo / tempo'
                FieldInput:
                    id: reps_prev
                    hint_text: 'Repeticiones semana anterior'
                FieldInput:
                    id: reps
                    hint_text: 'Repeticiones actuales'
                FieldInput:
                    id: peso
                    hint_text: 'Peso utilizado'
                FieldInput:
                    id: rir
                    hint_text: 'RIR'
                TextInput:
                    id: anotaciones
                    hint_text: 'Anotaciones'
                    size_hint_y: None
                    height: dp(110)
                    padding: [dp(12), dp(12), dp(12), dp(12)]
                    background_normal: ''
                    background_active: ''
                    background_color: 0.14, 0.18, 0.25, 1
                    foreground_color: 0.95, 0.97, 1, 1
                    hint_text_color: 0.65, 0.72, 0.82, 1
                    cursor_color: 0.36, 0.78, 0.69, 1
        ScrollView:
            size_hint_y: 1
            do_scroll_x: False
            GridLayout:
                cols:1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(10)
                SectionCard:
                    SectionTitle:
                        text: 'Acciones'
                    GridLayout:
                        cols: 2
                        size_hint_y: None
                        height: self.minimum_height
                        spacing: dp(8)
                        AppButton:
                            text: 'Agregar ejercicio'
                            on_release: root.add_exercise()
                        AppButton:
                            text: 'Finalizar entrenamiento'
                            background_color: 0.83, 0.37, 0.25, 1
                            on_release: root.finalize_training()
                        AppButton:
                            text: 'Limpiar sesion'
                            background_color: 0.31, 0.36, 0.47, 1
                            on_release: root.clear_session()
                        AppButton:
                            text: 'OCR'
                            background_color: 0.20, 0.43, 0.78, 1
                            on_release: app.root.current = 'ocr'
                        AppButton:
                            text: 'Configuracion'
                            background_color: 0.55, 0.43, 0.20, 1
                            on_release: app.root.current = 'settings'
                SectionCard:
                    SectionTitle:
                        text: 'Sesion actual'
                    Label:
                        text: 'Ejercicios cargados'
                        size_hint_y: None
                        height: dp(24)
                        color: 0.70, 0.78, 0.88, 1
                        halign: 'left'
                        text_size: self.size
                    ScrollView:
                        size_hint_y: None
                        height: dp(230)
                        do_scroll_x: False
                        GridLayout:
                            id: exercise_list
                            cols:1
                            size_hint_y: None
                            height: self.minimum_height
                            spacing: dp(6)

<OCRScreen>:
    name: 'ocr'
    image_path: ''
    BoxLayout:
        orientation: 'vertical'
        spacing: dp(10)
        padding: dp(10)
        canvas.before:
            Color:
                rgba: 0.04, 0.06, 0.10, 1
            Rectangle:
                pos: self.pos
                size: self.size
        SectionCard:
            SectionTitle:
                text: 'OCR'
            Label:
                text: 'Importa una imagen, revisa el texto y mandalo directo al formulario.'
                size_hint_y: None
                height: dp(42)
                color: 0.70, 0.78, 0.88, 1
                halign: 'left'
                text_size: self.width, None
            GridLayout:
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(8)
                AppButton:
                    text: 'Tomar foto (Camera)'
                    background_color: 0.20, 0.43, 0.78, 1
                    on_release: root.capture_camera()
                AppButton:
                    text: 'Seleccionar imagen'
                    on_release: root.open_filechooser()
                AppButton:
                    text: 'Mapear a campos'
                    background_color: 0.55, 0.43, 0.20, 1
                    on_release: root.map_text_to_fields()
        SectionCard:
            SectionTitle:
                text: 'Texto detectado'
            TextInput:
                id: ocr_text
                text: root.ocr_text
                size_hint_y: None
                height: dp(320)
                padding: [dp(12), dp(12), dp(12), dp(12)]
                background_normal: ''
                background_active: ''
                background_color: 0.14, 0.18, 0.25, 1
                foreground_color: 0.95, 0.97, 1, 1
                hint_text_color: 0.65, 0.72, 0.82, 1
                cursor_color: 0.36, 0.78, 0.69, 1
        GridLayout:
            cols: 2
            size_hint_y: None
            height: dp(46)
            spacing: dp(8)
            AppButton:
                text: 'Enviar a Google Sheets'
                background_color: 0.83, 0.37, 0.25, 1
                on_release: root.send_mapped_to_sheets()
            AppButton:
                text: 'Volver'
                background_color: 0.31, 0.36, 0.47, 1
                on_release: app.root.current = 'manual'

<SettingsScreen>:
    name: 'settings'
    creds_path: creds_path
    sheet_name: sheet_name
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10)
        spacing: dp(10)
        canvas.before:
            Color:
                rgba: 0.04, 0.06, 0.10, 1
            Rectangle:
                pos: self.pos
                size: self.size
        SectionCard:
            SectionTitle:
                text: 'Configuracion'
            Label:
                text: 'La app intenta encontrar las credenciales empaquetadas sola al iniciar.'
                size_hint_y: None
                height: dp(42)
                color: 0.70, 0.78, 0.88, 1
                halign: 'left'
                text_size: self.width, None
            FieldInput:
                id: creds_path
                hint_text: 'Ruta de credenciales JSON'
                text: root.creds
            FieldInput:
                id: sheet_name
                hint_text: 'Nombre del Spreadsheet'
                text: root.sheet
        GridLayout:
            cols: 1
            size_hint_y: None
            height: self.minimum_height
            spacing: dp(8)
            AppButton:
                text: 'Guardar'
                on_release: root.save()
            AppButton:
                text: 'Probar conexion'
                background_color: 0.20, 0.43, 0.78, 1
                on_release: root.test_connection()
            AppButton:
                text: 'Volver'
                background_color: 0.31, 0.36, 0.47, 1
                on_release: app.root.current = 'manual'
"""


class ManualScreen(Screen):
    ejercicio = ObjectProperty(None)
    series = ObjectProperty(None)
    metodo = ObjectProperty(None)
    tiempo = ObjectProperty(None)
    reps_prev = ObjectProperty(None)
    reps = ObjectProperty(None)
    peso = ObjectProperty(None)
    rir = ObjectProperty(None)
    anotaciones = ObjectProperty(None)
    reps_default = ObjectProperty(None)
    rir_default = ObjectProperty(None)

    def send_to_sheets(self):
        # kept for compatibility (sends current single exercise)
        config = Config.load()
        client = create_sheets_client()
        try:
            client.configure_from_service_account(config.get('creds_path'))
            sheet_name = config.get('sheet_name', 'Entrenamientos')
            row = [self.ids.fecha.text, self.ids.rutina.text, self.ids.mesociclo.text, self.ids.microciclo.text,
                   self.ejercicio.text, self.series.text, self.metodo.text, self.tiempo.text,
                   self.reps_prev.text, self.reps.text, self.peso.text, self.rir.text, self.anotaciones.text]
            client.append_row(sheet_name, row)
            self.manager.current = 'manual'
        except Exception as e:
            from kivy.uix.popup import Popup
            from kivy.uix.label import Label
            Popup(title='Error', content=Label(text=str(e)), size_hint=(0.8, 0.4)).open()

    def add_exercise(self):
        # Read current fields and add to session
        from utils import TrainingSession
        # Use per-exercise values; if empty, fall back to session defaults
        reps_val = self.reps.text.strip() or self.ids.reps_default.text.strip()
        rir_val = self.rir.text.strip() or self.ids.rir_default.text.strip()
        ex = {
            'Ejercicio': self.ejercicio.text,
            'Series': self.series.text,
            'Método': self.metodo.text,
            'Tiempo': self.tiempo.text,
            'Reps Semana Anterior': self.reps_prev.text,
            'Reps': reps_val,
            'Peso': self.peso.text,
            'RIR': rir_val,
            'Anotaciones': self.anotaciones.text
        }
        TrainingSession.add_exercise(ex)
        # Clear exercise fields for next entry
        self.ejercicio.text = ''
        self.series.text = ''
        self.metodo.text = ''
        self.tiempo.text = ''
        self.reps_prev.text = ''
        self.reps.text = ''
        self.peso.text = ''
        self.rir.text = ''
        self.anotaciones.text = ''
        self.refresh_exercise_list()

    def refresh_exercise_list(self):
        from utils import TrainingSession
        exercises = TrainingSession.get_exercises()
        container = self.ids.exercise_list
        container.clear_widgets()
        # show each exercise with delete button
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.label import Label
        from kivy.uix.button import Button
        for i, ex in enumerate(exercises):
            bl = BoxLayout(size_hint_y=None, height=dp(40))
            txt = f"{i+1}. {ex.get('Ejercicio','')} | S:{ex.get('Series','')} R:{ex.get('Reps','')} P:{ex.get('Peso','')}"
            bl.add_widget(Label(text=txt))
            btn = Button(text='Eliminar', size_hint_x=None, width=dp(90))
            def make_cb(idx):
                return lambda *_: (TrainingSession.remove_exercise(idx), self.refresh_exercise_list())
            btn.bind(on_release=make_cb(i))
            bl.add_widget(btn)
            container.add_widget(bl)

    def clear_session(self):
        from utils import TrainingSession
        TrainingSession.clear()
        self.refresh_exercise_list()

    def finalize_training(self):
        from utils import TrainingSession
        config = Config.load()
        client = create_sheets_client()
        try:
            client.configure_from_service_account(config.get('creds_path'))
            sheet_name = config.get('sheet_name', 'Entrenamientos')
            exercises = TrainingSession.get_exercises()
            if not exercises:
                from kivy.uix.popup import Popup
                from kivy.uix.label import Label
                Popup(title='Info', content=Label(text='No hay ejercicios en la sesión.'), size_hint=(0.6,0.3)).open()
                return
            fecha = self.ids.fecha.text
            rutina = self.ids.rutina.text
            meso = self.ids.mesociclo.text
            micro = self.ids.microciclo.text
            # Build rows (A..K) to match the sheet template (like the reference image)
            rows = []
            for ex in exercises:
                # Columns: Dia, Ejercicio, Series, Metodo, TEMPO, Tiempo descanso,
                #          Reps semana anterior, Reps, Peso utilizado, RIR, Anotaciones
                row = [
                    rutina,
                    ex.get('Ejercicio', ''),
                    ex.get('Series', ''),
                    ex.get('Método', ''),
                    ex.get('Tiempo', ''),  # mapped to TEMPO
                    '',  # descanso (no hay campo dedicado en UI)
                    ex.get('Reps Semana Anterior', ''),
                    ex.get('Reps', ''),
                    ex.get('Peso', ''),
                    ex.get('RIR', ''),
                    ex.get('Anotaciones', ''),
                ]
                rows.append(row)
            client.append_training(
                sheet_name,
                {'Fecha': fecha, 'Rutina': rutina, 'Mesociclo': meso, 'Microciclo': micro},
                rows,
            )
            TrainingSession.clear()
            self.refresh_exercise_list()
            from kivy.uix.popup import Popup
            from kivy.uix.label import Label
            Popup(title='Éxito', content=Label(text='Entrenamiento enviado.'), size_hint=(0.6,0.3)).open()
        except Exception as e:
            from kivy.uix.popup import Popup
            from kivy.uix.label import Label
            Popup(title='Error', content=Label(text=str(e)), size_hint=(0.8,0.4)).open()


class OCRScreen(Screen):
    ocr_text = StringProperty('')
    image_path = StringProperty('')

    def capture_camera(self):
        # Simple approach: open native camera via Plyer on mobile would be better.
        # Here, on desktop we fallback to ask user to select image.
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label
        Popup(title='Info', content=Label(text='En dispositivos móviles se usará la cámara. En PC, selecciona una imagen.'), size_hint=(0.8,0.4)).open()

    def open_filechooser(self):
        from kivy.uix.filechooser import FileChooserIconView
        from kivy.uix.popup import Popup
        box = FileChooserIconView()
        popup = Popup(title='Seleccionar imagen', content=box, size_hint=(0.9,0.9))

        def on_selection(instance, selection):
            if selection:
                self.image_path = selection[0]
                popup.dismiss()
                self.do_ocr()

        box.bind(on_submit=lambda inst, sel, touch: on_selection(inst, sel))
        popup.open()

    def do_ocr(self):
        if not self.image_path:
            return
        try:
            text = extract_text_from_image(self.image_path)
            self.ocr_text = text
        except Exception as e:
            from kivy.uix.popup import Popup
            from kivy.uix.label import Label
            Popup(title='OCR Error', content=Label(text=str(e)), size_hint=(0.8,0.4)).open()

    def map_text_to_fields(self):
        mapped = parse_ocr_to_fields(self.ocr_text)
        # push mapped values to Manual screen fields
        manual = self.manager.get_screen('manual')
        manual.ejercicio.text = mapped.get('Ejercicio', '')
        manual.series.text = mapped.get('Series', '')
        manual.metodo.text = mapped.get('Método', '')
        manual.tiempo.text = mapped.get('Tiempo', '')
        manual.reps_prev.text = mapped.get('Reps Semana Anterior', '')
        manual.reps.text = mapped.get('Reps', '')
        manual.peso.text = mapped.get('Peso', '')
        manual.rir.text = mapped.get('RIR', '')
        manual.anotaciones.text = mapped.get('Anotaciones', '')
        self.manager.current = 'manual'

    def send_mapped_to_sheets(self):
        # map then send
        self.map_text_to_fields()
        self.manager.get_screen('manual').send_to_sheets()


class SettingsScreen(Screen):
    creds = StringProperty('')
    sheet = StringProperty('Entrenamientos')

    def on_pre_enter(self):
        cfg = Config.load()
        self.creds = cfg.get('creds_path','')
        # Auto-detect service account in app assets on Android
        if not self.creds:
            auto_path = ensure_default_google_creds() or get_asset_path('service_account.json')
            if os.path.exists(auto_path):
                self.creds = auto_path
        self.sheet = cfg.get('sheet_name','Entrenamientos')

    def save(self):
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label
        cfg = Config.load()
        cfg['creds_path'] = self.ids.creds_path.text
        cfg['sheet_name'] = self.ids.sheet_name.text
        Config.save(cfg)
        Popup(title='Guardado', content=Label(text='Configuración guardada.'), size_hint=(0.6,0.3)).open()

    def test_connection(self):
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label
        cfg = Config.load()
        try:
            client = create_sheets_client()
            client.configure_from_service_account(cfg.get('creds_path'))
            Popup(title='Conexión OK', content=Label(text='Conexión establecida.'), size_hint=(0.6,0.3)).open()
        except Exception as e:
            Popup(title='Error', content=Label(text=str(e)), size_hint=(0.8,0.4)).open()


class GymApp(App):
    def build(self):
        try:
            logger.info("Starting GymApp build...")
            # Load the KV string and return the root widget
            root = Builder.load_string(KV)
            logger.info("KV loaded successfully")
            return root
        except Exception as e:
            logger.error(f"Error in build(): {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def on_start(self):
        try:
            logger.info("App started successfully")
            ensure_default_google_creds()
            if platform == 'android':
                logger.info("Running on Android with internal app storage only")

        except Exception as e:
            logger.error(f"Error in on_start(): {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def on_pause(self):
        try:
            logger.info("App paused")
            return True
        except Exception as e:
            logger.error(f"Error in on_pause(): {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return True

    def on_resume(self):
        try:
            logger.info("App resumed")
        except Exception as e:
            logger.error(f"Error in on_resume(): {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")


def main():
    try:
        logger.info("Starting main() function")
        app = GymApp()
        logger.info("GymApp instance created")
        app.run()
    except Exception as e:
        logger.error(f"Critical error in main(): {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Re-raise to ensure the crash is visible
        raise


if __name__ == '__main__':
    main()
