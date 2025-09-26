
import argparse, re
from pathlib import Path

BLOCK_START = re.compile(r"^===FILE:\s*(?P<path>.+?)\s*===$", re.MULTILINE)
BLOCK_END = re.compile(r"^===END===$", re.MULTILINE)

def parse_blocks(text: str):
    pos = 0
    while True:
        m = BLOCK_START.search(text, pos)
        if not m:
            break
        file_path = m.group("path").strip()
        start = m.end()
        m_end = BLOCK_END.search(text, start)
        if not m_end:
            raise ValueError(f"Bloque para '{file_path}' no tiene '===END==='")
        content = text[start:m_end.start()]
        pos = m_end.end()
        yield file_path, content.lstrip('\n')

def main():
    ap = argparse.ArgumentParser(description="Arma un proyecto desde bloques de archivos en un texto.")
    ap.add_argument("--input", required=True, help="Ruta al .txt con los bloques")
    ap.add_argument("--out", required=True, help="Carpeta destino del proyecto")
    args = ap.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    count = 0
    for rel_path, content in parse_blocks(text):
        dest = out / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        print(f"[WRITE] {dest}")
        count += 1

    if count == 0:
        raise SystemExit("No se encontraron bloques ===FILE: ... ===")
    print(f"Listo. Archivos creados: {count}")

if __name__ == "__main__":
    main()
