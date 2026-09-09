"""Extract model rows embedded in the Artificial Analysis leaderboard page."""
import json, re

def _arrays(text, key='"models":['):
    """Yield JSON arrays that follow `key`, using bracket matching."""
    for m in re.finditer(re.escape(key), text):
        i = m.end() - 1
        depth, instr, esc = 0, False, False
        for j in range(i, len(text)):
            c = text[j]
            if instr:
                if esc: esc = False
                elif c == '\\': esc = True
                elif c == '"': instr = False
                continue
            if c == '"': instr = True
            elif c == '[': depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    try: yield json.loads(text[i:j+1])
                    except Exception: pass
                    break

def extract(html):
    text = html.replace('\\"', '"').replace('\\n', ' ')
    rows = {}
    keys = set()
    for arr in _arrays(text):
        for r in arr:
            if not isinstance(r, dict) or 'slug' not in r: continue
            clean = {k: (None if v == '$undefined' else v) for k, v in r.items()}
            keys.update(clean)
            rows.setdefault(clean['slug'], {}).update(
                {k: v for k, v in clean.items() if v is not None})
    return rows, keys

if __name__ == '__main__':
    import sys
    rows, keys = extract(open(sys.argv[1], encoding='utf-8', errors='replace').read())
    print(f'{len(rows)} models, {len(keys)} distinct keys')
    print(sorted(keys))
