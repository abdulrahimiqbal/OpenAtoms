"""
Published ignition delay data for H2/O2/N2 mixtures.
Source: Slack & Grillo (1977), also consistent with GRI validation set.
Conditions: stoichiometric H2/O2 diluted in N2, P=1atm
These are the reference values the simulator must reproduce within tolerance.
"""

IGNITION_DELAY_DATA = [
    # (T_initial_K, ignition_delay_ms, reference)
    (1000.0, 0.18, "Slack & Grillo 1977"),
    (1100.0, 0.045, "Slack & Grillo 1977"),
    (1200.0, 0.012, "Slack & Grillo 1977"),
    (1300.0, 0.004, "Slack & Grillo 1977"),
]

# Acceptable deviation from published values
TOLERANCE_FRACTION = 0.25  # 25% - appropriate for mechanism/condition differences
