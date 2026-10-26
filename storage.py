"""Everything the agent remembers lives in one folder, DATA_DIR.

On Maritime that folder is /data, the persistent disk. It survives sleep,
restarts and redeploys, so the agent never forgets your notes or scores.

    /data/notes/*.md      your class notes, one file per topic
    /data/state.json      whose chat to message + the quiz in progress
    /data/history.jsonl   one line per finished quiz (used by /stats)
"""

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
NOTES_DIR = DATA_DIR / "notes"
STATE_FILE = DATA_DIR / "state.json"
HISTORY_FILE = DATA_DIR / "history.jsonl"

# Notes that ship with the code, copied to the disk the first time it boots.
STARTER_NOTES = Path(__file__).parent / "sample_notes"


def setup():
    """Create the folders, and seed the notes folder if it's empty."""
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    if not list_notes() and STARTER_NOTES.exists():
        for note in STARTER_NOTES.glob("*.md"):
            shutil.copy(note, NOTES_DIR / note.name)


# ---------- notes ----------

def list_notes():
    return sorted(p.name for p in NOTES_DIR.glob("*") if p.suffix in (".md", ".txt"))


def read_note(name):
    return (NOTES_DIR / name).read_text(encoding="utf-8")


def save_note(name, text):
    """Save a whole file of notes, e.g. one you sent the bot on Telegram."""
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", Path(name).stem).strip("_") or "notes"
    path = NOTES_DIR / f"{stem}.md"
    path.write_text(text, encoding="utf-8")
    return path.name


def append_quick_note(text):
    """Add a one-line note (from /note ...) to quick_notes.md."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(NOTES_DIR / "quick_notes.md", "a", encoding="utf-8") as f:
        f.write(f"- ({today}) {text}\n")


# ---------- state (small JSON file) ----------

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state):
    # Write to a temp file and then rename, so a crash mid-write can't
    # leave a half-written state.json behind.
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)


# ---------- quiz history ----------

def log_quiz(note, correct, total):
    row = {
        "time": datetime.now(timezone.utc).isoformat(),
        "note": note,
        "correct": correct,
        "total": total,
    }
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(row) + "\n")


def scores_by_note():
    """Average score (0.0 to 1.0) for every note that's been quizzed."""
    if not HISTORY_FILE.exists():
        return {}
    totals = {}
    for line in HISTORY_FILE.read_text().splitlines():
        row = json.loads(line)
        right, asked = totals.get(row["note"], (0, 0))
        totals[row["note"]] = (right + row["correct"], asked + row["total"])
    return {note: right / asked for note, (right, asked) in totals.items() if asked}


def pick_note_for_quiz():
    """Quiz a topic you've never been quizzed on, else your weakest one."""
    notes = list_notes()
    if not notes:
        return None
    scores = scores_by_note()
    never_quizzed = [n for n in notes if n not in scores]
    if never_quizzed:
        return never_quizzed[0]
    return min(notes, key=lambda n: scores[n])
