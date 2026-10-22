from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import xml.sax.saxutils

from config import get_config
from logger import *

DATETIME_PATTERN = re.compile(r'<\$\s*Datetime\s*:\s*["\']([^"\']+)["\']\s*\/\s*>')
TEXTFILE_PATTERN = re.compile(r'<\$\s*TextFile\s*:\s*["\']([^"\']+)["\']\s*\/\s*>')
COMPONENT_REF_PATTERN = re.compile(r'<\$\s*([^:\"\'\s/>]+)\s*\/\s*>')

def resolve_text_file_path(text_files_dir: str, path: str) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path(text_files_dir) / p
    return p.resolve()

def get_component_name(p: Path, components_dir: str | Path) -> str:
    rel = p.relative_to(components_dir)
    parts = list(rel.parts)
    if parts:
        last = parts[-1]
        for ext in (".html", ".htm"):
            if last.lower().endswith(ext):
                last = last[:-len(ext)]
                break
        parts[-1] = last
    return ".".join(parts)

# File copy helpers
_latest_component_mtime = -1
_components_changed = False
_datetime_components: set[str] = set()
_comp_textfiles: dict[str, set[str]] = {}
_manifest_textfile_snapshot: dict[str, float] = {}
_all_dependent_textfiles: set[str] = set()
_backup_established = False
_initial_output_existed = False

def init_backup_state() -> None:
    global _backup_established, _initial_output_existed
    _backup_established = False
    try:
        config = get_config()
        _initial_output_existed = os.path.exists(config.output_dir)
    except Exception:
        _initial_output_existed = False

# Copies a file if it's newer than what's in the dest directory
def copy_if_newer(src: str, dest: str) -> str:
    config = get_config()
    manifest = config.manifest

    # Get mtime from manifest
    src_mtime = Path(src).stat().st_mtime
    manifest_mtime = manifest.get(os.path.abspath(dest))

    is_build_file = dest.endswith(config.build_file_exts)

    # Check if dest file already exists and is in the manifest
    if os.path.exists(dest) and manifest_mtime > 0:
        # Get existing file mtime
        dest_mtime = Path(dest).stat().st_mtime

        # Check if this is an HTML file and components have changed (or component directory is newer)
        is_html_with_old_comps = is_build_file and (_components_changed or _latest_component_mtime > dest_mtime)

        # Check for Datetime and TextFile dependencies for build files
        is_datetime_page = False
        is_textfile_outdated = False

        if is_build_file:
            try:
                src_content = Path(src).read_text()
                # Check for Datetime directly in page or via components
                if DATETIME_PATTERN.search(src_content):
                    is_datetime_page = True
                else:
                    refs = set(COMPONENT_REF_PATTERN.findall(src_content))
                    if refs & _datetime_components:
                        is_datetime_page = True

                # Check for TextFiles directly in page or via components
                dependent_textfiles = set(TEXTFILE_PATTERN.findall(src_content))
                refs = set(COMPONENT_REF_PATTERN.findall(src_content))
                for ref in refs:
                    if ref in _comp_textfiles:
                        dependent_textfiles.update(_comp_textfiles[ref])

                for tf_rel in dependent_textfiles:
                    _all_dependent_textfiles.add(tf_rel)
                    tf_path = resolve_text_file_path(config.text_files_dir, tf_rel)
                    if not tf_path.exists():
                        is_textfile_outdated = True
                        break
                    tf_mtime = tf_path.stat().st_mtime
                    # Use snapshot of manifest textfile timestamps so other pages don't see mutated state (H1)
                    saved_tf_mtime = _manifest_textfile_snapshot.get(str(tf_path), -1)
                    if tf_mtime > dest_mtime or saved_tf_mtime != tf_mtime:
                        is_textfile_outdated = True
                        break
            except Exception:
                pass

        # Compare mod timestamps and dependency freshness (N3: manifest_mtime == src_mtime)
        if manifest_mtime == src_mtime and not is_html_with_old_comps and not is_datetime_page and not is_textfile_outdated:
            return dest

    # Base case, copy as usual
    manifest.put(os.path.abspath(dest), src_mtime)
    if is_build_file:
        try:
            src_content = Path(src).read_text()
            tfs = set(TEXTFILE_PATTERN.findall(src_content))
            refs = set(COMPONENT_REF_PATTERN.findall(src_content))
            for ref in refs:
                if ref in _comp_textfiles:
                    tfs.update(_comp_textfiles[ref])
            _all_dependent_textfiles.update(tfs)
        except Exception:
            pass
    vlog(f"Copied {src} --> {dest}")
    return shutil.copy2(src, dest)

