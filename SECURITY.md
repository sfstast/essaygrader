# Keeping credentials private

Store production secrets in Render Environment settings and local secrets in
an ignored `.env` file. Never place real keys, database connection strings,
private keys, account database files, or student submissions in source code,
notebook outputs, issues, or screenshots.

The GitHub Actions secret scan checks the full fetched Git history with a
checksum-verified Gitleaks release. Findings are fully redacted in its output.
It needs no application secrets and receives only read access to the repository.
A clean scan is not a guarantee that every kind of private information is absent.

Before publishing a notebook, clear its outputs. Keep student datasets and model
weights in private storage; the model data, prepared data, runs, adapters, and
local database files are ignored. The public rubric and curated writing examples
are application resources, not account records.

If a real secret is ever committed, revoke or rotate it at its provider first.
Deleting the current file does not remove it from Git history. Coordinate any
history cleanup with repository maintainers; public copies and forks can persist.
Do not post a secret or a private security report in public GitHub issues.
