#!/usr/bin/env python3
"""Seat Snatcher: read live seat counts from ASU's public class search.

Commands (run from the Skill folder):
  python3 scripts/seats.py list  --course "MAT 265" --term "Spring 2027" [--campus TEMPE] [--full-only | --open-only]
  python3 scripts/seats.py check --class 12745 [--class 34674 ...] --term "Spring 2027"
  python3 scripts/seats.py forget --class 12745 --term "Spring 2027"

Add --sample to any command to use the bundled files in assets/ instead of ASU (no network);
--sample after uses a second snapshot in which a seat has opened. Sample runs keep their own state file.

Exit codes:
  0   checked, nothing new to report
  10  a watched class has an open seat that is not reserved (call the student)
  11  only reserved seats opened (text the student; the seat may not be open to them)
  2   ASU's class search could not be reached or answered with an error
  3   no class matched
  4   bad arguments
Only Python's standard library is used.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://eadvs-cscc-catalog-api.apps.asu.edu/catalog-microservices/api/v1/search/classes"
PAGE = "https://catalog.apps.asu.edu/catalog/classes/classlist"
HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "assets")
STATE_DIR = os.path.join(os.path.expanduser("~"), ".config", "seat-snatcher")
SEASONS = {"spring": "1", "summer": "4", "fall": "7"}
SEASON_NAMES = {v: k.capitalize() for k, v in SEASONS.items()}


class UserError(Exception):
    """Bad input; message is shown to the student as is."""


def term_code(text):
    """'2271' or 'Spring 2027' or 'spring 27' -> '2271'."""
    t = (text or "").strip().lower()
    if re.fullmatch(r"2\d{2}[147]", t):
        return t
    m = re.fullmatch(r"(spring|summer|fall)\s*'?(\d{2}|\d{4})", t)
    if not m:
        raise UserError(f'Unknown term "{text}". Use a name like "Spring 2027" or a code like 2271.')
    year = m.group(2)[-2:]
    return "2" + year + SEASONS[m.group(1)]


def term_name(code):
    return f"{SEASON_NAMES.get(code[-1], '?')} 20{code[1:3]}"


def page_link(term, class_nbr=None, subject=None, number=None):
    q = {"term": term, "campusOrOnlineSelection": "A", "honors": "F", "promod": "F", "searchType": "all"}
    if class_nbr:
        q["keywords"] = class_nbr
    else:
        q["subject"], q["catalogNbr"] = subject, number
    return PAGE + "?" + urllib.parse.urlencode(q)


def enroll_link(term, c, course, swap_from=None):
    """ASU's own one-tap enroll link (the one its class search 'Add' button opens), with the linked
    recitation/lab pre-filled when the course has them. With swap_from, it uses ASU's Swap instead,
    which keeps the student's current section until the new one is confirmed."""
    main, rels = c, []
    if not is_main(c):
        mains = [p for p in required_partners(c, course) if is_main(p) and seats(p)[4] > 0]
        if mains:
            main, rels = mains[0], [c]
    for kind, lst in sorted(partner_sets(main, course).items()):
        if rels and any(comp(r) == kind for r in rels):
            continue
        free = [p for p in lst if seats(p)[4] > 0]
        if free:
            rels.append(free[0])
    action = "swapclass" if swap_from else "addclass"
    q = [("STRM", term), ("ASU_CLASS_NBR", main["CLAS"]["CLASSNBR"])]
    if swap_from:
        q.append(("ASU_SWAP_CLASS", str(swap_from)))
    for i, r in enumerate(rels[:2], 1):
        q.append((f"relClass{i}", r["CLAS"]["CLASSNBR"]))
    return f"https://www.asu.edu/go/{action}/?" + urllib.parse.urlencode(q)


