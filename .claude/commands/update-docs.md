---
description: Update documentation based on changes made to commands and project structure
allowed-tools: Bash, Codebase, Edit
---

# Update Documentation Workflow

This command updates project documentation to reflect the current state of commands and structure.

## Step 1: Analyze Current Structure

First, run the analysis script to gather information about all commands:

bash .claude/commands/scripts/update-docs.sh

This will:
- Scan all `.claude/commands/*.md` files to find available commands
- Create backups of documentation files
- Update README.md command table and counts
- Update CUSTOMIZING.md with structure information
- Report what commands exist vs what's documented

## Step 2: Review the Output

The script will show you:
- Which commands are available (from `.claude/commands/*.md`)
- Which commands are documented in SKILLS.md
- Which commands are missing documentation

## Step 3: Update SKILLS.md

After reviewing the script output, I (Claude) will:

1. **Check which commands are missing from SKILLS.md** by comparing:
   - Commands in `.claude/commands/` directory
   - Commands documented in SKILLS.md

2. **For each missing command**, I will:
   - Read the command's `.md` file to understand its purpose
   - Read the corresponding `.sh` script to understand its implementation
   - Generate comprehensive documentation following the existing pattern in SKILLS.md
   - Add it to the appropriate section

3. **Update the Table of Contents** to include all commands

4. **Verify consistency** across README.md, CUSTOMIZING.md, and SKILLS.md

## What Gets Updated

- **README.md**: Command count, command table, installation instructions
- **CUSTOMIZING.md**: Script paths, architecture explanations
- **SKILLS.md**: Full documentation for each command (this requires Claude's intelligence)

The bash script handles mechanical updates (counts, paths, tables), while Claude handles content generation for missing command documentation.
