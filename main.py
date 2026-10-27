"""Study Buddy: an always-on agent that quizzes you on your class notes.

How it fits together on Maritime:

  * Maritime keeps this server asleep most of the day (free while asleep).
  * Every night it wakes the agent on the schedule from GET /schedules and
    sends "nightly-quiz" to POST /chat. We pick a topic and text you
    the first question on Telegram.
  * When you reply on Telegram, Telegram forwards the message to
    POST /telegram, which wakes the agent. We grade it and send the next one.
  * Notes, scores and the quiz in progress live on the /data disk (storage.py).

Endpoints Maritime needs: GET /health, POST /chat, GET /schedules.
"""

import hashlib
import os
import threading

from fastapi import FastAPI, Header, HTTPException, Request

import quiz
import storage
import telegram

# Settings are read with os.getenv each time they're used (not once at the top),
# because Maritime hot-reloads env var edits into the running agent.
#   QUIZ_CRON       when the nightly quiz goes out, default 9:00 pm every day
#   QUIZ_TIMEZONE   default America/Los_Angeles
#   TELEGRAM_MODE   "webhook": Telegram pushes replies to us (instant)
#                   "poll": we wake every few minutes in the evening and fetch replies

HELP = """Hi! I'm your study buddy. Every night I'll quiz you on your notes.

/quiz - start a quiz now
/note <text> - save a quick note
/notes - list the topics I know
/stats - see your scores by topic
/stop - end the current quiz
You can also send me a .md or .txt file and I'll add it to your notes."""

app = FastAPI()
lock = threading.Lock()  # handle one message at a time so state.json stays consistent
storage.setup()


# ---------- Maritime's endpoints ----------

@app.get("/health")
def health():
    return {"ok": True}


@app.get("/schedules")
def schedules():
    """Maritime reads this and wakes us up at these times."""
    connect_telegram()  # Maritime calls this often while we're awake
    timezone = os.getenv("QUIZ_TIMEZONE", "America/Los_Angeles")
    jobs = [
        {"id": "nightly-quiz", "cron": os.getenv("QUIZ_CRON", "0 21 * * *"), "tz": timezone,
         "prompt": "nightly-quiz", "enabled": True},
    ]
    if os.getenv("TELEGRAM_MODE", "webhook") == "poll":
        jobs.append({"id": "check-replies", "cron": "*/5 18-23 * * *", "tz": timezone,
                     "prompt": "check-replies", "enabled": True})
    return jobs


@app.post("/chat")
def chat(body: dict):
    """Scheduled wake-ups land here, and so does the Maritime dashboard's Chat tab."""
    message = body.get("message", "").strip()
    connect_telegram()
    with lock:
        if body.get("source") == "scheduled" and message == "nightly-quiz":
            reply = handle_text("/quiz")
            chat_id = storage.load_state().get("chat_id")
            if chat_id:
                telegram.send(chat_id, "Time for tonight's quiz!\n\n" + reply)
            return {"response": reply}
        if body.get("source") == "scheduled" and message == "check-replies":
            return {"response": check_telegram_for_replies()}
        # Anything else is you typing in the dashboard, so it works like Telegram.
        return {"response": handle_text(message)}


# ---------- Telegram ----------

@app.on_event("startup")
def connect_telegram():
    """Point the Telegram bot at our /telegram endpoint, once per setting change.

    Runs on boot and again on every /schedules and /chat request. Maritime
    resumes a sleeping agent instead of rebooting it, so boot alone could miss
    a PUBLIC_URL you add later.
    """
    public_url = os.getenv("PUBLIC_URL", "").rstrip("/")
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if os.getenv("TELEGRAM_MODE", "webhook") != "webhook" or not public_url or not token:
        return

    # A fingerprint of the settings, so we only call Telegram when one changes
    # (and never write the secret itself to disk).
    fingerprint = hashlib.sha256(f"{public_url}|{secret}|{token}".encode()).hexdigest()
    with lock:
        state = storage.load_state()
        if state.get("webhook_fingerprint") == fingerprint:
            return
        try:
            result = telegram.set_webhook(f"{public_url}/telegram", secret)
        except Exception as error:  # never crash over this; we'll retry next request
            print("could not set Telegram webhook:", error)
            return
        print("setWebhook:", result)
        if result.get("ok"):
            state["webhook_fingerprint"] = fingerprint
            storage.save_state(state)


