"""
REAL DATA MODE — live vulnerability intelligence, no synthetic anything.

Pulls two real, free, industry-standard feeds (no API key needed):

  1. CISA KEV  — the US government's Known Exploited Vulnerabilities catalog.
                 Every entry is a CVE confirmed exploited by attackers in the
                 real world. Federal agencies are required by law (BOD 22-01)
                 to patch from this list.
  2. EPSS      — Exploit Prediction Scoring System from FIRST.org. A live ML
                 model giving each CVE a probability (0-1) of being exploited
                 in the next 30 days.

We merge them and rank: what is being exploited AND likely to keep being
exploited AND tied to ransomware = top of the queue.

Run:    python real_feeds.py        (needs internet)
Output: real_vulns.csv, real_dashboard.html

Honest note: a company would join this list against ITS OWN asset inventory
("do we even run this product?") — that's the 'contextual' part of contextual
risk. We have no inventory, so this ranks the global threat list. The
synthetic pipeline (asset_importance, environment) shows exactly what that
inventory join would add.
"""
import io
import json
import urllib.request

import numpy as np
import pandas as pd

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
EPSS_URL = "https://epss.cyentia.com/epss_scores-current.csv.gz"

GOLD, INK, DIM, RED, GREEN, BLUE = "#e7dba8", "#c9d4e4", "#5a687d", "#e0736a", "#7fd88f", "#8fb8d8"


