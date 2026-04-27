from datetime import datetime, timezone
import os
import pathlib
import re
import shutil

from config import config
from logger import *

# File copy helpers
_latest_ssg_comp_mtime = -1
_files_copied = []

# Copies a file & records its path
def copy(src: str, dest: str) -> str:
    _files_copied.append(dest)
    return shutil.copy2(src, dest)

# Copies a file if it's newer than what's in the dest directory
def copy_if_newer(src: str, dest: str) -> str:
    if os.path.exists(dest):
        src_mtime = os.path.getmtime(src)
        dest_mtime = os.path.getmtime(dest)

        # Check if this is an HTML file and the ssg-components directory has new content
        is_html_with_old_comps = dest.endswith(".html") and _latest_ssg_comp_mtime > dest_mtime

        # Compare mod timestamps
        if dest_mtime >= src_mtime and not is_html_with_old_comps:
            return dest
        else:
            vlog(f"Copied {src} --> {dest}")

    # Base case, copy as usual
    _files_copied.append(dest)
    return shutil.copy2(src, dest)

# Used by shutil.copytree to ignore the root ssg-components directory
def ignore_root_ssg_components(dir: str, _) -> None:
    if os.path.abspath(dir) == os.path.abspath(config.input_dir):
        return {"ssg-components"}
    return set()

# Used to copy the new source
def copy_source() -> tuple[str]:
    if os.path.exists(config.output_dir):
        # Handle copies
        if isarg("f"):
            # Purge all
            shutil.rmtree(config.output_dir)

            # Copy new
            shutil.copytree(config.input_dir, config.output_dir, ignore=ignore_root_ssg_components, copy_function=copy)
            log("Cleaned existing build content.")
        else:
            # Determine mtime of newest ssg component
            global _latest_ssg_comp_mtime
            _latest_ssg_comp_mtime = max(
                os.path.getmtime(str(p.resolve())) for p in pathlib.Path(config.components_dir).rglob("*")
            )

            # Copy only updated
            shutil.copytree(config.input_dir, config.output_dir, ignore=ignore_root_ssg_components, copy_function=copy_if_newer, dirs_exist_ok=True)

            if len(_files_copied) > 0:
                log("Updated modified build content.")
            else:
                log("Already up-to-date (-f to force rebuild).")
                exit(0)
    else:
        # Initial copy
        shutil.copytree(config.input_dir, config.output_dir, ignore=ignore_root_ssg_components, copy_function=copy)
    
    # Return updated files
    return tuple(_files_copied)

# Creates public/sitemap.xml with update timestamps for all HTML files
def build_sitemap(files: tuple[str]) -> None:
    # Overwrite any existing sitemap
    sitemap_path = os.path.join( config.output_dir, "sitemap.xml" )

    with open(sitemap_path, "w") as f:
        # Append header
        f.write(
            """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9 http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd">\n"""
        )

        # Get mod time of all files
        for file in files:
            # Determine "pretty" path
            pretty_path = "/" + file.removeprefix(config.output_dir) \
                .removeprefix("/") \
                .removesuffix("index.html")

            if pretty_path in config.sitemap_ignore: continue

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

# Simple JS minifier
def minify_js(text: str) -> str:
    # Remove comments
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)

    # Remove whitespace around symbols
    text = re.sub(r"\s*([{};,:=+\-*/()<>])\s*", r"\1", text)

    # Remove remaining whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()

# Minifies HTML, CSS, and JS files in-place
def minify() -> None:
    # Get files
    html_files = tuple( [p for p in pathlib.Path(config.output_dir).rglob("*.html")] )
    css_files = tuple( [p for p in pathlib.Path(config.output_dir).rglob("*.css")] )
    js_files = tuple( [p for p in pathlib.Path(config.output_dir).rglob("*.js")] )

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
