"""
Diagnostic: outputs ONLY raw pHash distances for every test image
against registered originals. No ML models = no segfault risk.
"""
import os, sys, glob
import numpy as np
import faiss

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import imagehash
from PIL import Image

DATASET = os.path.join(PROJECT_ROOT, 'data', 'test_dataset')
ORIGINALS = os.path.join(DATASET, 'originals')

def compute_phash(path):
    img = Image.open(path)
    h = imagehash.phash(img)
    arr = np.array(h.hash, dtype='float32').flatten()
    return arr, str(h)

# Fresh in-memory FAISS
idx = faiss.IndexFlatL2(64)

original_files = sorted(glob.glob(os.path.join(ORIGINALS, '*.*')))
orig_map = {}
for f in original_files:
    vec, h = compute_phash(f)
    fid = idx.ntotal
    idx.add(np.expand_dims(vec, 0))
    orig_map[fid] = {'path': f, 'name': os.path.basename(f), 'hash': h}
    print(f"  orig #{fid}: {os.path.basename(f)}  hash={h}")

print()
print(f"{'Folder':<40} {'File':<28} {'Matched Orig':<22} {'pDist':>7}")
print("=" * 100)

folders = sorted([d for d in os.listdir(DATASET) if os.path.isdir(os.path.join(DATASET, d)) and d != 'originals'])

for folder in folders:
    fdir = os.path.join(DATASET, folder)
    files = sorted(glob.glob(os.path.join(fdir, '*.*')))
    for fp in files:
        fname = os.path.basename(fp)
        vec, _ = compute_phash(fp)
        D, I = idx.search(np.expand_dims(vec, 0), 1)
        dist = float(D[0][0])
        fid = int(I[0][0])
        orig_name = orig_map.get(fid, {}).get('name', '?')
        print(f"{folder:<40} {fname:<28} {orig_name:<22} {dist:>7.1f}")
    print("-" * 100)
