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

| Argument | Usage                          | Description                                                   |
|----------|--------------------------------|---------------------------------------------------------------|
| -f       | `python3 generator/main.py -f` | Copy & rebuild all files instead of those that are unchanged. |
| -v       | `python3 generator/main.py -v` | Prints additional debug info to the terminal.                 |
| -c       | `python3 generator/main.py -c` | Uses color for printing information to the terminal.          |
| -x       | `python3 generator/main.py -x` | Skips minification for all assets.                            |

Note: to use multiple arguments, combine them (ex: `-vcf` will print verbose logs with colored output and force-rebuilds all assets)
