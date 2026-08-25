import logging
log = logging.getLogger(__name__)

class LocalEmbedder:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        log.info("Loading embedding model: %s", model_name)
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        log.info("Embedding model loaded.")

    def embed(self, texts):
        return self.model.encode(texts, show_progress_bar=False, convert_to_numpy=True).tolist()

    def embed_one(self, text): return self.embed([text])[0]
