# PricePal

The PricePal is a Python-based tool designed to track and compare product prices across multiple e-commerce websites. By periodically querying selected websites, the bot collects price data for specified products and saves this information to a CSV file. Users can then visualize price trends over time, identify price drops, and compare current prices across different platforms through interactive plots generated using Seaborn and Matplotlib libraries.

# TECHNOLOGY

# Programming Language

Python: 

The core programming language used for developing the application.

# Web Scraping

BeautifulSoup: A Python library used to parse HTML and XML documents for web scraping.

Requests: A simple HTTP library for making requests to fetch web pages.

Selenium WebDriver: A browser automation tool used for web scraping dynamic content that requires JavaScript execution.

# Data Processing and Analysis

Pandas: A powerful data manipulation and analysis library used for handling tabular data.

Datetime: A module for manipulating dates and times, essential for timestamping price data.

# Data Visualization

Matplotlib: A plotting library used for creating static, animated, and interactive visualizations in Python.

Seaborn: A statistical data visualization library based on Matplotlib, used for creating visually appealing and informative plots.

# User Interface

Command Line Interface (CLI): The primary user interface for interacting with the application.

# Data Storage

CSV (Comma-Separated Values): A simple file format used to store tabular data in plain text form. The project's price history data is stored in a CSV file.

# Miscellaneous

OS Module: Used for interacting with the operating system, particularly for checking file existence.

Collections: Specifically, the defaultdict from the collections module, used for handling missing keys in dictionaries.

# Project-Specific Modules

shpresa.py: Contains functions for scraping product data from the Shpresa website.

fejzo.py: Contains functions for scraping product data from the 3vFejzo website.

neptun.py: Contains functions for scraping product data from the Neptun website.

# Key Functions and Features

Product Search: Allows users to search for a product across three different websites.

Price Comparison: Compares the price of a product across the three websites and identifies the cheapest and most expensive options.

Price History: Displays the historical price data of a product over time, with visualizations.

Language Translation: Provides basic translations between English and Spanish.

Data Saving: Saves the search results and price history data to a CSV file.

# Visualization Enhancements

# Interactive Plots: 

Implemented using Matplotlib and Seaborn to provide dynamic and interactive visualizations.

# Annotations: 

Added to the plots to highlight significant price changes and drops.

# Web Scraping Details:

Static Content: Scraped using BeautifulSoup and Requests for straightforward HTML content.

Dynamic Content: Handled using Selenium WebDriver to automate browsers and scrape content that requires JavaScript execution to load fully.
