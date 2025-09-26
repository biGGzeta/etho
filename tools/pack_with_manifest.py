
import argparse, hashlib, json, os
from pathlib import Path
import zipfile
from datetime import datetime

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(description="Empaqueta una carpeta en zip y genera manifest.json (SHA256).")
    ap.add_argument("--folder", required=True, help="Carpeta a empaquetar")
    ap.add_argument("--out", required=True, help="Ruta del zip de salida")
    args = ap.parse_args()

    folder = Path(args.folder).resolve()
    out_zip = Path(args.out).resolve()
    if not folder.is_dir():
        raise SystemExit(f"No existe carpeta: {folder}")

    manifest = {
        "folder": str(folder.name),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "files": []
    }

    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in folder.rglob("*"):
            if p.is_file():
                rel = p.relative_to(folder).as_posix()
                digest = sha256_file(p)
                manifest["files"].append({"path": rel, "sha256": digest, "bytes": p.stat().st_size})
                z.write(p, arcname=rel)
        # embed manifest.json at root of zip
        z.writestr("manifest.json", json.dumps(manifest, indent=2))

    print(f"[ZIP] creado: {out_zip}")
    print(f"[FILES] {len(manifest['files'])} archivos incluidos")

if __name__ == "__main__":
    main()
