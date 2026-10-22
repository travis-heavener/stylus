from datetime import datetime
import os
from pathlib import Path
import re

from config import get_config
from exception import StylusException
from logger import *
from tools import vlog, DATETIME_PATTERN, TEXTFILE_PATTERN, resolve_text_file_path, get_component_name

# Injects HTML into the pseudo-element components
def inject_html(updated_build_files: tuple[str]) -> None:
    config = get_config()

    # Read all components
    components = {
        get_component_name(p, config.components_dir): p.read_text()
        for p in Path(config.components_dir).rglob("*")
        if p.is_file() and p.suffix.lower() in (".html", ".htm")
    }

    # Replace pseudo-components in components
    for key in components.keys():
        # Inject pseudo-components AFTER components
        components[key] = inject_pseudos(None, components[key], component_name=key)

    # Precompile pattern: match any component name (not pseudo-components which have colons)
    components_pattern = re.compile(
        r"(.*?)<\$\s*([^:\"'\s/>]+)\s*\/\s*>",
        flags=re.MULTILINE
    )

    comp_ref_pattern = re.compile(r"<\$\s*([^:\"'\s/>]+)\s*\/\s*>")
    comp_refs = {
        name: [m.strip() for m in comp_ref_pattern.findall(content)]
        for name, content in components.items()
    }

    # Shorthand to Regex replace elements
    def comp(m: re.Match) -> str:
        comp_name = m.group(2).strip()
        if comp_name not in components:
            raise KeyError(comp_name)

        # Fix indents
        if str.isspace(m.group(1)):
            indent = m.group(1).replace("\n", "")
            return indent + components[ comp_name ].replace("\n", f"\n{indent}")
        else:
            # No indents
            return m.group(1) + components[ comp_name ]

    # Find each build file in the subtree
    for file_name in updated_build_files:
        file = Path(file_name)
        body = file.read_text()

        # Detect circular component references before expansion to prevent exponential memory growth (N1)
        visited = set()
        rec_set = set()

        def detect_cycle(comp_name: str) -> bool:
            visited.add(comp_name)
            rec_set.add(comp_name)

            for ref in comp_refs.get(comp_name, []):
                if ref not in components:
                    continue
                if ref in rec_set:
                    return True
                if ref not in visited:
                    if detect_cycle(ref):
                        return True

            rec_set.remove(comp_name)
            return False

        for ref in comp_ref_pattern.findall(body):
            ref = ref.strip()
            if ref in components and ref not in visited:
                if detect_cycle(ref):
                    raise StylusException(f"Circular component reference detected in {file}")

        # Recursively replace component references with cycle detection (N1)
        depth = 0
        max_depth = 50
        while components_pattern.search(body):
            depth += 1
            if depth > max_depth:
                raise StylusException(f"Circular component reference detected in {file}")
            try:
                body = components_pattern.sub( comp, body )
            except KeyError as e:
                raise StylusException(f"Invalid component: {e}")

        # Inject pseudo-components that may be hiding in html file
        body = inject_pseudos(str(file), body)

        # Check for any remaining unknown components or pseudo-components
        leftover = re.search(r'<\$\s*([^>]+?)\s*\/?\s*>', body)
        if leftover:
            raw = leftover.group(1).strip().removesuffix("/").strip()
            raise StylusException(f"Invalid component: '{raw}'")

        # Write back to file
        file.write_text(body)

        # Log if verbose
        vlog(f"Built {file}")

# Injects pseudo-components into the HTML
__cachebust_attr_pattern = re.compile( r"""\$stylus-cache-bust-([A-Za-z_:][\w:.-]*)\s*=\s*(["'])((?:\\.|(?!\2).)*)\2""" )
def inject_pseudos(current_path: str | None, body: str, component_name: str | None = None) -> str:
    config = get_config()

    # Datetime pseudos
    body = DATETIME_PATTERN.sub(
        lambda m: datetime.now().strftime(m.group(1)),
        body
    )

    # TextFile pseudos
    try:
        def read_text(path: str) -> str:
            resolved_path = resolve_text_file_path(config.text_files_dir, path)
            with open(resolved_path, "r") as f:
                return f.read()

        body = TEXTFILE_PATTERN.sub(
            lambda f: read_text(f.group(1)),
            body
        )
    except FileNotFoundError as e:
        raise StylusException(f"Failed to resolve TextFile pseudo-component\nFileNotFoundError: {e}")

    # Cache bust pseudo-attributes
    try:
        input_dir = Path(config.input_dir).resolve()
        output_dir = Path(config.output_dir).resolve()

        def resolve_cache_bust_path(match: re.Match, attr_path: str) -> Path:
            # Strip hash & query string
            if "?" in attr_path: attr_path = attr_path[ :attr_path.index("?") ]
            if "#" in attr_path: attr_path = attr_path[ :attr_path.index("#") ]

            # Web-root relative paths
            if attr_path.startswith("/"):
                target = (input_dir / attr_path.removeprefix("/")).resolve()
            else:
                # Paths relative to current_path
                nonlocal current_path
                if current_path is None:
                    raise StylusException(
                        f"Cannot use Cache Bust pseudo-attribute w/ relative path in component.\n"
                        "Use absolute paths for cache busting in components.\n"
                        f"Context:\n  {match.group()}"
                    )

                current_file = Path(current_path).resolve()
                current_rel_parent = current_file.parent.relative_to(output_dir)
                source_parent = input_dir / current_rel_parent
                target = (source_parent / attr_path).resolve()

            if not target.is_relative_to(input_dir):
                raise StylusException(
                    "Failed to resolve Cache Bust pseudo-attribute (path escapes input directory)\n"
                    f"Source: {(component_name + ' (Component)') if current_path is None else current_path}\n"
                    f"Context:\n  {match.group()}"
                )

            if not target.exists():
                raise FileNotFoundError(f"'{target}' does not exist")

            if target.is_dir():
                for idx in config.index_files:
                    candidate = target / idx
                    if candidate.is_file():
                        target = candidate
                        break

            return target

        def replace_cache_bust(match: re.Match) -> str:
            attr, quote, path = match.groups()

            try:
                target_path = resolve_cache_bust_path(match, path)
                mod = int( target_path.stat().st_mtime * 1000 )
            except FileNotFoundError as e:
                raise StylusException(
                    "Failed to resolve Cache Bust pseudo-attribute (file not found)\n"
                    f"Source: {(component_name + ' (Component)') if current_path is None else current_path}\n"
                    f"Context:\n  {match.group()}"
                )

            # Isolate URL hash, if exists
            if "#" in path:
                base_path, hash_part = path.split("#", 1)
                hash_part = f"#{hash_part}"
            else:
                base_path = path
                hash_part = ""

            # Check & append cache-bust param
            if "?" in base_path:
                updated_base = f"{base_path}&_m={mod}"
            else:
                updated_base = f"{base_path}?_m={mod}"

            # Rebuild path w/ new query string & hash
            return f"{attr}={quote}{updated_base}{hash_part}{quote}"

        body = __cachebust_attr_pattern.sub(replace_cache_bust, body)
    except FileNotFoundError as e:
        raise StylusException(f"Failed to resolve Cache Bust pseudo-attribute\nFileNotFoundError: {e}")

    return body
