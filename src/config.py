import json
from pathlib import Path
import os
import sys

from logger import *
from manifest import Manifest

# Helper to validate arguments
def _validate_path(data: dict, key: str, make_if_missing: bool=False) -> str:
    # Get path of root directory
    root_path = os.getcwd()

    # Check if absolute or relative path exists
    rel_path = os.path.join(root_path, data[key])
    does_abs_exist = os.path.exists(data[key])
    does_rel_exist = os.path.exists(rel_path)

    if does_abs_exist: return os.path.abspath(data[key])
    if does_rel_exist:
        data[key] = rel_path
        return os.path.abspath(data[key])

    # Otherwise, invalid path
    if make_if_missing:
        # Create missing directory
        Path(data[key]).mkdir(parents=True, exist_ok=True)
        vlog(f"Created missing output directory: {data[key]}")

        # Properly format path now that it exists
        return os.path.abspath(data[key])
    else:
        err(f"Unknown path for \"{key}\": \"{data[key]}\"")
        raise FileNotFoundError()

# Config singleton
class _Config:
    def __init__(self, path: str) -> None:
        # Load json
        with open(path, "r") as f:
            data = json.load(f)

        # Init self
        try:
            # Load path fields
            self.input_dir = _validate_path( data, "inputDir" )
            self.output_dir = _validate_path( data, "outputDir", make_if_missing=True )
            self.components_dir = _validate_path( data, "componentsDir" )

            self.build_file_exts = tuple(data["buildExtensions"])
            self.sitemap_file_exts = tuple(data["sitemapExtensions"])
            self.index_files = tuple(data["indexFiles"])

            # Parse base address
            self.base_address = data["baseAddress"]
            if not self.base_address.endswith("/"): self.base_address += "/"

            # Sitemap fields
            self.generate_sitemap = data["generateSitemap"]
            self.sitemap_ignore: list[str] = data["sitemapIgnore"]
            self.truncate_sitemap_index_files = data["truncateSitemapIndexFiles"]

            # HTML auditor
            self.html_lang = data["htmlLang"]
            self.canonical_ignore: list[str] = data["canonicalIgnore"]
        except KeyError as e:
            err(f"Failed to parse config file, missing JSON key: \"{e}\"")
            sys.exit(1)
        except:
            err(f"Failed to parse config file")
            sys.exit(1)

        # Load manifest
        self.manifest = Manifest()

# Gets the config path, either default or from argv
def _get_config_path():
    argv = sys.argv[1:]
    config_path = None
    cleaned_args = []

    # Check argv
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--config":
            if i + 1 >= len(argv):
                err("--config requires a path")
                exit(1)
            config_path = argv[i + 1]
            i += 2
        else:
            cleaned_args.append(arg)
            i += 1

    # Put cleaned args back
    sys.argv = [sys.argv[0]] + cleaned_args
    return config_path

# Global hidden config variable
_config = None

# Loads global config variable
def load_config():
    global _config

    path = _get_config_path()
    if path is None:
        # Use default path
        path = Path(__file__).resolve().parent.parent / "config.json"
    else:
        # Resolve path
        path = Path(path).expanduser().resolve()

    # Update CWD to project root after resolving path to config file
    os.chdir( Path(__file__).resolve().parent.parent )

    # Load config
    _config = _Config(path)

# Get config file
def get_config():
    if _config is None:
        raise RuntimeError("Config not loaded")
    return _config
