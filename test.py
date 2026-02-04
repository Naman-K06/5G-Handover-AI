import pandas as pd

df = pd.read_csv("data/raw/handover_ml_road.csv")
print(df["handover_label"].value_counts())
