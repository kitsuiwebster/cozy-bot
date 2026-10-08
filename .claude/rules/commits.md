# Commit rules

Every commit Claude makes in this repo follows these rules. No exceptions.

- Atomic: one logical change per commit. Never mix a fix, a feature and a version bump in the same commit. If a change needs two explanations, it needs two commits.
- Type: only `feat:` or `fix:`. No `style:`, `refactor:`, `doc:`, `chore:` or anything else.
  - `feat:` adds or changes behaviour, UI or content (a UI tweak, a removed emoji, a version release).
  - `fix:` corrects something that was broken or wrong.
- Title in English, entirely lowercase, including product and library names (`couchdb`, `api`, `discord.py`). Example: `fix: run restore-task couchdb calls off the event loop`.
- Body optional, in English, normal capitalization, wrapped at 72 columns. It explains why, not what.
- Author: `kitsuiwebster <raphmartin1999@gmail.com>`.
- Never add a `Co-Authored-By` line or any other Claude or AI attribution, in commits or pull requests.
- Never use em dashes or en dashes anywhere in the message.

Before committing, check the title against: `^(feat|fix): [^A-Z]+$`.

Rewording is allowed only on commits that are not pushed yet (`git log origin/<branch>..<branch>`). Never rewrite pushed history.
