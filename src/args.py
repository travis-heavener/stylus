from argparse import ArgumentParser, Namespace

_args = None

# Creates an argparser
def init_argparser() -> None:
    global _args
    parser = ArgumentParser(
        description="A highly optimized static site generator (SSG) for creating pure HTML websites."
    )

    # Generator args
    parser.add_argument("-a", action="store_true", help="Skips HTML audit on all assets.")
    parser.add_argument("-c", action="store_true", help="Uses color for printing information to the terminal.")
    parser.add_argument("-f", action="store_true", help="Copy & rebuild all files instead of those that are unchanged.")
    parser.add_argument("-q", action="store_true", help="Suppresses additional debug info from terminal.")

    # Config file arg
    parser.add_argument(
        "--config", 
        type=str, 
        default=None, 
        metavar="/path/to/config.json",
        help="Loads the config file at specified path instead of config.json."
    )

    # Extract args
    _args = parser.parse_args()

# Returns a reference to the parser arguments
def get_args() -> Namespace: return _args
