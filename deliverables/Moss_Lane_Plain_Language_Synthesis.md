# Moss Lane Project: Plain-Language Synthesis

**What this document is:** A complete guide to understanding the Moss Lane project and its code, written for someone who doesn't code. Every technical term is explained. Every code pattern is broken down into what it actually does and why.

**Last updated:** March 31, 2026

---

## Research Overview

- **What was reviewed:** The entire Moss Lane codebase (~1,800 lines of Python), 40+ documentation files, deployment scripts, brand materials, trade logs, and career documents
- **Purpose:** Make the project understandable to anyone, regardless of coding background, so they could confidently read the code, understand decisions, and even make basic edits
- **Author context:** Josh Hillard built this from zero coding experience, using systems thinking from 6 years of technical leadership at Toast (FinTech)

---

## Part 1: What Is This Project?

### The One-Sentence Version

Moss Lane is a robot that watches the Solana cryptocurrency market 24/7, decides which new coins look promising, buys them automatically, watches the price, and sells them — all without human intervention.

### The Full Picture

| Term | What It Means |
|------|--------------|
| **Moss Lane** | The project's name. Named after Manchester City's old football ground — a nod to humble beginnings. |
| **Lazarus** | The name of the trading engine (the actual code that runs). Named after the biblical figure who rose from the dead — the theme is "rising from nothing." |
| **Solana** | A blockchain (think: a public digital ledger) that processes transactions very fast (~400 milliseconds). That speed matters when trading volatile coins. |
| **Memecoin** | A cryptocurrency token that's usually brand new, often joke-themed (like Dogecoin), and extremely volatile. Prices can spike 100% or crash 90% in minutes. |
| **Paper trading** | Practice mode. The bot pretends to buy and sell with fake money to test whether its strategy works before risking real funds. |

### The Goal