def fetch(params, sample=None):
    if sample:
        name = "sample_classes_after.json" if sample == "after" else "sample_classes.json"
        with open(os.path.join(ASSETS, name)) as f:
            data = json.load(f)
        classes = data.get("classes", [])
        if "keywords" in params:
            classes = [c for c in classes if c["CLAS"]["CLASSNBR"] == params["keywords"]]
        if "subject" in params:
            classes = [c for c in classes
                       if c["CLAS"]["SUBJECT"] == params["subject"] and c["CLAS"]["CATALOGNBR"] == params["catalogNbr"]]
        return classes
    q = {"refine": "Y", "campusOrOnlineSelection": "A", "honors": "F", "promod": "F", "searchType": "all"}
    q.update(params)
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(q), headers={
        # ASU's own class search page sends this header; the data is public and needs no login.
        "Authorization": "Bearer null",
        "Accept": "application/json",
        "Origin": "https://catalog.apps.asu.edu",
        "Referer": "https://catalog.apps.asu.edu/",
        "User-Agent": "Mozilla/5.0 (seat-snatcher Cubbie Skill)",
    })
    last = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r).get("classes", [])
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            time.sleep(2)
    raise ConnectionError(f"Could not reach ASU class search ({last}).")


def seats(c):
    """Return (cap, taken, open, reserved_open, unreserved_open)."""
    info = c.get("seatInfo") or {}
    clas = c["CLAS"]
    cap = int(info.get("ENRL_CAP", clas.get("ENRLCAP") or 0) or 0)
    taken = int(info.get("ENRL_TOT", clas.get("ENRLTOT") or 0) or 0)
    open_ = max(0, cap - taken)
    reserved_open = sum(max(0, int(r.get("ENRL_CAP") or 0) - int(r.get("ENRL_TOT") or 0))
                        for r in (c.get("reservedSeatsInfo") or []))
    reserved_open = min(reserved_open, open_)
    return cap, taken, open_, reserved_open, open_ - reserved_open


def when(c):
    clas = c["CLAS"]
    days = " ".join(d for d in (c.get("DAYLIST") or []) if d).strip()
    if clas.get("STARTTIME") and clas.get("ENDTIME"):
        return f"{days} {clas['STARTTIME']}-{clas['ENDTIME']}".strip()
    return "online" if clas.get("INSTRUCTIONMODE") in ("OL", "ICOURSE") or clas.get("LOCATION") == "ASUONLINE" else "time TBA"


def comp(c):
    """This section's component: LEC, REC, LAB, ..."""
    clas = c["CLAS"]
    return (clas.get("COMPONENTPRIMARY") or clas.get("SSRCOMPONENT") or "LEC").upper()


def is_main(c):
    """True for the course's main component (usually the lecture)."""
    clas = c["CLAS"]
    main = (clas.get("SSRCOMPONENT") or "LEC").upper()
    return comp(c) == main


def group_key(c):
    """Sections that must be taken together share this key (a lecture and its recitations or labs)."""
    clas = c["CLAS"]
    if not clas.get("ASSOCIATEDCLASS"):
        return None
    return (clas.get("SUBJECT"), clas.get("CATALOGNBR"), clas.get("CAMPUS"), clas.get("SESSIONCODE"),
            str(clas.get("ASSOCIATEDCLASS")))


def partner_sets(c, course):
    """Linked sections the student also needs, by component: {"REC": [...], "LAB": [...]}.
    The student needs one section of every other component in the group (a lecture plus one recitation
    plus one lab, for example)."""
    key = group_key(c)
    if key is None:
        return {}
    sets = {}
    for x in course:
        if group_key(x) == key and x["CLAS"]["CLASSNBR"] != c["CLAS"]["CLASSNBR"] and comp(x) != comp(c):
            sets.setdefault(comp(x), []).append(x)
    return sets


def required_partners(c, course):
    return [x for lst in partner_sets(c, course).values() for x in lst]


def takeable(c, course):
    """(can the student get in right now?, reason)."""
    if seats(c)[4] == 0:
        return False, "no unreserved seat"
    for kind, lst in partner_sets(c, course).items():
        if not any(seats(p)[4] > 0 for p in lst):
            return False, f"every linked {kind} is full"
    return True, ""


def print_partners(c, course):
    for kind, lst in partner_sets(c, course).items():
        print(f"    needs a {kind}: " + "; ".join(short(p) for p in lst))


