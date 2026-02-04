import numpy as np
import matplotlib.pyplot as plt
import osmnx as ox
import pandas as pd
import networkx as nx
import os
import matplotlib.colors as mcolors
import random
import json
from src.physics_engine import get_rsrp_vector

# -------------------
# 1. CONFIGURATION
# -------------------
UE_SPEED_KMH = 60           
TIME_STEP = 0.5             
HYSTERESIS_DB = 3.0         
TIME_TO_TRIGGER = 2.0       
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

# Function to get next route number
def get_next_route_number():
    """Find the next available route number"""
    route_files = [f for f in os.listdir(ROUTE_DATA_DIR) if f.startswith("route_") and f.endswith(".json")]
    if not route_files:
        return 1
    route_numbers = [int(f.replace("route_", "").replace(".json", "")) for f in route_files]
    return max(route_numbers) + 1

ROUTE_NUM = get_next_route_number()
ROUTE_FOLDER = os.path.join(OUTPUT_DIR, f"route_{ROUTE_NUM}")
os.makedirs(ROUTE_FOLDER, exist_ok=True)

ROUTE_FILE = os.path.join(ROUTE_DATA_DIR, f"route_{ROUTE_NUM}.json")
LOG_FILE = os.path.join(ROUTE_FOLDER, "baseline_logs.csv")
PLOT_FILE = os.path.join(ROUTE_FOLDER, "baseline_result.png")

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

def draw_hex_boundary(ax, center_x, center_y, radius):
    angles = np.linspace(np.pi/6, 2*np.pi + np.pi/6, 7)
    ax.plot(center_x + radius*np.cos(angles), 
            center_y + radius*np.sin(angles), 
            linewidth=1, color='#444', linestyle='--', zorder=1)

# -------------------
# 3. SETUP
# -------------------
print("Loading Environment...")
if not os.path.exists(GRAPH_FILE):
    print("Error: Run Step 1 first.")
    exit()

G = ox.load_graphml(GRAPH_FILE)
bs_coords = pd.read_csv(HEX_FILE).values

gdf_nodes, gdf_edges = ox.graph_to_gdfs(G)
minx, miny, maxx, maxy = gdf_edges.total_bounds
real_w = maxx - minx
real_h = maxy - miny
scale_factor = min(AREA_W / real_w, AREA_H / real_h)
offset_x = (AREA_W - (real_w * scale_factor)) / 2
offset_y = (AREA_H - (real_h * scale_factor)) / 2

# -------------------
# 4. INTELLIGENT ROUTE GENERATION
# -------------------
print("Calculating Optimal Route within Grid...")
valid_nodes = []
for n, data in G.nodes(data=True):
    cx, cy = transform_to_canvas(data['x'], data['y'], minx, miny, scale_factor, offset_x, offset_y)
    if 200 < cx < AREA_W - 200 and 200 < cy < AREA_H - 200:
        valid_nodes.append(n)

start_node = random.choice(valid_nodes)
end_node = random.choice(valid_nodes)
attempts = 0
while attempts < 100:
    s_data = G.nodes[start_node]
    e_data = G.nodes[end_node]
    sx, sy = transform_to_canvas(s_data['x'], s_data['y'], minx, miny, scale_factor, offset_x, offset_y)
    ex, ey = transform_to_canvas(e_data['x'], e_data['y'], minx, miny, scale_factor, offset_x, offset_y)
    dist = np.sqrt((sx-ex)**2 + (sy-ey)**2)
    if dist > 3000: 
        break
    end_node = random.choice(valid_nodes)
    attempts += 1

route = nx.shortest_path(G, start_node, end_node, weight='length')
route_points, cum_dist = get_path_points_and_length(G, route)
total_length = cum_dist[-1]
speed_ms = UE_SPEED_KMH / 3.6

# Save route for reproducibility
route_data = {
    "route_number": ROUTE_NUM,
    "start_node": int(start_node),
    "end_node": int(end_node),
    "route_nodes": [int(n) for n in route],
    "route_points": route_points.tolist(),
    "cum_dist": cum_dist.tolist(),
    "total_length": float(total_length)
}
with open(ROUTE_FILE, 'w') as f:
    json.dump(route_data, f, indent=2)
print(f"Route saved to {ROUTE_FILE}")

# -------------------
# 5. SIMULATION LOOP (With Time-To-Trigger)
# -------------------
print(f"Simulating Baseline Trip: {total_length/1000:.2f} km...")

logs = []
current_dist = 0
prev_shadow = None

# Initial State
start_x, start_y = transform_to_canvas(route_points[0][0], route_points[0][1], minx, miny, scale_factor, offset_x, offset_y)
rsrps, prev_shadow = get_rsrp_vector(np.array([start_x, start_y]), bs_coords, None)
curr_serving_cell = np.argmax(rsrps)

