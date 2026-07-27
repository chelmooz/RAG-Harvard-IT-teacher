import os
from pathlib import Path

count = 0
source_dir = Path('frontend/src')
for f in sorted(source_dir.rglob('*')):
    if f.suffix not in ('.js', '.css'):
        continue
    try:
        text = f.read_text(encoding='utf-8', errors='replace')
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.rstrip()
            if len(stripped) > 120:
                count += 1
                print(f"{f}:{i} ({len(stripped)})", file=__import__('sys').stderr)
    except Exception:
        pass
print(f"Total: {count}", file=__import__('sys').stderr)