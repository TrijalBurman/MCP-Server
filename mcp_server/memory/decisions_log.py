from datetime import datetime
from pathlib import Path
import yaml

class DecisionsLog:
    def __init__(self, memory_dir):
        self.path = Path(memory_dir) / "decisions.yaml"
        if not self.path.exists():
            self.path.write_text("decisions: []\n")

    def _load(self): return (yaml.safe_load(self.path.read_text()) or {}).get("decisions",[])
    def _save(self, d): self.path.write_text(yaml.dump({"decisions":d},allow_unicode=True,default_flow_style=False))

    def log_decision(self, title, rationale, outcome=""):
        d = self._load()
        entry = {"id":len(d)+1,"timestamp":datetime.utcnow().isoformat(),"title":title,"rationale":rationale,"outcome":outcome}
        d.append(entry); self._save(d); return entry

    def read_decisions(self, limit=20): return self._load()[-limit:]