def open_partner_text(c, course):
    picks = []
    for kind, lst in partner_sets(c, course).items():
        free = [p for p in lst if seats(p)[4] > 0]
        if free:
            picks.append(", ".join("#" + p["CLAS"]["CLASSNBR"] for p in free[:3]) + f" ({kind})")
    return "; ".join(picks)


def describe(c):
    clas = c["CLAS"]
    cap, taken, open_, res_open, free = seats(c)
    who = ", ".join(clas.get("INSTRUCTORSLIST") or []) or "Staff"
    if open_ == 0:
        state = f"FULL ({taken}/{cap})"
    elif res_open:
        state = f"{open_} open of {cap} ({res_open} reserved for certain students)"
    else:
        state = f"{open_} open of {cap}"
    return (f"#{clas['CLASSNBR']} {clas['SUBJECT']} {clas['CATALOGNBR']} {comp(c)} sec {clas.get('CLASSSECTION', '?')}, "
            f"session {clas.get('SESSIONCODE', '?')}, {clas.get('CAMPUS', '?').title()}, {when(c)}, {who}: {state}")


def short(c):
    cap, taken, open_, res_open, free = seats(c)
    s = "FULL" if open_ == 0 else (f"{free} open" if not res_open else f"{free} open + {res_open} reserved")
    return f"#{c['CLAS']['CLASSNBR']} {comp(c)} sec {c['CLAS'].get('CLASSSECTION', '?')} ({s})"


def parse_course(text):
    m = re.fullmatch(r"\s*([A-Za-z]{2,4})\s*-?\s*(\d{3}[A-Za-z]?)\s*", text or "")
    if not m:
        raise UserError(f'Use a course like "MAT 265" (got "{text}").')
    return m.group(1).upper(), m.group(2).upper()


def cmd_list(a):
    term = term_code(a.term)
    subject, number = parse_course(a.course)
    classes = fetch({"term": term, "subject": subject, "catalogNbr": number}, a.sample)
    if a.campus:
        want = a.campus.upper()
        classes = [c for c in classes if want in (c["CLAS"].get("CAMPUS", "") + " " + c["CLAS"].get("LOCATION", "")).upper()]
    if not classes:
        print(f"No sections of {subject} {number} found for {term_name(term)}.")
        return 3
    # Show the main sections (usually lectures); linked recitations/labs are listed under each one.
    mains = [c for c in classes if is_main(c)] or classes
    rows = [(c, takeable(c, classes)) for c in mains]
    if a.full_only:
        rows = [r for r in rows if not r[1][0]]
    if a.open_only:
        rows = [r for r in rows if r[1][0]]
    can = sum(1 for _, (ok, _) in rows if ok)
    print(f"{subject} {number}, {term_name(term)}: {len(rows)} sections shown, {can} you can get into now, "
          f"{len(rows) - can} full or blocked.")
    rows.sort(key=lambda r: (not r[1][0], r[0]["CLAS"]["CLASSNBR"]))
    for c, (ok, why) in rows[: a.limit]:
        line = "- " + describe(c)
        if not ok and why and why != "no unreserved seat":
            line += f" [blocked: {why}]"
        print(line)
        print_partners(c, classes)
    if len(rows) > a.limit:
        print(f"...and {len(rows) - a.limit} more. Narrow with --campus, --full-only or --open-only.")
    print(page_link(term, subject=subject, number=number))
    return 0


def state_path(sample):
    return os.path.join(STATE_DIR, "sample_state.json" if sample else "state.json")


def load_state(sample):
    try:
        with open(state_path(sample)) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state, sample):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = state_path(sample) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, state_path(sample))


