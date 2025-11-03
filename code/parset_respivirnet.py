## Parser for Epicentro ISS Surveillance Report
# This script extracts data from the Italian health authority (ISS) surveillance report for respiratory infections.

import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import os
from urllib.parse import urljoin

# Region names as they appear in the data vs the names used in Influcast
region_names = {'Piemonte': "piemonte", 
                "Valle d'Aosta/Vallée d'Aoste": 'valle_d_aosta', 
                'Lombardia': 'lombardia', 
                'Provincia Autonoma di Bolzano/Bozen': 'pa_bolzano', 
                'Provincia Autonoma di Trento': 'pa_trento',
                'Veneto': 'veneto', 
                'Friuli-Venezia Giulia': 'friuli_venezia_giulia', 
                'Liguria': 'liguria', 
                'Emilia-Romagna': 'emilia_romagna',
                'Toscana': 'toscana', 
                'Umbria': 'umbria', 
                'Marche': 'marche', 
                'Lazio': 'lazio', 
                'Abruzzo': 'abruzzo', 
                'Molise': 'molise',
                'Campania': 'campania', 
                'Puglia': 'puglia', 
                'Basilicata': 'basilicata', 
                'Calabria': 'calabria', 
                'Sicilia': 'sicilia',
                'Sardegna': 'sardegna'}

# Base URL for the surveillance report
BASE_URL = "https://www.epicentro.iss.it/sorveglianza-infezioni-respiratorie-acute/rapporto/rapporto.html"
season = "2025-2026" ## TODO: change to argument passed to the script

## Functions
def extract_week_info(soup):
    """Extract week number from the page (format: YYYY-WW)"""
    # Look for week pattern in headings
    headings = soup.find_all(['h2', 'h3', 'h4'])
    week_pattern = re.compile(r'(\d{4})-(\d{1,2})')
    
    for heading in headings:
        text = heading.get_text(strip=True)
        if 'settimana' in text.lower() or 'week' in text.lower():
            match = week_pattern.search(text)
            if match:
                year, week = match.groups()
                week = int(week)
                return f"{year}_{week:02d}", year, week

    return None, None, None


def extract_all_tables(soup):
    """Extract all tables from the page"""
    tables = soup.find_all('table')
    all_dfs = []
    
    for i, table in enumerate(tables):
        try:
            html_str = str(table)
            dfs = pd.read_html(html_str, thousands='.', decimal=',')
            if dfs:
                df = dfs[0]
                df['table_index'] = i
                all_dfs.append(df)
        except Exception as e:
            print(f"Could not parse table {i}: {e}")
            continue
    
    return all_dfs


def parse_italy_data(ari_ita, population_ita):
    """"Parses the Italy data from the ARI and population tables"""
    anno, settimana, numero_casi, numero_assistiti, incidenza = [], [], [], [], []
    for _, row in ari_ita.iterrows(): 
        year_week = row["Settimana"]["Settimana"]
        anno.append(year_week.split("-")[0])
        settimana.append(year_week.split("-")[1])
        numero_casi.append(row["Totale Casi"]["Totale Casi"])
        incidenza.append(row["Totale Incidenza"]["Totale Incidenza"])
        numero_assistiti.append(population_ita.loc[population_ita.Settimana == year_week]["Totale"].values[0])

    df_italy = pd.DataFrame({"anno": anno, 
                            "settimana": settimana, 
                            "numero_casi": numero_casi, 
                            "numero_assistiti": numero_assistiti, 
                            "incidenza": incidenza})
    df_italy["target"] = "ARI"
    return df_italy


def parse_regions_data(regions_table, regions_population):
    """Parses the regions data from the regions table and the regions population table"""
    regions_dfs = {}
    for _, row in regions_table.iterrows():
        # create df for this region
        region = region_names[row["Regione-PA"]["Regione-PA"]]
        year_week = row["Settimana"]["Settimana"]
        
        df_region = pd.DataFrame({"anno": [year_week.split("-")[0]], 
                                "settimana": [year_week.split("-")[1]], 
                                "numero_casi": [row["Totale Casi"]["Totale Casi"]], 
                                "incidenza": [row["Totale Incidenza"]["Totale Incidenza"]]})
        df_region["numero_assistiti"] = regions_population.loc[regions_population["Regione-PA"] == row["Regione-PA"]["Regione-PA"]]["Totale Assistiti"].values[0]
        df_region["target"] = "ARI"
        regions_dfs[region] = df_region
    return regions_dfs


def get_latest_week(path, target, season, region="italia"):
    """Get the latest week for a given target, season and region"""
    complete_path = os.path.join(path, season, "latest", f"{region}-latest-{target}.csv")
    if not os.path.exists(complete_path):
        return None
    df_latest = pd.read_csv(complete_path)
    df_latest["year_week"] = df_latest["anno"].astype(str) + "_" + df_latest["settimana"].astype(str).str.zfill(2)
    return df_latest.year_week.max()


