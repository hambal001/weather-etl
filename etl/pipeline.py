"""Run the full pipeline:  python -m etl.pipeline"""
import logging
import sys

from etl import config
from etl.extract import extract_all
from etl.load import get_engine, load
from etl.transform import transform


def run() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("pipeline")

    raw = extract_all()
    if not raw:
        log.error("Nothing extracted - all cities failed")
        return 1

    valid, rejected = transform(raw)
    if not rejected.empty:
        rejected.to_csv("rejected_rows.csv", index=False)
        log.warning("Wrote %d rejected rows to rejected_rows.csv", len(rejected))

    engine = get_engine(config.DATABASE_URL)
    load(engine, valid, rejected)
    return 0


if __name__ == "__main__":
    sys.exit(run())
