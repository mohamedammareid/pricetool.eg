import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import os
import sys
import webbrowser
from typing import List, Optional, Tuple
import logging
from dataclasses import dataclass
from urllib.parse import quote_plus
import time
import random
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import re  # Add this import at the top

# Add debug logging configuration
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='price_comparison.log'
)

def clear_terminal() -> None:
    """Clear terminal screen safely across different platforms."""
    try:
        os.system('cls' if os.name == 'nt' else 'clear')
        sys.stdout.write("\033[H")
        sys.stdout.flush()
    except Exception:
        print('\n' * 100)

def loading_animation() -> None:
    """Simple single line loading animation."""
    animation = "⣾⣽⣻⢿⡿⣟⣯⣷"
    message = "🔍 Searching Egyptian stores for best prices..."
    try:
        sys.stdout.write("\033[?25l")
        for frame in animation * 3:
            sys.stdout.write(f"\r{frame} {message}")
            sys.stdout.flush()
            time.sleep(0.1)
        print()
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

def loading_animation_inline() -> None:
    """Display inline loading animation."""
    animation = "⣾⣽⣻⢿⡿⣟⣯⣷"
    try:
        sys.stdout.write("\033[?25l")
        for frame in animation * 2:
            sys.stdout.write(f"\r{frame} Processing...")
            sys.stdout.flush()
            time.sleep(0.1)
    finally:
        sys.stdout.write("\r" + " " * 20 + "\r")  # Clear animation
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

@dataclass
class Product:
    name: str
    price: float
    website: str
    url: str
    timestamp: datetime

