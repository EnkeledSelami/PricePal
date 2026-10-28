import csv
import os
import sys
from datetime import datetime
import matplotlib.pyplot as plt
from collections import defaultdict
import pandas as pd
import seaborn as sns

from shpresa import search_shpresa
from fejzo import search_3vfejzo
from neptun import search_neptun

CSV_COLUMNS = ["Site", "Product Name", "Price (Lekë)", "URL", "Date", "Time"]
SEARCHERS = {
    '1': ('Shpresa', search_shpresa),
    '2': ('3vFejzo', search_3vfejzo),
    '3': ('Neptun', search_neptun),
}


def make_result(site, product_name, price, url):
    now = datetime.now()
    return (site, product_name, int(round(float(price))), url,
            now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S"))


def run_search(site, searcher, product_name, product_selector=None):
    """Isolate failures so an unavailable shop does not stop other searches."""
    product_name = product_name.strip()
    try:
        price, url = searcher(product_name, product_selector=product_selector)
        if price is None or not url:
            return None
        return make_result(site, product_name, price, url)
    except Exception as exc:
        print(f"Search failed on {site}: {exc}")
        return None


def save_results_to_file(results, filename='PriceHistory.csv'):
    write_header = not os.path.exists(filename) or os.path.getsize(filename) == 0
    with open(filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if write_header:
            writer.writerow(CSV_COLUMNS)
        writer.writerows(results)

def search_product_price(product_name, product_selector=None):
    results = []
    for site, searcher in SEARCHERS.values():
        result = run_search(site, searcher, product_name, product_selector=product_selector)
        if result:
            results.append(result)

    if not results:
        print(f"No matching products found for '{product_name}' on any site.")
        return []

    cheapest_site = min(results, key=lambda x: x[2])
    most_expensive_site = max(results, key=lambda x: x[2])
    print(f"The cheapest price for {product_name} is {cheapest_site[2]} Lekë on {cheapest_site[0]}: {cheapest_site[3]}")
    print(f"The most expensive price for {product_name} is {most_expensive_site[2]} Lekë on {most_expensive_site[0]}: {most_expensive_site[3]}")
    return results

def plot_price_history(product_data):
    product_name = product_data[0][1]
    df = pd.DataFrame(product_data, columns=["Site", "Product Name", "Price (Lekë)", "URL", "Date", "Time"])
    df['Price (Lekë)'] = pd.to_numeric(df['Price (Lekë)'], errors='coerce')
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.dropna(subset=['Price (Lekë)', 'Date'])
    if df.empty:
        print(f"No valid price history found for '{product_name}'.")
        return
    df = df.sort_values(by='Date')

    plt.figure(figsize=(12, 6))

    plt.subplot(1, 2, 1)
    sns.lineplot(data=df, x='Date', y='Price (Lekë)', marker='o', hue='Site', palette='tab10')
    plt.title(f'Price History for {product_name}')
    plt.xlabel('Date')
    plt.ylabel('Price (Lekë)')
    plt.grid(True)
    plt.xticks(rotation=45)

    for site in df['Site'].unique():
        site_df = df[df['Site'] == site]
        for i in range(1, len(site_df)):
            if site_df.iloc[i]['Price (Lekë)'] < site_df.iloc[i-1]['Price (Lekë)']:
                plt.annotate(f'Drop to {site_df.iloc[i]["Price (Lekë)"]} Lekë',
                             (site_df.iloc[i]['Date'], site_df.iloc[i]['Price (Lekë)']),
                             textcoords="offset points", xytext=(0, -15), ha='center', color='red')

    plt.subplot(1, 2, 2)
    # Use the most recent saved observation per store. A zero baseline keeps
    # every price visible (a truncated, inverted axis hid the lowest bar).
    latest = (df.sort_values(['Date', 'Time'])
                .groupby('Site', sort=False, as_index=False)
                .tail(1))
    bars = sns.barplot(data=latest, x='Site', y='Price (Lekë)',
                       hue='Site', palette='tab10', legend=False)
    max_price = latest['Price (Lekë)'].max()
    bars.set_ylim(0, max_price * 1.12)
    for container in bars.containers:
        bars.bar_label(container, fmt='%.0f', padding=3)
    plt.title('Latest Prices Across Websites')
    plt.xlabel('Website')
    plt.ylabel('Price (Lekë)')
    plt.grid(True)

    plt.tight_layout()
    plt.show()

def main():
    while True:
        print("Hello, how can I help you today?")
        print("1. Search products")
        print("2. Price Comparison")
        print("3. Price History")
        print("4. Language")
        print("5. Quit program")

        choice = input("Enter your choice: ")

        if choice == '1':
            product_name = input("Enter the product name you are looking for: ")
            print("In which website do you want me to look for?")
            print("1. Shpresa.al")
            print("2. 3vfejzo.al")
            print("3. Neptun.al")
            print("4. Quit Program")

            website_choice = input("Enter your choice: ")

            results = []
            if website_choice in SEARCHERS:
                site, searcher = SEARCHERS[website_choice]
                result = run_search(site, searcher, product_name)
                if result:
                    results.append(result)
                    print(f"Price: {result[2]} Lekë")
                    print(f"URL: {result[3]}")
            elif website_choice == '4':
                print("Exiting program.")
                break
            else:
                print("Invalid selection.")

            if results:
                save_choice = input("Do you want to save the results to a file? (yes/no): ").strip().lower()
                if save_choice == 'yes':
                    filename = 'PriceHistory.csv'
                    save_results_to_file(results, filename)

        elif choice == '2':
            product_name = input("Enter the product name you are looking for: ")
            results = search_product_price(product_name)
            if results:
                save_choice = input("Do you want to save the results to a file? (yes/no): ").strip().lower()
                if save_choice == 'yes':
                    filename = 'PriceHistory.csv'
                    save_results_to_file(results, filename)

        elif choice == '3':
            print("Which product data do you want to see?")
            product_data = defaultdict(list)
            product_names = []

            if not os.path.exists('PriceHistory.csv') or os.path.getsize('PriceHistory.csv') == 0:
                print("No saved price history yet. Search for a product and save the result first.")
                continue
            with open('PriceHistory.csv', mode='r', encoding='utf-8', newline='') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if all(row.get(column) for column in CSV_COLUMNS):
                        product_data[row['Product Name']].append(
                            [row[column] for column in CSV_COLUMNS]
                        )
            if not product_data:
                print("The price history file contains no usable records.")
                continue

            for index, product_name in enumerate(product_data.keys(), start=1):
                print(f"{index}. {product_name}")
                product_names.append(product_name)

            selection = input("Enter the number corresponding to the product you want to visualize: ")

            if selection.isdigit() and 1 <= int(selection) <= len(product_names):
                selected_product = product_names[int(selection) - 1]
                selected_product_data = product_data[selected_product]
                plot_price_history(selected_product_data)
            else:
                print("Invalid selection.")

        elif choice == '4':
            print("English or Spanish?")
            print("1. English")
            print("2. Spanish")
            language_choice = input("Enter your choice: ")

            if language_choice == '1':
                print("Whoever moves first buys the product.")
            elif language_choice == '2':
                print("El que se mueve primero compra el producto.")
            else:
                print("Invalid selection.")

        elif choice == '5':
            print("Exiting program.")
            break

        else:
            print("Invalid selection.")

if __name__ == "__main__":
    if "--cli" in sys.argv:
        main()
    else:
        from gui import launch_gui
        launch_gui()
