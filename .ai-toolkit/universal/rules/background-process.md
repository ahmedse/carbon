## Background Process Rule

Starting a long-running process incorrectly hangs the terminal forever.

```bash
# WRONG — stdin attached → terminal hangs
nohup cmd >log 2>&1 &

# CORRECT — fully detached
nohup cmd >log 2>&1 </dev/null &
setsid cmd >log 2>&1 </dev/null &
```

The `</dev/null` detaches stdin. Without it, the process holds the terminal open even after
the shell exits.

### For Project Servers
Always use the project's ops script, not raw commands:
```bash
./manage.sh start       # start detached
./manage.sh logs 100    # check logs (bounded output)
./manage.sh status      # confirm it's up
./manage.sh restart     # after changes
```

Never run `uvicorn`, `gunicorn`, `npm run dev`, or `python manage.py runserver` directly
in a session terminal — they will hang.

---

*Source: ~/ai-toolkit/universal/rules/background-process.md*
