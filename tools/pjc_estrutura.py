"""Resumo estrutural de um arquivo .PJC (somente leitura)."""
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter

path = sys.argv[1]
with zipfile.ZipFile(path) as z:
    name = z.namelist()[0]
    root = ET.fromstring(z.read(name))

paths = Counter()


def walk(el, prefix, depth):
    p = f"{prefix}/{el.tag}"
    paths[p] += 1
    if depth < int(sys.argv[2]) if len(sys.argv) > 2 else 6:
        for ch in el:
            walk(ch, p, depth + 1)


walk(root, "", 0)
for p, n in sorted(paths.items()):
    if len(list(filter(None, p.split("/")))) <= (int(sys.argv[2]) if len(sys.argv) > 2 else 6):
        print(f"{n:5d} {p}")
