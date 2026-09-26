# Contributing

This repository is my GitHub profile page, so there is not much to build here. Typo fixes and broken-link reports are welcome.

- **Found a bug in one of my projects?** Open the issue in that project's repository.
- **Changing the diagram:** edit `scripts/build_diagram.py`, never the SVGs by hand, then regenerate:

  ```bash
  python3 scripts/build_diagram.py
  ```

- **Before opening a pull request**, run the same checks as CI (Python 3.11+, no dependencies):

  ```bash
  python3 -m unittest discover -s tests -v
  python3 scripts/build_diagram.py --check
  ruff check . && ruff format --check .
  ```

Keep `README.md` and `README.pt-BR.md` in sync: the tests fail if they link to different repositories.
