import json
from pathlib import Path
from os import path
from sys import exit

from logger import *

# Helper to validate arguments
def _validate_path(data: dict, key: str) -> str:
    if not path.exists(data[key]):
        err(f"Unknown path for \"{key}\": \"{data[key]}\"")
        raise FileNotFoundError()
    return data[key]

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
            self.output_dir = _validate_path( data, "outputDir" )
            self.components_dir = _validate_path( data, "componentsDir" )

            # Parse base address
            self.base_address = data["baseAddress"]
            if not self.base_address.endswith("/"): self.base_address += "/"

            # Sitemap fields
            self.generate_sitemap = data["generateSitemap"]
            self.sitemap_ignore: list[str] = data["sitemapIgnore"]

            # HTML auditor
            self.meta_lang = data["metaLang"]
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
