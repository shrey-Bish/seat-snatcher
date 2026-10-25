# Seat Snatcher

A Cubbie Skill that watches full ASU classes and **calls you the moment a seat opens**, then texts you a one-tap
link that adds the class in My ASU.

We asked Cubbie what it wished it could do. Its answer: reliable access to university registration information, so
it could verify seats. Cubbie can run hourly checks and call you, but it can't read ASU's seat counts on its own.
This Skill gives it that, with a small script that reads ASU's public class search. No login, no keys.

## Install

Text this link to Cubbie and reply "yes":

```
https://github.com/shrey-Bish/seat-snatcher
```

## Try it

- "CHM 113 is full, tell me when a seat opens"
- "how many seats are left in MAT 265 for spring?"
- "watch class 12745 and call me if anything opens"
- "I'm in the 8 am section, swap me into 12745 if it opens"
- "got it, I'm in" (stops watching)

## What happens

```
MAT 265, Spring 2027: 1 section you can get into now, 1 full.
Want me to watch #12745? I'll check every hour, 7 am to midnight, and call you the moment a seat opens.
```

When a seat opens, your phone rings:

```
Seat Snatcher here. A seat just opened in MAT 265, class 12745. Open My ASU and register now.
The link is in your texts.
```

Then the text:

```
A seat opened in MAT 265, #12745 (1 open of 120).
Add it (one tap, opens My ASU):
https://www.asu.edu/go/addclass/?STRM=2271&ASU_CLASS_NBR=12745
```

## What makes it different

- **Lecture + lab, together.** Many courses need a lecture and a recitation or lab. A lecture with seats is useless
  if every linked lab is full, so Seat Snatcher only calls when you can actually get into both.
- **One tap to enroll.** The text links to ASU's own add page with the class (and its lab or recitation) already
  filled in. You sign in and confirm.
- **Swap, don't drop.** Already in another section? The link uses ASU's Swap, which keeps your current seat until
  the new one is confirmed, so you never end up with neither.
- **No false alarms.** Seats reserved for certain majors or programs are flagged, and you get one call when a class
  goes from full to open, not one every hour.

## How it works

- `scripts/seats.py` reads seat counts from the same public data ASU's class search page uses
  (Python standard library only).
- Cubbie runs it on an hourly scheduled check-in and stays silent until something you can take opens up.
- You register yourself in My ASU. Cubbie never touches your enrollment or asks for your password.

ASU only for now (all campuses and ASU Online).

## Try it without ASU

```
python3 scripts/seats.py check --class 12745 --term "Spring 2027" --sample
python3 scripts/seats.py check --class 12745 --term "Spring 2027" --sample after
```

The first run shows the class full. The second simulates a seat opening (exit code 10) and prints the one-tap link.

Built for the Cubbie Hackathon (Track 1) by Enrollment Goblins.
