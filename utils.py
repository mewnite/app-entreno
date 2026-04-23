import json
import os
import logging


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

