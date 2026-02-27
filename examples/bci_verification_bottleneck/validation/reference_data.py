"""
Published results from Iqbal (2026), "The Verification Bottleneck".
These are the reference values our pipeline must reproduce within tolerance.
"""

# d' crossover point: Bridge breaks even with uniform at approximately d' = 1.7
CROSSOVER_D_PRIME = 1.7
CROSSOVER_TOLERANCE = 0.2  # acceptable range: 1.5 to 1.9

# GPT-2 measured character entropy and speedup
GPT2_CHARACTER_ENTROPY_BITS = 2.2
GPT2_SPEEDUP_FACTOR = 2.3

# GPT-4 class projected entropy and speedup
GPT4_PROJECTED_ENTROPY_BITS = 1.5
GPT4_PROJECTED_SPEEDUP = 3.4

# Uniform prior baseline entropy (36 chars: A-Z + digits)
UNIFORM_ENTROPY_BITS = 5.17

# P300 d' values by device class
D_PRIME_CONSUMER_EEG = 0.4  # e.g. MUSE headband
D_PRIME_MIDRANGE_EEG = 0.8  # e.g. OpenBCI
D_PRIME_RESEARCH_GRADE = 2.1  # lab-grade active gel

# ITR improvement at consumer EEG d' = 0.4
BRIDGE_ITR_IMPROVEMENT_AT_LOW_D_PRIME = 2.0  # minimum 2x, paper shows ~3x

# N400 passive reading result
N400_PASSIVE_D_PRIME = 0.00
N400_ACTIVE_D_PRIME = 0.24
BCI_PRACTICAL_THRESHOLD_D_PRIME = 0.5

# Tolerance for all reproduced metrics
REPRODUCTION_TOLERANCE_FRACTION = 0.15  # 15%
