import json
from pathlib import Path
import os
from sys import exit

from logger import *

# Helper to validate arguments
def _validate_path(data: dict, key: str, make_if_missing: bool=False) -> str:
    # Get path of root directory
    root_path = Path(__file__).resolve().parent

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
        data[key] = os.path.abspath(data[key])
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
            exit(1)
        except:
            err(f"Failed to parse config file")
            exit(1)

# Get path to config file
__config_path = Path.joinpath(Path(__file__).resolve().parent.parent, "config.json")

# Global config object
if Path.exists(__config_path):
    config = _Config( str(__config_path) )
else:
    config = None
