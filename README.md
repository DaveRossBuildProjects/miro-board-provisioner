# Miro Board Provisioner

Bulk-create one personal Miro board per attendee from a template, each in its own named space, shared with the right people. Built for the Toronto Tech Week AI Prototyping workshops (May 2026): 83 morning + 79 afternoon attendees, provisioned in minutes instead of hours.

## The problem

A hands-on workshop needs every participant to have their own working copy of a rich template board. By hand, per person, that means: duplicate the template, rename it, create a space for them, move the board in, and add them (plus the facilitator) as editors. For 160+ people that is hours of error-prone clicking, and it has to be finished before doors open.

The Miro MCP connector can only create blank boards, so this needs the Miro REST API.

## What it does

For each row in a CSV (`name`, `email`):

1. Creates a **space** named after the person (Enterprise API)
2. **Copies the template board with all content** (v1 API, see gotchas)
3. **Renames** the copy to the person's name
4. **Moves** the board into their space
5. **Shares** it with the person and any `--also-share` emails as editors

Result: N spaces, each holding exactly one board, all named for the attendee.

## Quick start

```bash
pip install -r requirements.txt
export MIRO_TOKEN=...            # OAuth token from your Miro app (never commit it)
python provision_boards.py --template <board-url> --csv sample_attendees.csv \
    --also-share you@example.com --dry-run          # preview
python provision_boards.py --template <board-url> --csv attendees.csv \
    --also-share you@example.com --pause --limit 2  # try two people
python provision_boards.py --template <board-url> --csv attendees.csv --also-share you@example.com
```

Full setup (creating the Miro app, scopes, org/team IDs, admin approval) is in [docs/implementation-guide.md](docs/implementation-guide.md). Diagrams are in [docs/architecture.md](docs/architecture.md).

## Options

| Flag | Purpose |
|---|---|
| `--template` | Template board URL or ID (required) |
| `--csv` | CSV with name and email columns (required) |
| `--name-col`, `--email-col` | Column headers if not `name` / `email` |
| `--org-id`, `--team-id` | Override auto-detection |
| `--also-share` | Extra editor, repeatable (e.g. the facilitator) |
| `--role` | `editor` (default), `commenter`, `viewer` |
| `--pause` | Press Enter between people, to inspect early results |
| `--limit N` | Process only the first N |
| `--dry-run` | Print every write, send nothing |

Progress is written to `provision_log.csv`. Re-running skips emails already logged `ok`, so an interrupted run resumes without duplicating spaces or boards.

## Safety

- The token comes from `MIRO_TOKEN` only. Attendee CSVs hold personal data and are git-ignored; commit only the fake `sample_attendees.csv`.
- The script creates spaces and boards and shares with external emails. Test with `--dry-run` and `--limit 2` first.

## Provenance and status

This is a cleaned-up reference implementation reconstructed from the working May 2026 session. The original one-off script embedded attendee data and credentials and could not be published as-is. The API sequence (v1 copy, v2 rename, enterprise space creation, v2 move, v2 share) matches what ran successfully; validate the space-creation and move calls against your org with `--limit 2` before a large run.

Related: [miro-api-client](https://github.com/DaveRossBuildProjects/miro-api-client) is the general-purpose Miro REST client used for ad-hoc template and admin changes.

## License

MIT. See [LICENSE](LICENSE).
