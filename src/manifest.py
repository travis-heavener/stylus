import json
import os

from logger import *

class Manifest:
    """

    The build manifest contains a JSON object whose keys are paths in the build path
    and whose values are the last timestamp that the source file was updated.

    If the source file update timestamp in the manifest is outdated, the target file
    is subsequently updated as well in the build path.

    Keys are absolute paths (os.path.abspath)!

    """

    # Loads the manifest from a file, if present
    def __init__(self, manifest_path: str):
        self.manifest_path = manifest_path
        self.files_updated: set[str] = set()

        try:
            with open( manifest_path, "r" ) as f:
                vlog(f"Loaded manifest at {manifest_path}")
                self.data = json.load(f)
        except FileNotFoundError:
            self.data = {
                "paths": {},
                "buildPath": ""
            }

    # Gets the current buildPath
    def get_build_path(self) -> str:
        return self.data["buildPath"]

    # Sets the stored buildPath
    def set_build_path(self, build_path: str) -> None:
        self.data["buildPath"] = build_path

    # Clears the manifest
    def clear(self) -> None:
        self.files_updated.clear()
        self.data["paths"].clear()

    # Adds or updates a path in the paths dict
    def put(self, path: str, last_update_ts: float) -> None:
        self.data["paths"][path] = last_update_ts
        self.files_updated.add(path)

    # Returns the last update timestamp of a file in the build path, or -1
    def get(self, path: str) -> float:
        return self.data["paths"].get(path, -1)

    # Prunes deleted files from the manifest
    def prune(self, config: Any) -> None:
        keys = [k for k in self.data["paths"].keys()]
        for path in keys:
            # Ignore files only in output dir (e.g. sitemap)
            if self.data["paths"][path] == -1: continue

            # Resolve to source path
            src_path = path.replace(config.output_dir, config.input_dir)
            if not os.path.exists(src_path):
                del self.data["paths"][path]
                vlog(f"Pruned {src_path}")

                # Remove from output dir as well
                if os.path.exists(path):
                    os.remove(path)

    # Writes the manifest to the disk
    def export(self) -> int:
        try:
            with open( self.manifest_path + ".tmp", "w" ) as f:
                vlog(f"Updated manifest at {self.manifest_path}")
                json.dump(self.data, f)

            # Move updated manifest
            os.replace( self.manifest_path + ".tmp", self.manifest_path )
            return 0
        except Exception as e:
            err(f"Failed to write to manifest at {self.manifest_path}\n{e}")
            return 1

    # Prunes AND exports in one line, returns 0 on success or 1 on error
    def prune_and_export(self, config: Any) -> int:
        self.prune(config)
        return self.export()
