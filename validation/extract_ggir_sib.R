# Extract anglez and compute HASIB from existing GGIR RData files
# Save both anglez and sleep_score for Python validation

library(GGIR)

rdata_dir <- "D:/Scripts/monorepo/external/ggir/output/batch_r/output_data/meta/basic"
output_dir <- "D:/Scripts/monorepo/apps/sleep-scoring-demo/validation/ggir_reference"

rdata_files <- list.files(rdata_dir, pattern = "\\.RData$", full.names = TRUE)
cat("Found", length(rdata_files), "RData files\n")

# Process files
for (rdata_file in rdata_files[1:20]) {
  filename <- basename(rdata_file)
  cat("\nProcessing:", filename, "\n")

  tryCatch({
    load(rdata_file)

    if (!exists("M") || is.null(M$metashort)) {
      cat("  No metashort data\n")
      next
    }

    anglez <- M$metashort$anglez
    timestamps <- M$metashort$timestamp

    cat("  Epochs:", length(anglez), "\n")

    # Run HASIB vanHees2015 - wrap in tryCatch
    # ws3 = epoch size in seconds (5 for 5-second epochs)
    sib_result <- tryCatch({
      GGIR::HASIB(
        HASIB.algo = "vanHees2015",
        timethreshold = 5,
        anglethreshold = 5,
        time = timestamps,
        anglez = anglez,
        ws3 = 5
      )
    }, error = function(e) {
      cat("  HASIB error:", conditionMessage(e), "\n")
      return(NULL)
    })

    if (is.null(sib_result)) next

    # Extract the T5A5 column (timethreshold=5, anglethreshold=5)
    # HASIB returns a data.frame with columns like "T5A5"
    if (is.data.frame(sib_result) && "T5A5" %in% names(sib_result)) {
      sib <- sib_result$T5A5
      cat("  Using column: T5A5\n")
    } else if (is.data.frame(sib_result)) {
      # Try first column
      sib <- sib_result[, 1]
      cat("  Using first column:", names(sib_result)[1], "\n")
    } else if (is.numeric(sib_result) && length(sib_result) == length(anglez)) {
      sib <- sib_result
      cat("  Using numeric result directly\n")
    } else {
      cat("  Could not extract sleep scores. Result type:", class(sib_result), "\n")
      if (is.data.frame(sib_result)) cat("  Columns:", paste(names(sib_result), collapse=", "), "\n")
      next
    }

    cat("  Sleep epochs:", sum(sib), "(", round(100*mean(sib), 1), "%)\n")

    # Create output dataframe
    result_df <- data.frame(
      timestamp = timestamps,
      anglez = anglez,
      sleep_score = as.integer(sib)
    )

    # Save
    orig_name <- sub("^meta_", "", sub("\\.RData$", "", filename))
    orig_name <- sub("\\.gt3x$", "", orig_name)
    orig_name <- gsub(" ", "_", orig_name)
    orig_name <- gsub("[()]", "", orig_name)

    output_file <- file.path(output_dir, paste0(orig_name, "_sib.csv"))
    write.csv(result_df, output_file, row.names = FALSE)
    cat("  Saved:", basename(output_file), "\n")

  }, error = function(e) {
    cat("  ERROR:", conditionMessage(e), "\n")
  })

  # Clean up to avoid memory issues
  rm(M)
  gc()
}

cat("\nDone!\n")
