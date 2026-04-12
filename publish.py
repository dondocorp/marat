#!/usr/bin/env python3
"""
publish.py — Convert in-progress.md to a Jekyll post in _posts/.

Usage:
    python3 publish.py --title "Andreia"
    python3 publish.py --title "Andreia" --image-url "https://..."
    python3 publish.py --title "Andreia" --image-url "https://..." --date 2026-04-12
"""

import re
import sys
import argparse
import urllib.request
import urllib.parse
from datetime import date
from pathlib import Path


ACCENT_MAP = [
    ('á','a'),('à','a'),('â','a'),('ä','a'),
    ('é','e'),('è','e'),('ê','e'),('ë','e'),
    ('í','i'),('ì','i'),('î','i'),('ï','i'),
    ('ó','o'),('ò','o'),('ô','o'),('ö','o'),
    ('ú','u'),('ù','u'),('û','u'),('ü','u'),
    ('ñ','n'),('ç','c'),
]


def slugify(text: str) -> str:
    text = text.lower()
    for accented, plain in ACCENT_MAP:
        text = text.replace(accented, plain)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def inline_md(text: str) -> str:
    """Convert *italics* to <em>text</em>."""
    return re.sub(r'\*([^*\n]+)\*', r'<em>\1</em>', text)


def md_to_html(source: str) -> str:
    """
    Convert markdown body to HTML.
      - Blank-line-separated blocks → <p>
      - --- → <hr>
      - *text* → <em>text</em>
    """
    raw_sections = re.split(r'\n---\n', source)
    section_htmls = []

    for section in raw_sections:
        section = section.strip()
        if not section:
            continue
        raw_paras = re.split(r'\n{2,}', section)
        para_htmls = []
        for para in raw_paras:
            para = para.strip()
            if not para:
                continue
            para = ' '.join(para.splitlines())
            para = inline_md(para)
            para_htmls.append(f'<p>{para}</p>')
        section_htmls.append('\n'.join(para_htmls))

    return '\n\n<hr>\n\n'.join(section_htmls)


def download_image(url: str, dest_dir: Path, slug: str) -> str:
    """
    Download the image at url, save to assets/images/<slug>.<ext>,
    and return the local path string for use in the frontmatter.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Derive extension from the URL path (fallback to .jpg)
    parsed = urllib.parse.urlparse(url)
    url_path = parsed.path
    ext = Path(url_path).suffix.lower() or '.jpg'
    if ext not in {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif'}:
        ext = '.jpg'

    filename = f'{slug}{ext}'
    dest = dest_dir / filename

    print(f'Descargando imagen → assets/images/{filename} …')
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        dest.write_bytes(response.read())
    print(f'Imagen guardada: assets/images/{filename}')

    return f'/assets/images/{filename}'


def build_post(title: str, post_date: str, cover: str, body_html: str) -> str:
    safe_title = title.replace('"', '\\"')
    return f"""---
layout: post
title: "{safe_title}"
date: {post_date}
cover: "{cover}"
---
{body_html}
"""


def main():
    parser = argparse.ArgumentParser(
        description='Publish in-progress.md as a Jekyll post.'
    )
    parser.add_argument('--title',     default='', help='Post title')
    parser.add_argument('--date',      default='', help='Post date YYYY-MM-DD (default: today)')
    parser.add_argument('--image-url', default='', help='URL of cover image to download locally')
    args = parser.parse_args()

    repo_root  = Path(__file__).parent
    source_path = repo_root / 'in-progress.md'

    if not source_path.exists():
        sys.exit(f'Error: {source_path} not found.')

    source = source_path.read_text(encoding='utf-8').strip()

    title = args.title.strip() or input('Título del texto: ').strip()
    if not title:
        sys.exit('Error: se requiere un título.')

    post_date = args.date.strip() or date.today().isoformat()
    slug      = slugify(title)
    filename  = f'{post_date}-{slug}.html'
    output_path = repo_root / '_posts' / filename

    if output_path.exists():
        answer = input(f'_posts/{filename} ya existe. ¿Sobreescribir? [s/N] ').strip().lower()
        if answer != 's':
            sys.exit('Cancelado.')

    # Handle cover image
    image_url = args.image_url.strip()
    if image_url:
        cover = download_image(image_url, repo_root / 'assets' / 'images', slug)
    else:
        cover = 'IMAGE_URL_PLACEHOLDER'
        print('Sin imagen. Reemplaza IMAGE_URL_PLACEHOLDER en el post, o vuelve a correr con --image-url.')

    body_html    = md_to_html(source)
    post_content = build_post(title, post_date, cover, body_html)

    output_path.write_text(post_content, encoding='utf-8')
    print(f'Publicado: _posts/{filename}')


if __name__ == '__main__':
    main()
