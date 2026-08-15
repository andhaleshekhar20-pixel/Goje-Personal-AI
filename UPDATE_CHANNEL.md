# Goje update channel

Goje uses this private repository as its update source.

The desktop app reads `version.json` from `main`. If the remote version is newer,
it downloads the repository archive, stages it, backs up the current application,
and merges changed application files while preserving user data/config/plugins.

Preserved on update:
- data
- config
- plugins
- ai_inbox
- backups
- memory
- .env
- .venv

For a private repository, the desktop app needs a fine-grained GitHub token with
Contents: Read-only permission for this repository. The token is stored locally
in `config/github_token.txt` and is excluded from Git by `.gitignore`.

Future development workflow:
1. Build/test the next Goje version.
2. Update `version.json`.
3. Commit the changed application files.
4. Goje users click Update and receive the changes automatically.
