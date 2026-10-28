import csv
import os
from datetime import datetime
import matplotlib.pyplot as plt
from collections import defaultdict
import pandas as pd
import seaborn as sns

from shpresa import search_shpresa
from fejzo import search_3vfejzo
from neptun import search_neptun

def save_results_to_file(results, filename='PriceHistory.csv'):
    if not os.path.exists(filename):
        with open(filename, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["Site", "Product Name", "Price (Lekë)", "URL", "Date", "Time"])

    with open(filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        for result in results:
            writer.writerow(result)

def search_product_price(product_name):
    results = []

    shpresa_price, shpresa_url = search_shpresa(product_name)
    if shpresa_price is not None and shpresa_url is not None:
        results.append(('Shpresa', product_name, int(shpresa_price), shpresa_url, datetime.now().strftime("%Y-%m-%d"),
                        datetime.now().strftime("%H:%M:%S")))

    fejzo_price, fejzo_url = search_3vfejzo(product_name)
    if fejzo_price is not None and fejzo_url is not None:
        results.append(('3vFejzo', product_name, int(fejzo_price), fejzo_url, datetime.now().strftime("%Y-%m-%d"),
                        datetime.now().strftime("%H:%M:%S")))

    neptun_price, neptun_url = search_neptun(product_name)
    if neptun_price is not None and neptun_url is not None:
        results.append(('Neptun', product_name, int(neptun_price), neptun_url, datetime.now().strftime("%Y-%m-%d"),
                        datetime.now().strftime("%H:%M:%S")))

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
    df['Date'] = pd.to_datetime(df['Date'])
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
    unique_sites = df['Site'].unique()
    latest_prices = [df[df['Site'] == site]['Price (Lekë)'].iloc[-1] for site in unique_sites]
    sns.barplot(x=unique_sites, y=latest_prices, hue=unique_sites, palette='tab10', legend=False)
    plt.title('Latest Prices Across Websites')
    plt.xlabel('Website')
    plt.ylabel('Price (Lekë)')
    plt.grid(True)
    plt.gca().invert_yaxis()

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
            print("1. Shpres.al")
            print("2. 3vfejzo.al")
            print("3. Neptun.al")
            print("4. Quit Program")

            website_choice = input("Enter your choice: ")

            results = []
            if website_choice == '1':
                result = search_shpresa(product_name)
                if result[0] is not None:
                    results.append(('Shpresa', product_name, int(result[0]), result[1],
                                    datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S")))
                    print(f"Price: {int(result[0])} Lekë")
                    print(f"URL: {result[1]}")
            elif website_choice == '2':
                result = search_3vfejzo(product_name)
                if result[0] is not None:
                    results.append(('3vFejzo', product_name, int(result[0]), result[1],
                                    datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S")))
                    print(f"Price: {int(result[0])} Lekë")
                    print(f"URL: {result[1]}")
            elif website_choice == '3':
                result = search_neptun(product_name)
                if result[0] is not None:
                    results.append(('Neptun', product_name, int(result[0]), result[1],
                                    datetime.now().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S")))
                    print(f"Price: {int(result[0])} Lekë")
                    print(f"URL: {result[1]}")
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

            with open('PriceHistory.csv', mode='r', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader)  # Skip header
                for row in reader:
                    product_data[row[1]].append(row)

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
    main()
