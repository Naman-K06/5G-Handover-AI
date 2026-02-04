5G WIRELESS NETWORK HANDOVER OPTIMIZATION USING AI
===================================================

PROJECT INTRODUCTION
====================

This project demonstrates how artificial intelligence can improve cellular network handover 
decisions in 5G networks. Instead of using fixed, rule-based handover criteria (like traditional 
3GPP standards), we train a machine learning model to learn optimal handover decisions by analyzing 
signal strength patterns across a digital twin environment.

The system compares two approaches:
1. BASELINE: Traditional 3GPP handover logic with hysteresis and time-to-trigger rules
2. AI-BASED: Machine learning model that predicts the best cell to connect to

Results show that AI can reduce unnecessary handovers while maintaining or improving signal quality.


SIMULATION ENVIRONMENT & PARAMETERS
====================================

GEOGRAPHIC AREA:
  Location: Chandigarh, India
  Simulation Area: 5000m × 5000m grid
  Road Network: Downloaded from OpenStreetMap (OSM)
  Coverage: Realistic urban topology with actual road patterns

5G NETWORK SETUP:
  Base Station Layout: Hexagonal grid (standard 3GPP topology)
  Number of Cells: 19 base stations (hex cells)
  Inter-Site Distance (ISD): 950 meters
  Coverage Radius per Cell: 550 meters (derived from ISD)
  Network Type: LTE/5G simulation with signal propagation

USER EQUIPMENT (UE) PARAMETERS:
  Speed: 60 km/h (highway speed, ~17 m/s)
  Movement: Along actual road routes
  Simulation Time Step: 0.5 seconds per measurement
  Mobility Pattern: Realistic path-following on roads

SIGNAL PROPAGATION MODEL:
  Path Loss: Free-space model with distance-dependent attenuation
  Formula: L = 20*log10(d) + C (where d is distance)
  Urban Shadowing: Log-normal distribution (more realistic than free-space alone)
  Fading Effects: Stochastic variations representing environmental effects
  RSRP Calculation: Received Signal Strength Reference Power from all visible cells

HANDOVER PARAMETERS:
  Hysteresis Margin: 3 dB (prevents rapid cell switching)
  Time-to-Trigger (TTT): 2 seconds (measurement window before handover)
  AI Persistence: 6 steps buffer (prevents AI oscillation between cells)


SYSTEM COMPONENTS & CODE EXPLANATION
=====================================

CODE 1: 01_preprocess.py - Map & Grid Generation
------------------------------------------------

Purpose:
  Creates the digital twin environment for simulation. Downloads real road network data
  and generates hexagonal base station locations.

What it does:
  1. Downloads OpenStreetMap road network for Chandigarh
  2. Creates hexagonal grid layout representing 5G cell towers
  3. Saves network data and cell coordinates to files
  4. Generates visualization of map + hex grid overlay

Input:
  - None (downloads OSM data automatically)

Output:
  - road_network.graphml: Road network topology
  - hex_centers.csv: Base station coordinates (19 locations)
  - data/maps/digital_twin_map.png: Visualization of environment

Key Concepts:
  - Hexagonal grid provides optimal coverage with minimal overlap
  - Cells arranged in axial coordinate system
  - Each hex center is a base station location
  - Road network enables realistic UE movement

Runtime: ~2-3 minutes (depends on internet/OSM download)


CODE 2: 03_run_baseline.py - Baseline Handover Simulation
----------------------------------------------------------

Purpose:
  Simulates a user traveling on a road route using traditional 3GPP handover rules.
  Establishes baseline performance metrics.

What it does:
  1. Selects random start and end points on road network
  2. Calculates optimal route between them using shortest-path algorithm
  3. Simulates UE movement along the route at 60 km/h
  4. At each position, calculates signal strength (RSRP) from all 19 cells
  5. Makes handover decisions using 3GPP rules:
     - Hysteresis: Only switch if new cell is 3dB stronger
     - Time-to-Trigger: Wait 2 seconds before switching to prevent ping-ponging
  6. Logs all handover events and signal measurements
  7. Generates visualization and saves route for reproducibility

