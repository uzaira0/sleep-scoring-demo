# Extract anglez from reprocessed P1-1078-A-T1

rdata_file <- "D:/Scripts/monorepo/apps/sleep-scoring-demo/validation/ggir_reprocess/output_ggir_input/meta/basic/meta_P1-1078-A-T1 (2023-11-08).gt3x.RData"
output_file <- "D:/Scripts/monorepo/apps/sleep-scoring-demo/validation/ggir_reference/P1-1078-A-T1_2023-11-08_anglez_new.csv"

load(rdata_file)

# M$metashort contains the 5-second epoch data
metashort <- M$metashort

cat("Columns in metashort:\n")
print(colnames(metashort))

cat("\nNumber of epochs:", nrow(metashort), "\n")

# Extract timestamp and anglez
df <- data.frame(
  timestamp = metashort[, "timestamp"],
  anglez = as.numeric(metashort[, "anglez"])
)

write.csv(df, output_file, row.names = FALSE)
cat("Saved to:", output_file, "\n")
cat("First 5 rows:\n")
print(head(df, 5))
cat("Last 5 rows:\n")
print(tail(df, 5))
