# PricePal

The PricePal is a Python-based tool designed to track and compare product prices across multiple e-commerce websites. By periodically querying selected websites, the bot collects price data for specified products and saves this information to a CSV file. Users can then visualize price trends over time, identify price drops, and compare current prices across different platforms through interactive plots generated using Seaborn and Matplotlib libraries.

# FEATURES

# Search Products:

Query specific products on multiple e-commerce websites (Shpresa, 3vFejzo, Neptun).
Retrieve the current price and URL for each product.

# Price Comparison:


Compare prices for a given product across different websites.
Identify the cheapest and most expensive prices.


# Price History Visualization:


Generate line plots to visualize the price history of selected products.
Highlight significant price drops over time.
Create bar plots to compare the latest prices across websites.


# Data Storage:


Save collected price data to a CSV file.
Load and process historical data for visualization.


# Interactive Console Interface:


User-friendly menu for interacting with the bot.
Options to search products, compare prices, visualize price history, and change the language.


# Modules and Libraries

# CSV: 
For reading and writing price data.


# OS: 
To check file existence.

# Datetime: 
For timestamping collected data.

# Matplotlib & Seaborn: 
For creating visual plots.

# Pandas: 
For data manipulation and analysis.

Shpresa, 3vFejzo, Neptun: Custom modules for querying respective websites.
