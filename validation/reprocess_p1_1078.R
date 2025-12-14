# Reprocess P1-1078-A-T1 with GGIR using the correct GT3X file

library(GGIR)

# Copy the file to a temp input directory to avoid GGIR's path restriction
input_dir <- "D:/Scripts/monorepo/apps/sleep-scoring-demo/validation/ggir_input"
dir.create(input_dir, showWarnings = FALSE, recursive = TRUE)

src_file <- "D:/Scripts/monorepo/P1-1078-A-T1 (2023-11-08).gt3x"
dst_file <- file.path(input_dir, basename(src_file))
if (!file.exists(dst_file)) {
  file.copy(src_file, dst_file)
}

# Output directory
output_dir <- "D:/Scripts/monorepo/apps/sleep-scoring-demo/validation/ggir_reprocess"
dir.create(output_dir, showWarnings = FALSE, recursive = TRUE)

# Run GGIR Part 1 only to get anglez
cat("Processing:", dst_file, "\n")

# Use GGIR's g.getmeta to get the anglez values
result <- GGIR(
  datadir = input_dir,
  outputdir = output_dir,
  studyname = "reprocess_1078",
  mode = 1:2,  # Part 1 and 2 only
  overwrite = TRUE,
  do.report = FALSE,
  do.parallel = FALSE,
  windowsizes = c(5, 900, 3600),
  do.enmo = TRUE,
  do.anglez = TRUE,
  desiredtz = "America/Chicago"
)

cat("Done! Check output in:", output_dir, "\n")
