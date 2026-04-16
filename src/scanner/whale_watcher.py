#!/usr/bin/env python3
"""
WhaleWatcher — Real-Time Whale Copy-Trade Scanner for Lazarus

ARCHITECTURE:
  Single WebSocket  = logsSubscribe on Jupiter program via Helius RPC
  whale_set         = in-memory Python set of 20K+ wallet addresses (O(1) lookup)
  discover_wallets  = DexScreener scraper, refreshes hourly, populates whale_set
  curl_get()        = all external HTTP (never aiohttp for external APIs)
  aiohttp           = WebSocket to Helius RPC only
  Signal buffer     = thread-safe deque(maxlen=100), consumed by SignalAggregator

DATA FLOW:
  Helius WebSocket → logsSubscribe(Jupiter program)
    → parse tx logs → extract signer wallet
    → signer in whale_set? → extract token mint
    → curl_get(DexScreener) → validate via filter cascade
    → emit Signal to buffer
    → SignalAggregator.get_signals() drains buffer every 30s

WALLET DISCOVERY:
  discover_wallets() runs once per hour (async timer)
    → curl_get(DexScreener trending tokens)
    → extract top trader wallets
    → INSERT OR IGNORE into whale_wallets table
    → reload whale_set from DB

TIER SYSTEM:
  A = top 500 most profitable (win_count - loss_count)  → score 88.0
  B = top 5000                                          → score 85.0
  C = rest                                              → score 80.0

RESILIENCE:
  - Auto-reconnect on WebSocket disconnect (exponential backoff: 1s→30s)
  - Fail-closed: disconnected → get_signals() returns []
  - Discovery failures do not crash the watcher
  - Signal buffer maxlen=100 (drop oldest if full)

INTEGRATION:
  Called by SignalAggregator in lazarus.py:
    watcher = WhaleWatcher(db_path=DB_PATH, helius_key="...", ...)
    await watcher.start()
    signals = watcher.get_signals(db)  # every 30s scan cycle
"""

import asyncio
import aiohttp
import sqlite3
import logging
import json
import subprocess
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Set

log = logging.getLogger("whale_watcher")

# Jupiter v6 program ID
JUPITER_PROGRAM = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"

# Common tokens to ignore (stablecoins, wrapped SOL)
IGNORE_MINTS: Set[str] = {
    "So11111111111111111111111111111111111111112",       # WSOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",   # USDC
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",    # USDT
}

# Tier score mapping
TIER_SCORES: Dict[str, float] = {"A": 88.0, "B": 85.0, "C": 80.0}


# ══════════════════════════════════════════════════════════════════════════════
# Signal dataclass — duplicated from lazarus.py (no cross-import)
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class Signal:
    symbol:   str
    address:  str
    price:    float
    source:   str
    score:    float = 0.0
    hourly:   float = 0.0
    chg_pct:  float = 0.0
    mc:       float = 0.0
    liq:      float = 0.0
    extra:    Dict  = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════════════
