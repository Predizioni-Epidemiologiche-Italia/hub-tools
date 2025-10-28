regions <- c(italia = "IT",
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


# Build the absolute path to a forecast CSV under Influcast-main/previsioni
build_forecast_path <- function(model_name,
                                forecast_week,
                                previsioni_dir = "Influcast-main/previsioni") {
  if (is.null(model_name) || model_name == "") stop("model_name must be provided")
  if (is.null(forecast_week) || forecast_week == "") stop("forecast_week must be provided")

  if (!grepl("^[0-9]{4}_[0-9]{2}$", forecast_week)) {
    stop("forecast_week must be in 'YYYY_WW' format, e.g. '2025_10'")
  }

  parts <- strsplit(forecast_week, "_")[[1]]
  week_num <- as.integer(parts[2])
  if (is.na(week_num) || week_num < 1 || week_num > 53) {
    stop("Week component must be between 01 and 53")
  }

  return(file.path(previsioni_dir, model_name, paste0(forecast_week, ".csv"))) 
}

# Compute the Sunday (week end) date of an ISO week given year and week
iso_week_sunday <- function(year, week) {
  y <- as.integer(year)
  w <- as.integer(week)
  jan4 <- as.Date(sprintf("%04d-01-04", y))
  wday <- as.POSIXlt(jan4)$wday  # 0=Sun .. 6=Sat
  monday_week1 <- jan4 - ((wday + 6) %% 7)
  monday_target <- monday_week1 + 7L * (w - 1L)
  return(monday_target + 6L)
}

# Read a forecast CSV for a given model and epidemiological week
read_forecast <- function(model_name, forecast_week,
                          previsioni_dir = "Influcast-main/previsioni",
                          ...) {
  model_dir <- file.path(previsioni_dir, model_name)
  if (!dir.exists(model_dir)) {
    stop(sprintf("Model directory not found: %s", model_dir))
  }

  csv_path <- build_forecast_path(model_name, forecast_week, previsioni_dir)
  if (!file.exists(csv_path)) {
    stop(sprintf("Forecast file not found for %s: %s", forecast_week, csv_path))
  }

  df <- utils::read.csv(csv_path, stringsAsFactors = FALSE, check.names = FALSE, ...)
  # Add horizon_end_date: Sunday of ISO week (anno, settimana) plus orizzonte weeks
  if (all(c("anno", "settimana", "orizzonte") %in% names(df))) {
    sundays <- iso_week_sunday(df$anno, df$settimana)
    df$horizon_end_date <- as.Date(sundays) + (as.integer(df$orizzonte) * 7L)
  }
  return(df)
}

# Merge forecast and actual data on target, luogo, and horizon_end_date
merge_forecast_actuals <- function(forecast_df, actual_df, allowed_horizons = c(1, 2, 3, 4)) {
  if (missing(forecast_df) || missing(actual_df)) {
    stop("Both forecast_df and actual_df must be provided")
  }

  # Ensure horizon_end_date is Date in both
  if ("horizon_end_date" %in% names(forecast_df)) {
    forecast_df$horizon_end_date <- as.Date(forecast_df$horizon_end_date)
  }
  if ("horizon_end_date" %in% names(actual_df)) {
    actual_df$horizon_end_date <- as.Date(actual_df$horizon_end_date)
  }

  # Optionally filter forecast by allowed horizons (uses column 'orizzonte')
  if ("orizzonte" %in% names(forecast_df)) {
    forecast_df <- forecast_df[as.integer(forecast_df$orizzonte) %in% as.integer(allowed_horizons), , drop = FALSE]
  }

  # Select columns to keep
  keep_actual <- c("target", "luogo", "incidenza", "horizon_end_date")
  keep_actual <- keep_actual[keep_actual %in% names(actual_df)]
  actual_sel <- actual_df[, keep_actual, drop = FALSE]

  keep_forecast <- c(
    "luogo", "tipo_valore", "id_valore", "orizzonte", "valore",
    "target", "horizon_end_date", "model_name", "forecast_week"
  )
  keep_forecast <- keep_forecast[keep_forecast %in% names(forecast_df)]
  forecast_sel <- forecast_df[, keep_forecast, drop = FALSE]

  # Merge (inner join) on keys
  keys <- c("target", "luogo", "horizon_end_date")
  keys <- keys[keys %in% intersect(names(forecast_sel), names(actual_sel))]
  if (length(keys) < 3) {
    stop("Merge keys missing in inputs. Required: target, luogo, horizon_end_date")
  }

  merged <- merge(forecast_sel, actual_sel, by = keys, all = FALSE)
  # Rename columns as requested for scoringutils
  renames <- c(incidenza = "observed", valore = "predicted", 
               id_valore = "quantile_level", orizzonte = "horizon", 
               luogo = "location", model_name = "model")
  for (col in names(renames)) {
    if (col %in% names(merged)) {
      names(merged)[names(merged) == col] <- renames[col]
    }
  }

  # Drop optional raw count columns if present
  drop_cols <- c("tipo_valore")
  keep_names <- setdiff(names(merged), intersect(names(merged), drop_cols))
  merged <- merged[, keep_names, drop = FALSE]

  return(merged)
}

# Read and concatenate actual surveillance data for all regions
read_all_actuals <- function(season,
                             target,
                             regions,
                             week = NULL,
                             sorveglianza_dir = "Influcast-main/sorveglianza",
                             ...) {
  if (is.null(season) || season == "") stop("season must be provided, e.g. '2025-2026'")
  if (is.null(target) || target == "") stop("target must be provided, e.g. 'ARI'")
  if (is.null(regions) || is.null(names(regions)) || length(regions) == 0) {
    stop("regions must be a non-empty named list/vector")
  }

  results <- list()
  idx <- 1L
  for (reg in names(regions)) {
    df <- try({
      read_actual_data(
        season = season,
        target = target,
        region = reg,
        week = week,
        regions = regions,
        sorveglianza_dir = sorveglianza_dir,
        ...
      )
    }, silent = TRUE)

    if (inherits(df, "try-error")) {
      message(sprintf("Skipping region due to read error: %s", reg))
      next
    }

    results[[idx]] <- df
    idx <- idx + 1L
  }

  if (length(results) == 0) return(data.frame())

  out <- do.call(rbind, results)
  rownames(out) <- NULL
  if (all(c("anno", "settimana") %in% names(out))) {
    out$anno_settimana <- sprintf("%s_%02d", out$anno, as.integer(out$settimana))
  }
  return(out)
}

# List available model names under the previsioni directory
list_model_names <- function(previsioni_dir = "Influcast-main/previsioni") {
  if (!dir.exists(previsioni_dir)) {
    stop(sprintf("previsioni_dir not found: %s", previsioni_dir))
  }

  entries <- list.files(previsioni_dir, all.files = FALSE, no.. = TRUE)
  if (length(entries) == 0) return(character(0))

  model_paths <- file.path(previsioni_dir, entries)
  models <- entries[dir.exists(model_paths)]
  return(unname(sort(models)))
}

# Read forecasting weeks for a given season and return as "YYYY-MM"
get_season_weeks <- function(season,
                             supporting_dir = "Influcast-main/supporting-files",
                             csv_name = "forecasting_weeks.csv") {
  if (is.null(season) || season == "") stop("season must be provided, e.g. '2025-2026'")

  csv_path <- file.path(supporting_dir, csv_name)
  if (!file.exists(csv_path)) {
    stop(sprintf("forecasting_weeks file not found: %s", csv_path))
  }

  fw <- utils::read.csv(csv_path, stringsAsFactors = FALSE, check.names = FALSE)

  fw_season <- fw[fw$season == season & fw$horizon == 0, c("year", "week")]
  if (nrow(fw_season) == 0) return(character(0))

  ord <- order(fw_season$year, fw_season$week)
  fw_season <- fw_season[ord, , drop = FALSE]

  return(sprintf("%d_%02d", fw_season$year, fw_season$week))
}

# Read and concatenate forecasts for all combinations of models and weeks
read_all_forecasts <- function(models,
                               weeks,
                               previsioni_dir = "Influcast-main/previsioni",
                               ...) {
  if (missing(models) || length(models) == 0) stop("models must be a non-empty character vector")
  if (missing(weeks) || length(weeks) == 0) stop("weeks must be a non-empty character vector like 'YYYY_WW'")

  result_list <- list()
  idx <- 1L

  for (model in models) {
    for (wk in weeks) {
      # Attempt to read; skip missing with a message
      df <- try({
        read_forecast(model, wk, previsioni_dir = previsioni_dir, ...)
      }, silent = TRUE)

      if (inherits(df, "try-error")) {
        message(sprintf("Skipping missing or unreadable forecast: model=%s, week=%s", model, wk))
        next
      }

      df$model_name <- model
      df$forecast_week <- wk
      result_list[[idx]] <- df
      idx <- idx + 1L
    }
  }

  if (length(result_list) == 0) return(data.frame())

  # Concatenate; ensure row names are reset
  out <- do.call(rbind, result_list)
  rownames(out) <- NULL
  return(out)
}

# Read actual surveillance data for a given target/season/region, optionally a week
read_actual_data <- function(season,
                             target,
                             region,
                             week = NULL,
                             regions = NULL,
                             sorveglianza_dir = "Influcast-main/sorveglianza",
                             ...) {
  if (is.null(season) || season == "") stop("season must be provided, e.g. '2025-2026'")
  if (is.null(target) || target == "") stop("target must be provided, e.g. 'ARI'")
  if (is.null(region) || region == "") stop("region must be provided, e.g. 'italia' or 'lombardia'")

  # For ARI+ targets, files live under folder 'ARI+_FLU' and filenames include
  # the full target (ARI+_FLU_Aor ARI+_FLU_B). For others, folder == target.
  folder_target <- if (grepl("^ARI\\+_FLU", target)) "ARI+_FLU" else target
  filename_target <- target

  base_dir <- file.path(sorveglianza_dir, folder_target, season)
  if (!dir.exists(base_dir)) {
    stop(sprintf("Directory not found: %s", base_dir))
  }

  # Build simple filters for filename matching (case-sensitive, fixed strings)
  week_str <- if (!is.null(week) && week != "") week else NULL

  # Gather candidate files
  search_root <- base_dir
  if (is.null(week) || week == "") {
    # Use latest folder when no week specified if it exists
    latest_dir <- file.path(base_dir, "latest")
    if (dir.exists(latest_dir)) search_root <- latest_dir
  }

  files <- list.files(search_root, pattern = "\\.csv$", recursive = TRUE, full.names = TRUE)
  if (length(files) == 0) {
    stop(sprintf("No CSV files found under: %s", search_root))
  }

  # Filter by region and optional week and target name within filename
  name_vec <- basename(files)
  keep <- grepl(region, name_vec, fixed = TRUE)
  keep <- keep & grepl(filename_target, name_vec, fixed = TRUE)
  if (!is.null(week_str)) {
    keep <- keep & grepl(week_str, name_vec, fixed = TRUE)
  } else {
    # Prefer names containing 'latest' when week is not specified
    # but don't require it (fallback to any match)
    latest_mask <- grepl("latest", name_vec, fixed = TRUE)
    if (any(keep & latest_mask)) {
      keep <- keep & latest_mask
    }
  }

  candidates <- files[keep]
  if (length(candidates) == 0) {
    stop(sprintf("No matching files for season=%s, target=%s, region=%s%s",
                 season, target, region,
                 if (!is.null(week_str)) sprintf(", week=%s", week) else ""))
  }

  # If multiple candidates, pick the most recently modified
  if (length(candidates) > 1) {
    info <- file.info(candidates)
    candidates <- candidates[order(info$mtime, decreasing = TRUE)]
  }

  csv_path <- candidates[[1]]
  df <- utils::read.csv(csv_path, stringsAsFactors = FALSE, check.names = FALSE, ...)

  # Drop optional raw count columns if present
  drop_cols <- c("numero_casi", "numero_assistiti")
  keep_names <- setdiff(names(df), intersect(names(df), drop_cols))
  df <- df[, keep_names, drop = FALSE]

  # Add luogo from regions named list
  if (is.null(regions) || is.null(names(regions)) || is.null(regions[[region]])) {
    stop("'regions' must be a named list/vector and contain an entry for the provided region")
  }
  df$luogo <- regions[[region]]

  # Add week end date (Sunday of ISO week anno/settimana)
  if (all(c("anno", "settimana") %in% names(df))) {
    df$horizon_end_date <- as.Date(iso_week_sunday(df$anno, df$settimana))
  }
  return(df)
}