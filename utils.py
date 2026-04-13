import json
import os


class Config:
    CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

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

