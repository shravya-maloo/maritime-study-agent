# Study Buddy

An always-on AI study agent. It keeps my class notes on a persistent disk and
quizzes me on them over Telegram every night, focusing on the topics I'm
weakest at. It runs on [Maritime](https://maritime.sh), which hosts AI agents
that sleep when idle and wake up in about a second with their files intact.

It grew out of a quiz tool I built at Quadrant Technologies with Azure OpenAI,
which turned documents into quizzes. That version needed someone to open it
and click a button. This one comes to me.

## What it does

- **9 pm every night**, it texts me a 3-question quiz on Telegram.
- **I reply in Telegram**, and it grades each answer (it accepts the right idea
  in my own words), explains what I missed, and sends the next question.
- **It picks the topic:** a note I've never been quizzed on first, otherwise
  the one with my lowest average score.
- **Adding notes:** send the bot a `.md` or `.txt` file, or `/note <text>`.
- **Commands:** `/quiz`, `/note`, `/notes`, `/stats`, `/stop`, `/help`.

## How it works

```
 Maritime scheduler ──(9pm: "nightly-quiz")──▶ POST /chat ──┐
                                                            ▼
 You on Telegram ◀──── sendMessage ────────────── Study Buddy (FastAPI)
        │                                         │        │
        └── reply ──▶ Telegram ──▶ POST /telegram ┘        ▼
                                                   /data disk: notes,
                                                   quiz state, scores
```

| File | What's in it |
|---|---|
| `main.py` | The web server: Maritime's endpoints, Telegram handling, quiz flow |
| `quiz.py` | The two AI calls: write questions from notes, grade an answer |
| `storage.py` | Reading and writing notes, state and scores on the `/data` disk |
| `telegram.py` | Four small Telegram Bot API calls |
| `start.py` | Starts the server on the port Maritime gives it |
| `Dockerfile` | How Maritime builds the container |
| `sample_notes/` | Starter notes, copied to the disk on first boot |

### Design decisions (good to explain on a call)

- **Why the `/data` disk?** Maritime agents sleep when idle. Anything outside
  `/data` can disappear on a restart or redeploy, so notes, the quiz in
  progress and score history all live there. That's what lets a quiz span
  several messages and lets the bot remember my weak topics across weeks.
- **Why `/schedules` instead of a timer?** A sleeping agent's timers don't
  run. Maritime reads `GET /schedules`, wakes the agent just before 9 pm and
  sends the prompt to `/chat`. The agent costs nothing while it sleeps.
- **Why a Telegram webhook?** Telegram pushes each reply to `/telegram`, which
  wakes the agent, so it doesn't need to stay awake polling. There's also a
  fallback `TELEGRAM_MODE=poll` that checks for replies every 5 minutes in
  the evening.
- **Security:** keys live in Maritime's environment settings, never in the
  code. Only the first Telegram account that sends `/start` can use the bot,
  and `/telegram` rejects requests that don't carry the secret header
  Telegram sends.
- **Any AI provider:** `quiz.py` uses the OpenAI SDK, so it works with OpenAI,
  Maritime's built-in credits, or a free Groq key. Only env vars change.

## Settings (environment variables)

| Name | Required | What it is |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | From @BotFather. Mark it secret. |
| `TELEGRAM_WEBHOOK_SECRET` | yes | Any long random string you make up. Mark it secret. |
| `PUBLIC_URL` | yes | The agent's HTTPS address from the Maritime dashboard |
| `LLM_API_KEY` | yes* | AI key. *Not needed if Maritime provides `OPENAI_API_KEY`. |
| `LLM_BASE_URL` | for Groq | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | no | Default `gpt-4o-mini`; use `llama-3.3-70b-versatile` for Groq |
| `QUIZ_CRON` | no | Default `0 21 * * *` (9:00 pm) |
| `QUIZ_TIMEZONE` | no | Default `America/Los_Angeles` |
| `TELEGRAM_MODE` | no | `webhook` (default) or `poll` |

## Run it on your laptop

You can try the quiz flow without Telegram, using the `/chat` endpoint:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATA_DIR=./data LLM_API_KEY=your-key   # plus LLM_BASE_URL/LLM_MODEL for Groq
python start.py
# in a second terminal:
curl -s localhost:8080/chat -H 'Content-Type: application/json' -d '{"message": "/quiz"}'
curl -s localhost:8080/chat -H 'Content-Type: application/json' -d '{"message": "my answer"}'
```

To deploy it, see [DEPLOY.md](DEPLOY.md).
