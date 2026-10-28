from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

def search_neptun(product_name):
    driver = webdriver.Chrome()
    wait = WebDriverWait(driver, 30)
    product_details = {}

    try:
        driver.get("https://www.neptun.al/")

        search_bar = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[placeholder="Kërko"]')))
        search_bar.clear()
        search_bar.send_keys(product_name)
        search_bar.send_keys(Keys.RETURN)

        product_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.product-list-item-grid')))
        matching_products = []

        for idx, product in enumerate(product_elements, start=1):
            try:
                title_element = product.find_element(By.CSS_SELECTOR, 'h2.product-list-item__content--title')
                price_element = product.find_element(By.CSS_SELECTOR, '.product-price__amount--value')
                currency_element = product.find_element(By.CSS_SELECTOR, '.product-price__amount--currency')

                title = title_element.text.strip()
                price = price_element.text.strip()
                currency = currency_element.text.strip()

                href = product.find_element(By.TAG_NAME, 'a').get_attribute('href')

                if product_name.lower() in title.lower():
                    matching_products.append((title, float(price.replace('L', '').replace('.', '').strip()), href))
                    product_details[idx] = (title, float(price.replace('L', '').replace('.', '').strip()), href)
            except NoSuchElementException:
                continue

        if not matching_products:
            print(f"No matching products found for '{product_name}' on Neptun.")
            driver.quit()
            return None, None

        if len(matching_products) == 1:
            selected_title, selected_price, product_url = product_details[1]
            driver.get(product_url)
            time.sleep(5)
            driver.quit()
            return selected_price, product_url
        else:
            print(f"Available products in Neptun for {product_name}:")
            for idx, (title, price, href) in enumerate(matching_products, start=1):
                print(f"{idx}. {title}")
            print("0. No result matches your product, exit website")

            while True:
                try:
                    selection = int(input("Enter the number corresponding to the product you want to view: "))
                    if selection == 0:
                        print(f"No matching products found for '{product_name} on Neptun")
                        driver.quit()
                        return None, None
                    elif selection in product_details:
                        break
                    else:
                        print("Invalid selection. Please enter a valid number.")
                except ValueError:
                    print("Invalid input. Please enter a number.")

            selected_title, selected_price, product_url = product_details[selection]
            driver.get(product_url)
            time.sleep(5)
            driver.quit()
            return selected_price, product_url

    except TimeoutException:
        print(f"Timeout occurred while searching for '{product_name}' on Neptun.")
        driver.quit()
        return None, None
