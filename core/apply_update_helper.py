from __future__ import annotations
import sys
from pathlib import Path

base = Path(sys.argv[1]).resolve()
stage = Path(sys.argv[2]).resolve()

# The helper lives under <Goje>\core, so Python's default sys.path[0] is
# <Goje>\core. Add the application root before importing package modules.
sys.path.insert(0, str(base))

from core.audit import AuditLog
from core.permanent_updater import PermanentUpdater

logger = AuditLog(str(base / "data" / "audit.log"))
result = PermanentUpdater(base, logger).apply(str(stage))
print(result)
