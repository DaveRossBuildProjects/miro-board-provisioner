# Architecture

GitHub renders the Mermaid diagrams below natively.

## 1. System context

```mermaid
flowchart LR
    CSV[/"attendees.csv<br/>name, email"/] --> S
    ENV[("MIRO_TOKEN<br/>env var / secrets manager")] --> S
    S["provision_boards.py<br/>(runs on your machine)"]
    S -- "HTTPS + Bearer token" --> API["Miro REST API<br/>v1 + v2 + Enterprise"]
    API --> T[("Template board<br/>(source)")]
    API --> TEAM["Miro Team"]
    TEAM --> SP["N Spaces<br/>one per attendee"]
    SP --> B["N Boards<br/>full copy of template"]
    S --> LOG[/"provision_log.csv<br/>resume + audit"/]
    APP["Miro app<br/>boards:read/write<br/>projects:read/write"] -. "issues token for" .-> ENV
```

## 2. Per-attendee sequence

```mermaid
sequenceDiagram
    autonumber
    participant S as provision_boards.py
    participant M as Miro API
    participant L as provision_log.csv
    Note over S,M: Startup: GET v2 template board (team id), GET v1 oauth-token (org id)
    loop each person not already logged ok
        S->>M: POST v2 /orgs/{org}/teams/{team}/projects  {name}
        M-->>S: space id
        S->>M: POST v1 /boards/{template}/copy
        M-->>S: new board id ("Copy of ...", 178 items)
        S->>M: PATCH v2 /boards/{id}  {name}
        S->>M: PATCH v2 /boards/{id}  {teamId, projectId}
        S->>M: POST v2 /boards/{id}/members  {emails[], role}
        M-->>S: successful / failed
        S->>L: append ok or error row
        opt --pause
            S->>S: wait for Enter
        end
    end
```

## 3. Why v1 for the copy

```mermaid
flowchart TD
    A["Need a full copy of a rich template"] --> B{"Which endpoint?"}
    B -- "v2 PUT /boards?copy_from" --> C["201 OK, board created<br/>but 0 items (blank)"]
    B -- "v1 POST /boards/{id}/copy" --> D["201 OK, 178/178 items"]
    C --> X["Rejected: silent failure"]
    D --> E["Chosen. Rename afterwards<br/>(v1 prefixes 'Copy of')"]
```

## 4. Error handling and resumability

```mermaid
flowchart LR
    R["Run"] --> P{"person already ok in log?"}
    P -- yes --> SK["skip"]
    P -- no --> W["5 API steps"]
    W -- success --> OK["log ok"]
    W -- exception --> ER["log error, continue"]
    ER --> RE["fix cause, re-run:<br/>only non-ok people retried"]
```

## 5. Final state

```mermaid
flowchart TB
    TEAM["Team"] --> S1["Space: Ada Example"] --> B1["Board: Ada Example<br/>editors: Ada + facilitator"]
    TEAM --> S2["Space: Grace Sample"] --> B2["Board: Grace Sample<br/>editors: Grace + facilitator"]
    TEAM --> S3["Space: ..."] --> B3["Board: ..."]
```
