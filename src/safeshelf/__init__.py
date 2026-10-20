"""SafeShelf Tembisa: track everyday essentials from the delivery truck to the shelf.

The pipeline, one module per step:

    simulate.py   writes realistic daily CSV files (there's no real data feed yet)
    extract.py    finds the new files in data/incoming and reads them
    clean.py      writes names, codes and dates the same way every time
    validate.py   checks every row against the data quality rules
    load.py       puts the good rows into the SQLite database
    privacy.py    POPIA rules: no phone or ID numbers, old truck locations removed
    reports.py    turns the database into the daily report and the police report
    pipeline.py   runs the steps in order

Run everything with:  python -m safeshelf run --days 30
"""
