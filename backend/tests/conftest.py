import os
import sys
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp()) / "test_laras.db"
os.environ["YSNA_DATABASE_URL"] = f"sqlite:///{_tmp.as_posix()}"
os.environ["YSNA_DATA_MODE"] = "DEMO"
os.environ["YSNA_WORKER_MODE"] = "external"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
