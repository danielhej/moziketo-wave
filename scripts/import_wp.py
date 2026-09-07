#!/usr/bin/env python3
"""CLI wrapper for WP import."""

import asyncio

from app.services.import_wp import main

if __name__ == "__main__":
    asyncio.run(main())
