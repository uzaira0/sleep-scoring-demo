"""Debug force_tz - trace exact issue."""

from datetime import datetime, timezone

import pytz

chicago = pytz.timezone("America/Chicago")
utc = pytz.UTC

# From our data:
# start_time = 1698238800 (stored in GT3X as Unix timestamp)
# This is Oct 25, 2023 13:00:00 UTC = Oct 25, 2023 08:00:00 CDT

# But here's the key: the device was SET UP in Chicago timezone
# The start_time 1698238800 was MEANT to represent 08:00:00 local time
# But it got stored as 13:00:00 UTC (which is correct for 08:00 CDT)

# So when we compute timestamps as start_time + offset, we get TRUE UTC timestamps
# And there's no DST gap because Unix time is continuous

# HOWEVER, read.gt3x in R does something different:
# It creates timestamps with the GMT/UTC label, but the underlying values
# represent the LOCAL time the device recorded

# Let me trace through what R does:


# The GT3X file stores:
# - Start time as Unix timestamp (1698238800)
# - Sample offsets as subsecond values

# read.gt3x creates a POSIXct timestamp for each sample
# For sample at offset 907200 (10.5 days later), it creates:
# POSIXct = start_time + offset = 1698238800 + 907200 = 1699146000

# This Unix timestamp represents:
utc_ts = 1699146000
utc_dt = datetime.fromtimestamp(utc_ts, tz=utc)

# So 1699146000 UTC = Nov 5, 2023 01:00:00 UTC = Nov 4, 2023 20:00:00 CDT
# This is BEFORE the DST transition (which is Nov 5, 2023 02:00:00 CDT)

# Now here's the key insight:
# read.gt3x labels this timestamp as "GMT" but it's actually local time
# The comment in g.readaccfile.R says:
# "read.gt3x::read.gt3x returns timestamps as POSIXct with GMT timezone,
#  but they are actally in local time of the device."

# So read.gt3x is creating a POSIXct that LOOKS like:
#   2023-11-05 01:00:00 GMT
# But should actually represent:
#   2023-11-05 01:00:00 America/Chicago

# Then lubridate::force_tz changes it from GMT to America/Chicago:
# force_tz("2023-11-05 01:00:00 GMT", "America/Chicago")
#   → "2023-11-05 01:00:00 CDT" or "2023-11-05 01:00:00 CST"

# The question is: which one? CDT or CST?
# On Nov 5, 2023, 01:00:00 is AMBIGUOUS in Chicago:
# - 01:00:00 CDT (before DST ends at 2:00 AM)
# - 01:00:00 CST (after DST ends, clock falls back to 1:00 AM)

# lubridate probably picks one based on some rule...
# Let's check with pytz


# The time 01:00:00 on Nov 5, 2023 is ambiguous in Chicago
ambiguous_time = datetime(2023, 11, 5, 1, 0, 0)

# With is_dst=True (CDT)
cdt_version = chicago.localize(ambiguous_time, is_dst=True)

# With is_dst=False (CST)
cst_version = chicago.localize(ambiguous_time, is_dst=False)


# NOW the key question:
# If samples N and N+1 have wall clock times:
#   N: 01:59:59
#   N+1: 02:00:00 (which becomes 01:00:00 when DST ends)
#
# How does read.gt3x handle this?
# And how does force_tz handle the resulting timestamps?


# The device records continuously. At 01:59:59 CDT, the next sample is 01:59:59.033 CDT.
# Then at 02:00:00 CDT, the clock jumps BACK to 01:00:00 CST.
# But does the GT3X device actually record this?

# From our debug output, the GT3X data shows continuous timestamps
# with no gap at sample 27,215,850. The timestamps go:
#   907199.9667 -> 907200.0000 (continuous, 0.033s apart)

# This means the GT3X device does NOT adjust for DST internally.
# It just keeps counting seconds from start.

# So the "01:00:00" in the GT3X data is NOT the DST-adjusted time,
# it's just start_time + 907200 seconds.

