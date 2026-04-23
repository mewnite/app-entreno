import json
import os
import logging
import shutil


def get_app_storage_dir():
    """Return a writable config/data directory on every platform."""
    try:
        from kivy.utils import platform
        if platform == 'android':
            from android.storage import app_storage_path
            path = app_storage_path()
        else:
            path = os.path.dirname(os.path.abspath(__file__))
    except Exception:
        path = os.path.dirname(os.path.abspath(__file__))

    os.makedirs(path, exist_ok=True)
    return path


def find_existing_asset(candidates, debug=False):
    """Return the first candidate asset path that exists."""
    logger = logging.getLogger(__name__)
    for candidate in candidates:
        resolved = get_asset_path(candidate, debug=debug)
        if os.path.exists(resolved):
            if debug:
                logger.debug(f"Found candidate asset: {resolved}")
            return resolved
    return ''


def get_asset_path(filename, debug=False):
    """Get the absolute path to an asset file, handling Android packaging.

    Args:
        filename: Name or path of the file to find
        debug: If True, log the search process for debugging
    """
    logger = logging.getLogger(__name__)

    # First, try the file directly (if user provided absolute path)
    if os.path.exists(filename):
        if debug:
            logger.debug(f"Found file directly: {filename}")
        return filename

    # Try relative to current working directory
    cwd_path = os.path.join(os.getcwd(), filename)
    if os.path.exists(cwd_path):
        if debug:
            logger.debug(f"Found file in current working directory: {cwd_path}")
        return cwd_path

    # Try in the same directory as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, filename)
    if os.path.exists(script_path):
        if debug:
            logger.debug(f"Found file in script directory: {script_path}")
        return script_path

    # On Android, bundled files and user-provided files may live in app storage.
    try:
        from kivy.utils import platform
        if platform == 'android':
            app_path = os.path.join(get_app_storage_dir(), filename)
            if os.path.exists(app_path):
                if debug:
                    logger.debug(f"Found file in Android app storage: {app_path}")
                return app_path
            module_path = os.path.join(os.path.dirname(__file__), filename)
            if os.path.exists(module_path):
                if debug:
                    logger.debug(f"Found file in module directory: {module_path}")
                return module_path
            if debug:
                logger.debug(f"Android app storage dir: {get_app_storage_dir()}")
    except Exception as e:
        if debug:
            logger.debug(f"Error checking Android paths: {e}")

    # Return the original path (will likely fail, but we let the caller handle it)
    if debug:
        logger.debug(f"File not found, returning original path: {filename}")
    return filename


def ensure_asset_in_app_storage(filename, debug=False):
    """Copy a bundled asset into writable app storage and return the stable path."""
    logger = logging.getLogger(__name__)
    storage_path = os.path.join(get_app_storage_dir(), os.path.basename(filename))
    bundled_path = get_asset_path(filename, debug=debug)

    if os.path.exists(storage_path):
        if debug:
            logger.debug(f"Using existing app storage asset: {storage_path}")
        return storage_path

    if os.path.exists(bundled_path):
        try:
            shutil.copyfile(bundled_path, storage_path)
            if debug:
                logger.debug(f"Copied bundled asset to app storage: {storage_path}")
            return storage_path
        except Exception as exc:
            if debug:
                logger.debug(f"Could not copy asset to app storage: {exc}")
            return bundled_path

    return storage_path


def ensure_any_asset_in_app_storage(candidates, target_name=None, debug=False):
    """Copy the first available bundled asset into app storage and return the stable path."""
    logger = logging.getLogger(__name__)
    source_path = find_existing_asset(candidates, debug=debug)
    if not source_path:
        return ''

    final_name = target_name or os.path.basename(source_path)
    storage_path = os.path.join(get_app_storage_dir(), final_name)

    if os.path.exists(storage_path):
        if debug:
            logger.debug(f"Using existing app storage asset: {storage_path}")
        return storage_path

    try:
        shutil.copyfile(source_path, storage_path)
        if debug:
            logger.debug(f"Copied asset to app storage: {storage_path}")
        return storage_path
    except Exception as exc:
        if debug:
            logger.debug(f"Could not copy asset to app storage: {exc}")
        return source_path


def read_android_content_uri(uri: str) -> str:
    """Read text content from an Android content:// URI."""
    from jnius import autoclass

    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Uri = autoclass('android.net.Uri')
    InputStreamReader = autoclass('java.io.InputStreamReader')
    BufferedReader = autoclass('java.io.BufferedReader')
    StringBuilder = autoclass('java.lang.StringBuilder')

    activity = PythonActivity.mActivity
    resolver = activity.getContentResolver()
    input_stream = resolver.openInputStream(Uri.parse(uri))
    if input_stream is None:
        raise FileNotFoundError(f'No se pudo abrir el contenido: {uri}')

    reader = BufferedReader(InputStreamReader(input_stream, 'UTF-8'))
    builder = StringBuilder()
    line = reader.readLine()
    first = True
    while line is not None:
        if not first:
            builder.append('\n')
        builder.append(line)
        first = False
        line = reader.readLine()

    reader.close()
    input_stream.close()
    return str(builder.toString())


def import_json_to_app_storage(source: str, target_name='service_account.json') -> str:
    """Copy a selected JSON file into app storage and return its stable path."""
    target_path = os.path.join(get_app_storage_dir(), target_name)

    if source.startswith('content://'):
        content = read_android_content_uri(source)
        with open(target_path, 'w', encoding='utf-8') as file_obj:
            file_obj.write(content)
        return target_path

    if os.path.exists(source):
        shutil.copyfile(source, target_path)
        return target_path

    raise FileNotFoundError(source)


class Config:
    CONFIG_FILE = os.path.join(get_app_storage_dir(), 'config.json')

    @classmethod
    def load(cls):
        if not os.path.exists(cls.CONFIG_FILE):
            return {}
        try:
            with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    @classmethod
    def save(cls, data: dict):
        with open(cls.CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class TrainingSession:
    """Simple in-memory manager for the current training (list of exercises)."""
    _exercises = []

    @classmethod
    def clear(cls):
        cls._exercises = []

    @classmethod
    def add_exercise(cls, exercise: dict):
        cls._exercises.append(exercise)

    @classmethod
    def remove_exercise(cls, index: int):
        if 0 <= index < len(cls._exercises):
            cls._exercises.pop(index)

    @classmethod
    def get_exercises(cls):
        return list(cls._exercises)

