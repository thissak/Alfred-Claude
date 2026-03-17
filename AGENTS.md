# Alf Agent Guide

## Project

Alf is a personal AI assistant that runs on macOS and talks over iMessage.
The current production direction is bridge mode plus a runtime orchestrator.

Primary runtime path:

```text
iMessage
-> src/alf_bridge.py
-> run/inbox/*.json
-> src/process_inbox.py
-> src/runtime/orchestrator.py
-> run/outbox/*.json
-> src/alf_bridge.py
-> iMessage
```

Scheduled jobs run through:

```text
src/runtime/scheduler_worker.py
-> src/runtime/orchestrator.py::handle_scheduled_job()
-> run/outbox/*.json
-> src/alf_bridge.py
```

Legacy path:

- `src/alf.py`
- `src/brain.py`

These are retired from the default daemon set and should not be used for new work unless explicitly needed for rollback.

## Source Of Truth

- Current progress: `docs/PROGRESS.md`
- Architecture decisions: `docs/adr/`
- Temporary handoff notes: `docs/handoff/`
- Change history: `docs/CHANGELOG.md`

If a handoff doc conflicts with an ADR or current code, trust the code first, then ADR, then handoff notes.

## Working Rules

- Address the user as `감독님`.
- Prefer changing the runtime path over extending legacy `alf.py`.
- Keep bridge mode stable. Do not break `run/inbox` and `run/outbox` contracts.
- Keep data local unless the task explicitly needs an external service.
- Avoid destructive actions on launchd, logs, memory DB, or message DB without clear need.
- When validating messaging flows, prefer a safe path first:
  safe stubs or temporary outbox before real iMessage sends.
- If you must do a real end-to-end send, use a clearly labeled temporary schedule or test message and clean it up after.
- KIS and other brokerage credentials are read-only by policy.
- Do not add or run stock order, cancel, or modify flows.
- Stock automation may fetch balances, fills, quotes, rankings, and analysis inputs only.
- KIS access must go through `src/kis_readonly_client.py`.
- Do not call Korea Investment endpoints directly from ad hoc scripts or new modules.

## Key Files

- `src/runtime/orchestrator.py`: message and schedule orchestration
- `src/runtime/scheduler_worker.py`: due schedule worker
- `src/process_inbox.py`: inbox watcher and runtime entrypoint
- `src/alf_bridge.py`: iMessage bridge for inbox and outbox
- `src/memory.py`: SQLite memory and history
- `src/scheduler.py`: schedule storage and due-job logic
- `src/tools/`: runtime tools for memory, notes, and schedule parsing
- `daemon_ctl.py`: dev and launchd daemon management

## Daemons

Default operational daemons:

- `bridge`
- `inbox`
- `schedule`
- `email`

Legacy daemon:

- `alf`

Useful commands:

```bash
python3 daemon_ctl.py status
python3 daemon_ctl.py logs schedule -f
python3 daemon_ctl.py install schedule
python3 daemon_ctl.py install bridge
python3 daemon_ctl.py install inbox
```

## Validation

Minimum checks for code changes that touch runtime flow:

```bash
PYTHONPYCACHEPREFIX=/tmp/alf_pycache python3 -m py_compile daemon_ctl.py src/process_inbox.py src/runtime/orchestrator.py src/runtime/scheduler_worker.py
```

For safe end-to-end checks, prefer:

- temporary inbox/outbox directories
- patched `send_imessage`
- patched GPT call

For real end-to-end checks:

- record the exact test job or message used
- verify `logs/schedule.log` or relevant daemon logs
- verify `run/outbox` drain behavior
- clean up the temporary test schedule if it is not one-shot

## Done Criteria

A runtime refactor is not done until:

- code path works through `src/runtime/`
- daemon wiring is updated if needed
- a safe validation path has been run
- `docs/PROGRESS.md` is updated when the project status changed
- any lasting architecture decision is reflected in `docs/adr/` if the design changed materially
