# tsurutalab plugins for Claude Code

Four skills that build the control before the comparison. Each one stops Claude from reporting a
result that the data cannot yet support.

```
/plugin marketplace add tsurutanmen/claude-plugins
/plugin install verifygate@tsurutalab
```

Install any of the four the same way. Each skill loads when the task matches its description, or
call it directly, for example `/verifygate:verifygate`.

| Plugin | Use it when | What it prevents |
|---|---|---|
| [verifygate](https://github.com/tsurutanmen/verifygate) | You hand a coding task to another agent (Codex, a subagent, a teammate) | Accepting "done" when the check was already green before the work, or when the removed code was moved into a comment |
| [strictnull](https://github.com/tsurutanmen/strictnull) | A graph is called non-random, clustered, or "better than a random network" | Crediting wiring for what the degree sequence alone produces |
| [searchdiff](https://github.com/tsurutanmen/searchdiff) | Someone asks whether a title or content change helped search traffic | A before/after that mixes the change with the season and algorithm updates |
| [sameness](https://github.com/tsurutanmen/sameness) | Two or more pages of a site were built or edited | Pages that pass one by one but together read as one template |

## The command-line tools

The skills call a small Python tool. Claude installs it when it first needs it, or install it yourself:

```
pip install strictnull sameness searchdiff
pip install git+https://github.com/tsurutanmen/verifygate
```

Source, tests, and full documentation live in each tool's own repository, linked above.

## License

MIT
