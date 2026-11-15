"""Pure scheduling helpers for Life Blocker (no Gemini calls here).

- expand_fixed:   classes / shifts / gym (or Calendar events) -> concrete busy times
- build_segments: free time each day, split into high / medium / low energy slots
- Planner:        checks proposed blocks and fills anything left with a simple scheduler
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.getenv("CAMPUS_TZ", "America/Los_Angeles"))
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

BUFFER = timedelta(minutes=10)  # travel time around fixed commitments
GAP = timedelta(minutes=10)  # breathing room between planned blocks
MIN_SEGMENT = timedelta(minutes=30)
MIN_CHUNK = timedelta(minutes=30)
MAX_CHUNK = timedelta(minutes=120)

# Waking window per chronotype (start, end)
WINDOWS = {
    "morning": (time(7, 30), time(22, 30)),
    "night": (time(9, 30), time(23, 59)),
}

WORK_WORDS = ("shift", "work", "job", "internship")
GYM_WORDS = ("gym", "workout", "practice", "lift", "training", "run ")
DEEP_WORDS = ("essay", "study", "homework", "exam", "midterm", "final", "problem set",
              "pset", "project", "lab report", "read", "paper", "code", "assignment")


@dataclass
class Busy:
    title: str
    start: datetime
    end: datetime
    kind: str  # "work" | "gym" | "other"
    from_calendar: bool = False  # already on Google Calendar: plan around it, never re-book it


@dataclass
class Segment:
    id: str
    start: datetime
    end: datetime
    energy: str  # "high" | "medium" | "low"
    free: list[tuple[datetime, datetime]] = field(default_factory=list)

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass
class Task:
    title: str
    minutes: int
    energy: str  # "high" | "low"
    due: date | None
    remaining: int = 0

    def __post_init__(self) -> None:
        self.remaining = self.minutes

    @property
    def deadline(self) -> datetime | None:
        """Finish before the due date starts (don't leave it for the day it's due)."""
        if self.due is None:
            return None
        return datetime.combine(self.due, time(0, 0), TZ)


# ---------- parsing ----------

def parse_date(s: str) -> date:
    return date.fromisoformat(str(s)[:10])


def parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(str(s))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def parse_hhmm(s: str) -> time:
    h, m = str(s).strip().split(":")[:2]
    return time(int(h) % 24, int(m))


def kind_of(item: dict) -> str:
    if item.get("kind") in ("work", "gym", "other"):
        return item["kind"]
    title = f" {str(item.get('title', '')).lower()} "
    if any(w in title for w in WORK_WORDS):
        return "work"
    if any(w in title for w in GYM_WORDS):
        return "gym"
    return "other"


def normalize_tasks(raw: list | None) -> list[Task]:
    tasks = []
    for t in raw or []:
        title = str(t.get("title") or "Task").strip()
        try:
            minutes = max(15, int(t.get("minutes") or 60))
        except (TypeError, ValueError):
            minutes = 60
        energy = str(t.get("energy") or "").lower()
        if energy not in ("high", "low"):
            energy = "high" if any(w in title.lower() for w in DEEP_WORDS) else "low"
        due = None
        if t.get("due"):
            try:
                due = parse_date(t["due"])
            except ValueError:
                due = None
        tasks.append(Task(title=title, minutes=minutes, energy=energy, due=due))
    return tasks


# ---------- busy times ----------

def expand_fixed(fixed: list | None, start_d: date, end_d: date) -> list[Busy]:
    """Weekly items ({"days": [...], "start": "10:40"}) or one-off ISO events -> Busy list."""
    out: list[Busy] = []
    for item in fixed or []:
        s, e = item.get("start"), item.get("end")
        if not s:
            continue
        title, kind = str(item.get("title") or "Busy"), kind_of(item)
        cal = bool(item.get("from_calendar"))
        if "T" in str(s):  # one-off event, e.g. from Google Calendar
            bs = parse_dt(s)
            be = parse_dt(e) if e else bs + timedelta(hours=1)
            if be.date() >= start_d and bs.date() <= end_d:
                out.append(Busy(title, bs, be, kind, cal))
            continue
        days = {str(d)[:3].title() for d in (item.get("days") or DAYS)}
        st = parse_hhmm(s)
        et = parse_hhmm(e) if e else None
        d = start_d
        while d <= end_d:
            if DAYS[d.weekday()] in days:
                bs = datetime.combine(d, st, TZ)
                be = datetime.combine(d, et, TZ) if et else bs + timedelta(hours=1)
                if be <= bs:
                    be += timedelta(days=1)
                out.append(Busy(title, bs, be, kind, cal))
            d += timedelta(days=1)
    return sorted(out, key=lambda b: b.start)


# ---------- free time + energy ----------

def subtract(intervals, cut_start, cut_end):
    out = []
    for s, e in intervals:
        if cut_end <= s or cut_start >= e:
            out.append((s, e))
            continue
        if s < cut_start:
            out.append((s, cut_start))
        if cut_end < e:
            out.append((cut_end, e))
    return out


def base_energy(t: datetime, chronotype: str) -> str:
    h = t.hour + t.minute / 60
    if chronotype == "night":
        return "low" if h < 11 else "medium" if h < 16 else "high"
    return "high" if h < 12 else "medium" if h < 17 else "low"


def recovery_windows(busy: list[Busy], job_drain: str) -> list[tuple[datetime, datetime]]:
    """Low-energy time right after a shift or the gym: no deep work there."""
    out = []
    for b in busy:
        if b.kind == "work":
            hours = 2 if job_drain == "high" else 1
            out.append((b.end, b.end + timedelta(hours=hours)))
        elif b.kind == "gym":
            out.append((b.end, b.end + timedelta(hours=1)))
    return out


def build_segments(busy: list[Busy], start_d: date, end_d: date,
                   chronotype: str, job_drain: str) -> list[Segment]:
    chronotype = chronotype if chronotype in WINDOWS else "morning"
    ws, we = WINDOWS[chronotype]
    recovery = recovery_windows(busy, job_drain)
    segments: list[Segment] = []
    d = start_d
    while d <= end_d:
        day_start = datetime.combine(d, ws, TZ)
        day_end = datetime.combine(d, we, TZ)
        free = [(day_start, day_end)]
        for b in busy:
            free = subtract(free, b.start - BUFFER, b.end + BUFFER)

        # cut points where energy can change
        cuts = {datetime.combine(d, time(h), TZ) for h in (11, 12, 16, 17)}
        for rs, re in recovery:
            cuts.update({rs, re})

        pieces = []
        for s, e in free:
            points = sorted(c for c in cuts if s < c < e)
            edges = [s, *points, e]
            for ps, pe in zip(edges, edges[1:]):
                in_recovery = any(rs <= ps < re for rs, re in recovery)
                energy = "low" if in_recovery else base_energy(ps, chronotype)
                if pieces and pieces[-1][1] == ps and pieces[-1][2] == energy:
                    pieces[-1] = (pieces[-1][0], pe, energy)
                else:
                    pieces.append((ps, pe, energy))

        for ps, pe, energy in pieces:
            if pe - ps >= MIN_SEGMENT:
                seg = Segment(f"s{len(segments) + 1}", ps, pe, energy)
                seg.free = [(ps, pe)]
                segments.append(seg)
        d += timedelta(days=1)
    return segments


# ---------- placing blocks ----------

def energy_fits(task_energy: str, seg_energy: str) -> bool:
    return not (task_energy == "high" and seg_energy == "low")


def preference(task_energy: str, seg_energy: str) -> int:
    order = {"high": ["high", "medium", "low"], "low": ["low", "medium", "high"]}
    return order[task_energy].index(seg_energy)


@dataclass
class Placed:
    task: Task
    start: datetime
    end: datetime
    energy: str
    reason: str
    source: str  # "gemini" | "fallback"


class Planner:
    def __init__(self, segments: list[Segment], tasks: list[Task]):
        self.segments = segments
        self.tasks = tasks
        self.placed: list[Placed] = []
        self.rejected: list[str] = []

    def _task(self, title: str) -> Task | None:
        title = title.strip().lower()
        for t in self.tasks:
            if t.title.lower() == title:
                return t
        for t in self.tasks:
            if title in t.title.lower() or t.title.lower() in title:
                return t
        return None

    def _carve(self, seg: Segment, s: datetime, e: datetime) -> None:
        seg.free = [iv for iv in subtract(seg.free, s - GAP, e + GAP) if iv[1] - iv[0] >= timedelta(minutes=15)]

    def try_place(self, title: str, start: str, end: str, reason: str = "", source: str = "gemini") -> bool:
        """Accept a proposed block only if it fits every rule. Returns True if placed."""
        task = self._task(title)
        if task is None or task.remaining <= 0:
            self.rejected.append(f"{title}: unknown task or already scheduled")
            return False
        try:
            s, e = parse_dt(start), parse_dt(end)
        except (ValueError, TypeError):
            self.rejected.append(f"{title}: bad time format")
            return False
        if e - s < timedelta(minutes=15):
            self.rejected.append(f"{title}: block too short")
            return False
        # never give a task more time than it needs
        e = min(e, s + timedelta(minutes=task.remaining))
        if task.deadline and e > task.deadline:
            self.rejected.append(f"{title}: ends after the deadline")
            return False
        for seg in self.segments:
            if not energy_fits(task.energy, seg.energy):
                continue
            if any(fs <= s and e <= fe for fs, fe in seg.free):
                self._commit(task, seg, s, e, reason, source)
                return True
        self.rejected.append(f"{title}: overlaps something or wrong energy slot")
        return False

    def _commit(self, task, seg, s, e, reason, source):
        self._carve(seg, s, e)
        task.remaining -= int((e - s).total_seconds() // 60)
        self.placed.append(Placed(task, s, e, seg.energy, reason, source))

    def fill_remaining(self) -> None:
        """Simple backup scheduler for whatever Gemini didn't place."""
        far = datetime.max.replace(tzinfo=TZ)
        # earliest deadline first; same deadline keeps the listed order (steps of one process)
        order = sorted(self.tasks, key=lambda t: t.deadline or far)
        for task in order:
            candidates = sorted(
                (seg for seg in self.segments if energy_fits(task.energy, seg.energy)),
                key=lambda seg: (preference(task.energy, seg.energy), seg.start),
            )
            for seg in candidates:
                if task.remaining <= 0:
                    break
                for fs, fe in list(seg.free):
                    if task.remaining <= 0:
                        break
                    if task.deadline and fs >= task.deadline:
                        continue
                    limit = min(fe, task.deadline) if task.deadline else fe
                    length = min(timedelta(minutes=task.remaining), limit - fs, MAX_CHUNK)
                    if length < min(MIN_CHUNK, timedelta(minutes=task.remaining)):
                        continue
                    reason = f"{seg.energy.capitalize()}-energy slot that fits a {task.energy}-focus task"
                    self._commit(task, seg, fs, fs + length, reason, "fallback")

    def events(self) -> list[dict]:
        out = []
        for p in sorted(self.placed, key=lambda p: p.start):
            out.append({
                "title": p.task.title,
                "start": p.start.isoformat(),
                "end": p.end.isoformat(),
                "location": None,
                "description": f"{p.reason} ({p.energy} energy)".strip(),
                "source": "plan",
                "confidence": 0.9 if p.source == "gemini" else 0.75,
            })
        return out

    def unscheduled(self) -> list[dict]:
        return [
            {"task": t.title, "minutes_left": t.remaining,
             "why": "Not enough free time at the right energy level before it's due"}
            for t in self.tasks if t.remaining > 0
        ]
