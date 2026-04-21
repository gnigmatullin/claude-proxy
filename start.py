"""
start.py — reads master password from /dev/tty and starts uvicorn.
Used by systemd to allow interactive password entry.
"""
import os
import sys


def main():
    # Read password directly from terminal (works even when stdin is redirected)
    try:
        with open("/dev/tty", "r") as tty:
            tty.write("Master password: ")
            tty.flush()
            password = tty.readline().rstrip("\n")
    except Exception as e:
        print(f"ERROR: Cannot read password from /dev/tty: {e}", file=sys.stderr)
        sys.exit(1)

    # Pass password via environment variable to the app
    os.environ["MASTER_PASSWORD"] = password

    # Start uvicorn programmatically
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")))


if __name__ == "__main__":
    main()