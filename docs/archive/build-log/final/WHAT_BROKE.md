# WHAT BROKE — Honest Retrospective & Engineering Hardening Stories

> **"Judges read failure recovery first."**  
> SELLABLE is built on absolute transparency. Below are three critical production/runtime bugs encountered during real-world stress testing, along with the exact root causes, commit fixes, and prevention invariants implemented.

---

## Story 1: Windows cp1252 Console Crash & The Standard Unicode Encoding Discipline

### The Symptom
When running script tools or evaluation runs on Windows 11 machines, script execution crashed abruptly with:
`UnicodeEncodeError: 'charmap' codec can't encode character '\u26a1' in position 14: character maps to <undefined>`

### Root Cause
Windows console stdout defaults to code page `cp1252` (Windows-1252), which lacks support for emoji or extended UTF-8 glyphs. Any unhandled `print("⚡ Executing...")` statement throws an unrecoverable exception when piped to standard output on Windows environments.

### The Fix (Commit `e1915a8`)
1. **Console Output Discipline**: All CLI outputs in `scripts/doctor.py`, `run_demo.py`, `scripts/final_verify.py`, and `verify_numbers.py` were converted to strict ASCII text (e.g. `[ PASS ]`, `[ FAIL ]`, `[ WARN ]`).
2. **Explicit UTF-8 File I/O**: Every `open()`, `read_text()`, and `write_text()` call across all 159 Python files was updated to include explicit `encoding="utf-8"`.
3. **HTML Unicode Isolation**: Emojis and rich UTF-8 characters are restricted exclusively to server-rendered HTML UI views where browsers handle UTF-8 natively.

---

## Story 2: Atomic Binding Consumption Race Under 100-Thread Concurrency Testing

### The Symptom
During high-concurrency load testing (100 parallel execution threads issuing purchase orders simultaneously against the same single-use approval binding token), 2 out of 100 threads succeeded in creating Razorpay orders, violating **Invariant G5 / G16** (*Single-use binding token consumption*).

### Root Cause
The initial binding consumption logic performed a read-then-write sequence:
```python
# BROKEN READ-THEN-WRITE
binding = db.query("SELECT consumed FROM bindings WHERE token=?", [token])
if not binding.consumed:
    db.execute("UPDATE bindings SET consumed=1 WHERE token=?", [token])
    create_razorpay_order()
```
Because the read and update were separate non-atomic SQL operations, concurrent threads read `consumed = 0` simultaneously before either thread committed `consumed = 1`.

### The Fix (Commit `3f7987e`)
1. **Atomic Conditional SQL Update**: Replaced read-then-write with an atomic `UPDATE ... WHERE consumed=0` statement:
```python
cursor = db.execute(
    "UPDATE bindings SET consumed=1, consumed_at=? WHERE token=? AND consumed=0",
    [now_ts, token]
)
if cursor.rowcount == 0:
    raise BindingConsumedError("Token already consumed or invalid")
```
2. **SQLite WAL Mode**: Enabled Write-Ahead Logging (`PRAGMA journal_mode=WAL;`) and immediate transaction locking to enforce absolute serializability under high concurrency.
3. **Verification**: Validated by `tests/invariants/test_r10_expiry.py` and `tests/test_money_path_offline.py` asserting 100-thread single-execution guarantees.

---

## Story 3: Single-Worker Event Loop Deadlock in Demo Proxy (`/demo/checkout`)

### The Symptom
Navigating to `/demo/checkout` and executing scenario replays resulted in client HTTP timeouts (`ReadTimeout`) or `503 Service Unavailable` errors.

### Root Cause
The `/demo/checkout` proxy made external loopback HTTP requests (`httpx.get("http://127.0.0.1:8000/agent/run-scenario/...")`) back to the same server process. When uvicorn ran as a single worker thread, the thread was blocked waiting for the outbound HTTP request to respond, while the inbound handler for that request was queued behind the blocked thread — causing a classic single-worker loopback HTTP deadlock.

### The Fix (Commit `3f7987e` & `fbc85aa`)
1. **In-Process Direct Endpoint Invocation**: Refactored `demo_proxy` in `apps/api/demo_ui.py` to invoke Python endpoint functions (`run_scenario_endpoint`, `run_full_mission_ui`) directly in-memory, completely bypassing HTTP network loops.
2. **Dynamic API Key Evaluation**: Replaced static import-time `_API_KEY` evaluation with dynamic `_get_api_key()` to prevent 501/503 errors when `.env` is loaded after module initialization.
3. **Multi-Worker Server Configuration**: Updated default uvicorn server startup in `run_demo.py` and daemon configurations to run with multi-worker concurrency.

---

## Summary of Hardening Invariants

| Problem Domain | Root Cause | Architectural Invariant Enforced |
|---|---|---|
| **Windows Console Crashes** | `cp1252` encoding mismatch | Strict ASCII stdout + explicit `encoding="utf-8"` file I/O |
| **Concurrency Double-Spend** | Read-then-write SQL race | Atomic `UPDATE ... WHERE consumed=0` + SQLite WAL |
| **Single-Worker Deadlock** | Loopback HTTP requests to self | In-process Python handler calls in proxy routes |
