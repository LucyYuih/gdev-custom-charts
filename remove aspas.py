#!/usr/bin/env python3
"""
fix_json_charts_no_backup_v3.py

Versão robusta:
- Remove aspas externas.
- Detecta e normaliza qualquer chave que contenha 'chart' (case-insensitive).
- Normaliza strings/listas que pareçam chart (garante 2 espaços entre blocos; metadata interno com 1 espaço).
- Se arquivo não for JSON, tenta normalizar trechos que parecem chart.
- Sobrescreve sem backup.
"""
import sys
import os
import json
import re
from pathlib import Path

NUM_RE = re.compile(r'^-?\d+(?:\.\d+)?$')  # inteiro ou float
POSSIBLE_CHART_LINE = re.compile(r'(?:-?\d+(?:\.\d+)?\s+){5,}')  # 5+ números com espaços -> provável chart

def read_file_try_encodings(path: Path):
    encs = ("utf-8", "utf-8-sig", "latin-1")
    last_exc = None
    for e in encs:
        try:
            with open(path, "r", encoding=e) as f:
                return f.read(), e
        except Exception as exc:
            last_exc = exc
    raise last_exc

def write_file(path: Path, text: str, encoding: str):
    with open(path, "w", encoding=encoding) as f:
        f.write(text)

def remove_outer_quotes_from_text(text: str):
    if not text:
        return text, False
    leading_ws_len = len(text) - len(text.lstrip("\r\n\t "))
    trailing_ws_len = len(text) - len(text.rstrip("\r\n\t "))
    start_idx = leading_ws_len
    end_idx = len(text) - trailing_ws_len
    if start_idx >= end_idx:
        return text, False
    segment = text[start_idx:end_idx]
    if len(segment) >= 2 and segment[0] == '"' and segment[-1] == '"':
        new_segment = segment[1:-1]
        new_text = text[:start_idx] + new_segment + text[end_idx:]
        return new_text, True
    return text, False

def is_numeric_token(tok: str) -> bool:
    return NUM_RE.match(tok) is not None

def normalize_chart_string(s: str) -> str:
    if not isinstance(s, str):
        return s
    leading = re.match(r'^\s*', s).group(0)
    trailing = re.search(r'\s*$', s).group(0)
    body = s.strip()
    if body == "":
        return s

    # split por qualquer whitespace
    raw_tokens = re.split(r'\s+', body)
    chunks = []
    i = 0
    n = len(raw_tokens)
    while i < n:
        tok = raw_tokens[i]
        if is_numeric_token(tok):
            chunks.append(tok)
            i += 1
        else:
            meta = [tok]
            i += 1
            while i < n and not is_numeric_token(raw_tokens[i]):
                meta.append(raw_tokens[i])
                i += 1
            chunks.append(' '.join(meta))
    out = '  '.join(chunks)
    return leading + out + trailing

def normalize_in_obj(obj):
    """
    Percorre recursivamente obj (dict/list) e normaliza strings/lists em chaves 'chart'
    ou qualquer string que pareça chart.
    Retorna (changed_bool)
    """
    changed = False
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            v = obj[k]
            lk = k.lower()
            # se a chave indica 'chart' (pegamos qualquer chave que contenha 'chart')
            if 'chart' in lk:
                # se for string
                if isinstance(v, str):
                    newv = normalize_chart_string(v)
                    if newv != v:
                        obj[k] = newv
                        changed = True
                # se for lista de strings
                elif isinstance(v, list):
                    newlist = []
                    replaced = False
                    for item in v:
                        if isinstance(item, str):
                            nv = normalize_chart_string(item)
                            newlist.append(nv)
                            if nv != item:
                                replaced = True
                                changed = True
                        else:
                            newlist.append(item)
                    if replaced:
                        obj[k] = newlist
                else:
                    # se outro tipo, tentamos percorrer recursivamente
                    if normalize_in_obj(v):
                        changed = True
            else:
                # caso a chave não contenha 'chart', ainda podemos ter strings longas que parecem chart
                if isinstance(v, str):
                    if POSSIBLE_CHART_LINE.search(v):
                        nv = normalize_chart_string(v)
                        if nv != v:
                            obj[k] = nv
                            changed = True
                else:
                    if normalize_in_obj(v):
                        changed = True
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            if isinstance(item, str):
                if POSSIBLE_CHART_LINE.search(item):
                    nv = normalize_chart_string(item)
                    if nv != item:
                        obj[idx] = nv
                        changed = True
            else:
                if normalize_in_obj(item):
                    changed = True
    # outros tipos não alterados
    return changed

def process_json_text(original_text: str):
    text_no_outer, removed_quote = remove_outer_quotes_from_text(original_text)

    # tenta JSON
    try:
        obj = json.loads(text_no_outer)
    except Exception:
        # texto não-json: busca trechos que pareçam chart e normaliza no texto bruto
        text = text_no_outer
        changed = removed_quote
        def repl_match(m):
            nonlocal changed
            chunk = m.group(0)
            newchunk = normalize_chart_string(chunk)
            if newchunk != chunk:
                changed = True
            return newchunk
        new_text = POSSIBLE_CHART_LINE.sub(repl_match, text)
        return new_text, changed, "texto não-json (trechos normalizados se aplicável)"
    # se json válido, percorre e normaliza
    changed = removed_quote
    if normalize_in_obj(obj):
        changed = True
    if not changed:
        return text_no_outer, False, "json sem alterações"
    # serializa mantendo acentos e sem espaços extras
    new_text = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    return new_text, True, "json modificado"

def process_file(path: Path):
    try:
        content, encoding = read_file_try_encodings(path)
    except Exception as e:
        return False, f"erro lendo ({e})"
    new_content, changed, reason = process_json_text(content)
    if not changed:
        return False, reason
    try:
        write_file(path, new_content, encoding)
        return True, reason + " (sobrescrito)"
    except Exception as e:
        return False, f"falha ao salvar ({e})"

def walk_and_process(root: Path):
    stats = {"processed": 0, "changed": 0, "errors": 0}
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith(".json"):
                stats["processed"] += 1
                full = Path(dirpath) / fn
                ok, msg = process_file(full)
                if ok:
                    stats["changed"] += 1
                    print(f"[OK]  {full} -> {msg}")
                else:
                    print(f"[SKIP]{full} -> {msg}" if msg.startswith(("json","texto")) else f"[ERR] {full} -> {msg}")
                    if msg.startswith("erro"):
                        stats["errors"] += 1
    return stats

def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    root = Path(folder).resolve()
    if not root.exists() or not root.is_dir():
        print("Erro: pasta inválida:", root)
        sys.exit(1)
    print(f"Processando pasta: {root}")
    print("Atenção: sobrescrevendo arquivos sem backup.")
    stats = walk_and_process(root)
    print("-----")
    print(f"Verificados: {stats['processed']} .json")
    print(f"Modificados: {stats['changed']}")
    print(f"Erros: {stats['errors']}")

if __name__ == '__main__':
    main()
