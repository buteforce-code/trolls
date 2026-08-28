"""
Runtime autonomy settings — the switches that used to be environment only.

Why this file exists
--------------------
`AUTOPILOT_ENABLED` is read from `os.environ` when the Python worker starts, and
the worker is a brand-new process on every tick. That made the variable perfectly
readable and completely *unswitchable* from the dashboard, which is a different
process (Node) that cannot reach into the environment of a process nobody has
spawned yet. The dashboard said so out loud rather than draw a Pause button that
did nothing. These switches now live in one Postgres row both processes read.

Read at tick time, never at import time. A module-level constant would have
reintroduced exactly the bug this file exists to remove: a value frozen at
process start, in a process that restarts on a schedule.

Four settings, and why they are four
------------------------------------
  autopilot_enabled   Does the engine run at all.                 (kill switch)
  human_in_the_loop   When it runs, does it stop and wait for a person.
  publish_gap_hours   Minimum spacing between two published posts. (cadence)
  veto_window_hours   Minimum wait before a finished post may publish.

The first two are genuinely different questions and conflating them would make
the kill switch unusable: "stop publishing unreviewed" and "stop working" are
not the same instruction.

The last two were always two ideas wearing one name. `PUBLISH_GAP_HOURS` was
simultaneously the SEO cadence (roughly a post a day, on purpose) and the human's
reprieve before a finished post ships. Left conflated, "switch the human off"
would also have read as "publish the whole buffer this afternoon" — eight posts
in one hour, which is bad for search and unmistakably machine-generated. So
switching the human off collapses the veto window to zero and leaves the cadence
exactly where it was.

Precedence: environment, then database, then default
----------------------------------------------------
An environment variable that is *set* always wins. It is the break-glass: whoever
holds the host can force the engine off, or force the human back on, and no
browser session — including a stolen one — can override it. The database is where
the operator's ordinary, persisted intent lives; it is what the dashboard writes.

Every value records which of the three answered, in `sources`, so the dashboard
can say "the host is overriding this" instead of rendering a switch that silently
does nothing. A control that lies about its own authority is worse than no
control, which is the whole reason this file was written.

Failure is not permission
-------------------------
If the row cannot be read, `human_in_the_loop` falls back to True, never False.
Not knowing what the operator wants is a reason to stop at the gate, not a reason
to publish unreviewed to a live website. `autopilot_enabled` falls back to True
in the same case, because an engine that shuts itself down over a transient
database blip is its own outage — the safe combination is "keep working, stop
before anything goes out".
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping

TABLE = "autopilot_settings"
SETTINGS_ROW_ID = 1

# Bounds mirror the CHECK constraints in setup_db.py. Validating here as well
# means a row edited directly in the Supabase console — where the constraint is
# the only guard — still cannot hand the engine a zero-hour cadence.
GAP_HOURS_MIN, GAP_HOURS_MAX = 1, 720
VETO_HOURS_MIN, VETO_HOURS_MAX = 0, 720

# What the settings are when nothing has ever been configured. `human_in_the_loop`
# is False here to match what the engine already does — autopilot has auto-advanced
# both gates since it was written, and a default that silently halted a working
# pipeline on first read would be a regression disguised as a safety feature.
# The *failure* fallback below is the opposite, and deliberately so.
DEFAULTS: Mapping[str, Any] = {
    "autopilot_enabled": True,
    "human_in_the_loop": False,
    "publish_gap_hours": 24,
    "veto_window_hours": 24,
}

# Which environment variable overrides which setting.
ENV_KEYS: Mapping[str, str] = {
    "autopilot_enabled": "AUTOPILOT_ENABLED",
    "human_in_the_loop": "HUMAN_IN_THE_LOOP",
    "publish_gap_hours": "PUBLISH_GAP_HOURS",
    "veto_window_hours": "VETO_WINDOW_HOURS",
}

_TRUE = {"true", "1", "yes", "on"}
_FALSE = {"false", "0", "no", "off"}


@dataclass(frozen=True)
class Settings:
    """One tick's view of the switches, plus where each answer came from."""

    autopilot_enabled: bool
    human_in_the_loop: bool
    publish_gap_hours: int
    veto_window_hours: int
    # field -> "env" | "db" | "default". The dashboard renders this verbatim; a
    # value sourced from "env" is one the UI switch cannot change.
    sources: Mapping[str, str] = field(default_factory=dict)
    # Populated only when the database read failed, so the caller can log the
    # reason rather than silently running on fallbacks.
    error: str | None = None

    @property
    def effective_veto_hours(self) -> int:
        """The veto window that actually applies to the next scheduling decision.

        Zero when the human is out of the loop: the window exists to give a person
        time to object, and nobody is listening. Cadence is untouched by this — it
        is `publish_gap_hours`, and it is what stops an unattended engine from
        dumping a backlog in one afternoon.
        """
        return self.veto_window_hours if self.human_in_the_loop else 0

    def describe(self) -> str:
        """One log line naming every value and its authority."""
        parts = [
            f"{name}={getattr(self, name)}({self.sources.get(name, 'default')})"
            for name in ENV_KEYS
        ]
        line = "settings: " + ", ".join(parts)
        return f"{line} [db read failed: {self.error}]" if self.error else line


