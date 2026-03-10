"""
Create a blank Chess Karma SQLite database with the schema applied but no data.

Run from the repository root:
    python tools/create_blank_db.py

Output: chess_karma_blank.db  (in the repository root, next to main.py)
The file is included in the PyInstaller bundle and copied to the user's home
directory on first launch (only if ~/chess_karma.db does not already exist).
"""

import pathlib
import sqlite3
import sys

# Allow importing from the package without installing it
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from chess_karma.core.database import _DDL  # noqa: E402

OUTPUT = pathlib.Path(__file__).parent.parent / "chess_karma_blank.db"


def main() -> None:
    if OUTPUT.exists():
        OUTPUT.unlink()

    con = sqlite3.connect(OUTPUT)
    try:
        con.executescript(_DDL)
        con.commit()
    finally:
        con.close()

    print(f"Created: {OUTPUT}")


if __name__ == "__main__":
    main()
