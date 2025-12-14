"""Debug force_tz implementation."""

from datetime import UTC, datetime, timezone
from pathlib import Path

import gt3x_rs
import numpy as np

# Load the GT3X file
gt3x_file = Path("W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1/P1-1078-A-T1 (2023-11-08).gt3x")

data = gt3x_rs.load_gt3x_ggir_compat(str(gt3x_file))


# Convert start_time to datetime
start_dt = datetime.fromtimestamp(data.start_time, tz=UTC)

# The timestamps in GT3X are stored as offsets from start_time
# Let's look at the raw timestamp data around the DST transition
# DST ends on Nov 5, 2023 at 2:00 AM CDT (becomes 1:00 AM CST)

# The file starts on Oct 26, 2023 - so DST transition is about 10 days in
# At 30 Hz, that's about 10 * 24 * 3600 * 30 = 25,920,000 samples

# Let's find when the timestamps show an anomaly
timestamps = np.array(data.timestamps)

# Look for gaps in timestamps
diffs = np.diff(timestamps)
expected_diff = 1.0 / data.sample_rate

# Find unusual gaps
unusual = np.where(np.abs(diffs - expected_diff) > 0.001)[0]

if len(unusual) > 0:
    for i, idx in enumerate(unusual[:10]):
        ts_before = timestamps[idx]
        ts_after = timestamps[idx + 1]
        gap = ts_after - ts_before
        # Convert to datetime
        dt_before = datetime.fromtimestamp(data.start_time + ts_before, tz=UTC)
        dt_after = datetime.fromtimestamp(data.start_time + ts_after, tz=UTC)

# Now let's check what the actual Unix timestamps look like at the DST boundary
# DST ends on Nov 5, 2023 at 2:00 AM local (becomes 1:00 AM)
# In Chicago, Nov 5 2023 1:59:59 CDT = Nov 5 2023 06:59:59 UTC
# Then it becomes Nov 5 2023 1:00:00 CST = Nov 5 2023 07:00:00 UTC

# The problem is: GT3X stores local time as if it were UTC
# So the file says "06:59:59 UTC" but it's actually "01:59:59 CDT" (local)
# And then "07:00:00 UTC" which is actually "01:00:00 CST" (local)

# When we force_tz, we need to:
# 1. Interpret the "UTC" timestamp as local time (just the wall clock)
# 2. Then find the correct Unix timestamp for that wall clock time in the target TZ

# Let's look at sample index around 27,215,850 (from previous investigation)
target_sample = 27_215_850
window = 100

if target_sample + window < len(timestamps):
    for i in range(target_sample - 5, min(target_sample + window, len(timestamps))):
        ts = timestamps[i]
        unix_ts = data.start_time + ts
        dt = datetime.fromtimestamp(unix_ts, tz=UTC)
        if i > target_sample - 5:
            diff = timestamps[i] - timestamps[i - 1]
            if abs(diff - expected_diff) > 0.001 or i < target_sample + 10:
                pass
else:
    pass

# What's the issue?
# The GT3X timestamps are ALREADY in "fake UTC" - they store local time with UTC label
# But we're computing them as offsets from start_time

# Let me check the actual timestamp values

# The issue might be that timestamps are stored differently
# Let me check if they're absolute or relative

# Check if timestamps look like relative (small) or absolute (large)
if timestamps[0] > 1e9:
    pass
else:
    pass
