import os
import glob
import shutil
import json
import time
from datetime import datetime

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def discover_latest_csv(data_dir="data", patterns=("*.csv", "*.txt")):
    files = []
    for pat in patterns:
        files.extend(glob.glob(os.path.join(data_dir, pat)))
    if not files:
        return None
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return files[0]

def archive_copy(src_path: str, archive_dir: str, prefix: str = "feed"):
    ensure_dir(archive_dir)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base = os.path.basename(src_path)
    dst = os.path.join(archive_dir, f"{prefix}_{ts}_{base}")
    try:
        shutil.copy2(src_path, dst)
        return dst
    except Exception:
        return None

def write_json(obj, path):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def create_minimal_template(path: str):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write("timestamp,price,bid_vol,ask_vol,tb_ratio\n")
        f.write("2025-01-01 00:00:00,1000,10,12,0.52\n")
        f.write("2025-01-01 00:00:10,1000.2,11,11,0.51\n")
    return path
