import numpy as np
import matplotlib.pyplot as plt
import osmnx as ox
import pandas as pd
import networkx as nx
import os
import pickle
import random
import warnings
import json

# 1. FIX THE WARNINGS
warnings.filterwarnings("ignore", category=UserWarning)

# Fix path for physics engine
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from physics_engine import get_rsrp_vector

# -------------------
# 1. CONFIGURATION
# -------------------
UE_SPEED_KMH = 60           
TIME_STEP = 0.5             
HYSTERESIS_DB = 3.0         
TIME_TO_TRIGGER = 2.0
# NEW: AI Stability Buffer (Wait 3 steps before believing the AI)
AI_PERSISTENCE = 6          

AREA_W, AREA_H = 5000, 5000 
ISD = 950
HEX_RADIUS = ISD / np.sqrt(3)

# PATHS
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")
ROUTE_DATA_DIR = os.path.join(DATA_DIR, "route")
GRAPH_FILE = os.path.join(DATA_DIR, "road_network.graphml")
HEX_FILE = os.path.join(DATA_DIR, "hex_centers.csv")
MODEL_FILE = os.path.join(OUTPUT_DIR, "ai_handover_model.pkl")

# Function to get latest route number
def get_latest_route_number():
    """Find the latest saved route number"""
    route_files = [f for f in os.listdir(ROUTE_DATA_DIR) if f.startswith("route_") and f.endswith(".json")]
    if not route_files:
        print("Error: No routes found. Run Step 2 (baseline) first!")
        exit()
    route_numbers = [int(f.replace("route_", "").replace(".json", "")) for f in route_files]
    return max(route_numbers)

ROUTE_NUM = get_latest_route_number()
ROUTE_FOLDER = os.path.join(OUTPUT_DIR, f"route_{ROUTE_NUM}")
os.makedirs(ROUTE_FOLDER, exist_ok=True)

ROUTE_FILE = os.path.join(ROUTE_DATA_DIR, f"route_{ROUTE_NUM}.json")
RESULT_PLOT = os.path.join(ROUTE_FOLDER, "final_project_result.png")

# -------------------
# 2. HELPER FUNCTIONS
# -------------------
def get_path_points_and_length(G, route):
    points = []
    start_node = G.nodes[route[0]]
    points.append((start_node['x'], start_node['y']))
    for u, v in zip(route[:-1], route[1:]):
        edge_data = G.get_edge_data(u, v)[0]
        if 'geometry' in edge_data:
            points.extend(list(edge_data['geometry'].coords))
        else:
            node_v = G.nodes[v]
            points.append((node_v['x'], node_v['y']))
    points = np.array(points)
    dists = np.sqrt(np.sum(np.diff(points, axis=0)**2, axis=1))
    cum_dist = np.insert(np.cumsum(dists), 0, 0)
    return points, cum_dist

def transform_to_canvas(x_real, y_real, minx, miny, scale, off_x, off_y):
    x_c = (x_real - minx) * scale + off_x
    y_c = (y_real - miny) * scale + off_y
    return x_c, y_c

# -------------------
# 3. SETUP ENVIRONMENT
# -------------------
print("Loading Map, Grid, and AI Model...")
if not os.path.exists(MODEL_FILE):
    print("Error: AI Model not found. Run Step 4.")
    exit()

with open(MODEL_FILE, 'rb') as f:
    ai_model = pickle.load(f)

G = ox.load_graphml(GRAPH_FILE)
bs_coords = pd.read_csv(HEX_FILE).values

gdf_nodes, gdf_edges = ox.graph_to_gdfs(G)
minx, miny, maxx, maxy = gdf_edges.total_bounds
scale_factor = min(AREA_W / (maxx - minx), AREA_H / (maxy - miny))
offset_x = (AREA_W - ((maxx - minx) * scale_factor)) / 2
offset_y = (AREA_H - ((maxy - miny) * scale_factor)) / 2

# -------------------
# 4. LOAD ROUTE (SAME AS BASELINE)
# -------------------
print(f"Loading Route {ROUTE_NUM} (same as baseline)...")
if not os.path.exists(ROUTE_FILE):
    print(f"Error: Route file not found at {ROUTE_FILE}")
    exit()

with open(ROUTE_FILE, 'r') as f:
    route_data = json.load(f)

route = route_data["route_nodes"]
route_points = np.array(route_data["route_points"])
cum_dist = np.array(route_data["cum_dist"])
total_length = route_data["total_length"]
speed_ms = UE_SPEED_KMH / 3.6

# -------------------
# 5. SIMULATION LOOP (A/B TEST)
# -------------------
print(f"Running Comparison Simulation ({total_length/1000:.2f} km)...")

logs = []
current_dist = 0
prev_shadow = None

