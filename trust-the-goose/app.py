"""
TRUST THE GOOSE — golf shot tracker + club caddie.  MVP.

The core loop:
  1. Log a shot (club + carry distance)  ->  stored in a SQLite database
  2. See your bag (average distance + spread per club)  ->  GROUP BY in SQL
  3. Ask the Goose for a club at a target distance  ->  with a confidence tier:
        GREEN  "Trust the Goose."          lots of data, tight spread
        YELLOW "The Goose is unsure..."    thin data or wide spread
        RED    "Don't trust the Goose."    almost no data, or out of range

Run it:
    pip install flask
    python app.py
Then open http://127.0.0.1:5000 in your browser.

Everything is heavily commented because this is also a learning project
(Flask routes, SQL, and basic statistics all in one place).
"""

import os
import secrets
import sqlite3
import statistics
from contextlib import contextmanager

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

app = Flask(__name__)
# Signs the session cookie (flash messages + the CSRF token below). Set
# GOOSE_SECRET in the environment for a stable key; a fresh random one per
# start is fine for local use.
app.secret_key = os.environ.get("GOOSE_SECRET") or secrets.token_hex(16)


# --------------------------------------------------------------- tiny CSRF ---
# POST alone doesn't stop another website from auto-submitting a hidden form
# at http://127.0.0.1:5000 while the app is running (a "CSRF" attack) — which
# could quietly delete real shot data. Fix: every form carries a per-session
# token, and any route that changes data checks it.
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


def require_csrf():
    if request.form.get("_csrf") != session.get("_csrf"):
        abort(403)
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "goose.db")

# A standard bag, longest to shortest. (Edit to match your own set.)
CLUBS = [
    "Driver",
    "3-Wood",
    "5-Wood",
    "4-Hybrid",
    "5-Iron",
    "6-Iron",
    "7-Iron",
    "8-Iron",
    "9-Iron",
    "PW",
    "GW",
    "SW",
    "LW",
]


