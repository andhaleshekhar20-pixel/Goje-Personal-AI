from __future__ import annotations
import sys
from pathlib import Path
from core.audit import AuditLog
from core.permanent_updater import PermanentUpdater

base = Path(sys.argv[1])
stage = sys.argv[2]
logger = AuditLog(str(base / "data" / "audit.log"))
PermanentUpdater(base, logger).apply(stage)
