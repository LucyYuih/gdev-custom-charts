#!/usr/bin/env python3
"""
remove_quotes_and_normalize_spaces.py

Percorre recursivamente uma pasta procurando por arquivos .json.
Para cada arquivo:
 - remove aspas duplas externas que envolvem todo o conteúdo (se existirem)
 - verifica se os separadores entre valores (sequências de whitespace entre
   caracteres não-brancos) são exatamente duas spaces. Se não forem, normaliza
   para duas spaces.
 - sobrescreve o arquivo (sem criar backup).

Uso:
    python remove_quotes_and_normalize_spaces.py /caminho/para/pasta
    python remove_quotes_and_normalize_spaces.py    # usa o diretório atual
"""
import sys
import os
import argparse
from pathlib import Path
import re

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

def remove_outer_quotes(text):
    # mantém whitespace externo; remove aspas duplas apenas se envolverem o bloco não-whitespace
    if not text:
        return text, False
    leading_ws_len = len(text) - len(text.lstrip("\r\n\t "))
    trailing_ws_len = len(text) - len(text.rstrip("\r\n\t "))
    start_idx = leading_ws_len
    end_idx = len(text) - trailing_ws_len  # exclusivo
    if start_idx >= end_idx:
        return text, False
    segment = text[start_idx:end_idx]
    if len(segment) >= 2 and segment[0] == '"' and segment[-1] == '"':
        new_segment = segment[1:-1]
        new_text = text[:start_idx] + new_segment + text[end_idx:]
        return new_text, True
    return text, False

def separators_all_two_spaces(segment):
    # encontra todas as sequências de whitespace entre \S ... \S
    # retorna True se todas forem exatamente '  '
    runs = re.findall(r'(?<=\S)(\s+)(?=\S)', segment)
    if not runs:
        # sem separadores encontrados -> consideramos "ok"
        return True
    return all(r == '  ' for r in runs)

def normalize_segment_to_two_spaces(segment):
    # Se multiline: processa linha por linha, preservando quebras.
    if '\n' in segment:
        lines = segment.splitlines(keepends=True)
        new_lines = []
        for line in lines:
            # separar conteúdo da quebra
            if line.endswith('\r\n'):
                content, ending = line[:-2], '\r\n'
            elif line.endswith('\n') or line.endswith('\r'):
                content, ending = line[:-1], line[-1]
            else:
                content, ending = line, ''
            # normaliza sequências de espaços/tabs para duas spaces
            # não converte novoslines (já separados)
            # também remove tabs em favor de spaces
            new_content = re.sub(r'[ \t]+', '  ', content)
            # se houver outros whitespace invisíveis no meio (p.ex. unicode), convert to single space then to two
            new_content = re.sub(r'\u00A0', ' ', new_content)  # exemplo de nbsp
            new_lines.append(new_content + ending)
        return ''.join(new_lines)
    else:
        # single line: qualquer sequencia de whitespace vira duas spaces
        return re.sub(r'\s+', '  ', segment)

def process_file(path: Path):
    try:
        content, encoding = read_file_try_encodings(path)
    except Exception as e:
        return False, f"erro lendo ({e})"

    changed_any = False

    # 1) remover aspas externas se existirem
    content_after_quotes, removed = remove_outer_quotes(content)
    if removed:
        changed_any = True
        content = content_after_quotes

    # 2) identificar a região não-whitespace (pra não tocar em leading/trailing)
    leading_ws_len = len(content) - len(content.lstrip("\r\n\t "))
    trailing_ws_len = len(content) - len(content.rstrip("\r\n\t "))
    start_idx = leading_ws_len
    end_idx = len(content) - trailing_ws_len  # exclusive
    if start_idx < end_idx:
        segment = content[start_idx:end_idx]
        # checar se todos separadores entre tokens são exatamente duas spaces
        if not separators_all_two_spaces(segment):
            new_segment = normalize_segment_to_two_spaces(segment)
            # se mudou, aplica
            if new_segment != segment:
                changed_any = True
                content = content[:start_idx] + new_segment + content[end_idx:]

    if not changed_any:
        return False, "sem alteração necessária"

    # sobrescreve arquivo (SEM BACKUP)
    try:
        write_file(path, content, encoding)
        return True, "modificado"
    except Exception as e:
        return False, f"falha ao salvar ({e})"

def walk_and_process(root: Path):
    stats = {"processed": 0, "modified": 0, "skipped": 0, "errors": 0}
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith(".json"):
                stats["processed"] += 1
                full = Path(dirpath) / fn
                ok, msg = process_file(full)
                if ok:
                    stats["modified"] += 1
                    print(f"[MOD]  {full} -> {msg}")
                else:
                    if msg == "sem alteração necessária":
                        stats["skipped"] += 1
                        print(f"[OK]   {full} -> {msg}")
                    else:
                        stats["errors"] += 1
                        print(f"[ERR]  {full} -> {msg}")
    return stats

def main():
    ap = argparse.ArgumentParser(description="Remove aspas externas e normaliza separadores para duas spaces em .json (sem backup).")
    ap.add_argument("folder", nargs="?", default=".", help="pasta raiz para processar")
    args = ap.parse_args()

    root = Path(args.folder).resolve()
    if not root.exists() or not root.is_dir():
        print("Erro: pasta inválida:", root)
        sys.exit(1)

    print(f"Processando pasta: {root} (sem backups)")
    stats = walk_and_process(root)
    print("-----")
    print(f"Arquivos .json verificados: {stats['processed']}")
    print(f"Arquivos modificados: {stats['modified']}")
    print(f"Arquivos já OK (sem mudança): {stats['skipped']}")
    print(f"Erros: {stats['errors']}")

if __name__ == "__main__":
    main()
