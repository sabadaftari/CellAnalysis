import sqlite3
import pandas as pd
import os
import matplotlib.pyplot as plt
from scipy import stats

from data_overview import compute_frequencies, _configure_dir

DB_PATH = "cell-count.db"
OUTPUT_DIR = "outputs/"
BOXPLOT_PNG = OUTPUT_DIR + "boxplot.png"
STATS_CSV = OUTPUT_DIR + "part3_stats.csv"

ALPHA = 0.05  # significance threshold 5%
MELANOMA_QUERY = """
        SELECT
            sm.sample   AS sample,
            su.response    AS response,
            cc.population  AS population,
            cc.count       AS count
        FROM samples sm
        JOIN subjects su ON su.subject = sm.subject
        JOIN cell_counts cc ON cc.sample = sm.sample
        WHERE su.condition = 'melanoma'
          AND su.treatment = 'miraclib'
          AND sm.sample_type = 'PBMC'
    """
def load_melanoma(conn: sqlite3.Connection, query:str) -> pd.DataFrame:
    
    df = compute_frequencies(conn, MELANOMA_QUERY)
    comparison  = df.groupby(["response","population"])["percentage"].mean().unstack(level=0)
    comparison["difference"] = comparison["yes"]-comparison["no"]
    print(comparison)
    return df
    
def make_boxplot(df: pd.DataFrame, path: str) -> None:
    populations = sorted(df["population"].unique())
    fig, axes = plt.subplots(1, len(populations), figsize=(4 * len(populations), 5), sharey=False)

    if len(populations) == 1:
        axes = [axes]

    for ax, population in zip(axes, populations):
        subset = df[df["population"] == population]
        responder = subset[subset["response"] == "yes"]["percentage"]
        non_responder = subset[subset["response"] == "no"]["percentage"]

        ax.boxplot([responder, non_responder])
        ax.set_xticks([1, 2])
        ax.set_xticklabels(["Responder", "Non-responder"])
        ax.set_title(population)
        ax.set_ylabel("Relative frequency (%)")

    fig.suptitle("Cell population frequency: responders vs non-responders\n(melanoma, miraclib, PBMC)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run_significance_tests(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mann-Whitney U test per population (non-parametric, doesn't assume
    normality -- appropriate for small-ish clinical cohorts with skewed
    percentage data).
    """
    rows = []
    for population in sorted(df["population"].unique()):
        subset = df[df["population"] == population]
        # isolate percentages for both targets
        responder = subset[subset["response"] == "yes"]["percentage"]
        non_responder = subset[subset["response"] == "no"]["percentage"]

        # handle esge cases where a population might have no data points
        if len(responder) == 0 or len(non_responder)==0:
            continue
        
        # use Mann-Whitney U test to determine if two groups come from the same undelying population
        # using two-sided to see whether cell frequency goes up or down
        stat, p_value = stats.mannwhitneyu(responder, non_responder, alternative="two-sided")

        rows.append({
            "population": population,
            "n_responder": len(responder),
            "n_non_responder": len(non_responder),
            "mean_responder": round(responder.mean(), 2),
            "mean_non_responder": round(non_responder.mean(), 2),
            "median_responder": round(responder.median(), 2),
            "median_non_responder": round(non_responder.median(), 2),
            "u_statistic": round(stat, 2), # how many times data points in one group beat data points in the other group when paired up head to head
            "p_value": round(p_value, 4), # if <=0.05 the chance of this shift happening by accident is less than 5%
            "significant": p_value < ALPHA,
        })

    return pd.DataFrame(rows)


def main():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"Could not find {DB_PATH}. Run `python load_data.py` first."
        )

    _configure_dir(OUTPUT_DIR)

    conn = sqlite3.connect(DB_PATH)
    try:
        df = load_melanoma(conn,MELANOMA_QUERY)
    finally:
        conn.close()

    if df.empty:
        raise ValueError("No melanoma/miraclib/PBMC samples found. Please check the database contents.")

    make_boxplot(df, BOXPLOT_PNG)
    print(f"Saved boxplot to {BOXPLOT_PNG}")

    stats_df = run_significance_tests(df)
    stats_df.to_csv(STATS_CSV, index=False)
    print(f"Saved stats table to {STATS_CSV}")
    print(stats_df.to_string(index=False))

    significant = stats_df[stats_df["significant"]]["population"].tolist()
    if significant:
        print(f"\nSignificant populations (p < {ALPHA}): {', '.join(significant)}")
    else:
        print(f"\nNo populations reached significance at p < {ALPHA}.")


if __name__ == "__main__":
    main()
