# Test R's handling of DST
library(lubridate)

# Start time (Oct 25, 2023 1:00 PM CDT)
start_str <- "2023-10-25T13:00:00-0500"
start <- as.POSIXlt(start_str, format="%Y-%m-%dT%H:%M:%S%z", tz="America/Chicago")

cat("Start time:", format(start), "\n")
cat("Start as numeric (Unix):", as.numeric(start), "\n")

# Generate epochs (5 second intervals)
ws3 <- 5
n_epochs <- 243360  # What we expect from the data

# Method 1: Sequential Unix timestamps
starttime3 <- round(as.numeric(start))
time5 <- seq(starttime3, (starttime3 + ((n_epochs - 1) * ws3)), by = ws3)
time6 <- as.POSIXlt(time5, origin = "1970-01-01", tz = "America/Chicago")
timestamps <- strftime(time6, format = "%Y-%m-%dT%H:%M:%S%z")

cat("\nMethod 1 (GGIR's method):\n")
cat("Number of timestamps:", length(timestamps), "\n")
cat("First:", timestamps[1], "\n")
cat("Last:", timestamps[length(timestamps)], "\n")

# Check DST transition
nov5_1am <- grep("2023-11-05T01:", timestamps)
cat("Epochs at 01:xx on Nov 5:", length(nov5_1am), "\n")

# What's the last timestamp time in hours from start?
last_unix <- time5[length(time5)]
duration_hours <- (last_unix - starttime3) / 3600
cat("Duration in hours:", duration_hours, "\n")

# Now let's check what happens with 244080 epochs
n_epochs2 <- 244080
time5b <- seq(starttime3, (starttime3 + ((n_epochs2 - 1) * ws3)), by = ws3)
time6b <- as.POSIXlt(time5b, origin = "1970-01-01", tz = "America/Chicago")
timestamps_b <- strftime(time6b, format = "%Y-%m-%dT%H:%M:%S%z")

cat("\nWith 244080 epochs:\n")
cat("Last:", timestamps_b[length(timestamps_b)], "\n")
duration_hours_b <- (time5b[length(time5b)] - starttime3) / 3600
cat("Duration in hours:", duration_hours_b, "\n")
