# Check GGIR epoch count and timestamps
rdata_path <- "D:/Scripts/monorepo/apps/sleep-scoring-demo/validation/ggir_reprocess/output_ggir_input/meta/basic/meta_P1-1078-A-T1 (2023-11-08).gt3x.RData"
load(rdata_path)

cat("=== GGIR metashort info ===\n")
cat("Number of epochs:", nrow(M$metashort), "\n")
cat("Columns:", paste(names(M$metashort), collapse=", "), "\n")

cat("\nFirst 5 timestamps:\n")
print(head(M$metashort$timestamp, 5))

cat("\nLast 5 timestamps:\n")
print(tail(M$metashort$timestamp, 5))

# Check timestamps around DST (Nov 5, 2023 1-2 AM)
cat("\n=== DST check ===\n")
timestamps <- M$metashort$timestamp

# Count epochs per hour on Nov 5
nov5_1am <- grep("2023-11-05T01:", timestamps)
nov5_2am <- grep("2023-11-05T02:", timestamps)
nov5_0am <- grep("2023-11-05T00:", timestamps)

cat("Epochs at 00:xx on Nov 5:", length(nov5_0am), "\n")
cat("Epochs at 01:xx on Nov 5:", length(nov5_1am), "\n")
cat("Epochs at 02:xx on Nov 5:", length(nov5_2am), "\n")

# Show timestamps around the DST transition
if (length(nov5_1am) > 0) {
  cat("\nFirst few 1AM timestamps:\n")
  print(timestamps[nov5_1am[1:min(5, length(nov5_1am))]])
  cat("\nLast few 1AM timestamps:\n")
  print(timestamps[nov5_1am[(length(nov5_1am)-4):length(nov5_1am)]])
}
