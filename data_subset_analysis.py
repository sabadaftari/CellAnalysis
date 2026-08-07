import sqlite3
import pandas as pd
import os


DB_PATH = "cell-count.db"
OUTPUT_DIR = "outputs/"

BASELINE_CSV = OUTPUT_DIR+ "part4_baseline_samples.csv"
BY_PROJECT_CSV = OUTPUT_DIR+ "part4_by_project.csv"
BY_RESPONSE_CSV = OUTPUT_DIR+ "part4_by_response.csv"
BY_SEX_CSV = OUTPUT_DIR+ "part4_by_sex.csv"

def load_baseline_subset(conn: sqlite3.Connection) -> pd.DataFrame:
    """
    Step 1: melanoma, PBMC, baseline (time_from_treatment_start = 0),
    treatment = miraclib. One row per sample/subject (no need to touch
    cell_counts here -- this is a subject/sample-level filter).
    """
    query = """
        SELECT
            su.subject,
            su.project,
            su.condition,
            su.sex,
            su.treatment,
            su.response,
            sm.sample,
            sm.sample_type,
            sm.time_from_treatment_start
        FROM subjects su
        JOIN samples sm ON sm.subject = su.subject
        WHERE su.condition = 'melanoma'
          AND sm.sample_type = 'PBMC'
          AND su.treatment = 'miraclib'
          AND sm.time_from_treatment_start = 0
    """
    return pd.read_sql_query(query, conn)

def main() -> None:
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"Could not find {DB_PATH}. Run `python load_data.py` first."
        )

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    try:
        df = load_baseline_subset(conn)
    finally:
        conn.close()

    df.to_csv(BASELINE_CSV, index=False)

    # how many smaples from each project
    by_project = (
        df.groupby("project")["sample"]
        .count()
        .reset_index()
        .rename(columns={"sample": "n_samples"})
    )
    by_project.to_csv(BY_PROJECT_CSV, index=False)

    # how many subjects were responders/non-responders
    by_response = (
        df.drop_duplicates("subject")
        .groupby("response")["subject"]
        .count()
        .reset_index()
        .rename(columns={"subject": "n_subjects"})
    )
    by_response.to_csv(BY_RESPONSE_CSV, index=False)

    # how many subjects were males/females
    by_sex = (
        df.drop_duplicates("subject")
        .groupby("sex")["subject"]
        .count()
        .reset_index()
        .rename(columns={"subject": "n_subjects"})
    )
    by_sex.to_csv(BY_SEX_CSV, index=False)


if __name__ == "__main__":
    
    main()
