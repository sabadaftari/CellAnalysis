.DEFAULT_GOAL := pipeline

setup: requirements.txt
	pip install -r requirements.txt

pipeline: setup
	python load_data.py
	python data_overview.py
	python statistical_analysis.py
	python data_subset_analysis.py

dashboard: 
	python -m streamlit run dashboard.py

.PHONY: setup pipeline dashboard clean