def _env_bool(name: str) -> bool | None:
    """True/False if the variable is set to something recognisable, else None.

    None means "unset" and is not the same as False — the whole precedence rule
    turns on that distinction. An unparseable value is also None rather than a
    guess, because guessing `AUTOPILOT_ENABLED=maybe` in either direction is worse
    than falling through to the setting the operator actually saved.
    """
    raw = os.environ.get(name)
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    return None


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        return None


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _read_row(db: Any) -> tuple[Mapping[str, Any] | None, str | None]:
    """The settings row, or (None, reason). Never raises: a settings read must not
    be able to crash a tick that would otherwise have published correctly."""
    try:
        rows = (db.table(TABLE).select("*")
                .eq("id", SETTINGS_ROW_ID).limit(1).execute().data or [])
    except Exception as exc:
        return None, str(exc)[:300]
    if not rows:
        # The table exists but is empty. Treated as an error, not as "all defaults",
        # so the safe fallback applies: an empty row is indistinguishable from a
        # migration that half-ran, and neither is consent to publish unattended.
        return None, f"no row with id={SETTINGS_ROW_ID} in {TABLE}"
    return rows[0], None


def load_settings(db: Any) -> Settings:
    """Resolve every switch for this tick: env override, else database, else default."""
    row, error = _read_row(db)

    resolved: dict[str, Any] = {}
    sources: dict[str, str] = {}

    for name, env_key in ENV_KEYS.items():
        is_bool = isinstance(DEFAULTS[name], bool)
        env_value = _env_bool(env_key) if is_bool else _env_int(env_key)

        if env_value is not None:
            resolved[name], sources[name] = env_value, "env"
        elif row is not None and row.get(name) is not None:
            resolved[name], sources[name] = row[name], "db"
        else:
            resolved[name], sources[name] = DEFAULTS[name], "default"

    if error is not None:
        # Failure is not permission. We could not learn what the operator wants,
        # so we stop at the gates rather than ship to a live site unreviewed.
        # Only override where env did not already speak — a host-level
        # HUMAN_IN_THE_LOOP=false is a deliberate instruction, not an unknown.
        if sources["human_in_the_loop"] != "env":
            resolved["human_in_the_loop"], sources["human_in_the_loop"] = True, "fallback"

    return Settings(
        autopilot_enabled=bool(resolved["autopilot_enabled"]),
        human_in_the_loop=bool(resolved["human_in_the_loop"]),
        publish_gap_hours=_clamp(int(resolved["publish_gap_hours"]), GAP_HOURS_MIN, GAP_HOURS_MAX),
        veto_window_hours=_clamp(int(resolved["veto_window_hours"]), VETO_HOURS_MIN, VETO_HOURS_MAX),
        sources=sources,
        error=error,
    )


def env_overrides() -> dict[str, bool | int]:
    """Which settings the host is currently overriding, and to what.

    The dashboard needs this to tell the truth about a switch it cannot change.
    Reading it here rather than duplicating the parsing in TypeScript keeps one
    definition of "what counts as set".
    """
    out: dict[str, bool | int] = {}
    for name, env_key in ENV_KEYS.items():
        is_bool = isinstance(DEFAULTS[name], bool)
        value = _env_bool(env_key) if is_bool else _env_int(env_key)
        if value is not None:
            out[name] = value
    return out
