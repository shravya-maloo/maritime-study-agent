# Deploying Study Buddy to Maritime, step by step

This takes about 30 minutes. Everything here is free and no step asks for a
credit card. **Never paste a key into a chat, an email, or the code.** Keys go
only into Maritime's Environment settings.

## 1. Make the Telegram bot (5 min)

1. Install Telegram on your phone or computer and sign in.
2. Search for **@BotFather** (it has a blue check mark) and open a chat.
3. Send `/newbot`. Give it a name (e.g. `Shravya's Study Buddy`) and a
   username that ends in `bot` (e.g. `shravya_study_buddy_bot`).
4. BotFather replies with a **token** that looks like `123456789:AAH...`.
   Keep that message private, since anyone with the token controls your bot.
   You'll paste it into Maritime in step 4.

## 2. Get an AI key (5 min)

First, check whether Maritime gives you AI credits on the Free plan (step 4
will show you). If it doesn't, get a free Groq key:

1. Go to <https://console.groq.com> and sign up (Google sign-in works).
2. Click **API Keys** → **Create API Key**. Copy it (starts with `gsk_`)
   somewhere private. Groq only shows it once.

## 3. Put the code on GitHub (5 min)

1. On GitHub, click **New repository**. Name it `study-buddy`. Public is fine
   (there are no secrets in the code). Don't add a README; this project has one.
2. Upload these files: on the empty repo page click **uploading an existing
   file**, drag in everything in this folder **except** `.venv/` and `data/`,
   and click **Commit changes**. (Or use `git push` if you're comfortable.)
3. Optional: replace the files in `sample_notes/` with your own notes first.
   You can also send notes to the bot later.

## 4. Deploy on Maritime (10 min)

1. Sign up at <https://maritime.sh> and stay on the **Free** plan. Skip any
   promo code or checkout page.
2. Create a new agent **from GitHub**, pick your `study-buddy` repo and the
   `main` branch. If it asks for a framework, choose custom / "bring your own".
3. Open the agent's **Environment** settings and add the following. Mark the
   first three as **secret**:

   | Name | Value |
   |---|---|
   | `TELEGRAM_BOT_TOKEN` | the token from BotFather |
   | `TELEGRAM_WEBHOOK_SECRET` | make one up, like `purple-walrus-quiz-4821` |
   | `LLM_API_KEY` | your Groq key (skip if Maritime already lists `OPENAI_API_KEY`) |
   | `LLM_BASE_URL` | `https://api.groq.com/openai/v1` (Groq only) |
   | `LLM_MODEL` | `llama-3.3-70b-versatile` (Groq only) |

4. Wait for the first build to finish (a few minutes). Then copy the agent's
   **HTTPS URL** from the dashboard and add it as one more variable:
   `PUBLIC_URL` = that URL. Restart the agent. On boot it tells Telegram to
   send your messages to `PUBLIC_URL/telegram`.

## 5. Say hi (2 min)

1. In Telegram, open your bot and send `/start`. This makes you its owner,
   so nobody else can use it.
2. Send `/quiz`. You should get Question 1 within a few seconds. Answer it!
3. You can also type `/quiz` in the Maritime dashboard's **Chat** tab.

## 6. Check the nightly quiz

To test without waiting until 9 pm, set `QUIZ_CRON` to a few minutes from
now. For example, `40 22 * * *` means 10:40 pm Seattle time. Restart, wait,
and the quiz should arrive on Telegram. Then delete `QUIZ_CRON` to go back to 9 pm.

## If something doesn't work

- **The bot doesn't answer on Telegram.** Open this in your own browser (it
  has your token in it, so don't share the link):
  `https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo`.
  If `url` is empty, `PUBLIC_URL` isn't set or the agent didn't restart. If
  `last_error_message` shows an error, Maritime may not be forwarding the
  `/telegram` path. In that case add `TELEGRAM_MODE` = `poll`, open
  `https://api.telegram.org/bot<YOUR_TOKEN>/deleteWebhook` once, and restart.
  The bot will then answer within 5 minutes between 6 pm and midnight.
- **"I couldn't write a quiz just now..."** The error after it names the
  problem, usually a wrong `LLM_API_KEY`, `LLM_BASE_URL` or `LLM_MODEL`.
- **Anything else:** check the agent's **Logs** tab in Maritime.
