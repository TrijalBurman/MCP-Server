import os, re, unicodedata
from datetime import datetime
from pathlib import Path
import yaml

class ProjectMemory:
    def __init__(self, memory_dir):
        self.memory_dir  = Path(memory_dir)
        self.notes_dir   = self.memory_dir / "notes"
        self.status_path = self.memory_dir / "project_status.md"
        if not self.status_path.exists():
            self.status_path.write_text("# Project Status\n\n_No status yet._\n")

    def read_status(self, section=None):
        c = self.status_path.read_text(encoding="utf-8")
        if not section: return c
        m = re.search(rf"## {re.escape(section)}\n(.*?)(?=\n## |\Z)", c, re.DOTALL)
        return m.group(0) if m else f"Section '{section}' not found."

    def write_status(self, section, content):
        existing = self.status_path.read_text(encoding="utf-8")
        header   = f"## {section}"
        block    = f"{header}\n\n{content.strip()}\n"
        pat      = rf"{re.escape(header)}\n.*?(?=\n## |\Z)"
        updated  = re.sub(pat, block.rstrip(), existing, flags=re.DOTALL) if re.search(pat, existing, re.DOTALL) \
                   else existing.rstrip() + "\n\n" + block
        self.status_path.write_text(updated, encoding="utf-8")

    def full_status(self):
        return self.status_path.read_text(encoding="utf-8")

    @staticmethod
    def _slug(t):
        t = unicodedata.normalize("NFKD",t).encode("ascii","ignore").decode()
        return re.sub(r"[\s-]+","_",re.sub(r"[^\w\s-]","",t).strip().lower())[:80]

    def add_note(self, title, body, tags=None):
        ts   = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        path = self.notes_dir / f"{ts}_{self._slug(title)}.md"
        path.write_text(f"---\ntitle: {title}\ntags: [{', '.join(tags or [])}]\ncreated: {ts}\n---\n\n{body}\n")
        return str(path)

    def list_notes(self):
        out = []
        for p in sorted(self.notes_dir.glob("*.md")):
            txt, meta = p.read_text(encoding="utf-8"), {}
            m = re.match(r"---\n(.*?)\n---", txt, re.DOTALL)
            if m:
                try: meta = yaml.safe_load(m.group(1)) or {}
                except: pass
            out.append({"filename":p.name,"title":meta.get("title",p.stem),"tags":meta.get("tags",[]),"created":meta.get("created","")})
        return out

    def delete_note(self, title):
        for p in self.notes_dir.glob(f"*{self._slug(title)}*.md"):
            p.unlink(); return True
        return False
