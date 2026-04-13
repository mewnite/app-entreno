from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import ObjectProperty, StringProperty
from kivy.metrics import dp
from sheets import GoogleSheetsClient
from ocr import extract_text_from_image, parse_ocr_to_fields
from utils import Config
import os

KV = """
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
        spacing: dp(8)
        padding: dp(8)
        GridLayout:
            cols:2
            size_hint_y: None
            height: dp(120)
            spacing: dp(6)
            TextInput:
                id: fecha
                hint_text: 'Fecha (YYYY-MM-DD)'
                size_hint_x: 0.34
            TextInput:
                id: rutina
                hint_text: 'Rutina (ej: Pierna fuerza)'
                size_hint_x: 0.33
            TextInput:
                id: mesociclo
                hint_text: 'Mesociclo'
                size_hint_x: 0.165
            TextInput:
                id: microciclo
                hint_text: 'Microciclo'
                size_hint_x: 0.165
            TextInput:
                id: reps_default
                hint_text: 'Reps por defecto'
                size_hint_x: 0.165
            TextInput:
                id: rir_default
                hint_text: 'RIR por defecto'
                size_hint_x: 0.165
        ScrollView:
            size_hint_y: 0.45
            GridLayout:
                cols:1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(6)
                TextInput:
                    id: ejercicio
                    hint_text: 'Ejercicio'
                    size_hint_y: None
                    height: dp(40)
                TextInput:
                    id: series
                    hint_text: 'Series'
                    size_hint_y: None
                    height: dp(40)
                TextInput:
                    id: metodo
                    hint_text: 'Método'
                    size_hint_y: None
                    height: dp(40)
                TextInput:
                    id: tiempo
                    hint_text: 'Tiempo'
                    size_hint_y: None
                    height: dp(40)
                TextInput:
                    id: reps_prev
                    hint_text: 'Repeticiones semana anterior'
                    size_hint_y: None
                    height: dp(40)
                TextInput:
                    id: reps
                    hint_text: 'Repeticiones actuales'
                    size_hint_y: None
                    height: dp(40)
                TextInput:
                    id: peso
                    hint_text: 'Peso utilizado'
                    size_hint_y: None
                    height: dp(40)
                TextInput:
                    id: rir
                    hint_text: 'RIR'
                    size_hint_y: None
                    height: dp(40)
                TextInput:
                    id: anotaciones
                    hint_text: 'Anotaciones'
                    size_hint_y: None
                    height: dp(120)
        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: None
            height: dp(48)
            spacing: dp(6)
            Button:
                text: 'Agregar ejercicio'
                on_release: root.add_exercise()
            Button:
                text: 'Finalizar entrenamiento'
                on_release: root.finalize_training()
            Button:
                text: 'Limpiar sesión'
                on_release: root.clear_session()
            Button:
                text: 'OCR'
                on_release: app.root.current = 'ocr'
            Button:
                text: 'Configuración'
                on_release: app.root.current = 'settings'
        Label:
            text: 'Ejercicios en la sesión:'
            size_hint_y: None
            height: dp(24)
        ScrollView:
            size_hint_y: 0.3
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
        spacing: dp(6)
        padding: dp(6)
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            Button:
                text: 'Tomar foto (Camera)'
                on_release: root.capture_camera()
            Button:
                text: 'Seleccionar imagen'
                on_release: root.open_filechooser()
            Button:
                text: 'Mapear a campos'
                on_release: root.map_text_to_fields()
        TextInput:
            id: ocr_text
            text: root.ocr_text
            size_hint_y: 0.6
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            Button:
                text: 'Enviar a Google Sheets'
                on_release: root.send_mapped_to_sheets()
            Button:
                text: 'Volver'
                on_release: app.root.current = 'manual'

<SettingsScreen>:
    name: 'settings'
    creds_path: creds_path
    sheet_name: sheet_name
    BoxLayout:
        orientation: 'vertical'
        padding: dp(8)
        spacing: dp(6)
        TextInput:
            id: creds_path
            hint_text: 'Ruta a service_account.json (credenciales)'
            text: root.creds
            size_hint_y: None
            height: dp(40)
        TextInput:
            id: sheet_name
            hint_text: 'Nombre del Spreadsheet'
            text: root.sheet
            size_hint_y: None
            height: dp(40)
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            Button:
                text: 'Guardar'
                on_release: root.save()
            Button:
                text: 'Probar conexión'
                on_release: root.test_connection()
            Button:
                text: 'Volver'
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
        client = GoogleSheetsClient()
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
        client = GoogleSheetsClient()
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
            # Build rows and send as a block for better performance and formatting
            rows = []
            for ex in exercises:
                row = [fecha, rutina, meso, micro,
                       ex.get('Ejercicio',''), ex.get('Series',''), ex.get('Método',''), ex.get('Tiempo',''),
                       ex.get('Reps Semana Anterior',''), ex.get('Reps',''), ex.get('Peso',''), ex.get('RIR',''), ex.get('Anotaciones','')]
                rows.append(row)
            client.append_training(sheet_name, {'Fecha': fecha, 'Rutina': rutina, 'Mesociclo': meso, 'Microciclo': micro}, rows)
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
        client = GoogleSheetsClient()
        try:
            client.configure_from_service_account(cfg.get('creds_path'))
            Popup(title='Conexión OK', content=Label(text='Conexión establecida.'), size_hint=(0.6,0.3)).open()
        except Exception as e:
            Popup(title='Error', content=Label(text=str(e)), size_hint=(0.8,0.4)).open()


class GymApp(App):
    def build(self):
        # Load the KV string and return the root widget
        return Builder.load_string(KV)


if __name__ == '__main__':
    GymApp().run()
