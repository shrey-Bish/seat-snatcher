---
name: seat-snatcher
description: Watches full ASU classes and phones the student the moment a seat opens, with the link to register. Use when a student says a class they need is full, asks how many seats are open in an ASU course or class number, wants to be texted or called when a seat opens, or wants to stop watching a class. Reads Arizona State University's public class search with a small script (all campuses and ASU Online), so it needs no sign-in. Cubbie cannot read those seat counts on its own.
---

# Seat Snatcher

Registration season means full classes. Students refresh the class search for days and still miss the one seat
that opens at 2 pm on a Tuesday. This Skill reads live seat counts from ASU's public class search, checks the
classes the student cares about every hour, and calls the student the moment a seat opens, so they can grab it in
My ASU before anyone else.

It uses one script (`scripts/seats.py`, Python standard library only, no setup, no keys) plus Cubbie's
**reminders and scheduled check-ins** (including phone calls) and **memory**. Cubbie never registers, swaps or drops
a class for the student; the student does that in My ASU.

## When to use

- "CHM 113 is full, tell me when a seat opens"
- "watch class 34674 and call me if anything opens"
- "how many seats are left in MAT 265 for spring?"
- "is there any open section of ECN 211 on Tempe campus?"
- "stop watching CHM 113" / "got it, I'm in"

Only for Arizona State University. If the student is at another school, say: "Seat Snatcher only reads ASU's class
search for now." Then stop.

## Replies

Short, plain text, one idea per message, no Markdown. Put each link on its own line. Ask one question at a time
and suggest a default the student can accept with "yes".

## 1. Find the class

1. Get the course ("MAT 265") or a 5-digit class number ("12745"). If the student only gives a name ("calc 1"),
   ask for the course code.
2. Get the term. Default to the term students are registering for now: from October to January that is the coming
   Spring; from February to May it is the coming Fall (ask if they mean Summer). Say the term you used. The script
   takes names like "Spring 2027".
3. List the sections, from this Skill's folder:

   `python3 scripts/seats.py list --course "MAT 265" --term "Spring 2027"`

   Add `--campus TEMPE` (or POLY, DOWNTOWN, WEST, ONLINE) if the student named a campus, and `--full-only` if there
   are many sections and the student wants a full one watched. Each line shows the class number, the component
   (LEC, REC, LAB), section, campus, days and time, instructor, and seats ("FULL (120/120)" or "3 open of 42").
4. **Linked sections.** Many courses pair each lecture with recitations or labs, and the student needs a seat in
   each. The script lists the main sections and, under each one, a "needs a REC:" or "needs a LAB:" line with the
   linked sections and their seats; the student needs one of each. A lecture with seats whose recitations or labs are
   all full is marked "[blocked: ...]". Explain it in one line when it applies ("Lecture 1001 has room, but both of
   its recitations are full").
5. Text a short summary: how many sections the student could get into now, and how many are full or blocked. If one
   they can get into fits what they said, say so first: the fastest fix is a section that already has room.
   Some open seats are reserved for certain students (a major, a program); the script says so. Tell the student to
   check the class page for who the reserved seats are for.

## 2. Set up the watch (only with the student's yes)

1. Ask which class numbers to watch (a student can watch several sections of the same course).
2. Propose the plan and wait for "yes":
   "I'll check #12745 every hour, 7 am to midnight, and call you the moment a seat opens. OK?"
   The student can change how often (every hour is the default and the most this Skill uses), the hours, and call or
   text only. Save the choices with Cubbie's **memory**.
3. After "yes", run one check right away. It records the starting point, and it tells the student at once if a seat
   is already open:

   `python3 scripts/seats.py check --class 12745 --class 34674 --term "Spring 2027"`

4. Create one recurring scheduled check-in with Cubbie's **reminders and scheduled check-ins**, at the times the
   student chose. Word it so it makes sense on its own when it fires, for example:

   "Seat Snatcher check for the student: from the seat-snatcher Skill folder, run
   python3 scripts/seats.py check --class 12745 --class 34674 --term "Spring 2027"
   and act on the exit code as the Skill says (10: call and text; 11: text; 0: send nothing)."

5. Confirm in one line: which classes, how often, and that the first check already ran.

## 3. What each check does

Run the command in the check-in and act on its exit code. Send nothing when nothing changed.

| Exit code | Meaning | What Cubbie does |
| --- | --- | --- |
| 0 | Nothing the student can enroll in yet | Nothing. Stay silent. (On the first check, pass on what the script printed, such as "has a seat, but every linked recitation is full".) |
| 10 | The student can enroll now: an unreserved seat, and room in a linked section if the course has them | Call the student (if calls are on and it is within their hours), then text. |
| 11 | Only reserved seats opened | Text only: the seat may not be open to them. |
| 2 | ASU's class search did not answer | Nothing. If it fails 3 checks in a row, text once: "ASU's class search isn't answering, I'll keep trying." |
| 3 | The class number was not found | Text once with the number, ask the student to check it, and pause that class. |

The script alerts only when a class goes from "can't get in" to "can get in", so an open seat never triggers a call
every hour. For a lecture, it waits until one of its linked recitations or labs also has room (and the reverse when
the student watches a recitation or lab).

**The call** says, in a few words: "Seat Snatcher here. A seat just opened in MAT 265, class 12745. Open My ASU and
register now. The link is in your texts."
**The text** right after gives the course, the class number, the seats open, any linked section with room that
the student must add at the same time (the script names them: "these have room: #21671 (REC)"), and the class page link the
script printed, on its own line. Then: "Reply 'got it' when you're in, and I'll stop watching."

## 4. Stop watching

When the student says they got the seat, asks to stop, or drops the idea:

1. Run `python3 scripts/seats.py forget --class 12745 --term "Spring 2027"`.
2. Delete that class from the scheduled check-in (delete the check-in if no classes are left).
3. Confirm in one line.

If a watch has run for 14 days, text once to ask whether to keep going. Stop all watches for a term after its last
day to add classes, after telling the student.

## Ground rules

- Never register, swap, drop or join a waitlist for the student, and never ask for their ASU password. Registering
  happens in My ASU, by the student.
- Seat counts change by the minute. A check every hour can miss a seat that opens and fills between checks; say so if
  the student asks why they missed one.
- Report only what the script printed. Never guess a seat count.

## When something fails

- The script prints "Could not reach ASU class search": try once more on the next check; do not retry in a loop.
- A course has no sections that term: say so, and ask whether they meant another term.
- The student is not at ASU: say the Skill only covers ASU for now.

## Trying it without ASU

`python3 scripts/seats.py check --class 12745 --term "Spring 2027" --sample` uses bundled data (class 12745 is
full). Running it again with `--sample after` simulates a seat opening (exit code 10). Sample runs keep their own
state and never touch the student's watches.
