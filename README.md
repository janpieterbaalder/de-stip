# De Stip — bladerboek

Online bladerboek van het prentenboek *De Stip* (dicht 21 × 21 cm, open 42 × 21 cm), gemaakt uit
`bron/De Stip.pdf`. Een gewoon gebonden boek met harde kaft: rugschaduw in het midden, de kaft
buigt niet bij het omslaan.

- **`web/`** is de website zoals Vercel hem publiceert (statisch, geen build-stap).
  - `pages/` — pagina's voor het bladerboek (1600 × 1600): `p00` voorkant, `p01`–`p18`, `p19` achterkant
  - `pages-hd/` — scherpere versies voor inzoomen en de leesweergave (2400 × 2400)
- **`src/book.template.html`** — de pagina zelf (bladeranimatie, rug, inhoud, leesweergave).
- **`build.py`** — snijdt de PDF-bladen in pagina's en maakt `web/index.html`, pictogrammen,
  `vercel.json` en de artifactversie (`artifact/`) uit de template.
- **`bron/De Stip.pdf`** — de bron-PDF waaruit alles wordt gemaakt.

## Bijwerken

```bash
python build.py            # pagina's opnieuw als de PDF nieuwer is, daarna de website
python build.py --render   # pagina's altijd opnieuw maken
```

De site staat op `noindex`: bereikbaar via de link, maar niet vindbaar via zoekmachines.
