# Stylus Agent Guide

A quick-reference guide for AI agents and developers working on the Stylus static site generator.

## System Overview

Stylus is a zero-bloat static site generator (SSG) for static HTML sites written in Python (standard library only).

### Directory & File Structure

```text
Stylus/
├── src/
│   ├── main.py        # CLI entry point and build lifecycle coordination
│   ├── config.py      # Configuration parser, path validator, directory nesting checks
│   ├── manifest.py    # Build manifest management (build-manifest.json)
│   ├── tools.py       # Incremental copy, dependency tracking, sitemap generation, backup
│   ├── injector.py    # Injects components, pseudo-components, and cache-bust attributes
│   ├── auditor.py     # HTML accessibility and SEO auditor (HTMLParser-based)
│   ├── args.py        # CLI argument parsing (-a, -c, -f, -q, --config)
│   ├── logger.py      # Terminal logging helpers (vlog, log, warn, err)
│   └── exception.py   # StylusException custom exception class
├── example-src/       # Example site source HTML
├── example-components/# Example reusable HTML components
├── example-text/      # Example text files for TextFile pseudo-component
├── config.sample.json # Reference configuration
└── CONFIG.md          # User-facing config documentation
```

---

## Build Lifecycle & Pipeline

1. **Argument & Config Loading** (`main.py`, `config.py`):
   - Reads `--config <path>` (defaults to `config.json` in project root).
   - Resolves all directory paths relative to the configuration file's directory.
   - Verifies that configured directories (`inputDir`, `outputDir`, `componentsDir`, `textFilesDir`, `backupDir`) do not nest or conflict.
   - Loads or creates `build-manifest.json` alongside the config file.

2. **Backup Staging** (`tools.py:copy_source`, `restore_output_from_backup`):
   - Existing `outputDir` is backed up to `stylus-tmp/` before performing modifications.
   - **Backup Safety (H7)**: `_backup_established` and `_initial_output_existed` track state. If the initial backup fails before modifying anything, `restore_output_from_backup()` leaves the pre-existing `outputDir` completely intact. It only performs deletion/restoration if a valid backup was established.

3. **Incremental Copy & Invalidation** (`tools.py:copy_source`, `copy_if_newer`):
   - **Components Tracking (H3, N4)**:
     - Scans `componentsDir` using cross-platform `get_component_name(p, components_dir)` (`Path.parts`).
     - Safely handles empty component directories (`max(..., default=0)`).
     - Compares component names and timestamps against `manifest.get_components()`.
     - Detects component additions, edits, and deletions (using `!=` to detect older/reverted timestamps (**N3**)); invalidates all HTML files if components changed.
   - **Datetime Pages (H2)**:
     - Checks whether an HTML page directly contains `<$ Datetime:... />` or depends on a component that does.
     - Invalidates and rebuilds `Datetime` pages on subsequent builds so dynamic timestamps remain current.
   - **TextFile Dependencies (H1)**:
     - Takes an immutable snapshot of manifest text-file timestamps before traversing files (`_manifest_textfile_snapshot`), preventing traversal mutations from masking changes across multiple pages.
     - Checks direct and component-inherited `<$ TextFile:"..." />` dependencies.
     - Rebuilds dependent HTML pages when any referenced text file's mtime changes (newer or older) or when the text file is removed.
     - Syncs text file manifest entries after all copy decisions complete.

4. **HTML Injection** (`injector.py:inject_html`):
   - Loads components using cross-platform component names (`get_component_name`).
   - Recursively expands nested component references (`<$ Outer />` -> `<$ Inner />`) with cycle detection up to depth 50 (**N1**).
   - Replaces `<$ ComponentName />` syntax with component HTML, preserving indentation at each level.
   - Rejects unknown component names with `StylusException: Invalid component: '<name>'` (**M3**).
   - Replaces pseudo-components:
     - `<$ Datetime:"<strftime>" />`
     - `<$ TextFile:"<path>" />` (expands relative, absolute, and `~` home paths).
   - Replaces cache-bust pseudo-attributes (`$stylus-cache-bust-src`, `$stylus-cache-bust-href`):
     - Prevents directory traversal attacks escaping `inputDir` (**M4**).
   - Final pass verifies no unresolved `<$ ... />` syntax remains in output.

