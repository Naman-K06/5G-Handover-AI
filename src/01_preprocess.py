import numpy as np
import osmnx as ox
import pandas as pd
import os
import matplotlib.pyplot as plt

# -------------------
# 1. CONFIGURATION
# -------------------
PLACE = "Chandigarh, India"
AREA_W = 5000
AREA_H = 5000
ISD = 950 # Inter-Site Distance
HEX_RADIUS = ISD / np.sqrt(3)

# Define Folders
BASE_DIR = os.getcwd() # Gets current folder
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

# Create folders if they don't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
MAPS_DIR = os.path.join(DATA_DIR, "maps")
os.makedirs(MAPS_DIR, exist_ok=True)

# File Paths
GRAPH_FILE = os.path.join(DATA_DIR, "road_network.graphml")
HEX_FILE = os.path.join(DATA_DIR, "hex_centers.csv")
MAP_IMAGE = os.path.join(MAPS_DIR, "digital_twin_map.png")

# -------------------
# 2. MAP GENERATION
# -------------------
print(f"Downloading Map for {PLACE}...")
try:
    G = ox.graph_from_place(PLACE, network_type="drive")
    G = ox.project_graph(G)
    ox.save_graphml(G, filepath=GRAPH_FILE)
    gdf_nodes, gdf_edges = ox.graph_to_gdfs(G)
except Exception as e:
    print(f"Error downloading map: {e}")
    exit()

# -------------------
# 3. HEX GRID GENERATION
# -------------------
print("Generating 5G Hex Grid...")
def axial_to_xy(q, r, isd):
    x = isd * (q + r/2)
    y = isd * 3/2 * r / np.sqrt(3)
    return x, y

coords = []
for q in range(-2, 3):
    for r in range(-2, 3):
        if abs(-q - r) <= 2:
            coords.append(axial_to_xy(q, r, ISD))

# Center grid on 5000x5000 canvas
cells = np.array(coords)
cells[:,0] += AREA_W / 2 
cells[:,1] += AREA_H / 2

# Save Grid Data
pd.DataFrame(cells, columns=['x', 'y']).to_csv(HEX_FILE, index=False)

# -------------------
# 4. PLOTTING & SAVING
# -------------------
print("Creating Visualization...")

# Helper to draw hexes
def draw_hex(ax, x, y, radius):
    angles = np.linspace(np.pi/6, 2*np.pi + np.pi/6, 7)
    ax.plot(x + radius*np.cos(angles), 
            y + radius*np.sin(angles), 
            linewidth=2, color='red', alpha=0.8, zorder=5)

fig, ax = plt.subplots(figsize=(10, 10))
ax.set_facecolor('#1a1a1a') # Dark mode

# A. Draw Roads (Scaled to fit)
minx, miny, maxx, maxy = gdf_edges.total_bounds
real_w = maxx - minx
real_h = maxy - miny
scale_factor = min(AREA_W / real_w, AREA_H / real_h)
offset_x = (AREA_W - (real_w * scale_factor)) / 2
offset_y = (AREA_H - (real_h * scale_factor)) / 2

for geom in gdf_edges.geometry:
    xs, ys = geom.xy
    xs_plot = (np.array(xs) - minx) * scale_factor + offset_x
    ys_plot = (np.array(ys) - miny) * scale_factor + offset_y
    ax.plot(xs_plot, ys_plot, color='#555', linewidth=0.5, alpha=0.6)

# B. Draw Hexes
for i, (x, y) in enumerate(cells):
    draw_hex(ax, x, y, HEX_RADIUS)
    # Label the cell ID
    ax.text(x, y, str(i), color='white', weight='bold', ha='center', va='center', zorder=6)

# C. Formatting
ax.set_xlim(0, AREA_W)
ax.set_ylim(0, AREA_H)
ax.set_aspect('equal')
ax.axis('off') # Remove borders
plt.title(f"Digital Twin: {PLACE} + 5G Grid", color='white', fontsize=14)

# D. Save
print(f"Saving image to {MAP_IMAGE}...")
plt.savefig(MAP_IMAGE, dpi=300, bbox_inches='tight', facecolor='#1a1a1a')
plt.show()

print("Step 1 Complete: Map, Data, and Image saved.")