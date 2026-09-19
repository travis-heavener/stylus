#!/usr/bin/env python3

"""

Author: Travis Heavener
Date: April 23, 2026

"""

import json
import os
from pathlib import Path
from time import time
import traceback

from args import init_argparser
from auditor import audit_html
from config import get_config, load_config
from exception import StylusException
from injector import inject_html
from logger import *
from tools import *

# Returns the exit code
def main() -> int:
    # Debug profiling
    start = time()

    # Load arguments
    init_argparser()

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

        # Handle if already up-to-date
        if updated_files is None:
            # Prune & save manifest
            if config.manifest.prune_and_export(config) == 1:
                # Failed
                restore_output_from_backup()
                return 1

            # Build sitemap.xml since deleted files from manifest.prune may persist in sitemap.xml
            files = [str(p) for p in Path(config.output_dir).rglob("*")]
            sitemap_files = tuple([f for f in files if f.endswith(config.sitemap_file_exts)])

            sitemap_path = os.path.join( config.output_dir, "sitemap.xml" )
            if config.generate_sitemap:
                sitemap_files = tuple([f for f in files if f.endswith(config.sitemap_file_exts)])
                build_sitemap(sitemap_path, sitemap_files)
            elif os.path.exists( sitemap_path ):
                os.remove( sitemap_path )

            return 0

        # Otherwise, out-of-date
        files = [str(p) for p in Path(config.output_dir).rglob("*")]

        # 2. Build site from HTML skeleton
        updated_build_files = tuple([f for f in updated_files if f.endswith(config.build_file_exts)])
        inject_html(updated_build_files)

        # 3. Run accessibility audit on newly generated files
        if not get_args().a:
            audit_html(updated_build_files)
        else:
            warn("Skipping HTML audit")

        # 4. Minify assets
        if not get_args().x:
            minify()
        else:
            warn("Skipping minification")

        # 5. Prune & save manifest
        if config.manifest.prune_and_export(config) == 1:
            # Failed
            restore_output_from_backup()
            return 1

        # 6. Build sitemap.xml
        sitemap_path = os.path.join( config.output_dir, "sitemap.xml" )
        if config.generate_sitemap:
            files = [str(p) for p in Path(config.output_dir).rglob("*")]
            sitemap_files = tuple(
                f for f in files
                if f.endswith(config.sitemap_file_exts)
            )
            build_sitemap(sitemap_path, sitemap_files)
        elif os.path.exists( sitemap_path ):
            os.remove( sitemap_path )

        # Log success
        log(f"Build success ({round(time() - start)}s).")
        return 0
    except Exception as e:
        err(f"Build failed ({round(time() - start)}s):")

        if isinstance(e, StylusException):
            err(e.msg)
        else:
            traceback.print_exc()

        # Restore backup
        restore_output_from_backup()
        return 1

if __name__ == "__main__":
    status = main()

    # Remove backup contents
    config = get_config()
    backup_dir = Path(config.backup_dir)
    if backup_dir.exists(): shutil.rmtree(backup_dir)

    exit(status)
