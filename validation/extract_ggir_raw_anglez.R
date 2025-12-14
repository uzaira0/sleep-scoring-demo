# Extract raw anglez from GGIR RData file and look at day boundaries

rdata_file <- "D:/Scripts/monorepo/external/ggir/output/batch_r/output_data/meta/basic/meta_P1-1093-A-T1 (2024-03-04).gt3x.RData"

load(rdata_file)

cat("Objects loaded:\n")
print(ls())

# M contains metashort (5-sec epochs)
cat("\nM structure:\n")
print(names(M))

cat("\nmetashort columns:\n")
print(names(M$metashort))

# Get anglez
anglez <- M$metashort$anglez
cat("\nAnglez length:", length(anglez), "\n")
cat("First 10 values:", head(anglez, 10), "\n")

# Check day boundaries (every 17280 epochs)
epochs_per_day <- 17280
n_days <- ceiling(length(anglez) / epochs_per_day)

cat("\nDay boundaries:\n")
for (d in 0:(n_days-1)) {
  end_idx <- min((d+1) * epochs_per_day, length(anglez))
  start_idx <- d * epochs_per_day + 1

  # Last epoch of previous day (if not first day)
  if (d > 0) {
    prev_end <- d * epochs_per_day
    cat(sprintf("Day %d end (epoch %d): anglez = %.4f\n", d-1, prev_end, anglez[prev_end]))
  }

  # First epoch of this day
  cat(sprintf("Day %d start (epoch %d): anglez = %.4f\n", d, start_idx, anglez[start_idx]))
}

# Save to CSV for comparison
write.csv(data.frame(epoch=1:length(anglez), anglez=anglez),
          "validation/ggir_reference/P1-1093-A-T1_2024-03-04_anglez_from_rdata.csv",
          row.names=FALSE)
cat("\nSaved anglez to CSV\n")