# ------------------------------------------------------------------ database --
@contextmanager
def db():
    """Open a connection where each row acts like a dict (row['club']).

    Classic sqlite3 gotcha: `with conn:` commits/rolls back the transaction
    but does NOT close the connection. This wrapper does both — the inner
    `with conn:` handles the transaction, the finally closes the handle
    (which also matters on Windows, where open handles lock the .db file).
    """
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shots (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                club    TEXT    NOT NULL,
                carry   INTEGER NOT NULL,          -- carry distance in yards
                note    TEXT,
                logged  TEXT    DEFAULT (datetime('now','localtime'))
            )
        """)
        # migration: add lateral miss ('side') for dispersion charts.
        # negative = left, positive = right, 0 = dead straight.
        cols = [r[1] for r in conn.execute("PRAGMA table_info(shots)").fetchall()]
        if "side" not in cols:
            conn.execute("ALTER TABLE shots ADD COLUMN side INTEGER DEFAULT 0")


# ------------------------------------------------------------- the goose math --
def bag_stats():
    """Per-club summary. count + average come straight from SQL (GROUP BY);
    the spread (standard deviation) is computed in Python for accuracy."""
    with db() as conn:
        # SQL does the grouping — this is the query worth learning:
        summary = conn.execute("""
            SELECT club,
                   COUNT(*)   AS n,
                   ROUND(AVG(carry),1) AS avg,
                   MIN(carry) AS min,
                   MAX(carry) AS max
            FROM shots GROUP BY club
        """).fetchall()
        raw = conn.execute("SELECT club, carry FROM shots").fetchall()

    carries = {}
    for r in raw:
        carries.setdefault(r["club"], []).append(r["carry"])

    stats = {}
    for row in summary:
        c = row["club"]
        vals = carries[c]
        stats[c] = {
            "n": row["n"],
            "avg": row["avg"],
            "min": row["min"],
            "max": row["max"],
            # stdev (sample), not pstdev (population): your shots are a SAMPLE
            # of what that club really does. pstdev divides by n and understates
            # the spread when n is small — exactly when honesty matters most.
            # stdev divides by n-1 (Bessel's correction) and is the honest one.
            "std": round(statistics.stdev(vals), 1) if len(vals) > 1 else 0.0,
        }
    # keep bag order — and if a club was renamed in CLUBS, old shots logged
    # under the old name still show at the end instead of silently vanishing
    order = [c for c in CLUBS if c in stats] + sorted(
        c for c in stats if c not in CLUBS
    )
    return {c: stats[c] for c in order}


def ask_goose(target):
    """Given a target carry distance, recommend a club WITH a confidence tier.
    This is the whole brand in one function — and it's honest statistics,
    not decoration."""
    stats = bag_stats()
    if not stats:
        return {
            "tier": "red",
            "club": None,
            "headline": "Don't trust the Goose — I've got no data yet.",
            "detail": "Log a few shots first so the Goose can learn your bag.",
            "target": target,
        }

    # pick the club whose average carry is closest to the target
    club = min(stats, key=lambda c: abs(stats[c]["avg"] - target))
    s = stats[club]
    gap = abs(target - s["avg"])  # how far the target is from that club's avg
    n, std = s["n"], s["std"]

    # compare the target to what you've ACTUALLY logged (real min/max carries),
    # not to club averages — otherwise "outside everything you've logged" could
    # be literally false (avg 240 but a logged 265 exists).
    hi = max(v["max"] for v in stats.values())
    lo = min(v["min"] for v in stats.values())
    out_of_range = target > hi + 15 or target < lo - 15

    # --- the confidence tiers ---
    if out_of_range:
        tier = "red"
        head = "Don't trust the Goose on this one."
        det = (
            f"{target} yds is outside everything you've logged. "
            f"Closest club is the {club} (~{s['avg']} yds)."
        )
    elif n < 2:
        tier = "red"
        head = "Don't trust the Goose — barely any data."
        det = f"Only {n} shot logged with the {club}. Hit a few more and ask again."
    elif n >= 5 and std <= 9 and gap <= max(std, 5):
        tier = "green"
        head = f"Trust the Goose. Pull the {club}."
        det = f"{n} shots, average {s['avg']} yds, tight spread (±{std})."
    else:
        tier = "yellow"
        reason = (
            "wide spread"
            if std > 9
            else "thin data" if n < 5 else "the target's a stretch"
        )
        head = f"The Goose is unsure... probably the {club}."
        det = f"{n} shots, avg {s['avg']} (±{std}) — {reason}."

    return {
        "tier": tier,
        "club": club,
        "headline": head,
        "detail": det,
        "stats": s,
        "target": target,
    }


# ------------------------------------------------------------------- routes ---
@app.route("/", methods=["GET", "POST"])
def log():
    if request.method == "POST":
        require_csrf()
        try:
            club = request.form["club"]
            carry = int(request.form["carry"])
            note = request.form.get("note", "").strip()[:140]  # keep notes short
            side = int(request.form.get("side") or 0)
            side = max(-70, min(70, side))  # keep it realistic
            if club in CLUBS and 10 <= carry <= 400:
                with db() as conn:
                    conn.execute(
                        "INSERT INTO shots (club, carry, side, note) VALUES (?,?,?,?)",
                        (club, carry, side, note),
                    )
                flash(f"Logged: {club} — {carry} yds", "ok")
            else:
                flash("Pick a club and a realistic carry (10–400 yds).", "err")
        except (KeyError, ValueError):
            flash("Please fill in club and carry distance.", "err")
        return redirect(url_for("log"))

    with db() as conn:
        recent = conn.execute(
            "SELECT * FROM shots ORDER BY id DESC LIMIT 12"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS c FROM shots").fetchone()["c"]
    # remember the last club used so range sessions don't mean re-picking
    # the same club after every single shot
    last_club = recent[0]["club"] if recent else None
    return render_template(
        "log.html", clubs=CLUBS, recent=recent, total=total, last_club=last_club
    )


@app.route("/bag")
def bag():
    return render_template("bag.html", stats=bag_stats())


@app.route("/dispersion")
def dispersion():
    """Scatter of every shot: how far left/right (x) vs how far it carried (y),
    one colour per club. This is your shot pattern."""
    with db() as conn:
        rows = conn.execute("SELECT club, carry, side FROM shots").fetchall()
    by = {}
    for r in rows:
        d = by.setdefault(r["club"], {"x": [], "y": []})
        d["x"].append(r["side"] if r["side"] is not None else 0)
        d["y"].append(r["carry"])
    # one Plotly trace per club (so the legend lets you toggle clubs on/off);
    # same renamed-club safety as bag_stats — old names still get a trace
    order = [c for c in CLUBS if c in by] + sorted(c for c in by if c not in CLUBS)
    traces = [
        {
            "name": c,
            "x": by[c]["x"],
            "y": by[c]["y"],
            "mode": "markers",
            "type": "scatter",
            "marker": {"size": 11},
        }
        for c in order
    ]
    return render_template("dispersion.html", traces=traces, has_data=bool(rows))


def adjust_for_weather(target, wind, wdir, temp):
    """Turn the real distance into what it 'plays like' after wind and cold air.
    Headwind and cold make the ball fall short, so you need more club."""
    adj = 0.0
    notes = []
    # plain text with real unicode (−, °), NOT HTML entities: entities would
    # force the template to disable escaping (|safe), which is the exact habit
    # that turns into an XSS hole the day user text joins these strings.
    if wind and wdir == "into":
        a = target * 0.011 * wind          # ~1.1% longer per mph of headwind
        adj += a
        notes.append(f"+{round(a)} into a {wind} mph wind")
    elif wind and wdir == "down":
        a = target * 0.006 * wind          # tailwind helps about half as much
        adj -= a
        notes.append(f"−{round(a)} downwind {wind} mph")
    if temp is not None:
        a = ((72 - temp) / 10.0) * 2.0 * (target / 150.0)   # ~2 yds per 10°F at 150
        if abs(a) >= 1:
            adj += a
            notes.append(f"{'+' if a > 0 else '−'}{abs(round(a))} at {temp}°F")
    return max(10, round(target + adj)), notes


@app.route("/goose", methods=["GET", "POST"])
def goose():
    result = None
    form = request.form if request.method == "POST" else request.args
    target = form.get("target")
    if target:
        try:
            t = int(target)
            if not 10 <= t <= 400:
                raise ValueError
            # never trust the browser's min/max attributes — clamp on the
            # server too (anyone can send any value with curl)
            wind = max(0, min(50, int(form.get("wind") or 0)))
            wdir = form.get("wdir", "none")
            temp = form.get("temp")
            temp = int(temp) if temp not in (None, "") else None
            if temp is not None:
                temp = max(-20, min(120, temp))
            plays, notes = adjust_for_weather(t, wind, wdir, temp)
            result = ask_goose(plays)
            result["actual"] = t
            result["plays_like"] = plays
            result["wx_notes"] = notes
        except (ValueError, TypeError):
            flash("Enter a target between 10 and 400 yds.", "err")
    return render_template("goose.html", result=result, form=form)


# POST-only on purpose: browsers sometimes pre-load plain links (GET) before
# you click them — if deleting were a GET link, hovering could wipe a shot.
# POST means it only happens when the form is actually submitted.
@app.route("/delete/<int:shot_id>", methods=["POST"])
def delete(shot_id):
    require_csrf()
    with db() as conn:
        conn.execute("DELETE FROM shots WHERE id = ?", (shot_id,))
    flash("Shot removed.", "ok")
    return redirect(url_for("log"))


@app.route("/reset", methods=["POST"])
def reset():
    require_csrf()
    with db() as conn:
        conn.execute("DELETE FROM shots")
    flash("All shots cleared.", "ok")
    return redirect(url_for("log"))


# run at import (it's idempotent), so the tables exist no matter how the app
# is started — `python app.py`, `flask run`, or a real server later
init_db()

if __name__ == "__main__":
    print("Trust the Goose running -> http://127.0.0.1:5000")
    # 127.0.0.1 = this computer only. NEVER pair debug=True with
    # host="0.0.0.0": the Werkzeug debug console is remote code execution
    # for anyone on the same network.
    app.run(host="127.0.0.1", debug=True)