# Initial State
start_x, start_y = transform_to_canvas(route_points[0][0], route_points[0][1], minx, miny, scale_factor, offset_x, offset_y)
rsrps, prev_shadow = get_rsrp_vector(np.array([start_x, start_y]), bs_coords, None)

# --- STATE TRACKING ---
# System A: Traditional
cell_trad = np.argmax(rsrps)
cand_trad = -1
ttt_timer = 0

# System B: AI
cell_ai = np.argmax(rsrps)
ai_cand = -1
ai_timer = 0  # Persistence Counter

while current_dist < total_length:
    current_dist += speed_ms * TIME_STEP
    
    # 1. Move & Physics
    curr_x_real = np.interp(current_dist, cum_dist, route_points[:,0])
    curr_y_real = np.interp(current_dist, cum_dist, route_points[:,1])
    ux, uy = transform_to_canvas(curr_x_real, curr_y_real, minx, miny, scale_factor, offset_x, offset_y)
    rsrps, prev_shadow = get_rsrp_vector(np.array([ux, uy]), bs_coords, prev_shadow)
    
    # 2. TRADITIONAL LOGIC (A3 + TTT)
    best_candidate = np.argmax(rsrps)
    if best_candidate != cell_trad and rsrps[best_candidate] > (rsrps[cell_trad] + HYSTERESIS_DB):
        if best_candidate == cand_trad:
            ttt_timer += TIME_STEP
        else:
            cand_trad = best_candidate
            ttt_timer = TIME_STEP
        
        if ttt_timer >= TIME_TO_TRIGGER:
            cell_trad = best_candidate # HANDOVER
            cand_trad = -1
            ttt_timer = 0
    else:
        cand_trad = -1
        ttt_timer = 0
        
    # 3. AI LOGIC (With Persistence)
    # The AI predicts the pure best cell
    ai_prediction = ai_model.predict([list(rsrps)])[0]
    
    if ai_prediction != cell_ai:
        # AI wants to switch
        if ai_prediction == ai_cand:
            ai_timer += 1 # Confidence increasing
        else:
            ai_cand = ai_prediction
            ai_timer = 1 # Start timer
        
        # Only switch if AI has insisted for 'AI_PERSISTENCE' frames
        if ai_timer >= AI_PERSISTENCE:
            cell_ai = ai_prediction
            ai_cand = -1
            ai_timer = 0
    else:
        ai_cand = -1
        ai_timer = 0

    # 4. Log
    logs.append({
        "cell_trad": cell_trad,
        "cell_ai": cell_ai,
        "rsrp_trad": rsrps[cell_trad],
        "rsrp_ai": rsrps[cell_ai]
    })

# -------------------
# 6. ANALYSIS & PLOTTING
# -------------------
df = pd.DataFrame(logs)

# Count Handovers
ho_trad = (df['cell_trad'].diff().fillna(0) != 0).sum()
ho_ai = (df['cell_ai'].diff().fillna(0) != 0).sum()

# Count Ping-Pongs
def count_pp(series):
    return sum((series.shift(1) != series) & (series.shift(2) == series))

pp_trad = count_pp(df['cell_trad'])
pp_ai = count_pp(df['cell_ai'])

# Avg Signal Quality
avg_rsrp_trad = df['rsrp_trad'].mean()
avg_rsrp_ai = df['rsrp_ai'].mean()

print("\n" + "="*40)
print("FINAL PROJECT RESULTS")
print("="*40)
print(f"METRIC            | TRADITIONAL | AI-BASED")
print("-" * 40)
print(f"Total Handovers   | {ho_trad:<11} | {ho_ai}")
print(f"Ping-Pongs        | {pp_trad:<11} | {pp_ai}")
print(f"Avg RSRP (dBm)    | {avg_rsrp_trad:<11.2f} | {avg_rsrp_ai:.2f}")
print("="*40)

# PLOTTING
labels = ['Traditional', 'AI Optimized']
ho_counts = [ho_trad, ho_ai]
pp_counts = [pp_trad, pp_ai]

x = np.arange(len(labels))
width = 0.35

fig, ax = plt.subplots(figsize=(10, 6))
rects1 = ax.bar(x - width/2, ho_counts, width, label='Total Handovers', color='#3498db')
rects2 = ax.bar(x + width/2, pp_counts, width, label='Ping-Pongs (Instability)', color='#e74c3c')

ax.set_ylabel('Count')
ax.set_title(f'Comparison: AI reduces Handovers vs Stability')
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.legend()
ax.grid(axis='y', linestyle='--', alpha=0.3)

def autolabel(rects):
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height}',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha='center', va='bottom')

autolabel(rects1)
autolabel(rects2)

plt.savefig(RESULT_PLOT, dpi=300)
print(f"Final Graph saved to: {RESULT_PLOT}")
plt.show()