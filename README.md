# tsurutalab plugins for Claude Code

Skills that stop Claude from reporting a result the evidence cannot yet support. Four of them
build the control before the comparison. knowledge-ledger keeps count of the code the agent wrote that
you have not yet explained, and token-lens puts a cat in the status line that runs as fast as you
spend.

```
/plugin marketplace add tsurutanmen/claude-plugins
/plugin install verifygate@tsurutalab
```

Install any of them the same way. Each skill loads when the task matches its description, or
call it directly, for example `/verifygate:verifygate`.

| Plugin | Use it when | What it prevents |
|---|---|---|
| [verifygate](https://github.com/tsurutanmen/verifygate) | You hand a coding task to another agent (Codex, a subagent, a teammate) | Accepting "done" when the check was already green before the work, or when the removed code was moved into a comment |
| [strictnull](https://github.com/tsurutanmen/strictnull) | A graph is called non-random, clustered, or "better than a random network" | Crediting wiring for what the degree sequence alone produces |
| [searchdiff](https://github.com/tsurutanmen/searchdiff) | Someone asks whether a title or content change helped search traffic | A before/after that mixes the change with the season and algorithm updates |
| [sameness](https://github.com/tsurutanmen/sameness) | Two or more pages of a site were built or edited | Pages that pass one by one but together read as one template |
| [token-lens](plugins/token-lens) | You want to see how fast the session is using your limit | Finding out the five-hour window is full only when it is |
| [knowledge-ledger](plugins/knowledge-ledger) | The agent writes code you will have to maintain | Shipping code nobody on the team can explain, without anyone noticing how much of it there is |

## The command-line tools

The skills call a small Python tool. Claude installs it when it first needs it, or install it yourself:

```
pip install strictnull sameness searchdiff
pip install git+https://github.com/tsurutanmen/verifygate
```

Source, tests, and full documentation live in each tool's own repository, linked above.
knowledge-ledger and token-lens have no package to install: their scripts ship inside the plugins and use only the
Python standard library.

## License

MIT
