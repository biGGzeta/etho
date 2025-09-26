
import argparse, json, hashlib
from pathlib import Path

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(description="Verifica integridad contra manifest.json (SHA256).")
    ap.add_argument("--folder", required=True, help="Carpeta a verificar (debe contener manifest.json o se debe pasar con --manifest)")
    ap.add_argument("--manifest", help="Ruta alternativa a manifest.json si no está en la carpeta")
    args = ap.parse_args()

    folder = Path(args.folder)
    manifest_path = Path(args.manifest) if args.manifest else (folder / "manifest.json")
    if not manifest_path.exists():
        raise SystemExit(f"No se encontró manifest.json en {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mismatches = []
    missing = []

    for entry in manifest["files"]:
        rel = entry["path"]
        expected = entry["sha256"]
        f = folder / rel
        if not f.exists():
            missing.append(rel)
            continue
        digest = sha256_file(f)
        if digest != expected:
            mismatches.append((rel, expected, digest))

    if missing or mismatches:
        if missing:
            print("[MISSING] Archivos faltantes:")
            for rel in missing:
                print("  -", rel)
        if mismatches:
            print("[MISMATCH] Archivos con hash diferente:")
            for rel, exp, got in mismatches:
                print(f"  - {rel}\n      esperado={exp}\n      actual  ={got}")
        raise SystemExit("Verificación FALLIDA.")
    else:
        print("OK. Integridad verificada.")

if __name__ == "__main__":
    main()
