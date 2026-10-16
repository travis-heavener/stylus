from html.parser import HTMLParser
from pathlib import Path

from config import get_config
from logger import *

class _AuditorHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.has_charset = False
        self.has_viewport = False
        self.html_lang = None
        self.canonical_hrefs: list[str] = []
        self.img_tags: list[tuple[str, bool]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._process_tag(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._process_tag(tag, attrs)

    def _process_tag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        attr_dict = {k.lower(): (v if v is not None else "") for k, v in attrs}

        if tag_lower == "html":
            if "lang" in attr_dict:
                self.html_lang = attr_dict["lang"]

        elif tag_lower == "meta":
            if "charset" in attr_dict and attr_dict["charset"].lower() == "utf-8":
                self.has_charset = True
            if attr_dict.get("http-equiv", "").lower() == "content-type":
                content = attr_dict.get("content", "").lower()
                if "charset=utf-8" in content.replace(" ", ""):
                    self.has_charset = True
            if attr_dict.get("name", "").lower() == "viewport":
                self.has_viewport = True

        elif tag_lower == "link":
            if attr_dict.get("rel", "").lower() == "canonical":
                if "href" in attr_dict:
                    self.canonical_hrefs.append(attr_dict["href"])

        elif tag_lower == "img":
            has_alt = "alt" in attr_dict
            self.img_tags.append((self.get_starttag_text() or "<img...>", has_alt))

# Audits HTML files for accessibility & W3 guidelines/recommendations
def audit_html(html_files: tuple[str]) -> None:
    config = get_config()
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

        parser = _AuditorHTMLParser()
        parser.feed(body)

        # Check for charset="UTF-8"
        if not parser.has_charset:
            fail_with_msg("Missing meta charset=\"UTF-8\"")

        # Verify canonical tag
        rel_posix = Path(file).relative_to(config.output_dir).as_posix()
        short_path = "/" + rel_posix

        # Remove index file suffixes
        for suffix in config.index_files:
            if short_path.endswith(suffix):
                short_path = short_path.removesuffix(suffix)
                break

        if short_path not in config.canonical_ignore:
            canonical = config.base_address + short_path.removeprefix("/")
            if canonical not in parser.canonical_hrefs:
                fail_with_msg(f"Missing or invalid canonical link (should be \"{canonical}\").")

        # Check for meta viewport
        if not parser.has_viewport:
            fail_with_msg("Missing meta viewport tag")

        # Check for lang="en"
        if parser.html_lang is None or parser.html_lang.lower() != config.html_lang.lower():
            fail_with_msg(f"Missing HTML lang=\"{config.html_lang}\"")

        # Check for alt text on img elements
        for tag_str, has_alt in parser.img_tags:
            if not has_alt:
                fail_with_msg(f"Missing alt text on img, near \"{tag_str[:min(30, len(tag_str))]}...\"")

    # Log status
    if is_passing:
        log("Passing HTML audit")
    else:
        warn("Failing HTML audit")
