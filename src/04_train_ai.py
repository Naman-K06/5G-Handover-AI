import numpy as np
import pandas as pd
import os
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

# Fix path import so we can see physics_engine
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from physics_engine import get_rsrp_vector

# -------------------
# 1. CONFIGURATION
# -------------------
NUM_SAMPLES = 15000     # 15,000 Training points
TEST_SPLIT = 0.2        # 20% reserved for testing
AREA_W, AREA_H = 5000, 5000

# PATHS
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")
HEX_FILE = os.path.join(DATA_DIR, "hex_centers.csv")
MODEL_FILE = os.path.join(OUTPUT_DIR, "ai_handover_model.pkl")
CM_PLOT = os.path.join(OUTPUT_DIR, "ai_confusion_matrix.png")

# -------------------
# 2. DATA GENERATION
# -------------------
print(f"Loading Hex Grid from {HEX_FILE}...")
if not os.path.exists(HEX_FILE):
    print("Error: Run Step 1 first!")
    exit()

bs_coords = pd.read_csv(HEX_FILE).values
num_cells = len(bs_coords)

print(f"Generating {NUM_SAMPLES} synthetic training points...")
data = []

# We create random users all over the map to teach the AI the "Signal Map"
for _ in range(NUM_SAMPLES):
    # Random Location
    ux = np.random.uniform(0, AREA_W)
    uy = np.random.uniform(0, AREA_H)
    
    # Get Physics-based Signals (Fresh noise every time)
    # We pass None for prev_shadowing because these are independent snapshots
    rsrps, _ = get_rsrp_vector(np.array([ux, uy]), bs_coords, None)
    
    # LABEL: What is the ACTUAL best cell? (Ground Truth)
    # The AI tries to predict this index based on the noisy signals
    best_cell = np.argmax(rsrps)
    
    # Feature Vector: [rsrp_0, rsrp_1, ... rsrp_18] + [Label]
    row = list(rsrps) + [best_cell]
    data.append(row)

# Convert to DataFrame
cols = [f"rsrp_{i}" for i in range(num_cells)] + ["label"]
df = pd.DataFrame(data, columns=cols)

# -------------------
# 3. AI TRAINING
# -------------------
print("Training Random Forest Classifier...")

X = df.drop(columns=['label'])
y = df['label']

# Split Data (80% Train, 20% Test)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SPLIT, random_state=42)

# Initialize Model (100 Decision Trees)
# This algorithm is excellent at finding patterns in noisy sensor data
clf = RandomForestClassifier(n_estimators=100, random_state=42)
clf.fit(X_train, y_train)

# Evaluate on the Test Set
preds = clf.predict(X_test)
acc = accuracy_score(y_test, preds)

print("-" * 30)
print(f"AI MODEL RESULTS")
print("-" * 30)
print(f"Accuracy: {acc*100:.2f}%")
print("Interpretation: The AI can correctly identify the best tower")
print(f"{acc*100:.1f}% of the time, even with heavy signal noise.")

# -------------------
# 4. SAVE & VISUALIZE
# -------------------
# Save Model
with open(MODEL_FILE, 'wb') as f:
    pickle.dump(clf, f)
print(f"Model saved to {MODEL_FILE}")

# Plot Confusion Matrix
cm = confusion_matrix(y_test, preds)
plt.figure(figsize=(10, 8))
sns.heatmap(cm, annot=False, cmap='Blues', fmt='d')
plt.title(f'AI Model Confusion Matrix (Acc: {acc*100:.1f}%)')
plt.xlabel('Predicted Cell ID')
plt.ylabel('Actual Best Cell ID')
plt.savefig(CM_PLOT)
print(f"Confusion Matrix saved to {CM_PLOT}")