from datetime import datetime
import os
from pathlib import Path
import re

from config import get_config
from logger import *
from tools import vlog

# Injects HTML into the pseudo-element components
def inject_html(updated_build_files: tuple[str]) -> None:
    config = get_config()

    # Read all components
    components = {
        str(p).removeprefix(config.components_dir).removeprefix("/").replace("/", ".") \
            .removesuffix(".html").removesuffix(".htm")
        : p.read_text()
        for p in Path(config.components_dir).rglob("*")
        if p.is_file()
    }

    # Replace pseudo-components in components
    for key in components.keys():
        # Inject pseudo-components AFTER components
        components[key] = inject_pseudos(None, components[key])

    # Precompile pattern
    components_pattern = re.compile(
        rf"(.*?)<\$\s*({ '|'.join(map(re.escape, components.keys())) })\s*\/\s*>",
        flags=re.MULTILINE
    )

    # Shorthand to Regex replace elements
    def comp(m: re.Match) -> str:
        # Fix indents
        if str.isspace(m.group(1)):
            indent = m.group(1).replace("\n", "")
            return indent + components[ m.group(2).strip() ].replace("\n", f"\n{indent}")
        else:
            # No indents
            return m.group(1) + components[ m.group(2).strip() ]

    # Find each build file in the subtree
    for file_name in updated_build_files:
        file = Path(file_name)
        # Replace all pseudo-elements with their HTML components
        try:
            body = components_pattern.sub( comp, file.read_text() )
        except KeyError as e:
            err(f"Invalid component: {e}")
            exit(1)

        # Inject pseudo-components that may be hiding in html file
        body = inject_pseudos(str(file), body)

        # Write back to file
        file.write_text(body)

        # Log if verbose
        vlog(f"Built {file}")

# Injects pseudo-components into the HTML
__datetime_pattern = re.compile(r'<\$\s*Datetime\s*:\s*"([^"]+)"\s*/>')
__textfile_pattern = re.compile(r'<\$\s*TextFile\s*:\s*"([^"]+)"\s*/>')
__cachebust_attr_pattern = re.compile( r"""\$stylus-cache-bust-([A-Za-z_:][\w:.-]*)\s*=\s*(["'])((?:\\.|(?!\2).)*)\2""" )
def inject_pseudos(current_path: str | None, body: str) -> str:
    config = get_config()

    # Datetime pseudos
    body = __datetime_pattern.sub(
        lambda m: datetime.now().strftime(m.group(1)),
        body
    )

    # TextFile pseudos
    try:
        def read_text(path: str) -> str:
            with open(os.path.join(config.text_files_dir, path), "r") as f:
                return f.read()

        body = __textfile_pattern.sub(
            lambda f: read_text(f.group(1)),
            body
        )
    except FileNotFoundError as e:
        err(f"Failed to resolve TextFile pseudo-component\nFileNotFoundError: {e}")

    # Cache bust pseudo-attributes
    try:
        input_dir = Path(config.input_dir).resolve()
        output_dir = Path(config.output_dir).resolve()

        def resolve_cache_bust_path(match: re.Match, attr_path: str) -> Path:
            # Web-root relative paths
            if attr_path.startswith("/"): return input_dir / attr_path.removeprefix("/")

            # Paths relative to current_path
            if current_path is None: raise ValueError(match.group())

            current_file = Path(current_path).resolve()
            current_rel_parent = current_file.parent.relative_to(output_dir)
            source_parent = input_dir / current_rel_parent
            return (source_parent / attr_path).resolve()

        def replace_cache_bust(match: re.Match) -> str:
            attr, quote, path = match.groups()
            mod = int( resolve_cache_bust_path(match, path).stat().st_mtime * 1000 )
            return f"{attr}={quote}{path}?_m={mod}{quote}"

        body = __cachebust_attr_pattern.sub(replace_cache_bust, body)
    except ValueError as e:
        err(f"Cannot use Cache Bust pseudo-attribute w/ relative path in component.\nUse absolute paths for cache busting in components.\nContext:\n  {e}")
    except FileNotFoundError as e:
        err(f"Failed to resolve Cache Bust pseudo-attribute\nFileNotFoundError: {e}")

    return body
