# domain-check

Rapidly check whether `.com` domains are available, via Verisign's RDAP
(`https://rdap.verisign.com/com/v1/domain/<name>`).

- Stdlib-only Python 3.9+ — no `pip install` needed
- Parallel requests with retry/backoff on 429/503
- Structured JSON output by default (easy for agents to parse)
- Accepts bare labels (`foo`), `foo.com`, or pasted URLs (`https://www.foo.com/path`)

## Usage

```bash
# One or more domains as args (JSON output)
./domain_check.py foo bar baz.com

# Human-readable
./domain_check.py --plain foo bar baz.com

# From a file (one per line; lines starting with # are comments)
./domain_check.py --file candidates.txt

# From stdin
printf "foo\nbar\n" | ./domain_check.py -

# Tuning
./domain_check.py --workers 4 --timeout 10 foo bar
```

## Output

JSON is a list of objects, one per input, preserving order:

```json
[
  {"input": "foo", "domain": "foo.com", "available": true,  "status": "available", "detail": null},
  {"input": "github", "domain": "github.com", "available": false, "status": "taken", "detail": null},
  {"input": "bad!", "domain": null, "available": null, "status": "invalid", "detail": "invalid label ..."}
]
```

`status` is one of `available`, `taken`, `invalid`, `error`.
Exit code is `0` if at least one check produced a definitive answer, `2` if every
check errored (e.g. no network).

## Notes

- Only `.com` is supported. Other TLDs return `status: invalid`.
- RDAP is authoritative for `.com` registration state, but a domain can still
  be reserved/premium even when `available` — confirm at a registrar before
  buying.
- Verisign rate-limits aggressive callers; the default of 4 workers with
  retry/backoff is a safe starting point.
