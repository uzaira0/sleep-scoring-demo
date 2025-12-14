# GGIR Sleep Detection Validation Script
# This script runs GGIR's sleep detection algorithms on test GT3X files
# and exports the results for comparison with Python implementations.
#
# Algorithms validated:
# - vanHees2015 (SIB - Sustained Inactivity Bout detection)
# - HDCZA (Heuristic algorithm looking at Distribution of Change in Z-Angle)
# - Sadeh1994
# - ColeKripke1992
#
# References:
# - van Hees VT, et al. (2015). PLoS ONE. https://doi.org/10.1371/journal.pone.0142533
# - van Hees VT, et al. (2018). Scientific Reports. https://doi.org/10.1038/s41598-018-31266-z

library(GGIR)
library(data.table)

# Configuration
GGIR_PATH <- "D:/Scripts/monorepo/external/ggir"
OUTPUT_PATH <- file.path(GGIR_PATH, "output", "sleep_validation")
DATA_PATH <- file.path(GGIR_PATH, "data")

# Test file
TEST_FILE <- "TestUA_MOS2E22180349_2023-03-07___09-39-04.gt3x"

# Create output directory
dir.create(OUTPUT_PATH, showWarnings = FALSE, recursive = TRUE)
dir.create(file.path(OUTPUT_PATH, "validation_data"), showWarnings = FALSE)

cat("=== GGIR Sleep Detection Validation ===\n")
cat("Test file:", TEST_FILE, "\n")
cat("Output path:", OUTPUT_PATH, "\n\n")

# Helper function to calculate z-angle from raw acceleration
calculate_z_angle <- function(ax, ay, az) {
  # z_angle = arctan(az / sqrt(ax^2 + ay^2)) * (180/pi)
  return(atan2(az, sqrt(ax^2 + ay^2)) * (180 / pi))
}

# Run GGIR Part 1 to get calibrated data and angle
cat("Running GGIR Part 1 (calibration and metric extraction)...\n")

tryCatch({
  GGIR(
    datadir = DATA_PATH,
    outputdir = OUTPUT_PATH,
    mode = c(1, 2, 3),  # Parts 1, 2, 3 for sleep detection
    do.report = c(),
    overwrite = TRUE,
    verbose = TRUE,
    # Part 1 settings
    do.cal = TRUE,
    do.enmo = TRUE,
    do.anglez = TRUE,  # Calculate z-angle
    windowsizes = c(5, 900, 3600),  # 5-second epochs
    # Part 3 settings (sleep detection)
    HASIB.algo = "vanHees2015",  # SIB algorithm
    HASPT.algo = "HDCZA",  # SPT detection
    anglethreshold = 5,  # Default angle threshold
    timethreshold = 5,   # Default time threshold (minutes)
    # Additional sleep algorithms to test
    # These will be run separately
    f0 = 1,  # Start from first file
    f1 = 1   # Process only first file
  )
  cat("GGIR processing complete.\n\n")
}, error = function(e) {
  cat("Error running GGIR:", conditionMessage(e), "\n")
})

# Extract and export results
cat("Extracting validation data...\n")

# Find the output RData file
meta_files <- list.files(
  path = file.path(OUTPUT_PATH, "output_data", "meta", "basic"),
  pattern = "\\.RData$",
  full.names = TRUE
)

if (length(meta_files) > 0) {
  cat("Found meta file:", meta_files[1], "\n")

  # Load the RData file
  load(meta_files[1])

  # Extract angle-z data (M$metashort contains the 5-second epoch data)
  if (exists("M") && !is.null(M$metashort)) {
    metashort <- M$metashort

    # Export angle-z time series
    angle_z_df <- data.frame(
      timestamp = metashort$timestamp,
      anglez = metashort$anglez,
      ENMO = metashort$ENMO
    )

    write.csv(
      angle_z_df,
      file.path(OUTPUT_PATH, "validation_data", "r_anglez_5sec.csv"),
      row.names = FALSE
    )
    cat("Exported angle-z data:", nrow(angle_z_df), "rows\n")
  }

  # Extract metalong (15-minute epoch data with non-wear)
  if (exists("M") && !is.null(M$metalong)) {
    metalong <- M$metalong

    metalong_df <- data.frame(
      timestamp = metalong$timestamp,
      nonwearscore = metalong$nonwearscore
    )

    write.csv(
      metalong_df,
      file.path(OUTPUT_PATH, "validation_data", "r_metalong.csv"),
      row.names = FALSE
    )
    cat("Exported metalong data:", nrow(metalong_df), "rows\n")
  }
}

