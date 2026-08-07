#  Miraclib Single Cell Analysis

Analysis pipeline and interactive dashboard for a clinical trial
cell count data (`cell-count.csv`).

## Installation

```bash
make setup      # installs pandas, matplotlib, scipy, streamlit
make pipeline   # Part 1: builds cell-count.db and loads cell-count.csv and creates a relational database
                # Part 2: generates part2_frequencies.csv, displaying the relative frequency of each cell population
                # Part 3: generates part3_stats.csv, compare the differences in cell population relative frequencies of melanoma patients receiving miraclib who respond versus those who do not. creates a boxplot for better visualization. identifies the most significant cell population after this treatment.
                # Part 4: generates part4_baseline_samples.csv, part4_by_project.csv, part4_by_response.csv, part4_by_sex.csv. create baseline samples from all malenoma PBMC from patients who have been treated with miraclib at time 0.
make dashboard  # starts the streamlit dashboard
```

Each script can also be run individually, in order:

```bash
python load_data.py         # Part 1
python data_overview.py     # Part 2
python statistical_analysis.py      # Part 3
python data_subset_analysis.py      # Part 4
streamlit run dashboard.py  # dashboard
```

`load_data.py` is safely re-runnable: it deletes and rebuilds `cell_counts.db`
from scratch each time, so re-running the pipeline never leaves stale data
behind.

## Dashboard

[Link to the running dashboard goes here]

## Database schema

The data is modeled as four normalized tables that mirror the natural
hierarchy of a clinical trial: **project → subject → sample → cell count**.

```
projects (project_id)
  └── subjects (subject_id, project_id, condition, age, sex, treatment, response)
        └── samples (sample_id, subject_id, sample_type, time_from_treatment_start)
              └── cell_counts (sample_id, population, count)
```

### Why this design

- A subject's `condition`, `treatment`, and `response` are fixed properties of 
  that person, not of any one blood draw. 
  Storing them once in `subjects` (rather than repeating them on every
  sample and every population row, as the flat CSV does) means an update or
  correction only has to happen in one place, and there is no risk of the
  same subject having contradictory `treatment` values across rows.
- `cell_counts` is "long format", meaning one row per (sample, population),
  instead of one column per population as in the raw CSV. Adding a new immune cell
  population in the future (e.g. a 6th marker) requires zero schema changes
  and zero `ALTER TABLE` statements. It's just new rows with a new
  `population` value. A wide table, by contrast, would need a migration
  every time the assay panel changes.
- Foreign keys express the real hierarchy. (`subjects.project`,
  `samples.subject`, `cell_counts.sample`), which lets every question
  in Parts 2-4 be answered with a straightforward `JOIN` + `WHERE` +
  `GROUP BY`, instead of pandas merging on a flat table.
- Indexes on the foreign key columns and on `population` keep the
  `JOIN`/`GROUP BY` queries used throughout Parts 2-4 fast even as row counts
  grow, since SQLite can use them instead of scanning full tables.

### How this scales

The current schema keeps working well for larger datasets according to the following reasons:

1. The `subjects` and `samples` tables grow with the number of
  patients/samples, but stay narrow (a handful of columns each), so they
  remain cheap to scan, filter, and index even at 100x today's row
  counts.
2. The long-format `cell_counts` table grows linearly with
  `n_samples * n_populations`. This is the largest table by row count, but
  each row is tiny (4 integer/text fields), and it is exactly the shape
  SQL is good at aggregating (`GROUP BY population`, `GROUP BY sample_id`,
  `SUM(count)`, etc.) without needing a schema change.
3. New analytics types plug in as new queries, not new tables. Because
  every population is a row rather than a column, adding a totally new kind
  of analysis (for example comparing time points, comparing across projects,
  computing correlations between populations) is a `SELECT ... GROUP BY`
  away, not a data modeling problem. The same is true for new sample
  metadata (for instance adding a "batch" or "site" column to `samples`). It's an
  additive column, not a restructuring of existing tables.

## Code structure

Each analytical part from the assignment has its own script, so the
mapping from requirement to code is explicit and each piece can be run,
tested, or debugged independently:

| File | Purpose |
|---|---|
| `load_data.py` | **Part 1.** Initializes `cell_counts.db` and loads every row of `cell-count.csv` into `projects` / `subjects` / `samples` / `cell_counts`. |
| `data_overview.py` | **Part 2.** Computes per sample and per population relative frequency and writes `outputs/part2_frequencies.csv`. |
| `statistical_analysis.py` | **Part 3.** Filters to melanoma + miraclib + PBMC samples, compares responders vs non-responders per population with a Mann-Whitney U test, and saves a boxplot (`outputs/part3_boxplot.png`) and a stats table (`outputs/part3_stats.csv`). |
| `data_subset_analysis.py` | **Part 4.** Filters to day0 melanoma + miraclib + PBMC samples and breaks the subset down by project, response, and sex. |
| `dashboard.py` | Streamlit dashboard that displays the outputs of Parts 2-4 interactively (falls back to recomputing from the database live if the `outputs/` CSVs aren't present yet, except for tab 2). |
| `Makefile` | `make setup`, `make pipeline`, `make dashboard` — see "How to run this" above. |

### Design rationale

- One script per Part: keeps each analysis self-contained and directly
  traceable to the assignment requirements.
- Operational Simplicity: Avoided using a separate `chema.db` file to keep the project     footprint as minimal as possible. Fewer external files mean fewer points of failure, making the application easier to deploy and ensuring it won't break if a secondary file is accidentally misplaced or omitted.
- SQL does the heavy filtering/joining, pandas does the shaping: Each
  script issues one focused SQL query against `cell_counts.db`, then
  uses pandas only for percentage math, grouping, and formatting the final
  table. We get what data do I need from SQL where it
  belongs, and heavier manipulations in Python.
- Scripts write to `outputs/` and are independently runnable: Every
  script can be run on its own (`python part3_stats.py`) and also chains
  together via `make pipeline`. The dashboard reads from `outputs/` when
  available and only recomputes from the database as a fallback, so the
  dashboard stays fast and the pipeline output is the single source of
  truth for what we see.
- Mann-Whitney U test: (rather than a t-test) was chosen for Part 3
  because relative-frequency percentages are bounded and often skewed, so a
  non-parametric test that doesn't assume normally-distributed data is a
  safer default for convincing Yah D'yada of a real effect.
- Replaced static boxplot chart with interactive rendering. This gives users visibility into the underlying dataset numbers. Ensuring the dashboard is fully functional rather than just a presentation layer.
