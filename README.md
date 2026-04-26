# Stylus
## Travis Heavener

## About
Stylus is a static site generator (SSG) that builds with no additional markup bloat.

## Getting Started
Copy the sample configuration file (config.sample.json) to config.json in the root directory of this repository.

Update the configuration settings as needed.

See [CONFIG.md](CONFIG.md) for documentation.

### Command-Line Arguments

The `src/main.py` script has a few ephemeral controls that are controlled outside of the configuration file:

| Argument | Usage                    | Description                                                   |
|----------|--------------------------|---------------------------------------------------------------|
| -f       | `python3 src/main.py -f` | Copy & rebuild all files instead of those that are unchanged. |
| -v       | `python3 src/main.py -v` | Prints additional debug info to the terminal.                 |
| -c       | `python3 src/main.py -c` | Uses color for printing information to the terminal.          |
| -x       | `python3 src/main.py -x` | Skips minification for all assets.                            |

Note: to use multiple arguments, combine them (ex: `-vcf` will print verbose logs with colored output and force-rebuilds all assets)

## Components

Components are reusable HTML snippets that are dynamically replaced by the SSG at compile-time.

Consider the directory structure below:

| Path                                 | Description                         |
|--------------------------------------|-------------------------------------|
| /components                          | Directory containing all components |
| /components/Header.html              | Reusable header                     |
| /components/Footer.html              | Reusable footer                     |
| /components/Buttons/BookConsult.html | Reusable consultation button        |

Using `<$ Header >` in your HTML will replace itself with the contents of /components/Header.html completely, while matching surrounding indent.
The same goes for /components/Footer.html.

For components in subdirectories, use the notation `<$ Buttons.BookConsult >` for /components/Buttons/BookConsult.html.

## Pseudo-Components

Pseudo-components are dynamic components that resolve to raw text as opposed to a specific HTML component.

### Datetime

The datetime pseudo-component resolves a datetime string using [strftime format codes](https://strftime.org/).

Example:
```
<p>&copy; <$ Datetime:"%b. %Y" ></p>
```

becomes

```
© Apr. 2026
```
