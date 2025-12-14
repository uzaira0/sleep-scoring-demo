"""Test chrono-tz ambiguous handling via Rust."""

import gt3x_rs

# Quick test - just call the force_tz function with a few timestamps
# around the DST transition

# These are the Unix timestamps from the R output (BEFORE force_tz):
# Index 27215850: 2023-11-05 00:59:59.966 GMT (Unix: 1699145999.967)
# Index 27215851: 2023-11-05 01:00:00.000 GMT (Unix: 1699146000.000)

# Actually, let me trace what my force_tz_timestamps does
# The input timestamps are "local time stored as UTC"

# From our Rust code:
# - We load start_time = 1698238800 (Oct 25, 2023 13:00:00 UTC)
# - We compute timestamp = start_time + offset
# - This gives Unix timestamps like 1699146000

# But wait - the R output shows the SAME Unix timestamps before force_tz!
# So read.gt3x is creating timestamps using the same method we are.

# The difference is what force_tz does:
# R's force_tz("2023-11-05 01:00:00 GMT", "America/Chicago") -> CST
# Our force_tz should do the same

# Let me check what chrono-tz does for 2023-11-05 01:00:00 in Chicago
# This is in the ambiguous hour

# Actually, I realize the issue: 2023-11-05 01:00:00 GMT is NOT in the ambiguous hour!
# The ambiguous hour is 01:00-01:59 LOCAL TIME in Chicago on Nov 5.
# 01:00:00 GMT = 19:00:00 CDT = 20:00:00 CST (on Nov 4!)

# So there's no ambiguity for 01:00:00 GMT interpreted in Chicago.
# The issue is that read.gt3x stores the data as if GMT, but it's actually local.

# Let me trace this more carefully:
# 1. Device records at 01:00:00 LOCAL (Chicago) on Nov 5
# 2. This gets stored in GT3X as some internal representation
# 3. read.gt3x interprets it as 01:00:00 GMT (adding the wrong timezone)
# 4. force_tz("01:00:00 GMT", "America/Chicago") keeps "01:00:00" but changes TZ to Chicago
# 5. 01:00:00 Chicago on Nov 5 IS ambiguous (could be CDT or CST)
# 6. lubridate picks CST because... some heuristic

# So our Rust force_tz should:
# 1. Take Unix timestamp that represents "local time as if UTC"
# 2. Extract the wall clock (01:00:00)
# 3. Interpret that wall clock in Chicago
# 4. For ambiguous times, pick based on sequence

# The key issue is: how does lubridate pick CST vs CDT?
# It must be looking at the progression of wall clock times.
# 00:59:59 -> 01:00:00 = wall clock advancing past midnight
# After midnight on Nov 5, the ambiguous hour should be CST (standard time)

# Actually, looking at the DST rules:
# DST ends at 2:00 AM CDT, which becomes 1:00 AM CST
# So times BEFORE 2:00 AM CDT are in DST
# Times AT/AFTER 1:00 AM CST are in standard time

# The wall clock goes: 01:59:59 CDT -> 01:00:00 CST (clock falls back)
# But in our data, wall clock goes: 00:59:59 -> 01:00:00 (advancing past midnight)
# This is the FIRST 01:00:00 (before the DST switch), so it should be CDT!

# Wait, let me check the R output again:
# Index 27215850: 2023-11-05 00:59:59.966 CDT (Unix: 1699163999.967) - AFTER force_tz
# 00:59:59 CDT = 05:59:59 UTC

# Index 27215851: 2023-11-05 01:00:00.000 CST (Unix: 1699167600.000) - AFTER force_tz
# 01:00:00 CST = 07:00:00 UTC

# So lubridate interprets:
# - 00:59:59 as CDT (6 hours behind UTC)
# - 01:00:00 as CST (6 hours behind UTC)

# But wait, CDT is UTC-5 and CST is UTC-6!
# Let me recalculate:
# 00:59:59 CDT = 05:59:59 UTC, Unix = 1699163999.967 ✓
# 01:00:00 CST = 07:00:00 UTC, Unix = 1699167600.000 ✓

# So the gap is exactly 1 hour + 0.033 seconds (1 sample at 30Hz)
# This makes sense because lubridate is treating the wall clock times as:
# - 00:59:59 = first occurrence of that time (CDT)
# - 01:00:00 = SECOND occurrence of that time (CST, after fall back)

# The key insight: when wall clock goes from 00:59:xx to 01:00:xx on Nov 5,
# lubridate treats the 01:00:xx as being AFTER the DST transition.

# This is a heuristic: once we reach the ambiguous hour (01:00-01:59),
# interpret it as standard time (CST).


# Unfortunately I can't easily test chrono_tz from Python
# Let me add some debug output to the Rust code instead