Start with **$103 worth of SOL** (Solana's native currency) and grow it to **$20,000** through automated trading. But equally important: Josh is using this project to learn Python, databases, servers, and APIs — and to prove he can build production-grade software as a career pivot.

---

## Part 2: How the Bot Works (The Big Picture)

The bot runs in a continuous loop, repeating three phases:

```
SCAN → DECIDE → MONITOR
  ↑                    |
  └────────────────────┘  (repeats forever)
```

### Phase 1: SCAN (Finding Candidates)

Every 30 seconds, the bot asks a public website called **DexScreener** "What coins are moving right now?" It searches 16 different queries to cast a wide net.

### Phase 2: DECIDE (The 9-Point Filter)

This is where the bot is most strict. **Every coin starts as rejected.** It must pass ALL 9 checks to get bought. If it fails even one, it's skipped. This is called **"fail-closed"** — the door is locked by default and only opens if every key fits.

The 9 filters (in order):

| # | Filter | What It Checks | Why It Matters |
|---|--------|---------------|----------------|
| 1 | **Blacklist** | Is this coin on the "never touch" list? | Coins that previously caused losses get permanently blocked |
| 2 | **Market Cap** | Is the coin's total value between $10K and $10M? | Too small = probably a scam. Too big = not enough room to grow |
| 3 | **Liquidity** | Is there at least $50K available to trade? | Low liquidity = you can't sell when you need to |
| 4 | **1-Hour Momentum** | Has the price risen 10-80% in the last hour? | Below 10% = not enough energy. Above 80% = you're probably too late |
| 5 | **5-Minute Momentum** | Is the price still going up right now (>0.5%)? | Confirms the move is still active, not already fading |
| 6 | **Volume/Market Cap** | Is trading volume at least 10% of total value? | High volume relative to size = real interest, not just one person |
| 7 | **Pair Age** | Has this coin existed for more than 60 minutes? | Brand-new coins are overwhelmingly scams (called "rugs") |
| 8 | **Cooldown** | Has the bot already traded this coin recently? | Prevents buying the same coin over and over during a pump |
| 9 | **Not Held** | Is the bot already holding this coin? | Can't buy what you already own |

### Phase 3: MONITOR (Watching Positions)

Once the bot buys a coin, it checks the price **every 3 seconds** and follows a strict 7-step priority list for when to sell. The list is checked in order — whichever rule triggers first, wins:

| Priority | Rule Name | What It Does | Plain English |
|----------|-----------|-------------|---------------|
| **Tier 1** | Hard Floor | Sell if down 15% | "Absolute emergency eject. No matter what, we're out." |
| **Tier 2** | Emergency Rug | Sell if down 12% in 30 seconds | "The price just fell off a cliff — this is a scam, get out NOW." |
| **Tier 3** | Take Profit | Sell if up 25% | "We hit our target. Lock in the win." |
| **Tier 4** | Trailing Stop | After +8%, trail by 4% | "Price is running. Let it ride, but if it drops 4% from the peak, sell." |
| **Tier 5** | Sniper Timeout | Sell if <1% gain after 60 seconds | "This coin isn't going anywhere. Cut it and find the next one." |
| **Tier 6** | Stop Loss | Sell if down 8% | "Normal loss limit. Take the small hit, move on." |
| **Tier 7** | Timeout | Sell after 10-15 minutes | "Time's up. Memecoins move fast — if nothing happened, it won't." |

---

## Part 3: Key Code Explained Line by Line

This section takes real code from the project and explains each piece so you could read it confidently.

### 3.1 The Configuration Dictionary (CFG)

**What it is:** A settings file built into the code. Think of it as the bot's instruction manual — all the numbers it uses to make decisions.

```python
CFG = {
    "position_pct": 0.15,
    "take_profit": 0.25,
    "stop_loss": -0.08,
    "hard_floor": -0.15,
    "trail_arm": 0.08,
    "trail_pct": 0.04,
    "sniper_timeout_sec": 60,
}
```

**Line-by-line:**

| Code | What It Means | In Real Terms |
|------|--------------|---------------|
| `"position_pct": 0.15` | Use 15% of your wallet per trade | If you have $1,000, bet $150 each time |
| `"take_profit": 0.25` | Sell when the price goes up 25% | Bought at $1.00? Sell at $1.25 |
| `"stop_loss": -0.08` | Sell when the price drops 8% | Bought at $1.00? Sell at $0.92 to limit damage |
| `"hard_floor": -0.15` | Absolute maximum loss: 15% | No matter what, never lose more than 15% on one trade |
| `"trail_arm": 0.08` | Trailing stop activates after 8% gain | Once you're up 8%, start protecting profits |
| `"trail_pct": 0.04` | Trail by 4% from the highest price seen | If price hits $1.50, sell if it drops below $1.44 |
| `"sniper_timeout_sec": 60` | If less than 1% gain after 60 seconds, sell | Quick kill on trades that aren't working |

**Key concept — `0.15` means 15%:** In code, percentages are written as decimals. 1.0 = 100%, 0.25 = 25%, 0.08 = 8%. So when you see `0.15`, read it as "fifteen percent."

### 3.2 The curl_get() Function

**What it is:** A custom-built way to fetch data from websites. The bot needs to ask external services "what's the price of this coin?" — this is how it asks.

```python
def curl_get(url, headers=None, timeout=10):
    cmd = ["curl", "-s", "-m", str(timeout)]
    if headers:
        for k, v in headers.items():
            cmd += ["-H", f"{k}: {v}"]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+5)
    return json.loads(result.stdout)
```

**Line-by-line:**

| Code | What It Does |
|------|-------------|
| `def curl_get(url, headers=None, timeout=10):` | **Defines a reusable command** called `curl_get`. It takes a web address (`url`), optional identification headers, and a time limit (default 10 seconds). |
| `cmd = ["curl", "-s", "-m", str(timeout)]` | **Builds a command** to run `curl` (a standard tool for fetching web pages). `-s` = silent mode (no progress bars). `-m` = max time allowed. |
| `for k, v in headers.items():` | **Loops through any headers** (identification info some websites require, like API keys). |
| `cmd += ["-H", f"{k}: {v}"]` | **Adds each header** to the command in the format websites expect. |
| `cmd.append(url)` | **Adds the web address** to the end of the command. |
| `subprocess.run(cmd, ...)` | **Runs the command** as if you typed it in a terminal window. `capture_output=True` means "save the response so I can read it." |
| `json.loads(result.stdout)` | **Converts the response** from raw text into structured data Python can work with. |

**Why not use the "normal" Python way?** The standard Python library for web requests (`aiohttp`) silently fails on certain external APIs — it says it worked but returns nothing. Josh discovered this bug and built this workaround. It's not pretty, but it's reliable. This is documented as a critical rule in the project: "Never use aiohttp for external APIs."

### 3.3 The EnvLoader Class

**What it is:** A custom tool for reading secret configuration (passwords, API keys) from a file.

```python
class EnvLoader:
    def __init__(self, path=".env"):
        self.vars = {}
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, _, val = line.partition("=")
                val = val.strip().strip('"').strip("'")
                self.vars[key.strip()] = val
```

**Line-by-line:**

| Code | What It Does |
|------|-------------|
| `class EnvLoader:` | **Creates a blueprint** called `EnvLoader` for reading environment files. |
| `def __init__(self, path=".env"):` | **When created**, it looks for a file named `.env` by default. |
| `self.vars = {}` | **Starts with an empty dictionary** (a lookup table) to store settings. |
| `with open(path) as f:` | **Opens the file** safely (auto-closes when done). |
| `for line in f:` | **Reads each line** one at a time. |
| `line = line.strip()` | **Removes extra spaces** from the beginning and end. |
| `if not line or line.startswith("#"):` | **Skips blank lines and comments** (lines starting with `#` are notes, not settings). |
| `key, _, val = line.partition("=")` | **Splits the line** at the first `=` sign. Left side = setting name, right side = setting value. |
| `val = val.strip().strip('"').strip("'")` | **Cleans up the value** by removing spaces and quotation marks. |
| `self.vars[key.strip()] = val` | **Stores the setting** in the lookup table. |

**Why build a custom one?** The standard Python library for this (`python-dotenv`) breaks when values have certain types of quotation marks. Josh hit this bug on the server and it caused the bot to crash on startup. This custom version handles all quote styles correctly.

### 3.4 The Main Trading Loop

**What it is:** The heartbeat of the bot. This is what runs 24/7.

```python
async def run(self):
    while True:
        try:
            signals = await self.scan_signals()
            for sig in signals:
                if self.can_trade(sig):
                    await self.execute_entry(sig)
            await asyncio.sleep(30)
        except Exception as e:
            logging.error(f"Main loop error: {e}")
            await asyncio.sleep(60)
```

**Line-by-line:**

| Code | What It Does |
|------|-------------|
| `async def run(self):` | **Defines the main loop.** `async` means it can do multiple things at once (like watching prices while scanning for new coins). |
| `while True:` | **Run forever.** This loop never stops on its own — it's designed to run 24/7. |
| `try:` | **"Try to do this, and if something breaks, handle it gracefully instead of crashing."** |
| `signals = await self.scan_signals()` | **Ask DexScreener for coins that are moving.** `await` means "wait for the answer before continuing." |
| `for sig in signals:` | **Look at each coin** that came back from the scan. |
| `if self.can_trade(sig):` | **Run the 9-point filter.** Only proceeds if the coin passes every check. |
| `await self.execute_entry(sig)` | **Buy the coin** through Jupiter (the trading service). |
| `await asyncio.sleep(30)` | **Wait 30 seconds** before scanning again. |
| `except Exception as e:` | **If anything goes wrong**, catch the error instead of crashing. |
| `logging.error(...)` | **Write the error** to a log file so Josh can investigate later. |
| `await asyncio.sleep(60)` | **After an error, wait 60 seconds** (longer pause) before trying again. |

### 3.5 The 7-Tier Exit Check

**What it is:** The decision tree for when to sell. Runs every 3 seconds for every coin the bot is holding.

```python
async def check_exits(self, position):
    price = await self.get_price(position.token)
    pnl_pct = (price - position.entry_price) / position.entry_price
    elapsed = time.time() - position.entry_time

    # Tier 1: Hard Floor
    if pnl_pct <= self.cfg["hard_floor"]:
        return "hard_floor"

    # Tier 2: Emergency Rug Detection
    if position.price_30s_ago and (price - position.price_30s_ago) / position.price_30s_ago <= -0.12:
        return "emergency_rug"

    # Tier 3: Take Profit
    if pnl_pct >= self.cfg["take_profit"]:
        return "take_profit"

    # Tier 4: Trailing Stop
    if position.trail_armed and pnl_pct <= position.peak_pnl - self.cfg["trail_pct"]:
        return "trailing_stop"

    # ... continues through Tiers 5, 6, 7
```

**Line-by-line:**

| Code | What It Does |
|------|-------------|
| `price = await self.get_price(position.token)` | **Get the current price** from Birdeye (price service). |
| `pnl_pct = (price - position.entry_price) / position.entry_price` | **Calculate profit/loss as a percentage.** If you bought at $1.00 and it's now $1.25, that's `(1.25 - 1.00) / 1.00 = 0.25` = 25% gain. |
| `elapsed = time.time() - position.entry_time` | **How long have we held this coin?** Current time minus the time we bought it, in seconds. |
| `if pnl_pct <= self.cfg["hard_floor"]:` | **Tier 1: If we're down 15% or more, SELL.** No questions asked. |
| `return "hard_floor"` | **Report why we sold** — this gets logged to the database. |
| `if ... <= -0.12:` | **Tier 2: If the price dropped 12% in the last 30 seconds** — this is a "rug pull" (scam crash). |
| `if pnl_pct >= self.cfg["take_profit"]:` | **Tier 3: If we're up 25%, SELL.** Lock in the win. |
| `if position.trail_armed and ...` | **Tier 4: If trailing stop is active** (because we hit +8%) **and the price dropped 4% from its peak**, sell. |

**Key concept — `return` stops the function:** When any tier triggers and returns a reason, all lower tiers are skipped. That's why order matters — hard floor (the emergency brake) is checked first.

### 3.6 The Learning Engine

**What it is:** After every trade, the bot analyzes its recent history and adjusts its bet size.

```python
def adjust_position_size(self):
    recent = self.get_recent_trades(window=20)
    wins = [t for t in recent if t["pnl"] > 0]
    win_rate = len(wins) / len(recent) if recent else 0

    if win_rate >= 0.45:
        new_pct = min(self.cfg["position_pct"] * 1.05, 0.25)
    elif win_rate <= 0.30:
        new_pct = max(self.cfg["position_pct"] * 0.95, 0.10)
    else:
        new_pct = self.cfg["position_pct"]

    self.update_config("position_pct", new_pct)
```

**Line-by-line:**

| Code | What It Does |
|------|-------------|
| `recent = self.get_recent_trades(window=20)` | **Get the last 20 trades** from the database. |
| `wins = [t for t in recent if t["pnl"] > 0]` | **Count the winners** — trades where profit/loss was positive. |
| `win_rate = len(wins) / len(recent)` | **Calculate win rate.** 9 wins out of 20 trades = 45%. |
| `if win_rate >= 0.45:` | **If winning 45% or more of the time...** |
| `new_pct = min(...* 1.05, 0.25)` | **Increase bet size by 5%, but never above 25%.** `min()` means "take the smaller of these two numbers" — it's a safety cap. |
| `elif win_rate <= 0.30:` | **If winning 30% or less...** |
| `new_pct = max(...* 0.95, 0.10)` | **Decrease bet size by 5%, but never below 10%.** `max()` means "take the larger" — it's a safety floor. |
| `self.update_config("position_pct", new_pct)` | **Save the new setting** to the database (Layer 3 config). |

**Why this matters:** The bot learns from its own performance. On a hot streak? It bets a little more. On a cold streak? It bets less. But it can never go below 10% or above 25% — the guardrails prevent it from getting reckless or too timid.

---

## Part 4: Key Phrases — Glossary

| Term | Definition |
|------|-----------|
| **API (Application Programming Interface)** | A way for two programs to talk to each other. When the bot asks DexScreener for prices, it's using DexScreener's API — like ordering from a menu at a restaurant instead of going into the kitchen. |
| **async / await** | Python's way of doing multiple things at once without multiple programs. `await` means "start this task, and while we're waiting for the answer, go do something else." Like texting someone and doing dishes while you wait for their reply. |
| **Blacklist** | A permanent "do not touch" list. If a coin caused a big loss (>15%), it gets added automatically and the bot will never buy it again. |
| **Blockchain** | A public digital ledger. Every transaction is recorded permanently and can be verified by anyone. Solana is one specific blockchain. |
| **CFG (Configuration)** | The bot's settings — all the numbers that control its behavior (how much to bet, when to sell, etc.). |
| **Cooldown** | A waiting period. After trading a coin, the bot waits 2 hours before trading it again. Prevents chasing the same coin repeatedly. |
| **curl** | A command-line tool for fetching data from websites. Like a web browser, but with no visual interface — just raw data in, data out. |
| **Database (SQLite)** | A file that stores structured data — every trade, every price check, every configuration change. SQLite is a database that lives in a single file (no server needed). |
| **DEX (Decentralized Exchange)** | A trading platform with no central company running it. Jupiter is a DEX on Solana — trades happen directly between wallets on the blockchain. |
| **Dictionary (dict / {})** | A Python data structure that stores key-value pairs. Like a real dictionary: look up "take_profit" and get back `0.25`. Written with curly braces `{}`. |
| **Fail-Closed** | A safety philosophy. The default answer is "NO." Something must explicitly prove it's safe before the system says "yes." Like a locked door that only opens with 9 correct keys. |
| **.env File** | A text file that stores secrets (passwords, API keys) separately from the code. This way, the code can be shared publicly without exposing private credentials. |
| **Event Loop** | The engine that manages async tasks. Think of it as a juggler — it keeps multiple balls (tasks) in the air, giving each one attention when needed. |
| **Function (`def`)** | A named, reusable block of code. `def curl_get(url):` means "here's a recipe called `curl_get` that takes a web address and does something with it." |
| **Hard Floor** | The absolute maximum loss allowed on any single trade (15%). Named "hard" because it cannot be overridden by any other rule. |
| **JSON** | A standard format for structured data, like a form with labeled fields. `{"name": "Bitcoin", "price": 50000}` — easy for both humans and computers to read. |
| **Jupiter** | The trading service the bot uses to execute swaps on Solana. It finds the best price across multiple sources, like a travel site comparing airline prices. |
| **Liquidity** | How much money is available to trade a coin. Low liquidity means you might not be able to sell when you want to — like trying to sell a rare stamp vs. selling a dollar bill. |
| **Logging** | Writing notes about what the bot is doing to a file. Essential for debugging ("why did it sell that coin?") and performance tracking. |
| **Market Cap** | The total value of all coins in existence for a given token. Price per coin x number of coins = market cap. |
| **Memecoin** | A cryptocurrency token that's usually joke-themed, very new, and extremely volatile. High risk, high potential reward. |
| **Paper Trading** | Practice mode with fake money. The bot runs all its logic, but instead of actually buying/selling, it records what it *would* have done. Used to validate strategy before risking real money. |
| **PnL (Profit and Loss)** | The financial result of a trade. Positive = you made money. Negative = you lost money. Often shown as a percentage. |
| **Position** | An active trade — a coin the bot currently holds. "Open a position" = buy. "Close a position" = sell. |
| **Profit Factor** | Total money won divided by total money lost. A Profit Factor of 2.0 means you won $2 for every $1 you lost. Above 1.0 = profitable overall. |
| **RPC (Remote Procedure Call)** | A way to send commands to the Solana blockchain. The bot uses Helius (a company) as its RPC provider — they relay commands to the blockchain. |
| **Rug Pull ("Rug")** | A crypto scam where creators of a coin suddenly remove all the money, making the coin worthless. The price drops 90%+ in seconds. |
| **Self-Regulation** | The bot's ability to pause itself when things are going badly. After 3 losses in a row, it switches to "cautious" mode (smaller bets). After 5, it pauses entirely. |
| **Slippage** | The difference between the expected price and the actual price you get. Like ordering a $10 item but being charged $10.50 because the price changed while your order was processing. |
| **SOL** | Solana's native cryptocurrency. Used to pay transaction fees and as the base currency for trading. |
| **Stoic Gate** | A self-imposed rule: no changing the bot's settings until 20 trades are complete. Prevents reacting emotionally to a small number of results. Named because it requires discipline and patience. |
| **subprocess** | Python's way of running external commands (like curl) as if typing them into a terminal window. |
| **systemd** | A Linux tool that manages programs running on a server. It auto-restarts the bot if it crashes and collects its logs. |
| **Token** | A digital asset on a blockchain. Each memecoin is a token with its own unique address (a long string of characters). |
| **Trailing Stop** | A sell rule that follows a rising price. Once the price rises 8% above your buy price, the trailing stop "arms." From that point, if the price drops 4% from its highest point, it sells. This lets winners run while protecting gains. |
| **Try/Except** | Python's safety net. "Try to do this thing. If it breaks, do this other thing instead of crashing." |
| **VPS (Virtual Private Server)** | A computer in a data center that you rent. The bot runs on a Vultr VPS in New Jersey — it's always on, always connected, running 24/7. |
| **WSOL (Wrapped SOL)** | A technical wrapper that lets SOL be traded like any other token on Jupiter. The address `So111...112` is always WSOL. Think of it as SOL wearing a name tag so the trading system recognizes it. |
| **Win Rate** | The percentage of trades that were profitable. 4 wins out of 10 trades = 40% win rate. |

---

## Part 5: The Three-Layer Config System

One of the project's most clever designs. Think of it as three layers of rules, where each layer can override the one below it:

```
┌──────────────────────────────┐
│  Layer 3: LEARNING ENGINE    │  ← Top layer. The bot's self-adjustments
│  (adjusts bet size based     │    based on its own trading results.
│   on recent performance)     │    Can only change position_pct.
├──────────────────────────────┤
│  Layer 2: RUNTIME CONFIG     │  ← Middle layer. Josh can change these
│  (stored in database,        │    without restarting the bot. Like
│   changed via dashboard)     │    adjusting a thermostat.
├──────────────────────────────┤
│  Layer 1: CODE DEFAULTS      │  ← Bottom layer. The safety net.
│  (CFG dictionary in code,    │    If nothing else overrides, these
│   never changes at runtime)  │    values are used. Like factory settings.
└──────────────────────────────┘
```

**Why three layers?** Layer 1 guarantees the bot always has safe defaults. Layer 2 lets Josh make adjustments without touching the code. Layer 3 lets the bot learn and adapt on its own, within strict guardrails (10-25% position size only).

---

## Part 6: External Services Map

The bot talks to four external services. Here's what each one does:

| Service | What It Does | Analogy | Needs a Key? |
|---------|-------------|---------|-------------|
| **DexScreener** | Finds coins that are moving | A stock screener / market scanner | No (public) |
| **Birdeye** | Gets real-time prices | A live price ticker | Yes (free tier) |
| **Helius (Solana RPC)** | Reads the blockchain and sends transactions | A bank teller who processes your trades | Yes (free tier) |
| **Jupiter** | Executes the actual swaps (buy/sell) | A broker who fills your order at the best price | No (public) |

---

## Part 7: Current Status (as of March 31, 2026)

### Where Things Stand

- **Phase:** Paper trading validation (v3.1)
- **Trades completed:** 7 out of 20 needed
- **Win rate:** 28.6% (target: 40%)
- **Profit Factor:** 1.42 (target: 1.5)
- **Net result:** +$158.26 on $10,000 virtual balance (+1.58%)
- **Decision date:** April 7, 2026

### What's Working

1. **Losses are controlled.** Average loss is -4.66% (v2 was -17.23% — nearly 4x worse). The 7-tier exit chain is doing its job.
2. **Winners are big enough to compensate.** The first profitable trade (CLOWN token) gained +29.59%, more than covering multiple small losses.
3. **No catastrophic failures.** The emergency rug detector fired once and worked correctly.

### What's Being Watched

1. **Low trade frequency** — Only 2.3 trades per day. This is because the crypto market is in "Extreme Fear" (Fear & Greed Index = 8 out of 100). Not a system problem, but it slows validation.
2. **Small sample size** — 7 trades isn't enough to draw conclusions. Need 20+ for statistical significance.
3. **Win rate below target** — 28.6% vs 40% target. However, with asymmetric risk (small losses, big wins), a lower win rate can still be profitable.

### The Go-Live Decision

On April 7, if all metrics pass AND Josh's gut says yes, the bot switches from paper trading to real money. Both conditions must be met — the numbers can't override human judgment, and human judgment can't override bad numbers.

---

## Part 8: Key Decisions and Why They Were Made

| Decision | What Was Chosen | Why | What Was Rejected |
|----------|----------------|-----|-------------------|
| **Language** | Python | Easiest to learn, huge ecosystem, Josh is learning from scratch | Rust (too complex), JavaScript (less suited for data work) |
| **Database** | SQLite | Single file, no setup, good enough for one bot | PostgreSQL (overkill for this scale) |
| **HTTP for external APIs** | curl subprocess | aiohttp silently fails on external APIs | aiohttp (broken for this use case) |
| **Hosting** | Vultr VPS ($6/mo) | Cheap, reliable, full control | AWS/GCP (overengineered for one bot) |
| **Trading platform** | Jupiter DEX | Direct blockchain access, no KYC, fastest execution | Centralized exchanges (slower, require identity verification) |
| **Config management** | 3-layer hierarchy | Safe defaults + runtime flexibility + self-learning | Single config file (too rigid) |
| **Process management** | systemd | Auto-restart, log collection, standard Linux tooling | Docker (unnecessary complexity) |

---

## Part 9: How to Read the Code (Quick Start)

If you want to open `lazarus.py` and orient yourself, here are the landmarks:

1. **Top of file (lines 1-50):** Import statements — these are like "ingredients needed." Each `import` pulls in a library the bot uses.

2. **CFG dictionary (~line 60):** The settings block. All the numbers that control behavior.

3. **EnvLoader class (~line 100):** Reads the `.env` secrets file.

4. **BirdeyeScanner class (~line 150):** Scans DexScreener for moving coins.

5. **LazarusEngine class (~line 300):** The main brain. Contains:
   - `scan_signals()` — Phase 1 (find coins)
   - `can_trade()` — Phase 2 (9-point filter)
   - `execute_entry()` — Buy a coin
   - `check_exits()` — Phase 3 (7-tier sell rules)
   - `monitor_positions()` — Watch all open trades
   - `run()` — The main loop

6. **Bottom of file (~line 1200):** `if __name__ == "__main__":` — This is where the program starts when you run it. It creates the engine and calls `run()`.

### Reading Tip: Follow the Verbs

Python code reads almost like English if you focus on the function names (verbs):
- `scan_signals()` = scan for signals
- `can_trade()` = can we trade this?
- `execute_entry()` = execute an entry (buy)
- `check_exits()` = check if we should exit (sell)
- `get_price()` = get the price
- `adjust_position_size()` = adjust position size

---

*This synthesis was generated from a complete review of the Moss Lane codebase and documentation. For the live code, see the `/github-repo/engine/` directory. For detailed architecture, see `/github-repo/docs/architecture.md`.*
