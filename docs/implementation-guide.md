# Implementation Guide

End-to-end setup for running the board provisioner against your own Miro team.

## 1. Prerequisites

- A Miro **Enterprise** plan. Creating spaces through the API uses an org-scoped endpoint.
- Membership of the team that will own the boards, with permission to create boards and spaces there.
- The **template board** in that team, with copying allowed for team editors.
- Python 3.9+ and `pip install -r requirements.txt`.
- An attendee CSV with `name` and `email` columns (extra columns such as company or title are ignored; use `--name-col` / `--email-col` if headers differ).

## 2. Create the Miro app and get a token

The script acts as you, through a Miro app you create and install on the target team.

1. Open Miro, then **Profile settings, Your apps** (https://miro.com/app/settings/user-profile/apps), and choose **Create new app**.
2. Name it (for example "Duplicate board") and pick the **team** that will own the boards. The token is bound to this team, so a different team needs its own install and token.
3. Under **Permissions**, enable:
   - `boards:read`
   - `boards:write`
   - `projects:read`
   - `projects:write`
4. For a personal-token style app, the OAuth-only fields can hold placeholders: App URL `https://localhost`, Redirect URI `https://localhost/callback`.
5. Choose **Install app and get OAuth token**, select the team, and copy the access token.
6. Store the token in a secrets manager (1Password, Vault, etc.) and load it at run time:

   ```bash
   export MIRO_TOKEN="<token>"
   ```

Never paste the token into chat, scripts, or commits. The app's **client secret** is not used by this script at all; keep it out of the workflow. If a token or secret is ever exposed, revoke the secret, regenerate the token, and reinstall the app.

### Admin approval in customer or locked-down orgs

Many orgs require an admin to approve new apps. If your app shows "needs admin approval", you have three options: ask an org admin to approve it, ask an admin to create the app and token themselves (same four scopes) and run the script, or run the script on their behalf during a screen share. Without an approved app there is no API route; the script cannot work around it.

## 3. Find the IDs

| Value | Where to get it |
|---|---|
| Template board ID | The board URL: `https://miro.com/app/board/<ID>/`. The script accepts the full URL. |
| Team ID | Auto-detected from the template board (`team.id`). Override with `--team-id`. |
| Org ID | Auto-detected from `GET /v1/oauth-token`. If your token does not return it, pass `--org-id` (visible in the admin console URL, or via the Enterprise API). |

## 4. Run it

```bash
# 1. Preview. No writes, no token needed.
python provision_boards.py --template <url> --csv attendees.csv --also-share you@example.com --dry-run

# 2. Pilot two people, pausing between them. Open their boards in Miro and check content, name, space and sharing.
python provision_boards.py --template <url> --csv attendees.csv --also-share you@example.com --limit 2 --pause

# 3. Full run (Enter-to-advance optional).
python provision_boards.py --template <url> --csv attendees.csv --also-share you@example.com
```

Stop any time with Ctrl+C. `provision_log.csv` records each person as `ok` or `error` with the board and space IDs. Re-running skips `ok` rows; fix and re-run errors. If a person partly succeeded before failing (for example the board exists but sharing failed), clean that attendee's space and board in Miro before retrying so you do not create duplicates.

## 5. Verify

Spot-check a few attendees in Miro: the space exists with their name, it contains one board with the full template content (item count matches the template), and the attendee plus facilitator are editors.

## 6. Reusing for another team or org

Create a new app on the new team (new token), set `MIRO_TOKEN`, and pass the new template, CSV, `--team-id` and `--org-id`. No code changes are required.

## 7. Gotchas learned the hard way

1. **v2 `copy_from` silently makes blank boards.** `PUT /v2/boards?copy_from=<id>` returned success but created boards with 0 items for this template (a rich one: 17 item types including dot voting, dynamic polls, QR companions, prototyping screens, mind maps, doc and table formats). Changing the template's `copyAccess` to `anyone` did not help. The **v1** endpoint `POST /v1/boards/{id}/copy` copied all 178 items correctly, so the script uses v1 for the copy.
2. **v1 copies are named "Copy of ..."**, so the script renames afterwards with a v2 PATCH.
3. **`POST /v2/teams/{id}/projects` does not exist** (404). Spaces are created through the org-scoped Enterprise endpoint `POST /v2/orgs/{org_id}/teams/{team_id}/projects`.
4. **Board names are capped at 60 characters**; the script truncates.
5. **Item-by-item copying is not viable** for templates with these widget types, which have no public create endpoints. Always copy the whole board.
6. **A stale file ran instead of the edited one** during the original debugging. If output does not match the code, check which file you are running.
7. **Blank boards with no errors** is the signature of gotcha 1. Check the new board's item count against the template.
8. **Sandboxed environments** (Claude Cowork's VM, some CI) may block `api.miro.com`. If you see tunnel or 403 errors before any Miro response, run the script on your own machine.
9. **Sharing failures** (`failed` entries from the members call) usually mean the email is already a member or the org restricts external sharing. The script reports them as errors.

## 8. Not covered by this script

Setting org-level license tiers and admin roles is a separate workflow, done through the Enterprise admin APIs (see the miro-api-client project for the `request` command).
