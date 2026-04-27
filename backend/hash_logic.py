import os
import faiss
import numpy as np
import imagehash
from PIL import Image

FAISS_INDEX_PATH = "../data/faiss.index"
VECTOR_DIMENSION = 64

if os.path.exists(FAISS_INDEX_PATH):
    index = faiss.read_index(FAISS_INDEX_PATH)
else:
    index = faiss.IndexFlatL2(VECTOR_DIMENSION)

def compute_phash(image_path: str) -> np.ndarray:
    """
    Computes a 64-bit perceptual hash for an image and returns it as a 64-len float32 numpy array.
    """
    img = Image.open(image_path)
    hash_obj = imagehash.phash(img)
    hash_array = np.array(hash_obj.hash, dtype='float32').flatten()
    return hash_array, str(hash_obj)

def add_to_index(hash_vector: np.ndarray) -> int:
    """
    Adds a float array to the FAISS index, saves it to disk, and returns the assigned FAISS ID.
    """
    assigned_id = index.ntotal
    vector_2d = np.expand_dims(hash_vector, axis=0)
    index.add(vector_2d)
    faiss.write_index(index, FAISS_INDEX_PATH)
    return assigned_id

def search_index(hash_vector: np.ndarray, top_k: int = 1):
    """
    Searches the FAISS index for the k nearest neighbors.
    Returns lists of (distance, faiss_id) matches.
    """
    if index.ntotal == 0:
        return []

    vector_2d = np.expand_dims(hash_vector, axis=0)
    distances, indices = index.search(vector_2d, top_k)
    
    results = []
    for dist, faiss_id in zip(distances[0], indices[0]):
        if faiss_id != -1:
            results.append({
                "faiss_id": int(faiss_id),
                "distance": float(dist)
            })
    return results