def compute_ari_plus_df(df_italy, df_flu_viruses, df_other_viruses, influenza_strain, target_name): 
    """Computes the ARI+FLU_A/B data from the ARI and the flu viruses data"""
    anno, settimana, incidenza = [], [], []
    for _, row in df_italy.iterrows():
        week = row["settimana"]

        # get Flu total positives
        flu_total = df_flu_viruses.loc[df_flu_viruses["Unnamed: 0"] == "Totale"][week].values[0]

        # get other viruses total positives
        other_viruses_total = df_other_viruses.loc[df_other_viruses["Unnamed: 0"] == "Totale"][week].values[0]

        # get total positives
        total_positives = flu_total + other_viruses_total

        # get influenza strain positives
        flu_strain_positives = df_flu_viruses.loc[df_flu_viruses["Unnamed: 0"] == influenza_strain][week].values[0]

        # get positivity rate
        positivity_rate = flu_strain_positives / total_positives

        anno.append(row["anno"])
        settimana.append(week)
        incidenza.append(row["incidenza"] * positivity_rate)

    df_ari_plus = pd.DataFrame({"anno": anno, "settimana": settimana, "incidenza": incidenza})
    df_ari_plus["target"] = target_name
    return df_ari_plus

# TODO: Add argument parser
# TODO: Fix all paths
# TODO: Possibily move all functions to a separate file
if __name__ == "__main__":
    print("Fetching data...")
    response = requests.get(BASE_URL)
    print("Data fetched")

    # Parse HTML
    soup = BeautifulSoup(response.content, 'html.parser')

    # Extract week info
    week_id, year, week = extract_week_info(soup)
    print(f"Extracted week info: {week_id} (Year: {year}, Week: {week})")

    # Get latest week
    latest_week = get_latest_week("./Influcast-main/sorveglianza/ARI/", "ARI", season)

    if latest_week is not None or latest_week != week_id:

        # Extract all tables
        all_dataframes = extract_all_tables(soup)
        print(f"Extracted {len(all_dataframes)} tables")

        # Parse Italy data (ARI)
        ari_ita, population_ita = all_dataframes[0], all_dataframes[3]
        df_italy = parse_italy_data(ari_ita, population_ita)

        # Save Italy data (ARI)
        df_italy.to_csv("./Influcast-main/sorveglianza/ARI/{}/{}-{}-ARI.csv".format(season,"italia", week_id), index=False)
        df_italy.to_csv("./Influcast-main/sorveglianza/ARI/{}/latest/italia-latest-ARI.csv".format(season), index=False)

        # Parse regions data
        regions_table, regions_population = all_dataframes[1], all_dataframes[4]
        regions_dfs = parse_regions_data(regions_table, regions_population)

        # Save regions data (ARI)
        for region, df_region in regions_dfs.items():
            latest_file_path = "./Influcast-main/sorveglianza/ARI/{}/latest/{}-latest-ARI.csv".format(season, region)
            if os.path.exists(latest_file_path):
                # Import latest file for this region 
                df_latest_region = pd.read_csv(latest_file_path)
                # Concatenate the two dataframes
                df_latest_region = pd.concat([df_latest_region, df_region], ignore_index=True)
                # Save week and latest file
            else: 
                df_latest_region = df_region
            df_latest_region.to_csv("./Influcast-main/sorveglianza/ARI/{}/latest/{}-latest-ARI.csv".format(season, region), index=False)
            df_latest_region.to_csv("./Influcast-main/sorveglianza/ARI/{}/{}-{}-ARI.csv".format(season, region, week_id), index=False)

        # Compute ARI+FLU_A/B data
        df_flu_viruses, df_other_viruses = all_dataframes[5], all_dataframes[6]
        df_ari_plus_A = compute_ari_plus_df(df_italy, df_flu_viruses, df_other_viruses, "Influenza A", "ARI+_FLU_A")
        df_ari_plus_B = compute_ari_plus_df(df_italy, df_flu_viruses, df_other_viruses, "Influenza B", "ARI+_FLU_B")

        # Save ARI+FLU_A/B data
        df_ari_plus_A.to_csv("./Influcast-main/sorveglianza/ARI+_FLU/{}/{}-{}-ARI+_FLU_A.csv".format(season, "italia", week_id), index=False)
        df_ari_plus_A.to_csv("./Influcast-main/sorveglianza/ARI+_FLU/{}/latest/italia-latest-ARI+_FLU_A.csv".format(season), index=False)
        df_ari_plus_B.to_csv("./Influcast-main/sorveglianza/ARI+_FLU/{}/{}-{}-ARI+_FLU_B.csv".format(season, "italia", week_id), index=False)
        df_ari_plus_B.to_csv("./Influcast-main/sorveglianza/ARI+_FLU/{}/latest/italia-latest-ARI+_FLU_B.csv".format(season), index=False)

