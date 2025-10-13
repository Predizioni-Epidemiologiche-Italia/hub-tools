#install.packages("scoringutils")
library(scoringutils)
library(dplyr)
# source("forecast_utils.R")


# Add parameters for previsioni_dir, supporting_dir, sorveglianza_dir


# ---- Imposta working directory robusto ----
suppressMessages({
  if (!requireNamespace("fs", quietly = TRUE)) install.packages("fs")
  if (!requireNamespace("here", quietly = TRUE)) install.packages("here")
  library(fs)
  library(here)
})

# Rileva automaticamente la root del repo corrente (InflucastEval)
root <- here::here()
cat(sprintf("Working directory base: %s\n", root))

# Costruisci percorsi relativi ai repository coinvolti
hub_tools_dir <- fs::path(root, "hub-tools", "r_code")
forecast_utils_path <- fs::path(hub_tools_dir, "forecast_utils.R")

# Importa funzioni ausiliarie
source(forecast_utils_path)



# List all models and weeks

models <- list_model_names(previsioni_dir = "data/previsioni")
weeks <- get_season_weeks("2024-2025", supporting_dir = "data/supporting-files")

# Import forecasts
forecasts <- read_all_forecasts(models, weeks, previsioni_dir = "data/previsioni")

# Import actual data
ili_latest <- read_all_actuals("2024-2025", "ILI", regions, sorveglianza_dir = "data/sorveglianza")
ili_plusA_latest <- read_all_actuals("2024-2025", "ILI+_FLU_A", regions, sorveglianza_dir = "data/sorveglianza")
ili_plusB_latest <- read_all_actuals("2024-2025", "ILI+_FLU_B", regions, sorveglianza_dir = "data/sorveglianza")
target_data <- rbind(ili_latest, ili_plusA_latest, ili_plusB_latest)

# Merge forecasts and actual data
merged <- merge_forecast_actuals(forecasts, target_data)

# Read exceptions and exclude them from the merged dataframe (forecast_unit are lists)
keys <- c("target", "location", "horizon_end_date", "horizon", "model", "forecast_week")

exceptions_path = file.path("configs", "exceptions.csv")
if (file.exists(exceptions_path)) {
  message(sprintf("Leggo exceptions da: %s", exceptions_path))
  exceptions <- read.csv(exceptions_path, stringsAsFactors = FALSE, check.names = FALSE)
} else {
  warning(sprintf("File exceptions NON trovato: %s — procedo senza.", exceptions_path))
  exceptions <- NULL
}
# exceptions <- read.csv("exceptions.csv", stringsAsFactors = FALSE)
# Make types consistent with merged
exceptions <- exceptions %>%
  mutate(
    horizon_end_date = as.Date(horizon_end_date)
  )
exceptions <- distinct(exceptions, across(all_of(keys)))
merged_filtered <- merged %>%
  anti_join(exceptions, by = keys)

# Convert to forecast_quantile object
forecast_quantile <- merged_filtered |>
  as_forecast_quantile(
    forecast_unit = c(
      "target", "location", "horizon_end_date", "horizon", "model", "forecast_week"    
    )
  )

# Compute scores
scores <- forecast_quantile |>
  score()

# Compute relative scores
baseline_name <- "Influcast-quantileBaseline"
keys <- c("target", "location", "horizon_end_date", "horizon", "forecast_week")
baseline <- scores %>%
  filter(model == baseline_name) %>%
  select(all_of(keys), wis_baseline = wis, ae_median_baseline = ae_median)

scores_rel <- scores %>%
  left_join(baseline, by = keys) %>%
  mutate(
    rel_wis = ifelse(is.finite(wis_baseline) & wis_baseline != 0, wis / wis_baseline, NA_real_),
    rel_ae_median = ifelse(is.finite(ae_median_baseline) & ae_median_baseline != 0, ae_median / ae_median_baseline, NA_real_)
  )

# Save scores
scores_out <- subset(scores_rel, select = -c(wis_baseline, ae_median_baseline))
write.csv(scores_out, "scores.csv", row.names = FALSE)

# Aggregate scores by model, target, location
#scores_aggregated <- scores |>
#  summarise_scores(by = c("model", "target", "location"))
#head(scores_aggregated)
#write.csv(scores_aggregated, "scores_aggregated.csv", row.names = FALSE)
