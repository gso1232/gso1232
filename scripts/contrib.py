#!/usr/bin/env python3
"""
Pull the last year of daily contribution counts for one user and write
data/contributions.json with everything the two cards draw: the days, the
streaks, the best day, active days and the monthly totals.

The query goes through `gh api graphql`, so gh owns the auth: locally that is
your gh login, in Actions it is the GH_TOKEN the workflow hands it.

    python scripts/contrib.py [login]
"""
import datetime as dt
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGIN = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PROFILE_USER", "gso1232")
OUT = os.path.join(ROOT, "data", "contributions.json")

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}"""

LEVEL = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
         "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def fetch():
    raw = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={QUERY}", "-F", f"login={LOGIN}"],
        capture_output=True, text=True, check=True, encoding="utf-8",
    ).stdout
    weeks = json.loads(raw)["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [
        {"date": d["date"], "count": d["contributionCount"], "level": LEVEL[d["contributionLevel"]]}
        for w in weeks for d in w["contributionDays"]
    ]


def run_at(days, end):
    """Length and first index of the run of active days ending at `end`."""
    i = end
    while i >= 0 and days[i]["count"] > 0:
        i -= 1
    return end - i, i + 1


def streaks(days):
    # today is still going: a zero today does not break yesterday's run
    end = len(days) - 1
    if days[end]["count"] == 0:
        end -= 1
    cur_len, cur_start = run_at(days, end)
    current = {"length": cur_len,
               "start": days[cur_start]["date"] if cur_len else None,
               "end": days[end]["date"] if cur_len else None}

    longest = {"length": 0, "start": None, "end": None}
    for i, d in enumerate(days):
        if d["count"] and (i + 1 == len(days) or not days[i + 1]["count"]):
            n, s = run_at(days, i)
            if n > longest["length"]:
                longest = {"length": n, "start": days[s]["date"], "end": d["date"]}
    return current, longest


def summarise(days):
    total = sum(d["count"] for d in days)
    active = sum(1 for d in days if d["count"])
    best = max(days, key=lambda d: d["count"])
    current, longest = streaks(days)

    months = {}
    for d in days:
        months[d["date"][:7]] = months.get(d["date"][:7], 0) + d["count"]

    return {
        "login": LOGIN,
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "total": total,
        "active_days": active,
        "per_active_day": round(total / active, 1) if active else 0.0,
        "current_streak": current,
        "longest_streak": longest,
        "best_day": {"date": best["date"], "count": best["count"]},
        "months": [{"month": k, "count": v} for k, v in sorted(months.items())],
        "days": days,
    }


if __name__ == "__main__":
    data = summarise(fetch())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    print(f"{LOGIN}: {data['total']} contributions over {data['active_days']} active days, "
          f"current streak {data['current_streak']['length']}, "
          f"longest {data['longest_streak']['length']}")