def fetch_kev():
    req = urllib.request.Request(KEV_URL, headers={"User-Agent": "aspm-mini student project"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.load(r)
    kev = pd.DataFrame(data["vulnerabilities"])
    print(f"      CISA KEV catalog v{data.get('catalogVersion','?')}: {len(kev)} exploited CVEs")
    return kev


def fetch_epss():
    # Download with an explicit timeout, THEN parse. pd.read_csv(url) opens
    # the connection with no timeout at all — one stalled server and the
    # whole control panel hangs forever behind its run lock.
    req = urllib.request.Request(
        EPSS_URL, headers={"User-Agent": "aspm-mini student project"}
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        buf = io.BytesIO(r.read())
    # first line of the file is a metadata comment, so skip it
    epss = pd.read_csv(buf, compression="gzip", skiprows=1)
    print(f"      EPSS scores: {len(epss):,} CVEs scored")
    return epss


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def bar_chart(title, pairs, color, fmt="{:.0f}", width=460):
    if not pairs:
        return ""
    vmax = max(v for _, v in pairs) or 1
    bar_h, gap, label_w = 24, 9, 190
    h = len(pairs) * (bar_h + gap) + 34
    out = [f'<svg width="{width}" height="{h}" xmlns="http://www.w3.org/2000/svg">',
           f'<text x="0" y="15" fill="{DIM}" font-size="11" letter-spacing="2" '
           f'font-family="monospace">{esc(title).upper()}</text>']
    y = 28
    for label, val in pairs:
        w = max(2, (width - label_w - 66) * val / vmax)
        out.append(f'<text x="{label_w-8}" y="{y+16}" fill="{INK}" font-size="11.5" '
                   f'text-anchor="end" font-family="monospace">{esc(str(label)[:24])}</text>')
        out.append(f'<rect x="{label_w}" y="{y}" width="{w:.0f}" height="{bar_h}" rx="3" fill="{color}"/>')
        out.append(f'<text x="{label_w+w+7:.0f}" y="{y+16}" fill="{GOLD}" font-size="11.5" '
                   f'font-family="monospace">{fmt.format(val)}</text>')
        y += bar_h + gap
    out.append("</svg>")
    return "".join(out)


def main():
    print("[real 1/3] Downloading live feeds...")
    kev = fetch_kev()
    epss = fetch_epss()

    print("[real 2/3] Merging and ranking...")
    df = kev.merge(epss, left_on="cveID", right_on="cve", how="left")
    df["epss"] = df["epss"].fillna(df["epss"].median())
    df["ransomware"] = df["knownRansomwareCampaignUse"].eq("Known")
    added = pd.to_datetime(df["dateAdded"], errors="coerce")
    days_old = (pd.Timestamp.today().normalize() - added).dt.days.fillna(9999)

    # Risk = likelihood of continued exploitation, amplified by ransomware use
    # and by being a fresh addition to the exploited list.
    df["risk_score"] = (
        df["epss"]
        * np.where(df["ransomware"], 1.5, 1.0)
        * np.where(days_old <= 90, 1.2, 1.0)
        * 100
    ).clip(upper=100).round(1)

    df = df.sort_values("risk_score", ascending=False).reset_index(drop=True)
    df.insert(0, "priority_rank", df.index + 1)

    keep = ["priority_rank", "cveID", "vendorProject", "product", "vulnerabilityName",
            "dateAdded", "epss", "percentile", "ransomware", "risk_score", "shortDescription"]
    df[keep].to_csv("real_vulns.csv", index=False)

    print("[real 3/3] Building real_dashboard.html...")
    total = len(df)
    n_ransom = int(df["ransomware"].sum())
    n_recent = int((days_old <= 30).sum())
    med_epss = df["epss"].median()

    kpis = [
        ("Exploited CVEs (KEV)", f"{total:,}", INK),
        ("Ransomware-linked", f"{n_ransom:,} ({n_ransom/total:.0%})", RED),
        ("Added last 30 days", f"{n_recent}", GOLD),
        ("Median EPSS", f"{med_epss:.1%}", BLUE),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="v" style="color:{c}">{v}</div>'
        f'<div class="k">{k}</div></div>' for k, v, c in kpis)

    top_vendors = df["vendorProject"].value_counts().head(8)
    charts = (
        bar_chart("Most-exploited vendors (KEV entries)",
                  list(top_vendors.items()), BLUE)
        + bar_chart("Highest exploitation probability (EPSS)",
                    [(r["cveID"], r["epss"] * 100) for _, r in df.head(8).iterrows()],
                    RED, "{:.0f}%")
    )

    cols = ["priority_rank", "cveID", "vendorProject", "product", "epss", "ransomware",
            "dateAdded", "risk_score"]
    head = "".join(f"<th>{c.replace('_',' ')}</th>" for c in cols)
    body = ""
    for _, r in df.head(15).iterrows():
        tds = "".join(
            f"<td>{r[c]:.2f}</td>" if c == "epss" else f"<td>{esc(r[c])}</td>" for c in cols)
        body += f"<tr title=\"{esc(r['vulnerabilityName'])}\">{tds}</tr>"

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>ASPM Mini — Live Threat Feed</title>
<style>
body{{background:#04060a;color:{INK};font:13px/1.5 ui-monospace,Consolas,monospace;
     padding:26px;max-width:1150px;margin:0 auto}}
h1{{font:600 20px/1 system-ui,sans-serif;letter-spacing:.25em;text-transform:uppercase;
    color:{GOLD};margin:0 0 4px}}
.sub{{color:{DIM};font-size:11px;letter-spacing:.1em;text-transform:uppercase;margin-bottom:24px}}
.row{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:22px}}
.kpi{{background:#080c13;border:1px solid #18202e;border-radius:10px;padding:16px 20px;flex:1;min-width:170px}}
.kpi .v{{font:600 22px/1.2 system-ui,sans-serif}}
.kpi .k{{color:{DIM};font-size:10px;letter-spacing:.14em;text-transform:uppercase;margin-top:6px}}
.panel{{background:#080c13;border:1px solid #18202e;border-radius:10px;padding:18px;margin-bottom:22px}}
.panel h2{{font:600 11px/1 system-ui,sans-serif;letter-spacing:.2em;text-transform:uppercase;
          color:{DIM};margin:0 0 14px}}
svg{{margin-right:28px;margin-bottom:10px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th,td{{padding:7px 9px;border-bottom:1px solid #131a26;text-align:left}}
th{{color:{DIM};font-size:9.5px;letter-spacing:.13em;text-transform:uppercase}}
tr:first-child td{{color:{GOLD};font-weight:600}}
.note{{color:{DIM};font-size:11.5px;line-height:1.7}}
</style></head><body>
<h1>Live Threat Feed</h1>
<div class="sub">real data · CISA KEV + FIRST.org EPSS · fetched by real_feeds.py</div>
<div class="row">{kpi_html}</div>
<div class="panel"><h2>The landscape</h2>{charts}</div>
<div class="panel"><h2>Top 15 — highest continued-exploitation risk (hover a row for the CVE name)</h2>
<table><tr>{head}</tr>{body}</table></div>
<div class="panel"><h2>Method</h2>
<p class="note">risk = EPSS probability × 1.5 if used in ransomware campaigns × 1.2 if added to KEV
in the last 90 days. Every CVE here is already confirmed exploited in the wild — this ranks which
fires are still spreading. Next step for full context: join against an asset inventory
("do we run this product?"), which is what the synthetic pipeline's asset_importance and
environment columns demonstrate.</p></div>
</body></html>"""

    with open("real_dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"      Done. {total} real exploited CVEs ranked -> real_vulns.csv, real_dashboard.html")
    t = df.iloc[0]
    print(f"      #1 right now: {t['cveID']} — {t['vendorProject']} {t['product']} "
          f"(EPSS {t['epss']:.0%}, ransomware: {'yes' if t['ransomware'] else 'no'})")


if __name__ == "__main__":
    main()
