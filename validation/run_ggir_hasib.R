# Run GGIR HASIB (vanHees2015) on GT3X files
# This uses the actual GGIR implementation, not a custom reimplementation

library(GGIR)

# Configuration
input_dir <- "D:/Scripts/monorepo/external/ggir/data"
output_dir <- "D:/Scripts/monorepo/apps/sleep-scoring-demo/validation/ggir_reference"

# Get all GT3X files
gt3x_files <- list.files(input_dir, pattern = "\\.gt3x$", full.names = TRUE)
cat("Found", length(gt3x_files), "GT3X files\n")

for (gt3x_file in gt3x_files) {
  filename <- basename(gt3x_file)

  if (grepl("DO NOT USE", filename)) {
    cat("Skipping:", filename, "\n")
    next
  }

  cat("\n========================================\n")
  cat("Processing:", filename, "\n")

  tryCatch({
    # Run GGIR part 1 to get metashort (contains anglez at 5-sec epochs)
    # This is the proper way to get GGIR's anglez calculation

    temp_output <- tempdir()

    GGIR(
      datadir = dirname(gt3x_file),
      outputdir = temp_output,
      studyname = tools::file_path_sans_ext(filename),
      mode = 1,  # Only part 1
      do.report = FALSE,
      overwrite = TRUE,
      print.filename = TRUE,
      desiredtz = "America/Chicago",
      windowsizes = c(5, 900, 3600),  # 5-sec epochs
      do.anglez = TRUE,
      do.anglex = FALSE,
      do.angley = FALSE,
      do.enmo = FALSE,
      chunksize = 1,
      do.cal = TRUE,
      minloadcrit = 72,
      verbose = FALSE,
      f0 = which(basename(list.files(dirname(gt3x_file), pattern = "\\.gt3x$")) == filename),
      f1 = which(basename(list.files(dirname(gt3x_file), pattern = "\\.gt3x$")) == filename)
    )

    # Find the output RData file
    ms_file <- list.files(
      file.path(temp_output, "output_", tools::file_path_sans_ext(filename), "meta/basic"),
      pattern = "meta_.*\\.RData$",
      full.names = TRUE
    )

    if (length(ms_file) > 0) {
      # Load metashort data
      load(ms_file[1])

      # Extract anglez and timestamps
      anglez <- M$metashort$anglez
      timestamps <- M$metashort$timestamp

      # Run HASIB with vanHees2015
      sib_result <- GGIR::HASIB(
        HASIB.algo = "vanHees2015",
        timethreshold = 5,
        anglethreshold = 5,
        time = timestamps,
        anglez = anglez
      )

      # Create output dataframe
      result_df <- data.frame(
        timestamp = timestamps,
        anglez = anglez,
        sleep_score = sib_result
      )

      # Save
      file_id <- tools::file_path_sans_ext(filename)
      file_id <- gsub(" ", "_", file_id)
      file_id <- gsub("[()]", "", file_id)
      output_file <- file.path(output_dir, paste0(file_id, "_sib.csv"))
      write.csv(result_df, output_file, row.names = FALSE)

      cat("  Epochs:", nrow(result_df), "\n")
      cat("  Sleep:", sum(result_df$sleep_score), "(", round(100*mean(result_df$sleep_score), 1), "%)\n")
      cat("  Saved:", output_file, "\n")
    } else {
      cat("  ERROR: No metashort file found\n")
    }

  }, error = function(e) {
    cat("  ERROR:", conditionMessage(e), "\n")
  })
}

cat("\n========================================\n")
cat("Done!\n")
