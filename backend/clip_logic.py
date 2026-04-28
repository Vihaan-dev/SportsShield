import os
import faiss
import numpy as np

# All heavy imports (torch, open_clip) are lazy-loaded inside functions
# to prevent segfaults and startup crashes.

MODEL_NAME = 'ViT-B-32'
PRETRAINED = 'openai'  # Use 'openai' weights (smaller, ships with open_clip, no extra download)

FAISS_CLIP_INDEX_PATH = "../data/clip_faiss.index"
VECTOR_DIMENSION = 512

# ---- Lazy model singleton ----
_model = None
_preprocess = None

def get_model():
    global _model, _preprocess
    if _model is None:
        import torch
        import open_clip
        # Force CPU for stability on macOS
        device = "cpu"
        _model, _, _preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=PRETRAINED, device=device)
        _model.eval()
    return _model, _preprocess

# ---- FAISS index (loaded once) ----
_index = None

def get_index():
    global _index
    if _index is None:
        if os.path.exists(FAISS_CLIP_INDEX_PATH):
            _index = faiss.read_index(FAISS_CLIP_INDEX_PATH)
        else:
            _index = faiss.IndexFlatIP(VECTOR_DIMENSION)
    return _index

def compute_embedding(image_path: str) -> np.ndarray:
    """
    Computes Semantic CLIP embedding.
    """
    import torch
    from PIL import Image

    model, preprocess = get_model()
    image = preprocess(Image.open(image_path)).unsqueeze(0)
    
    with torch.no_grad():
        image_features = model.encode_image(image)
        
    # Normalize for cosine similarity matching in FAISS Inner Product
    image_features /= image_features.norm(dim=-1, keepdim=True)
    return image_features.cpu().numpy()

def add_to_index(embedding_vector: np.ndarray) -> int:
    """
    Saves new semantic vector and returns the semantic FAISS ID.
    """
    index = get_index()
    assigned_id = index.ntotal
    index.add(embedding_vector)
    faiss.write_index(index, FAISS_CLIP_INDEX_PATH)
    return assigned_id

def search_index(embedding_vector: np.ndarray, top_k: int = 1):
    """
    Searches the Semantic index.
    Returns (similarity, clip_faiss_id) using inner product (cosine similarity).
    """
    index = get_index()
    if index.ntotal == 0:
        return []

    similarities, indices = index.search(embedding_vector, top_k)
    
    results = []
    for sim, clip_faiss_id in zip(similarities[0], indices[0]):
        if clip_faiss_id != -1:
            results.append({
                "clip_faiss_id": int(clip_faiss_id),
                "similarity": float(sim)
            })
    return results
