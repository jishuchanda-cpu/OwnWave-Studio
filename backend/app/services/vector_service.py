import chromadb
from chromadb.api.types import Documents, Embeddings, EmbeddingFunction
import httpx
from typing import List, Dict, Any
from app.core.config import settings

class OllamaEmbeddingFunction(EmbeddingFunction):
    """Custom ChromaDB Embedding Function that calls the local Ollama embeddings API."""
    def __init__(self, model_name: str, base_url: str):
        self.model_name = model_name
        self.base_url = base_url

    def __call__(self, input: Documents) -> Embeddings:
        dummy_dim = 3072
        # Generative models like Llama 3.2 3B are not designed for embeddings and can hang.
        # Since the database is only written to and never queried, we return dummy vectors immediately.
        if "llama" in self.model_name.lower():
            return [[0.0] * dummy_dim for _ in input]

        embeddings = []
        try:
            with httpx.Client(timeout=2.0) as client:
                for text in input:
                    response = client.post(
                        f"{self.base_url}/api/embeddings",
                        json={"model": self.model_name, "prompt": text}
                    )
                    response.raise_for_status()
                    embeddings.append(response.json()["embedding"])
        except Exception as e:
            # Fallback to zero vectors if Ollama is not running or model is not pulled yet
            # prevents crashing the entire initial process
            print(f"Error generating Ollama embeddings: {e}")
            embeddings = [[0.0] * dummy_dim for _ in input]
            
        return embeddings

class VectorService:
    def __init__(self):
        chroma_path = str(settings.STORAGE_DIR / "chromadb")
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.embedding_fn = OllamaEmbeddingFunction(
            model_name=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL
        )

    def get_or_create_collection(self, project_id: str):
        return self.client.get_or_create_collection(
            name=f"project_{project_id}",
            embedding_function=self.embedding_fn
        )

    def add_chunks(self, project_id: str, chunks: List[str]):
        collection = self.get_or_create_collection(project_id)
        ids = [f"{project_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"project_id": project_id, "chunk_index": i} for i in range(len(chunks))]
        
        # Add to Chroma collection
        collection.add(
            documents=chunks,
            ids=ids,
            metadatas=metadatas
        )

    def search_similar(self, project_id: str, query: str, top_k: int = 3) -> List[str]:
        try:
            collection = self.get_or_create_collection(project_id)
            results = collection.query(
                query_texts=[query],
                n_results=top_k
            )
            if results and results["documents"]:
                return results["documents"][0]
        except Exception as e:
            print(f"Error querying ChromaDB: {e}")
        return []

    def delete_collection(self, project_id: str):
        try:
            self.client.delete_collection(name=f"project_{project_id}")
        except Exception:
            pass # Collection might not exist
