rdata_path <- "D:/Scripts/monorepo/apps/sleep-scoring-demo/validation/ggir_reprocess/output_ggir_input/meta/basic/meta_P1-1078-A-T1 (2023-11-08).gt3x.RData"
load(rdata_path)

# Extract calibration coefficients
cal <- C$cal.error.end

cat("offset_x,offset_y,offset_z,scale_x,scale_y,scale_z\n")
cat(paste(cal$offset[1], cal$offset[2], cal$offset[3],
          cal$scale[1], cal$scale[2], cal$scale[3], sep=","), "\n")

# Save to CSV
output_path <- "D:/Scripts/monorepo/apps/sleep-scoring-demo/validation/ggir_reference/P1-1078-A-T1_calibration_new.csv"
cal_df <- data.frame(
  offset_x = cal$offset[1],
  offset_y = cal$offset[2],
  offset_z = cal$offset[3],
  scale_x = cal$scale[1],
  scale_y = cal$scale[2],
  scale_z = cal$scale[3]
)
write.csv(cal_df, output_path, row.names = FALSE)
cat("Saved to:", output_path, "\n")
