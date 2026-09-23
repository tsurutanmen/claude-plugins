---
name: knowledge-ledger
description: Show which agent-written lines the user has not yet explained, and run an explain-it-back session that pays that debt down. Use when the user asks what they don't understand in their own code, asks to be quizzed on what the agent wrote, says "knowledge ledger" or "knowledge debt", or at the end of a long coding session when they want to check they can still explain the result.
---

# knowledge-ledger

A hook records every line the agent writes with Write, Edit or MultiEdit into
`.knowledge-ledger/ledger.jsonl` in the project. A line leaves the ledger when
it disappears from the code, or when the user rewrites it themselves. A line is
**explained** once the user has described it in their own words.

**Debt** = agent-written lines still in the code that the user has not explained.

The script is `scripts/kledger.py` in this skill's directory. Standard library
only. Call it with `python3` (or `python` on Windows).

## Commands

```
python3 <skill-dir>/scripts/kledger.py status            # table, highest debt first
python3 <skill-dir>/scripts/kledger.py status --json
python3 <skill-dir>/scripts/kledger.py explain FILE --lines A-B   # explanation on stdin
python3 <skill-dir>/scripts/kledger.py record --git      # agents without hooks: lines added since HEAD
```

## Explain-it-back session

1. Run `status`. Pick the file with the most debt, and in it a block of 5 to 30
   agent-written lines that belong together (one function, one branch).
2. Show the block with line numbers. Ask one question: what does this do, and
   why is it written this way? Do not hint at the answer.
3. **The user writes the explanation. You never write it for them,** never
   offer a draft to approve, and never paraphrase their words into something
   better before recording. The ledger measures what the user can say, not what
   you can.
4. Read the user's explanation against the code. If it is wrong or leaves out
   something that matters (an edge case, a side effect, why a guard is there),
   say which part and let them try again. Do not correct it yourself.
5. When it holds up, record the user's text exactly as they wrote it:
   `explain FILE --lines A-B` with the text on stdin. Minimum 40 characters.
6. Report the new debt number, then offer the next block. Stop when the user
   says stop.

## Rules

- Do not run `explain` with text you wrote. If the user says "you explain it and
  mark it", explain it to them, then ask them to put it back in their own words.
- The ledger file is meant to be committed. Suggest committing it with the code.
- Debt is a count, not a grade. Do not describe a number as good or bad.
- Lines the agent wrote before the plugin was installed are not in the ledger.
  `record --git` only covers uncommitted changes.
