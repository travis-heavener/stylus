#!/usr/bin/env python3

"""

Author: Travis Heavener
Date: April 23, 2026

"""

import json
from pathlib import Path
from time import time
import traceback

from auditor import audit_html
from config import get_config, load_config
from injector import inject_html
from logger import *
from tools import *

if __name__ == "__main__":
    # Debug profiling
    start = time()

    # Load config
    try:
        load_config()
        config = get_config()
    except FileNotFoundError as e:
        err(f"Failed to load config file\nFileNotFoundError: {e}")
        exit(1)
    except json.decoder.JSONDecodeError as e:
        err(f"Failed to load config file\nJSONDecodeError: {e}")
        exit(1)

    try:
        # 1. Copy source
        updated_files = copy_source()
        files = [str(p) for p in Path(config.output_dir).rglob("*")]

        # 2. Build site from HTML skeleton
        updated_build_files = tuple([f for f in updated_files if f.endswith(config.build_file_exts)])
        inject_html(updated_build_files)

        # 3. Build sitemap.xml
        sitemap_files = tuple([f for f in files if f.endswith(config.sitemap_file_exts)])
        build_sitemap(sitemap_files)

        # 4. Run accessibility audit on newly generated files
        if not isarg("a"):
            audit_html(updated_build_files)
        else:
            warn("Skipping HTML audit")

        # 5. Minify assets
        if not isarg("x"):
            minify()
        else:
            warn("Skipping minification")

        # Prune & save manifest
        config.manifest.prune(config)
        config.manifest.export()

        # Log success
        log(f"Build success ({round(time() - start)}s).")
    except Exception as e:
        err(f"Build failed ({round(time() - start)}s):")
        traceback.print_exc()
