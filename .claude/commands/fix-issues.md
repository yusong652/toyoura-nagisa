# Fix Issues Command

## Context Analysis
Before fixing issues, analyze the repository and available issues:
1. Use `gh issue list` to view all open issues
2. Use `gh issue view <number>` to get detailed information about specific issues
3. Check issue labels, assignees, and priorities
4. Read issue descriptions and comments for context

## Issue Selection
When selecting issues to fix:
- **Priority**: Focus on high-priority issues first (bugs > features > enhancements)
- **Complexity**: Start with issues you can reasonably fix
- **Labels**: Look for "good first issue", "bug", "help wanted" labels
- **Assignment**: Check if issues are already assigned

## Workflow Steps

### 1. List and Analyze Issues
```bash
# List all open issues
gh issue list --state open

# View specific issue details
gh issue view <issue_number>

# List issues with specific labels
gh issue list --label "bug"
gh issue list --label "good first issue"
```

### 2. Select and Assign Issue
```bash
# Self-assign an issue
gh issue edit <issue_number> --add-assignee @me

# Add a comment to indicate you're working on it
gh issue comment <issue_number> --body "I'm working on this issue"
```

### 3. Create Feature Branch
```bash
# Create a new branch for the fix
git checkout -b fix/issue-<issue_number>-<brief-description>
```

### 4. Implement the Fix
- Read the issue description carefully
- Reproduce the issue if it's a bug
- Implement the fix following project conventions
- Add tests if applicable
- Update documentation if needed

### 5. Test the Fix
```bash
# Run tests
uv run pytest

# Run linting and type checking
npm run lint      # for frontend
uv run ruff      # for backend (if configured)
```

### 6. Commit with Issue Reference
```bash
# Commit with issue reference
git add .
git commit -m "fix: <description> (#<issue_number>)

<detailed explanation>

Fixes #<issue_number>"
```

### 7. Create Pull Request
```bash
# Push branch
git push -u origin fix/issue-<issue_number>-<brief-description>

# Create PR referencing the issue
gh pr create --title "Fix: <description>" --body "## Summary
This PR fixes issue #<issue_number>

## Changes
- <change 1>
- <change 2>

## Test Plan
- <test 1>
- <test 2>

Fixes #<issue_number>" --assignee @me
```

### 8. Update Issue Status
```bash
# Add a comment about the PR
gh issue comment <issue_number> --body "PR #<pr_number> has been created to fix this issue"

# After PR is merged, the issue will be automatically closed if you used "Fixes #<issue_number>" in the PR
```

## Best Practices

### Communication
- Comment on issues before starting work
- Update issue status regularly
- Ask for clarification if requirements are unclear
- Mention related issues in PRs

### Code Quality
- Follow existing code style and conventions
- Add appropriate tests
- Update documentation
- Ensure CI passes before requesting review

### Issue Resolution
- Verify the fix resolves the original issue
- Test edge cases
- Consider backward compatibility
- Document any breaking changes

## Common Issue Types

### Bug Fixes
1. Reproduce the bug locally
2. Add a failing test case
3. Implement the fix
4. Verify test passes
5. Check for regressions

### Feature Requests
1. Understand requirements fully
2. Design solution architecture
3. Implement incrementally
4. Add comprehensive tests
5. Update documentation

### Documentation Issues
1. Identify what's missing or incorrect
2. Update relevant documentation
3. Ensure accuracy and clarity
4. Add examples if helpful

## Automation

### Quick Fix Workflow
For simple bug fixes:
```bash
# One-liner to view and start working on an issue
ISSUE_NUM=123 && gh issue view $ISSUE_NUM && gh issue edit $ISSUE_NUM --add-assignee @me && git checkout -b fix/issue-$ISSUE_NUM
```

### Issue Templates
Use issue templates to ensure consistent information:
- Bug reports should include reproduction steps
- Feature requests should include use cases
- Documentation issues should reference specific sections

Remember: Always communicate clearly, test thoroughly, and follow project guidelines!