@app.post("/telegram")
async def telegram_webhook(request: Request,
                           x_telegram_bot_api_secret_token: str = Header(default="")):
    # Telegram sends our secret back in this header, so we know it's really Telegram.
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    if secret and x_telegram_bot_api_secret_token != secret:
        raise HTTPException(status_code=403)
    update = await request.json()
    with lock:
        handle_telegram_update(update)
    return {"ok": True}


def check_telegram_for_replies():
    """Poll mode: fetch and handle any messages that arrived since last time."""
    state = storage.load_state()
    updates = telegram.get_updates(state.get("update_offset", 0))
    for update in updates:
        handle_telegram_update(update)
        state = storage.load_state()
        state["update_offset"] = update["update_id"] + 1
        storage.save_state(state)
    return f"handled {len(updates)} message(s)"


def handle_telegram_update(update):
    message = update.get("message") or {}
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    if not chat_id:
        return

    # The first person to send /start becomes the owner. Everyone else is ignored,
    # so strangers who find the bot can't read your notes or use your AI credits.
    state = storage.load_state()
    if "chat_id" not in state and text.startswith("/start"):
        state["chat_id"] = chat_id
        storage.save_state(state)
    if chat_id != state.get("chat_id"):
        telegram.send(chat_id, "Sorry, this is a private study bot.")
        return

    if "document" in message:
        reply = save_sent_file(message["document"])
    else:
        reply = handle_text(text)
    telegram.send(chat_id, reply)


def save_sent_file(document):
    name = document.get("file_name", "notes.md")
    if not name.endswith((".md", ".txt")):
        return "I can only read .md or .txt files for now."
    text = telegram.download_file(document["file_id"]).decode("utf-8", errors="ignore")
    saved_as = storage.save_note(name, text)
    return f"Saved {saved_as}. I'll start quizzing you on it."


# ---------- the study logic ----------

def handle_text(text):
    """Figure out what you meant and return the reply to send back."""
    command = text.split(maxsplit=1)[0].lower() if text else ""
    state = storage.load_state()

    if command in ("/start", "/help", ""):
        return HELP
    if command == "/quiz":
        return start_quiz()
    if command == "/note":
        note = text[len("/note"):].strip()
        if not note:
            return "Usage: /note photosynthesis happens in the chloroplast"
        storage.append_quick_note(note)
        return "Got it, saved to quick_notes.md."
    if command == "/notes":
        return "Your topics:\n" + "\n".join(f"- {n}" for n in storage.list_notes())
    if command == "/stats":
        return stats()
    if command == "/stop":
        state.pop("quiz", None)
        storage.save_state(state)
        return "Quiz stopped. Send /quiz whenever you want another."
    if "quiz" in state:
        return answer_question(text)
    return "No quiz running right now. Send /quiz to start one, or /help."


def start_quiz():
    note = storage.pick_note_for_quiz()
    if note is None:
        return "I don't have any notes yet. Send me a .md file or use /note."
    try:
        questions = quiz.make_questions(storage.read_note(note))
    except Exception as error:
        return f"I couldn't write a quiz just now ({error}). Try /quiz again in a minute."

    state = storage.load_state()
    state["quiz"] = {"note": note, "questions": questions, "index": 0, "correct": 0}
    storage.save_state(state)
    return f"Topic: {note}\n\nQ1: {questions[0]['question']}"


def answer_question(answer):
    state = storage.load_state()
    current = state["quiz"]
    question = current["questions"][current["index"]]

    try:
        result = quiz.grade(question["question"], question["answer"], answer)
    except Exception as error:
        return f"I couldn't grade that just now ({error}). Send your answer again."

    if result.get("correct"):
        current["correct"] += 1
        reply = f"Correct! {result.get('feedback', '')}"
    else:
        reply = f"Not quite. {result.get('feedback', '')}\nAnswer: {question['answer']}"

    current["index"] += 1
    total = len(current["questions"])
    if current["index"] < total:
        next_q = current["questions"][current["index"]]["question"]
        reply += f"\n\nQ{current['index'] + 1}: {next_q}"
    else:
        storage.log_quiz(current["note"], current["correct"], total)
        reply += f"\n\nDone! You got {current['correct']}/{total} on {current['note']}."
        del state["quiz"]

    storage.save_state(state)
    return reply


def stats():
    scores = storage.scores_by_note()
    if not scores:
        return "No quizzes finished yet. Send /quiz to take your first one."
    lines = [f"- {note}: {round(score * 100)}%" for note, score in sorted(scores.items())]
    return "Your average scores:\n" + "\n".join(lines)