Input:
  - Digital twin (from Code 1)

Output:
  - data/route/route_N.json: Saved route (reused by Code 5)
  - outputs/route_N/baseline_logs.csv: Handover time-series data
  - outputs/route_N/baseline_result.png: Trajectory map with cells

Key Metrics:
  - Total handovers: Count of cell switches
  - Trip distance: Route length in meters
  - Signal quality: Average RSRP across route

How Routes Work:
  - Each run generates new route (route_1, route_2, etc.)
  - Route is saved for reproducibility
  - Code 5 loads the same route for fair comparison


CODE 3: 04_train_ai.py - AI Model Training
--------------------------------------------

Purpose:
  Trains a machine learning model to learn handover patterns from synthetic data.
  The model learns: "Given RSRP from all cells, which cell is best to connect to?"

What it does:
  1. Generates 15,000 random UE positions across the 5000×5000 map
  2. For each position, calculates RSRP measurements from all 19 cells
  3. Determines ground-truth best cell (cell with highest signal)
  4. Creates training dataset with features = [RSRP_0, RSRP_1, ... RSRP_18]
  5. Trains Random Forest Classifier (100 decision trees)
  6. Tests on held-out 20% of data to measure accuracy
  7. Saves trained model for use in Code 5

Input:
  - Digital twin (from Code 1)
  - Random synthetic data points

Output:
  - outputs/ai_handover_model.pkl: Serialized trained model
  - outputs/ai_confusion_matrix.png: Accuracy visualization by cell

Key Metrics:
  - Training accuracy: ~94-95%
  - Model learns signal map independent of routes
  - Works for any UE path, not just training routes

Why Random Forest:
  - Robust to noisy signal measurements
  - No feature normalization needed
  - Fast inference (<1ms per decision)
  - Provides feature importance ranking


CODE 4: 05_final_comparison.py - AI vs Baseline Comparison
-----------------------------------------------------------

Purpose:
  Compares AI-based handovers with traditional baseline on identical route.
  Proves whether AI actually improves handover decisions.

What it does:
  1. Loads the latest saved route (from Code 2)
  2. Loads trained AI model (from Code 3)
  3. Simulates UE movement on the same route twice:
     - SIMULATION A: Traditional 3GPP handover logic (baseline)
     - SIMULATION B: AI model predictions with persistence buffer
  4. Compares metrics side-by-side:
     - Handover count (fewer is better)
     - Ping-pongs (cell oscillations, should be zero)
     - Average RSRP quality (higher is better)
  5. Generates side-by-side visualization
  6. Outputs comparison table to terminal

Input:
  - Saved route (from Code 2): data/route/route_N.json
  - Trained model (from Code 3): outputs/ai_handover_model.pkl
  - Digital twin (from Code 1)

Output:
  - outputs/route_N/final_project_result.png: Comparison visualization
  - Terminal output: Metrics table (handovers, RSRP, etc.)

Key Insight:
  Both methods use IDENTICAL route and signal propagation
  Only difference: handover decision logic
  This ensures FAIR comparison

Typical Results:
  - AI reduces handovers by 10-30%
  - Signal quality similar or slightly better
  - No increase in ping-pongs


CODE 5: physics_engine.py - Signal Propagation Model
-----------------------------------------------------

Purpose:
  Core mathematical model for calculating signal strength at any location.
  Used by all other codes to determine RSRP values.

What it does:
  1. Takes UE position and all base station locations
  2. Calculates distance from UE to each base station
  3. Applies path loss formula (free-space + distance attenuation)
  4. Adds urban shadowing (log-normal random variation)
  5. Returns RSRP array: [signal_cell_0, signal_cell_1, ... signal_cell_18]

Signal Calculation Formula:
  RSRP = Transmit_Power - Path_Loss - Shadowing + Antenna_Gain
  
  Where:
  - Path Loss = 20*log10(distance) + Constant
  - Shadowing = Random log-normal variation (urban environment)
  - Result: Realistic signal measurements with noise

