"""Print "<scenario> <solver> <sweep_value>" of the first unfinished unit among the
given scenarios (in the order run.py would compute them), or nothing if all are done."""
import sys
from pathlib import Path

from config import CONFIGS
from run import load_done

for name in sys.argv[1:]:
    cfg = CONFIGS[name]
    _, done = load_done(Path(cfg.rundir) / "results.csv")
    for s in (x.strip().lower() for x in cfg.solvers):
        for v in cfg.sweep_values:
            for r in range(cfg.realizations):
                if (round(float(v), 4), r, s) not in done:
                    print(name, s, v)
                    sys.exit(0)
