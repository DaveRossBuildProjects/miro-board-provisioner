#!/usr/bin/env python3
"""
provision_boards.py - bulk-provision one Miro board per person from a template.

For every row in a CSV (name, email) this script:
  1. creates a Miro space (project) named after the person   [Enterprise API, v2]
  2. copies the template board WITH content                    [v1 API - see README]
  3. renames the copy to the person's name                     [v2 PATCH]
  4. moves the board into the person's space                   [v2 PATCH]
  5. shares the board with the person (+ optional extra editors) [v2 members]

Auth: set MIRO_TOKEN in your environment. Never hardcode the token.

  export MIRO_TOKEN="$(pbpaste)"        # or load it from a secrets manager
  python provision_boards.py --template https://miro.com/app/board/uXjV.../ \
      --csv attendees.csv --also-share you@example.com --pause

Run with --dry-run first. Results are appended to provision_log.csv; people already
logged as successful are skipped on re-run, so an interrupted run can be resumed.
"""
import argparse
import csv
import os
import re
import sys
import time
import urllib.parse

import requests

V1 = "https://api.miro.com/v1"
V2 = "https://api.miro.com/v2"
LOG_FILE = "provision_log.csv"
LOG_FIELDS = ["email", "name", "space_id", "board_id", "board_url", "status", "error"]


def board_id_from(ref):
    m = re.search(r"/board/([^/?#]+)", ref)
    return urllib.parse.unquote(m.group(1) if m else ref.strip())


def enc(board_id):
    return urllib.parse.quote(board_id, safe="")


class Miro:
    def __init__(self, token, dry_run=False):
        self.dry_run = dry_run
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/json"})

    def call(self, method, url, **kw):
        if self.dry_run and method != "GET":
            print(f"      [dry-run] {method} {url} {kw.get('json', '')}")
            return {"id": "DRY_RUN_ID"}
        for attempt in range(5):
            r = self.s.request(method, url, timeout=60, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(min(float(r.headers.get("Retry-After", 2 ** attempt)), 60))
                continue
            if not r.ok:
                raise RuntimeError(f"HTTP {r.status_code} {method} {url}: {r.text[:400]}")
            return r.json() if r.text.strip() else {}
        raise RuntimeError(f"Retries exhausted: {method} {url}")


def read_people(path, name_col, email_col):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit("CSV is empty.")
    headers = {h.lower().strip(): h for h in rows[0]}
    nk, ek = headers.get(name_col.lower()), headers.get(email_col.lower())
    if not nk or not ek:
        sys.exit(f"CSV needs columns '{name_col}' and '{email_col}'. Found: {list(rows[0])}")
    people = []
    for r in rows:
        name, email = r[nk].strip(), r[ek].strip().lower()
        if name and email:
            people.append((name, email))
    return people


def load_done():
    if not os.path.exists(LOG_FILE):
        return set()
    with open(LOG_FILE, newline="") as f:
        return {r["email"] for r in csv.DictReader(f) if r["status"] == "ok"}


def log(row):
    new = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in LOG_FIELDS})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True, help="Template board URL or ID")
    ap.add_argument("--csv", required=True, help="CSV with name and email columns")
    ap.add_argument("--name-col", default="name")
    ap.add_argument("--email-col", default="email")
    ap.add_argument("--org-id", help="Miro org ID (auto-detected from the token if omitted)")
    ap.add_argument("--team-id", help="Team ID (auto-detected from the template board if omitted)")
    ap.add_argument("--also-share", action="append", default=[], help="Extra editor email (repeatable)")
    ap.add_argument("--role", default="editor", choices=["viewer", "commenter", "editor"])
    ap.add_argument("--pause", action="store_true", help="Press Enter between people (inspect first results)")
    ap.add_argument("--limit", type=int, help="Only process the first N people")
    ap.add_argument("--dry-run", action="store_true", help="Print writes instead of sending them")
    args = ap.parse_args()

    token = os.environ.get("MIRO_TOKEN", "").strip()
    if not token and not args.dry_run:
        sys.exit("Set MIRO_TOKEN in your environment (never hardcode it).")
    m = Miro(token or "dry-run", args.dry_run)

    template = board_id_from(args.template)
    people = read_people(args.csv, args.name_col, args.email_col)
    if args.limit:
        people = people[: args.limit]

    # --- discover team / org -------------------------------------------------
    team_id, org_id = args.team_id, args.org_id
    if not args.dry_run:
        tmpl = m.call("GET", f"{V2}/boards/{enc(template)}")
        team_id = team_id or tmpl["team"]["id"]
        print(f"Template: {tmpl['name']}  (team {team_id})")
        if not org_id:
            ident = m.call("GET", f"{V1}/oauth-token")
            org_id = (ident.get("organization") or {}).get("id")
        if not org_id:
            sys.exit("Could not detect org ID; pass --org-id.")
    team_id, org_id = team_id or "TEAM_ID", org_id or "ORG_ID"

    done = load_done()
    todo = [(n, e) for n, e in people if e not in done]
    print(f"{len(people)} people in CSV, {len(people) - len(todo)} already done, {len(todo)} to process.\n")

    ok = failed = 0
    for i, (name, email) in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {name} <{email}>")
        row = {"email": email, "name": name}
        try:
            space = m.call("POST", f"{V2}/orgs/{org_id}/teams/{team_id}/projects", json={"name": name[:60]})
            row["space_id"] = space["id"]
            print(f"   space created: {space['id']}")

            copy = m.call("POST", f"{V1}/boards/{enc(template)}/copy")
            bid = copy["id"]
            row["board_id"], row["board_url"] = bid, f"https://miro.com/app/board/{bid}"
            print(f"   board copied:  {bid}")

            m.call("PATCH", f"{V2}/boards/{enc(bid)}", json={"name": name[:60]})   # v1 prefixes "Copy of"
            print("   board renamed")

            m.call("PATCH", f"{V2}/boards/{enc(bid)}", json={"teamId": team_id, "projectId": space["id"]})
            print("   board moved into space")

            emails = [email] + [e for e in args.also_share if e.lower() != email]
            res = m.call("POST", f"{V2}/boards/{enc(bid)}/members", json={"emails": emails, "role": args.role})
            if res.get("failed"):
                raise RuntimeError(f"share failed: {res['failed']}")
            print(f"   shared with {len(emails)} editor(s)")
            row["status"] = "ok"
            ok += 1
        except Exception as e:  # keep going; the log makes the run resumable
            row["status"], row["error"] = "error", str(e)
            failed += 1
            print(f"   ERROR: {e}")
        if not args.dry_run:
            log(row)
        if args.pause and i < len(todo):
            input("   Press Enter for the next person (Ctrl+C to stop)... ")

    print(f"\nDone. ok={ok} failed={failed}. Log: {LOG_FILE}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
