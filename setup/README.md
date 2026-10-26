# Setting up the GitHub board

`setup_github.py` creates everything on your GitHub account in one go:

- the repository, with these docs
- the labels and the milestones (one per iteration)
- 29 issues (user stories and tasks)
- the project board

Everything it creates comes from `backlog.json`, so you can change things there first. For example, you can change the repository name, make it `"private"`, or move the due dates.

## 1. Install the GitHub CLI (`gh`)

Check whether you already have it:

```bash
gh --version
```

If that prints **2.40 or newer**, skip to step 2. Otherwise, install the current version from GitHub's official package repository. The version in Pop!_OS/Ubuntu 22.04's own repository (2.4) is too old for project boards.

```bash
sudo wget -qO /usr/share/keyrings/githubcli-archive-keyring.gpg https://cli.github.com/packages/githubcli-archive-keyring.gpg
sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh
```

## 2. Log in

```bash
gh auth login
```

Choose **GitHub.com**, then **HTTPS**, then **Yes** (to use it for git), then **Login with a web browser**. Copy the code it shows and paste it into the browser page.

The script also asks GitHub for permission to manage project boards. When it shows a second code, approve it the same way.

## 3. Preview, then run

From the project folder:

```bash
python3 setup/setup_github.py --dry-run
```

This shows everything that would be created, without changing anything. When it looks right, run:

```bash
python3 setup/setup_github.py
```

It takes about a minute. If anything goes wrong halfway, fix it and run it again: anything already created is skipped.

## 4. Switch the board to columns

On the website, open the board and click the small arrow next to the view name ("View 1"). Choose **Layout → Board**, then **Save**. Your issues now show as cards in **Todo / In Progress / Done** columns.

Optional: add a **Backlog** or **In Review** column with the **+** at the right of the board.

## Adding a column later

To add a column after the board is set up, use `add_status_column.py` rather than editing the Status field by hand. When GitHub replaces the list of columns, cards can lose their column. The script keeps every card where it is. Preview first:

```bash
python3 setup/add_status_column.py Testing --before Done --dry-run
```

It shows the columns now and after, and changes nothing. Then add it:

```bash
python3 setup/add_status_column.py Testing --before Done
```

It saves a backup of every card's column first, then checks afterwards that every card is still in place and puts back any that moved. It reads the account and board name from `backlog.json`. Use `--owner` and `--project` for a different board, `--color` to pick the colour (purple by default), and `--yes` to skip the confirmation. If the column already exists, it changes nothing. If the new column doesn't show on the board, scroll to the right of the columns, click **+** and tick it.
