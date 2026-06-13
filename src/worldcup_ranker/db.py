import json
from pathlib import Path
from typing import Any

class SimpleJSONDB:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.save({})

    def load(self) -> Any:
        with self.path.open('r', encoding='utf-8') as f:
            return json.load(f)

    def save(self, data: Any) -> None:
        with self.path.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
