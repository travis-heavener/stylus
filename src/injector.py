from datetime import datetime
from pathlib import Path
import re

from config import config
from logger import *
from tools import vlog

# Injects HTML into the pseudo-element components
def inject_html(updated_files: tuple[str]) -> None:
    # Read all components
    components = {
        str(p).removeprefix(config.components_dir).removeprefix("/").replace("/", ".").removesuffix(".html")
        : p.read_text()
        for p in Path(config.components_dir).rglob("*")
        if p.is_file()
    }

    # Replace pseudo-components in components
    for key in components.keys():
        # Inject pseudo-components AFTER components
        components[key] = inject_pseudo_components(components[key])

    # Precompile pattern
    components_pattern = re.compile(
        rf"^(\s*)<\$\s*({ '|'.join([k for k in components.keys()]) })\s*\/\s*>",
        flags=re.MULTILINE
    )

    # Shorthand to Regex replace elements
    def comp(m: re.Match) -> str:
        indent = m.group(1).replace("\n", "") # Fix indents
        return indent + components[ m.group(2).strip() ].replace("\n", f"\n{indent}")

    # Find each HTML file in the subtree
    html_files = tuple( [Path(f) for f in updated_files if f.endswith(".html")] )

    for file in html_files:
        # Replace all pseudo-elements with their HTML components
        try:
            body = components_pattern.sub( comp, file.read_text() )
        except KeyError as e:
            err(f"Invalid component: {e}")
            exit(1)

        # Inject pseudo-components that may be hiding in html file
        body = inject_pseudo_components(body)

        # Write back to file
        file.write_text(body)

        # Log if verbose
        vlog(f"Built {file}")

# Injects pseudo-components into the HTML
__datetime_pattern = re.compile(r'<\$\s*Datetime\s*:\s*"([^"]+)"\s*/>')
def inject_pseudo_components(body: str) -> str:
    # Datetime pseudos
    body = __datetime_pattern.sub(
        lambda m: datetime.now().strftime(m.group(1)),
        body
    )

    return body