5. **HTML Audit** (`auditor.py:audit_html`):
   - Powered by standard library `html.parser.HTMLParser` (`_AuditorHTMLParser`).
   - Evaluates actual parsed attribute pairs, eliminating false positives from text inside attributes like `<img data-note="alt=..." src="...">` (**M1**).
   - Accepts both quoted and valid unquoted HTML attribute values (**N2**).
   - Case-insensitive checks (**M2**):
     - `<meta charset="UTF-8">` (matches `utf-8` / `UTF-8`).
     - `<meta name="viewport" ...>`.
     - `<html lang="...">`.
     - `<link rel="canonical" href="...">`.
   - Validates `img` tags (`alt=""`, `alt='...'`, `alt="val"`, `alt=val`, boolean `alt`).

6. **Manifest & Sitemap** (`manifest.py`, `tools.py:build_sitemap`):
   - Generates `/sitemap.xml` with XML-escaped URLs and lastmod timestamps if `generateSitemap` is enabled.
   - Prunes deleted output files from manifest.
   - Writes manifest atomically via `.tmp` file replacement (**M7**).

---

## Resolved Bug Reference

| ID | Issue | Solution |
|---|---|---|
| **H1** | `TextFile` changes don't invalidate dependent pages / inconsistent traversal | Snapshot text-file timestamps before traversal; compare text file mtimes against snapshot; sync manifest after copy pass. |
| **H2** | `Datetime` pages don't rebuild on subsequent builds | Identify pages containing `Datetime` directly or via components; invalidate them on subsequent builds. |
| **H3** | Component deletion unhandled; empty component dir crash | Set `default=0` on `max()`; store component keys in manifest to detect additions/deletions/edits. |
| **H4** | Manifest persistence ordering | Export manifest after pruning and sitemap build. |
| **H5** | Config path resolution | Resolved paths relative to configuration file location via `_validate_dir_path()`. |
| **H6** | Nested/cyclical directories / `stylus-tmp` conflict deletion | `_get_nested_paths()` verifies no configured directories nest within each other; backup path is validated before cleaning stale staging files. |
| **H7** | Failed backup can delete pre-existing output | `init_backup_state()` initializes backup tracking before component discovery; never delete pre-existing output if backup was not established. |
| **M1** | Auditor misses `<img>` forms or mis-identifies embedded `alt=` | Use `HTMLParser` to inspect actual tag attributes; properly accepts empty/unquoted/boolean `alt` while rejecting `data-note="...alt=..."`. |
| **M2** | HTML auditor case-sensitivity | Parsed attributes and tags are lowercased by `HTMLParser`. |
| **M3** | Unknown component syntax silently untouched | `components_pattern` matches any component syntax; raises `StylusException` on unknown component. |
| **M4** | Cache-bust paths escaping `inputDir` | `resolve_cache_bust_path` verifies `target.is_relative_to(input_dir)`. |
| **M5** | Relative cache-bust `ValueError` | Properly resolve relative paths against output-relative parent directory. |
| **M6** | Sitemap XML escaping | Escaped URLs with `xml.sax.saxutils.escape`. |
| **M7** | Atomic manifest write | Write to `.tmp` file then `os.replace`. |
| **M8** | Configured paths being files | `_validate_dir_path` checks `path.is_dir()`. |
| **N1** | Circular component references / exponential memory exhaustion | DFS cycle detection before recursive expansion in `inject_html()` prevents exponential memory growth. |
| **N2** | Auditor rejects valid unquoted attribute values | `HTMLParser` natively parses unquoted HTML5 attribute values. |
| **N3** | Decreased modification timestamps not detected | Compare mtimes with `!=` instead of `>=` and `>`, catching backward timestamp jumps. |
| **N4** | Component-name generation breaks on Windows | `get_component_name()` uses `Path.relative_to().parts` joined with `.`. |
