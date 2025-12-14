# Extract anglez and run HASIB from existing GGIR RData files
library(GGIR)

rdata_dir <- "D:/Scripts/monorepo/external/ggir/output/batch_r/output_data/meta/basic"
output_dir <- "D:/Scripts/monorepo/apps/sleep-scoring-demo/validation/ggir_reference"

rdata_files <- list.files(rdata_dir, pattern = "\\.RData$", full.names = TRUE)
cat("Found", length(rdata_files), "RData files\n")

# Process first 20 files
for (rdata_file in rdata_files[1:min(20, length(rdata_files))]) {
  filename <- basename(rdata_file)
  cat("\nProcessing:", filename, "\n")

  tryCatch({
    load(rdata_file)

    # Extract metashort (5-sec epoch data)
    if (!exists("M") || is.null(M$metashort)) {
      cat("  No metashort data\n")
      next
    }

    anglez <- M$metashort$anglez
    timestamps <- M$metashort$timestamp

    cat("  Epochs:", length(anglez), "\n")
    cat("  NA epochs:", sum(is.na(anglez)), "\n")

    # Run HASIB vanHees2015
    sib_result <- GGIR::HASIB(
      HASIB.algo = "vanHees2015",
      timethreshold = 5,
      anglethreshold = 5,
      time = timestamps,
      anglez = anglez
    )

    # Extract sleep scores from result (HASIB returns a list)
    if (is.list(sib_result)) {
      # Try different possible field names
      if (!is.null(sib_result$sib.cla.sum)) {
        sib <- sib_result$sib.cla.sum
      } else if (!is.null(sib_result$sibdetection)) {
        sib <- sib_result$sibdetection
      } else {
        # Just use first element
        sib <- sib_result[[1]]
      }
    } else {
      sib <- sib_result
    }

    # Ensure it's numeric
    sib <- as.numeric(sib)

    cat("  Sleep epochs:", sum(sib, na.rm=TRUE), "(", round(100*mean(sib, na.rm=TRUE), 1), "%)\n")

    # Create output dataframe
    result_df <- data.frame(
      timestamp = timestamps,
      anglez = anglez,
      sleep_score = sib
    )

    # Save - extract original filename from meta_XXX.gt3x.RData
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
}

cat("\nDone!\n")
