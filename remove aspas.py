#!/usr/bin/env python3
"""
fix_json_charts_no_backup.py

- Percorre recursivamente uma pasta.
- Remove aspas duplas externas do conteúdo de cada .json (primeiro/último caractere não-branco).
- Se for JSON válido e contiver "ChartBF" ou "ChartDad" (strings), normaliza separadores
  para ter exatamente dois espaços entre campos numéricos (e garante dois espaços antes de
  palavras de metadata como "Eye Note").
- Sobrescreve os arquivos sem criar backups.

Uso:
    python fix_json_charts_no_backup.py /caminho/para/pasta
    python fix_json_charts_no_backup.py    # usa pasta atual
"""
import sys
import os
import json
import re
from pathlib import Path

NUM_RE = r'-?\d+(?:\.\d+)?'  # número inteiro ou float (com sinal opcional)

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
    end_idx = len(text) - trailing_ws_len  # exclusive
    if start_idx >= end_idx:
        return text, False
    segment = text[start_idx:end_idx]
    if len(segment) >= 2 and segment[0] == '"' and segment[-1] == '"':
        new_segment = segment[1:-1]
        new_text = text[:start_idx] + new_segment + text[end_idx:]
        return new_text, True
    return text, False

def normalize_separators_for_chart(s: str) -> str:
    """
    Objetivo: garantir dois espaços entre campos numéricos no 'Chart' string,
    sem quebrar metadata textual (ex: "Eye Note"). Regras aplicadas:
    - Substitui repetidamente ocorrências de: number<single-space>number -> number<two-spaces>number
    - Garante também dois espaços entre number e uma palavra (metadata) que venha depois.
    - Não altera múltiplos espaços já corretos.
    """
    if not isinstance(s, str) or s.strip() == "":
        return s

    # 1) Repetidamente transformar número<single_space>número -> número<2spaces>número
    pattern_num_num = re.compile(rf'(?P<a>{NUM_RE}) (?P<b>{NUM_RE})')
    prev = None
    out = s
    # loop até estabilizar (resolve cadeias com mais de um espaço faltando)
    while prev != out:
        prev = out
        out = pattern_num_num.sub(r'\g<a>  \g<b>', out)

    # 2) Garantir dois espaços entre número e palavra (metadata) — ex: "0.00 Eye Note" -> "0.00  Eye Note"
    # Usa lookahead para não engolir as palavras seguintes
    pattern_num_word = re.compile(rf'(?P<a>{NUM_RE}) (?=(?:[A-Za-zÀ-ÿ]))')
    out = pattern_num_word.sub(r'\g<a>  ', out)

    # 3) Às vezes pode haver casos como "1  Eye Note" (com já 2 espaços) — ok.
    # 4) Para segurança, evitar colapsar espaços em outras partes: não fazemos mais substituições.
    return out

def process_json_text(original_text: str):
    """
    Remove aspas externas e, se for JSON válido, normaliza ChartBF/ChartDad.
    Retorna (new_text, changed_bool, reason)
    """
    text_no_outer, removed_quote = remove_outer_quotes_from_text(original_text)

    # tentar decodificar JSON
    try:
        obj = json.loads(text_no_outer)
    except Exception:
        # não é JSON válido: apenas retornamos a remoção de aspas (se ocorreu) e ponto.
        return text_no_outer, removed_quote, "texto (não json) - apenas remoção de aspas aplicada se necessário"

    changed = removed_quote
    # se for dict, verificar keys
    if isinstance(obj, dict):
        for key in ("ChartBF", "ChartDad"):
            if key in obj and isinstance(obj[key], str):
                before = obj[key]
                after = normalize_separators_for_chart(before)
                if after != before:
                    obj[key] = after
                    changed = True
    else:
        # se for JSON mas não dicionário, não mexemos além da possível remoção de aspas
        pass

    # serializar de volta — sem indent, para não alterar muito o formato original
    new_text = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    return new_text, changed, "json modificado" if changed else "json sem alterações relevantes"

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
        return True, reason + " (sobrescrito sem backup)"
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
                    if msg.startswith("json") or msg == "sem alteração necessária" or msg.startswith("texto (não json)"):
                        # tratamos como skip informativo
                        print(f"[SKIP]{full} -> {msg}")
                    else:
                        stats["errors"] += 1
                        print(f"[ERR] {full} -> {msg}")
    return stats

def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "."
    root = Path(folder).resolve()
    if not root.exists() or not root.is_dir():
        print("Erro: pasta inválida:", root)
        sys.exit(1)

    print(f"Processando pasta: {root}")
    print("Atenção: arquivos serão sobrescritos sem backup.")
    stats = walk_and_process(root)
    print("-----")
    print(f"Arquivos .json verificados: {stats['processed']}")
    print(f"Arquivos modificados: {stats['changed']}")
    print(f"Erros: {stats['errors']}")

if __name__ == "__main__":
    main()
