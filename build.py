"""Maakt het bladerboek van het prentenboek De Stip uit bron/De Stip.pdf.

De PDF heeft tien bladen van 42 x 21 cm: blad 1 is de omslag (links achterkant, rechts voorkant),
blad 2-10 zijn de dubbele pagina's 1-18. Het boek zelf is dicht 21 x 21 cm.

- web/pages/     pagina's voor het bladerboek (1600 x 1600)
- web/pages-hd/  scherpere versies voor inzoomen en de leesweergave (2400 x 2400)
- web/index.html volledige pagina voor Vercel
- artifact/      alleen de inhoud, voor een Claude-artifact

Gebruik:  python build.py            (pagina's worden alleen opnieuw gemaakt als de PDF nieuwer is)
          python build.py --render   (pagina's altijd opnieuw maken)
"""
import os, sys, json, hashlib, re
import pymupdf
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(HERE, 'web')
PDF = os.path.join(HERE, 'bron', 'De Stip.pdf')
SITE_URL = 'https://de-stip.vercel.app'
TITLE = 'De Stip'
DESC = 'Bladerboek van het prentenboek De Stip, over Chantal en Manon.'
N_PAGES = 20                                   # voorkant, p. 1-18, achterkant
SIZES = (('pages', 1600, 84), ('pages-hd', 2400, 86))
BG = (233, 230, 221)                           # --bg uit de template


def name(i):
    return f'p{i:02d}.jpg'


def version(folder):
    """Korte hash over de bestanden, zodat browsers na een update de nieuwe pagina's ophalen."""
    h = hashlib.sha1()
    for n in sorted(os.listdir(folder)):
        st = os.stat(os.path.join(folder, n))
        h.update(f'{n}{st.st_size}{int(st.st_mtime)}'.encode())
    return h.hexdigest()[:8]


def halves(doc):
    """(beeldindex, PDF-blad, uitsnede) voor elke pagina van het boek, in leesvolgorde."""
    out = []
    for k, page in enumerate(doc):
        r = page.rect
        L = pymupdf.Rect(0, 0, r.width / 2, r.height)
        R = pymupdf.Rect(r.width / 2, 0, r.width, r.height)
        if k == 0:
            out += [(0, page, R), (N_PAGES - 1, page, L)]
        else:
            out += [(2 * k - 1, page, L), (2 * k, page, R)]
    return sorted(out, key=lambda t: t[0])


def page_text(page, clip):
    """Lopende tekst van één pagina (voor schermlezers), zonder paginanummer."""
    mid = page.rect.width / 2
    left = clip.x0 < mid / 2
    lines = []
    for b in page.get_text('dict')['blocks']:
        for ln in b.get('lines', []):
            spans = [s for s in ln['spans'] if s['size'] > 10]
            if spans and (ln['bbox'][0] < mid) == left:
                lines.append(''.join(s['text'] for s in spans))
    return re.sub(r'\s+', ' ', ' '.join(lines)).strip()


def render(doc):
    for folder, size, q in SIZES:
        os.makedirs(os.path.join(WEB, folder), exist_ok=True)
    for i, page, clip in halves(doc):
        for folder, size, q in SIZES:
            z = size / clip.width
            pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=clip, alpha=False)
            img = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            if img.size != (size, size):
                img = img.resize((size, size), Image.LANCZOS)
            img.save(os.path.join(WEB, folder, name(i)), 'JPEG', quality=q, optimize=True, progressive=True)
        print('klaar', name(i))


