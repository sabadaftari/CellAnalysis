import sqlite3
import pandas as pd
import os
from pathlib import Path

DB_PATH = "cell-count.db"
OUTPUT_DIR = "outputs/"
OUTPUT_CSV_NAME = OUTPUT_DIR + "part2_frequencies.csv"
QUERY = """
        SELECT
            sample AS sample,
            population,
            count
        FROM cell_counts
        ORDER BY sample, population
    """
    
def compute_frequencies(conn: sqlite3.Connection, QUERY:str) -> pd.DataFrame:
    """Return one row per (sample, population) with count, total_count, percentage."""
    
    # because we want to write a python program, we design the query to stay simple and do the 
    # heavy math calculations with python.
    df = pd.read_sql_query(QUERY, conn)

    # total_count per sample = sum of counts across all 5 populations
    totals = df.groupby("sample")["count"].sum().rename("total_count")
    df = df.merge(totals, on="sample")

    df["percentage"] = (df["count"] / df["total_count"] * 100).round(2)
    return df

def _configure_dir(path: Path) -> None:
    """Ensure the directory exists, if not create one."""
    os.makedirs(path, exist_ok=True)
    
def main() -> None:
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"Could not find {DB_PATH}. Run `python load_data.py` first."
        )

    _configure_dir(OUTPUT_DIR)

    # connect to the database
    conn = sqlite3.connect(DB_PATH)
    try:
        df = compute_frequencies(conn, QUERY) 
        # reorder columns to match the required schema exactly, do not have duplicated columns to drop
        df = df[["sample", "total_count", "population", "count", "percentage"]]
    finally:
        conn.close()

    df.to_csv(OUTPUT_CSV_NAME, index=False)
    print(f"Wrote {len(df)} rows to {OUTPUT_CSV_NAME}")
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