# Now run HASIB and HASPT directly on the angle data for detailed validation
cat("\n=== Running HASIB algorithms directly ===\n")

if (exists("M") && !is.null(M$metashort)) {
  anglez <- M$metashort$anglez
  timestamps <- M$metashort$timestamp
  ws3 <- 5  # 5-second epochs

  # Run vanHees2015 (SIB)
  cat("Running vanHees2015 SIB...\n")
  sib_result <- HASIB(
    HASIB.algo = "vanHees2015",
    timethreshold = 5,
    anglethreshold = 5,
    time = timestamps,
    anglez = anglez,
    ws3 = ws3
  )

  # Export SIB results
  sib_df <- data.frame(
    timestamp = timestamps,
    anglez = anglez,
    sib_T5A5 = as.numeric(sib_result[, 1])
  )

  write.csv(
    sib_df,
    file.path(OUTPUT_PATH, "validation_data", "r_sib_vanHees2015.csv"),
    row.names = FALSE
  )
  cat("Exported SIB results:", nrow(sib_df), "rows\n")
  cat("  Sleep epochs:", sum(sib_df$sib_T5A5 == 1), "\n")
  cat("  Wake epochs:", sum(sib_df$sib_T5A5 == 0), "\n")

  # Run HDCZA for SPT detection
  cat("\nRunning HDCZA SPT detection...\n")

  # Create invalid vector (all valid for now)
  invalid <- rep(0, length(anglez))

  # HDCZA parameters
  params_sleep <- list(
    HDCZA_threshold = c(10, 15),  # 10th percentile * 15
    spt_min_block_dur = 30,       # Minimum 30 minutes
    spt_max_gap_dur = 60,         # Maximum 60 minute gaps
    HASPT.ignore.invalid = FALSE
  )

  hdcza_result <- HASPT(
    angle = anglez,
    params_sleep = params_sleep,
    ws3 = ws3,
    HASPT.algo = "HDCZA",
    invalid = invalid
  )

  # Export HDCZA results
  hdcza_df <- data.frame(
    SPTE_start_idx = hdcza_result$SPTE_start,
    SPTE_end_idx = hdcza_result$SPTE_end,
    tib_threshold = hdcza_result$tib.threshold,
    part3_guider = hdcza_result$part3_guider
  )

  write.csv(
    hdcza_df,
    file.path(OUTPUT_PATH, "validation_data", "r_hdcza_spt.csv"),
    row.names = FALSE
  )
  cat("Exported HDCZA SPT results\n")
  cat("  SPT start index:", hdcza_result$SPTE_start, "\n")
  cat("  SPT end index:", hdcza_result$SPTE_end, "\n")
  cat("  Threshold:", hdcza_result$tib.threshold, "\n")

  # Also export the crude SPT estimate if available
  if (!is.null(hdcza_result$spt_crude_estimate)) {
    spt_crude_df <- data.frame(
      timestamp = timestamps[1:length(hdcza_result$spt_crude_estimate)],
      spt_crude = hdcza_result$spt_crude_estimate
    )

    write.csv(
      spt_crude_df,
      file.path(OUTPUT_PATH, "validation_data", "r_hdcza_spt_crude.csv"),
      row.names = FALSE
    )
    cat("Exported HDCZA crude SPT estimate:", nrow(spt_crude_df), "rows\n")
  }
}

cat("\n=== Validation data export complete ===\n")
cat("Output directory:", file.path(OUTPUT_PATH, "validation_data"), "\n")
cat("\nFiles created:\n")
list.files(file.path(OUTPUT_PATH, "validation_data"), full.names = FALSE)
