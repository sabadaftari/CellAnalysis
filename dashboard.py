import os
import sqlite3

import pandas as pd
import streamlit as st

import data_overview
import statistical_analysis
import data_subset_analysis

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT_DIR, "cell-count.db")
OUTPUT_DIR = os.path.join(ROOT_DIR, "outputs")

st.set_page_config(page_title="Loblaw Bio | Cell Count Analysis", layout="wide")
st.title("Loblaw Bio — miraclib cell analysis")
st.caption("Interactive dashboard for Bob Loblaw's clinical trial cell count data.")

tab_overview, tab_freq, tab_stats, tab_subset = st.tabs(["Database overview", 
                                                         "Part 2: frequencies", 
                                                         "Part 3: responders vs non-responders", 
                                                         "Part 4: baseline subset"])

def get_connection() -> sqlite3.Connection:
    
    if not os.path.exists(DB_PATH):
        st.error("cell-count.db not found. Run `python load_data.py` first (or `make pipeline`).")
        st.stop()
    return sqlite3.connect(DB_PATH)

""" Tab 0: quick database overview """

with tab_overview:
    conn = get_connection()
    n_projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    n_subjects = conn.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
    n_samples = conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
    n_counts = conn.execute("SELECT COUNT(*) FROM cell_counts").fetchone()[0]
    conn.close()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Projects", n_projects)
    col2.metric("Subjects", n_subjects)
    col3.metric("Samples", n_samples)
    col4.metric("Cell count records", n_counts)

    st.markdown("Database file: `cell-counts.db`")

"""Tab 1: Part 2 - relative frequency table"""

with tab_freq:
    st.subheader("Relative frequency of each cell population per sample")

    csv_path = os.path.join(OUTPUT_DIR, "part2_frequencies.csv")
    if not os.path.exists(csv_path):
        conn = get_connection()
        df_freq = data_overview.compute_frequencies(conn)
        conn.close()
    else:
        df_freq = pd.read_csv(csv_path)

    samples = sorted(df_freq["sample"].unique())
    selected = st.multiselect("Filter by sample (leave empty to show all)", samples)
    shown = df_freq[df_freq["sample"].isin(selected)] if selected else df_freq

    st.dataframe(shown, use_container_width=True, height=400)
    st.download_button("Download full table as CSV",
                        data=df_freq.to_csv(index=False),
                        file_name="part2_frequencies.csv")


""" Tab 2: Part 3 - responders vs non-responders, interactive map """

with tab_stats:
    st.subheader(" Melanoma + Miraclib + PBMC: Responders vs Non-Responders")

    stats_path = os.path.join(OUTPUT_DIR, "part3_stats.csv")
    
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

    # fetch raw data safely for our interactive visualizations
    conn = get_connection()
    try:
        # load the clean filtered dataset
        raw_stats_df = statistical_analysis.load_melanoma(conn,MELANOMA_QUERY)
    except Exception as e:
        st.error(f"Failed to fetch statistical baseline data: {e}")
        raw_stats_df = pd.DataFrame()
    finally:
        conn.close()

    if not raw_stats_df.empty:
        # add an interactive Cell Population Dropdown selector
        available_populations = sorted(raw_stats_df["population"].unique())
        
        st.markdown("### Interactive Visualization Controls")
        selected_population = st.selectbox(
            "Select an immune cell population to plot:", 
            available_populations
        )

        # filter dataset to just the user's chosen subpopulation
        filtered_plot_df = raw_stats_df[raw_stats_df["population"] == selected_population]

        # generate an interactive boxplot with Plotly Express
        import plotly.express as px

        fig = px.box(
            filtered_plot_df, 
            x="response", 
            y="count", 
            color="response",
            points="all",  # overlays raw data points on top of boxes to see sample size
            labels={"response": "Therapeutic Response Status", "count": "Absolute Cell Count"},
            title=f"Distribution of {selected_population} Counts by Response Group",
            color_discrete_map={"yes": "#2ecc71", "no": "#e74c3c"}, # green for responders, red for non
            template="plotly_dark" # fits clean modern dark themes natively
        )
        
        # smooth styling adjustments
        fig.update_layout(showlegend=False, boxmode="overlay")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Unable to render boxplots. Verify database content parameters.")

    # render the companion Significance Matrix Table below the interactive plot
    st.markdown("### Mann-Whitney U Test Significance Summary")
    st.caption("Significance verification calculations (alpha threshold: $p < 0.05$)")
    
    if os.path.exists(stats_path):
        stats_df = pd.read_csv(stats_path)
        st.dataframe(stats_df, use_container_width=True)

        significant = stats_df[stats_df["significant"]]["population"].tolist()
        if significant:
            st.success(f" Statistically significant variance confirmed in: **{', '.join(significant)}**")
        else:
            st.info("No tracked populations cleared significance barriers ($p < 0.05$).")
    else:
        st.warning("Statistical breakdown file `part3_stats.csv` missing. Run `make pipeline` to compile.")


""" Tab 3: Part 4 - baseline subset breakdowns""" 

with tab_subset:
    st.subheader("Day0, a subset of melanoma + miraclib + PBMC ")

    by_project_path = os.path.join(OUTPUT_DIR, "part4_by_project.csv")
    by_response_path = os.path.join(OUTPUT_DIR, "part4_by_response.csv")
    by_sex_path = os.path.join(OUTPUT_DIR, "part4_by_sex.csv")

    if all(os.path.exists(p) for p in [by_project_path, by_response_path, by_sex_path]):
        by_project = pd.read_csv(by_project_path)
        by_response = pd.read_csv(by_response_path)
        by_sex = pd.read_csv(by_sex_path)
    else:
        conn = get_connection()
        subset_df = data_subset_analysis.load_baseline_subset(conn)
        conn.close()
        by_project = subset_df.groupby("project")["sample"].count().reset_index().rename(columns={"sample": "n_samples"})
        by_response = subset_df.drop_duplicates("subject").groupby("response")["subject"].count().reset_index().rename(columns={"subject": "n_subjects"})
        by_sex = subset_df.drop_duplicates("subject").groupby("sex")["subject"].count().reset_index().rename(columns={"subject": "n_subjects"})

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Samples per project**")
        st.dataframe(by_project, use_container_width=True)
        st.bar_chart(by_project.set_index("project"))
    with col2:
        st.markdown("**Subjects by response**")
        st.dataframe(by_response, use_container_width=True)
        st.bar_chart(by_response.set_index("response"))
    with col3:
        st.markdown("**Subjects by sex**")
        st.dataframe(by_sex, use_container_width=True)
        st.bar_chart(by_sex.set_index("sex"))