# curl_get() — subprocess HTTP (never aiohttp for external APIs)
# ══════════════════════════════════════════════════════════════════════════════
def curl_get(url: str, timeout: int = 10) -> dict:
    """Fetch JSON from URL via subprocess curl. Returns {} on failure."""
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", str(timeout), url],
            capture_output=True, text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {}
        return json.loads(result.stdout)
    except (json.JSONDecodeError, Exception) as e:
        log.warning(f"curl_get failed: {url[:80]}... — {e}")
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# WhaleWatcher — main class
# ══════════════════════════════════════════════════════════════════════════════
class WhaleWatcher:
    """
    Real-time whale copy-trade scanner via Jupiter WebSocket subscription.

    Usage:
        watcher = WhaleWatcher(db_path="/path/to/lazarus.db", helius_key="xxx")
        await watcher.start()
        ...
        signals = watcher.get_signals(db)  # called every scan cycle
        ...
        await watcher.stop()
    """

    def __init__(
        self,
        db_path: str,
        helius_key: str,
        # Filter thresholds (same as CFG in lazarus.py, passed explicitly)
        min_mc: float = 10_000,
        max_mc: float = 10_000_000,
        min_liq: float = 50_000,
        min_chg_pct: float = 10.0,
        min_pair_age_min: float = 60,
        # Discovery config
        discovery_interval_sec: int = 3600,
        # Blacklist
        blacklist: Optional[Set[str]] = None,
    ):
        self.db_path = db_path
        self.helius_key = helius_key
        self.ws_url = f"wss://mainnet.helius-rpc.com/?api-key={helius_key}"

        # Filter thresholds
        self.min_mc = min_mc
        self.max_mc = max_mc
        self.min_liq = min_liq
        self.min_chg_pct = min_chg_pct
        self.min_pair_age_min = min_pair_age_min

        # Discovery
        self.discovery_interval_sec = discovery_interval_sec

        # Blacklist
        self.blacklist: Set[str] = blacklist or set()
        self.blacklist.update(IGNORE_MINTS)

        # In-memory whale set (O(1) lookup)
        self._whale_set: Set[str] = set()
        self._whale_tiers: Dict[str, str] = {}  # address → tier (A/B/C)

        # Signal buffer (thread-safe via deque maxlen)
        self._signal_buffer: deque = deque(maxlen=100)

        # State tracking
        self._connected = False
        self._running = False
        self._signals_today = 0
        self._last_signal_time: Optional[str] = None
        self._reconnect_delay = 1.0

        # Background thread + event loop
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event: Optional[asyncio.Event] = None

        # Database (owned by this module, separate connection)
        self._db_lock = threading.Lock()
        self._db_conn: Optional[sqlite3.Connection] = None

        # WebSocket subscription ID
        self._sub_id: Optional[int] = None

    # ──────────────────────────────────────────────────────────────────────
    # Database setup
    # ──────────────────────────────────────────────────────────────────────
    def _init_db(self):
        """Create whale-specific tables in the shared Lazarus database."""
        self._db_conn = sqlite3.connect(
            self.db_path, check_same_thread=False, timeout=10,
        )
        self._db_conn.executescript("""
            CREATE TABLE IF NOT EXISTS whale_wallets (
                address TEXT PRIMARY KEY,
                source TEXT,
                discovered_at TEXT,
                win_count INTEGER DEFAULT 0,
                loss_count INTEGER DEFAULT 0,
                last_seen TEXT,
                tier TEXT DEFAULT 'C'
            );
            CREATE TABLE IF NOT EXISTS whale_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                whale_address TEXT,
                token_address TEXT,
                token_symbol TEXT,
                action TEXT,
                signal_score REAL
            );
        """)
        self._db_conn.commit()

    def _load_whale_set(self):
        """Load whale addresses + tiers from DB into memory."""
        if not self._db_conn:
            return
        with self._db_lock:
            rows = self._db_conn.execute(
                "SELECT address, tier FROM whale_wallets"
            ).fetchall()
        self._whale_set = {r[0] for r in rows}
        self._whale_tiers = {r[0]: (r[1] or "C") for r in rows}
        log.info(f"Loaded {len(self._whale_set)} whale addresses into memory")

    def _recompute_tiers(self):
        """Recompute A/B/C tiers based on profitability ranking."""
        if not self._db_conn:
            return
        with self._db_lock:
            rows = self._db_conn.execute(
                "SELECT address, win_count, loss_count FROM whale_wallets "
                "ORDER BY (win_count - loss_count) DESC"
            ).fetchall()

        updates: List[tuple] = []
        for i, (addr, wins, losses) in enumerate(rows):
            if i < 500:
                tier = "A"
            elif i < 5000:
                tier = "B"
            else:
                tier = "C"
            updates.append((tier, addr))

        with self._db_lock:
            self._db_conn.executemany(
                "UPDATE whale_wallets SET tier = ? WHERE address = ?", updates,
            )
            self._db_conn.commit()

        # Reload into memory
        self._whale_tiers = {addr: tier for tier, addr in updates}

    # ──────────────────────────────────────────────────────────────────────
    # Wallet discovery (DexScreener scraper)
    # ──────────────────────────────────────────────────────────────────────
    def _discover_wallets(self):
        """
        Scrape DexScreener for top traders on trending tokens.
        Inserts new wallets into whale_wallets table.
        Called on a timer (default: once per hour).
        """
        log.info("Starting wallet discovery cycle")
        discovered = 0

        # Step 1: Get trending/boosted tokens from DexScreener
        trending = curl_get(
            "https://api.dexscreener.com/token-boosts/top/v1", timeout=15,
        )
        if not isinstance(trending, list):
            trending = trending.get("tokens", []) if isinstance(trending, dict) else []

        # Extract Solana token addresses from trending
        token_addrs: List[str] = []
        for item in trending[:30]:  # cap at 30 tokens per cycle
            chain = item.get("chainId", "")
            addr = item.get("tokenAddress", "")
            if chain == "solana" and addr:
                token_addrs.append(addr)

        if not token_addrs:
            # Fallback: use known popular Solana pairs search
            search = curl_get(
                "https://api.dexscreener.com/latest/dex/search?q=solana%20pump",
                timeout=15,
            )
            for pair in (search.get("pairs", []) or [])[:20]:
                if pair.get("chainId") == "solana":
                    base_addr = pair.get("baseToken", {}).get("address", "")
                    if base_addr and base_addr not in IGNORE_MINTS:
                        token_addrs.append(base_addr)

        # Step 2: For each token, get pair data and extract trader info
        now = datetime.now(timezone.utc).isoformat()
        for token_addr in token_addrs:
            try:
                data = curl_get(
                    f"https://api.dexscreener.com/latest/dex/tokens/{token_addr}",
                    timeout=10,
                )
                pairs = data.get("pairs", [])
                if not pairs:
                    continue

                # Extract transaction makers from pair data
                for pair in pairs[:3]:  # top 3 pairs per token
                    # DexScreener pairs include txns data with makers
                    txns = pair.get("txns", {})
                    # The pair info includes maker addresses in some endpoints
                    # We also extract from the pair URL pattern
                    pair_addr = pair.get("pairAddress", "")
                    if not pair_addr:
                        continue

                    # Try the traders endpoint for this pair
                    traders_data = curl_get(
                        f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair_addr}",
                        timeout=10,
                    )
                    traders_pairs = traders_data.get("pairs", []) if isinstance(traders_data, dict) else []
                    for tp in traders_pairs:
                        # Extract maker/buyer addresses from transaction metadata
                        info = tp.get("info", {})
                        websites = info.get("websites", [])
                        # DexScreener doesn't directly expose wallet addresses
                        # in the free API — we extract top holders from
                        # the token profile data instead
                        pass

                    # Use Helius to get recent swap signers for this token
                    # This is more reliable than DexScreener for wallet discovery
                    helius_url = (
                        f"https://api.helius.xyz/v0/addresses/{token_addr}/transactions"
                        f"?api-key={self.helius_key}&limit=20&type=SWAP"
                    )
                    txs = curl_get(helius_url, timeout=10)
                    if not isinstance(txs, list):
                        continue

                    wallets_found: Set[str] = set()
                    for tx in txs:
                        signer = ""
                        # feePayer is the transaction signer
                        signer = tx.get("feePayer", "")
                        if not signer:
                            # Fallback: first account key
                            accts = tx.get("accountData", [])
                            if accts:
                                signer = accts[0].get("account", "")
                        if signer and signer not in IGNORE_MINTS and len(signer) > 30:
                            wallets_found.add(signer)

                    # Insert discovered wallets
                    with self._db_lock:
                        for wallet in wallets_found:
                            try:
                                self._db_conn.execute(
                                    "INSERT OR IGNORE INTO whale_wallets "
                                    "(address, source, discovered_at, last_seen) "
                                    "VALUES (?, ?, ?, ?)",
                                    (wallet, f"dex_{token_addr[:8]}", now, now),
                                )
                                discovered += 1
                            except sqlite3.IntegrityError:
                                pass
                        self._db_conn.commit()

            except Exception as e:
                log.warning(f"Discovery error for {token_addr[:12]}: {e}")
                continue

        # Step 3: Recompute tiers and reload whale_set
        self._recompute_tiers()
        self._load_whale_set()
        log.info(
            f"Discovery complete: {discovered} new wallets found, "
            f"{len(self._whale_set)} total tracked"
        )

    # ──────────────────────────────────────────────────────────────────────
    # WebSocket: Jupiter log parsing
    # ──────────────────────────────────────────────────────────────────────
    def _parse_jupiter_log(self, log_data: dict) -> Optional[Dict]:
        """
        Parse a logsSubscribe notification for Jupiter swap data.

        Returns dict with {signer, token_mint} if a tracked whale is detected,
        or None if not relevant.
        """
        value = log_data.get("value", {})
        logs = value.get("logs", [])
        signature = value.get("signature", "")

        if not logs:
            return None

        # Extract signer from the log context
        # The first log typically contains "Program log: Instruction: ..."
        # The account keys are in the transaction metadata
        # For logsSubscribe, we need to fetch the tx to get the signer
        # But we can check if any tracked whale is mentioned in the logs

        # Quick scan: check if any log line mentions a tracked wallet
        # This is a fast pre-filter before fetching full tx data
        err = value.get("err")
        if err is not None:
            return None  # Failed transactions — skip

        # The signature lets us fetch full tx details to get the signer
        if not signature:
            return None

        return {"signature": signature}

    async def _resolve_swap_details(
        self, session: aiohttp.ClientSession, signature: str,
    ) -> Optional[Dict]:
        """
        Fetch full transaction details via Helius parsed transactions API
        to extract signer and token received.

        Uses curl_get() for the actual HTTP call (subprocess).
        """
        # Use Helius parsed transaction endpoint
        url = (
            f"https://api.helius.xyz/v0/transactions/?api-key={self.helius_key}"
        )
        # Helius parse endpoint accepts POST with transaction signatures
        try:
            result = subprocess.run(
                [
                    "curl", "-s", "--max-time", "8",
                    "-X", "POST",
                    "-H", "Content-Type: application/json",
                    "-d", json.dumps({"transactions": [signature]}),
                    url,
                ],
                capture_output=True, text=True,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return None
            txs = json.loads(result.stdout)
        except (json.JSONDecodeError, Exception):
            return None

        if not isinstance(txs, list) or not txs:
            return None

        tx = txs[0]
        signer = tx.get("feePayer", "")

        # Check if signer is a tracked whale
        if signer not in self._whale_set:
            return None

        # Find token received by the signer (= buy side of swap)
        token_addr = None
        for change in (tx.get("tokenTransfers") or []):
            if change.get("toUserAccount") == signer:
                mint = change.get("mint", "")
                if mint and mint not in self.blacklist:
                    token_addr = mint
                    break

        if not token_addr:
            return None

        return {
            "signer": signer,
            "token_mint": token_addr,
            "signature": signature,
        }

    async def _validate_and_emit(self, swap: Dict):
        """
        Validate token via DexScreener filter cascade and emit Signal.
        Mirrors SmartMoneyScanner filter logic (lazarus.py:772-783).
        """
        token_addr = swap["token_mint"]
        signer = swap["signer"]
        tier = self._whale_tiers.get(signer, "C")
        base_score = TIER_SCORES.get(tier, 80.0)

        # Fetch pair data from DexScreener
        pd = curl_get(
            f"https://api.dexscreener.com/latest/dex/tokens/{token_addr}",
            timeout=8,
        )
        pairs = pd.get("pairs", [])
        if not pairs:
            return

        # Use highest-liquidity pair
        pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))

        price = float(pair.get("priceUsd", 0) or 0)
        mc = float(pair.get("marketCap", 0) or pair.get("fdv", 0) or 0)
        liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
        sym = pair.get("baseToken", {}).get("symbol", token_addr[:8]).strip()
        c1h = float(pair.get("priceChange", {}).get("h1", 0) or 0)

        # ── Filter cascade (matches SmartMoneyScanner) ──
        if price <= 0:
            return
        if not (self.min_mc < mc < self.max_mc):
            return
        if liq < self.min_liq:
            return
        if c1h < self.min_chg_pct:
            return

        # Age gate
        pair_created = pair.get("pairCreatedAt", 0)
        if pair_created:
            age_min = (time.time() * 1000 - pair_created) / 60000
            if age_min < self.min_pair_age_min:
                return

        # Blacklist check
        if token_addr in self.blacklist:
            return

        # ── Emit signal ──
        source_id = f"whale_{signer[:8]}"
        signal = Signal(
            symbol=sym,
            address=token_addr,
            price=price,
            source=source_id,
            score=base_score,
            hourly=c1h,
            chg_pct=c1h,
            mc=mc,
            liq=liq,
            extra={"whale": signer, "tier": tier, "sig": swap["signature"][:16]},
        )

        self._signal_buffer.append(signal)
        self._signals_today += 1
        self._last_signal_time = datetime.now(timezone.utc).isoformat()

        log.info(
            f"WHALE SIGNAL [{tier}]: wallet={signer[:8]} token={sym} "
            f"liq=${liq:.0f} chg1h={c1h:.1f}% score={base_score}"
        )

        # Record to DB
        with self._db_lock:
            try:
                self._db_conn.execute(
                    "INSERT INTO whale_signals VALUES (NULL,?,?,?,?,?,?)",
                    (
                        datetime.now(timezone.utc).isoformat(),
                        signer, token_addr, sym, "buy", base_score,
                    ),
                )
                # Update last_seen on the whale wallet
                self._db_conn.execute(
                    "UPDATE whale_wallets SET last_seen = ? WHERE address = ?",
                    (datetime.now(timezone.utc).isoformat(), signer),
                )
                self._db_conn.commit()
            except Exception as e:
                log.warning(f"DB write error: {e}")

    # ──────────────────────────────────────────────────────────────────────
    # WebSocket event loop
    # ──────────────────────────────────────────────────────────────────────
    async def _ws_loop(self):
        """Main WebSocket loop with auto-reconnect and exponential backoff."""
        self._stop_event = asyncio.Event()

        while self._running and not self._stop_event.is_set():
            try:
                async with aiohttp.ClientSession() as session:
                    log.info(f"Connecting to Helius WebSocket...")
                    async with session.ws_connect(
                        self.ws_url,
                        heartbeat=30,
                        timeout=aiohttp.ClientWSTimeout(ws_close=10),
                    ) as ws:
                        self._connected = True
                        self._reconnect_delay = 1.0  # reset backoff
                        log.info("WebSocket connected — subscribing to Jupiter logs")

                        # Subscribe to Jupiter program logs
                        subscribe_msg = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "logsSubscribe",
                            "params": [
                                {"mentions": [JUPITER_PROGRAM]},
                                {"commitment": "confirmed"},
                            ],
                        }
                        await ws.send_json(subscribe_msg)

                        # Read subscription confirmation
                        async for msg in ws:
                            if self._stop_event.is_set():
                                break

                            if msg.type == aiohttp.WSMsgType.TEXT:
                                try:
                                    data = json.loads(msg.data)
                                except json.JSONDecodeError:
                                    continue

                                # Subscription confirmation
                                if "result" in data and self._sub_id is None:
                                    self._sub_id = data["result"]
                                    log.info(
                                        f"Subscribed to Jupiter logs "
                                        f"(sub_id={self._sub_id})"
                                    )
                                    continue

                                # Log notification
                                if data.get("method") == "logsNotification":
                                    params = data.get("params", {})
                                    parsed = self._parse_jupiter_log(
                                        params.get("result", {}),
                                    )
                                    if parsed and parsed.get("signature"):
                                        # Resolve in background to not block WS
                                        asyncio.create_task(
                                            self._handle_swap(
                                                session, parsed["signature"],
                                            )
                                        )

                            elif msg.type in (
                                aiohttp.WSMsgType.CLOSED,
                                aiohttp.WSMsgType.ERROR,
                            ):
                                log.warning(f"WebSocket closed: {msg.type}")
                                break

            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
                log.warning(f"WebSocket error: {e}")
            except Exception as e:
                log.warning(f"WebSocket unexpected error: {e}")
            finally:
                self._connected = False
                self._sub_id = None

            if self._running and not self._stop_event.is_set():
                log.info(
                    f"Reconnecting in {self._reconnect_delay:.0f}s..."
                )
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)

    async def _handle_swap(
        self, session: aiohttp.ClientSession, signature: str,
    ):
        """Resolve a swap transaction and emit signal if whale match."""
        try:
            swap = await self._resolve_swap_details(session, signature)
            if swap:
                await self._validate_and_emit(swap)
        except Exception as e:
            log.warning(f"Swap handler error ({signature[:16]}): {e}")

    async def _discovery_loop(self):
        """Run wallet discovery on a timer."""
        while self._running:
            try:
                # Run discovery in a thread to avoid blocking the event loop
                await asyncio.get_event_loop().run_in_executor(
                    None, self._discover_wallets,
                )
            except Exception as e:
                log.warning(f"Discovery loop error: {e}")

            # Wait for next cycle (or stop)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.discovery_interval_sec,
                )
                break  # stop_event was set
            except asyncio.TimeoutError:
                pass  # Normal: timer expired, run discovery again

    async def _run(self):
        """Main async entry point — runs WS + discovery concurrently."""
        self._stop_event = asyncio.Event()

        # Run initial discovery before connecting WebSocket
        log.info("Running initial wallet discovery...")
        await asyncio.get_event_loop().run_in_executor(
            None, self._discover_wallets,
        )

        # Run WebSocket loop and discovery loop concurrently
        await asyncio.gather(
            self._ws_loop(),
            self._discovery_loop(),
            return_exceptions=True,
        )

    def _thread_target(self):
        """Background thread entry point."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run())
        except Exception as e:
            log.warning(f"WhaleWatcher thread error: {e}")
        finally:
            self._loop.close()

    # ──────────────────────────────────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────────────────────────────────
    async def start(self):
        """
        Start the WhaleWatcher in a background thread.
        Initializes DB, loads whale set, connects WebSocket.
        """
        if self._running:
            log.warning("WhaleWatcher already running")
            return

        log.info("Starting WhaleWatcher...")
        self._running = True

        # Initialize database and load whale set
        self._init_db()
        self._load_whale_set()

        # Start background thread with its own event loop
        self._thread = threading.Thread(
            target=self._thread_target,
            name="whale-watcher",
            daemon=True,
        )
        self._thread.start()
        log.info("WhaleWatcher started (background thread)")

    async def stop(self):
        """Graceful shutdown: close WebSocket, stop discovery, join thread."""
        if not self._running:
            return

        log.info("Stopping WhaleWatcher...")
        self._running = False

        # Signal the stop event in the background loop
        if self._loop and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)

        # Wait for background thread to finish
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)

        # Close DB connection
        if self._db_conn:
            try:
                self._db_conn.close()
            except Exception:
                pass

        self._connected = False
        log.info("WhaleWatcher stopped")

    def get_signals(self, db=None) -> List[Signal]:
        """
        Return accumulated signals since last call, then clear buffer.
        Fail-closed: returns [] if WebSocket is disconnected.

        Args:
            db: Database instance (unused here — kept for interface compatibility
                with SmartMoneyScanner.scan(db) pattern)
        """
        if not self._connected:
            return []

        signals = []
        while self._signal_buffer:
            try:
                signals.append(self._signal_buffer.popleft())
            except IndexError:
                break
        return signals

    def get_stats(self) -> Dict:
        """Return current watcher status for monitoring."""
        return {
            "connected": self._connected,
            "whales_tracked": len(self._whale_set),
            "signals_emitted_today": self._signals_today,
            "last_signal_time": self._last_signal_time or "never",
            "tier_a_count": sum(1 for t in self._whale_tiers.values() if t == "A"),
            "tier_b_count": sum(1 for t in self._whale_tiers.values() if t == "B"),
            "tier_c_count": sum(1 for t in self._whale_tiers.values() if t == "C"),
            "buffer_depth": len(self._signal_buffer),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Standalone test
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    DB_PATH = "/home/solbot/lazarus/logs/lazarus.db"
    HELIUS_KEY = os.environ.get("HELIUS_API_KEY", "")

    async def main():
        watcher = WhaleWatcher(
            db_path=DB_PATH,
            helius_key=HELIUS_KEY,
            min_mc=10_000,
            max_mc=10_000_000,
            min_liq=50_000,
            min_chg_pct=10.0,
            min_pair_age_min=60,
        )

        await watcher.start()
        print(f"\nWhaleWatcher started. Stats: {watcher.get_stats()}")
        print("Listening for whale swaps for 60 seconds...\n")

        for i in range(12):  # 12 cycles × 5s = 60s
            await asyncio.sleep(5)
            signals = watcher.get_signals()
            if signals:
                for sig in signals:
                    print(
                        f"  SIGNAL: {sig.symbol} | ${sig.price:.6f} | "
                        f"score={sig.score} | source={sig.source} | "
                        f"mc=${sig.mc:.0f} | liq=${sig.liq:.0f}"
                    )
            else:
                print(f"  [{i+1}/12] No signals — {watcher.get_stats()}")

        await watcher.stop()
        print("\nWhaleWatcher stopped.")

    asyncio.run(main())
