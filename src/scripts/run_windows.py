from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

base = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or Path.home()) / "TSCurator"
log_dir = base / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "app_crash.log"

try:
    from thera_curator.app import main
    raise SystemExit(main())
except SystemExit:
    raise
except BaseException:
    detail = traceback.format_exc()
    try:
        log_file.write_text(detail, encoding="utf-8")
    except Exception:
        pass
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                "Thera-SAbDab WHO INN Curator could not start.\n\n"
                f"A crash log was written to:\n{log_file}",
                "Thera-SAbDab WHO INN Curator",
                0x10,
            )
        except Exception:
            pass
    raise
