# Price Comparison Tool

This project is a Python-based tool designed to compare product prices across various e-commerce websites in Egypt. It retrieves product details, identifies the best deals, and stores the data in a SQLite database for analysis.

---

## Features

- **Web Scraping**: Fetches product details and prices from websites like Amazon Egypt, Noon Egypt, and Jumia Egypt using BeautifulSoup.
- **Database Management**: Stores product data in a SQLite database, ensuring efficient organization and retrieval.
- **Best Price Detection**: Saves and updates the best price for each product.
- **Advanced Matching**: Includes enhanced matching algorithms for product names and model numbers.
- **Error Handling & Logging**: Logs errors and debug messages for troubleshooting.
- **Loading Animations**: User-friendly animations to enhance the CLI experience.

---

## Technologies Used

- **Python Libraries**:
  - `requests` for HTTP requests.
  - `BeautifulSoup` from `bs4` for web scraping.
  - `sqlite3` for database management.
  - `logging` for error and debug logging.
  - `dataclasses` for structured data representation.
  - `re` for regex-based text processing.
- **SQLite**: Lightweight database for storing product information.

---

## How It Works

1. **Database Initialization**:
   - The `DatabaseManager` class sets up a SQLite database (`product_prices.db`) with a `products` table.
   - It ensures duplicate prevention using unique constraints on product names and websites.

2. **Web Scraping**:
   - The `WebScraper` class fetches product data from multiple e-commerce websites.
   - Implements retry logic and error handling for reliable data fetching.

3. **Price Comparison**:
   - Extracts and normalizes product names and prices.
   - Saves the best deal for each product in the database.

4. **Search Query Handling**:
   - Supports variations in search terms (e.g., brand names, model numbers).
   - Uses regex and advanced matching for improved accuracy.

5. **Command-Line Interface (CLI)**:
   - User interacts with the tool via the terminal.
   - Includes clear-screen functionality and animations for a seamless experience.

---

## Requirements

1. Python 3.7+
2. Required libraries (install with pip):
   ```bash
   pip install requests beautifulsoup4
   ```

---

## Usage

1. Clone the repository.
2. Install the required Python libraries.
3. Run the script:
   ```bash
   python main.py
   ```
4. Enter product names to search for best prices.

---

## Folder Structure

- `main.py`: The entry point of the application.
- `scraper.py`: Contains web scraping logic.
- `database.py`: Handles database operations.
- `utils.py`: Utility functions like loading animations.
- `requirements.txt`: List of required libraries.
- `README.md`: Project documentation.

---

## Future Enhancements

1. Add support for more e-commerce websites.
2. Enhance product relevance and matching algorithms.
3. Introduce a graphical user interface (GUI).
4. Implement real-time notifications for price drops.

---

## Contributions

Contributions are welcome! If you want to contribute:

1. Fork the repository.
2. Create a new branch.
3. Commit your changes.
4. Open a pull request.

---

## Author

Mohammed Ammar Mohammed Eid

---

## Contact

For any queries or suggestions, feel free to contact me at [your email address].

