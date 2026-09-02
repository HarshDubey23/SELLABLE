"""CLI entry point for the external buyer.

    python -m external_buyer.run --base http://127.0.0.1:8000 \
        --mission missions/happy_path.json
"""
from __future__ import annotations

import sys

from external_buyer.buyer import main

if __name__ == "__main__":
    sys.exit(main())
