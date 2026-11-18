"""Run the whole SupeRR Selector pipeline end to end.

    python run_pipeline.py                 # every step, in order
    python run_pipeline.py --from cup      # resume from a step (earlier outputs must already exist)
    python run_pipeline.py --only tsp      # run a single step
    python run_pipeline.py --skip validate_rankings   # e.g. skip the slow bootstrap

Steps (each reads the previous step's files in data/processed and writes a report to outputs/):
  validate           clean data + prove data assumptions          (~10 s)
  match_state        situation before/after every ball            (~10 s)
  msp_inn2           chase win probability, leverage, WPA          (~10 s)
  msp_inn1           first-innings win probability; join innings  (~5 min)
  tsp                tournament stakes per team per match          (~15 s)
  ipp                form pressure per player per match            (~10 s)
  select_pressure    choose pressure weights / cut-off out of sample (~6 min)
  cup                ratings and rankings (+ sensitivity variants) (~1 min)
  validate_rankings  separation, bootstrap, stability, charts      (~5 min)
"""
import argparse
import importlib
import time

STEPS = [
    ("validate", "src.validate"),
    ("match_state", "src.match_state"),
    ("msp_inn2", "src.pressure_msp"),
    ("msp_inn1", "src.pressure_msp1"),
    ("tsp", "src.pressure_tsp"),
    ("ipp", "src.pressure_ipp"),
    ("select_pressure", "src.select_pressure"),
    ("cup", "src.cup"),
    ("validate_rankings", "src.validate_rankings"),
]


def main():
    names = [n for n, _ in STEPS]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="start", choices=names, help="start from this step")
    ap.add_argument("--only", choices=names, help="run just this step")
    ap.add_argument("--skip", nargs="*", default=[], choices=names, help="steps to skip")
    a = ap.parse_args()

    todo = names[names.index(a.start):] if a.start else names
    if a.only:
        todo = [a.only]
    todo = [n for n in todo if n not in a.skip]

    t_all = time.time()
    for name, module in STEPS:
        if name not in todo:
            continue
        print(f"\n{'=' * 70}\n>>> {name}  ({module})\n{'=' * 70}")
        t = time.time()
        importlib.import_module(module).main()
        print(f"<<< {name} finished in {time.time() - t:.0f}s")
    print(f"\nPipeline finished in {time.time() - t_all:.0f}s. Rankings: outputs/rankings_batting.csv, outputs/rankings_bowling.csv")


if __name__ == "__main__":
    main()
