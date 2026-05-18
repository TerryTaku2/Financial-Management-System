import glob
import re
import html
pattern = re.compile(r'(<option\b(?:(?!\bvalue\b)[^>])*)>([^<]*)</option>', re.IGNORECASE)
changed = []
for fp in glob.glob('frontend/pages/*.html'):
    with open(fp, 'r', encoding='utf-8') as f:
        text = f.read()
    def repl(m):
        attrs = m.group(1)
        txt = m.group(2)
        if re.search(r'\bvalue\b', attrs, re.IGNORECASE):
            return m.group(0)
        v = html.escape(txt, quote=True)
        return f'{attrs} value="{v}">{txt}</option>'
    new = pattern.sub(repl, text)
    if new != text:
        with open(fp, 'w', encoding='utf-8') as f:
            f.write(new)
        changed.append(fp)
print('files_modified=', len(changed))
for fp in changed:
    print(fp)
