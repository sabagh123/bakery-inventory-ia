---
name: ibcs-bakery-management
description: "Development agent for the IB Computer Science IA bakery management system."
---

# IB CS IA Bakery Management Agent

Work only on the existing bakery management project in this workspace.

The project uses:
- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript
- pytest

## Development rules

- Focus only on the milestone or feature requested by the user.
- Preserve the existing Flask/SQLite architecture.
- Preserve the database design from the existing project unless a change is genuinely required.
- Do not rewrite the project from scratch.
- Do not perform broad refactors unless explicitly requested.
- Edit the existing project files directly.
- Keep code simple, readable, and understandable by an IB Computer Science student.
- Use simple variable and function names consistent with the existing project.
- Avoid unnecessary comments and docstrings.
- Preserve existing working functionality.
- Do not remove or weaken existing tests.
- Run `python -m pytest` after implementing a feature.
- If tests fail because of your changes, investigate and fix them.
- Do not commit or push to Git unless the user explicitly asks.
- Do not change Criterion C architecture or planned behavior without explaining why.
- At the end of each implementation task, report:
  - files changed
  - functionality implemented
  - pytest result
  - any errors fixed
  - any design changes made
Use this agent for targeted development tasks in this project only.