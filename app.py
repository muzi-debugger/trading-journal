import sqlite3
import MetaTrader5 as mt5
from flask import Flask, render_template
from dotenv import load_dotenv
import os
from datetime import datetime
import logging
# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def create_database():
    """Create the SQLite database and journal table if it doesn't exist."""
    conn = sqlite3.connect('trading_journal.db')
    cursor = conn.cursor()
    
    # Create table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS journal (
        position_id INTEGER PRIMARY KEY AUTOINCREMENT,
        account INTEGER,
        name TEXT,
        opening_balance REAL,
        gain REAL,
        profit REAL,
        closing_balance REAL,
        symbol TEXT,
        opened DATETIME,
        closed DATETIME
    )
    ''')


    conn.commit()
    conn.close()
    logger.info("Database and table created successfully.")

def get_journal_data():
    """Fetch all data from the journal table."""
    conn = sqlite3.connect('trading_journal.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM journal')
    raw_data = cursor.fetchall()
    conn.close()

    # Parse opened and closed timestamps
    data = [
        list(row[:8]) + 
        [datetime.fromisoformat(row[8]) if row[8] else None, 
         datetime.fromisoformat(row[9]) if row[9] else None]
        for row in raw_data
    ]
    return data


def update_journal(account, name, opening_balance, gain, profit, closing_balance, symbol, opened, closed):
    conn = sqlite3.connect('trading_journal.db')
    cursor = conn.cursor()

    # Check if the position already exists
    cursor.execute('''
    SELECT 1 FROM journal WHERE account = ? AND symbol = ? AND opened = ?
    ''', (account, symbol, opened))
    exists = cursor.fetchone()

    if not exists:
        # Insert only if the position doesn't exist
        cursor.execute('''
        INSERT INTO journal (account, name, opening_balance, gain, profit, closing_balance, symbol, opened, closed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (account, name, opening_balance, gain, profit, closing_balance, symbol, opened, closed))
        conn.commit()
        logger.info(f"Journal updated with new position for account {account}, symbol {symbol}.")
    else:
        logger.info(f"Position for account {account}, symbol {symbol}, and opened time {opened} already exists.")

    conn.close()

def fetch_account_data():
    if not mt5.initialize():
        logger.error("Failed to initialize MT5 connection. Shutting down.")
        return

    logger.info("MT5 initialized successfully.")

    login = int(os.getenv('MT5_LOGIN'))
    password = os.getenv('MT5_PASSWORD')
    server = os.getenv('MT5_SERVER')

    if not mt5.login(login, password=password, server=server):
        logger.error("Failed to log in to MT5 account. Shutting down.")
        mt5.shutdown()
        return

    logger.info("Logged in to MT5 account successfully.")

    account_info = mt5.account_info()
    if account_info is None:
        logger.error("Failed to fetch account info.")
        mt5.shutdown()
        return

    positions = mt5.positions_get()
    if not positions:
        logger.info("No open positions.")
        mt5.shutdown()
        return

    # Process each open position
    for position in positions:
        account = account_info.login
        name = "Tebogo"  # Replace with actual name
        opening_balance = account_info.balance
        gain = (position.profit / opening_balance * 100) if account_info.balance > 0 else 0
        profit = position.profit
        closing_balance = account_info.equity
        symbol = position.symbol
        opened = datetime.fromtimestamp(position.time)
        closed = None  # For now, set to None

        update_journal(account, name, opening_balance, gain, profit, closing_balance, symbol, opened, closed)

    mt5.shutdown()
    logger.info("MT5 connection closed.")


def fetch_position_data():
    """Fetch position data from MT5 for journal updates."""
    positions = mt5.positions_get()
    if not positions:
        logger.info("No open positions.")
        return None
    
    # Fetch the first position (or loop for all)
    position = positions[0]
    symbol = position.symbol
    opened = datetime.fromtimestamp(position.time)  # Position opened time
    closed = datetime.fromtimestamp(position.time_update) if position.time_update > 0 else None

    return symbol, opened, closed



@app.route('/')
def home():
    """Render the home page with journal data."""
    fetch_account_data()  # Fetch and update account data
    data = get_journal_data()  # Fetch data from the database
    logger.info(f"Fetched data for journal: {data}")
    return render_template('journal.html', data=data)

if __name__ == '__main__':
    create_database()  # Ensure the database and table exist
    app.run(debug=True)  # Run the Flask app
