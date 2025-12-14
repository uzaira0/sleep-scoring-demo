# Trace exactly where GGIR gets 244,080 epochs

library(read.gt3x)
library(lubridate)

file_path <- "D:/Scripts/monorepo/P1-1078-A-T1 (2023-11-08).gt3x"

# Read all data like GGIR does
cat("Reading GT3X file...\n")
data <- read.gt3x(path = file_path, asDataFrame = TRUE)
cat("Total samples from read.gt3x:", nrow(data), "\n")

# Apply force_tz like GGIR does
data$time <- force_tz(data$time, "America/Chicago")

# Check time range
cat("\nTime range:\n")
cat("First:", format(data$time[1], "%Y-%m-%d %H:%M:%S %Z"), "\n")
cat("Last:", format(data$time[nrow(data)], "%Y-%m-%d %H:%M:%S %Z"), "\n")

# Calculate expected epochs using GGIR's method
sf <- 30
ws3 <- 5  # epoch size
ws2 <- 900  # 15-min window

# GGIR truncates to ws2 boundaries
# use = (floor(LD / (ws2*sf))) * (ws2*sf)
LD <- nrow(data)
use <- floor(LD / (ws2*sf)) * (ws2*sf)
n_epochs <- use / (ws3 * sf)

cat("\nEpoch calculation:\n")
cat("Total samples (LD):", LD, "\n")
cat("Samples per ws2 (15-min):", ws2*sf, "\n")
cat("Number of ws2 windows:", floor(LD / (ws2*sf)), "\n")
cat("Usable samples (use):", use, "\n")
cat("Samples per epoch:", ws3*sf, "\n")
cat("Expected epochs:", n_epochs, "\n")

# Now check what happens with timestamps
cat("\n=== Checking timestamps at DST boundary ===\n")

# Find samples around Nov 5 2 AM (DST transition)
dst_time <- as.POSIXct("2023-11-05 02:00:00", tz = "America/Chicago")
dst_idx <- which.min(abs(as.numeric(data$time) - as.numeric(dst_time)))
cat("DST transition at sample index:", dst_idx, "\n")

# Check time deltas around DST
if (dst_idx > 100 && dst_idx < nrow(data) - 100) {
  cat("\nTimestamps around DST transition:\n")
  for (i in (dst_idx-5):(dst_idx+5)) {
    delta <- as.numeric(data$time[i+1]) - as.numeric(data$time[i])
    cat(sprintf("Sample %d: %s, delta=%.4f\n", i, format(data$time[i], "%Y-%m-%d %H:%M:%S %Z"), delta))
  }
}

# Check for any gaps in timestamps
cat("\n=== Checking for time gaps ===\n")
deltas <- diff(as.numeric(data$time))
expected_delta <- 1/sf
gaps <- which(abs(deltas - expected_delta) > 0.01)
cat("Number of timestamp anomalies:", length(gaps), "\n")

if (length(gaps) > 0) {
  cat("\nFirst 10 anomalies:\n")
  for (i in 1:min(10, length(gaps))) {
    idx <- gaps[i]
    cat(sprintf("Index %d: delta=%.4f sec (expected %.4f)\n", idx, deltas[idx], expected_delta))
    cat(sprintf("  Before: %s\n", format(data$time[idx], "%Y-%m-%d %H:%M:%S %Z")))
    cat(sprintf("  After:  %s\n", format(data$time[idx+1], "%Y-%m-%d %H:%M:%S %Z")))
  }
}