def cmd_check(a):
    term = term_code(a.term)
    state = load_state(a.sample)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    code = 0
    cache = {}

    def course_list(subject, number):
        if (subject, number) not in cache:
            cache[(subject, number)] = fetch({"term": term, "subject": subject, "catalogNbr": number}, a.sample)
        return cache[(subject, number)]

    for nbr in a.cls:
        nbr = str(nbr).strip().lstrip("#")
        if not nbr.isdigit():
            raise UserError(f'Class numbers are 5 digits, like 12745 (got "{nbr}").')
        c, course = None, None
        if a.course:
            # The course search is the same one `list` uses, and the most reliable way to read seats.
            lst = course_list(*parse_course(a.course))
            hit = [x for x in lst if x["CLAS"]["CLASSNBR"] == nbr]
            if hit:
                c, course = hit[0], lst
        if c is None:
            found = [x for x in fetch({"term": term, "keywords": nbr}, a.sample) if x["CLAS"]["CLASSNBR"] == nbr]
            if not found:
                print(f"#{nbr}: no class with that number in {term_name(term)}.")
                code = max(code, 3) if code < 10 else code
                continue
            c = found[0]
            course = [c]
            if group_key(c) is not None:
                course = course_list(c["CLAS"]["SUBJECT"], c["CLAS"]["CATALOGNBR"]) or [c]
                course = [x for x in course if x["CLAS"]["CLASSNBR"] != nbr] + [c]
        cap, taken, open_, res_open, free = seats(c)
        ok, why = takeable(c, course)
        key = f"{term}:{nbr}"
        before = state.get(key)
        was_ok = bool(before and before.get("takeable", before.get("unreserved_open", 0) > 0))
        state[key] = {"open": open_, "unreserved_open": free, "takeable": ok, "checked_utc": now}
        print("- " + describe(c))
        partners = required_partners(c, course)
        print_partners(c, course)
        if ok and not was_ok:
            msg = f"SEAT OPEN: #{nbr} has {free} seat(s) open now"
            extra = open_partner_text(c, course)
            if extra:
                msg += f". Add a linked section at the same time, these have room: {extra}"
            print(msg + ". Register in My ASU before someone else does.")
            verb = "Swap into it" if a.swap_from else "Add it"
            print(f"{verb} (one tap, opens My ASU):")
            print(enroll_link(term, c, course, a.swap_from))
            print("Class page:")
            print(page_link(term, class_nbr=nbr))
            code = 10
        elif not ok and free > 0 and partners and (before is None or before.get("unreserved_open", 0) == 0):
            print(f"#{nbr} has a seat, but {why}, so you can't enroll yet. Still watching.")
        elif open_ > 0 and free == 0 and (before is None or before.get("open", 0) == 0):
            print(f"RESERVED ONLY: #{nbr} has {open_} open seat(s), but they are reserved for certain students. "
                  "Check the class page to see who they are for.")
            print(page_link(term, class_nbr=nbr))
            code = max(code, 11) if code != 10 else 10
        elif not ok and was_ok:
            print(f"#{nbr} can't be taken right now: {why}. Still watching.")
    save_state(state, a.sample)
    return code


def cmd_forget(a):
    term = term_code(a.term)
    state = load_state(a.sample)
    for nbr in a.cls:
        state.pop(f"{term}:{str(nbr).strip().lstrip('#')}", None)
    save_state(state, a.sample)
    print("Stopped tracking: " + ", ".join("#" + str(n) for n in a.cls))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Live seat counts from ASU class search.")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("list", "check", "forget"):
        s = sub.add_parser(name)
        s.add_argument("--term", required=True, help='e.g. "Spring 2027" or 2271')
        s.add_argument("--sample", nargs="?", const="before", choices=["before", "after"],
                       help="use the bundled sample data instead of ASU")
        if name == "list":
            s.add_argument("--course", required=True, help='e.g. "MAT 265"')
            s.add_argument("--campus", help="e.g. TEMPE, POLY, ONLINE")
            s.add_argument("--full-only", action="store_true")
            s.add_argument("--open-only", action="store_true")
            s.add_argument("--limit", type=int, default=12)
        else:
            s.add_argument("--class", dest="cls", action="append", required=True, help="5-digit class number")
            if name == "check":
                s.add_argument("--course", help='the course the class belongs to, e.g. "CHM 113" (recommended)')
                s.add_argument("--swap-from", dest="swap_from",
                               help="class number the student is enrolled in now; the alert link then uses ASU's Swap")
    a = p.parse_args(argv)
    try:
        return {"list": cmd_list, "check": cmd_check, "forget": cmd_forget}[a.cmd](a)
    except UserError as e:
        print(e)
        return 4
    except ConnectionError as e:
        print(f"{e} Try again in a few minutes.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
