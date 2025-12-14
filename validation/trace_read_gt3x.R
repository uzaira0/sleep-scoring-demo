# Trace what read.gt3x does with timestamps

library(read.gt3x)
library(lubridate)

gt3x_file <- "W:/Projects/TECH Study/Data/Accelerometer Data/Raw Data/gt3x/T1/P1-1078-A-T1 (2023-11-08).gt3x"

cat("Loading GT3X file...\n")
data <- read.gt3x(gt3x_file, asDataFrame = TRUE)

cat("Total samples:", nrow(data), "\n")
cat("Columns:", paste(colnames(data), collapse=", "), "\n")
cat("\n")

# Check the timestamp column
cat("First timestamp:\n")
print(data$time[1])
cat("  Class:", class(data$time[1]), "\n")
cat("  TZ:", attr(data$time[1], "tzone"), "\n")
cat("  As numeric (Unix):", as.numeric(data$time[1]), "\n")

cat("\n")

# Look at timestamps around the DST transition
# From previous analysis, sample ~27,215,850 is around Nov 5

# Find samples around Nov 5, 01:00:00
target_unix <- as.numeric(as.POSIXct("2023-11-05 01:00:00", tz="GMT"))
cat("Looking for samples near Unix timestamp:", target_unix, "\n")

# Find the closest sample
diffs <- abs(as.numeric(data$time) - target_unix)
closest_idx <- which.min(diffs)
cat("Closest sample index:", closest_idx, "\n")
cat("Closest sample timestamp:", as.character(data$time[closest_idx]), "\n")
cat("Closest sample Unix:", as.numeric(data$time[closest_idx]), "\n")

cat("\n")
cat("Timestamps around index", closest_idx, ":\n")
for (i in (closest_idx - 5):(closest_idx + 100)) {
    if (i > 0 && i <= nrow(data)) {
        ts <- data$time[i]
        unix_ts <- as.numeric(ts)
        if (i > closest_idx - 5) {
            prev_unix <- as.numeric(data$time[i - 1])
            delta <- unix_ts - prev_unix
            if (abs(delta - 1/30) > 0.001) {
                cat(sprintf("*** GAP *** Index %d: %s (Unix: %.3f, delta: %.4f)\n",
                    i, format(ts, "%Y-%m-%d %H:%M:%OS3 %Z"), unix_ts, delta))
            } else if (i <= closest_idx + 5) {
                cat(sprintf("Index %d: %s (Unix: %.3f)\n",
                    i, format(ts, "%Y-%m-%d %H:%M:%OS3 %Z"), unix_ts))
            }
        }
    }
}

cat("\n")
cat("Now applying force_tz...\n")
data$time_forced <- force_tz(data$time, "America/Chicago")

cat("\nAfter force_tz, timestamps around index", closest_idx, ":\n")
for (i in (closest_idx - 5):(closest_idx + 100)) {
    if (i > 0 && i <= nrow(data)) {
        ts <- data$time_forced[i]
        unix_ts <- as.numeric(ts)
        if (i > closest_idx - 5) {
            prev_unix <- as.numeric(data$time_forced[i - 1])
            delta <- unix_ts - prev_unix
            if (abs(delta - 1/30) > 0.001) {
                cat(sprintf("*** GAP *** Index %d: %s (Unix: %.3f, delta: %.4f)\n",
                    i, format(ts, "%Y-%m-%d %H:%M:%OS3 %Z"), unix_ts, delta))
            } else if (i <= closest_idx + 5) {
                cat(sprintf("Index %d: %s (Unix: %.3f)\n",
                    i, format(ts, "%Y-%m-%d %H:%M:%OS3 %Z"), unix_ts))
            }
        }
    }
}
