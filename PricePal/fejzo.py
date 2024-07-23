from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

def search_3vfejzo(product_name):
    driver = webdriver.Chrome()
    driver.get("https://3vfejzo.al/")
    wait = WebDriverWait(driver, 30)

    try:
        try:
            cookie_banner = wait.until(EC.presence_of_element_located((By.ID, 'cookie-law-info-bar')))
            accept_button = cookie_banner.find_element(By.CSS_SELECTOR, 'a.cli_action_button.cli_accept_all_button')
            if accept_button.is_displayed():
                accept_button.click()
                time.sleep(1)
        except (TimeoutException, NoSuchElementException):
            pass

        search_icon = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.search-toggle i.icon_search')))
        search_icon.click()

        search_bar = wait.until(EC.presence_of_element_located((By.ID, 's')))
        search_bar.clear()
        search_bar.send_keys(product_name)
        search_button = wait.until(EC.element_to_be_clickable((By.ID, 'searchsubmit')))
        search_button.click()

        print(f"Available products in 3vFejzo for {product_name}:")
        matching_products = []

        product_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'h3.product-title a')))
        matching_products = [(product.text, product.get_attribute('href')) for product in product_elements if product_name.lower() in product.text.lower()]

        if not matching_products:
            print(f"No matching products found for '{product_name}' on 3vFejzo.")
            driver.quit()
            return None, None

        for idx, product in enumerate(matching_products, start=1):
            print(f"{idx}. {product[0]}")

        if len(matching_products) == 1:
            selected_product = matching_products[0]
            product_url = selected_product[1]
            driver.get(product_url)
            price_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'p.price .woocommerce-Price-amount')))
            price_text = price_element.text.replace('L', '').replace('.', '').strip()
            driver.execute_script("arguments[0].style.border='2px solid red'; arguments[0].style.padding='2px';", price_element)
            time.sleep(2)
            driver.quit()
            return float(price_text), product_url
        else:
            print("0. No result matches your product, exit website")

            selected_index = int(input("Enter the number corresponding to the product you want to view: "))

            if selected_index == 0:
                print(f"No matching products found for '{product_name}' on 3vFejzo.")
                driver.quit()
                return None, None
            elif 1 <= selected_index <= len(matching_products):
                selected_product = matching_products[selected_index - 1]
                product_url = selected_product[1]

                # Click on the selected product link
                driver.get(product_url)
                price_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'p.price .woocommerce-Price-amount')))
                price_text = price_element.text.replace('L', '').replace('.', '').strip()
                driver.execute_script("arguments[0].style.border='2px solid red'; arguments[0].style.padding='2px';", price_element)
                time.sleep(2)
                driver.quit()
                return float(price_text), product_url
            else:
                print("Invalid selection.")
                driver.quit()
                return None, None

    except TimeoutException:
        print(f"No search results found for '{product_name}' on 3vFejzo.")
        driver.quit()
        return None, None
