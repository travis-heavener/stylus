import os
import re

from config import *
from logger import *

# Audits HTML files for accessibility & W3 guidelines/recommendations
def audit_html(html_files: tuple[str]) -> None:
    is_passing = True

    def fail_with_msg(*args) -> None:
        nonlocal is_passing
        warn("Audit:", *args, f"({file})")
        is_passing = False

    # Open each file
    for file in html_files:
        # Read file contents
        with open(file, "r") as f:
            body = f.read()

        # Check for charset="UTF-8"
        if not re.search(r"""<meta\s.*?\bcharset=['"]UTF-8['"].*?>""", body):
            fail_with_msg("Missing meta charset=\"UTF-8\"")

        # Verify canonical tag
        short_path = file.removeprefix(config.output_dir).removesuffix("index.html")
        if short_path not in config.canonical_ignore:
            canonical = config.canonical_base + short_path.removeprefix("/")
            canonical_pat_a = rf"""rel=['"]canonical['"].*?\bhref=['"]{canonical}['"]"""
            canonical_pat_b = rf"""href=['"]{canonical}['"].*?\brel=['"]canonical['"]"""
            if not re.search(rf"""<link\s.*?\b({canonical_pat_a})|({canonical_pat_b}).*?>""", body):
                fail_with_msg(f"Missing or invalid canonical link (should be \"{canonical}\").")

        # Check for meta viewport
        if not re.search(r"""<meta\s.*?\bname=['"]viewport['"].*?>""", body):
            fail_with_msg("Missing meta viewport tag")

        # Check for lang="en"
        if not re.search(rf"""<html\s.*?\blang=['"]{config.meta_lang}['"].*?>""", body):
            fail_with_msg("Missing HTML lang=\"en\"")

        # Check for alt text on img elements
        imgs = re.findall(r"<img .*?>", body)
        for img in imgs:
            if not re.search(r"""\balt=['"].*?['"]""", img):
                fail_with_msg(f"Missing alt text on img, near \"{img[:min(30, len(img))]}...\"")

    # Log status
    if is_passing:
        log("Passing HTML audit")
    else:
        warn("Failing HTML audit")