# TTT Variables
candidate_cell = -1
time_triggered = 0  # How long the candidate has been better

while current_dist < total_length:
    current_dist += speed_ms * TIME_STEP
    
    # Move
    curr_x_real = np.interp(current_dist, cum_dist, route_points[:,0])
    curr_y_real = np.interp(current_dist, cum_dist, route_points[:,1])
    ux, uy = transform_to_canvas(curr_x_real, curr_y_real, minx, miny, scale_factor, offset_x, offset_y)
    
    # Physics
    rsrps, prev_shadow = get_rsrp_vector(np.array([ux, uy]), bs_coords, prev_shadow)
    
    # --- HANDOVER LOGIC WITH TTT ---
    best_candidate = np.argmax(rsrps)
    
    # Is the candidate better than serving + hysteresis?
    if best_candidate != curr_serving_cell and rsrps[best_candidate] > (rsrps[curr_serving_cell] + HYSTERESIS_DB):
        if best_candidate == candidate_cell:
            # It's the same candidate as last time, increase timer
            time_triggered += TIME_STEP
        else:
            # It's a new candidate, reset timer
            candidate_cell = best_candidate
            time_triggered = TIME_STEP
            
        # Has it been better for long enough?
        if time_triggered >= TIME_TO_TRIGGER:
            curr_serving_cell = best_candidate # EXECUTE HANDOVER
            candidate_cell = -1
            time_triggered = 0
    else:
        # Condition failed (signal dropped or serving got better), reset timer
        candidate_cell = -1
        time_triggered = 0

    # Log
    log_entry = {
        "x": ux, "y": uy, 
        "serving_cell": curr_serving_cell, 
        "rsrp_serving": rsrps[curr_serving_cell]
    }
    for i in range(len(bs_coords)):
        log_entry[f"rsrp_{i}"] = rsrps[i]
        
    logs.append(log_entry)

# -------------------
# 6. VISUALIZATION
# -------------------
df = pd.DataFrame(logs)
df.to_csv(LOG_FILE, index=False)
handovers = (df['serving_cell'].diff().fillna(0) != 0).sum()

print(f"Total Handovers: {handovers} (with TTT={TIME_TO_TRIGGER}s)")
print("Generating Plot...")

fig, ax = plt.subplots(figsize=(12, 10)) 
ax.set_facecolor('black')

rect = plt.Rectangle((0, 0), AREA_W, AREA_H, linewidth=2, edgecolor='white', facecolor='none', zorder=10)
ax.add_patch(rect)

for (bx, by) in bs_coords:
    draw_hex_boundary(ax, bx, by, HEX_RADIUS)

for geom in gdf_edges.geometry:
    if geom.geom_type == 'LineString':
        xs, ys = geom.xy
        xs_c = (np.array(xs) - minx) * scale_factor + offset_x
        ys_c = (np.array(ys) - miny) * scale_factor + offset_y
        ax.plot(xs_c, ys_c, color='#333', linewidth=0.5, alpha=0.5)
    elif geom.geom_type == 'MultiLineString':
        for part in geom.geoms:
            xs, ys = part.xy
            xs_c = (np.array(xs) - minx) * scale_factor + offset_x
            ys_c = (np.array(ys) - miny) * scale_factor + offset_y
            ax.plot(xs_c, ys_c, color='#333', linewidth=0.5, alpha=0.5)

ax.scatter(bs_coords[:,0], bs_coords[:,1], c='red', marker='h', s=80, zorder=3, label='Base Station')
for i, (bx, by) in enumerate(bs_coords):
    ax.text(bx, by, str(i), color='white', fontweight='bold', ha='center', va='center', fontsize=8, zorder=4)

cmap = plt.get_cmap('tab20', 20) 
sc = ax.scatter(df['x'], df['y'], c=df['serving_cell'], cmap=cmap, vmin=0, vmax=19, s=15, zorder=5)

cbar = plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.04, ticks=range(20))
cbar.set_label('Serving Cell ID', color='white', fontsize=12)
cbar.ax.yaxis.set_tick_params(color='white', labelcolor='white')
cbar.ax.set_yticklabels([str(i) for i in range(20)]) 

ax.set_title(f"Baseline Trip: {total_length/1000:.1f}km | {handovers} Handovers", color='white', fontsize=14)
ax.set_xlim(-100, AREA_W+100)
ax.set_ylim(-100, AREA_H+100)
ax.set_aspect('equal')
ax.axis('off')

plt.savefig(PLOT_FILE, dpi=300, bbox_inches='tight', facecolor='black')
print(f"Plot saved to: {PLOT_FILE}")
plt.show()