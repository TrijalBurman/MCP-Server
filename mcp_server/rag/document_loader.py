import logging
from pathlib import Path
log = logging.getLogger(__name__)
CHUNK_SIZE, OVERLAP = 500, 100

def _chunk(text, source, page=0):
    chunks, start = [], 0
    while start < len(text):
        t = text[start:start+CHUNK_SIZE].strip()
        if t: chunks.append({"text":t,"source":source,"page":str(page)})
        start += CHUNK_SIZE - OVERLAP
    return chunks

def _pdf(p):
    import fitz
    out = []
    with fitz.open(str(p)) as d:
        for i,pg in enumerate(d): out.extend(_chunk(pg.get_text(), p.name, i+1))
    return out

def _docx(p):
    from docx import Document
    return _chunk("\n".join(x.text for x in Document(str(p)).paragraphs if x.text.strip()), p.name)

def _text(p): return _chunk(p.read_text(encoding="utf-8",errors="replace"), p.name)

LOADERS = {".pdf":_pdf,".docx":_docx,".md":_text,".txt":_text,".markdown":_text}

class DocumentLoader:
    def __init__(self, docs_dir, vs): self.dir=Path(docs_dir); self.vs=vs

    def ingest_file(self, path):
        fn = LOADERS.get(path.suffix.lower())
        if not fn: return 0
        self.vs.delete_by_source(path.name)
        chunks = fn(path); self.vs.add_chunks(chunks)
        log.info("Indexed %d chunks from %s", len(chunks), path.name); return len(chunks)

    def ingest_all(self):
        total = sum(self.ingest_file(p) for p in self.dir.iterdir()
                    if p.is_file() and p.suffix.lower() in LOADERS)
        log.info("Total: %d chunks", total); return total
