---
role: ANALYTIC,CODER
description: Git commands
when: Use for interaction with git
---

**Rules**
- DONT add to git file, if you hasnt created it!

---

Add file to repository
If you created new file - use this tool for adding to repository

$1 - path to file

```
git add "$1"
```

---

Show all git branches

```
git branch
```

---

Create git commit

$1 - message for commit

```
git commit . -m "$1"
```

---

Execute git diff command, compare current branch and other branch

$1 - branch name (use `git_branch` command for get list if branches)

```
git --no-pager diff $1
```

---

Run command git status

```
git status
```