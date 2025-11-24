#install.packages("scoringutils")
library(scoringutils)
library(dplyr)
# source("forecast_utils.R")


# Add parameters for previsioni_dir, supporting_dir, sorveglianza_dir
regions_list <- c(italia = "IT",
             abruzzo = "01",
             basilicata = "02",
             calabria = "03",
             campania = "04",
             emilia_romagna = "05",
             friuli_venezia_giulia = "06",
             lazio = "07",
             liguria = "08",
             lombardia = "09",
             marche = "10",
             molise = "11",
             pa_bolzano = "12",
             pa_trento = "13",
             piemonte = "14",
             puglia = "15",
             sardegna = "16",
             sicilia = "17",
             toscana = "18",
             umbria = "19",
             valle_d_aosta = "20",
             veneto = "21")


# ---- Imposta working directory robusto ----
suppressMessages({
  if (!requireNamespace("fs", quietly = TRUE)) install.packages("fs")
  if (!requireNamespace("here", quietly = TRUE)) install.packages("here")
  if (!requireNamespace("optparse", quietly = TRUE)) install.packages("optparse")
  library(fs)
  library(here)
  library(optparse)
})


# Legge i parametri di lancio
option_list <- list(
  make_option("--forecasts", type = "character", help = "Directory delle previsioni"),
  make_option("--surveillance", type = "character", help = "Directory della sorveglianza"),
  make_option("--support", type = "character", help = "Directory dei file di support"),
  make_option("--exceptions", type = "character", help = "File CSV delle eccezioni"),
  make_option("--out", type = "character", default = "scores.csv", help = "File di output")
)

opt <- parse_args(OptionParser(option_list = option_list))

# Variabili usate poi nello script
forecasts_dir     <- opt$forecasts
surveillance_dir  <- opt$surveillance
support_dir       <- opt$support
exceptions_file   <- opt$exceptions
out_file          <- opt$out

message("== Parametri ricevuti ==")
message("Forecasts:     ", forecasts_dir)
message("Sorveglianza:  ", surveillance_dir)
message("Supporto:      ", support_dir)
message("Eccezioni:     ", exceptions_file)
message("Output:        ", out_file)


# Rileva automaticamente la root del repo corrente (InflucastEval)
root <- here::here()
cat(sprintf("Working directory base: %s\n", root))

# Costruisci percorsi relativi ai repository coinvolti
hub_tools_dir <- fs::path(root, "hub-tools", "r_code")
forecast_utils_path <- fs::path(hub_tools_dir, "forecast_utils.R")

# Importa funzioni ausiliarie
source(forecast_utils_path)



# List all models and weeks

models <- list_model_names(previsioni_dir = forecasts_dir)
weeks <- get_season_weeks("2025-2026", supporting_dir = support_dir)

# Import forecasts
forecasts <- read_all_forecasts(models, weeks, previsioni_dir = forecasts_dir)

# Import actual data
ari_latest <- read_all_actuals("2025-2026", "ARI", regions = regions_list, sorveglianza_dir = surveillance_dir)
ari_plusA_latest <- read_all_actuals("2025-2026", "ARI+_FLU_A", regions = regions_list, sorveglianza_dir = surveillance_dir)
ari_plusB_latest <- read_all_actuals("2025-2026", "ARI+_FLU_B", regions = regions_list, sorveglianza_dir = surveillance_dir)
target_data <- rbind(ari_latest, ari_plusA_latest, ari_plusB_latest)

# Merge forecasts and actual data
merged <- merge_forecast_actuals(forecasts, target_data)

# Read exceptions and exclude them from the merged dataframe (forecast_unit are lists)
keys <- c("target", "location", "horizon_end_date", "horizon", "model", "forecast_week")

exceptions_path = exceptions_file
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
write.csv(scores_out, out_file, row.names = FALSE)
# Aggregate scores by model, target, location
#scores_aggregated <- scores |>
#  summarise_scores(by = c("model", "target", "location"))
#head(scores_aggregated)
#write.csv(scores_aggregated, "scores_aggregated.csv", row.names = FALSE)
