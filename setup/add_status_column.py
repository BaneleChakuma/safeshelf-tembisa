#!/usr/bin/env python3
"""Add a column to the SafeShelf Tembisa project board without moving any cards.

    python3 setup/add_status_column.py Testing --before Done --dry-run   # preview only
    python3 setup/add_status_column.py Testing --before Done             # add it

Board columns are the options of the project's "Status" field. When you add an option
through GitHub's API, the whole option list is replaced; if it isn't done carefully,
every card loses its column. This script:
  1. saves a backup of every card's column
  2. sends the existing columns back with their IDs (which keeps the cards in place),
     plus the new one in the right position
  3. checks that every card is still in its column, and puts back any that moved

Needs the GitHub CLI (gh), logged in with permission to manage projects
(setup/setup_github.py already arranged that).
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKLOG_FILE = ROOT / "setup" / "backlog.json"
COLORS = ["GRAY", "BLUE", "GREEN", "YELLOW", "ORANGE", "RED", "PINK", "PURPLE"]

FIELD_QUERY = """
query($project: ID!, $field: String!) {
  node(id: $project) {
    ... on ProjectV2 {
      field(name: $field) {
        ... on ProjectV2SingleSelectField { id name options { id name color description } }
      }
    }
  }
}"""

ITEMS_QUERY = """
query($project: ID!, $field: String!, $cursor: String) {
  node(id: $project) {
    ... on ProjectV2 {
      items(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          content {
            ... on Issue { title }
            ... on PullRequest { title }
            ... on DraftIssue { title }
          }
          fieldValueByName(name: $field) {
            ... on ProjectV2ItemFieldSingleSelectValue { optionId name }
          }
        }
      }
    }
  }
}"""

UPDATE_FIELD = """
mutation($field: ID!, $options: [ProjectV2SingleSelectFieldOptionInput!]) {
  updateProjectV2Field(input: {fieldId: $field, singleSelectOptions: $options}) {
    projectV2Field { ... on ProjectV2SingleSelectField { id } }
  }
}"""


def say(message=""):
    print(message, flush=True)


def fail(message):
    say(f"\n✗ {message}")
    sys.exit(1)


def gh(args, stdin=None):
    result = subprocess.run(["gh", *args], text=True, capture_output=True, input=stdin)
    if result.returncode != 0:
        fail(f"This gh command failed: gh {' '.join(args[:3])}\n{(result.stderr or result.stdout).strip()}")
    return result.stdout


def graphql(query, variables):
    out = gh(["api", "graphql", "--input", "-"], stdin=json.dumps({"query": query, "variables": variables}))
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        fail(f"Unexpected reply from GitHub:\n{out[:500]}")
    if data.get("errors"):
        fail("GitHub returned an error:\n  " + "\n  ".join(e.get("message", "?") for e in data["errors"]))
    return data["data"]


def defaults_from_backlog():
    try:
        backlog = json.loads(BACKLOG_FILE.read_text(encoding="utf-8"))
        return backlog["repo"]["owner"], backlog["project"]["title"]
    except (OSError, ValueError, KeyError):
        return None, None


def find_project(owner, title):
    listing = json.loads(gh(["project", "list", "--owner", owner, "--format", "json", "--limit", "100"]) or "{}")
    for project in listing.get("projects", []):
        if project.get("title") == title:
            return project
    fail(f'Can\'t find a project called "{title}" on {owner}\'s account.')


def get_field(project_id, field_name):
    node = graphql(FIELD_QUERY, {"project": project_id, "field": field_name}).get("node") or {}
    field = node.get("field") or {}
    if not field.get("options"):
        fail(f'The project has no single-select field called "{field_name}".')
    return field


def get_items(project_id, field_name):
    items, cursor = {}, None
    while True:
        node = graphql(ITEMS_QUERY, {"project": project_id, "field": field_name, "cursor": cursor})["node"]
        page = node["items"]
        for item in page["nodes"]:
            value = item.get("fieldValueByName") or {}
            items[item["id"]] = {
                "title": (item.get("content") or {}).get("title", "(untitled)"),
                "option_id": value.get("optionId"),
                "option_name": value.get("name"),
            }
        if not page["pageInfo"]["hasNextPage"]:
            return items
        cursor = page["pageInfo"]["endCursor"]


def column_counts(field, items):
    counts = {o["name"]: 0 for o in field["options"]}
    for item in items.values():
        if item["option_name"] in counts:
            counts[item["option_name"]] += 1
    return counts


def show_columns(field, items):
    counts = column_counts(field, items)
    for option in field["options"]:
        say(f"    {option['name']:<14} {counts[option['name']]} cards")


def main():
    owner_default, title_default = defaults_from_backlog()
    parser = argparse.ArgumentParser(description="Add a column (Status option) to the project board, keeping every card in place.")
    parser.add_argument("name", help='name of the new column, e.g. "Testing"')
    parser.add_argument("--before", default="Done", help='put it before this column (default: "Done")')
    parser.add_argument("--color", default="PURPLE", type=str.upper, choices=COLORS, help="column colour (default: PURPLE)")
    parser.add_argument("--description", default="Code done: running tests and checking acceptance criteria before merging")
    parser.add_argument("--owner", default=owner_default, help="GitHub account that owns the board")
    parser.add_argument("--project", default=title_default, help="title of the project board")
    parser.add_argument("--field", default="Status", help='the field that makes the columns (default: "Status")')
    parser.add_argument("--dry-run", action="store_true", help="show what would change, change nothing")
    parser.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    args = parser.parse_args()

    if not args.owner or not args.project:
        fail("Please give --owner and --project (couldn't read them from setup/backlog.json).")
    if shutil.which("gh") is None:
        fail("The GitHub CLI (gh) isn't installed. See setup/README.md.")
    if subprocess.run(["gh", "auth", "status"], capture_output=True).returncode != 0:
        fail("You're not logged in to the GitHub CLI. Run:  gh auth login")

    project = find_project(args.owner, args.project)
    project_id = project["id"]
    field = get_field(project_id, args.field)
    names = [o["name"] for o in field["options"]]

    existing = next((n for n in names if n.strip().lower() == args.name.strip().lower()), None)
    if existing:
        say(f'✓ The board already has a "{existing}" column, so there\'s nothing to do.')
        return

    items = get_items(project_id, args.field)
    new_option = {"name": args.name, "color": args.color, "description": args.description}
    options = [{"id": o["id"], "name": o["name"], "color": o["color"], "description": o.get("description") or ""}
               for o in field["options"]]
    position = next((i for i, o in enumerate(options) if o["name"].lower() == args.before.lower()), None)
    if position is None:
        say(f'• There\'s no "{args.before}" column, so "{args.name}" will go at the end.')
        position = len(options)
    options.insert(position, new_option)

    say(f'Board  : {args.project} ({project.get("url", "")})')
    say(f"Cards  : {len(items)}")
    say("\nColumns now:")
    show_columns(field, items)
    say("\nColumns after:")
    say("    " + " → ".join(o["name"] for o in options))

    if args.dry_run:
        say("\nDRY RUN: nothing was changed. Run it again without --dry-run to add the column.")
        return
    if not args.yes:
        if not input(f'\nAdd "{args.name}"? Every card stays where it is. [y/N] ').strip().lower().startswith("y"):
            say("Okay, nothing was changed.")
            return

    # 1. Backup
    backup = Path(tempfile.gettempdir()) / f"board_status_backup_{datetime.now():%Y%m%d-%H%M%S}.json"
    backup.write_text(json.dumps({"project": project_id, "field": field, "items": items}, indent=2), encoding="utf-8")
    say(f"\n✓ Backed up every card's column to {backup}")

    # 2. Add the column, sending the existing options back with their IDs
    graphql(UPDATE_FIELD, {"field": field["id"], "options": options})
    say(f'✓ Added "{args.name}"')

    # 3. Check every card is still in its column, and fix any that moved
    new_field = get_field(project_id, args.field)
    by_name = {o["name"]: o["id"] for o in new_field["options"]}
    if args.name not in by_name:
        fail(f'GitHub didn\'t add "{args.name}". Nothing else should have changed; check the board, '
             f"and the backup is at {backup}.")
    after = get_items(project_id, args.field)
    moved = [(item_id, before) for item_id, before in items.items()
             if before["option_name"] and (after.get(item_id) or {}).get("option_name") != before["option_name"]]
    if moved:
        say(f"• {len(moved)} cards lost their column, putting them back...")
        for item_id, before in moved:
            gh(["project", "item-edit", "--id", item_id, "--project-id", project_id,
                "--field-id", new_field["id"], "--single-select-option-id", by_name[before["option_name"]]])
        after = get_items(project_id, args.field)
        still = [b["title"] for i, b in moved if (after.get(i) or {}).get("option_name") != b["option_name"]]
        if still:
            fail(f"These cards couldn't be put back: {', '.join(still)}. Their old columns are in {backup}.")
        say(f"✓ Put back {len(moved)} cards")
    say(f"✓ Checked: all {len(after)} cards are in the same columns as before\n")
    show_columns(new_field, after)
    say(f'\nDone! Open your board to see the "{args.name}" column. If it doesn\'t show, scroll to the')
    say(f'right of the columns, click +, and tick "{args.name}".')


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        say("\nStopped.")
        sys.exit(130)
