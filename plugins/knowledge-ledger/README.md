# knowledge-ledger

A ledger of the lines a coding agent wrote into your project, and which of them you have
explained in your own words.

```
/plugin marketplace add tsurutanmen/claude-plugins
/plugin install knowledge-ledger@tsurutalab
```

## What it does

- A `PostToolUse` hook records the lines Claude writes with Write, Edit and MultiEdit into
  `.knowledge-ledger/ledger.jsonl`. For an edit, only the lines that are new count, not the
  surrounding context. Blank lines and lines with no letters or digits (`}`, `);`) are skipped.
- A line leaves the count when it disappears from the file, or when you rewrite it yourself.
  Lines are matched by content, so moving code around keeps the record.
- `status` shows, per file, how many agent-written lines are still there and how many you have
  explained. The difference is the debt.
- The skill runs an explain-it-back session: it shows you a block, you explain it, it checks your
  explanation against the code, and it records **your** text. It is told never to write the
  explanation for you.
- The ledger is a plain file meant to be committed, so the git history is the history of the debt.

```
$ python3 kledger.py status
AI-written lines still in the code: 4 of 4 (100%)
explained in your own words: 0   unexplained (debt): 4

 debt    AI  lines  file
    4     4      4  fizz.py
```

## Other agents

Agents without Claude Code hooks can run `kledger.py record --git` after their edits, which
records the lines added since the last commit. See [AGENTS.md](AGENTS.md).

## What it does not do

- It does not know about code the agent wrote before the plugin was installed.
- It cannot tell whether you wrote an explanation yourself. The skill tells the agent not to write
  it, and the ledger records who ran the command (`--by`, default `human`), nothing more.
- A 40-character minimum is the only check the script makes on an explanation. Whether it is
  right is judged in the conversation, not by the script.

## Tests

```
python -m unittest discover -s plugins/knowledge-ledger/tests
```

Standard library only. MIT.
