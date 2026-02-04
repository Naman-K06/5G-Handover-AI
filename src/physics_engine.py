import numpy as np
# -------------------
# 1. RADIO CONFIGURATION
# -------------------
FC_GHZ = 3.5            # Frequency: 3.5 GHz (Standard 5G Band)
TX_POWER_DBM = 46       # Base Station Power: 46 dBm (40 Watts)
PATH_LOSS_EXP = 3.2     # Path Loss Exponent (Urban Environment)

# Free Space Reference Loss at 1 meter distance
# Formula: 32.4 + 20*log10(f_GHz)
PL0 = 32.4 + 20 * np.log10(FC_GHZ)

# -------------------
# 2. SHADOWING CONFIG (Gudmundson Model)
# -------------------
SHADOW_SIGMA = 6.0      # Standard Deviation of the noise (dB)
CORRELATION = 0.8       # Memory Factor (0.0 = Random, 1.0 = Constant)

# -------------------
# 3. PHYSICS FUNCTION
# -------------------
def get_rsrp_vector(user_pos, bs_coords, prev_shadowing=None):
    """
    Calculates the Signal Strength (RSRP) for ALL 19 cells at once.
    
    Parameters:
    - user_pos: [x, y] coordinates of the User
    - bs_coords: [[x1,y1], [x2,y2]...] coordinates of all Base Stations
    - prev_shadowing: The shadowing vector from the PREVIOUS time step (numpy array)
    
    Returns:
    - rsrp: Array of 19 signal strengths (dBm)
    - current_shadowing: The new shadowing state (to be passed to next step)
    """
    
    # A. Calculate Distance to all Cells
    # We use np.maximum(..., 1.0) to avoid dividing by zero if we hit a tower exactly
    dx = bs_coords[:, 0] - user_pos[0]
    dy = bs_coords[:, 1] - user_pos[1]
    distance = np.maximum(np.sqrt(dx**2 + dy**2), 1.0)
    
    # B. Log-Distance Path Loss Model
    # Loss increases as distance increases
    path_loss = PL0 + 10 * PATH_LOSS_EXP * np.log10(distance)
    
    # C. Correlated Shadowing Logic (The "Advanced" Part)
    # Generate fresh random noise
    fresh_noise = np.random.normal(0, SHADOW_SIGMA, size=len(distance))
    
    if prev_shadowing is None:
        # First step of simulation: just use random noise
        current_shadowing = fresh_noise
    else:
        # Subsequent steps: Mix old noise with new noise
        # S_new = (Correlation * S_old) + (sqrt(1 - Corr^2) * N_fresh)
        term1 = CORRELATION * prev_shadowing
        term2 = np.sqrt(1 - CORRELATION**2) * fresh_noise
        current_shadowing = term1 + term2
        
    # D. Final RSRP Calculation
    # RSRP = Transmit Power - Path Loss + Shadowing
    rsrp = TX_POWER_DBM - path_loss + current_shadowing
    
    return rsrp, current_shadowing