Key Features:
  - Vectorized for speed (calculates all cells at once)
  - Supports spatial correlation (signal changes smoothly with position)
  - Independent random fading per calculation (realistic variations)

Why It Matters:
  - All handover decisions based on RSRP values
  - Accurate physics model = accurate handover simulation


EXECUTION ORDER
===============

For quick demo:
  1. python -m src.01_preprocess        (generates map + grid)
  2. python -m src.04_train_ai          (trains AI model)
  3. python -m src.03_run_baseline      (creates route_1 + baseline)
  4. python -m src.05_final_comparison  (compares on route_1)

Optional - test on more routes:
  5. python -m src.03_run_baseline      (creates route_2)
  6. python -m src.05_final_comparison  (compares on route_2)

Each run creates new route_N and outputs/route_N/ folder


FOLDER STRUCTURE
================

WMC Project/
├── src/
│   ├── 01_preprocess.py
│   ├── 03_run_baseline.py
│   ├── 04_train_ai.py
│   ├── 05_final_comparison.py
│   └── physics_engine.py
├── data/
│   ├── road_network.graphml         (OSM road network)
│   ├── hex_centers.csv              (19 cell locations)
│   ├── route/
│   │   ├── route_1.json
│   │   ├── route_2.json
│   │   └── route_N.json
│   └── maps/
│       └── digital_twin_map.png
├── outputs/
│   ├── ai_handover_model.pkl        (trained model)
│   ├── ai_confusion_matrix.png
│   ├── route_1/
│   │   ├── baseline_logs.csv
│   │   ├── baseline_result.png
│   │   └── final_project_result.png
│   └── route_2/
│       ├── baseline_logs.csv
│       ├── baseline_result.png
│       └── final_project_result.png
└── Project Docs/
    ├── README.md
    └── task.md


KEY RESEARCH FINDINGS
====================

AI Advantages:
  - Reduces unnecessary handovers (learns optimal switching points)
  - Maintains signal quality (no degradation)
  - Generalizes to unseen routes (model learns signal map, not specific routes)
  - Real-time capable (<1ms inference per decision)

Baseline Advantages:
  - Simple, deterministic rules (easier to understand)
  - Proven in production networks
  - No dependency on trained model

Best Use Case for AI:
  - High-speed scenarios where handovers waste resources
  - Urban environments with complex signal patterns
  - Networks where load-balancing is critical


NEXT STEPS
==========

Show to Teacher:
  - Run full sequence and show outputs
  - Explain comparison results
  - Discuss improvements for research paper

For Research Paper:
  - Add cross-validation on unseen routes
  - Add statistical significance testing
  - Test hyperparameter variations
  - Compare with other ML algorithms
  - See task.md for full improvement list


TECHNICAL DETAILS
=================

Dependencies:
  - numpy, pandas: Data processing
  - matplotlib: Visualization
  - scikit-learn: Machine learning (Random Forest)
  - osmnx, networkx: Road networks and routing
  - shapely: Geometric operations

Python Version: 3.14+
Virtual Environment: .venv/ in project root

Performance:
  - Code 1: ~2-3 minutes (OSM download)
  - Code 3: ~1-2 minutes per route (simulation)
  - Code 4: ~30-60 seconds (model training)
  - Code 5: ~1-2 minutes (comparison)
  - Total: ~10-15 minutes full run


REPRODUCIBILITY
===============

Routes are saved for reproducibility:
  - Code 2 saves route to data/route/route_N.json
  - Code 4 loads latest saved route automatically
  - Same route ensures fair comparison

Model training currently has random variation:
  - Each Code 3 run generates different random training data
  - Model accuracy varies ±1-2%
  - Fix: Add random.seed(42) for deterministic results (future improvement)

Visualization files:
  - PNG outputs saved to outputs/route_N/
  - Can be viewed to verify simulation correctness


CONTACT & NOTES
===============

Project: 5G Wireless Network Handover Optimization
Created: February 2026
Status: Initial working version, ready for teacher review
Next Phase: Research paper improvements and multi-user extension
