#!/usr/bin/env python3
"""
remove_outer_quotes.py

Percorre uma pasta (recursivamente) e, para cada arquivo com extensão .json,
remove uma aspa dupla (") no começo e outra no final do conteúdo do arquivo,
quando presentes. Salva substituindo o arquivo original por padrão e cria um
backup com extensão .bak (pode desativar com --no-backup).

Uso:
    python remove_outer_quotes.py /caminho/para/pasta
    python remove_outer_quotes.py        # usa o diretório atual

Opções:
    --no-backup    : não criar backups .bak (sobrescreve direto)
"""

import sys
import os
import argparse
from pathlib import Path

def read_file_try_encodings(path):
    encs = ("utf-8", "utf-8-sig", "latin-1")
    last_exc = None
    for e in encs:
        try:
            with open(path, "r", encoding=e) as f:
                return f.read(), e
        except Exception as exc:
            last_exc = exc
    raise last_exc

def write_file(path, text, encoding):
    with open(path, "w", encoding=encoding) as f:
        f.write(text)

def remove_outer_quotes_from_text(text):
    # encontra primeiro e último caractere não-whitespace
    if not text:
        return text, False
    # keep leading/trailing whitespace to preserve formatting
    leading_ws_len = len(text) - len(text.lstrip("\r\n\t "))
    trailing_ws_len = len(text) - len(text.rstrip("\r\n\t "))
    # slice indices for non-whitespace region
    start_idx = leading_ws_len
    end_idx = len(text) - trailing_ws_len  # exclusive
    if start_idx >= end_idx:
        return text, False
    segment = text[start_idx:end_idx]
    if len(segment) >= 2 and segment[0] == '"' and segment[-1] == '"':
        # remove only the outer quotes, keep inner text as-is
        new_segment = segment[1:-1]
        new_text = text[:start_idx] + new_segment + text[end_idx:]
        return new_text, True
    return text, False

def process_file(path: Path, make_backup: bool = True):
    try:
        content, encoding = read_file_try_encodings(path)
    except Exception as e:
        return False, f"erro lendo ({e})"

    new_content, changed = remove_outer_quotes_from_text(content)
    if not changed:
        return False, "sem alteração necessária"

    # backup
    if make_backup:
        bak = path.with_suffix(path.suffix + ".bak")
        try:
            if not bak.exists():
                # copy original content to .bak using same encoding
                write_file(bak, content, encoding)
        except Exception as e:
            return False, f"falha ao criar backup ({e})"

    # overwrite original (mantendo a mesma codificação que lemos)
    try:
        write_file(path, new_content, encoding)
        return True, "substituído"
    except Exception as e:
        return False, f"falha ao salvar ({e})"

def walk_and_process(root: Path, make_backup: bool = True):
    stats = {"processed": 0, "changed": 0, "errors": 0}
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith(".json"):
                stats["processed"] += 1
                full = Path(dirpath) / fn
                ok, msg = process_file(full, make_backup=make_backup)
                if ok:
                    stats["changed"] += 1
                    print(f"[OK]  {full} -> {msg}")
                else:
                    if msg == "sem alteração necessária":
                        print(f"[SKIP]{full} -> {msg}")
                    else:
                        stats["errors"] += 1
                        print(f"[ERR] {full} -> {msg}")
    return stats

def main():
    ap = argparse.ArgumentParser(description="Remover aspas externas de arquivos .json")
    ap.add_argument("folder", nargs="?", default=".", help="pasta raiz para processar")
    ap.add_argument("--no-backup", action="store_true", help="não criar arquivo .bak antes de sobrescrever")
    args = ap.parse_args()

    root = Path(args.folder).resolve()
    if not root.exists() or not root.is_dir():
        print("Erro: pasta inválida:", root)
        sys.exit(1)

    print(f"Processando pasta: {root}")
    stats = walk_and_process(root, make_backup=not args.no_backup)
    print("-----")
    print(f"Arquivos .json verificados: {stats['processed']}")
    print(f"Arquivos modificados: {stats['changed']}")
    print(f"Erros: {stats['errors']}")

if __name__ == "__main__":
    main()
