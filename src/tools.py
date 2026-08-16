from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil

from config import get_config
from logger import *

# File copy helpers
_latest_component_mtime = -1

# Copies a file if it's newer than what's in the dest directory
def copy_if_newer(src: str, dest: str) -> str:
    config = get_config()
    manifest = config.manifest

    # Get mtime from manifest
    src_mtime = Path(src).stat().st_mtime
    manifest_mtime = manifest.get(dest)

    # Check if dest file already exists and is in the manifest
    if os.path.exists(dest) and manifest_mtime > 0:
        # Get existing file mtime
        dest_mtime = Path(dest).stat().st_mtime

        # Check if this is an HTML file and the ssg-components directory has new content
        is_html_with_old_comps = dest.endswith(config.build_file_exts) and _latest_component_mtime > dest_mtime

        # Compare mod timestamps
        if manifest_mtime >= src_mtime and not is_html_with_old_comps:
            return dest

    # Base case, copy as usual
    manifest.put(os.path.abspath(dest), src_mtime)
    vlog(f"Copied {src} --> {dest}")
    return shutil.copy2(src, dest)

# Used to copy the new source
def copy_source() -> tuple[str]:
    config = get_config()
    manifest = config.manifest

    # Copy helper
    def copy(src: str, dest: str) -> str:
        manifest.put(os.path.abspath(dest), Path(src).stat().st_mtime)
        return shutil.copy2(src, dest)

    # Verify output directory exists
    if os.path.exists(config.output_dir):
        # If build path changed (or force rebuild flag), purge all & rebuild
        if isarg("f") or os.path.abspath(config.output_dir) != os.path.abspath(manifest.get_build_path()):
            # Purge all, create new manifest
            shutil.rmtree(config.output_dir)
            manifest.clear()
            manifest.set_build_path(config.output_dir)

            # Copy new
            shutil.copytree(config.input_dir, config.output_dir, copy_function=copy)
            log("Cleaned existing build content.")
        else: # Build path matches manifest & not a force rebuild
            # Determine mtime of newest ssg component
            global _latest_component_mtime
            _latest_component_mtime = max( p.stat().st_mtime for p in Path(config.components_dir).rglob("*") )

            # Copy only updated
            shutil.copytree(config.input_dir, config.output_dir, copy_function=copy_if_newer, dirs_exist_ok=True)

            if len(manifest.files_updated) > 0:
                log("Updated modified build content.")
            else:
                log("Already up-to-date (-f to force rebuild).")
                exit(0)
    else: # Output directory doesn't exist, create new manifest
        # Fresh copy
        manifest.clear()
        manifest.set_build_path(config.output_dir)
        shutil.copytree(config.input_dir, config.output_dir, copy_function=copy)

    # Return updated files
    return tuple(manifest.files_updated)

# Creates public/sitemap.xml with update timestamps for all HTML files
def build_sitemap(files: tuple[str]) -> None:
    config = get_config()

    # Overwrite any existing sitemap
    sitemap_path = os.path.join( config.output_dir, "sitemap.xml" )

    # Add stub to manifest
    config.manifest.put(os.path.abspath(sitemap_path), -1)

    with open(sitemap_path, "w") as f:
        # Append header
        f.write(
            """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9 http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">\n"""
        )

        # Get mod time of all files
        for file in files:
            # Determine "pretty" path
            pretty_path = "/" + file.removeprefix(config.output_dir) \
                .removeprefix("/")

            # Check if file is allowed in sitemap
            if pretty_path in config.sitemap_ignore: continue

            # Remove index.html if needed
            if config.truncate_sitemap_index_files:
                for suffix in config.index_files:
                    if pretty_path.endswith(suffix):
                        pretty_path = pretty_path.removesuffix(suffix)
                        break

            # Calculate index priority
            priority = max(0.2, 1.2 - 0.2 * pretty_path.count("/"))

            # Determine timestamp
            mtime = os.path.getmtime(file)
            dt = datetime.fromtimestamp(mtime, tz=timezone.utc).replace(microsecond=0)
            timestamp = dt.isoformat()

            # Write
            f.write(f"""    <url>
        <loc>{config.base_address}{pretty_path.removeprefix("/")}</loc>
        <lastmod>{timestamp}</lastmod>
        <priority>{priority:.2f}</priority>
    </url>\n""")

        # Close sitemap
        f.write("</urlset>\n")

# Simple HTML minifier
def minify_html(text: str) -> str:
    # Remove comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Strip whitespace
    text = re.sub(r">\s+<", "><", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# Simple CSS minifier
def minify_css(text: str) -> str:
    # Remove comments
    text = re.sub(r"\/\*.*?\*\/", "", text, flags=re.DOTALL)

    # Strip whitespace
    # Remove unnecessary whitespace around symbols
    text = re.sub(r"\s*{\s*", "{", text)
    text = re.sub(r"\s*}\s*", "}", text)
    text = re.sub(r"\s*;\s*", ";", text)
    text = re.sub(r"\s*:\s*", ":", text)
    text = re.sub(r"\s*,\s*", ",", text)

    # Remove final semicolon before }
    text = re.sub(r";}", "}", text)

    # Collapse remaining whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()

def minify_js(text: str) -> str:
    # Pattern to match comments and strings
    pattern = re.compile(
        r'/\*.*?\*/|'            # Block comments
        r'//[^\n]*|'             # Line comments
        r'"(?:\\.|[^"\\])*"|'    # Double-quote strings
        r"'(?:\\.|[^'\\])*'|"    # Single-quote strings
        r"`(?:\\.|[^`\\])*`",    # Template literals (backticks)
        re.DOTALL
    )

    strings = []

    # Strip comments and temporarily replace strings with placeholders
    def replacer(match):
        val = match.group(0)
        if val.startswith('/*') or val.startswith('//'):
            return '' # Delete comments

        # Otherwise, it's a string (save & leave placeholder)
        strings.append(val)
        return f"__MINIFY_STR_{len(strings)-1}__"

    text = pattern.sub(replacer, text)
    
    # Remove whitespace around symbols
    text = re.sub(r"\s*([{}();,:=+*/<>!&|?\[\]~%^\-])\s*", r"\1", text)

    # Remove remaining consecutive whitespace
    text = re.sub(r"\s+", " ", text)

    # Re-inject original strings back into placeholders
    for i, s in enumerate(strings):
        # Use .replace() instead of regex so escape chars inside
        #   JS strings don't confuse the regex engine
        text = text.replace(f"__MINIFY_STR_{i}__", s)

    return text.strip()

# Minifies HTML, CSS, and JS files in-place
def minify() -> None:
    config = get_config()

    # Get files
    files = tuple( [p for p in Path(config.output_dir).rglob("*")] )
    html_files = tuple( [p for p in files if p.suffix in (".html", ".htm")] )
    css_files = tuple( [p for p in files if p.suffix == ".css"] )
    js_files = tuple( [p for p in files if p.suffix == ".js"] )

    # HTML files
    for file in html_files:
        # Read & minify
        text = file.read_text()
        text = minify_html(text)

        # Write (truncated)
        with open(file, "w") as f:
            f.write(text)

    # CSS files
    for file in css_files:
        # Read & minify
        text = file.read_text()
        text = minify_css(text)

        # Write (truncated)
        with open(file, "w") as f:
            f.write(text)

    # JS files
    for file in js_files:
        # Read & minify
        text = file.read_text()
        text = minify_js(text)

        # Write (truncated)
        with open(file, "w") as f:
            f.write(text)
    
    log("Minified all HTML, CSS, and JS files")
