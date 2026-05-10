# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

*Ácrata y Banquero* — a personal literary blog at `dondo.com.co`. Jekyll 4.3 site hosted on GitHub Pages. Posts are in Spanish (a few in English). No tests, no build pipeline beyond Jekyll.

## Commands

```bash
# Serve locally with live reload
bundle exec jekyll serve --livereload

# Build static site to _site/
bundle exec jekyll build

# Publish a new post from in-progress.md
python3 publish.py --title "Título" --image-url "https://..."
python3 publish.py --title "Título"          # without cover image

# Import from Medium export
python3 convert_medium.py /path/to/medium-export/posts/

# Download missing images for existing posts
python3 convert_medium.py --update-images
```

## Publishing workflow

1. Write the text in `in-progress.md` (plain Markdown).
2. Run `python3 publish.py --title "..."` — it converts the Markdown to HTML paragraphs, downloads the cover image locally to `assets/images/`, writes a dated file to `_posts/`, and clears `in-progress.md`.
3. Commit and push; GitHub Pages builds automatically.

Post filenames follow the pattern `YYYY-MM-DD-slug.html`. The slug is auto-generated from the title (accents stripped, spaces → hyphens).

## Post format

Posts are `.html` files with Jekyll front matter:

```yaml
---
layout: post
title: "Title"
date: YYYY-MM-DD
cover: "/assets/images/slug.jpg"   # optional
cover_credit: "Caption text"       # optional
---
```

Body is raw HTML: `<p>` paragraphs, `<hr>` for section breaks, `<em>` for italics. The `publish.py` script handles the Markdown→HTML conversion (`*text*` → `<em>text</em>`, blank lines → `<p>`, `---` → `<hr>`).

## Markdown conventions in `in-progress.md`

- `*text*` → `<em>text</em>` (italics — used for book titles and dialogue emphasis)
- Blank line → paragraph break
- `---` on its own line → `<hr>` section separator

## Defining the cover image in `in-progress.md`

Add a `cover:` directive anywhere in the file (typically the first line) with the remote image URL:

```
cover: https://example.com/imagen.jpg

El texto empieza aquí...
```

`publish.py` extracts the directive, downloads the image to `assets/images/<slug>.<ext>`, and removes the line from the body before converting to HTML. The `--image-url` CLI flag takes precedence if both are present.

If no image is provided, the post is created with `IMAGE_URL_PLACEHOLDER` in the front matter.

## Writing texts

When asked to write or draft a text for this blog, use exclusively vocabulary already present in `vocabulario.txt`. Do not introduce words that don't appear in that file. The register is literary Spanish: personal, essayistic, sometimes narrative — consistent with the existing posts.

## Vocabulary check on publish

After running `publish.py` (or when editing a post in `_posts/`), compare the words in the new post against `vocabulario.txt`. Report any words not present in the file — these are candidates the author added manually and may warrant updating `vocabulario.txt`.

To regenerate `vocabulario.txt` after new posts are added:

```bash
python3 - <<'EOF'
import os, re
from collections import Counter

stopwords = {
    'el','la','los','las','un','una','unos','unas','de','del','en','con','por',
    'para','sin','sobre','entre','hasta','desde','hacia','ante','bajo','contra',
    'durante','mediante','según','tras','al','a','que','y','o','pero','si','ni',
    'aunque','porque','como','cuando','donde','mientras','después','antes','sino',
    'pues','ya','más','menos','me','se','le','lo','nos','os','les','yo','tú',
    'él','ella','nosotros','ellos','ellas','mi','tu','su','mis','tus','sus',
    'este','esta','estos','estas','ese','esa','esos','esas','esto','eso',
    'es','son','era','eran','fue','fueron','ser','estar','ha','han','he','hemos',
    'había','habrán','haber','hay','hubo','tiene','tienen','tenía','tuvo','tener',
    'hace','hacen','hizo','hacer','puede','pueden','pudo','poder','va','van',
    'iba','ir','quiere','quería','quiso','querer','sabe','sabía','supo','saber',
    'dice','decía','dijo','decir','viene','venía','vino','venir','da','dan',
    'daba','dio','dar','no','sí','muy','bien','también','siempre','nunca',
    'aquí','allí','ahora','antes','hoy','así','tan','todo','todos','toda',
    'todas','mismo','misma','solo','sólo','aún','cada','otro','otra','mucho',
    'mucha','nada','algo','alguien','nadie','the','and','of','to','in','is',
    'it','that','this','was','for','on','are','with','as','at','be','by',
    'from','or','an','but','not','what','all','were','when','we','there',
}

all_words = []
for fn in os.listdir('_posts'):
    if fn.endswith('.html'):
        text = re.sub(r'<[^>]+>', ' ', open(f'_posts/{fn}').read())
        text = re.sub(r'^---.*?---', '', text, flags=re.DOTALL)
        words = re.findall(r"[a-záéíóúüñàèìòùA-ZÁÉÍÓÚÜÑ]{3,}", text, re.UNICODE)
        all_words.extend([w.lower() for w in words])

freq = Counter(all_words)
filtered = {w: c for w, c in freq.items() if w not in stopwords}
with open('vocabulario.txt', 'w') as f:
    f.write(f"# Vocabulario — {len(filtered)} palabras únicas\n\n")
    f.write(f"{'PALABRA':<30} {'FRECUENCIA':>10}\n")
    f.write("-" * 42 + "\n")
    for w in sorted(filtered):
        f.write(f"{w:<30} {filtered[w]:>10}\n")
print(f"vocabulario.txt actualizado — {len(filtered)} palabras")
EOF
```

## Site structure

- `_layouts/default.html` — base HTML shell (Cormorant Garamond + DM Mono fonts, GoatCounter analytics)
- `_layouts/post.html` — wraps content with title, date, cover image, and prev/next navigation
- `assets/css/style.css` — all styles
- `assets/images/` — cover images, organized by post slug for Medium imports, flat for `publish.py` posts
- `_config.yml` — site title, URL, permalink format (`/:year/:month/:day/:title/`)
