import logging, uuid
log = logging.getLogger(__name__)

class VectorStore:
    COLL = "documents"
    def __init__(self, db_dir, embedder):
        import chromadb
        from chromadb.config import Settings
        self.emb  = embedder
        self.coll = chromadb.PersistentClient(path=db_dir,settings=Settings(anonymized_telemetry=False)) \
                              .get_or_create_collection(self.COLL, metadata={"hnsw:space":"cosine"})
        log.info("VectorStore ready — %d chunks", self.coll.count())

    def add_chunks(self, chunks):
        if not chunks: return
        texts = [c["text"] for c in chunks]
        self.coll.add(ids=[str(uuid.uuid4()) for _ in chunks],
                      embeddings=self.emb.embed(texts), documents=texts,
                      metadatas=[{k:v for k,v in c.items() if k!="text"} for c in chunks])

    def search(self, query, top_k=5):
        if self.coll.count()==0:
            return [{"text":"No documents indexed yet.","source":"","score":0.0}]
        r = self.coll.query(query_embeddings=[self.emb.embed_one(query)],
                            n_results=min(top_k,self.coll.count()),
                            include=["documents","metadatas","distances"])
        return [{"text":t,"source":m.get("source",""),"page":m.get("page",""),"score":round(1-d,4)}
                for t,m,d in zip(r["documents"][0],r["metadatas"][0],r["distances"][0])]

    def delete_by_source(self, source):
        r = self.coll.get(where={"source":source})
        if r["ids"]: self.coll.delete(ids=r["ids"])

    def count(self): return self.coll.count()
