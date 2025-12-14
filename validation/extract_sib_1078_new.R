# Extract SIB data from the reprocessed GGIR output for P1-1078-A-T1
rdata_path <- "D:/Scripts/monorepo/apps/sleep-scoring-demo/validation/ggir_reprocess/output_ggir_input/meta/basic/meta_P1-1078-A-T1 (2023-11-08).gt3x.RData"
load(rdata_path)

# Get metashort data
metashort <- M$metashort

cat("Columns in metashort:\n")
print(names(metashort))

# Add sleep_score column using HASIB algorithm (from van Hees 2015)
# This is computed in Part 3, but we only ran Part 1-2
# For now, just save the anglez and we'll compute HASIB in Python

output_path <- "D:/Scripts/monorepo/apps/sleep-scoring-demo/validation/ggir_reference/P1-1078-A-T1_2023-11-08_anglez_reprocessed.csv"
write.csv(metashort[, c("timestamp", "anglez")], output_path, row.names = FALSE)

cat("Number of epochs:", nrow(metashort), "\n")
cat("Saved to:", output_path, "\n")
cat("First 5 rows:\n")
print(head(metashort[, c("timestamp", "anglez")], 5))
cat("Last 5 rows:\n")
print(tail(metashort[, c("timestamp", "anglez")], 5))
