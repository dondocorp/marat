#!/usr/bin/env python3
"""
migrate_images.py — Download all external images in _posts/ to assets/images/
and rewrite the src attributes to local paths.

Idempotente: si una imagen ya existe localmente la saltea y actualiza la
referencia en el post de todas formas. Se puede correr tantas veces como
haga falta hasta que todas las imágenes estén descargadas.

Usage:
    python3 migrate_images.py               # dry run
    python3 migrate_images.py --apply       # descargar + reescribir
    python3 migrate_images.py --apply --post 2026-03-15-andreia.html
"""

import re
import sys
import time
import hashlib
import argparse
import urllib.error
import urllib.request
import urllib.parse
from pathlib import Path


IMAGE_HOSTS = (
    'cdn-images-1.medium.com',
    'miro.medium.com',
    'images.medium.com',
)

CONTENT_TYPE_EXT = {
    'image/jpeg':    '.jpg',
    'image/jpg':     '.jpg',
    'image/png':     '.png',
    'image/webp':    '.webp',
    'image/gif':     '.gif',
    'image/avif':    '.avif',
    'image/svg+xml': '.svg',
}
FALLBACK_EXT = '.jpg'

MAX_RETRIES   = 5
RETRY_BASE_S  = 2      # first wait: 2 s, then 4, 8, 16, 32
POLITE_WAIT_S = 0.3    # pause between successful downloads


def is_external_image(url: str) -> bool:
    try:
        host = urllib.parse.urlparse(url).netloc
        return any(h in host for h in IMAGE_HOSTS)
    except Exception:
        return False


def is_broken_url(url: str) -> bool:
    """Detect Medium URLs with NaN dimensions — these are permanently gone."""
    return '/NaN/NaN/' in url or '/t/NaN/' in url


def url_to_base_name(url: str) -> str:
    """Return a stable, filesystem-safe base name (no extension) for a URL."""
    path_part = urllib.parse.urlparse(url).path.rstrip('/')
    raw = Path(path_part).name
    safe = re.sub(r'[^a-zA-Z0-9._-]', '-', raw)
    safe = re.sub(r'-+', '-', safe).strip('-')
    url_hash = hashlib.md5(url.encode()).hexdigest()[:6]
    return f'{url_hash}-{safe}'


def find_existing(images_dir: Path, base_name: str) -> Path | None:
    """Return the existing local file for base_name (any extension), or None."""
    matches = list(images_dir.glob(f'{base_name}.*'))
    return matches[0] if matches else None