def icons(doc):
    """Pictogrammen uit de voorkant (het huis met het bordje), deelafbeelding uit de hele omslag."""
    cover = Image.open(os.path.join(WEB, 'pages-hd', name(0)))
    W = cover.width
    x0, y0, side = int(W * 0.05), int(W * 0.15), int(W * 0.85)
    sq = cover.crop((x0, y0, x0 + side, y0 + side))
    for size, fn in ((180, 'apple-touch-icon.png'), (192, 'icon-192.png'), (512, 'icon-512.png'), (48, 'favicon.png')):
        sq.resize((size, size), Image.LANCZOS).save(os.path.join(WEB, fn), optimize=True)
    # 1200 x 630: de opengeslagen omslag (achter- en voorkant) op de achtergrondkleur
    p = doc[0]
    pix = p.get_pixmap(matrix=pymupdf.Matrix(1130 / p.rect.width, 1130 / p.rect.width), alpha=False)
    spread = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    og = Image.new('RGB', (1200, 630), BG)
    og.paste(spread, ((1200 - spread.width) // 2, (630 - spread.height) // 2))
    og.save(os.path.join(WEB, 'og.jpg'), 'JPEG', quality=86, optimize=True)


def main():
    doc = pymupdf.open(PDF)
    assert doc.page_count == N_PAGES // 2, doc.page_count
    pages_dir = os.path.join(WEB, 'pages')
    stale = not os.path.isdir(pages_dir) or len(os.listdir(pages_dir)) != N_PAGES or \
        os.path.getmtime(PDF) > min(os.path.getmtime(os.path.join(pages_dir, n)) for n in os.listdir(pages_dir))
    if '--render' in sys.argv or stale:
        render(doc)

    names = [name(i) for i in range(N_PAGES)]
    texts = [''] * N_PAGES
    for i, page, clip in halves(doc):
        texts[i] = page_text(page, clip)
    texts[0] = 'Voorkant: het huis De Stip, met het bordje De Stip boven de voordeur.'
    texts[-1] = 'Achterkant: een bankje onder een boom, naast het pad naar De Stip.'

    v = version(pages_dir)
    body = open(os.path.join(HERE, 'src', 'book.template.html'), encoding='utf8').read()

    def fill(pages, hd):
        return (body.replace('/*PAGES*/[]', json.dumps(pages))
                    .replace('/*HD*/[]', json.dumps(hd))
                    .replace('/*TEXTS*/[]', json.dumps(texts, ensure_ascii=False)))

    # --- website (Vercel) ---
    pages = [f'pages/{n}?v={v}' for n in names]
    hd = [f'pages-hd/{n}?v={v}' for n in names]
    content = fill(pages, hd)
    head = f'''<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<meta name="description" content="{DESC}">
<meta name="theme-color" content="#e9e6dd" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#171b1a" media="(prefers-color-scheme: dark)">
<meta property="og:type" content="book">
<meta property="og:title" content="{TITLE}">
<meta property="og:description" content="{DESC}">
<meta property="og:image" content="{SITE_URL}/og.jpg">
<meta property="og:url" content="{SITE_URL}/">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="favicon.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="manifest" href="manifest.webmanifest">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="{TITLE}">
<link rel="preload" as="image" href="{pages[0]}">
<style>html{{box-sizing:border-box;padding-top:env(safe-area-inset-top,0px)}}body{{margin:0;font:14px system-ui,sans-serif}}img{{max-width:100%}}[hidden]{{display:none!important}}</style>
'''
    # de <title> en het eigen <style>-blok uit de template komen direct na deze kop
    title_end = content.index('</title>') + len('</title>')
    title, rest = content[:title_end], content[title_end:]
    # het artifact-meta-label is buiten claude.ai niet nodig
    rest = rest.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', '')
    style_end = rest.index('</style>') + len('</style>')
    html = head + title + rest[:style_end] + '\n</head>\n<body>\n' + rest[style_end:].lstrip() + '\n</body>\n</html>\n'
    open(os.path.join(WEB, 'index.html'), 'w', encoding='utf8').write(html)

    manifest = {
        'name': TITLE, 'short_name': TITLE, 'start_url': './', 'scope': './', 'display': 'standalone',
        'orientation': 'any', 'background_color': '#e9e6dd', 'theme_color': '#326c70', 'lang': 'nl',
        'icons': [{'src': 'icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
                  {'src': 'icon-512.png', 'sizes': '512x512', 'type': 'image/png'}],
    }
    json.dump(manifest, open(os.path.join(WEB, 'manifest.webmanifest'), 'w', encoding='utf8'), indent=1, ensure_ascii=False)
    vercel = {
        'cleanUrls': True,
        'headers': [
            {'source': '/(.*)', 'headers': [{'key': 'X-Robots-Tag', 'value': 'noindex, nofollow'}]},
            {'source': '/pages/(.*)', 'headers': [{'key': 'Cache-Control', 'value': 'public, max-age=31536000, immutable'}]},
            {'source': '/pages-hd/(.*)', 'headers': [{'key': 'Cache-Control', 'value': 'public, max-age=31536000, immutable'}]},
        ],
    }
    json.dump(vercel, open(os.path.join(WEB, 'vercel.json'), 'w'), indent=1)
    open(os.path.join(WEB, 'robots.txt'), 'w').write('User-agent: *\nDisallow: /\n')
    icons(doc)

    # --- Claude-artifact (alleen inhoud; de viewer levert het HTML-skelet) ---
    art = os.path.join(HERE, 'artifact')
    os.makedirs(art, exist_ok=True)
    open(os.path.join(art, 'index.html'), 'w', encoding='utf8').write(fill([f'pages/{n}' for n in names], []))
    print('klaar: versie', v, '| index.html', len(html) // 1024, 'KB')


if __name__ == '__main__':
    main()
