# mergeguard.__main__
# Runs the package entrypoint when invoked as a module.

from .cli import app

if __name__ == "__main__":
    app()
