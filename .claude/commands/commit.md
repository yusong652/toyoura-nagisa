# Git Commit Command

Please create a git commit following these requirements.

Note: These requirements are based on the project's commit guidelines defined in:
- `CLAUDE.md` (lines 376-397)
- `.claude/CLAUDE.local.md` (lines 278-286)

## Commit Requirements

1. **Review Changes**: First run these commands in parallel to understand the current state:
   - `git status` to see all untracked files
   - `git diff` to see both staged and unstaged changes
   - `git log -5 --oneline` to see recent commit message style

2. **Analyze Changes**:
   - Summarize the nature of changes (new feature, enhancement, bug fix, refactoring, test, docs, etc.)
   - Ensure the message accurately reflects the changes and their purpose
   - Check for any sensitive information that shouldn't be committed

3. **Commit Message Format**:
   - Use conventional commit format: `<type>: <description>`
   - Types: feat (new feature), fix (bug fix), docs (documentation), style (formatting), refactor (code restructuring), test (tests), chore (maintenance)
   - Concise description (1-2 sentences) focusing on "why" rather than "what"
   - Frame changes in the context of the aiNagisa voice-enabled AI assistant project

4. **Attribution Requirements**:
   - Project Attribution: Reference the aiNagisa project repository URL `https://github.com/yusong652/aiNagisa`
   - Co-authorship: Use "Co-authored-with: Nagisa Toyoura <nagisa.toyoura@gmail.com>"
   - Do NOT use any external tool attributions

5. **Commit Example**:
```bash
git commit -m "$(cat <<'EOF'
feat: improve tool extraction logic

Enhance MCP tool result processing for better LLM integration
in the aiNagisa voice-enabled AI assistant.

https://github.com/yusong652/aiNagisa

Co-authored-with: Nagisa Toyoura <nagisa.toyoura@gmail.com>
EOF
)"
```

## Execution Steps

1. Run git status, git diff, and git log commands in parallel
2. Add relevant untracked files to staging area
3. Create commit using HEREDOC format for proper formatting
4. Run git status to confirm commit succeeded
5. If commit fails due to pre-commit hooks, retry ONCE to include automated changes

## Important Notes

- NEVER update git config
- DO NOT push to remote unless explicitly requested
- Don't create empty commits if there are no changes
- Always use HEREDOC for commit messages to ensure proper formatting
- Include project URL and co-authorship in every commit