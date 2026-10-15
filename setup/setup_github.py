#!/usr/bin/env python3
"""Set up SafeShelf Tembisa on GitHub.

Creates (on your own account):
  - the repository, with the plan and docs in this folder
  - labels (type, epic, priority)
  - milestones (one per iteration)
  - issues (the user stories in setup/backlog.json)
  - a GitHub Projects board with every issue on it

Needs the GitHub CLI (gh) 2.40 or newer, logged in as the repository owner.
See setup/README.md.

    python3 setup/setup_github.py --dry-run   # preview: changes nothing
    python3 setup/setup_github.py             # create everything

Safe to run again: anything that already exists is skipped.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKLOG_FILE = ROOT / "setup" / "backlog.json"
MIN_GH_VERSION = (2, 40, 0)
PAUSE = 1.0  # seconds between creating issues, to stay well inside GitHub's limits


# ----------------------------------------------------------------- helpers

def say(message=""):
    print(message, flush=True)


def fail(message):
    say(f"\n✗ {message}")
    sys.exit(1)


def run(cmd, check=True, interactive=False):
    """Run a command. Returns (exit code, stdout, stderr)."""
    if interactive:
        result = subprocess.run(cmd, text=True)
        return result.returncode, "", ""
    result = subprocess.run(cmd, text=True, capture_output=True)
    if check and result.returncode != 0:
        fail(f"This command failed:\n  {shlex.join(cmd)}\n\n{(result.stderr or result.stdout).strip()}")
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def gh_json(args):
    """Run a gh command that prints JSON and return the parsed result."""
    _, out, _ = run(["gh", *args])
    try:
        return json.loads(out) if out else {}
    except json.JSONDecodeError:
        fail(f"Unexpected output from: gh {shlex.join(args)}\n{out[:500]}")


def git(*args, check=True):
    return run(["git", "-C", str(ROOT), *args], check=check)


# ----------------------------------------------------------------- backlog

def load_backlog():
    try:
        backlog = json.loads(BACKLOG_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"Can't find {BACKLOG_FILE}. Run this from the project folder.")
    except json.JSONDecodeError as err:
        fail(f"setup/backlog.json isn't valid JSON (line {err.lineno}): {err.msg}")

    labels = {label["name"] for label in backlog["labels"]}
    milestones = {m["title"] for m in backlog["milestones"]}
    titles = set()
    problems = []
    for issue in backlog["issues"]:
        if issue["title"] in titles:
            problems.append(f"two issues are called {issue['title']!r}")
        titles.add(issue["title"])
        for label in issue["labels"]:
            if label not in labels:
                problems.append(f"issue {issue['title']!r} uses unknown label {label!r}")
        if issue.get("milestone") and issue["milestone"] not in milestones:
            problems.append(f"issue {issue['title']!r} uses unknown milestone {issue['milestone']!r}")
    for m in backlog["milestones"]:
        if m.get("due") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", m["due"]):
            problems.append(f"milestone {m['title']!r} has due date {m['due']!r}; use YYYY-MM-DD")
    if backlog["repo"]["visibility"] not in ("public", "private"):
        problems.append('repo "visibility" must be "public" or "private"')
    if problems:
        fail("Please fix setup/backlog.json:\n  - " + "\n  - ".join(problems))
    return backlog


def show_plan(backlog):
    repo = backlog["repo"]
    full = f"{repo['owner']}/{repo['name']}"
    say(f"Account     : {repo['owner']}")
    say(f"Repository  : https://github.com/{full} ({repo['visibility']}), with the plan and docs")
    say(f"Labels      : {len(backlog['labels'])}")
    say(f"Milestones  : {len(backlog['milestones'])} (one per iteration)")
    say(f"Issues      : {len(backlog['issues'])} (user stories and tasks)")
    say(f"Board       : GitHub Project \"{backlog['project']['title']}\" with every issue on it")


def show_backlog(backlog):
    for m in backlog["milestones"]:
        due = f"  (due {m['due']})" if m.get("due") else ""
        say(f"\n{m['title']}{due}")
        for issue in backlog["issues"]:
            if issue.get("milestone") == m["title"]:
                kind = "story" if "user story" in issue["labels"] else "task "
                prio = next((l.split(": ")[1] for l in issue["labels"] if l.startswith("priority: ")), "")
                say(f"  - [{kind}] {issue['title']}  ({prio})")


# ----------------------------------------------------------------- checks

def check_tools():
    if shutil.which("git") is None:
        fail("git isn't installed. Install it with:  sudo apt install git")
    if shutil.which("gh") is None:
        fail("The GitHub CLI (gh) isn't installed. See setup/README.md, step 1.")
    _, out, _ = run(["gh", "--version"])
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", out)
    version = tuple(int(x) for x in match.groups()) if match else (0, 0, 0)
    if version < MIN_GH_VERSION:
        have = ".".join(map(str, version))
        need = ".".join(map(str, MIN_GH_VERSION))
        fail(f"Your gh is version {have}; this needs {need} or newer. See setup/README.md, step 1.")


def check_login(owner):
    code, out, err = run(["gh", "auth", "status", "--hostname", "github.com"], check=False)
    if code != 0:
        fail("You're not logged in to the GitHub CLI. Run:  gh auth login")
    _, login, _ = run(["gh", "api", "user", "--jq", ".login"])
    if login.lower() != owner.lower():
        fail(f"You're logged in as {login}, but setup/backlog.json is for {owner}.\n"
             f"  Log in as {owner} (gh auth login), or change \"owner\" in setup/backlog.json.")
    status = f"{out}\n{err}"
    scopes_line = next((line for line in status.splitlines() if "scopes" in line.lower()), "")
    if scopes_line and "'project'" not in scopes_line:
        say("• Your GitHub login needs permission to manage project boards.")
        say("  gh will show a code: copy it, then approve it in your browser.\n")
        code, _, _ = run(["gh", "auth", "refresh", "--hostname", "github.com", "--scopes", "project"],
                         check=False, interactive=True)
        if code != 0:
            fail("Couldn't add the project permission. Try:  gh auth refresh -s project")
    return login


# ----------------------------------------------------------------- steps

def ensure_git_identity():
    _, email, _ = git("config", "user.email", check=False)
    _, name, _ = git("config", "user.name", check=False)
    if email and name:
        return
    user = gh_json(["api", "user"])
    login = user.get("login", "")
    if not name:
        git("config", "user.name", user.get("name") or login)
    if not email:
        # GitHub's private "noreply" address, so your real email isn't published in commits
        git("config", "user.email", f"{user.get('id')}+{login}@users.noreply.github.com")


def ensure_repo(backlog):
    repo = backlog["repo"]
    full = f"{repo['owner']}/{repo['name']}"
    code, _, _ = run(["gh", "repo", "view", full, "--json", "name"], check=False)
    if code == 0:
        say(f"• Repository {full} already exists, so its files are left as they are")
        return full

    if not (ROOT / ".git").exists():
        git("init", "-b", "main")
    ensure_git_identity()
    _, remotes, _ = git("remote")
    if "origin" in remotes.split():
        fail("This folder already has a Git remote called 'origin'.\n"
             "  Remove it with:  git remote remove origin   then run this again.")
    git("add", "-A")
    _, changes, _ = git("status", "--porcelain")
    if changes:
        git("commit", "-m", "docs: project plan, user stories and GitHub setup")
    run(["gh", "repo", "create", full, f"--{repo['visibility']}", "--description", repo["description"],
         "--source", str(ROOT), "--remote", "origin", "--push"])
    say(f"✓ Created https://github.com/{full} and pushed the plan and docs")
    return full


def ensure_labels(backlog, full):
    for label in backlog["labels"]:
        run(["gh", "label", "create", label["name"], "--repo", full, "--color", label["color"],
             "--description", label["description"], "--force"])
    say(f"✓ Labels ready ({len(backlog['labels'])})")


def ensure_milestones(backlog, full):
    existing = gh_json(["api", f"repos/{full}/milestones?state=all&per_page=100"])
    have = {m["title"] for m in existing} if isinstance(existing, list) else set()
    created = 0
    for m in backlog["milestones"]:
        if m["title"] in have:
            continue
        cmd = ["gh", "api", "--method", "POST", f"repos/{full}/milestones",
               "-f", f"title={m['title']}", "-f", f"description={m['description']}"]
        if m.get("due"):
            cmd += ["-f", f"due_on={m['due']}T12:00:00Z"]
        run(cmd)
        created += 1
    say(f"✓ Milestones ready ({created} created, {len(backlog['milestones']) - created} already there)")


def ensure_issues(backlog, full):
    existing = gh_json(["issue", "list", "--repo", full, "--state", "all", "--limit", "500", "--json", "title,url"])
    have = {i["title"]: i["url"] for i in existing} if isinstance(existing, list) else {}
    urls, created = [], 0
    total = len(backlog["issues"])
    for n, issue in enumerate(backlog["issues"], 1):
        if issue["title"] in have:
            urls.append(have[issue["title"]])
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(issue["body"])
            body_file = fh.name
        cmd = ["gh", "issue", "create", "--repo", full, "--title", issue["title"], "--body-file", body_file]
        for label in issue["labels"]:
            cmd += ["--label", label]
        if issue.get("milestone"):
            cmd += ["--milestone", issue["milestone"]]
        try:
            _, out, _ = run(cmd)
        finally:
            os.unlink(body_file)
        url = out.splitlines()[-1].strip()
        urls.append(url)
        created += 1
        say(f"  [{n}/{total}] {issue['title']}")
        time.sleep(PAUSE)
    say(f"✓ Issues ready ({created} created, {total - created} already there)")
    return urls


def ensure_project(backlog, full, owner, issue_urls):
    proj_cfg = backlog["project"]
    listing = gh_json(["project", "list", "--owner", owner, "--format", "json", "--limit", "100"])
    projects = listing.get("projects", []) if isinstance(listing, dict) else []
    project = next((p for p in projects if p.get("title") == proj_cfg["title"]), None)
    if project is None:
        project = gh_json(["project", "create", "--owner", owner, "--title", proj_cfg["title"], "--format", "json"])
        say(f"✓ Created project board \"{proj_cfg['title']}\"")
    else:
        say(f"• Project board \"{proj_cfg['title']}\" already exists, so it's reused")
    number, project_id = str(project["number"]), project["id"]
    url = project.get("url", f"https://github.com/users/{owner}/projects/{number}")

    # Nice-to-haves: if any of these fail, the board still works.
    visibility = "PUBLIC" if backlog["repo"]["visibility"] == "public" else "PRIVATE"
    run(["gh", "project", "edit", number, "--owner", owner, "--description", proj_cfg["description"],
         "--readme", proj_cfg["readme"], "--visibility", visibility], check=False)
    run(["gh", "project", "link", number, "--owner", owner, "--repo", full], check=False)

    items = gh_json(["project", "item-list", number, "--owner", owner, "--format", "json", "--limit", "500"])
    on_board = {(item.get("content") or {}).get("url") for item in items.get("items", [])}

    fields = gh_json(["project", "field-list", number, "--owner", owner, "--format", "json"])
    status = next((f for f in fields.get("fields", []) if f.get("name") == "Status"), None)
    todo = None
    if status:
        todo = next((o["id"] for o in status.get("options", [])
                     if o.get("name", "").lower().replace(" ", "") == "todo"), None)

    added = 0
    for issue_url in issue_urls:
        if issue_url in on_board:
            continue
        item = gh_json(["project", "item-add", number, "--owner", owner, "--url", issue_url, "--format", "json"])
        if status and todo and item.get("id"):
            run(["gh", "project", "item-edit", "--id", item["id"], "--project-id", project_id,
                 "--field-id", status["id"], "--single-select-option-id", todo], check=False)
        added += 1
        time.sleep(PAUSE / 2)
    say(f"✓ Board ready ({added} issues added, {len(issue_urls) - added} already on it)")
    return url


# ----------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Create the SafeShelf Tembisa repo, issues and board on GitHub.")
    parser.add_argument("--dry-run", action="store_true", help="show what would be created, change nothing")
    parser.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    args = parser.parse_args()

    backlog = load_backlog()
    owner = backlog["repo"]["owner"]

    if args.dry_run:
        say("DRY RUN: nothing will be created.\n")
        show_plan(backlog)
        show_backlog(backlog)
        say("\nLooks right? Run it for real with:  python3 setup/setup_github.py")
        return

    check_tools()
    check_login(owner)

    say("\nThis will create the following on GitHub:\n")
    show_plan(backlog)
    if not args.yes:
        answer = input("\nGo ahead? [y/N] ").strip().lower()
        if not answer.startswith("y"):
            say("Okay, nothing was created.")
            return
    say("")

    full = ensure_repo(backlog)
    ensure_labels(backlog, full)
    ensure_milestones(backlog, full)
    issue_urls = ensure_issues(backlog, full)
    board_url = ensure_project(backlog, full, owner, issue_urls)

    say("\nAll done!")
    say(f"  Repository : https://github.com/{full}")
    say(f"  Issues     : https://github.com/{full}/issues")
    say(f"  Milestones : https://github.com/{full}/milestones")
    say(f"  Board      : {board_url}")
    say("\nOne last step on the website: open the board, click the small arrow next to the view")
    say("name (\"View 1\"), choose Layout → Board, then click Save. Your issues now show as cards in")
    say("Todo / In Progress / Done columns.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        say("\nStopped. Run the script again any time; it continues where it left off.")
        sys.exit(130)
