# Check what read.gt3x returns for timestamps
library(read.gt3x)

file_path <- "D:/Scripts/monorepo/P1-1078-A-T1 (2023-11-08).gt3x"

# Read first 1000 samples
data <- read.gt3x(path = file_path, batch_begin = 1, batch_end = 1000, asDataFrame = TRUE)

cat("=== read.gt3x output ===\n")
cat("Class of time column:", class(data$time), "\n")
cat("Timezone of time column:", attr(data$time, "tzone"), "\n")
cat("\nFirst 5 timestamps:\n")
print(head(data$time, 5))

cat("\nTimestamps as numeric (Unix):\n")
print(as.numeric(head(data$time, 5)))

# Now apply force_tz like GGIR does
library(lubridate)
data$time_forced <- force_tz(data$time, "America/Chicago")

cat("\n=== After force_tz to America/Chicago ===\n")
cat("First 5 timestamps:\n")
print(head(data$time_forced, 5))

cat("\nTimestamps as numeric (Unix):\n")
print(as.numeric(head(data$time_forced, 5)))

# Check total sample count
cat("\n=== Sample count check ===\n")
full_data <- read.gt3x(path = file_path, asDataFrame = TRUE)
cat("Total samples:", nrow(full_data), "\n")
cat("First timestamp:", format(full_data$time[1]), "\n")
cat("Last timestamp:", format(full_data$time[nrow(full_data)]), "\n")
