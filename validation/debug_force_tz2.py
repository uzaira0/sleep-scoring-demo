"""Debug force_tz - trace exact GGIR behavior."""

from datetime import datetime

import pytz

# Key insight: GT3X stores local time AS IF it were UTC
# GGIR reads it as UTC, then force_tz to the device's timezone

# Example from P1-1078-A-T1:
# start_time = 1698238800 (Oct 25, 2023 13:00:00 UTC)
# But the device was in Chicago, so this is actually Oct 25, 2023 08:00:00 CDT

# The key question: what does force_tz do?

chicago = pytz.timezone("America/Chicago")
utc = pytz.UTC

# The GT3X file has timestamps stored as "seconds since start_time"
# At the DST transition point (sample ~27,215,850), the timestamp offset is ~907200 seconds
# 907200 / 3600 = 252 hours = 10.5 days after start

# So the timestamp at sample 27,215,850 is:
# 1698238800 + 907200 = 1699146000 = Nov 5, 2023 01:00:00 UTC

# But wait - this is where the PROBLEM is!
# The GT3X device doesn't actually store Unix timestamps
# It stores LOCAL TIME with a UTC label

# Let's trace what GGIR does:


# Step 1: read.gt3x reads the timestamp as POSIXct with GMT timezone
# This creates a datetime that LOOKS like UTC but is actually local time
fake_utc_ts = 1699146000  # Nov 5, 2023 01:00:00 "UTC" (but actually local)
fake_utc_dt = datetime.utcfromtimestamp(fake_utc_ts)

# Step 2: GGIR uses lubridate::force_tz(time, "America/Chicago")
# This KEEPS the wall clock time but CHANGES the timezone
# So "Nov 5 01:00:00 GMT" becomes "Nov 5 01:00:00 Chicago"

# The wall clock is: 2023-11-05 01:00:00
wall_clock = datetime(2023, 11, 5, 1, 0, 0)

# Now interpret this in Chicago timezone
# On Nov 5, 2023, 1:00 AM is AMBIGUOUS in Chicago:
# - 1:00 AM CDT (before DST ends) = 6:00 AM UTC
# - 1:00 AM CST (after DST ends) = 7:00 AM UTC

# Before DST ends (1:59:59 CDT):
before_dst = chicago.localize(datetime(2023, 11, 5, 1, 59, 59), is_dst=True)

# After DST ends (1:00:00 CST):
after_dst = chicago.localize(datetime(2023, 11, 5, 1, 0, 0), is_dst=False)

# The gap!
gap = after_dst.timestamp() - before_dst.timestamp()


# The problem is:
# - GT3X stores continuous local time (wall clock advances normally)
# - At DST end, the wall clock goes: 1:59:59 CDT -> 1:00:00 CST
# - The device keeps recording, so its "seconds since start" increases by 1/30
# - But when we force_tz, we go from interpreting 1:59:59 as CDT to 1:00:00 as CST
# - This creates a 1-hour GAP in Unix timestamps


# Let's check what the start_time really means
start_time = 1698238800

# If this is TRUE UTC:
start_utc = datetime.utcfromtimestamp(start_time)

# Convert to Chicago time
start_chicago = utc.localize(datetime.utcfromtimestamp(start_time)).astimezone(chicago)

# So start_time = Oct 25, 2023 13:00:00 UTC = Oct 25, 2023 08:00:00 CDT
# This is MORNING in Chicago - makes sense for a study device

# Now, the key question: does the device store TRUE Unix timestamps?
# Or does it store "local time seconds"?

# If TRUE Unix timestamps:
# - Offset 907200 means 907200 seconds have passed in real time
# - This is about 10.5 days
# - start + 907200 = Nov 5, 2023 01:00:00 UTC = Oct 4, 2023 19:00:00 Chicago (wait, that's wrong)

# Actually let me recalculate:
ts_at_dst = start_time + 907200
dt_at_dst_utc = datetime.utcfromtimestamp(ts_at_dst)
dt_at_dst_chicago = utc.localize(datetime.utcfromtimestamp(ts_at_dst)).astimezone(chicago)

# Hmm, Nov 5 01:00:00 UTC = Nov 4 19:00:00 or 20:00:00 Chicago
# That's not the DST transition time!

# The DST transition on Nov 5, 2023 happens at 2:00 AM CDT local = 7:00 AM UTC
dst_transition_utc = datetime(2023, 11, 5, 7, 0, 0)  # 2:00 AM CDT = 7:00 AM UTC
dst_transition_unix = dst_transition_utc.replace(tzinfo=utc).timestamp()

offset_at_dst = dst_transition_unix - start_time

# At 30 Hz, this is:
sample_at_dst = int(offset_at_dst * 30)

# So the DST transition should be around sample 28,576,800, not 27,215,850
# Let's check what time sample 27,215,850 actually is


offset_27m = 907200  # from the debug output
ts_27m = start_time + offset_27m
dt_27m_utc = datetime.utcfromtimestamp(ts_27m)
dt_27m_chicago = utc.localize(datetime.utcfromtimestamp(ts_27m)).astimezone(chicago)

# OH! Nov 5 01:00:00 UTC = Nov 4 20:00:00 CDT (before DST) or 19:00:00 CST (after DST)
# This is NOT the DST transition time at all!

# The R investigation showed the gap at sample 27,215,850
# Let me re-read what that R script found...
