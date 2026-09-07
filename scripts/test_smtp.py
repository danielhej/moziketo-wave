#!/usr/bin/env python3
"""Send a test email via wave SMTP (Postfix relay).

Usage: python scripts/test_smtp.py to@example.com
"""

import asyncio
import sys

from app.services.email import send_email


async def main() -> None:
    recipient = sys.argv[1] if len(sys.argv) > 1 else "hajidanial8@gmail.com"
    ok = await send_email(
        to=recipient,
        subject="Moziketo Wave SMTP test",
        body="If you received this, Postfix relay + wave email config work.",
    )
    print("sent" if ok else "skipped_or_failed")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
