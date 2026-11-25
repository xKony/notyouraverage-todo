"""Module entrypoint allowing `python -m nyatodo` execution."""

from nyatodo.app import main

if __name__ == "__main__":
    raise SystemExit(main())
