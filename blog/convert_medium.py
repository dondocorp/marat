#!/usr/bin/env python3
"""
Convert Medium export HTML files to Jekyll-compatible HTML posts.

Usage:
    1. Go to medium.com → Settings → Security and apps → Export your data
    2. Download and unzip the archive
    3. Run: python3 convert_medium.py /path/to/medium-export/posts/ [output_dir]

To download images for existing posts in _posts/:
    python3 convert_medium.py --update-images [posts_dir]

Each HTML file in the export will become a .html file in _posts/
Images are downloaded locally to assets/images/<post-slug>/
"""

import os
import sys
import re
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing beautifulsoup4...")
    os.system("pip3 install beautifulsoup4")
    from bs4 import BeautifulSoup

try:
    import requests
except ImportError:
    print("Installing requests...")
    os.system("pip3 install requests")
    import requests


def slugify(text):
    text = text.lower()
    text = re.sub(r'[áàäâ]', 'a', text)
    text = re.sub(r'[éèëê]', 'e', text)
    text = re.sub(r'[íìïî]', 'i', text)
    text = re.sub(r'[óòöô]', 'o', text)
    text = re.sub(r'[úùüû]', 'u', text)
    text = re.sub(r'[ñ]', 'n', text)
    text = re.sub(r'[ç]', 'c', text)
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text.strip())
    text = re.sub(r'-+', '-', text)
    return text[:80]


def extract_date(soup, filename):
    time_tag = soup.find('time')
    if time_tag and time_tag.get('datetime'):
        try:
            dt = datetime.fromisoformat(time_tag['datetime'][:10])
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass

    for meta in soup.find_all('meta'):
        prop = meta.get('property', '') or meta.get('name', '')
        if 'published' in prop or 'date' in prop:
            content = meta.get('content', '')
            if content:
                try:
                    dt = datetime.fromisoformat(content[:10])
                    return dt.strftime('%Y-%m-%d')
                except Exception:
                    pass

    mtime = Path(filename).stat().st_mtime
    return datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')


def download_image(url, images_dir):
    """Download an image to images_dir. Returns local filename or None on failure."""
    try:
        parsed = urlparse(url)
        url_filename = Path(parsed.path).name
        if not url_filename or '.' not in url_filename:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            url_filename = f"image_{url_hash}.jpg"

        dest_path = images_dir / url_filename
        if dest_path.exists():
            return url_filename

        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; blog-importer/1.0)'
        })
        response.raise_for_status()
        images_dir.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(response.content)
        return url_filename
    except Exception as e:
        print(f"    Warning: failed to download {url}: {e}")
        return None


def update_image_srcs(html_content, post_slug, assets_base):
    """Download remote images and update src attributes to local paths."""
    soup = BeautifulSoup(html_content, 'html.parser')
    images_dir = Path(assets_base) / post_slug
    changed = False

    for img in soup.find_all('img'):
        src = img.get('src', '')
        if not src or not src.startswith('http'):
            continue
        local_name = download_image(src, images_dir)
        if local_name:
            img['src'] = f"/assets/images/{post_slug}/{local_name}"
            changed = True

    return str(soup) if changed else html_content


def convert_file(html_path, output_dir, assets_base):
    """Copy a Medium export HTML file to output_dir as a Jekyll post, downloading images."""
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')

    # Extract title (for naming only)
    title = ''
    h1 = soup.find('h1')
    if h1:
        title = h1.get_text(strip=True)
    if not title:
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True).split('–')[0].strip()
    if not title:
        title = Path(html_path).stem

    # Extract date (for naming only)
    date_str = extract_date(soup, html_path)

    slug = slugify(title)
    post_slug = f'{date_str}-{slug}'
    out_filename = f'{post_slug}.html'
    out_path = Path(output_dir) / out_filename

    # Download images and update src in original HTML
    updated_html = update_image_srcs(html, post_slug, assets_base)

    # Add Jekyll front matter
    safe_title = title.replace('"', '\\"')
    front_matter = f'---\nlayout: post\ntitle: "{safe_title}"\ndate: {date_str}\n---\n\n'

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(front_matter + updated_html + '\n')

    return out_filename


def update_existing_post(html_path, assets_base):
    """Download images for an already-converted post and update its src attributes."""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Separate front matter from HTML body
    if content.startswith('---'):
        end = content.index('---', 3)
        front_matter = content[:end + 3]
        html_body = content[end + 3:]
    else:
        front_matter = ''
        html_body = content

    post_slug = Path(html_path).stem  # e.g. 2013-05-21-sentados-en-el-lago
    updated_body = update_image_srcs(html_body, post_slug, assets_base)

    if updated_body != html_body:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(front_matter + updated_body + '\n')
        return True
    return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == '--update-images':
        posts_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('_posts')
        assets_base = Path(sys.argv[3]) if len(sys.argv) > 3 else Path('assets/images')
        html_files = list(posts_dir.glob('*.html'))
        if not html_files:
            print(f"No HTML files found in {posts_dir}")
            sys.exit(1)
        print(f"Updating images for {len(html_files)} post(s)...\n")
        for html_file in sorted(html_files):
            try:
                changed = update_existing_post(html_file, assets_base)
                status = '✓' if changed else '–'
                print(f"  {status}  {html_file.name}")
            except Exception as e:
                print(f"  ✗  {html_file.name}  —  {e}")
        print("\nDone.")
        return

    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('_posts')
    assets_base = Path(sys.argv[3]) if len(sys.argv) > 3 else Path('assets/images')
    output_dir.mkdir(exist_ok=True)
    assets_base.mkdir(parents=True, exist_ok=True)

    if input_path.is_file():
        files = [input_path]
    else:
        files = list(input_path.glob('*.html'))

    if not files:
        print(f"No HTML files found in {input_path}")
        sys.exit(1)

    print(f"Converting {len(files)} file(s) → {output_dir}/\n")

    for html_file in sorted(files):
        try:
            out = convert_file(html_file, output_dir, assets_base)
            print(f"  ✓  {html_file.name}  →  {out}")
        except Exception as e:
            print(f"  ✗  {html_file.name}  —  {e}")

    print(f"\nDone. {len(files)} article(s) written to {output_dir}/")


if __name__ == '__main__':
    main()