# BUT - and here's the key - when read.gt3x creates POSIXct timestamps,
# it formats them as human-readable times. And the human-readable time
# for Unix timestamp 1699146000 + 21600 (CDT offset) would be... let me check

# Actually, I think the issue is different. Let me check what Unix timestamp
# corresponds to each sample.


# From my understanding, read.gt3x does this:
# 1. Read start_time from GT3X (Unix timestamp)
# 2. For each sample, compute timestamp = start_time + (sample_index / sample_rate)
# 3. Return as POSIXct with GMT timezone

# So for sample 27,215,850:
# timestamp = 1698238800 + (27215850 / 30) = 1698238800 + 907195 = 1699145995

start_time = 1698238800
sample_rate = 30
sample_index = 27215850

timestamp_unix = start_time + (sample_index / sample_rate)

# Hmm, that's Nov 5, 2023 00:59:55 UTC = Nov 4, 2023 19:59:55 CDT
# That's NOT at the DST transition time

# Let me find the correct sample index for the DST transition
# DST transition: Nov 5, 2023 02:00:00 CDT = Nov 5, 2023 07:00:00 UTC
dst_transition_unix = datetime(2023, 11, 5, 7, 0, 0, tzinfo=utc).timestamp()

samples_from_start = (dst_transition_unix - start_time) * sample_rate

# So DST transition should be around sample 27,864,000, not 27,215,850!

# Let me check what the R trace script actually found...
# The R script said the gap was at index 27,215,850 with:
#   Before: 2023-11-05 00:59:59 CDT
#   After:  2023-11-05 01:00:00 CST

# If "00:59:59 CDT" is the wall clock time shown in R, then the Unix timestamp would be:
# 2023-11-05 00:59:59 CDT = 2023-11-05 05:59:59 UTC
before_dst_unix = datetime(2023, 11, 5, 5, 59, 59, tzinfo=utc).timestamp()

# And "01:00:00 CST" would be:
# 2023-11-05 01:00:00 CST = 2023-11-05 07:00:00 UTC
after_dst_unix = datetime(2023, 11, 5, 7, 0, 0, tzinfo=utc).timestamp()


# So the gap in R is between Unix timestamps 1699167599 and 1699171200
# That's a gap of 3601 seconds (1 hour + 1 second)

# Now let me find which sample corresponds to 1699167599
sample_at_before = (before_dst_unix - start_time) * sample_rate

# Hmm, that's around 27.86M, not 27.21M
# There's a discrepancy in my understanding...

# WAIT - I think I finally get it!
# The issue is that read.gt3x labels the timestamps as GMT, but they're LOCAL time!
# So Unix timestamp 1699146000 is labeled as "2023-11-05 01:00:00 GMT" by R
# But this is WRONG - it's actually a local time that happened to be stored as UTC

# The start_time in the GT3X file represents a LOCAL time, not UTC!
# So 1698238800 doesn't mean Oct 25 13:00 UTC
# It means Oct 25 08:00 CDT was stored AS IF it were 08:00 UTC


# The GT3X device stores start_time as local time but without timezone info
# It gets interpreted as UTC by parsers

# If start_time represents 08:00:00 CDT (local), but is stored as Unix timestamp
# using UTC interpretation, then:
# 08:00:00 treated as UTC gives Unix timestamp 1698220800 (wrong)
# 08:00:00 CDT is actually Unix timestamp 1698238800 (stored value)

# Wait, that's confusing. Let me think again...

# Actually, the stored value 1698238800 IS correct for 08:00 CDT!
# Because 08:00 CDT = 13:00 UTC = 1698238800

# So the start_time is correct. The issue must be elsewhere.

# Let me re-read the R source code comment more carefully:
# "read.gt3x::read.gt3x returns timestamps as POSIXct with GMT timezone,
#  but they are actally in local time of the device."

# This means read.gt3x is doing something weird internally.
# Let me check the read.gt3x source code...
