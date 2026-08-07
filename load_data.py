import sqlite3
import csv
from pathlib import Path
import os

DB_NAME = "cell-count.db"
CSV_NAME = "cell-count.csv"

def initialize_database(cursor):
    """Initialize the SQLite database with the schema of choice explained in README.md."

    Args:
        cursor (sqlite3.Cursor): the empty database to write on
    """
    
    # the projects table
    cursor.execute("""CREATE TABLE IF NOT EXISTS projects ("project" TEXT PRIMARY KEY);""")
         
    # the subjects table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            subject  TEXT PRIMARY KEY,
            project  TEXT NOT NULL,
            condition   TEXT NOT NULL,
            age         INTEGER,
            sex         TEXT,
            treatment   TEXT,
            response    TEXT,
            FOREIGN KEY (project) REFERENCES projects("project")
        );
    """)
         
    # the sample table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS samples (
            sample                TEXT PRIMARY KEY,
            subject                TEXT NOT NULL,
            sample_type                TEXT NOT NULL,
            time_from_treatment_start  INTEGER,
            FOREIGN KEY (subject) REFERENCES subjects(subject)
        );
    """)
         
    # the cell counts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cell_counts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            sample   TEXT NOT NULL,
            population  TEXT NOT NULL,
            count       INTEGER NOT NULL,
            FOREIGN KEY (sample) REFERENCES samples(sample)
        );
    """)
         
    # the indices for faster queries (GROUP BY / WHERE)
    cursor.execute(
        'CREATE INDEX IF NOT EXISTS idx_subjects_project ON subjects(project);')
         
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_samples_subject ON samples(subject);")
         
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_cellcounts_sample ON cell_counts(sample);")
         
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_cellcounts_population ON cell_counts(population);")


def _locate_path(csv_path: Path) -> bool:
    """fEnsure the directory exists."""
    if not os.path.exists(csv_path):
        print(f"Error: Could not locate '{csv_path}' in the root directory.")
        return False
    return True
    
def load_csv_data(cursor,path):
    if _locate_path(path):
        
        """Design a relational database schema effectively, 
        we will make sure we don't have data redundancy."""
        
        seen_projects = set()
        seen_subjects = set()
        seen_samples = set()

        projects_batch = []
        subjects_batch = []
        samples_batch = []
        cell_counts_batch = []

        # map target long-format keys to CSV column names
        cell_populations = [
            "b_cell",
            "cd8_t_cell",
            "cd4_t_cell",
            "nk_cell",
            "monocyte",
        ]
        
        """Load all the rows from cell-count.csv"""
        with open(path, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for row in reader:
                # handle optional/null data structures 
                proj_id = row["project"]
                subj_id = row["subject"]
                samp_id = row["sample"]

                age = int(row["age"]) if row.get("age") else None
                sex = row.get("sex")
                treatment = row.get("treatment")

                # response column clean up (maps empty values safely to Python None/SQL NULL)
                response = row.get("response")
                if not response or response.lower() in ["", "null", "none", "na"]:
                    response = None

                # gather uniquely identified projects
                if proj_id not in seen_projects:
                    seen_projects.add(proj_id)
                    projects_batch.append((proj_id,))

                # gather uniquely identified subjects
                if subj_id not in seen_subjects:
                    seen_subjects.add(subj_id)
                    subjects_batch.append(
                        (subj_id,
                        proj_id,
                        row["condition"],
                        age,
                        sex,
                        treatment,
                        response,))

                # gather uniquely identified blood samples
                if samp_id not in seen_samples:
                    seen_samples.add(samp_id)
                    time_point = (
                        int(row["time_from_treatment_start"])
                        if row.get("time_from_treatment_start")
                        else None
                    )
                    samples_batch.append(
                        (samp_id, subj_id, row["sample_type"], time_point)
                    )

                # pivot columns to long format rows (1 sample row turns into 5 cell rows)
                # long format helps us modify the schema for new data better, handle missing data,
                # computing arithmatics across all cell types more effectively,
                # helps filtering and searching
                for pop in cell_populations:
                    if pop in row and row[pop]:
                        cell_counts_batch.append((samp_id, pop, int(row[pop])))
                        
        # run batched transactional execution commands sequentially
        # batch running will help us scale this code for larger scale datasets
        cursor.executemany("INSERT OR IGNORE INTO projects (project) VALUES (?);",
            projects_batch,)
        
        cursor.executemany("INSERT OR IGNORE INTO subjects (subject, project, condition, age, sex, treatment, response) VALUES (?, ?, ?, ?, ?, ?, ?);",
            subjects_batch,)
        
        cursor.executemany("INSERT OR IGNORE INTO samples (sample, subject,sample_type, time_from_treatment_start) VALUES (?, ?, ?, ?);",
            samples_batch,)
        
        cursor.executemany("INSERT INTO cell_counts (sample, population, count) VALUES (?, ?, ?);",
            cell_counts_batch,)

        print(f"\nYay! '{DB_NAME}' created and loaded all data.")
   
def main():
    
    # delete old file completely from scratch if it exists
    if Path(DB_NAME).exists():
            try:
                Path(DB_NAME).unlink()
                print(f"Existing '{DB_NAME}' found and cleanly removed.")
            except OSError as e:
                print(f"Error purging old database file: {e}")
                return 
            
    # create an empty database only if the file with this name does not exist
    connection = sqlite3.connect(DB_NAME)

    # enforce rules that link related tables together
    connection.execute("PRAGMA foreign_keys = ON;")
    cursor = connection.cursor()

    try:
        initialize_database(cursor)
        load_csv_data(cursor, CSV_NAME)
        connection.commit()

    except Exception as error:
        connection.rollback()
        print(f"\nError: Failed to load data. Details: {error}")

    finally:
        connection.close()


if __name__ == "__main__":
    main()