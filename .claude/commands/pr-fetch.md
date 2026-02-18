---
description: Fetch PR branch locally, show diff, and run tests
allowed-tools: Bash
argument-hint: <pr-number>
---

Execute the PR fetch automation script:

bash .claude/commands/scripts/pr-fetch.sh $ARGUMENTS

This fetches and checks out a PR branch locally, shows the diff, and optionally runs tests.
