from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import time


def search_shpresa(product_name):
    driver = webdriver.Chrome()
    driver.get("https://shop.shpresa.al/")
    wait = WebDriverWait(driver, 60)  # Increased timeout to 60 seconds

    try:
        search_bar = wait.until(EC.presence_of_element_located((By.ID, 'esSearchInput')))
        search_bar.clear()
        search_bar.send_keys(product_name)
        search_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Kërko")]')))
        search_button.click()

        print(f"Available products in Shpresa for {product_name}:")
        matching_products = []

        try:
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a.flex.border-b.py-2')))

            time.sleep(1)

            product_elements = driver.find_elements(By.CSS_SELECTOR, 'a.flex.border-b.py-2')

            for idx, product in enumerate(product_elements, start=1):
                try:
                    title_element = product.find_element(By.CSS_SELECTOR, 'span.text-lg.font-bold.block.text-gray-800')
                    if product_name.lower() in title_element.text.lower():
                        matching_products.append((title_element.text.strip(), product.get_attribute('href')))
                        print(f"{idx}. {title_element.text.strip()}")
                except (StaleElementReferenceException, NoSuchElementException):
                    continue

            if not matching_products:
                print(f"No matching products found for '{product_name}' on Shpresa.")
                driver.quit()
                return None, None

            if len(matching_products) == 1:
                selected_product = matching_products[0]
                product_url = selected_product[1]
                driver.get(product_url)
                price_element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'span.woocommerce-Price-amount')))
                price_text = price_element.text.replace('L', '').replace(',', '').strip()
                driver.execute_script("arguments[0].style.border='2px solid red'; arguments[0].style.padding='2px';",
                                      price_element)
                time.sleep(2)
                driver.quit()
                return float(price_text), product_url
            else:
                print("0. No result matches your product, exit website")

                selected_index = int(input("Enter the number corresponding to the product you want to view: "))

                if selected_index == 0:
                    print(f"No matching products found for '{product_name}' on Shpresa.")
                    driver.quit()
                    return None, None
                elif 0 < selected_index <= len(matching_products):
                    selected_product = matching_products[selected_index - 1]
                    product_url = selected_product[1]

                    driver.get(product_url)
                    price_element = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'span.woocommerce-Price-amount')))
                    price_text = price_element.text.replace('L', '').replace(',', '').strip()
                    driver.execute_script(
                        "arguments[0].style.border='2px solid red'; arguments[0].style.padding='2px';", price_element)
                    time.sleep(2)
                    driver.quit()
                    return float(price_text), product_url
                else:
                    print("Invalid selection.")
                    driver.quit()
                    return None, None

        except TimeoutException:
            print(f"No search results found for '{product_name}' on Shpresa.")
            driver.quit()
            return None, None

    except TimeoutException:
        print(f"Timeout occurred while searching for '{product_name}' on Shpresa.")
        driver.quit()
        return None, None
