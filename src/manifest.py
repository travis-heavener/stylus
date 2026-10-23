import json
import os
from pathlib import Path

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
        if "components" in self.data:
            self.data["components"].clear()
        if "componentHashes" in self.data:
            self.data["componentHashes"].clear()
        if "textFiles" in self.data:
            self.data["textFiles"].clear()
        if "textFileHashes" in self.data:
            self.data["textFileHashes"].clear()
        if "fileHashes" in self.data:
            self.data["fileHashes"].clear()
        if "datetimes" in self.data:
            self.data["datetimes"].clear()

    # Gets the stored rendered value of a Datetime format, or None
    def get_datetime(self, fmt: str) -> str | None:
        return self.data.get("datetimes", {}).get(fmt)

    # Stores the rendered value of a Datetime format
    def put_datetime(self, fmt: str, val: str) -> None:
        if "datetimes" not in self.data:
            self.data["datetimes"] = {}
        self.data["datetimes"][fmt] = val

    # Gets the stored components mapping
    def get_components(self) -> dict[str, float]:
        return self.data.get("components", {})

    # Sets the stored components mapping
    def set_components(self, components: dict[str, float]) -> None:
        self.data["components"] = components

    # Gets the stored component hashes mapping
    def get_component_hashes(self) -> dict[str, str]:
        return self.data.get("componentHashes", {})

    # Sets the stored component hashes mapping
    def set_component_hashes(self, component_hashes: dict[str, str]) -> None:
        self.data["componentHashes"] = component_hashes

    # Gets the last update timestamp of a text file, or -1
    def get_textfile(self, path: str) -> float:
        return self.data.get("textFiles", {}).get(path, -1)

    # Stores the update timestamp of a text file
    def put_textfile(self, path: str, mtime: float) -> None:
        if "textFiles" not in self.data:
            self.data["textFiles"] = {}
        self.data["textFiles"][path] = mtime

    # Gets the stored hash of a text file, or None
    def get_textfile_hash(self, path: str) -> str | None:
        return self.data.get("textFileHashes", {}).get(path)

    # Stores the hash of a text file
    def put_textfile_hash(self, path: str, file_hash: str) -> None:
        if "textFileHashes" not in self.data:
            self.data["textFileHashes"] = {}
        self.data["textFileHashes"][path] = file_hash

    # Gets the stored hash of a build/output file, or None
    def get_file_hash(self, path: str) -> str | None:
        return self.data.get("fileHashes", {}).get(path)

    # Stores the hash of a build/output file
    def put_file_hash(self, path: str, file_hash: str) -> None:
        if "fileHashes" not in self.data:
            self.data["fileHashes"] = {}
        self.data["fileHashes"][path] = file_hash

    # Adds or updates a path in the paths dict
    def put(self, path: str, last_update_ts: float) -> None:
        self.data["paths"][path] = last_update_ts
        self.files_updated.add(path)

    # Removes a path from the paths dict
    def remove(self, path: str) -> None:
        if path in self.data.get("paths", {}):
            del self.data["paths"][path]
        if "fileHashes" in self.data and path in self.data["fileHashes"]:
            del self.data["fileHashes"][path]
        self.files_updated.discard(path)

    # Returns the last update timestamp of a file in the build path, or -1
    def get(self, path: str) -> float:
        return self.data["paths"].get(path, -1)

    # Prunes deleted files from the manifest
    def prune(self, config: Any) -> None:
        sitemap_abs = os.path.abspath(os.path.join(config.output_dir, "sitemap.xml"))
        keys = [k for k in self.data["paths"].keys()]
        for path in keys:
            # Ignore files only in output dir (e.g. sitemap), but prune if removed
            if self.data["paths"][path] == -1:
                if path == sitemap_abs and not getattr(config, "generate_sitemap", True):
                    del self.data["paths"][path]
                    if "fileHashes" in self.data and path in self.data["fileHashes"]:
                        del self.data["fileHashes"][path]
                    if os.path.exists(path):
                        os.remove(path)
                    continue
                if not os.path.exists(path):
                    del self.data["paths"][path]
                    if "fileHashes" in self.data and path in self.data["fileHashes"]:
                        del self.data["fileHashes"][path]
                continue

            # Resolve to source path cleanly without substring replacement
            try:
                rel = Path(path).resolve().relative_to(Path(config.output_dir).resolve())
                src_path = str(Path(config.input_dir).resolve() / rel)
            except ValueError:
                src_path = path

            if not os.path.exists(src_path):
                del self.data["paths"][path]
                if "fileHashes" in self.data and path in self.data["fileHashes"]:
                    del self.data["fileHashes"][path]
                vlog(f"Pruned {src_path}")

                # Remove from output dir as well
                if os.path.exists(path):
                    os.remove(path)

        if "textFiles" in self.data:
            for tf_path in list(self.data["textFiles"].keys()):
                if not os.path.exists(tf_path):
                    del self.data["textFiles"][tf_path]
                    if "textFileHashes" in self.data and tf_path in self.data["textFileHashes"]:
                        del self.data["textFileHashes"][tf_path]

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
