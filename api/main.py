import os
from pathlib import Path

from polaris.app import create_app

app = create_app(Path(os.environ.get("POLARIS_DATA", Path(__file__).resolve().parent / "data")))
