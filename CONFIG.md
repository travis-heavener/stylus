# CONFIG.md

## About

This document describes each setting available in `config.json` and how it affects the build process.

### inputDir: string

Defines the directory containing your source files.

This is where you place and edit your HTML, CSS, JavaScript, and other static assets before they are processed.

### outputDir: string

Defines the directory where compiled files are written.

This is the directory your HTTP server should serve.

### componentsDir: string

Defines the directory containing reusable components used during compilation.

It is recommended to place this outside of `inputDir` to prevent component files from appearing in the final build output.

### textFilesDir: string

Defines the reference directory containing files for TextFile pseudo-components.
While you are able to use absolute paths, you may use relative paths which resolve to this directory instead.

It is recommended to place this outside of `inputDir` to prevent extra text files from appearing in the final build output.

### buildExtensions: array[string]

Specifies a list of file extensions to run through the compiler and HTML auditor.

Example:

```json
"buildExtensions": [".html", ".htm"]
```

### sitemapExtensions: array[string]

Specifies a list of file extensions to run through the sitemap generator.

Example:

```json
"sitemapExtensions": [".html", ".htm"]
```

### indexFiles: array[string]

Specifies a list of special file paths to treat as index files (e.g. "index.html", "index.php").

This only applies to the sitemap generator and canonical URL validation.

Example:

```json
"indexFiles": ["index.html", "index.htm", "index.php"]
```

### generateSitemap: boolean

Controls whether a `/sitemap.xml` file is generated in the root of outputDir.

### truncateSitemapIndexFiles: boolean

Determines whether index.html is removed from URLs in the generated sitemap.

Examples:

- `false`: `http://localhost/index.html`
- `true`: `http://localhost/`

### sitemapIgnore: array[string]

Specifies a list of HTML file paths to exclude from sitemap generation.

Only applies when `generateSitemap` is enabled.

Example:

```json
"sitemapIgnore": ["/404.html", "/dashboard/index.html"]
```

### baseAddress: string

Specifies the base URL (FQDN) used for:
- Generating the sitemap
- Validating canonical link tags

Example:

```json
"baseAddress": "http://localhost/"
```

### canonicalIgnore: array[string]

Specifies a list of HTML file paths to exclude from canonical tag validation.

Useful for pages that should not appear in search results (e.g., error pages or private sections).

Example:

```json
"canonicalIgnore": ["/404.html", "/dashboard/index.html"]
```

### htmlLang: string

Specifies the expected language value for the `<html lang="...">` attribute.

Ensuring this attribute is set correctly improves accessibility and SEO.
