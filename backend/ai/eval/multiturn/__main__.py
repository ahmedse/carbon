"""CLI entry point for multi-turn runner.

python -m ai.eval.multiturn --report /tmp/out.json [--scripts <glob>] [--keepdb] [--verbose]
"""

import sys

from .runner import main

if __name__ == "__main__":
    sys.exit(main())
