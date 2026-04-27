from sys import argv
from typing import Any

# Check if an argument is set
def isarg(c: str) -> bool:
    if len(argv) <= 1: return False
    return argv[1][0] == "-" and c in argv[1]

# Prints all arguments to console with a debug message,
#   IF the -v flag is set (for verbose logging)
def vlog(*args: list[Any]) -> None:
    if isarg("v"):
        log(*args)

# Prints all arguments to console with a debug message
def log(*args: list[Any]) -> None:
    if isarg("c"): # Colored ANSI output
        print("\033[96m\033[1m[INFO]\033[0m", *args)
    else:
        print("[INFO]", *args)

# Prints all arguments to console with a warning message
def warn(*args: list[Any]) -> None:
    if isarg("c"): # Colored ANSI output
        print("\033[93m\033[1m[WARN]\033[0m", *args)
    else:
        print("[WARN]", *args)

# Prints all arguments to console with an error message
def err(*args: list[Any]) -> None:
    if isarg("c"): # Colored ANSI output
        print("\033[91m\033[1m[ERROR]\033[0m", *args)
    else:
        print("[ERROR]", *args)