def download_with_retry(url: str, images_dir: Path, base_name: str) -> Path | None:
    """
    Download url to images_dir/<base_name>.<ext>.
    Retries on 429 (Too Many Requests) and transient errors with
    exponential backoff. Returns the local Path on success, None on failure.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                url, headers={'User-Agent': 'Mozilla/5.0 (compatible)'}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                ct  = resp.headers.get('Content-Type', '').split(';')[0].strip()
                ext = CONTENT_TYPE_EXT.get(ct, FALLBACK_EXT)
                dest = images_dir / f'{base_name}{ext}'
                images_dir.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(resp.read())
            print(f'  ✓ {dest.name}')
            return dest

        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Definitively gone — no point retrying
                print(f'  ✗ 404 (imagen eliminada): {url}', file=sys.stderr)
                return None
            elif e.code == 429:
                retry_after = int(e.headers.get('Retry-After', RETRY_BASE_S * (2 ** (attempt - 1))))
                print(f'  429 — espera {retry_after}s (intento {attempt}/{MAX_RETRIES})')
                time.sleep(retry_after)
            elif e.code in (503, 502, 504) and attempt < MAX_RETRIES:
                wait = RETRY_BASE_S * (2 ** (attempt - 1))
                print(f'  {e.code} — reintentando en {wait}s')
                time.sleep(wait)
            else:
                print(f'  ✗ HTTP {e.code}: {url}', file=sys.stderr)
                return None

        except Exception as e:
            if attempt < MAX_RETRIES:
                wait = RETRY_BASE_S * (2 ** (attempt - 1))
                print(f'  error ({e}) — reintentando en {wait}s')
                time.sleep(wait)
            else:
                print(f'  ✗ {e}: {url}', file=sys.stderr)
                return None

    print(f'  ✗ agotados {MAX_RETRIES} intentos: {url}', file=sys.stderr)
    return None


def resolve_local(url: str, images_dir: Path, dry_run: bool) -> str | None:
    """
    Return the local /assets/images/... path for url.
    - If the file already exists locally: return path, no download.
    - If not and dry_run: return placeholder string.
    - If not and not dry_run: download, return path or None on failure.
    """
    base_name = url_to_base_name(url)
    existing  = find_existing(images_dir, base_name)

    if existing:
        print(f'  skip (ya existe) {existing.name}')
        return f'/assets/images/{existing.name}'

    if dry_run:
        print(f'  [dry] descargaría → {base_name}{FALLBACK_EXT}')
        return f'/assets/images/{base_name}{FALLBACK_EXT}'

    dest = download_with_retry(url, images_dir, base_name)
    if dest:
        time.sleep(POLITE_WAIT_S)
        return f'/assets/images/{dest.name}'
    return None


def process_post(post_path: Path, images_dir: Path, dry_run: bool) -> int:
    content = post_path.read_text(encoding='utf-8')

    # Collect external image URLs from src="..." and cover: frontmatter
    src_urls = [m.group(1) for m in re.finditer(r'src="(https?://[^"]+)"', content)
                if is_external_image(m.group(1))]

    cover_match = re.search(r'^cover:\s*"?(https?://[^"\s]+)"?', content, re.MULTILINE)
    if cover_match and is_external_image(cover_match.group(1)):
        src_urls.append(cover_match.group(1))

    unique_urls = list(dict.fromkeys(src_urls))
    if not unique_urls:
        return 0

    print(f'\n{post_path.name}  ({len(unique_urls)} imagen{"es" if len(unique_urls) != 1 else ""})')

    url_to_local: dict[str, str] = {}
    failed: list[str] = []
    for url in unique_urls:
        if is_broken_url(url):
            print(f'  ✗ URL rota (NaN): {url}', file=sys.stderr)
            failed.append(url)
            continue
        local = resolve_local(url, images_dir, dry_run)
        if local:
            url_to_local[url] = local
        else:
            failed.append(url)

    # Append failed URLs to a log for manual review
    if failed and not dry_run:
        log_path = post_path.parent.parent / 'missing_images.log'
        with log_path.open('a', encoding='utf-8') as f:
            for url in failed:
                f.write(f'{post_path.name}\t{url}\n')

    if not url_to_local:
        return 0

    # Rewrite post file
    new_content = content
    for url, local in url_to_local.items():
        new_content = new_content.replace(f'src="{url}"', f'src="{local}"')
        new_content = re.sub(
            r'(cover:\s*)"?' + re.escape(url) + r'"?',
            rf'\g<1>"{local}"',
            new_content
        )

    if not dry_run and new_content != content:
        post_path.write_text(new_content, encoding='utf-8')
        print(f'  → {post_path.name} reescrito')

    return len(url_to_local)


def main():
    parser = argparse.ArgumentParser(
        description='Migrate external images to assets/images/ (idempotente).'
    )
    parser.add_argument('--apply', action='store_true',
                        help='Ejecutar de verdad. Sin este flag es dry run.')
    parser.add_argument('--post',  default='',
                        help='Procesar solo este archivo (ej. 2026-03-15-andreia.html).')
    args = parser.parse_args()

    dry_run   = not args.apply
    repo_root = Path(__file__).parent
    posts_dir = repo_root / '_posts'
    images_dir = repo_root / 'assets' / 'images'

    if dry_run:
        print('── DRY RUN ── (pasa --apply para ejecutar)\n')

    if args.post:
        post_files = [posts_dir / args.post]
        if not post_files[0].exists():
            sys.exit(f'Error: {post_files[0]} no encontrado.')
    else:
        post_files = sorted(posts_dir.glob('*.html'))

    total_posts  = 0
    total_images = 0

    for post_path in post_files:
        n = process_post(post_path, images_dir, dry_run)
        if n:
            total_posts  += 1
            total_images += n

    print(f'\n── {"Simulación" if dry_run else "Migración"} completada: '
          f'{total_images} imágenes en {total_posts} posts ──')
    if dry_run:
        print('Corre con --apply para ejecutar.')


if __name__ == '__main__':
    main()
