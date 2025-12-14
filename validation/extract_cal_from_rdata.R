# Extract calibration from the GGIR RData file
rdata_path <- "D:/Scripts/monorepo/apps/sleep-scoring-demo/validation/ggir_reprocess/output_ggir_input/meta/basic/meta_P1-1078-A-T1 (2023-11-08).gt3x.RData"
load(rdata_path)

cat("Objects loaded:\n")
print(ls())

cat("\nC object structure:\n")
print(names(C))

cat("\nCalibration from C:\n")
print(C$scale)
print(C$offset)

cat("\nM object names:\n")
print(names(M))
