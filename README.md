# Seat Snatcher

A Cubbie Skill that watches full ASU classes and **calls you the moment a seat opens.**

We asked Cubbie what it wished it could do. Its answer: reliable access to university registration information, so
it could verify seats. Cubbie can run hourly checks and call you, but it can't read ASU's seat counts on its own.
This Skill gives it that, with a small script that reads ASU's public class search. No login, no keys.

## Install

Text this repository's link to Cubbie and reply "yes":

```
https://github.com/<owner>/seat-snatcher
```

## Try it

- "CHM 113 is full, tell me when a seat opens"
- "how many seats are left in MAT 265 for spring?"
- "watch class 12745 and call me if anything opens"
- "got it, I'm in" (stops watching)

## What happens

```
MAT 265, Spring 2027: 20 sections, 2 full.
Want me to watch #12745 (online, session A)? I'll check every hour, 7 am to midnight, and call you the moment a seat opens.
```

Then, when a seat opens, your phone rings:

```
Seat Snatcher here. A seat just opened in MAT 265, class 12745. Open My ASU and register now.
```

## How it works

- `scripts/seats.py` reads seat counts from the same public data ASU's class search page uses
  (Python standard library only).
- Cubbie runs it on an hourly scheduled check-in and stays silent until a class goes from full to open.
- Seats reserved for certain students are flagged, so you're not called for a seat you can't take.
- You register yourself in My ASU. Cubbie never touches your enrollment or asks for your password.

ASU only for now (all campuses and ASU Online).

Built for the Cubbie Hackathon (Track 1).