# Used to copy the new source
def copy_source() -> tuple[str] | None:
    global _backup_established, _initial_output_existed
    config = get_config()
    manifest = config.manifest

    # Track backup state to prevent deleting pre-existing output if backup fails (H7)
    init_backup_state()

    # Snapshot existing textfile timestamps from manifest for stable invalidation decisions (H1)
    global _manifest_textfile_snapshot, _all_dependent_textfiles
    manifest.files_updated.clear()
    _manifest_textfile_snapshot = dict(manifest.data.get("textFiles", {}))
    _all_dependent_textfiles.clear()

    # Discover all component files (N4: cross-platform path handling)
    comp_files = [p for p in Path(config.components_dir).rglob("*") if p.is_file() and p.suffix.lower() in (".html", ".htm")]
    current_components: dict[str, float] = {}
    comp_contents: dict[str, str] = {}
    for p in comp_files:
        key = get_component_name(p, config.components_dir)
        current_components[key] = p.stat().st_mtime
        try:
            comp_contents[key] = p.read_text()
        except Exception:
            pass

    global _datetime_components, _comp_textfiles, _components_changed, _latest_component_mtime
    _datetime_components = set()
    for key, content in comp_contents.items():
        if DATETIME_PATTERN.search(content):
            _datetime_components.add(key)

    _comp_textfiles = {}
    for key, content in comp_contents.items():
        tfs = set(TEXTFILE_PATTERN.findall(content))
        if tfs:
            _comp_textfiles[key] = tfs

    changed = True
    while changed:
        changed = False
        for key, content in comp_contents.items():
            refs = set(COMPONENT_REF_PATTERN.findall(content))
            for ref in refs:
                if ref in _datetime_components and key not in _datetime_components:
                    _datetime_components.add(key)
                    changed = True
                if ref in _comp_textfiles:
                    before_len = len(_comp_textfiles.get(key, ()))
                    _comp_textfiles.setdefault(key, set()).update(_comp_textfiles[ref])
                    if len(_comp_textfiles[key]) > before_len:
                        changed = True

    saved_components = manifest.get_components()
    _components_changed = False
    if set(current_components.keys()) != set(saved_components.keys()):
        _components_changed = True
    elif any(current_components[k] != saved_components.get(k, 0) for k in current_components):
        _components_changed = True

    all_comp_entries = [Path(config.components_dir)] + list(Path(config.components_dir).rglob("*"))
    _latest_component_mtime = max((p.stat().st_mtime for p in all_comp_entries), default=0)

    # Copy helper
    def copy(src: str, dest: str) -> str:
        manifest.put(os.path.abspath(dest), Path(src).stat().st_mtime)
        if dest.endswith(config.build_file_exts):
            try:
                src_content = Path(src).read_text()
                tfs = set(TEXTFILE_PATTERN.findall(src_content))
                refs = set(COMPONENT_REF_PATTERN.findall(src_content))
                for ref in refs:
                    if ref in _comp_textfiles:
                        tfs.update(_comp_textfiles[ref])
                _all_dependent_textfiles.update(tfs)
            except Exception:
                pass
        return shutil.copy2(src, dest)

    def _sync_textfile_manifest() -> None:
        for tf_rel in _all_dependent_textfiles:
            tf_path = resolve_text_file_path(config.text_files_dir, tf_rel)
            if tf_path.exists():
                manifest.put_textfile(str(tf_path), tf_path.stat().st_mtime)

    # Verify output directory exists
    if _initial_output_existed:
        # Backup current contents
        if os.path.exists(config.backup_dir):
            shutil.rmtree(config.backup_dir)
        try:
            shutil.copytree(config.output_dir, config.backup_dir)
            _backup_established = True
        except Exception:
            shutil.rmtree(config.backup_dir, ignore_errors=True)
            _backup_established = False
            raise

        # If build path changed (or force rebuild flag), purge all & rebuild
        if get_args().f or os.path.abspath(config.output_dir) != os.path.abspath(manifest.get_build_path()):
            # Purge all, create new manifest
            shutil.rmtree(config.output_dir)
            manifest.clear()
            manifest.set_build_path(config.output_dir)

            # Copy new
            shutil.copytree(config.input_dir, config.output_dir, copy_function=copy)
            manifest.set_components(current_components)
            _sync_textfile_manifest()
            log("Cleaned existing build content.")
        else: # Build path matches manifest & not a force rebuild
            # Copy only updated
            shutil.copytree(config.input_dir, config.output_dir, copy_function=copy_if_newer, dirs_exist_ok=True)
            manifest.set_components(current_components)
            _sync_textfile_manifest()

            if len(manifest.files_updated) > 0:
                log("Updated modified build content.")
            else:
                log("Already up-to-date (-f to force rebuild).")

                # Mark as unchanged
                return None
    else: # Output directory doesn't exist, create new manifest
        # Fresh copy
        manifest.clear()
        manifest.set_build_path(config.output_dir)
        shutil.copytree(config.input_dir, config.output_dir, copy_function=copy)
        manifest.set_components(current_components)
        _sync_textfile_manifest()

    # Return updated files
    return tuple(manifest.files_updated)

# Restores the output directory from backup
def restore_output_from_backup() -> None:
    config = get_config()
    global _backup_established, _initial_output_existed

    # If backup was not established, do NOT delete pre-existing output directory (H7)
    if not _backup_established:
        if _initial_output_existed:
            return
        if os.path.exists(config.output_dir):
            shutil.rmtree(config.output_dir)
        return

    # Backup was established; wipe corrupted output and restore cleanly from backup
    if os.path.exists(config.backup_dir):
        if os.path.exists(config.output_dir):
            shutil.rmtree(config.output_dir)
        shutil.copytree(config.backup_dir, config.output_dir)

# Creates public/sitemap.xml with update timestamps for all HTML files
def build_sitemap(sitemap_path: str, files: tuple[str]) -> None:
    config = get_config()

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
            rel_posix = Path(file).relative_to(config.output_dir).as_posix()
            pretty_path = "/" + rel_posix

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
        <loc>{ xml.sax.saxutils.escape(config.base_address + pretty_path.removeprefix("/")) }</loc>
        <lastmod>{timestamp}</lastmod>
        <priority>{priority:.2f}</priority>
    </url>\n""")

        # Close sitemap
        f.write("</urlset>\n")
