import json
import os

from logger import *

_build_manifest_path = "build-manifest.json"

class Manifest:
    """

    The build manifest contains a JSON object whose keys are paths in the build path
    and whose values are the last timestamp that the source file was updated.

    If the source file update timestamp in the manifest is outdated, the target file
    is subsequently updated as well in the build path.

    Keys are absolute paths (os.path.abspath)!

    """

    # Loads the manifest from a file, if present
    def __init__(self):
        self.files_updated: set[str] = set()

        try:
            with open( os.path.join(os.getcwd(), _build_manifest_path), "r" ) as f:
                vlog(f"Loaded {_build_manifest_path}")
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

    # Writes the manifest to the disk
    def export(self) -> None:
        try:
            with open( os.path.join(os.getcwd(), _build_manifest_path), "w" ) as f:
                vlog(f"Updated {_build_manifest_path}")
                json.dump(self.data, f)
        except Exception as e:
            err(f"Failed to write to {_build_manifest_path}\n{e}")