class DatabaseManager:
    def __init__(self, db_name: str = 'product_prices.db'):
        self.db_name = db_name
        # Add datetime adapter for SQLite
        sqlite3.register_adapter(datetime, lambda x: x.isoformat())
        self.setup_database()

    def setup_database(self) -> None:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    price REAL,
                    website TEXT,
                    url TEXT,
                    timestamp DATETIME,
                    UNIQUE(name, website)
                )
            ''')
            conn.commit()

    def save_product(self, product: Product) -> None:
        if not product.name or product.price is None:
            return
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO products 
                (name, price, website, url, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                product.name, product.price, product.website, product.url, product.timestamp
            ))
            conn.commit()

    def save_best_deal(self, product: Product) -> None:
        """Save only the best deal found for a product."""
        if not product.name or product.price is None:
            return
        
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            
            # Check if we already have a better price for this product
            cursor.execute('''
                SELECT price FROM products 
                WHERE name = ? 
                ORDER BY price ASC 
                LIMIT 1
            ''', (product.name,))
            
            result = cursor.fetchone()
            if not result or product.price < result[0]:
                # Save new best price
                cursor.execute('''
                    INSERT OR REPLACE INTO products 
                    (name, price, website, url, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    product.name, product.price, product.website, 
                    product.url, product.timestamp
                ))
                conn.commit()

    def get_products_summary(self) -> List[Tuple[str, float, float]]:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name, MIN(price), AVG(price) 
                FROM products 
                GROUP BY name
                ORDER BY MIN(timestamp) DESC
            ''')
            return cursor.fetchall()

    def clear_database(self) -> None:
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM products')
            conn.commit()

class WebScraper:
    def __init__(self):
        self.session = self._create_session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }

    def _clean_text_for_comparison(self, text: str) -> str:
        """Clean text for comparison by removing special characters and extra spaces."""
        # Keep only alphanumeric, spaces, and dashes
        cleaned = ''.join(c for c in text if c.isalnum() or c.isspace() or c == '-')
        return ' '.join(cleaned.lower().split())

    def _exact_text_match(self, text1: str, text2: str) -> bool:
        """Check if two product names match."""
        t1 = self._clean_text_for_comparison(text1)
        t2 = self._clean_text_for_comparison(text2)
        
        # Try exact match first
        if t1 == t2:
            return True
        
        # Try matching without spaces
        if t1.replace(' ', '') == t2.replace(' ', ''):
            return True
            
        # Try matching the model number
        model_pattern = r'([a-z0-9]+-?[a-z0-9]+)'
        t1_models = set(re.findall(model_pattern, t1))
        t2_models = set(re.findall(model_pattern, t2))
        
        return bool(t1_models & t2_models)

    def _create_session(self):
        session = requests.Session()
        retry = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def get_soup(self, url: str) -> Optional[BeautifulSoup]:
        try:
            time.sleep(random.uniform(1, 2))
            response = self.session.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logging.error(f"Error fetching {url}: {str(e)}")
            return None

    def _extract_price(self, price_text: str) -> Optional[float]:
        """Enhanced price extraction."""
        try:
            # Remove all non-numeric characters except . and ,
            price_text = re.sub(r'[^\d,.]', '', price_text)
            
            # Handle Arabic numerals
            arabic_to_english = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
            price_text = price_text.translate(arabic_to_english)
            
            # Handle different price formats
            if ',' in price_text and '.' in price_text:
                price_text = price_text.replace(',', '')
            elif ',' in price_text:
                price_text = price_text.replace(',', '.')
                
            # Convert to float
            return float(price_text)
        except (ValueError, AttributeError):
            return None

    def _prepare_search_query(self, query: str) -> List[str]:
        """Prepare multiple search variations."""
        query = query.strip().lower()
        
        # Extract model number if present
        model_pattern = r'([a-z0-9]+-?[a-z0-9]+)'
        model_numbers = re.findall(model_pattern, query)
        
        # Find brand name
        brand = next((word for word in query.split() if word in self.common_brands), '')
        
        # Create search variations
        variations = []
        if brand and model_numbers:
            variations.append(f"{brand} {model_numbers[0]}")
        
        # Add first 3 words
        words = query.split()[:3]
        variations.append(' '.join(words))
        
        # Add full query
        variations.append(query)
        
        # Add model number only if exists
        if model_numbers:
            variations.append(model_numbers[0])
            
        return list(set(variations))  # Remove duplicates

    def _check_availability(self, item_soup: BeautifulSoup, website: str) -> bool:
        """Check if product is actually available for purchase."""
        if website == 'Amazon Egypt':
            stock_elem = item_soup.select_one('#availability span')
            if stock_elem:
                text = stock_elem.text.lower()
                return 'in stock' in text or 'available' in text
        elif website == 'Noon Egypt':
            return not bool(item_soup.select_one('.out-of-stock'))
        elif website == 'Jumia Egypt':
            return not bool(item_soup.select_one('.-mas'))
        return True

    def _check_relevance(self, product_name: str, search_terms: List[str]) -> bool:
        """Improved relevance checking."""
        if not product_name or not search_terms:
            return False
            
        product_name = product_name.lower()
        
        # Important keywords that must be present
        critical_terms = ['lenovo', 'legion', 'laptop'] if 'lenovo legion' in ' '.join(search_terms).lower() else []
        if critical_terms and not all(term in product_name for term in critical_terms):
            return False
            
        # Check individual word matches
        matches = sum(1 for term in search_terms if term.lower() in product_name)
        return matches / len(search_terms) >= 0.4  # Reduced threshold for better matches

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        return ' '.join(text.lower().split())

    def _exact_match_score(self, product_name: str, search_query: str) -> float:
        """Calculate how closely the product name matches search query."""
        if not product_name or not search_query:
            return 0.0
            
        product = self._normalize_text(product_name)
        query = self._normalize_text(search_query)
        
        # Extract key specifications
        query_specs = self._extract_specs(query)
        product_specs = self._extract_specs(product)
        
        # Calculate matches
        spec_matches = sum(1 for spec in query_specs if spec in product_specs)
        total_specs = len(query_specs) if query_specs else 1
        
        return spec_matches / total_specs

    def _extract_specs(self, text: str) -> List[str]:
        """Extract specifications from text."""
        specs = []
        words = text.lower().split()
        
        # Patterns to match
        patterns = [
            r'\d+gb',
            r'\d+tb',
            r'rtx\s*\d+',
            r'i\d-\d+',
            r'\d+th',
            r'ddr\d',
        ]
        
        for word in words:
            for pattern in patterns:
                if re.search(pattern, word):
                    specs.append(word)
                    
        return specs

    def _extract_amazon_product_id(self, url: str) -> Optional[str]:
        """Extract Amazon product ID from URL."""
        patterns = [
            r'/dp/([A-Z0-9]{10})',
            r'product/([A-Z0-9]{10})',
        ]
        for pattern in patterns:
            if match := re.search(pattern, url):
                return match.group(1)
        return None

    def _simplified_text(self, text: str) -> str:
        """Convert text to simple searchable format."""
        # Remove special chars and extra spaces
        cleaned = re.sub(r'[^\w\s-]', ' ', text.lower())
        return ' '.join(cleaned.split())

    def scrape_amazon(self, query: str) -> List[Product]:
        """Direct Amazon search with better product matching."""
        products = []
        
        # Fix URL undefined error and add search URL
        search_url = f"https://www.amazon.eg/s?k={quote_plus(query)}&language=en"
        print("\r🔍 Checking Amazon.eg...")
        
        soup = self.get_soup(search_url)
        if not soup:
            return products

        # Update selectors to match Amazon's current structure
        items = soup.select('div.s-result-item:not(.AdHolder)')
        print(f"Found {len(items)} items on Amazon...")

        for item in items[:30]:
            try:
                # Try multiple selectors for product info
                name_elem = (
                    item.select_one('h2 span.a-text-normal') or 
                    item.select_one('.a-size-medium.a-text-normal') or
                    item.select_one('.a-size-base-plus')
                )
                
                price_elem = (
                    item.select_one('span.a-price span.a-offscreen') or
                    item.select_one('span.a-price .a-price-whole') or
                    item.select_one('.a-price')
                )
                
                link = item.select_one('a.a-link-normal[href*="/dp/"]')
                
                if not all([name_elem, price_elem, link]):
                    continue

                name = name_elem.text.strip()
                price = self._extract_price(price_elem.text)
                
                if not price:
                    continue

                product_url = link['href']
                if not product_url.startswith('http'):
                    product_url = f"https://www.amazon.eg{product_url}"

                products.append(Product(
                    name=name,
                    price=price,
                    website='Amazon Egypt',
                    url=product_url,
                    timestamp=datetime.now()
                ))
                print(f"Found on Amazon: {name[:70]}... ({price} EGP)")

            except Exception as e:
                logging.debug(f"Error parsing Amazon item: {str(e)}")
                continue

        return products

    def _extract_price(self, price_text: str) -> Optional[float]:
        """Enhanced price extraction for Amazon."""
        try:
            # Remove currency symbols and text
            price_text = re.sub(r'[^\d.,]', '', price_text)
            
            # Handle different number formats
            if ',' in price_text and '.' in price_text:
                price_text = price_text.replace(',', '')
            elif ',' in price_text:
                price_text = price_text.replace(',', '.')
            
            return float(price_text)
        except (ValueError, AttributeError):
            return None

    def scrape_noon(self, query: str) -> List[Product]:
        """Direct Noon search with exact matching."""
        products = []
        url = f"https://www.noon.com/egypt-en/search?q={quote_plus(query)}"
        
        print("\r🔍 Checking Noon.com...")
        soup = self.get_soup(url)
        if not soup:
            return products

        items = soup.select('div[data-qa="product-grid"] div[data-qa="product-item"], div.productContainer')
        print(f"Found {len(items)} items on Noon...")

        for item in items[:30]:
            try:
                name_elem = item.select_one('div[data-qa="product-name"], div.name')
                price_elem = item.select_one('div[data-qa="price-box"] strong, span.price')
                link = item.select_one('a[href*="/egypt-en/"]')
                
                if not all([name_elem, price_elem, link]):
                    continue

                name = name_elem.text.strip()
                price = self._extract_price(price_elem.text)
                if not price:
                    continue

                url = f"https://www.noon.com{link['href']}"
                
                products.append(Product(
                    name=name,
                    price=price,
                    website='Noon Egypt',
                    url=url,
                    timestamp=datetime.now()
                ))
                print(f"Found: {name[:50]}... at {price} EGP")

            except Exception as e:
                logging.debug(f"Error parsing Noon item: {e}")

        return products

    def scrape_carrefour(self, query: str) -> List[Product]:
        """Direct Carrefour search with exact matching."""
        products = []
        url = f"https://www.carrefouregypt.com/mafegy/en/search?q={quote_plus(query)}"
        
        print("\r🔍 Checking Carrefour...")
        soup = self.get_soup(url)
        if not soup:
            return products

        items = soup.select('div.product-item, div.product_grid_item')
        print(f"Found {len(items)} items on Carrefour...")

        for item in items[:30]:
            try:
                name_elem = item.select_one('.product-name, .name')
                price_elem = item.select_one('.price, .product-price')
                link = item.select_one('a[href*="/p/"]')
                
                if not all([name_elem, price_elem, link]):
                    continue

                name = name_elem.text.strip()
                price = self._extract_price(price_elem.text)
                if not price:
                    continue

                url = link['href']
                if not url.startswith('http'):
                    url = f"https://www.carrefouregypt.com{url}"

                products.append(Product(
                    name=name,
                    price=price,
                    website='Carrefour Egypt',
                    url=url,
                    timestamp=datetime.now()
                ))
                print(f"Found: {name[:50]}... at {price} EGP")

            except Exception as e:
                logging.debug(f"Error parsing Carrefour item: {e}")

        return products

def _shorten_url(url: str) -> str:
    """Shorten URL for display by keeping domain and truncating path."""
    try:
        if len(url) <= 60:
            return url
        domain_end = url.find('/', 8)  # Find first / after https://
        if domain_end == -1:
            return url[:57] + "..."
        return url[:domain_end] + "/..." 
    except:
        return url

class PriceComparisonTool:
    def __init__(self):
        self.db = DatabaseManager()
        self.scraper = WebScraper()

    def search_products(self, query: str) -> List[Product]:
        """Search using exact query."""
        loading_animation()
        all_products = []
        
        websites = [
            (self.scraper.scrape_amazon, "Amazon Egypt"),
            (self.scraper.scrape_noon, "Noon Egypt"),
            (self.scraper.scrape_carrefour, "Carrefour Egypt")
        ]
        
        for scraper_func, website in websites:
            try:
                site_products = scraper_func(query)
                if site_products:
                    all_products.extend(site_products)
            except Exception as e:
                logging.error(f"Error searching {website}: {e}")
        
        return sorted(all_products, key=lambda x: x.price)

    def _extract_user_price(self, price_input: str) -> Optional[float]:
        if not price_input:
            return None
        try:
            cleaned = ''.join(c for c in price_input if c.isdigit() or c == '.' or c == ',')
            cleaned = cleaned.replace(',', '')
            return float(cleaned)
        except ValueError:
            return None

    def _shorten_url(self, url: str, max_length: int = 60) -> str:
        """Shorten URL for display."""
        if len(url) <= max_length:
            return url
        domain_end = url.find('/', 8)  # Find first / after https://
        if domain_end == -1:
            return url[:max_length] + "..."
        domain = url[:domain_end]
        path = url[domain_end:]
        if len(path) > 30:
            path = path[:27] + "..."
        return f"{domain}{path}"

    def display_results(self, products: List[Product], user_price: Optional[float] = None, search_query: str = "") -> None:
        if not products:
            print("\n❌ No matching products found.")
            print("💡 Try searching with:")
            print(f"  - Model number only: JR-BP560S")
            print(f"  - Shorter name: Joyroom JR-BP560S Stylus")
            print(f"  - Basic terms: Joyroom Stylus Pen")
            return

        # Sort by match score and price
        valid_products = [p for p in products if p.price is not None]
        if not valid_products:
            print("\n❌ No products with valid prices found.")
            return

        sorted_products = sorted(valid_products, key=lambda x: (x.price))
        best_deal = sorted_products[0]

        print("\n✨ Found Matching Products!")
        print("=" * 80)
        print(f"🏆 BEST PRICE FOUND:")
        print(f"🏷️ {best_deal.name}")
        print(f"💰 Price: {best_deal.price:,.2f} EGP")
        print(f"🌐 Website: {best_deal.website}")
        print(f"🔗 {_shorten_url(best_deal.url)}")
        print("=" * 80)

        if user_price:
            if user_price > best_deal.price:
                savings = user_price - best_deal.price
                print(f"\n💡 Better price available! You could save {savings:,.2f} EGP")
                print(f"💰 Your price: {user_price:,.2f} EGP")
                print(f"🏷️ Best price: {best_deal.price:,.2f} EGP")
                print(f"✨ Potential savings: {savings:,.2f} EGP ({(savings/user_price*100):.1f}%)")
                print(f"\n🛒 Get this deal: {best_deal.url}")
            else:
                print(f"\n✅ Excellent! You got a great deal!")
                print(f"💰 Your price: {user_price:,.2f} EGP")
                print(f"📊 Current best price: {best_deal.price:,.2f} EGP")
                print(f"💫 You saved: {best_deal.price - user_price:,.2f} EGP!")
        else:
            print("\n💡 Current best price available at:")
            print(f"🛒 {best_deal.url}")

        print("\n💡 Available on other websites:")
        websites = set(p.website for p in products)
        for website in websites:
            site_products = [p for p in products if p.website == website]
            if site_products:
                best_site_deal = min(site_products, key=lambda x: x.price)
                print(f"\n🏪 {website}:")
                print(f"💰 Best Price: {best_site_deal.price:,.2f} EGP")
                print(f"🔗 {_shorten_url(best_site_deal.url)}")

        if len(sorted_products) > 1:
            print("\n📊 All Available Prices:")
            print("-" * 80)
            for product in sorted_products[1:]:
                print(f"🏷️ {product.name}")
                print(f"💰 Price: {product.price:,.2f} EGP")
                print(f"🌐 {product.website}")
                print(f"🔗 {_shorten_url(product.url)}")
                print("-" * 80)

        # After showing all results, ask about opening links
        if products:
            print("\n🌐 Would you like to open the product links?")
            print("1. Open all product links")
            print("2. Open top 5 best deals only")
            print("3. Skip")
            
            while True:
                choice = input("\nChoice (1-3): ").strip()
                if choice == "1":
                    self.open_product_links(products, best_only=False)
                    break
                elif choice == "2":
                    self.open_product_links(products, best_only=True)
                    break
                elif choice == "3":
                    break
                else:
                    print("❌ Invalid choice. Please try again.")

        input("\nPress Enter to return to menu...")

    def open_product_links(self, products: List[Product], best_only: bool = False) -> None:
        """Open product links in browser."""
        if not products:
            return
            
        sorted_products = sorted(products, key=lambda x: x.price)
        
        if best_only:
            links_to_open = [p.url for p in sorted_products[:5]]
            print("\n🔗 Opening top 5 best deals...")
        else:
            links_to_open = [p.url for p in sorted_products]
            print("\n🔗 Opening all product links...")
        
        for url in links_to_open:
            try:
                webbrowser.open(url, new=2)
                time.sleep(0.5)
            except Exception as e:
                logging.error(f"Error opening URL {url}: {e}")

    def save_results(self, products: List[Product]) -> None:
        for product in products:
            self.db.save_product(product)

    def show_price_history(self) -> None:
        while True:
            clear_terminal()
            records = self.db.get_products_summary()
            
            if not records:
                print("\n❌ No price history available.")
                input("\nPress Enter to return to main menu...")
                return

            print("\n📊 Price History Summary")
            print("=" * 80)
            for name, min_price, avg_price in records:
                print(f"📦 Product: {name}")
                print(f"💰 Best Price: {min_price:.2f} EGP")
                print(f"📈 Average: {avg_price:.2f} EGP")
                print("-" * 80)

            print("\n1. Clear history")
            print("2. Back to menu")
            
            choice = input("\nChoice (1-2): ")
            
            if choice == "1":
                confirm = input("\n⚠️ Clear all price history? (y/n): ")
                if confirm.lower() == 'y':
                    self.db.clear_database()
                    print("\n✅ History cleared!")
                    input("\nPress Enter to continue...")
                    break
            elif choice == "2":
                break

def main():
    tool = PriceComparisonTool()
    
    while True:
        clear_terminal()
        print("🔍 Egyptian Price Comparison Tool")
        print("=" * 40)
        print("1. Search Products")
        print("2. View History")
        print("3. Exit")
        
        choice = input("\nChoice (1-3): ").strip()
        
        if choice == "1":
            clear_terminal()
            search_query = input("🔍 Enter product name: ").strip()
            
            if not search_query:
                print("\n❌ Please enter a product name.")
                input("\nPress Enter to continue...")
                continue
            
            print("\n")
            loading_animation()
            products = tool.search_products(search_query)
            
            print("\n💰 Enter the price you paid (or press Enter to skip): ", end='', flush=True)
            loading_animation_inline()
            price_input = input().strip()
            
            user_price = tool._extract_user_price(price_input) if price_input else None
            tool.display_results(products, user_price, search_query)
            tool.save_results(products)
            
            input("\nPress Enter to return to menu...")
        
        elif choice == "2":
            tool.show_price_history()
            
        elif choice == "3":
            print("\n👋 Thanks for using Price Comparison Tool!")
            break
        else:
            print("\n❌ Invalid choice!")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Program terminated by user.")
    except Exception as e:
        print(f"\n❌ An error occurred: {str(e)}")