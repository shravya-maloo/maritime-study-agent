"""Entrypoint. Maritime tells us which port to listen on through $PORT.

We start the server from Python (not a shell command) because Maritime's
docs warn that shell-string commands break when its VMs boot.
"""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
