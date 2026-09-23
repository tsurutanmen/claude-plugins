# knowledge-ledger for agents without Claude Code hooks

For Codex, Cursor, Copilot, Gemini CLI and any other agent that reads AGENTS.md.
Copy this section into the project's own AGENTS.md, with the path to
`kledger.py` adjusted.

## Recording what you wrote

After you finish a set of file edits, and before you hand control back to the
user, run:

```
python3 path/to/kledger.py record --git
```

It records the lines added since the last commit as agent-written. Run it
before the user commits. Running it again on the same uncommitted changes does
not inflate the count: a line is never counted more times than it appears in
the file.

## When the user asks what they don't understand

Follow `skills/knowledge-ledger/SKILL.md`. The user writes every explanation.
You check it against the code and record their text as they wrote it:

```
python3 path/to/kledger.py status
python3 path/to/kledger.py explain FILE --lines A-B < their_explanation.txt
```
