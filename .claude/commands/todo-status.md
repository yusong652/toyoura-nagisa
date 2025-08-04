Check current project todo status and progress.

Read today's todo file from: .claude/todos/todo_$(date +%Y-%m-%d).md

If today's file doesn't exist, check the most recent todo file in .claude/todos/

Actions:
1. Compare the todo file with current TodoWrite tool status
2. Update the todo file by marking completed items with [x] instead of [ ]
3. Add completion timestamps where applicable

Show:
- Current todo list with completion status
- Progress summary (X/Y tasks completed)
- Any high-priority or blocked items
- Time spent vs estimates if available
- Suggestions for next steps

The updated todo file should reflect the actual progress tracked in the session.