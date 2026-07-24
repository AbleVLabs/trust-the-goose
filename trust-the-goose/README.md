# 🦢 Trust the Goose

A golf shot tracker and club caddie. Log your shots, the Goose learns your **real**
distances, then calls the club for any target &mdash; and tells you how far to trust the call:

- 🟢 **Trust the Goose** — plenty of shots with that club, tight spread.
- 🟡 **The Goose is unsure** — thin data or a wide spread.
- 🔴 **Don't trust the Goose** — barely any data, or you're asking for a distance outside your range.

Every number comes from shots *you* log. No sample data, no made-up averages.

Built by **AbleV Labs**.

## Run it

```
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000**. (On Windows, double-click **`Start-Goose.bat`**.)

Start on the **Log a shot** page and enter a few real carries. Once the bag has data,
**Ask the Goose** and **Dispersion** come alive.

## What's inside

| Page | What it does | The skill behind it |
|---|---|---|
| **Log a shot** | Save a club, carry, and left/right miss to the database | Flask forms, SQL `INSERT` |
| **My bag** | Your average distance and spread per club | SQL `GROUP BY`, standard deviation |
| **Dispersion** | Every shot plotted — left/right vs carry, one colour per club | Plotly scatter, per-club traces |
| **Ask the Goose** | Calls a club for a target, adjusted for wind and temperature, with a confidence tier | Basic statistics + weather math |

The database is **SQLite** (`goose.db`, created automatically) — real SQL, zero setup.

## How the confidence works

Honest math, not decoration. For a target distance, the Goose picks the club whose
average carry is closest, then grades its own confidence on three things:

1. **How many shots** you've logged with that club — more shots, more certainty.
2. **How tight the spread is** — a low standard deviation earns trust.
3. **Whether the target is inside your logged range** — ask for 300 when your longest is 250 and you get a 🔴. The Goose won't pretend.

## Playing conditions

On **Ask the Goose**, add wind and temperature and the Goose shows what the shot
*plays like* before it picks a club — headwind and cold air both cost you distance.

## Roadmap

- 📉 ML carry prediction (scikit-learn) — learn from conditions, not just averages
- 🌍 Interactive hole / course map
- 📊 Handicap dashboard · 📋 round history · 📄 PDF / Excel export
- Move to MySQL/PostgreSQL when it outgrows SQLite

---

*Trust the Goose · by AbleV Labs*
