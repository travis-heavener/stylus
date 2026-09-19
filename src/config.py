import json
from pathlib import Path
import os
import shutil
import sys

from args import get_args
from logger import *
from manifest import Manifest

# Returns all paths that are nested or are relative to one-another (including those that match)
def _get_nested_paths(*path_strs: list[str]) -> tuple[bool, tuple[str]]:
    paths = tuple([ Path(p).expanduser().resolve() for p in path_strs ])
    invalid_paths = set()

    for i, A in enumerate(paths):
        for j, B in enumerate(paths):
            if i == j: continue

            # Verify non-cyclical
            if A.is_relative_to(B) or B.is_relative_to(A):
                invalid_paths.add(A)
                invalid_paths.add(B)

    # Return conflicting paths
    return tuple(invalid_paths)

# Helper to validate arguments
def _validate_dir_path(root_path: str, data: dict, key: str, make_if_missing: bool=False) -> str:
    # Check if absolute or relative path exists
    rel_path = os.path.join(root_path, data[key])
    does_abs_exist = os.path.exists(data[key])
    does_rel_exist = os.path.exists(rel_path)

    # Check absolute & relative paths
    if does_abs_exist or does_rel_exist:
        if does_rel_exist: data[key] = rel_path

        if Path(data[key]).is_dir():
            return os.path.abspath(data[key])
        else:
            err(f"In config file, {data[key]} must be a directory")
            raise NotADirectoryError()

    # Otherwise, invalid path
    if make_if_missing:
        # Create missing directory
        new_path = Path(root_path).joinpath( data[key] )
        new_path.mkdir(parents=True, exist_ok=True)
        vlog(f"Created missing output directory: {str(new_path)}")

        # Properly format path now that it exists
        return str(new_path.resolve())
    else:
        err(f"Unknown path for \"{key}\": \"{data[key]}\"")
        raise FileNotFoundError()

# Config singleton
class _Config:
    def __init__(self, path: str) -> None:
        # Save the parent directory of the config.json file
        self._config_file_parent_dir = Path(path).resolve().parent

        # Store build manifest alongside config file
        self.manifest_path = str(self._config_file_parent_dir / "build-manifest.json")

        # Load json
        with open(path, "r") as f:
            data = json.load(f)

        # Init self
        try:
            # Load path fields
            self.input_dir = _validate_dir_path( self._config_file_parent_dir, data, "inputDir" )
            self.output_dir = _validate_dir_path( self._config_file_parent_dir, data, "outputDir", make_if_missing=True )
            self.components_dir = _validate_dir_path( self._config_file_parent_dir, data, "componentsDir" )
            self.text_files_dir = _validate_dir_path( self._config_file_parent_dir, data, "textFilesDir" )

            # Create buffer staging directory
            self.backup_dir = self._config_file_parent_dir / "stylus-tmp"
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            self.backup_dir = os.path.abspath( self.backup_dir )

            # Verify directory fields are non-nested
            nested_paths = _get_nested_paths(
                self.input_dir, self.output_dir, self.components_dir, self.text_files_dir, self.backup_dir
            )
            if len(nested_paths):
                err("Paths in configuration file must NOT be nested within one another")
                for i, path in enumerate(nested_paths):
                    print(f"  - Path #{i+1}: {nested_paths[i]}", file=sys.stderr)

                # Finally, raise the exception to abort
                raise Exception()

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
        self.manifest = Manifest(self.manifest_path)

# Global hidden config variable
_config = None

# Loads global config variable
def load_config():
    global _config
    args = get_args()

    path = args.config
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
