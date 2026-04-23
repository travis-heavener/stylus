#!/usr/bin/env python3

"""

Author: Travis Heavener
Date: April 23, 2026

"""

import os
from pathlib import Path
from time import time
import traceback

from auditor import audit_html
from config import config
from injector import inject_html
from logger import *
from tools import *

if __name__ == "__main__":
    # Debug profiling
    start = time()

    # Update CWD to project root
    os.chdir( Path(__file__).resolve().parent )

    # Verify config file was loaded
    if config is None:
        err("Failed to load config.json")

    try:
        # 1. Copy source
        updated_files = copy_source()

        # 2. Build site from HTML skeleton
        inject_html(updated_files)

        # 3. Build sitemap.xml
        html_files = tuple( [str(p) for p in Path(config.output_dir).rglob("*.html")] )
        build_sitemap(html_files)

        # 4. Run accessibility audit
        audit_html(html_files)

        # 5. Minify assets
        if not isarg("x"):
            minify()
        else:
            warn("Skipping minification")

        # Log success
        log(f"Build success ({round(time() - start)}s).")
    except Exception as e:
        log(f"Build failed ({round(time() - start)}s):")
        traceback.print_exc()
