# Paranoid Penguin

A little desktop app that checks how locked-down my own computer and home network
actually are, gives the whole thing a plain letter grade — A through F — and hands
me a short list of what to fix first.

I built it while teaching myself security and data science. I kept running into terms
like "attack surface" and "posture management" and wanted to actually *see* my own
instead of taking some vendor's word for it. Turns out you can do a stripped-down
version of what the big enterprise tools do at home, with a weekend and some Python.
So I did.

The penguin's paranoid so you don't have to be.

![Paranoid Penguin](logo.png)

## What it actually does

Open it and you get one screen with buttons. Each one runs a check and drops the
result into a dashboard with your grade sitting at the top:

- **Threat intel** — pulls the day's list of vulnerabilities that are actually being
  exploited out in the wild, straight from CISA and EPSS (the same feeds the pros watch).
- **Computer scan** — what's installed, which ports are open, whether your firewall and
  antivirus are actually on.
- **App audit** — checks your Python packages against real CVE databases and tells you
  exactly what to update.
- **Hardening audit** — a stripped-down CIS benchmark: disk encryption, UAC, Remote
  Desktop, that ancient SMBv1 protocol, the guest account, update history. Every finding
  is tagged with the MITRE ATT&CK technique it defends against, because that's how real
  security teams talk about this stuff.
- **Startup review** — everything that launches when you boot, which is exactly where
  malware likes to hide so it survives a restart.
- **Login monitor** — reads the Windows log for a pile of failed sign-ins, i.e. someone
  sitting there trying to guess their way in.
- **Network map** — every device on my network, and it yells if a new one shows up that
  it hasn't seen before.
- **Connection monitor** — shows what my PC is talking to *right now*: every live outbound
  connection, the program behind it, and the server it's reaching. This is how you catch
  malware phoning home.
- **Wi-Fi audit** — checks whether the network I'm on is actually encrypted, and flags any
  open networks my laptop has saved (the thing that gets you at coffee shops).

## Running it

You'll need Python (grab it from python.org and tick the "Add to PATH" box during the
install). Then just double-click **`Start-ParanoidPenguin.bat`** and it opens in your
browser.

Right-click it and "Run as administrator" if you want the disk-encryption and login
checks — those two need the extra permission to read.

First-time setup (the threat feed and computer scan need pandas/numpy):

```
pip install -r requirements.txt
```

Two optional add-ons switch on two of the checks:
- `pip install pip-audit` for the app audit
- `winget install Insecure.Nmap` for the network map

Want it to run itself? **`Schedule-Weekly.bat`** sets up an automatic scan every Sunday
so I don't have to remember. **`Build-EXE.bat`** bundles the whole thing into a single
`.exe` you can hand to someone who doesn't have Python.

## A word on privacy

The results describe *my machine* — open ports, installed software, the devices on my
network. That's basically a treasure map for anyone who wants to break in, so it does
**not** belong on the public internet. The included `.gitignore` keeps all of it out of
the repo automatically. If you fork this: don't commit your scan output, and blur your
screenshots.

## Where I'm honest about it

This is a learning project and I'd rather tell you what it isn't than oversell it:

- The "your software matches a known-exploited product" check matches on *names*, not
  version numbers yet — so treat those as "go check whether you're patched," not "you're
  definitely owned." The Python audit *does* compare versions, so that one you can trust.
- A real posture-management platform runs around the clock on a server watching an entire
  company. This runs on my laptop when I click a button. Same idea, a lot smaller.

## What's next

Things I want to add: a grade that tracks over time so I can watch myself get more
secure, buttons that fix the easy stuff for me, and smarter matching to kill the false
alarms.

---

Built by **Carlos Abel Vivanco** — [AbleV Labs](https://ablevlabs.com).
