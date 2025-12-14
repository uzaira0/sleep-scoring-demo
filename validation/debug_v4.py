"""Debug v4 processing to see what timestamps look like."""

from datetime import UTC
from pathlib import Path

import gt3x_rs
import numpy as np

gt3x_file = Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1/P1-1078-A-T1 (2023-11-08).gt3x")

data = gt3x_rs.load_gt3x_ggir_compat(str(gt3x_file))


# Check the timestamps
timestamps = np.array(data.timestamps)

# These timestamps are offsets from start_time, stored in some unit
# Let me check what TIME_UNIT is


# Look at sample around DST transition
# From R: sample 27215850 is around the DST transition
idx = 27215850
if idx < len(timestamps):
    ts = timestamps[idx]

    # If it's in microseconds, convert to Unix timestamp
    if ts > 1e9:  # Looks like microseconds
        unix_ts = data.start_time + (ts / 1e6)
    else:
        unix_ts = data.start_time + ts

    from datetime import datetime, timezone

    dt = datetime.fromtimestamp(unix_ts, tz=UTC)
