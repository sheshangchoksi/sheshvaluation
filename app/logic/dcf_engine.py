from app.logic._st_shim import st

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import random
import requests
from bs4 import BeautifulSoup
import re
from io import StringIO
# ── yf_ratelimit shim ──────────────────────────────────────────
# Replaces direct yfinance calls with rate-limit-safe wrappers.
# DO NOT remove this block.
from app.logic.yf_ratelimit import safe_ticker as _rl_ticker, safe_download as _rl_download

class _YFShim:
    """Makes existing yf.Ticker() / yf.download() calls use safe wrappers."""
    @staticmethod
    def Ticker(symbol, **_):
        return _rl_ticker(symbol)
    @staticmethod
    def download(tickers, **kwargs):
        return _rl_download(tickers, **kwargs)

yf = _YFShim()
# ── end shim ───────────────────────────────────────────────────

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# Stock Price Comparison Module
try:
    from stock_price_comparison import (
        get_stock_comparison_data_listed,
        get_stock_comparison_data_screener
    )
    STOCK_COMPARISON_AVAILABLE = True
except ImportError as e:
    STOCK_COMPARISON_AVAILABLE = False
    STOCK_COMPARISON_ERROR = str(e)

# Screener Excel Mode Module
try:
    from screener_excel_mode import (
        parse_screener_excel_to_dataframes,
        get_value_from_screener_df,
        detect_screener_year_columns,
        extract_screener_financials,
        get_screener_shares_outstanding,
        calculate_screener_ddm_valuation,
        calculate_screener_rim_valuation,
        generate_screener_valuation_excel,
        display_screener_financial_summary,
        display_screener_ddm_results,
        display_screener_rim_results,
        fetch_ticker_data_for_screener
    )
    SCREENER_MODE_AVAILABLE = True
except ImportError as e:
    SCREENER_MODE_AVAILABLE = False
    SCREENER_MODE_ERROR = str(e)

# Screener Auto Download Module
try:
    from screener_auto_download_streamlit import integrate_with_existing_upload_section
    AUTO_DOWNLOAD_AVAILABLE = True
except ImportError as e:
    AUTO_DOWNLOAD_AVAILABLE = False
    AUTO_DOWNLOAD_ERROR = str(e)

# Indian Stock Market APIs (fallback for Yahoo Finance)
SCREENER_IMPORT_ERROR = None
try:
    from app.logic.utils_indian_apis import get_indian_stock_data, get_nse_quote, get_screener_data, fetch_screener_financials
    INDIAN_APIS_AVAILABLE = True
except ImportError as e:
    INDIAN_APIS_AVAILABLE = False
    SCREENER_IMPORT_ERROR = f"ImportError: {e}"
    # Define robust embedded screener with better parsing
    def fetch_screener_financials(symbol, num_years=5):
        """Robust Screener.in scraper with detailed logging and Streamlit Cloud compatibility"""
        import time as _time
        import random as _random
        try:
            from bs4 import BeautifulSoup
            import requests
            import streamlit as st
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            import os
            
            # Disable proxy that may be blocking screener.in
            os.environ.pop('HTTP_PROXY', None)
            os.environ.pop('HTTPS_PROXY', None)
            os.environ.pop('http_proxy', None)
            os.environ.pop('https_proxy', None)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive'
            }
            
            # Set up session with retries
            session = requests.Session()
            session.trust_env = False  # Bypass proxy blocking screener.in
            retry_strategy = Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            
            urls_to_try = [f"https://www.screener.in/company/{symbol}/consolidated/", f"https://www.screener.in/company/{symbol}/"]
            
            soup = None
            connection_error = False
            last_error = None
            
            for url in urls_to_try:
                try:
                    _time.sleep(_random.uniform(1.5, 3.0))
                    st.info(f"🔍 Attempting to fetch from: {url}")
                    
                    # Try with SSL verification first
                    try:
                        resp = session.get(url, headers=headers, timeout=30, verify=True)
                    except requests.exceptions.SSLError:
                        st.warning("⚠️ SSL verification failed, retrying without verification...")
                        resp = session.get(url, headers=headers, timeout=30, verify=False)
                    
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.content, 'lxml')
                        st.success(f"✅ Successfully connected to Screener.in")
                        break
                    else:
                        st.warning(f"⚠️ Received status code {resp.status_code}, trying next URL...")
                        
                except requests.exceptions.ConnectionError as e:
                    connection_error = True
                    last_error = str(e)
                    st.error(f"❌ CONNECTION ERROR: Cannot reach www.screener.in")
                    
                    # Check if it's Streamlit Cloud specific issue
                    if "Connection refused" in str(e) or "Errno 111" in str(e):
                        st.error("🔴 **STREAMLIT CLOUD NETWORK RESTRICTION DETECTED**")
                        st.markdown("---")
                        st.markdown("### ✅ Recommended Solutions:")
                        st.markdown("""
                        **Option 1: Use Screener Excel Mode (Recommended)**
                        1. Visit [screener.in/company/{}/consolidated/](https://www.screener.in/company/{}/consolidated/)
                        2. Click the **Export** button to download Excel file
                        3. Return to this app and select **"Screener Excel Mode"**
                        4. Upload the downloaded Excel file
                        
                        **Option 2: Use Yahoo Finance Mode**
                        - For listed companies with NSE/BSE tickers
                        - Select "Listed Company (Yahoo Finance)" mode
                        
                        **Option 3: Deploy Elsewhere**
                        - Deploy on Heroku, Railway, or your own server
                        - These platforms typically have fewer network restrictions
                        
                        **Option 4: Upgrade Streamlit Cloud**
                        - Streamlit Cloud Teams/Enterprise may have better network access
                        """.format(symbol, symbol))
                        st.markdown("---")
                    return None
                    
                except requests.exceptions.Timeout:
                    st.warning(f"⚠️ Timeout accessing {url} (30s), trying next URL...")
                    continue
                    
                except Exception as e:
                    st.warning(f"⚠️ Error accessing {url}: {type(e).__name__}: {str(e)}")
                    last_error = str(e)
                    continue
            
            if soup is None:
                if not connection_error:
                    st.error(f"❌ Could not access Screener.in page for {symbol}")
                    if last_error:
                        st.error(f"Last error: {last_error}")
                    st.info("💡 Try using **Screener Excel Mode** instead - upload a manually downloaded file from screener.in")
                return None
            
            company_name = soup.find('h1').get_text(strip=True) if soup.find('h1') else symbol
            
            # Try to extract current price from page
            current_price = 0
            try:
                # Look for price in the top metrics section
                price_elem = soup.find('span', class_='number')
                if price_elem:
                    price_text = price_elem.get_text(strip=True).replace(',', '').replace('₹', '').strip()
                    current_price = float(price_text)
                    st.write(f"✓ Found Current Price: ₹{current_price:.2f}")
            except:
                pass
            
            # More flexible table parsing
            def parse_row(table, keywords, debug_name=""):
                if table is None:
                    return []
                for tr in table.find_all('tr'):
                    cells = tr.find_all(['td', 'th'])
                    if not cells:
                        continue
                    label = cells[0].get_text(strip=True).lower().replace('\xa0', ' ').replace('–', '-').replace('+', '').strip()
                    
                    # Try each keyword
                    for kw in keywords:
                        if kw.lower() in label:
                            values = []
                            for cell in cells[1:]:
                                raw = cell.get_text(strip=True).replace(',', '').replace('\xa0', '')
                                try:
                                    values.append(float(raw))
                                except:
                                    values.append(0.0)
                            if debug_name and values:
                                st.write(f"✓ Found {debug_name}: {len(values)} years")
                            return values
                return []
            
            # Get ALL tables on page
            all_tables = soup.find_all('table')
            st.info(f"📊 Found {len(all_tables)} tables on Screener.in page")
            
            # Find tables by their parent section IDs (more reliable)
            pl_table = None
            bs_table = None
            
            # Method 1: Find by section ID
            pl_section = soup.find('section', {'id': 'profit-loss'})
            if pl_section:
                # Find the main results table (not segment table)
                main_table = pl_section.find('div', {'data-result-table': ''})
                if main_table:
                    pl_table = main_table.find('table')
                    if pl_table:
                        st.write("✓ Found P&L table by section ID and data-result-table")
            
            bs_section = soup.find('section', {'id': 'balance-sheet'})
            if bs_section:
                main_table = bs_section.find('div', {'data-result-table': ''})
                if main_table:
                    bs_table = main_table.find('table')
                    if bs_table:
                        st.write("✓ Found Balance Sheet table by section ID and data-result-table")
            
            # Method 2: Fallback - look for class="data-table"
            if pl_table is None or bs_table is None:
                st.warning("⚠️ Using fallback method - searching by class")
                data_tables = soup.find_all('table', class_='data-table')
                
                for idx, table in enumerate(data_tables):
                    # Check what section this table is in
                    parent_section = table.find_parent('section')
                    if parent_section and parent_section.get('id'):
                        section_id = parent_section.get('id')
                        st.write(f"  Table #{idx+1} is in section: {section_id}")
                        
                        if 'profit' in section_id or 'loss' in section_id:
                            if pl_table is None:
                                pl_table = table
                                st.write(f"✓ Using Table #{idx+1} as P&L")
                        elif 'balance' in section_id or 'sheet' in section_id:
                            if bs_table is None:
                                bs_table = table
                                st.write(f"✓ Using Table #{idx+1} as Balance Sheet")
            
            if pl_table is None or bs_table is None:
                st.error(f"❌ Could not locate financial tables. Found {len(all_tables)} total tables.")
                if pl_table is None:
                    st.error("  Missing: P&L table")
                if bs_table is None:
                    st.error("  Missing: Balance Sheet table")
                return None
            
            st.write("### 📋 Parsing P&L Statement")
            # More flexible parsing - return first match found
            def parse_row_flexible(table, keywords, debug_name=""):
                if table is None:
                    return []
                
                for tr in table.find_all('tr'):
                    cells = tr.find_all(['td', 'th'])
                    if not cells:
                        continue
                    
                    # Get label from first cell
                    first_cell = cells[0]
                    label = first_cell.get_text(strip=True).lower()
                    
                    # Remove special characters
                    label = label.replace('\xa0', ' ').replace('–', '-').replace('+', '').replace('&amp;', '').replace('  ', ' ').strip()
                    
                    # Try each keyword
                    for kw in keywords:
                        if kw.lower() in label:
                            values = []
                            for cell in cells[1:]:
                                raw = cell.get_text(strip=True).replace(',', '').replace('\xa0', '')
                                try:
                                    val = float(raw)
                                    values.append(val)
                                except:
                                    values.append(0.0)
                            
                            # Only return if we found actual non-zero values
                            if values and any(v != 0 for v in values):
                                if debug_name:
                                    st.write(f"✓ Found {debug_name}: {len(values)} years - Label: '{label[:60]}'")
                                return values
                
                return []
            
            raw_revenue = parse_row_flexible(pl_table, ['revenue'], "Revenue")
            raw_expenses = parse_row_flexible(pl_table, ['expenses'], "Expenses")
            raw_operating_profit = parse_row_flexible(pl_table, ['financing profit', 'operating profit'], "Financing/Operating Profit")
            raw_other_income = parse_row_flexible(pl_table, ['other income'], "Other Income")
            raw_interest = parse_row_flexible(pl_table, ['interest'], "Interest")
            raw_depreciation = parse_row_flexible(pl_table, ['depreciation'], "Depreciation")
            raw_pbt = parse_row_flexible(pl_table, ['profit before tax'], "PBT")
            raw_tax = []
            raw_tax_pct = parse_row_flexible(pl_table, ['tax %'], "Tax %")
            raw_net_profit = parse_row_flexible(pl_table, ['net profit'], "Net Profit")
            raw_eps = parse_row_flexible(pl_table, ['eps in rs'], "EPS")
            
            st.write("### 🏦 Parsing Balance Sheet")
            # Equity & Liabilities
            raw_equity_capital = parse_row_flexible(bs_table, ['equity capital'], "Equity Capital")
            raw_reserves = parse_row_flexible(bs_table, ['reserves'], "Reserves")
            raw_borrowing = parse_row_flexible(bs_table, ['borrowing'], "Borrowing")
            raw_other_liabilities = parse_row_flexible(bs_table, ['other liabilities'], "Other Liabilities")
            raw_trade_payables = parse_row_flexible(bs_table, ['trade payables'], "Trade Payables")
            raw_advance_customers = parse_row_flexible(bs_table, ['advance from customers'], "Advance from Customers")
            
            # Assets - main items
            raw_fixed_assets = parse_row_flexible(bs_table, ['fixed assets'], "Fixed Assets")
            raw_gross_block = parse_row_flexible(bs_table, ['gross block'], "Gross Block")
            raw_accumulated_dep = parse_row_flexible(bs_table, ['accumulated depreciation'], "Accumulated Depreciation")
            raw_cwip = parse_row_flexible(bs_table, ['cwip'], "CWIP")
            raw_investments = parse_row_flexible(bs_table, ['investments'], "Investments")
            
            # Current Assets
            raw_trade_receivables = parse_row_flexible(bs_table, ['trade receivables'], "Trade Receivables")
            raw_cash = parse_row_flexible(bs_table, ['cash equivalents'], "Cash")
            raw_inventory = parse_row_flexible(bs_table, ['inventories'], "Inventory")
            raw_loans_advances = parse_row_flexible(bs_table, ['loans n advances'], "Loans & Advances")
            raw_other_assets = parse_row_flexible(bs_table, ['other assets'], "Other Assets")
            
            # SECOND PASS: If main items are missing, look for them as nested items
            # This catches items that appear AFTER expandable section headers
            if not raw_trade_receivables:
                st.info("  🔍 Trade receivables not found as main item, searching nested items...")
                # Look for rows that come after "Other Assets" or similar
                found_nested = False
                in_other_assets_section = False
                for tr in bs_table.find_all('tr'):
                    cells = tr.find_all(['td', 'th'])
                    if not cells:
                        continue
                    label = cells[0].get_text(strip=True).lower()
                    
                    # Check if we're in "Other Assets" section
                    if 'other asset' in label:
                        in_other_assets_section = True
                        continue
                    
                    # If we're in the section and find trade receivables
                    if in_other_assets_section and ('trade receivable' in label or 'receivable' in label):
                        values = []
                        for cell in cells[1:]:
                            raw = cell.get_text(strip=True).replace(',', '').replace('\xa0', '')
                            try:
                                values.append(float(raw))
                            except:
                                values.append(0.0)
                        if values and any(v != 0 for v in values):
                            raw_trade_receivables = values
                            st.write(f"  ✓ Found nested Trade Receivables: {len(values)} years")
                            found_nested = True
                            break
                    
                    # Stop if we hit next major section
                    if in_other_assets_section and ('total' in label or 'fixed asset' in label or 'investment' in label):
                        break
            
            if not raw_inventory:
                st.info("  🔍 Inventory not found as main item, searching nested items...")
                in_other_assets_section = False
                for tr in bs_table.find_all('tr'):
                    cells = tr.find_all(['td', 'th'])
                    if not cells:
                        continue
                    label = cells[0].get_text(strip=True).lower()
                    
                    if 'other asset' in label:
                        in_other_assets_section = True
                        continue
                    
                    if in_other_assets_section and ('inventor' in label or 'stock' in label):
                        values = []
                        for cell in cells[1:]:
                            raw = cell.get_text(strip=True).replace(',', '').replace('\xa0', '')
                            try:
                                values.append(float(raw))
                            except:
                                values.append(0.0)
                        if values and any(v != 0 for v in values):
                            raw_inventory = values
                            st.write(f"  ✓ Found nested Inventory: {len(values)} years")
                            break
                    
                    if in_other_assets_section and ('total' in label or 'fixed asset' in label):
                        break
            
            raw_total_assets = parse_row_flexible(bs_table, ['total assets', 'total asset'], "Total Assets")
            raw_total_liabilities = parse_row_flexible(bs_table, ['total liabilities', 'total liability'], "Total Liabilities")
            
            # Determine main receivables based on what's available
            st.write("### 🔍 Determining Working Capital Items")
            
            # Use trade receivables if available
            raw_receivables = raw_trade_receivables if raw_trade_receivables and sum(raw_trade_receivables) > 0 else []
            
            # If no trade receivables but has loans & advances (NBFC), use that
            if not raw_receivables and raw_loans_advances and sum(raw_loans_advances) > 0:
                raw_receivables = raw_loans_advances
                st.info("  🏦 Using Loans & Advances as Receivables (NBFC detected)")
            
            # Use trade payables if available
            raw_payables = raw_trade_payables if raw_trade_payables and sum(raw_trade_payables) > 0 else []
            
            # If no trade payables but has advances from customers, use that
            if not raw_payables and raw_advance_customers and sum(raw_advance_customers) > 0:
                raw_payables = raw_advance_customers
                st.info("  📦 Using Advances from Customers as Payables")
            
            # If no payables at all, use other liabilities
            if not raw_payables and raw_other_liabilities and sum(raw_other_liabilities) > 0:
                raw_payables = raw_other_liabilities
                st.info("  📊 Using Other Liabilities as Payables")
            
            # Show what we found
            if raw_receivables:
                st.write(f"  ✓ Receivables: {len(raw_receivables)} years")
            else:
                st.warning("  ⚠️ No Receivables found")
            
            if raw_payables:
                st.write(f"  ✓ Payables: {len(raw_payables)} years")
            else:
                st.warning("  ⚠️ No Payables found")
            
            if raw_inventory:
                st.write(f"  ✓ Inventory: {len(raw_inventory)} years")
            else:
                st.info("  ℹ️ No Inventory (may be service/NBFC company)")
            
            # Check what we got
            items_found = sum([
                1 if raw_revenue else 0,
                1 if raw_net_profit else 0,
                1 if raw_equity_capital else 0,
                1 if raw_reserves else 0,
                1 if raw_borrowing else 0,
                1 if raw_fixed_assets else 0,
                1 if raw_operating_profit or raw_pbt else 0
            ])
            
            st.info(f"📊 Extracted {items_found}/7 key line items successfully")
            
            # Show what's missing
            missing_items = []
            if not raw_revenue:
                missing_items.append("Revenue")
            if not raw_net_profit:
                missing_items.append("Net Profit")
            if not raw_equity_capital:
                missing_items.append("Equity Capital")
            if not raw_reserves:
                missing_items.append("Reserves")
            if not raw_borrowing:
                missing_items.append("Borrowings")
            if not raw_fixed_assets:
                missing_items.append("Fixed Assets")
            if not (raw_operating_profit or raw_pbt):
                missing_items.append("Operating Profit/PBT")
            
            if missing_items:
                st.warning(f"⚠️ Missing items: {', '.join(missing_items)}")
            
            if items_found < 3:
                st.error("❌ Insufficient data extracted from Screener.in. Too few key line items found.")
                st.warning("💡 This can happen if:\n- Company has limited financial history\n- Screener.in changed their HTML structure\n- Company uses non-standard accounting labels")
                return None
            
            def pad(lst, n):
                lst = [v for v in lst if v is not None]
                if len(lst) < n:
                    lst = [0.0] * (n - len(lst)) + lst
                return lst[-n:]
            
            n = num_years
            revenue = pad(raw_revenue, n)
            expenses = pad(raw_expenses, n)
            operating_profit = pad(raw_operating_profit, n)
            other_income = pad(raw_other_income, n)
            interest = pad(raw_interest, n)
            depreciation = pad(raw_depreciation, n)
            pbt = pad(raw_pbt, n)
            tax = pad(raw_tax, n)
            tax_pct = pad(raw_tax_pct, n)
            net_profit = pad(raw_net_profit, n)
            eps = pad(raw_eps, n)
            
            equity_capital = pad(raw_equity_capital, n)
            reserves = pad(raw_reserves, n)
            borrowing = pad(raw_borrowing, n)
            other_liabilities = pad(raw_other_liabilities, n)
            payables = pad(raw_payables, n)
            receivables = pad(raw_receivables, n)
            fixed_assets = pad(raw_fixed_assets, n)
            gross_block = pad(raw_gross_block, n)
            accumulated_dep = pad(raw_accumulated_dep, n)
            cwip = pad(raw_cwip, n)
            cash_vals = pad(raw_cash, n)
            inventory_vals = pad(raw_inventory, n)
            investments = pad(raw_investments, n)
            other_assets = pad(raw_other_assets, n)
            total_assets = pad(raw_total_assets, n)
            
            # Calculate shares from EPS
            shares = 0
            for i in range(n - 1, -1, -1):
                if eps[i] != 0 and net_profit[i] != 0:
                    shares = int((net_profit[i] * 10_000_000) / eps[i])
                    st.success(f"✅ Calculated shares: {shares:,} (from Year {i+1} EPS: ₹{eps[i]:.2f})")
                    break
            
            # If EPS method failed, try NSEPy
            if shares == 0:
                st.warning("⚠️ Could not calculate from EPS. Trying NSEPy...")
                try:
                    # Try to get from NSE
                    import requests
                    nse_url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': '*/*',
                        'Accept-Language': 'en-US,en;q=0.9',
                    }
                    # Get session cookies first
                    session = requests.Session()
                    session.get("https://www.nseindia.com", headers=headers, timeout=5)
                    resp = session.get(nse_url, headers=headers, timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        # NSE gives "issuedSize" in number of shares
                        shares = data.get('securityInfo', {}).get('issuedSize', 0)
                        if shares > 0:
                            st.success(f"✅ Fetched shares from NSE: {shares:,}")
                        else:
                            st.info("💡 NSE data available but no issuedSize found")
                    else:
                        st.info(f"💡 NSE API returned status {resp.status_code}")
                except Exception as e:
                    st.info(f"💡 NSE fetch failed: {str(e)[:100]}")
            
            if shares == 0:
                st.warning("⚠️ Could not calculate shares outstanding. Will need manual input.")
            
            CR_TO_LAC = 10.0
            from datetime import datetime as _dt
            current_year = _dt.now().year
            years_labels = [str(current_year - i) for i in range(n)]
            
            financials_out = {
                'years': years_labels,
                'revenue': [], 'cogs': [], 'opex': [], 'ebitda': [], 'depreciation': [],
                'ebit': [], 'interest': [], 'interest_income': [], 'tax': [], 'nopat': [],
                'fixed_assets': [], 'inventory': [], 'receivables': [], 'payables': [],
                'cash': [], 'equity': [], 'st_debt': [], 'lt_debt': []
            }
            
            for i in range(n - 1, -1, -1):
                rev = revenue[i] * CR_TO_LAC
                dep_val = depreciation[i] * CR_TO_LAC
                int_val = interest[i] * CR_TO_LAC
                other_inc = other_income[i] * CR_TO_LAC
                
                # Use operating profit if available, else derive from PBT
                if operating_profit[i] != 0:
                    ebit_val = operating_profit[i] * CR_TO_LAC
                    ebitda_val = ebit_val + dep_val
                else:
                    pbt_val = pbt[i] * CR_TO_LAC
                    ebitda_val = pbt_val + int_val + dep_val
                    ebit_val = ebitda_val - dep_val
                
                # COGS and OpEx estimation
                cogs_val = rev * 0.55 if rev > 0 else 0.0
                opex_val = max(0, rev - cogs_val - ebitda_val)
                if opex_val < 0 and expenses[i] != 0:
                    total_exp = expenses[i] * CR_TO_LAC
                    cogs_val = total_exp * 0.65
                    opex_val = total_exp * 0.35
                
                # Tax calculation
                tax_val = tax[i] * CR_TO_LAC if tax[i] != 0 else ebit_val * 0.25
                t_rate = min(0.35, tax_val / ebit_val) if ebit_val != 0 else 0.25
                nopat_val = ebit_val * (1 - t_rate)
                
                # Balance sheet
                eq_val = (equity_capital[i] + reserves[i]) * CR_TO_LAC
                fa_val = fixed_assets[i] * CR_TO_LAC
                pay_val = payables[i] * CR_TO_LAC
                rec_val = receivables[i] * CR_TO_LAC
                cash_val = cash_vals[i] * CR_TO_LAC
                inv_val = inventory_vals[i] * CR_TO_LAC
                borrow_val = borrowing[i] * CR_TO_LAC
                st_debt_val = borrow_val * 0.30
                lt_debt_val = borrow_val * 0.70
                
                for key, val in zip(
                    ['revenue', 'cogs', 'opex', 'ebitda', 'depreciation', 'ebit', 'interest', 'interest_income', 'tax', 'nopat', 'fixed_assets', 'inventory', 'receivables', 'payables', 'cash', 'equity', 'st_debt', 'lt_debt'],
                    [rev, cogs_val, opex_val, ebitda_val, dep_val, ebit_val, int_val, other_inc, tax_val, nopat_val, fa_val, inv_val, rec_val, pay_val, cash_val, eq_val, st_debt_val, lt_debt_val]
                ):
                    financials_out[key].append(val)
            
            st.success(f"✅ Successfully parsed financials for {company_name}")
            return {'financials': financials_out, 'shares': shares, 'company_name': company_name, 'current_price': current_price}
            
        except Exception as e:
            st.error(f"❌ Scraper error: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            return None
except Exception as e:
    INDIAN_APIS_AVAILABLE = False
    SCREENER_IMPORT_ERROR = f"Exception: {e}"
    fetch_screener_financials = None

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image as RLImage, KeepTogether
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
import tempfile
import os
from PIL import Image as PILImage
import io


# ================================
# AGGRESSIVE RATE LIMIT PREVENTION WITH DATA CACHING
# ================================

# Global cache for yfinance DATA (not just ticker objects)
# This caches .info, .financials, .balance_sheet, .cashflow to prevent duplicate API calls
_TICKER_DATA_CACHE = {}
_CACHE_TIMESTAMP = {}
CACHE_DURATION = 300  # 5 minutes cache

class CachedTickerData:
    """
    Wrapper class that caches yfinance ticker data properties
    This prevents rate limits by caching .info, .financials, etc.
    """
    def __init__(self, ticker_symbol, force_refresh=False):
        self.symbol = ticker_symbol
        self._ticker_obj = None
        self._info = None
        self._financials = None
        self._balance_sheet = None
        self._cashflow = None
        self._history = None
        self._loaded = False
        
        # Load from cache or fetch new
        if not force_refresh and ticker_symbol in _TICKER_DATA_CACHE:
            cache_age = time.time() - _CACHE_TIMESTAMP.get(ticker_symbol, 0)
            if cache_age < CACHE_DURATION:
                cached_data = _TICKER_DATA_CACHE[ticker_symbol]
                self._info = cached_data.get('info')
                self._financials = cached_data.get('financials')
                self._balance_sheet = cached_data.get('balance_sheet')
                self._cashflow = cached_data.get('cashflow')
                self._history = cached_data.get('history')
                self._loaded = True
    
    def _ensure_loaded(self):
        """Lazy load ticker data on first access"""
        if not self._loaded:
            try:
                self._ticker_obj = yf.Ticker(self.symbol)
                # Fetch all data at once to minimize API calls
                self._info = self._ticker_obj.info
                self._financials = self._ticker_obj.financials
                self._balance_sheet = self._ticker_obj.balance_sheet
                self._cashflow = self._ticker_obj.cashflow
                self._loaded = True
                
                # Cache the data
                _TICKER_DATA_CACHE[self.symbol] = {
                    'info': self._info,
                    'financials': self._financials,
                    'balance_sheet': self._balance_sheet,
                    'cashflow': self._cashflow,
                    'history': self._history
                }
                _CACHE_TIMESTAMP[self.symbol] = time.time()
            except Exception as e:
                # Return empty data on error
                self._info = {}
                self._financials = pd.DataFrame()
                self._balance_sheet = pd.DataFrame()
                self._cashflow = pd.DataFrame()
                raise e
    
    @property
    def info(self):
        """Get cached info or fetch if needed"""
        if self._info is None:
            self._ensure_loaded()
        return self._info if self._info is not None else {}
    
    @property
    def financials(self):
        """Get cached financials or fetch if needed"""
        if self._financials is None:
            self._ensure_loaded()
        return self._financials if self._financials is not None else pd.DataFrame()
    
    @property
    def balance_sheet(self):
        """Get cached balance sheet or fetch if needed"""
        if self._balance_sheet is None:
            self._ensure_loaded()
        return self._balance_sheet if self._balance_sheet is not None else pd.DataFrame()
    
    @property
    def cashflow(self):
        """Get cached cashflow or fetch if needed"""
        if self._cashflow is None:
            self._ensure_loaded()
        return self._cashflow if self._cashflow is not None else pd.DataFrame()
    
    def history(self, *args, **kwargs):
        """Get historical data - cache by parameters"""
        cache_key = f"{self.symbol}_history_{str(args)}_{str(kwargs)}"
        
        if cache_key in _TICKER_DATA_CACHE:
            cache_age = time.time() - _CACHE_TIMESTAMP.get(cache_key, 0)
            if cache_age < CACHE_DURATION:
                return _TICKER_DATA_CACHE[cache_key]
        
        # Fetch new history
        if self._ticker_obj is None:
            self._ticker_obj = yf.Ticker(self.symbol)
        
        hist_data = self._ticker_obj.history(*args, **kwargs)
        
        # Cache it
        _TICKER_DATA_CACHE[cache_key] = hist_data
        _CACHE_TIMESTAMP[cache_key] = time.time()
        
        return hist_data

def get_cached_ticker(ticker_symbol, force_refresh=False):
    """
    Get cached ticker data wrapper
    This returns a CachedTickerData object that caches .info, .financials, etc.
    to prevent rate limits from repeated API calls
    """
    return CachedTickerData(ticker_symbol, force_refresh)

def clear_ticker_cache():
    """Clear the ticker data cache"""
    global _TICKER_DATA_CACHE, _CACHE_TIMESTAMP
    _TICKER_DATA_CACHE = {}
    _CACHE_TIMESTAMP = {}


# ================================

# ================================

# Helper function for ticker exchange suffix
def get_currency_symbol(info_dict):
    """
    Return the correct currency symbol for a Yahoo Finance info dict.
    Defaults to ₹ for INR (Indian stocks), otherwise uses the ISO code
    wrapped neatly (e.g. '$', '€', 'CNY ', 'USD ').
    """
    _SYMBOLS = {
        'INR': '₹',
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'JPY': '¥',
        'CNY': '¥',
        'HKD': 'HK$',
        'SGD': 'S$',
        'AUD': 'A$',
        'CAD': 'C$',
        'CHF': 'CHF ',
        'KRW': '₩',
        'TWD': 'NT$',
        'BRL': 'R$',
    }
    if not info_dict:
        return '₹'
    # yfinance exposes 'currency' (price currency) and 'financialCurrency' (statement currency)
    ccy = info_dict.get('currency') or info_dict.get('financialCurrency') or 'INR'
    return _SYMBOLS.get(ccy.upper(), f'{ccy} ')

def get_ticker_with_exchange(ticker, exchange_suffix):
    """Add exchange suffix to ticker. If suffix is empty or ticker already has one, return as-is."""
    ticker = ticker.strip().upper()
    # Already has a recognised suffix — leave it alone
    known = ('.NS', '.BO', '.L', '.SS', '.HK', '.DE', '.F', '.KS', '.TW', '.SI', '.AX', '.TO', '.V')
    if any(ticker.endswith(s) for s in known):
        return ticker
    if not exchange_suffix:          # NASDAQ/NYSE / Other — bare ticker is correct
        return ticker
    return f"{ticker}.{exchange_suffix}"

# PDF EXPORT FUNCTIONS (EMBEDDED)
# ================================
class PageNumCanvas(canvas.Canvas):
    """Custom canvas to add page numbers and headers"""
    
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self.pages = []
        
    def showPage(self):
        self.pages.append(dict(self.__dict__))
        self._startPage()
        
    def save(self):
        page_count = len(self.pages)
        for page_num, page in enumerate(self.pages, 1):
            self.__dict__.update(page)
            if page_num > 1:  # Skip page number on cover
                self.draw_page_number(page_num - 1, page_count - 1)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)
        
    def draw_page_number(self, page_num, page_count):
        """Add page number at bottom"""
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.grey)
        self.drawRightString(
            7.5*inch, 0.5*inch,
            f"Page {page_num} of {page_count}"
        )


def save_plotly_as_image(fig, width=1400, height=600):
    """Convert plotly figure to image bytes for PDF"""
    try:
        img_bytes = fig.to_image(format="png", width=width, height=height, scale=2)
        return img_bytes
    except Exception as e:
        print(f"Error converting chart: {e}")
        return None


def create_fair_value_chart(fair_values, current_price=None):
    """Create the fair value comparison bar chart"""
    methods = list(fair_values.keys())
    values = list(fair_values.values())
    
    colors_map = {
        'DCF': '#06A77D',
        'P/E': '#2E86AB',
        'P/B': '#4ECDC4',
        'P/S': '#FF6B6B',
        'EV/EBITDA': '#95E1D3',
        'DDM': '#F38181',
        'Residual Income': '#AA96DA'
    }
    
    bar_colors = [colors_map.get(m.split()[0], '#A8DADC') for m in methods]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=methods,
        y=values,
        marker=dict(color=bar_colors, line=dict(color='white', width=2)),
        text=[f"₹{v:.2f}" for v in values],
        textposition='outside',
        showlegend=False
    ))
    
    avg_value = np.mean(values)
    fig.add_hline(y=avg_value, line_dash="dash", line_color="red",
                  annotation_text=f"Average: ₹{avg_value:.2f}")
    
    if current_price and current_price > 0:
        fig.add_hline(y=current_price, line_dash="dot", line_color="blue",
                      annotation_text=f"Current: ₹{current_price:.2f}")
    
    fig.update_layout(
        title="Fair Value Comparison - All Methods",
        xaxis_title="Valuation Method",
        yaxis_title="Fair Value (₹)",
        height=500,
        showlegend=False,
        plot_bgcolor='white',
        font=dict(size=12)
    )
    
    fig.update_xaxes(tickangle=-45)
    
    return fig


def create_peer_heatmap(peer_data, target_ticker):
    """Create peer comparison heatmap"""
    if peer_data.empty:
        return None
    
    # Prepare data for heatmap
    metrics = ['pe', 'pb', 'ps', 'ev_ebitda']
    display_names = ['P/E', 'P/B', 'P/S', 'EV/EBITDA']
    
    heat_data = []
    companies = []
    
    for _, row in peer_data.iterrows():
        companies.append(row.get('name', row.get('ticker', 'Unknown')))
        heat_data.append([row.get(m, 0) for m in metrics])
    
    heat_array = np.array(heat_data).T
    
    # Normalize to percentiles
    heat_normalized = np.zeros_like(heat_array)
    for i in range(len(heat_array)):
        heat_normalized[i] = np.argsort(np.argsort(heat_array[i])) / (len(heat_array[i]) - 1) * 100
    
    fig = go.Figure(data=go.Heatmap(
        z=heat_normalized,
        x=companies,
        y=display_names,
        text=heat_array,
        texttemplate='%{text:.2f}x',
        textfont={"size": 10},
        colorscale=[
            [0, '#06A77D'],
            [0.5, '#F4D35E'],
            [1, '#D62828']
        ],
        colorbar=dict(title="Percentile")
    ))
    
    fig.update_layout(
        title="Peer Valuation Multiples Heatmap",
        height=400,
        xaxis_title="Company",
        yaxis_title="Multiple"
    )
    
    return fig


def create_spider_chart(target_multiples, peer_medians):
    """Create spider/radar chart comparing target vs peers"""
    categories = list(target_multiples.keys())
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatterpolar(
        r=list(target_multiples.values()),
        theta=categories,
        fill='toself',
        name='Target Company',
        line=dict(color='#D62828', width=2)
    ))
    
    fig.add_trace(go.Scatterpolar(
        r=list(peer_medians.values()),
        theta=categories,
        fill='toself',
        name='Peer Median',
        line=dict(color='#2E86AB', width=2)
    ))
    
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True)),
        showlegend=True,
        title="Target vs Peer Median - Valuation Multiples",
        height=500
    )
    
    return fig


def generate_professional_pdf(data_package, output_path=None):
    """
    Generate professional PDF report
    
    Parameters:
    -----------
    data_package : dict
        {
            'company_name': str,
            'ticker': str,
            'current_price': float,
            'financials': dict,
            'dcf_results': dict,
            'fair_values': dict,
            'peer_data': pd.DataFrame,
            'comp_results': dict (optional)
        }
    
    Returns:
    --------
    str : Path to generated PDF
    """
    
    # Extract data
    company_name = data_package.get('company_name', 'Company')
    ticker = data_package.get('ticker', 'TICKER')
    current_price = data_package.get('current_price', 0)
    financials = data_package.get('financials', {})
    dcf_results = data_package.get('dcf_results', {})
    fair_values = data_package.get('fair_values', {})
    peer_data = data_package.get('peer_data', pd.DataFrame())
    comp_results = data_package.get('comp_results')
    
    # Create output path
    if not output_path:
        temp_dir = tempfile.gettempdir()
        output_path = os.path.join(temp_dir, f"{ticker}_Professional_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
    
    # Create PDF document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=1*inch,
        bottomMargin=0.75*inch
    )
    
    # Styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='CoverTitle',
        parent=styles['Heading1'],
        fontSize=36,
        textColor=HexColor('#2E86AB'),
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=20
    ))
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=HexColor('#2E86AB'),
        spaceAfter=12,
        spaceBefore=12
    ))
    styles.add(ParagraphStyle(
        name='SubHeader',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=HexColor('#06A77D'),
        spaceAfter=8
    ))
    
    story = []
    
    # ==========================================
    # COVER PAGE
    # ==========================================
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("DCF VALUATION REPORT", styles['CoverTitle']))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(f"<b>{company_name}</b>", styles['Heading1']))
    story.append(Paragraph(f"Ticker: {ticker}", styles['Normal']))
    story.append(Spacer(1, 1*inch))
    story.append(Paragraph(
        f"<para align=center>Report Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</para>",
        styles['Normal']
    ))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(
        "<para align=center><i>Professional Discounted Cash Flow Analysis</i></para>",
        styles['Normal']
    ))
    story.append(PageBreak())
    
    # ==========================================
    # EXECUTIVE SUMMARY
    # ==========================================
    story.append(Paragraph("EXECUTIVE SUMMARY", styles['SectionHeader']))
    story.append(Spacer(1, 0.2*inch))
    
    avg_fv = np.mean([v for v in fair_values.values() if v and v > 0]) if fair_values else 0
    upside = ((avg_fv - current_price) / current_price * 100) if current_price > 0 else 0
    
    # Key metrics table
    summary_data = [
        ['Metric', 'Value', 'Details'],
        ['Current Market Price', f"₹{current_price:.2f}" if current_price > 0 else "N/A (Unlisted)", 
         'Latest trading price' if current_price > 0 else 'Private company'],
        ['DCF Fair Value', f"₹{dcf_results.get('fair_value_per_share', 0):.2f}", 
         'Intrinsic value from DCF model'],
        ['Average Fair Value', f"₹{avg_fv:.2f}", 
         f'Average of {len(fair_values)} valuation methods'],
        ['Upside Potential', f"{upside:+.1f}%", 
         'Potential gain/loss from current price']
    ]
    
    summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch, 3*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#F5F5F5')])
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Recommendation
    if upside > 15:
        recommendation = "STRONG BUY"
        rec_color = HexColor('#06A77D')
    elif upside > 0:
        recommendation = "BUY / HOLD"
        rec_color = HexColor('#F4D35E')
    else:
        recommendation = "HOLD / SELL"
        rec_color = HexColor('#D62828')
    
    rec_style = ParagraphStyle(
        'Recommendation',
        parent=styles['Normal'],
        fontSize=16,
        textColor=rec_color,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    story.append(Paragraph(f"<b>Investment Recommendation: {recommendation}</b>", rec_style))
    story.append(PageBreak())
    
    # ==========================================
    # HISTORICAL FINANCIALS
    # ==========================================
    if financials and 'years' in financials:
        story.append(Paragraph("HISTORICAL FINANCIAL ANALYSIS", styles['SectionHeader']))
        story.append(Spacer(1, 0.2*inch))
        
        years = financials['years']
        
        # Financial metrics table
        fin_data = [['Metric'] + [str(y) for y in years]]
        
        metrics_map = {
            'Revenue (₹ Lacs)': 'revenue',
            'EBITDA (₹ Lacs)': 'ebitda',
            'EBIT (₹ Lacs)': 'ebit',
            'NOPAT (₹ Lacs)': 'nopat',
            'Free Cash Flow (₹ Lacs)': 'fcf',
            'CAPEX (₹ Lacs)': 'capex'
        }
        
        for label, key in metrics_map.items():
            if key in financials:
                values = financials[key]
                row = [label] + [f"₹{v:,.0f}" for v in values]
                fin_data.append(row)
        
        # Growth rates
        if 'revenue' in financials and len(financials['revenue']) > 1:
            revenues = financials['revenue']
            growth_rates = []
            for i in range(1, len(revenues)):
                growth = ((revenues[i] - revenues[i-1]) / revenues[i-1]) * 100
                growth_rates.append(f"{growth:.1f}%")
            fin_data.append(['Revenue Growth (YoY)'] + ['—'] + growth_rates)
        
        fin_table = Table(fin_data, colWidths=[2.5*inch] + [1.2*inch] * len(years))
        fin_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#F5F5F5')])
        ]))
        
        story.append(fin_table)
        story.append(PageBreak())
    
    # ==========================================
    # DCF VALUATION BREAKDOWN
    # ==========================================
    if dcf_results:
        story.append(Paragraph("DCF VALUATION METHODOLOGY", styles['SectionHeader']))
        story.append(Spacer(1, 0.2*inch))
        
        story.append(Paragraph("Key Assumptions", styles['SubHeader']))
        
        assumptions_data = [
            ['Parameter', 'Value', 'Description'],
            ['WACC', f"{dcf_results.get('wacc', 0)*100:.2f}%", 'Weighted Average Cost of Capital'],
            ['Terminal Growth Rate', f"{dcf_results.get('terminal_growth_rate', 0)*100:.2f}%", 'Perpetual growth assumption'],
            ['Forecast Period', f"{dcf_results.get('forecast_years', 5)} years", 'Explicit forecast period'],
            ['Tax Rate', f"{dcf_results.get('tax_rate', 0)*100:.2f}%", 'Corporate tax rate']
        ]
        
        assumptions_table = Table(assumptions_data, colWidths=[2*inch, 1.5*inch, 3*inch])
        assumptions_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#06A77D')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#F5F5F5')])
        ]))
        
        story.append(assumptions_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Valuation results
        story.append(Paragraph("Valuation Results", styles['SubHeader']))
        
        valuation_data = [
            ['Component', 'Value (₹ Lacs)', 'Per Share (₹)'],
            ['Enterprise Value', f"{dcf_results.get('enterprise_value', 0):,.2f}", '—'],
            ['Less: Net Debt', f"{dcf_results.get('net_debt', 0):,.2f}", '—'],
            ['Equity Value', f"{dcf_results.get('equity_value', 0):,.2f}", '—'],
            ['Shares Outstanding', f"{dcf_results.get('shares', 0):,.0f}", '—'],
            ['Fair Value per Share', '—', f"₹{dcf_results.get('fair_value_per_share', 0):.2f}"]
        ]
        
        valuation_table = Table(valuation_data, colWidths=[2.5*inch, 2*inch, 2*inch])
        valuation_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#2E86AB')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), HexColor('#E8F4F8')),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, HexColor('#F5F5F5')])
        ]))
        
        story.append(valuation_table)
        story.append(PageBreak())
    
    # ==========================================
    # FAIR VALUE COMPARISON CHART
    # ==========================================
    if fair_values:
        story.append(Paragraph("FAIR VALUE ANALYSIS", styles['SectionHeader']))
        story.append(Spacer(1, 0.2*inch))
        
        # Create and add fair value chart
        fv_chart = create_fair_value_chart(fair_values, current_price)
        fv_img = save_plotly_as_image(fv_chart, width=1400, height=600)
        
        if fv_img:
            img = RLImage(io.BytesIO(fv_img), width=6.5*inch, height=3*inch)
            story.append(KeepTogether([img]))
            story.append(Spacer(1, 0.2*inch))
        
        # Summary statistics
        values = [v for v in fair_values.values() if v and v > 0]
        stats_data = [
            ['Statistic', 'Value'],
            ['Minimum', f"₹{min(values):.2f}"],
            ['Maximum', f"₹{max(values):.2f}"],
            ['Average', f"₹{np.mean(values):.2f}"],
            ['Median', f"₹{np.median(values):.2f}"],
            ['Std Deviation', f"₹{np.std(values):.2f}"]
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 3*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#06A77D')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#F5F5F5')])
        ]))
        
        story.append(stats_table)
        story.append(PageBreak())
    
    # ==========================================
    # PEER COMPARISON (if available)
    # ==========================================
    if comp_results and not peer_data.empty:
        story.append(Paragraph("PEER COMPARISON ANALYSIS", styles['SectionHeader']))
        story.append(Spacer(1, 0.2*inch))
        
        # Peer heatmap
        heatmap = create_peer_heatmap(peer_data, ticker)
        if heatmap:
            heatmap_img = save_plotly_as_image(heatmap, width=1400, height=500)
            if heatmap_img:
                img = RLImage(io.BytesIO(heatmap_img), width=6.5*inch, height=2.5*inch)
                story.append(KeepTogether([img]))
                story.append(Spacer(1, 0.3*inch))
        
        # Spider chart if we have target multiples
        if comp_results.get('target'):
            target = comp_results['target']
            target_multiples = {
                'P/E': target.get('pe', 0),
                'P/B': target.get('pb', 0),
                'P/S': target.get('ps', 0),
                'EV/EBITDA': target.get('ev_ebitda', 0)
            }
            
            peer_medians = {
                'P/E': comp_results['multiples_stats'].get('pe', {}).get('median', 0),
                'P/B': comp_results['multiples_stats'].get('pb', {}).get('median', 0),
                'P/S': comp_results['multiples_stats'].get('ps', {}).get('median', 0),
                'EV/EBITDA': comp_results['multiples_stats'].get('ev_ebitda', {}).get('median', 0)
            }
            
            spider = create_spider_chart(target_multiples, peer_medians)
            spider_img = save_plotly_as_image(spider, width=1400, height=600)
            
            if spider_img:
                img = RLImage(io.BytesIO(spider_img), width=6.5*inch, height=3*inch)
                story.append(KeepTogether([img]))
        
        story.append(PageBreak())
    
    # ==========================================
    # CONCLUSION
    # ==========================================
    story.append(Paragraph("CONCLUSION & RECOMMENDATIONS", styles['SectionHeader']))
    story.append(Spacer(1, 0.2*inch))
    
    conclusion_text = f"""
    Based on comprehensive discounted cash flow analysis and relative valuation methodologies, 
    the estimated fair value for <b>{company_name}</b> ({ticker}) is <b>₹{avg_fv:.2f}</b> per share.
    """
    
    if current_price > 0:
        conclusion_text += f"""
        <br/><br/>
        The current market price of ₹{current_price:.2f} represents a <b>{upside:+.1f}%</b> 
        {'discount to' if upside > 0 else 'premium to'} our fair value estimate.
        <br/><br/>
        <b>Investment Recommendation: {recommendation}</b>
        """
    
    conclusion_text += """
    <br/><br/>
    <i>Risk Factors:</i>
    <br/>
    • Market volatility and macroeconomic conditions
    <br/>
    • Changes in industry dynamics and competitive landscape
    <br/>
    • Execution risks in business strategy
    <br/>
    • Regulatory and policy changes
    <br/><br/>
    <i>Disclaimer: This valuation is for informational purposes only and should not be 
    considered as investment advice. Please consult with a qualified financial advisor 
    before making investment decisions.</i>
    """
    
    story.append(Paragraph(conclusion_text, styles['Normal']))
    
    # Build PDF
    doc.build(story, canvasmaker=PageNumCanvas)
    
    return output_path


# Convenience function for easy import
def export_to_pdf(data_package):
    """
    Simple wrapper function for PDF generation
    
    Usage:
        from pdf_exporter import export_to_pdf
        
        pdf_path = export_to_pdf({
            'company_name': 'Reliance Industries',
            'ticker': 'RELIANCE',
            'current_price': 2500,
            'financials': financials_dict,
            'dcf_results': dcf_dict,
            'fair_values': {'DCF': 2600, 'P/E': 2550},
            'peer_data': peer_df,
            'comp_results': comp_dict
        })
    
    Returns:
        str: Path to generated PDF file
    """
    return generate_professional_pdf(data_package)



# STREAMLIT UI
# ================================

# Initialize session state for rate limiting
if 'last_yahoo_request' not in st.session_state:
    st.session_state.last_yahoo_request = 0

if 'yahoo_request_count' not in st.session_state:
    st.session_state.yahoo_request_count = 0

if 'session_start_time' not in st.session_state:
    import time
    st.session_state.session_start_time = time.time()

# Reset counter every hour
import time
if time.time() - st.session_state.session_start_time > 3600:
    st.session_state.yahoo_request_count = 0
    st.session_state.session_start_time = time.time()

# Fix text truncation in metrics and throughout the app
st.markdown("""
    <style>
    /* Fix metric value truncation */
    [data-testid="stMetricValue"] {
        width: fit-content;
        white-space: nowrap;
        overflow: visible !important;
        text-overflow: clip !important;
    }
    
    /* Fix metric label truncation */
    [data-testid="stMetricLabel"] {
        width: fit-content;
        white-space: nowrap;
        overflow: visible !important;
        text-overflow: clip !important;
    }
    
    /* Fix metric container */
    [data-testid="metric-container"] {
        overflow: visible !important;
        width: fit-content;
        min-width: max-content;
    }
    
    /* Fix metric delta truncation */
    [data-testid="stMetricDelta"] {
        white-space: nowrap;
        overflow: visible !important;
    }
    
    /* General fix for all div elements in columns */
    [data-testid="column"] > div {
        overflow: visible !important;
    }
    
    /* Ensure proper spacing for columns */
    [data-testid="column"] {
        overflow: visible !important;
        min-width: fit-content;
    }
    </style>
    """, unsafe_allow_html=True)


# UTILITY FUNCTIONS
# ================================


# Auto peer fetching utility - MANDATORY
try:
    from app.logic.utils_peer_fetcher import get_industry_peers
    PEER_FETCHER_AVAILABLE = True
except Exception as e:
    PEER_FETCHER_AVAILABLE = False
    print(f"[DCF] ERROR: Peer fetcher not available: {e}")

def sanitize_value(val):
    """Convert string values to float, handling various formats"""
    if pd.isna(val) or val == '' or val == '-':
        return 0.0
    try:
        return float(str(val).replace(',', ''))
    except:
        return 0.0

def safe_extract(data, key, year, default=0.0):
    """
    ROBUST EXTRACTOR: Safely extract value from DataFrame/dict, handling None/NaN/missing data
    
    This is THE solution to the VEDL/TATAMOTORS None-value problem.
    Returns 0.0 instead of None to prevent NaN cascading through calculations.
    
    Args:
        data: DataFrame or dict containing financial data
        key: Row index or dictionary key to extract
        year: Column name (for DataFrame) or nested key
        default: Default value if extraction fails (default: 0.0)
    
    Returns:
        float: Extracted value or default (never None or NaN)
    """
    try:
        if isinstance(data, pd.DataFrame):
            if key in data.index and year in data.columns:
                val = data.loc[key, year]
                # Handle None, NaN, inf
                if val is None or pd.isna(val) or np.isinf(val):
                    return default
                return abs(float(val))
            return default
        elif isinstance(data, dict):
            val = data.get(key, default)
            if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
                return default
            return abs(float(val))
        return default
    except Exception:
        return default

def safe_divide(numerator, denominator, default=0.0):
    """
    ROBUST DIVISION: Safely divide two numbers, handling None/NaN/zero division
    
    Args:
        numerator: Number to divide
        denominator: Number to divide by
        default: Default value if division fails (default: 0.0)
    
    Returns:
        float: Result of division or default (never None or NaN)
    """
    try:
        # Handle None inputs
        if numerator is None or denominator is None:
            return default
        
        # Convert to float and check for NaN/inf
        num = float(numerator)
        den = float(denominator)
        
        if np.isnan(num) or np.isinf(num) or np.isnan(den) or np.isinf(den):
            return default
        
        # Handle zero denominator
        if den == 0:
            return default
        
        result = num / den
        
        # Check result validity
        if np.isnan(result) or np.isinf(result):
            return default
        
        return result
    except Exception:
        return default

def ensure_valid_number(val, default=0.0):
    """
    ROBUST VALIDATOR: Ensure a value is a valid number (not None, NaN, or inf)
    
    Args:
        val: Value to validate
        default: Default value if validation fails (default: 0.0)
    
    Returns:
        float: Valid number or default (never None or NaN)
    """
    try:
        if val is None:
            return default
        
        num = float(val)
        
        if np.isnan(num) or np.isinf(num):
            return default
        
        return num
    except Exception:
        return default

def parse_excel_to_dataframes(excel_file):
    """Parse Excel file and extract Balance Sheet and P&L as DataFrames"""
    try:
        # Read both sheets from Excel
        df_bs = pd.read_excel(excel_file, sheet_name='BalanceSheet', header=None)
        df_pl = pd.read_excel(excel_file, sheet_name='Profit&Loss', header=None)
        
        # Set first column as 'Item' and rest as year columns
        # Column 0 = Item names, Columns 1,2,3... = Year data
        
        # Extract header row (first row contains year numbers)
        bs_years = df_bs.iloc[0, 1:].values  # Get year values from first row
        pl_years = df_pl.iloc[0, 1:].values
        
        # Create column names: 'Item' for first column, '_XX' for year columns
        bs_columns = ['Item'] + [f'_{int(year)}' if pd.notna(year) else f'_col{i}' 
                                  for i, year in enumerate(bs_years, 1)]
        pl_columns = ['Item'] + [f'_{int(year)}' if pd.notna(year) else f'_col{i}' 
                                  for i, year in enumerate(pl_years, 1)]
        
        # Remove header row and set column names
        df_bs = df_bs.iloc[1:].copy()  # Skip header row
        df_bs.columns = bs_columns
        
        df_pl = df_pl.iloc[1:].copy()
        df_pl.columns = pl_columns
        
        # Reset index
        df_bs = df_bs.reset_index(drop=True)
        df_pl = df_pl.reset_index(drop=True)
        
        # Convert year columns to numeric (sanitize values)
        for col in df_bs.columns[1:]:  # Skip 'Item' column
            df_bs[col] = df_bs[col].apply(sanitize_value)
        
        for col in df_pl.columns[1:]:
            df_pl[col] = df_pl[col].apply(sanitize_value)
        
        # Remove rows where Item is NaN or empty
        df_bs = df_bs[df_bs['Item'].notna() & (df_bs['Item'] != '')]
        df_pl = df_pl[df_pl['Item'].notna() & (df_pl['Item'] != '')]
        
        return df_bs, df_pl
        
    except Exception as e:
        st.error(f"Error parsing Excel: {str(e)}")
        return None, None

def get_value_from_df(df, item_name, year_col):
    """Extract value from DataFrame by item name (case-insensitive partial match)"""
    if df is None or df.empty:
        return 0.0
    
    item_name_lower = item_name.lower()
    mask = df['Item'].str.lower().str.contains(item_name_lower, na=False, regex=False)
    matching = df[mask]
    
    if not matching.empty and year_col in matching.columns:
        return matching.iloc[0][year_col]
    return 0.0

def detect_year_columns(df):
    """Detect year columns dynamically (columns starting with _)"""
    if df is None or df.empty:
        return []
    
    year_cols = [col for col in df.columns if col.startswith('_') and col != 'Item']
    # Sort by numeric value after underscore
    year_cols.sort(key=lambda x: int(x[1:]) if x[1:].isdigit() else 0)
    return year_cols

# ================================
# BUSINESS MODEL CLASSIFICATION (RULEBOOK COMPLIANT)
# ================================

def classify_business_model(financials, income_stmt=None, balance_sheet=None):
    """
    Classify company as OPERATING or INTEREST-DOMINANT per Rulebook Section 2.
    
    Returns:
        dict: {
            'type': 'OPERATING' or 'INTEREST_DOMINANT',
            'criteria_met': list of criteria that triggered classification,
            'metrics': dict of calculated ratios
        }
    """
    criteria_met = []
    metrics = {}
    
    # Calculate 3-year averages for classification
    try:
        # Method 1: From extracted financials dict
        if financials and 'revenue' in financials and 'interest' in financials:
            revenues = financials['revenue']
            interest_expenses = financials['interest']
            
            # Get interest income if available (from additional fields)
            interest_income = financials.get('interest_income', [0] * len(revenues))
            
            # Calculate averages
            avg_revenue = np.mean(revenues) if revenues else 0
            avg_interest_expense = np.mean(interest_expenses) if interest_expenses else 0
            avg_interest_income = np.mean(interest_income) if interest_income else 0
            
            # Criterion 1: Interest Income / Total Revenue ≥ 50%
            if avg_revenue > 0:
                interest_income_ratio = (avg_interest_income / avg_revenue) * 100
                metrics['interest_income_ratio'] = interest_income_ratio
                if interest_income_ratio >= 50:
                    criteria_met.append(f"Interest Income / Revenue = {interest_income_ratio:.1f}% (≥50%)")
            
            # Criterion 2: Interest Expense / Total Expenses ≥ 40%
            # Total Expenses = COGS + Opex + Interest + Depreciation
            total_expenses = []
            for i in range(len(revenues)):
                exp = (financials.get('cogs', [0]*len(revenues))[i] + 
                       financials.get('opex', [0]*len(revenues))[i] + 
                       interest_expenses[i] +
                       financials.get('depreciation', [0]*len(revenues))[i])
                total_expenses.append(exp)
            
            avg_total_expenses = np.mean(total_expenses) if total_expenses else 0
            if avg_total_expenses > 0:
                interest_expense_ratio = (avg_interest_expense / avg_total_expenses) * 100
                metrics['interest_expense_ratio'] = interest_expense_ratio
                if interest_expense_ratio >= 40:
                    criteria_met.append(f"Interest Expense / Total Expenses = {interest_expense_ratio:.1f}% (≥40%)")
        
        # Method 2: Check raw statements for Net Interest Income presence
        if income_stmt is not None:
            nii_fields = ['Net Interest Income', 'Net Interest Margin', 'Interest Income Net']
            for field in nii_fields:
                if field in income_stmt.index:
                    criteria_met.append(f"Presence of '{field}' line item")
                    break
        
        # Method 3: Balance sheet structure check
        if balance_sheet is not None:
            # Check for lending business indicators
            lending_indicators = ['Loans', 'Advances', 'Loans And Advances', 'Net Loans']
            financial_assets = ['Financial Assets', 'Investment Securities']
            
            for indicator in lending_indicators + financial_assets:
                if indicator in balance_sheet.index:
                    # Check if it's a significant portion
                    if 'Total Assets' in balance_sheet.index:
                        try:
                            asset_val = abs(balance_sheet.loc[indicator, balance_sheet.columns[0]])
                            total_assets = abs(balance_sheet.loc['Total Assets', balance_sheet.columns[0]])
                            if total_assets > 0 and (asset_val / total_assets) > 0.5:
                                criteria_met.append(f"Balance Sheet dominated by {indicator} ({asset_val/total_assets*100:.1f}% of assets)")
                        except:
                            pass
    
    except Exception as e:
        st.warning(f"Classification warning: {str(e)}")
    
    # Decision: INTEREST-DOMINANT if 2+ criteria met
    is_interest_dominant = len(criteria_met) >= 2
    
    classification = {
        'type': 'INTEREST_DOMINANT' if is_interest_dominant else 'OPERATING',
        'criteria_met': criteria_met,
        'metrics': metrics
    }
    
    return classification

def validate_fcff_eligibility(classification):
    """
    Check if FCFF DCF is valid per Rulebook Section 3.
    Returns: (is_valid: bool, reason: str)
    """
    if classification['type'] == 'INTEREST_DOMINANT':
        return False, "🚫 FCFF DCF is NOT VALID for Interest-Dominant entities. Debt is operating raw material, not financing."
    
    return True, "✅ FCFF DCF is valid for Operating Companies"

def show_classification_warning(classification):
    """Display business model classification and restrictions"""
    if classification['type'] == 'INTEREST_DOMINANT':
        st.error("""
        🚫 **INTEREST-DOMINANT ENTITY DETECTED**
        
        This company derives significant income from interest operations (lending/banking).
        
        **Why FCFF DCF is Invalid:**
        - Interest expense = Operating Cost (like COGS), not financing cost
        - Interest income = Revenue
        - Debt = Operating raw material (inventory equivalent)
        - EBIT/NOPAT/WACC are economically meaningless
        
        **Criteria Met:**
        """)
        for criterion in classification['criteria_met']:
            st.write(f"  • {criterion}")
        
        st.info("""
        **Recommended Valuation Methods:**
        - ✅ Residual Income Model (preferred)
        - ✅ Dividend Discount Model
        - ✅ P/B with ROE analysis
        - ✅ Relative valuation (P/E, P/B)
        
        ❌ FCFF DCF is blocked to prevent economically invalid valuation.
        """)
        
        return True  # Should stop execution
    
    else:
        st.success(f"""
        ✅ **OPERATING COMPANY CLASSIFICATION**
        
        FCFF DCF valuation is appropriate for this company.
        """)
        
        if classification['criteria_met']:
            with st.expander("ℹ️ Classification Details"):
                st.write("The following interest-related metrics were detected but did not exceed thresholds:")
                for criterion in classification['criteria_met']:
                    st.write(f"  • {criterion}")
        
        return False  # Can continue

# ================================
# BANK VALUATION METHODS
# ================================

def calculate_residual_income_model(financials, shares, cost_of_equity, terminal_growth=3.5, projection_years=5, assumed_roe=None, dcf_projections=None):
    """
    Residual Income Model - Suitable for both banks and non-banking companies
    RI = Net Income - (Cost of Equity × Book Value of Equity)
    Value = Book Value + PV(Future Residual Income)
    
    Particularly effective for:
    - Companies with stable book value
    - Banks and financial institutions
    - Asset-heavy businesses
    
    Args:
        terminal_growth: Terminal growth rate (default 3.5%)
        projection_years: Years to project (default 5)
        assumed_roe: Override ROE if provided
        dcf_projections: DCF projections dict with 'nopat' key - if provided, uses projected NOPAT as Net Income (NO DUPLICATION!)
    """
    try:
        # Validation checks with specific error messages
        if 'equity' not in financials or len(financials['equity']) == 0:
            return {
                'error': True,
                'reason': 'No equity (book value) data available',
                'suggestion': 'RIM requires balance sheet equity data. Use DCF or DDM instead.'
            }
        
        # Get latest data - USE NEWEST (index 0, not -1)
        latest_equity = financials['equity'][0] * 100000  # Convert from Lacs to Rupees
        
        if latest_equity <= 0:
            return {
                'error': True,
                'reason': f'Company has negative or zero book value (₹{latest_equity:,.0f})',
                'suggestion': 'RIM requires positive equity. This company may be distressed. Use DCF instead.'
            }
        
        # Calculate average ROE
        net_incomes = []
        equities = []
        for i in range(len(financials['years'])):
            # Approximate net income from NOPAT (banks don't really have NOPAT, using as proxy)
            ni = financials['nopat'][i] * 100000
            eq = financials['equity'][i] * 100000
            net_incomes.append(ni)
            equities.append(eq)
        
        avg_net_income = np.mean(net_incomes)
        
        if avg_net_income <= 0:
            return {
                'error': True,
                'reason': f'Company has negative average net income (₹{avg_net_income:,.0f} Lacs)',
                'suggestion': 'RIM requires profitable companies. This company is loss-making. Use DCF or asset-based valuation.'
            }
        
        # Use provided ROE or calculate
        if assumed_roe:
            roe = assumed_roe
        else:
            roe = (avg_net_income / latest_equity * 100) if latest_equity > 0 else 15
        
        if roe < 0:
            return {
                'error': True,
                'reason': f'Company has negative ROE ({roe:.1f}%)',
                'suggestion': 'RIM requires positive ROE. Company is destroying shareholder value. Use DCF instead.'
            }
        
        # Calculate historical book value growth rate using CAGR (data newest to oldest)
        if len(equities) > 1 and equities[-1] > 0 and equities[0] > 0:
            num_years = len(equities) - 1
            # Start = oldest (last), End = newest (first)
            bv_growth = ((equities[0] / equities[-1]) ** (1 / num_years) - 1) * 100
            bv_growth = max(-50, min(bv_growth, 150))  # Allow up to 150% growth
        else:
            bv_growth = 10.0  # Default
        
        # Project N years of residual income
        # ✅ USE EXISTING DCF PROJECTIONS IF AVAILABLE - NO DUPLICATION!
        projections = []
        current_bv = latest_equity
        
        if dcf_projections and 'nopat' in dcf_projections and len(dcf_projections['nopat']) >= projection_years:
            # Use projected NOPAT from DCF as Net Income (already calculated!)
            for year in range(1, projection_years + 1):
                projected_nopat_lacs = dcf_projections['nopat'][year-1]  # 0-indexed
                current_ni = projected_nopat_lacs * 100000  # Convert to Rupees
                
                # Book value grows with retained earnings
                # Simplified: BV grows at historical rate
                current_bv = current_bv * (1 + bv_growth / 100)
                
                # Residual income = NI - (Ke × BV)
                ri = current_ni - (cost_of_equity / 100 * current_bv)
                
                # Present value
                pv_ri = ri / ((1 + cost_of_equity / 100) ** year)
                projections.append({
                    'year': year,
                    'book_value': current_bv,
                    'net_income': current_ni,
                    'residual_income': ri,
                    'pv_ri': pv_ri,
                    'source': 'DCF Projected NOPAT'
                })
        else:
            # Fallback: use ROE-based projection
            current_ni = avg_net_income
            for year in range(1, projection_years + 1):
                # Growth in book value
                current_bv = current_bv * (1 + bv_growth / 100)
                current_ni = current_bv * (roe / 100)
                
                # Residual income = NI - (Ke × BV)
                ri = current_ni - (cost_of_equity / 100 * current_bv)
                
                # Present value
                pv_ri = ri / ((1 + cost_of_equity / 100) ** year)
                projections.append({
                    'year': year,
                'book_value': current_bv,
                'net_income': current_ni,
                'residual_income': ri,
                'pv_ri': pv_ri,
                'source': 'ROE-based projection'
            })
        
        # Terminal value of residual income
        if cost_of_equity / 100 > terminal_growth / 100:
            terminal_ri = projections[-1]['residual_income'] * (1 + terminal_growth / 100) / (cost_of_equity / 100 - terminal_growth / 100)
            pv_terminal_ri = terminal_ri / ((1 + cost_of_equity / 100) ** 5)
        else:
            pv_terminal_ri = 0
        
        # Total value = Current BV + Sum of PV(RI) + PV(Terminal RI)
        sum_pv_ri = sum([p['pv_ri'] for p in projections])
        total_equity_value = latest_equity + sum_pv_ri + pv_terminal_ri
        
        value_per_share = total_equity_value / shares if shares > 0 else 0
        book_value_per_share = latest_equity / shares if shares > 0 else 0
        current_eps = avg_net_income / shares if shares > 0 else 0
        
        return {
            'method': 'Residual Income Model',
            'current_book_value': latest_equity,
            'book_value_per_share': book_value_per_share,
            'current_eps': current_eps,
            'roe': roe,
            'bv_growth': bv_growth,
            'cost_of_equity': cost_of_equity,
            'terminal_growth': terminal_growth,
            'projections': projections,
            'sum_pv_ri': sum_pv_ri,
            'terminal_ri_pv': pv_terminal_ri,
            'total_equity_value': total_equity_value,
            'value_per_share': value_per_share,
            'using_dcf_projections': bool(dcf_projections)
        }
    except Exception as e:
        return {
            'error': True,
            'reason': f'Calculation error: {str(e)}',
            'suggestion': 'Check if financial data is complete and valid. Use DCF as primary valuation method.',
            'technical_details': str(e)
        }

def calculate_dividend_discount_model(financials, shares, cost_of_equity, ticker=None, div_growth_override=None, payout_ratio_override=None, dcf_projections=None):
    """
    Dividend Discount Model (Gordon Growth Model)
    Value = D1 / (Ke - g)
    
    Args:
        div_growth_override: Override dividend growth rate
        payout_ratio_override: Override payout ratio
        dcf_projections: DCF projections dict with 'nopat' key - if provided, uses projected NOPAT for dividend projections (NO DUPLICATION!)
    """
    try:
        # Try to fetch actual dividend data from yfinance
        actual_dividends = []
        div_growth_calculated = None
        payout_ratio_calculated = None
        
        if ticker:
            try:
                stock = get_cached_ticker(get_ticker_with_exchange(ticker, exchange_suffix))
                dividends_hist = stock.dividends
                
                if not dividends_hist.empty and len(dividends_hist) > 0:
                    # Get annual dividends for last 3 years
                    dividends_by_year = dividends_hist.resample('Y').sum()
                    if len(dividends_by_year) >= 2:
                        recent_divs = dividends_by_year[-3:].values
                        actual_dividends = recent_divs.tolist()
                        
                        # Calculate growth rate using CAGR (data is newest to oldest)
                        if len(actual_dividends) >= 2 and actual_dividends[-1] > 0 and actual_dividends[0] > 0:
                            num_years = len(actual_dividends) - 1
                            # Start = oldest (last), End = newest (first)
                            div_growth_calculated = ((actual_dividends[0] / actual_dividends[-1]) ** (1 / num_years) - 1) * 100
                            div_growth_calculated = max(-50, min(div_growth_calculated, 150))  # Allow up to 150%
                        
                        # Calculate payout ratio from actual data - USE NEWEST nopat (index 0)
                        latest_div = actual_dividends[-1] if actual_dividends else 0
                        latest_ni = financials['nopat'][0] * 100000
                        if latest_ni > 0 and latest_div > 0:
                            payout_ratio_calculated = (latest_div * shares) / latest_ni
                            payout_ratio_calculated = max(0.1, min(payout_ratio_calculated, 0.9))
            except Exception as e:
                pass
        
        # Calculate average earnings
        net_incomes = []
        for i in range(len(financials['years'])):
            ni = financials['nopat'][i] * 100000
            net_incomes.append(ni)
        
        avg_net_income = np.mean(net_incomes)
        
        # Use overrides or calculated or default values
        if payout_ratio_override:
            payout_ratio = payout_ratio_override / 100
        elif payout_ratio_calculated:
            payout_ratio = payout_ratio_calculated
        else:
            payout_ratio = 0.40
        
        if div_growth_override:
            div_growth = div_growth_override
        elif div_growth_calculated:
            div_growth = div_growth_calculated
        else:
            div_growth = 8.0
        
        # Calculate dividends
        total_dividends = avg_net_income * payout_ratio
        dps = total_dividends / shares if shares > 0 else 0
        
        # If we have actual dividends, use the latest as current DPS
        if actual_dividends:
            dps = actual_dividends[-1]
        
        # Next year dividend
        d1 = dps * (1 + div_growth / 100)
        
        # DDM valuation
        if cost_of_equity <= div_growth:
            return None
        
        value_per_share = d1 / ((cost_of_equity - div_growth) / 100)
        
        # 5-year dividend projection
        # ✅ USE EXISTING DCF PROJECTIONS IF AVAILABLE - NO DUPLICATION!
        projections_list = []
        
        if dcf_projections and 'nopat' in dcf_projections and len(dcf_projections['nopat']) > 0:
            # Use projected NOPAT from DCF (already calculated!)
            for year_idx, projected_nopat_lacs in enumerate(dcf_projections['nopat'], 1):
                projected_ni = projected_nopat_lacs * 100000  # Convert to Rupees
                projected_dividend = projected_ni * payout_ratio
                projected_dps = projected_dividend / shares if shares > 0 else 0
                pv_div = projected_dps / ((1 + cost_of_equity / 100) ** year_idx)
                projections_list.append({
                    'year': year_idx,
                    'dividend': projected_dps,
                    'pv_dividend': pv_div,
                    'source': 'DCF Projected NOPAT'
                })
        else:
            # Fallback: use growth-based projection
            current_div = dps
            for year in range(1, 6):
                current_div = current_div * (1 + div_growth / 100)
                pv_div = current_div / ((1 + cost_of_equity / 100) ** year)
                projections_list.append({
                    'year': year,
                    'dividend': current_div,
                    'pv_dividend': pv_div,
                    'source': 'Growth-based projection'
                })
        
        return {
            'method': 'Dividend Discount Model',
            'current_dps': dps,
            'payout_ratio': payout_ratio * 100,
            'dividend_growth': div_growth,
            'required_return': cost_of_equity,
            'next_year_dps': d1,
            'projections': projections_list,
            'value_per_share': value_per_share,
            'using_actual_data': bool(actual_dividends),
            'using_dcf_projections': bool(dcf_projections),
            'historical_dividends': actual_dividends if actual_dividends else None
        }
    except Exception as e:
        st.error(f"DDM error: {str(e)}")
        return None

def calculate_pb_roe_valuation(financials, shares, cost_of_equity, assumed_roe=None):
    """
    P/B with ROE Analysis
    Fair P/B = ROE / Cost of Equity
    
    Args:
        assumed_roe: Override ROE if provided
    """
    try:
        # Latest book value - USE NEWEST (index 0)
        latest_equity = financials['equity'][0] * 100000
        book_value_per_share = latest_equity / shares if shares > 0 else 0
        
        # Calculate ROE
        net_incomes = []
        equities = []
        for i in range(len(financials['years'])):
            ni = financials['nopat'][i] * 100000
            eq = financials['equity'][i] * 100000
            net_incomes.append(ni)
            equities.append(eq)
        
        avg_net_income = np.mean(net_incomes)
        avg_equity = np.mean(equities)
        
        # Use provided ROE or calculate
        if assumed_roe:
            roe = assumed_roe
        else:
            roe = (avg_net_income / avg_equity * 100) if avg_equity > 0 else 15
        
        # Fair P/B ratio
        fair_pb = roe / cost_of_equity
        
        # Fair value per share
        value_per_share = book_value_per_share * fair_pb
        
        return {
            'method': 'P/B with ROE Analysis',
            'book_value_per_share': book_value_per_share,
            'roe': roe,
            'cost_of_equity': cost_of_equity,
            'fair_pb_ratio': fair_pb,
            'value_per_share': value_per_share,
            'historical_roe': [(net_incomes[i] / equities[i] * 100) for i in range(len(net_incomes))]
        }
    except Exception as e:
        st.error(f"P/B ROE error: {str(e)}")
        return None


def get_auto_peers_or_default(ticker):
    """Get auto peers or fallback to defaults - MANDATORY"""
    if PEER_FETCHER_AVAILABLE:
        try:
            print(f"[DCF] Auto-fetching peers for {ticker}...")
            peers = get_industry_peers(ticker, max_peers=10, exclude_self=True)
            if peers:
                # VERIFY: ticker not in peer list
                ticker_upper = ticker.upper()
                peers = [p for p in peers if p.upper() != ticker_upper]
                peer_str = ",".join(peers)
                print(f"[DCF] ✅ Auto-fetched {len(peers)} peers: {peers[:5]}")
                return peer_str
            else:
                print("[DCF] ⚠️ No peers found, using defaults")
        except Exception as e:
            print(f"[DCF] ⚠️ Error fetching peers: {e}")
    return "HDFCBANK,ICICIBANK,SBIN,AXISBANK,KOTAKBANK"

def calculate_relative_valuation(ticker, financials, shares, peer_tickers=None, exchange_suffix="NS"):
    """
    Relative Valuation using peer multiples
    P/E and P/B comparisons with actual peer data
    
    Handles rate limiting gracefully with retries and delays
    """
    import time
    import random
    
    try:
        if not ticker:
            return None
        
        # Get stock info with rate limit handling
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                stock = get_cached_ticker(get_ticker_with_exchange(ticker, exchange_suffix))
                info = stock.info if stock else None
                # Robust price fetching - try multiple methods
                if info:
                    current_price = info.get('currentPrice', 0)
                    if not current_price or current_price == 0:
                        current_price = info.get('regularMarketPrice', 0)
                if not current_price or current_price == 0:
                    try:
                        hist = stock.history(period='1d')
                        if not hist.empty:
                            current_price = hist['Close'].iloc[-1]
                    except:
                        pass
                break
            except Exception as e:
                if "rate" in str(e).lower() or "429" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1) + random.uniform(0.5, 1.5)
                        st.warning(f"⏳ Rate limit hit. Waiting {wait_time:.1f}s... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        st.error("❌ Rate limit exceeded. Using fallback calculations.")
                        current_price = 0
                else:
                    raise
        
        # Calculate company metrics - USE NEWEST (index 0)
        latest_ni = financials['nopat'][0] * 100000
        eps = latest_ni / shares if shares > 0 else 0
        
        # USE NEWEST equity (index 0)
        latest_equity = financials['equity'][0] * 100000
        bvps = latest_equity / shares if shares > 0 else 0
        
        current_pe = current_price / eps if eps > 0 else 0
        current_pb = current_price / bvps if bvps > 0 else 0
        
        # Fetch peer multiples with rate limiting
        peer_pe_list = []
        peer_pb_list = []
        peer_data = []
        
        # Default bank peers if none provided
        if not peer_tickers:
            peer_tickers = get_auto_peers_or_default(ticker)
        
        peers = [t.strip() for t in peer_tickers.split(',') if t.strip()]
        
        st.info(f"📊 Fetching data for {len(peers[:10])} peer companies...")
        
        for i, peer in enumerate(peers[:10]):  # Limit to 10 peers
            try:
                # Add delay between requests to avoid rate limiting
                if i > 0:
                    time.sleep(random.uniform(1.0, 1.5))  # Reduced from 2-3s since caching prevents duplicates
                
                peer_stock = get_cached_ticker(get_ticker_with_exchange(peer, exchange_suffix))
                peer_info = peer_stock.info if peer_stock else None
                
                if not peer_info:
                    continue
                
                peer_pe = peer_info.get('trailingPE', 0)
                peer_pb = peer_info.get('priceToBook', 0)
                # Robust price fetching for peers
                peer_price = peer_info.get('currentPrice', 0)
                if not peer_price or peer_price == 0:
                    peer_price = peer_info.get('regularMarketPrice', 0)
                if not peer_price or peer_price == 0:
                    try:
                        hist = peer_stock.history(period='1d')
                        if not hist.empty:
                            peer_price = hist['Close'].iloc[-1]
                    except:
                        pass
                
                if peer_pe and peer_pe > 0 and peer_pe < 100:  # Sanity check
                    peer_pe_list.append(peer_pe)
                
                if peer_pb and peer_pb > 0 and peer_pb < 20:  # Sanity check
                    peer_pb_list.append(peer_pb)
                
                if peer_price > 0:
                    peer_data.append({
                        'ticker': peer,
                        'price': peer_price,
                        'pe': peer_pe if peer_pe else 'N/A',
                        'pb': peer_pb if peer_pb else 'N/A'
                    })
            except Exception as e:
                if "rate" in str(e).lower() or "429" in str(e):
                    st.warning(f"⏳ Rate limit hit on peer {peer}. Skipping...")
                    time.sleep(2)  # Longer delay after rate limit
                continue
        
        # Calculate sector averages
        if peer_pe_list:
            sector_avg_pe = np.median(peer_pe_list)  # Use median to avoid outliers
            sector_low_pe = np.percentile(peer_pe_list, 25)
            sector_high_pe = np.percentile(peer_pe_list, 75)
            st.success(f"✅ Fetched {len(peer_pe_list)} peer P/E ratios")
        else:
            st.warning("⚠️ Using default industry P/E multiples (no peer data available)")
            sector_avg_pe = 20  # Fallback
            sector_low_pe = 15
            sector_high_pe = 25
        
        if peer_pb_list:
            sector_avg_pb = np.median(peer_pb_list)
            sector_low_pb = np.percentile(peer_pb_list, 25)
            sector_high_pb = np.percentile(peer_pb_list, 75)
        else:
            sector_avg_pb = 3  # Fallback
            sector_low_pb = 2
            sector_high_pb = 4
        
        # Fair value based on sector multiples
        fair_value_pe = eps * sector_avg_pe
        fair_value_pb = bvps * sector_avg_pb
        
        # Conservative and aggressive estimates
        conservative_value = eps * sector_low_pe
        aggressive_value = eps * sector_high_pe
        
        return {
            'method': 'Relative Valuation',
            'current_price': current_price,
            'eps': eps,
            'bvps': bvps,
            'current_pe': current_pe,
            'current_pb': current_pb,
            'sector_avg_pe': sector_avg_pe,
            'sector_avg_pb': sector_avg_pb,
            'sector_low_pe': sector_low_pe,
            'sector_high_pe': sector_high_pe,
            'sector_low_pb': sector_low_pb,
            'sector_high_pb': sector_high_pb,
            'fair_value_pe_based': fair_value_pe,
            'fair_value_pb_based': fair_value_pb,
            'conservative_value': conservative_value,
            'aggressive_value': aggressive_value,
            'avg_fair_value': (fair_value_pe + fair_value_pb) / 2,
            'peer_count': len(peer_pe_list),
            'peer_data': peer_data,
            'rate_limited': len(peer_pe_list) == 0  # Flag if we got rate limited
        }
    except Exception as e:
        error_msg = str(e)
        if "rate" in error_msg.lower() or "429" in error_msg:
            st.error("❌ **Rate Limit Exceeded**")
            st.info("""
            **Why this happens:**
            - Yahoo Finance limits requests to prevent abuse
            - Too many requests in short time
            
            **Solutions:**
            1. Wait 5-10 minutes and try again
            2. Reduce number of peer companies
            3. Use the app during off-peak hours
            4. Consider using cached/default multiples
            
            **Alternative:** Use P/B ROE model or DDM for valuation instead
            """)
        else:
            st.error(f"Relative valuation error: {error_msg}")
        return None

# ================================
# YAHOO FINANCE SCRAPING WITH CACHING AND RETRY
# ================================

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_yahoo_financials_cached(ticker, exchange_suffix="NS"):
    """Cached wrapper for Yahoo Finance fetch"""
    return fetch_yahoo_financials_internal(ticker, exchange_suffix)

def fetch_yahoo_financials(ticker, exchange_suffix="NS"):
    """
    Fetch financial statements from Yahoo Finance with comprehensive error handling
    
    Features:
    - Retry logic with exponential backoff
    - Rate limit detection
    - Session caching
    - Automatic delays
    """
    import time
    import random
    
    max_retries = 3
    base_delay = 3  # seconds
    
    for attempt in range(max_retries):
        try:
            # Add delay before request (except first attempt)
            if attempt > 0:
                delay = base_delay * (2 ** attempt) + random.uniform(1, 3)
                st.warning(f"⏳ Rate limit detected. Waiting {delay:.1f} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            elif attempt == 0 and hasattr(st.session_state, 'last_yahoo_request'):
                # Add small delay between different requests
                elapsed = time.time() - st.session_state.last_yahoo_request
                if elapsed < 1:
                    time.sleep(1 - elapsed)
            
            # Try cached version first
            if attempt == 0:
                try:
                    return fetch_yahoo_financials_cached(ticker, exchange_suffix)
                except:
                    pass  # If cache fails, continue to direct fetch
            
            # Direct fetch
            result = fetch_yahoo_financials_internal(ticker, exchange_suffix)
            
            # Track request time and count
            st.session_state.last_yahoo_request = time.time()
            st.session_state.yahoo_request_count += 1
            
            return result
            
        except Exception as e:
            error_str = str(e).lower()
            
            if any(keyword in error_str for keyword in ['rate', '429', 'too many', 'limit']):
                if attempt < max_retries - 1:
                    continue  # Try again with delay
                else:
                    # All retries exhausted
                    st.error("❌ **Yahoo Finance Rate Limit Exceeded**")
                    st.warning("""
                    **Too many requests to Yahoo Finance. Please try one of these options:**
                    
                    1. ⏰ **Wait 10-15 minutes** and try again
                    2. 🌐 **Use a different network** (mobile hotspot, VPN)
                    3. 🔄 **Restart your Streamlit app** to clear session
                    4. 📊 **Use the Excel upload feature** for unlisted companies instead
                    
                    **Why this happens:**
                    Yahoo Finance limits free API requests to prevent abuse. This is a Yahoo limitation, not an issue with our app.
                    """)
                    return None, "Rate limit exceeded. Please try again later or use alternative data sources."
            else:
                # Other error
                if attempt < max_retries - 1:
                    continue
                else:
                    return None, f"Error fetching data: {str(e)}"
    
    return None, "Failed to fetch data after multiple retries"

def fetch_yahoo_financials_internal(ticker, exchange_suffix="NS"):
    """Internal function for actual Yahoo Finance fetch"""
    try:
        stock = get_cached_ticker(get_ticker_with_exchange(ticker, exchange_suffix))
        
        # Get financial statements
        income_stmt = stock.financials
        balance_sheet = stock.balance_sheet
        cash_flow = stock.cashflow
        
        # Get company info
        info = stock.info if stock else None
        
        if income_stmt.empty or balance_sheet.empty:
            return None, "No financial data available"
        
        # Get shares outstanding - ROBUST MULTI-METHOD APPROACH
        shares = 0
        
        # Method 1: Direct from info
        if info:
            shares = info.get('sharesOutstanding', 0)
        
        # Method 2: Implied shares outstanding
        if (shares == 0 or shares is None) and info:
            shares = info.get('impliedSharesOutstanding', 0)
        
        # Method 3: From balance sheet (Total Common Stock / Par Value)
        if (shares == 0 or shares is None) and not balance_sheet.empty:
            try:
                # Try to get from Common Stock or Share Capital
                for row_name in ['Common Stock', 'Share Capital', 'Ordinary Shares Capital', 'Common Stock Equity']:
                    if row_name in balance_sheet.index:
                        common_stock = balance_sheet.loc[row_name].iloc[0]
                        # Typically par value is ₹1, ₹2, ₹5, or ₹10
                        # Try different par values to estimate
                        for par_value in [1, 2, 5, 10]:
                            estimated_shares = abs(common_stock) / par_value
                            # Sanity check: shares should be reasonable (between 1M and 100B)
                            if 1_000_000 < estimated_shares < 100_000_000_000:
                                shares = estimated_shares
                                break
                        if shares > 0:
                            break
            except:
                pass
        
        # Method 4: Calculate from market cap and price
        if (shares == 0 or shares is None) and info and 'marketCap' in info and 'currentPrice' in info:
            market_cap = info.get('marketCap', 0)
            current_price = info.get('currentPrice', 0)
            if market_cap > 0 and current_price > 0:
                shares = market_cap / current_price
        
        # Method 5: From enterprise value and price
        if (shares == 0 or shares is None) and info and 'enterpriseValue' in info and 'currentPrice' in info:
            ev = info.get('enterpriseValue', 0)
            price = info.get('currentPrice', 0)
            if ev > 0 and price > 0:
                # Rough estimate assuming EV ≈ Market Cap for many companies
                shares = ev / price
        
        # Final check
        if shares is None:
            shares = 0
        
        shares_source = "Unknown"
        if shares > 0:
            if info and info.get('sharesOutstanding', 0) > 0:
                shares_source = "Direct (sharesOutstanding)"
            elif info.get('impliedSharesOutstanding', 0) > 0:
                shares_source = "Implied shares"
            elif 'marketCap' in info and 'currentPrice' in info:
                shares_source = "Calculated from Market Cap"
            else:
                shares_source = "Estimated from Balance Sheet"
        
        return {
            'income_statement': income_stmt,
            'balance_sheet': balance_sheet,
            'cash_flow': cash_flow,
            'info': info,
            'shares': shares,
            'shares_source': shares_source  # Track how shares were obtained
        }, None
        
    except Exception as e:
        return None, f"Error fetching data: {str(e)}"

def extract_financials_listed(yahoo_data, num_years=3):
    """
    Extract financial metrics from Yahoo Finance OR Screener.in data
    
    Args:
        yahoo_data: Dictionary containing either Yahoo Finance data OR Screener.in data
        num_years: Number of historical years to extract (default 3)
    
    Returns:
        Dictionary with financial metrics in ₹ Lacs
    """
    
    # CHECK IF THIS IS SCREENER.IN DATA
    if '_screener_financials' in yahoo_data:
        # SCREENER.IN DATA PATH
        st.info("📊 Using Screener.in financial data")
        financials = yahoo_data['_screener_financials']
        
        # BUGFIX: Validate that all required fields exist and have data
        required_fields = [
            'years', 'revenue', 'cogs', 'opex', 'ebitda', 'depreciation',
            'ebit', 'interest', 'tax', 'nopat', 'fixed_assets', 'inventory',
            'receivables', 'payables', 'cash', 'equity', 'st_debt', 'lt_debt'
        ]
        
        missing_fields = []
        empty_fields = []
        for field in required_fields:
            if field not in financials:
                missing_fields.append(field)
            elif isinstance(financials[field], list) and len(financials[field]) == 0:
                empty_fields.append(field)
            elif isinstance(financials[field], list) and all(v == 0 for v in financials[field]):
                empty_fields.append(field + " (all zeros)")
        
        if missing_fields:
            st.error(f"❌ Missing financial fields from Screener.in: {', '.join(missing_fields)}")
            st.info("💡 Try using Yahoo Finance data source instead")
        
        if empty_fields:
            st.warning(f"⚠️ Empty or zero financial fields from Screener.in: {', '.join(empty_fields)}")
            st.info("💡 This may be due to incomplete data on Screener.in for this stock")
            
            # DEBUG: Show actual values for troubleshooting
            with st.expander("🔍 Debug: View Raw Screener Data"):
                debug_data = {
                    'Fixed Assets': financials.get('fixed_assets', []),
                    'Inventory': financials.get('inventory', []),
                    'Receivables': financials.get('receivables', []),
                    'Payables': financials.get('payables', []),
                    'Equity': financials.get('equity', []),
                    'ST Debt': financials.get('st_debt', []),
                    'LT Debt': financials.get('lt_debt', [])
                }
                st.json(debug_data)
        
        # Screener data is already in the correct format (₹ Lacs)
        # Just ensure we only return the requested number of years
        if num_years < len(financials['years']):
            # Truncate to requested years (newest first)
            for key in financials.keys():
                if isinstance(financials[key], list):
                    financials[key] = financials[key][:num_years]
        
        return financials
    
    # YAHOO FINANCE DATA PATH (ORIGINAL CODE)
    try:
        income_stmt = yahoo_data['income_statement']
        balance_sheet = yahoo_data['balance_sheet']
        cash_flow = yahoo_data['cash_flow']
        
        # Get last N years (columns are sorted newest to oldest)
        years = income_stmt.columns[:min(num_years, len(income_stmt.columns))]
        
        opex_methods_used = []  # Track which method was used for each year
        
        financials = {
            'years': [str(y.year) for y in years],
            'revenue': [],
            'cogs': [],
            'opex': [],
            'ebitda': [],
            'depreciation': [],
            'ebit': [],
            'interest': [],
            'interest_income': [],  # Added for business classification
            'tax': [],
            'nopat': [],
            'fixed_assets': [],
            'inventory': [],
            'receivables': [],
            'payables': [],
            'cash': [],
            'equity': [],
            'st_debt': [],
            'lt_debt': [],
        }
        
        for year in years:
            # Income Statement - Values are already in the correct currency
            # ROBUST: Use safe_extract to handle None values
            revenue = safe_extract(income_stmt, 'Total Revenue', year, default=0)
            cogs = safe_extract(income_stmt, 'Cost Of Revenue', year, default=0)
            
            # Try to get Operating Expenses directly from various fields
            opex = 0
            opex_method = "None"
            
            # Method 1: Try direct operating expense fields
            opex_fields = [
                'Operating Expense',
                'Total Operating Expenses',
                'Operating Expenses',
                'Selling General And Administration',
                'Selling General Administrative',
                'SG&A Expense'
            ]
            
            for field in opex_fields:
                if field in income_stmt.index:
                    opex = abs(income_stmt.loc[field, year])
                    opex_method = f"Method 1: Direct field '{field}'"
                    break
            
            # Method 2: If not found, try to calculate from Gross Profit - Operating Income
            if opex == 0:
                gross_profit = 0
                if 'Gross Profit' in income_stmt.index:
                    gross_profit = abs(income_stmt.loc['Gross Profit', year])
                elif revenue > 0 and cogs > 0:
                    gross_profit = revenue - cogs
                
                operating_income = abs(income_stmt.loc['Operating Income', year]) if 'Operating Income' in income_stmt.index else 0
                
                if gross_profit > 0 and operating_income > 0:
                    opex = gross_profit - operating_income
                    opex_method = "Method 2: Gross Profit - Operating Income"
            
            # Method 3: If still not found, try SG&A + R&D + Other
            if opex == 0:
                sga = abs(income_stmt.loc['Selling General And Administration', year]) if 'Selling General And Administration' in income_stmt.index else 0
                rd = abs(income_stmt.loc['Research And Development', year]) if 'Research And Development' in income_stmt.index else 0
                other_opex = abs(income_stmt.loc['Other Operating Expenses', year]) if 'Other Operating Expenses' in income_stmt.index else 0
                opex = sga + rd + other_opex
                if opex > 0:
                    opex_method = f"Method 3: SG&A({sga/100000:.2f}) + R&D({rd/100000:.2f}) + Other({other_opex/100000:.2f})"
            
            # Get EBITDA - ROBUST: Handle None values
            ebitda = (
                safe_extract(income_stmt, 'EBITDA', year) or
                safe_extract(income_stmt, 'Normalized EBITDA', year) or
                max(0, revenue - cogs - opex)  # Calculate if not available
            )
            ebitda = ensure_valid_number(ebitda, default=0)
            
            # Get depreciation separately for projections - ROBUST
            depreciation = (
                safe_extract(income_stmt, 'Reconciled Depreciation', year) or
                safe_extract(cash_flow, 'Depreciation And Amortization', year) or
                safe_extract(income_stmt, 'Depreciation', year) or
                0
            )
            
            # Fallback: Calculate from Operating Income vs EBITDA or use revenue-based estimate
            if depreciation == 0:
                operating_income = safe_extract(income_stmt, 'Operating Income', year, default=0)
                if ebitda > operating_income and operating_income > 0:
                    depreciation = ebitda - operating_income
                else:
                    depreciation = revenue * 0.02 if revenue > 0 else 0  # 2% of revenue fallback
            
            depreciation = ensure_valid_number(depreciation, default=0)
            
            # Final safety check: If opex is still 0 or unreasonable, derive from EBITDA
            if opex == 0 or opex < 0:
                opex = revenue - cogs - ebitda
                opex_method = "Method 4 (Fallback): Revenue - COGS - EBITDA"
                if opex < 0:
                    opex = revenue * 0.15  # Assume 15% of revenue as default
                    opex_method = "Method 5 (Default): 15% of Revenue"
            
            # EBIT
            ebit = ebitda - depreciation
            
            # Interest Expense - ROBUST: Handle None values
            interest = (
                safe_extract(income_stmt, 'Interest Expense', year) or
                safe_extract(income_stmt, 'Interest Expense Non Operating', year) or
                0
            )
            
            # For banks: check if Net Interest Income is negative (then it's an expense)
            if interest == 0 and 'Net Interest Income' in income_stmt.index:
                net_int = safe_extract(income_stmt, 'Net Interest Income', year, default=0)
                if net_int < 0:
                    interest = abs(net_int)
            
            interest = ensure_valid_number(interest, default=0)
            
            # Interest Income (for business classification) - ROBUST
            interest_income = (
                safe_extract(income_stmt, 'Interest Income', year) or
                safe_extract(income_stmt, 'Interest And Dividend Income', year) or
                0
            )
            
            # For banks: Net Interest Income is primary revenue if positive
            if interest_income == 0 and 'Net Interest Income' in income_stmt.index:
                net_int = safe_extract(income_stmt, 'Net Interest Income', year, default=0)
                if net_int > 0:
                    interest_income = abs(net_int)
            
            interest_income = ensure_valid_number(interest_income, default=0)
            
            # Tax - ROBUST
            tax = safe_extract(income_stmt, 'Tax Provision', year, default=0)
            tax = ensure_valid_number(tax, default=0)
            
            # NOPAT (using 25% tax as default) - ROBUST calculation
            ebt = ebit - interest
            if ebt > 0 and tax > 0:
                tax_rate_effective = safe_divide(tax, ebt, default=0.25)
                tax_rate_effective = min(max(tax_rate_effective, 0), 0.35)  # Clamp between 0 and 35%
            else:
                tax_rate_effective = 0.25
            
            nopat = ebit * (1 - tax_rate_effective)
            nopat = ensure_valid_number(nopat, default=0)
            
            # Balance Sheet - Values are already in the correct currency
            # ROBUST: Use safe_extract for all balance sheet items to handle None values
            total_assets = safe_extract(balance_sheet, 'Total Assets', year, default=0)
            
            # Fixed Assets
            fixed_assets = (
                safe_extract(balance_sheet, 'Net PPE', year) or
                safe_extract(balance_sheet, 'Gross PPE', year) or
                safe_extract(balance_sheet, 'Properties', year) or
                (total_assets * 0.3 if total_assets > 0 else 0)  # Fallback: 30% of total assets
            )
            
            # Current Assets - ROBUST: These can be None for many companies
            inventory = safe_extract(balance_sheet, 'Inventory', year, default=0)
            
            receivables = (
                safe_extract(balance_sheet, 'Receivables', year) or
                safe_extract(balance_sheet, 'Accounts Receivable', year) or
                safe_extract(balance_sheet, 'Gross Accounts Receivable', year) or
                0
            )
            
            cash = (
                safe_extract(balance_sheet, 'Cash And Cash Equivalents', year) or
                safe_extract(balance_sheet, 'Cash Cash Equivalents And Short Term Investments', year) or
                0
            )
            
            # Liabilities - ROBUST: These can also be None
            payables = (
                safe_extract(balance_sheet, 'Payables', year) or
                safe_extract(balance_sheet, 'Accounts Payable', year) or
                safe_extract(balance_sheet, 'Payables And Accrued Expenses', year) or
                0
            )
            
            # Debt - ROBUST: Handle None debt values
            st_debt = (
                safe_extract(balance_sheet, 'Current Debt', year) or
                safe_extract(balance_sheet, 'Current Debt And Capital Lease Obligation', year) or
                0
            )
            
            lt_debt = (
                safe_extract(balance_sheet, 'Long Term Debt', year) or
                safe_extract(balance_sheet, 'Long Term Debt And Capital Lease Obligation', year) or
                0
            )
            
            # Equity - ROBUST: Critical for WACC calculation
            equity = (
                safe_extract(balance_sheet, 'Stockholders Equity', year) or
                safe_extract(balance_sheet, 'Total Equity Gross Minority Interest', year) or
                safe_extract(balance_sheet, 'Common Stock Equity', year) or
                0
            )
            
            # Convert to Lacs (divide by 100,000)
            # ROBUST: Ensure all values are valid numbers before storage
            # Yahoo Finance data is in actual currency (Rupees for Indian stocks)
            financials['revenue'].append(ensure_valid_number(revenue / 100000, 0))
            financials['cogs'].append(ensure_valid_number(cogs / 100000, 0))
            financials['opex'].append(ensure_valid_number(opex / 100000, 0))
            financials['ebitda'].append(ensure_valid_number(ebitda / 100000, 0))
            financials['depreciation'].append(ensure_valid_number(depreciation / 100000, 0))
            financials['ebit'].append(ensure_valid_number(ebit / 100000, 0))
            financials['interest'].append(ensure_valid_number(interest / 100000, 0))
            financials['interest_income'].append(ensure_valid_number(interest_income / 100000, 0))
            financials['tax'].append(ensure_valid_number(tax / 100000, 0))
            financials['nopat'].append(ensure_valid_number(nopat / 100000, 0))
            
            financials['fixed_assets'].append(ensure_valid_number(fixed_assets / 100000, 0))
            financials['inventory'].append(ensure_valid_number(inventory / 100000, 0))
            financials['receivables'].append(ensure_valid_number(receivables / 100000, 0))
            financials['payables'].append(ensure_valid_number(payables / 100000, 0))
            financials['cash'].append(ensure_valid_number(cash / 100000, 0))
            financials['equity'].append(ensure_valid_number(equity / 100000, 0))
            financials['st_debt'].append(ensure_valid_number(st_debt / 100000, 0))
            financials['lt_debt'].append(ensure_valid_number(lt_debt / 100000, 0))
            
            # Track which method was used for opex
            opex_methods_used.append(f"{year.year}: {opex_method}")
        
        
        return financials
        
    except Exception as e:
        st.error(f"Error extracting financials: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return None

def get_stock_beta(ticker, market_ticker=None, period_years=3,
                   beta_start_date=None, beta_end_date=None):
    """Calculate beta using daily return regression of stock vs market.

    Date priority:
        beta_start_date / beta_end_date  →  explicit window (user-chosen)
        period_years                     →  fallback rolling window
    
    Market index auto-selection:
        NSE (.NS)  →  NIFTY 50  (^NSEI)
        BSE (.BO)  →  SENSEX    (^BSESN)
    
    Returns: float beta (clamped 0.1 – 3.0)
    """
    try:
        if not ticker:
            st.warning("⚠️ Invalid ticker provided — using default β=1.0")
            return 1.0

        # Ensure exchange suffix
        if '.NS' not in ticker and '.BO' not in ticker:
            ticker = ticker + '.NS'

        # Auto-select market index
        if market_ticker is None:
            market_ticker = '^NSEI' if '.NS' in ticker else '^BSESN'

        # ── Date window ───────────────────────────────────────────────────
        if beta_start_date is not None and beta_end_date is not None:
            start_date = pd.Timestamp(beta_start_date)
            end_date   = pd.Timestamp(beta_end_date)
        else:
            end_date   = pd.Timestamp(datetime.now())
            start_date = end_date - pd.DateOffset(years=period_years)

        # ── Fetch daily OHLCV ─────────────────────────────────────────────
        stock_obj  = yf.Ticker(ticker)
        market_obj = yf.Ticker(market_ticker)

        stock  = stock_obj.history(start=start_date, end=end_date, period=None)
        market = market_obj.history(start=start_date, end=end_date, period=None)

        # Flatten MultiIndex if present (yfinance ≥ 0.2.x)
        if isinstance(stock.columns, pd.MultiIndex):
            stock.columns = stock.columns.get_level_values(0)
        if isinstance(market.columns, pd.MultiIndex):
            market.columns = market.columns.get_level_values(0)

        if stock.empty or market.empty:
            st.warning(f"⚠️ No price data for {ticker} in chosen period — using β=1.0")
            return 1.0

        # ── Daily returns (pct_change = day-over-day) ─────────────────────
        stock_returns  = stock['Close'].pct_change().dropna()
        market_returns = market['Close'].pct_change().dropna()

        # Align on common trading days
        aligned = pd.concat([stock_returns, market_returns], axis=1, join='inner').dropna()
        aligned.columns = ['stock', 'market']

        n_obs = len(aligned)
        if n_obs < 20:
            st.warning(f"⚠️ Only {n_obs} overlapping trading days for {ticker} — using β=1.0")
            return 1.0

        # ── OLS β = Cov(Rs, Rm) / Var(Rm) ───────────────────────────────
        cov    = aligned['stock'].cov(aligned['market'])
        var_m  = aligned['market'].var()

        if var_m == 0:
            return 1.0

        beta = cov / var_m

        # Caption for transparency
        index_name = "NIFTY 50" if market_ticker == '^NSEI' else "SENSEX"
        st.caption(
            f"   β vs {index_name} | {n_obs} daily obs "
            f"({aligned.index[0].strftime('%d-%b-%Y')} → {aligned.index[-1].strftime('%d-%b-%Y')})"
        )

        return max(0.1, min(beta, 3.0))

    except Exception as e:
        st.warning(f"Could not calculate beta for {ticker}: {str(e)}")
        return 1.0

def get_risk_free_rate(custom_ticker=None):
    """
    Get risk-free rate by calculating historical CAGR from Yahoo Finance ticker data.
    
    For bond indices/yields: Uses the closing value directly if it's already a percentage
    For stocks/indices: Calculates CAGR from price history
    
    Returns:
        tuple: (rate, debug_messages_list)
    """
    from datetime import datetime, timedelta
    pass  # yf available via module-level shim (yf_ratelimit)
    import pandas as pd
    
    ticker = custom_ticker if custom_ticker else '^TNX'
    debug = []
    
    debug.append(f"🔍 Fetching data for: `{ticker}`")
    
    try:
        # Fetch maximum available historical data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365*20)  # Try to get 20 years
        
        debug.append(f"📅 **Fetching data** from {start_date.date()} to {end_date.date()}")
        
        # Try to get data from Yahoo Finance
        ticker_obj = yf.Ticker(ticker)
        gsec_data = ticker_obj.history(period='max')
        
        if len(gsec_data) < 2:
            gsec_data = ticker_obj.history(start=start_date, end=end_date, period=None)
        
        if len(gsec_data) < 2:
            gsec_data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if isinstance(gsec_data.columns, pd.MultiIndex):
                gsec_data.columns = gsec_data.columns.get_level_values(0)
        
        # If we got good data, proceed with it
        if len(gsec_data) >= 2:
            debug.append(f"✅ **Successfully fetched {len(gsec_data)} rows of data**")
        else:
            # Check if we have a curated rate for this ticker
            ticker_upper = ticker.upper()
            curated_rates = {
                'NIFTYGS10YR.NS': (6.68, 'India 10Y G-Sec'),
                'NIFTYGS10YR': (6.68, 'India 10Y G-Sec'),
                'NIFTY GS 10YR': (6.68, 'India 10Y G-Sec'),
                'NIFTYGS5YR.NS': (6.43, 'India 5Y G-Sec'),
                'NIFTYGS5YR': (6.43, 'India 5Y G-Sec'),
                'NIFTY GS 5YR': (6.43, 'India 5Y G-Sec'),
                'NIFTYGS3YR.NS': (6.05, 'India 3Y G-Sec'),
                'NIFTYGS3YR': (6.05, 'India 3Y G-Sec'),
                'NIFTY GS 3YR': (6.05, 'India 3Y G-Sec'),
                '^TNX': (4.50, 'US 10Y Treasury'),
            }
            
            if ticker_upper in curated_rates:
                curated_rate, description = curated_rates[ticker_upper]
                debug.append(f"📊 **Using market rate for {description}**: {curated_rate}%")
                debug.append(f"💡 Source: Current market data (Feb 2026)")
                debug.append(f"✅ You can manually override this value in the field below")
                return curated_rate, debug
            else:
                # No curated rate available
                debug.append(f"⚠️ Unable to fetch historical data for ticker: {ticker}")
                debug.append(f"💡 **Try these alternatives:**")
                debug.append(f"   • Use ^TNX (US 10Y Treasury) - reliable data")
                debug.append(f"   • Manually enter rate in the field below")
                fallback = 6.83
                debug.append(f"⚠️ Using default fallback: {fallback}%")
                return fallback, debug
        
        debug.append(f"📊 **Downloaded {len(gsec_data)} rows of data**")
        
        # Show actual date range and data
        if len(gsec_data) > 0:
            debug.append(f"📋 Date range: {gsec_data.index[0].date()} to {gsec_data.index[-1].date()}")
        
        # Extract close prices
        close_prices = gsec_data['Close'].dropna()
        
        if len(close_prices) < 2:
            debug.append(f"⚠️ Insufficient data points: {len(close_prices)}")
            fallback = 6.83
            return fallback, debug
        
        # Get first and last prices
        first_price = float(close_prices.iloc[0])
        last_price = float(close_prices.iloc[-1])
        
        # Calculate time period
        first_date = close_prices.index[0]
        last_date = close_prices.index[-1]
        days_diff = (last_date - first_date).days
        years = days_diff / 365.25
        
        debug.append(f"📊 Period: {years:.1f} years | Price: {first_price:.2f} → {last_price:.2f}")
        
        # Determine if this is a yield/rate or a price
        avg_price = close_prices.mean()
        price_volatility = close_prices.std() / avg_price if avg_price > 0 else 0
        
        # Decision logic
        if avg_price < 50 and price_volatility < 0.5:
            # Likely already a yield/rate
            days_to_use = min(90, len(close_prices))
            recent_prices = close_prices.iloc[-days_to_use:]
            avg_rate = recent_prices.mean()
            
            debug.append(f"📈 Interpretation: Direct yield/rate (avg={avg_price:.2f})")
            debug.append(f"✅ Result: {avg_rate:.2f}% (90-day average)")
            
            return round(avg_rate, 2), debug
            
        else:
            # Calculate CAGR for stocks/indices
            if first_price <= 0 or years <= 0:
                debug.append(f"❌ Cannot calculate CAGR (invalid data)")
                fallback = 6.83
                return fallback, debug
            
            cagr = ((last_price / first_price) ** (1 / years) - 1) * 100
            
            debug.append(f"📈 Interpretation: Price data, calculating CAGR")
            debug.append(f"✅ Result: {cagr:.2f}% CAGR over {years:.1f} years")
            
            return round(cagr, 2), debug
        
    except Exception as e:
        debug.append(f"❌ Error: {type(e).__name__}: {str(e)[:100]}")
        fallback = 6.83
        return fallback, debug

def get_market_return(custom_ticker=None):
    """
    Calculate market return (CAGR) from historical index data.
    
    Args:
        custom_ticker: Yahoo Finance ticker (use % prefix, e.g., %5ENSEBANK for ^NSEBANK)
    
    Returns:
        tuple: (return_rate, debug_messages_list)
    """
    from datetime import datetime, timedelta
    pass  # yf available via module-level shim (yf_ratelimit)
    import pandas as pd
    
    ticker = custom_ticker if custom_ticker else '%5EBSESN'  # Default to BSE Sensex
    
    debug = []
    debug.append(f"🔍 Fetching market data for: `{ticker}`")
    
    try:
        end_date = datetime.now()
        
        debug.append(f"📅 Requesting maximum available historical data")
        
        # Try to get ALL available data using period='max'
        ticker_obj = yf.Ticker(ticker)
        market_data = ticker_obj.history(period='max')
        
        if len(market_data) < 2:
            # Fallback: try with date range
            start_date = end_date - timedelta(days=365*30)  # 30 years as fallback
            market_data = ticker_obj.history(start=start_date, end=end_date, period=None)
        
        if len(market_data) < 2:
            market_data = yf.download(ticker, period='max', progress=False)
            if isinstance(market_data.columns, pd.MultiIndex):
                market_data.columns = market_data.columns.get_level_values(0)
        
        # If we got good data, calculate CAGR
        if len(market_data) >= 252:  # At least 1 year
            debug.append(f"✅ Successfully fetched {len(market_data)} rows")
            
            start_price = float(market_data['Close'].iloc[0])
            end_price = float(market_data['Close'].iloc[-1])
            num_years = len(market_data) / 252  # 252 trading days per year
            
            if start_price > 0 and num_years > 0:
                cagr = ((end_price / start_price) ** (1 / num_years) - 1) * 100
                
                debug.append(f"📊 Period: {num_years:.1f} years | Price: {start_price:.2f} → {end_price:.2f}")
                debug.append(f"✅ Market CAGR: {cagr:.2f}%")
                
                return round(cagr, 2), debug
        
        # Curated fallback rates
        ticker_upper = ticker.upper()
        curated_market_returns = {
            '%5EBSESN': (12.5, 'BSE Sensex'),
            '%5ENSEI': (12.8, 'NSE Nifty 50'),
            '%5ENSEBANK': (15.2, 'Nifty Bank'),
            '%5EGSPC': (10.5, 'S&P 500'),
            '%5EDJI': (9.8, 'Dow Jones'),
        }
        
        if ticker_upper in curated_market_returns:
            curated_rate, description = curated_market_returns[ticker_upper]
            debug.append(f"📊 Using historical average for {description}: {curated_rate}%")
            debug.append(f"💡 Source: Long-term market averages")
            debug.append(f"✅ You can manually override this value below")
            return curated_rate, debug
        
        # Generic fallback
        debug.append(f"⚠️ Unable to fetch data for {ticker}")
        debug.append(f"💡 Try: %5EBSESN (Sensex), %5ENSEI (Nifty), or manual entry")
        fallback = 12.0
        return fallback, debug
        
    except Exception as e:
        debug.append(f"❌ Error: {type(e).__name__}: {str(e)[:100]}")
        fallback = 12.0
        return fallback, debug

# ================================
# ADVANCED CHARTING FUNCTIONS
# ================================

def create_waterfall_chart(valuation):
    """Create waterfall chart showing DCF value buildup"""
    fig = go.Figure(go.Waterfall(
        name = "DCF Waterfall",
        orientation = "v",
        measure = ["relative", "relative", "total"],
        x = ["PV of Projected FCFF", "PV of Terminal Value", "Enterprise Value"],
        textposition = "outside",
        text = [f"₹{valuation['sum_pv_fcff']:.2f}L", 
                f"₹{valuation['pv_terminal_value']:.2f}L",
                f"₹{valuation['enterprise_value']:.2f}L"],
        y = [valuation['sum_pv_fcff'], valuation['pv_terminal_value'], 0],
        connector = {"line":{"color":"rgb(63, 63, 63)"}},
    ))
    
    fig.update_layout(
        title = "DCF Valuation Waterfall",
        showlegend = False,
        height = 500,
        yaxis_title="Value (₹ Lacs)"
    )
    
    return fig

def create_fcff_projection_chart(projections):
    """Create detailed FCFF projection chart with components"""
    years = [f"Year {y}" for y in projections['year']]
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('FCFF Projection', 'Revenue & EBITDA', 'Working Capital Changes', 'Capex & Depreciation'),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}]]
    )
    
    # FCFF Projection
    fig.add_trace(
        go.Bar(name='FCFF', x=years, y=projections['fcff'], marker_color='#2E86AB'),
        row=1, col=1
    )
    
    # Revenue & EBITDA
    fig.add_trace(
        go.Scatter(name='Revenue', x=years, y=projections['revenue'], mode='lines+markers', line=dict(color='#06A77D', width=3)),
        row=1, col=2
    )
    fig.add_trace(
        go.Scatter(name='EBITDA', x=years, y=projections['ebitda'], mode='lines+markers', line=dict(color='#F77F00', width=3)),
        row=1, col=2
    )
    
    # Working Capital
    fig.add_trace(
        go.Bar(name='Δ WC', x=years, y=projections['delta_wc'], marker_color='#D62828'),
        row=2, col=1
    )
    
    # Capex & Depreciation
    fig.add_trace(
        go.Bar(name='Capex', x=years, y=projections['capex'], marker_color='#F77F00'),
        row=2, col=2
    )
    fig.add_trace(
        go.Bar(name='Depreciation', x=years, y=projections['depreciation'], marker_color='#06A77D'),
        row=2, col=2
    )
    
    fig.update_layout(height=800, showlegend=True, title_text="Comprehensive Financial Projections")
    fig.update_xaxes(title_text="Year", row=2, col=1)
    fig.update_xaxes(title_text="Year", row=2, col=2)
    fig.update_yaxes(title_text="₹ Lacs", row=1, col=1)
    fig.update_yaxes(title_text="₹ Lacs", row=1, col=2)
    fig.update_yaxes(title_text="₹ Lacs", row=2, col=1)
    fig.update_yaxes(title_text="₹ Lacs", row=2, col=2)
    
    return fig

def create_sensitivity_heatmap(projections, wacc_range, g_range, num_shares):
    """Create sensitivity analysis heatmap"""
    last_fcff = projections['fcff'][-1]
    n = len(projections['fcff'])
    
    # Create matrix
    matrix = []
    for w in wacc_range:
        row = []
        for g in g_range:
            if g >= w - 0.1:
                row.append(None)
            else:
                try:
                    fcff_n1 = last_fcff * (1 + g/100)
                    tv = fcff_n1 / ((w/100) - (g/100))
                    pv_tv = tv / ((1 + w/100) ** n)
                    
                    # Calculate sum_pv_fcff (approximate from first calc)
                    sum_pv_fcff = sum([projections['fcff'][i] / ((1 + w/100) ** (i+1)) for i in range(len(projections['fcff']))])
                    
                    ev = sum_pv_fcff + pv_tv
                    eq_val = ev * 100000
                    fv = eq_val / num_shares if num_shares > 0 else 0
                    row.append(fv)
                except:
                    row.append(None)
        matrix.append(row)
    
    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=[f"{g:.1f}%" for g in g_range],
        y=[f"{w:.1f}%" for w in wacc_range],
        colorscale='RdYlGn',
        text=[[f"₹{val:.1f}" if val else "N/A" for val in row] for row in matrix],
        texttemplate="%{text}",
        textfont={"size":10},
        colorbar=dict(title="Fair Value ₹")
    ))
    
    fig.update_layout(
        title='Sensitivity Analysis: Fair Value per Share',
        xaxis_title='Terminal Growth Rate (g)',
        yaxis_title='WACC',
        height=600
    )
    
    return fig

def create_historical_financials_chart(financials, reverse_years=False):
    """
    Create comprehensive historical financials overview
    
    Args:
        financials: Financial data dict
        reverse_years: If True, reverse the years for chronological display (used in Screener mode)
    """
    years = financials['years']
    
    # Reverse years and all data arrays for chronological display if needed
    if reverse_years:
        years = list(reversed(years))
        # Create reversed version of financials dict for plotting
        financials_plot = {}
        for key, value in financials.items():
            if isinstance(value, list) and key != 'years':
                financials_plot[key] = list(reversed(value))
            else:
                financials_plot[key] = value
        financials_plot['years'] = years
    else:
        financials_plot = financials
    
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=('Revenue & EBITDA Trend', 'Profitability Margins', 
                       'Balance Sheet Health', 'Cash Flow Quality',
                       'Working Capital Efficiency', 'Leverage Ratios'),
        specs=[[{"secondary_y": True}, {"secondary_y": False}],
               [{"secondary_y": True}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}]]
    )
    
    # Revenue & EBITDA
    fig.add_trace(
        go.Bar(name='Revenue', x=years, y=financials_plot['revenue'], marker_color='#06A77D'),
        row=1, col=1, secondary_y=False
    )
    fig.add_trace(
        go.Scatter(name='EBITDA Margin %', x=years, 
                  y=[(financials_plot['ebitda'][i]/financials_plot['revenue'][i]*100) if financials_plot['revenue'][i] > 0 else 0 
                     for i in range(len(years))],
                  mode='lines+markers', line=dict(color='#F77F00', width=3), marker=dict(size=10)),
        row=1, col=1, secondary_y=True
    )
    
    # Profitability Margins
    ebitda_margins = [(financials_plot['ebitda'][i]/financials_plot['revenue'][i]*100) if financials_plot['revenue'][i] > 0 else 0 
                      for i in range(len(years))]
    ebit_margins = [(financials_plot['ebit'][i]/financials_plot['revenue'][i]*100) if financials_plot['revenue'][i] > 0 else 0 
                    for i in range(len(years))]
    
    fig.add_trace(
        go.Scatter(name='EBITDA Margin', x=years, y=ebitda_margins, mode='lines+markers', line=dict(width=3)),
        row=1, col=2
    )
    fig.add_trace(
        go.Scatter(name='EBIT Margin', x=years, y=ebit_margins, mode='lines+markers', line=dict(width=3)),
        row=1, col=2
    )
    
    # Balance Sheet
    fig.add_trace(
        go.Bar(name='Equity', x=years, y=financials_plot['equity'], marker_color='#06A77D'),
        row=2, col=1, secondary_y=False
    )
    total_debt = [financials_plot['st_debt'][i] + financials_plot['lt_debt'][i] for i in range(len(years))]
    fig.add_trace(
        go.Bar(name='Debt', x=years, y=total_debt, marker_color='#D62828'),
        row=2, col=1, secondary_y=False
    )
    fig.add_trace(
        go.Scatter(name='Debt/Equity', x=years,
                  y=[(total_debt[i]/financials_plot['equity'][i]) if financials_plot['equity'][i] > 0 else 0 
                     for i in range(len(years))],
                  mode='lines+markers', line=dict(color='#2E86AB', width=3)),
        row=2, col=1, secondary_y=True
    )
    
    # Cash Flow Quality (NOPAT vs EBIT)
    fig.add_trace(
        go.Bar(name='EBIT', x=years, y=financials_plot['ebit'], marker_color='#F77F00'),
        row=2, col=2
    )
    fig.add_trace(
        go.Bar(name='NOPAT', x=years, y=financials_plot['nopat'], marker_color='#06A77D'),
        row=2, col=2
    )
    
    # Working Capital Components
    fig.add_trace(
        go.Bar(name='Inventory', x=years, y=financials_plot['inventory'], marker_color='#2E86AB'),
        row=3, col=1
    )
    fig.add_trace(
        go.Bar(name='Receivables', x=years, y=financials_plot['receivables'], marker_color='#06A77D'),
        row=3, col=1
    )
    fig.add_trace(
        go.Bar(name='Payables', x=years, y=financials_plot['payables'], marker_color='#D62828'),
        row=3, col=1
    )
    
    # Leverage Ratios
    debt_to_ebitda = [(total_debt[i]/financials_plot['ebitda'][i]) if financials_plot['ebitda'][i] > 0 else 0 
                      for i in range(len(years))]
    interest_coverage = [(financials_plot['ebit'][i]/financials_plot['interest'][i]) if financials_plot['interest'][i] > 0 else 0 
                         for i in range(len(years))]
    
    fig.add_trace(
        go.Scatter(name='Debt/EBITDA', x=years, y=debt_to_ebitda, mode='lines+markers', line=dict(width=3)),
        row=3, col=2
    )
    fig.add_trace(
        go.Scatter(name='Interest Coverage', x=years, y=interest_coverage, mode='lines+markers', line=dict(width=3)),
        row=3, col=2
    )
    
    fig.update_layout(height=1200, showlegend=True, title_text="Historical Financial Analysis Dashboard")
    fig.update_yaxes(title_text="₹ Lacs", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Margin %", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Margin %", row=1, col=2)
    fig.update_yaxes(title_text="₹ Lacs", row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Ratio", row=2, col=1, secondary_y=True)
    fig.update_yaxes(title_text="₹ Lacs", row=2, col=2)
    fig.update_yaxes(title_text="₹ Lacs", row=3, col=1)
    fig.update_yaxes(title_text="Ratio", row=3, col=2)
    
    return fig

def create_wacc_breakdown_chart(wacc_details):
    """Create visual breakdown of WACC components"""
    labels = ['Cost of Equity (Ke)', 'After-tax Cost of Debt (Kd)']
    values = [wacc_details['ke'], wacc_details['kd_after_tax']]
    weights = [wacc_details['we'], wacc_details['wd']]
    contributions = [wacc_details['ke'] * wacc_details['we'] / 100, 
                    wacc_details['kd_after_tax'] * wacc_details['wd'] / 100]
    
    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "pie"}, {"type": "bar"}]],
        subplot_titles=('Capital Structure Weights', 'WACC Components Contribution')
    )
    
    # Capital structure pie
    fig.add_trace(
        go.Pie(labels=['Equity', 'Debt'], values=[wacc_details['we'], wacc_details['wd']],
               marker_colors=['#06A77D', '#D62828']),
        row=1, col=1
    )
    
    # WACC contribution bar
    fig.add_trace(
        go.Bar(name='Contribution to WACC', x=labels, y=contributions,
               marker_color=['#06A77D', '#D62828'],
               text=[f"{c:.2f}%" for c in contributions],
               textposition='auto'),
        row=1, col=2
    )
    
    fig.update_layout(height=400, showlegend=True, title_text=f"WACC Breakdown (Total: {wacc_details['wacc']:.2f}%)")
    
    return fig

def create_bank_valuation_comparison_chart(valuations_dict):
    """Create comparison chart for multiple bank valuation methods"""
    methods = []
    values = []
    colors = []
    
    color_map = {
        'Residual Income Model': '#2E86AB',
        'Dividend Discount Model': '#06A77D',
        'P/B with ROE Analysis': '#F77F00',
        'Relative Valuation (P/E)': '#D62828',
        'Relative Valuation (P/B)': '#9D4EDD'
    }
    
    for method, val_data in valuations_dict.items():
        if val_data and 'value_per_share' in val_data:
            methods.append(method)
            values.append(val_data['value_per_share'])
            colors.append(color_map.get(method, '#888888'))
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=methods,
        y=values,
        marker_color=colors,
        text=[f"₹{v:.2f}" for v in values],
        textposition='auto',
    ))
    
    if values:
        avg_value = np.mean(values)
        fig.add_hline(y=avg_value, line_dash="dash", line_color="red",
                     annotation_text=f"Average: ₹{avg_value:.2f}",
                     annotation_position="right")
    
    fig.update_layout(
        title="Bank Valuation Methods Comparison",
        xaxis_title="Valuation Method",
        yaxis_title="Fair Value per Share (₹)",
        height=500,
        showlegend=False
    )
    
    return fig

def create_price_vs_value_gauge(current_price, fair_value):
    """Create gauge chart showing current price vs fair value"""
    # Check for invalid fair value (zero, negative, or unrealistic)
    if fair_value <= 0:
        return None
    
    ratio = (current_price / fair_value) * 100
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = current_price,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': f"Current Price vs Fair Value (₹{fair_value:.2f})", 'font': {'size': 20}},
        delta = {'reference': fair_value, 'valueformat': '.2f'},
        gauge = {
            'axis': {'range': [None, max(current_price, fair_value) * 1.5], 'tickformat': '₹.2f'},
            'bar': {'color': "#2E86AB"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, fair_value * 0.8], 'color': '#06A77D'},
                {'range': [fair_value * 0.8, fair_value * 1.2], 'color': '#F4D35E'},
                {'range': [fair_value * 1.2, fair_value * 2], 'color': '#D62828'}],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': fair_value}}))
    
    fig.update_layout(height=400)
    
    if ratio < 80:
        recommendation = "🟢 UNDERVALUED - Potential Buy"
    elif ratio > 120:
        recommendation = "🔴 OVERVALUED - Potential Sell"
    else:
        recommendation = "🟡 FAIRLY VALUED - Hold"
    
    fig.add_annotation(
        text=recommendation,
        xref="paper", yref="paper",
        x=0.5, y=-0.1,
        showarrow=False,
        font=dict(size=16, color="black", family="Arial Black")
    )
    
    return fig

# ================================
# DCF CALCULATION FUNCTIONS
# ================================

def extract_financials_unlisted(df_bs, df_pl, year_cols):
    """Extract financial metrics from Excel DataFrames"""
    num_years = min(3, len(year_cols))
    # year_cols is sorted oldest->newest. Take the most recent N years,
    # then REVERSE to newest-first so financials['...'][0] = latest year,
    # matching the convention used everywhere else (Yahoo/Screener data,
    # WACC, DCF projections, comp valuation, etc.)
    last_years = list(reversed(year_cols[-num_years:]))
    
    financials = {
        'years': last_years,
        'revenue': [],
        'cogs': [],
        'opex': [],
        'ebitda': [],
        'depreciation': [],
        'ebit': [],
        'interest': [],
        'interest_income': [],  # Added for business classification
        'tax': [],
        'nopat': [],
        'fixed_assets': [],
        'inventory': [],
        'receivables': [],
        'payables': [],
        'cash': [],
        'equity': [],
        'st_debt': [],
        'lt_debt': [],
    }
    
    for year_col in last_years:
        # Income Statement
        revenue = get_value_from_df(df_pl, 'Net Revenue', year_col)
        # COGS: Use 'Cost of Materials' for manufacturers; fall back to
        # Purchases of Stock-in-trade +/- Changes in Inventories for trading
        # companies (e.g. Zepto, Blinkit) where Cost of Materials = 0.
        cogs_materials = get_value_from_df(df_pl, 'Cost of Materials', year_col)
        purchases_sit  = get_value_from_df(df_pl, 'Purchases of Stock-in-trade', year_col)
        changes_inv    = get_value_from_df(df_pl, 'Changes in Inventories', year_col)
        if cogs_materials > 0:
            cogs = cogs_materials
        elif purchases_sit > 0:
            # Trading COGS = Purchases ± Changes in Inventories
            # "Changes in Inventories" row is typically positive when stock decreases
            cogs = purchases_sit + changes_inv
        else:
            cogs = 0.0
        employee_exp = get_value_from_df(df_pl, 'Employee Benefit', year_col)
        other_exp = get_value_from_df(df_pl, 'Other Expenses', year_col)
        depreciation = get_value_from_df(df_pl, 'Depreciation', year_col)
        interest = get_value_from_df(df_pl, 'Finance Costs', year_col)
        interest_income = get_value_from_df(df_pl, 'Finance Income', year_col)  # For classification
        tax = get_value_from_df(df_pl, 'Income Tax', year_col)
        
        opex = employee_exp + other_exp
        ebitda = revenue - opex - cogs
        ebit = ebitda - depreciation
        pbt = ebit - interest
        pat = pbt - tax
        nopat = ebit * (1 - 0.25)  # Assuming 25% tax
        
        financials['revenue'].append(revenue)
        financials['cogs'].append(cogs)
        financials['opex'].append(opex)
        financials['ebitda'].append(ebitda)
        financials['depreciation'].append(depreciation)
        financials['ebit'].append(ebit)
        financials['interest'].append(interest)
        financials['interest_income'].append(interest_income)  # Store for classification
        financials['tax'].append(tax)
        financials['nopat'].append(nopat)
        
        # Balance Sheet
        fixed_assets = get_value_from_df(df_bs, 'Tangible Assets', year_col)
        inventory = get_value_from_df(df_bs, 'Inventories', year_col)
        receivables = get_value_from_df(df_bs, 'Trade Receivables', year_col)
        payables = get_value_from_df(df_bs, 'Trade Payables', year_col)
        cash = get_value_from_df(df_bs, 'Cash and Bank', year_col)
        equity = get_value_from_df(df_bs, 'Total Equity', year_col)
        st_debt = get_value_from_df(df_bs, 'Short Term Borrowings', year_col)
        lt_debt = get_value_from_df(df_bs, 'Long Term Borrowings', year_col)
        
        financials['fixed_assets'].append(fixed_assets)
        financials['inventory'].append(inventory)
        financials['receivables'].append(receivables)
        financials['payables'].append(payables)
        financials['cash'].append(cash)
        financials['equity'].append(equity)
        financials['st_debt'].append(st_debt)
        financials['lt_debt'].append(lt_debt)
    
    return financials

def fetch_screener_peer_data(ticker_symbol):
    """
    Fetch peer company data from Screener.in for comparative valuation
    
    Args:
        ticker_symbol: NSE/BSE ticker (without .NS/.BO suffix)
    
    Returns:
        dict with peer financial data or None
    """
    try:
        import time
        import random
        
        # Clean ticker
        ticker_clean = ticker_symbol.replace('.NS', '').replace('.BO', '')
        
        # Add delay for respectful scraping
        time.sleep(random.uniform(1.5, 3.0))
        
        screener_data = fetch_screener_financials(ticker_clean, num_years=3)
        
        if not screener_data or not screener_data.get('financials'):
            return None
        
        financials = screener_data['financials']
        shares = screener_data.get('shares', 0)
        
        # Convert to format expected by perform_comparative_valuation
        # Values are already in Lacs, need to convert to rupees for compatibility
        revenue = ensure_valid_number(financials['revenue'][0] * 100000, 0)  # Most recent year
        ebitda = ensure_valid_number(financials['ebitda'][0] * 100000, 0)
        net_income = ensure_valid_number(financials['nopat'][0] * 100000, 0)
        total_debt = ensure_valid_number((financials['st_debt'][0] + financials['lt_debt'][0]) * 100000, 0)
        cash = ensure_valid_number(financials['cash'][0] * 100000, 0)
        equity = ensure_valid_number(financials['equity'][0] * 100000, 0)
        
        eps = safe_divide(net_income, shares, default=0)
        book_value = safe_divide(equity, shares, default=0)
        
        return {
            'ticker': ticker_clean,
            'name': screener_data.get('company_name', ticker_clean),
            'price': 0,  # Screener doesn't provide live price
            'shares': shares,
            'market_cap': 0,  # Cannot calculate without price
            'revenue': revenue,
            'ebitda': ebitda,
            'net_income': net_income,
            'eps': eps,
            'book_value': book_value,
            'total_debt': total_debt,
            'cash': cash,
            'enterprise_value': 0,  # Cannot calculate without market cap
            '_source': 'screener'
        }
    
    except Exception as e:
        print(f"Error fetching Screener data for {ticker_symbol}: {e}")
        return None


def perform_comparative_valuation(target_ticker, comp_tickers_str, target_financials=None, target_shares=None, exchange_suffix="NS", projections=None, use_screener_peers=False):
    """
    Perform comparative valuation using peer multiples
    
    Args:
        target_ticker: Target company ticker
        comp_tickers_str: Comma-separated peer tickers
        target_financials: Target company financials dict
        target_shares: Target company shares outstanding
        exchange_suffix: NS or BO
        projections: DCF projections dict with 'nopat' key
        use_screener_peers: If True, fetch peer data from Screener.in instead of Yahoo Finance
    """
    try:
        comp_tickers = [t.strip() for t in comp_tickers_str.split(',') if t.strip()]
        
        if not comp_tickers:
            return None
        
        results = {
            'target': {},
            'comparables': [],
            'multiples_stats': {},
            'valuations': {},
            '_peer_source': 'screener' if use_screener_peers else 'yahoo',
            '_currency_symbol': '₹'  # default; updated below from target info
        }
        
        # Get target company data
        if target_ticker:
            # Listed company
            target_stock = get_cached_ticker(get_ticker_with_exchange(target_ticker, exchange_suffix))
            target_info = target_stock.info if target_stock else None
            target_financials_yf = target_stock.financials
            target_bs = target_stock.balance_sheet
            
            if not target_info:
                st.error(f"Could not fetch data for {target_ticker}")
                return results
            
            # Detect currency from target ticker
            results['_currency_symbol'] = get_currency_symbol(target_info)
            _csym = results['_currency_symbol']  # shorthand for formula strings below

            results['target'] = {
                'name': target_info.get('longName', target_ticker),
                # Robust price fetching - try multiple methods
                'current_price': target_info.get('currentPrice', 0) or target_info.get('regularMarketPrice', 0) or 0,
                'shares': target_info.get('sharesOutstanding', 0),
                'market_cap': target_info.get('marketCap', 0),
                'enterprise_value': target_info.get('enterpriseValue', 0),
                'revenue': safe_extract(target_financials_yf, 'Total Revenue', target_financials_yf.columns[0]) if 'Total Revenue' in target_financials_yf.index else 0,
                'ebitda': target_info.get('ebitda', 0),
                'net_income': safe_extract(target_financials_yf, 'Net Income', target_financials_yf.columns[0]) if 'Net Income' in target_financials_yf.index else 0,
                'book_value_per_share': target_info.get('bookValue', 0),
                'total_debt': safe_extract(target_bs, 'Long Term Debt', target_bs.columns[0]) if 'Long Term Debt' in target_bs.index else 0,
                'cash': safe_extract(target_bs, 'Cash And Cash Equivalents', target_bs.columns[0]) if 'Cash And Cash Equivalents' in target_bs.index else 0,
            }
            
            # Calculate EPS and Book Value - ALWAYS set to avoid KeyError
            if results['target']['shares'] > 0 and results['target']['net_income'] != 0:
                results['target']['eps'] = results['target']['net_income'] / results['target']['shares']
            else:
                results['target']['eps'] = 0
                
        else:
            # Unlisted company - arrays have NEWEST first, so [0] = latest
            equity_lacs = target_financials['equity'][0]  # Latest equity in Lacs
            equity_rupees = equity_lacs * 100000  # Convert to Rupees
            book_value_per_share = equity_rupees / target_shares if target_shares > 0 else 0
            
            results['target'] = {
                'name': 'Target Company (Unlisted)',
                'current_price': 0,
                'shares': target_shares,
                'market_cap': 0,
                'enterprise_value': 0,
                'revenue': target_financials['revenue'][0] * 100000,  # [0] = latest year
                'ebitda': target_financials['ebitda'][0] * 100000,
                'net_income': target_financials['nopat'][0] * 100000,  # Using NOPAT as proxy
                'book_value_per_share': book_value_per_share,  # CALCULATE from equity
                'total_debt': (target_financials['st_debt'][0] + target_financials['lt_debt'][0]) * 100000,
                'cash': target_financials['cash'][0] * 100000,
                'eps': (target_financials['nopat'][0] * 100000) / target_shares if target_shares > 0 else 0,
            }
        
        # Get comparable companies data
        comp_data = []
        
        if use_screener_peers:
            # FETCH PEER DATA FROM SCREENER.IN
            st.info(f"🌐 Fetching peer data from Screener.in for {len(comp_tickers)} companies...")
            
            for idx, ticker in enumerate(comp_tickers):
                try:
                    peer_data = fetch_screener_peer_data(ticker)
                    
                    if peer_data:
                        # Calculate multiples (most will be 0 since no price/market cap)
                        pe = 0  # Cannot calculate without price
                        pb = 0  # Cannot calculate without price
                        ps = 0  # Cannot calculate without market cap
                        
                        # Can calculate EV-based multiples if we have enterprise value
                        enterprise_value = peer_data['enterprise_value']
                        ev_ebitda = safe_divide(enterprise_value, peer_data['ebitda'], default=0)
                        ev_sales = safe_divide(enterprise_value, peer_data['revenue'], default=0)
                        
                        comp_data.append({
                            'ticker': peer_data['ticker'],
                            'name': peer_data['name'],
                            'price': peer_data['price'],
                            'market_cap': peer_data['market_cap'],
                            'revenue': peer_data['revenue'],
                            'ebitda': peer_data['ebitda'],
                            'net_income': peer_data['net_income'],
                            'eps': peer_data['eps'],
                            'book_value': peer_data['book_value'],
                            'pe': pe,
                            'pb': pb,
                            'ps': ps,
                            'ev_ebitda': ev_ebitda,
                            'ev_sales': ev_sales,
                            'enterprise_value': enterprise_value,
                            'shares': peer_data['shares']
                        })
                        
                        st.success(f"✅ {peer_data['name']}")
                    else:
                        st.warning(f"⚠️ Could not fetch data for {ticker}")
                
                except Exception as e:
                    st.warning(f"⚠️ Error fetching {ticker}: {str(e)}")
                    continue
            
            if not comp_data:
                st.warning("⚠️ Could not fetch any peer data from Screener.in. Try Yahoo Finance instead.")
                return None
        
        else:
            # FETCH PEER DATA FROM YAHOO FINANCE (ORIGINAL CODE)
            for idx, ticker in enumerate(comp_tickers):
                try:
                    # Add delay between requests to avoid rate limiting
                    if idx > 0:
                        time.sleep(random.uniform(1.0, 1.5))
                    
                    # Ticker already has suffix (.NS or .BO) from UI combination
                    comp_stock = get_cached_ticker(ticker)
                    comp_info = comp_stock.info if comp_stock else None
                    
                    if not comp_info:
                        st.warning(f"Could not fetch data for {ticker}")
                        continue
                    
                    comp_financials_yf = comp_stock.financials
                    comp_bs = comp_stock.balance_sheet
                    
                    # Extract financial data
                    shares = comp_info.get('sharesOutstanding', 0)
                    # Robust price fetching - try multiple methods
                    price = comp_info.get('currentPrice', 0)
                    if not price or price == 0:
                        price = comp_info.get('regularMarketPrice', 0)
                    if not price or price == 0:
                        try:
                            hist = comp_stock.history(period='1d')
                            if not hist.empty:
                                price = hist['Close'].iloc[-1]
                        except:
                            pass
                    market_cap = comp_info.get('marketCap', 0)
                    
                    revenue = safe_extract(comp_financials_yf, 'Total Revenue', comp_financials_yf.columns[0]) if 'Total Revenue' in comp_financials_yf.index and not comp_financials_yf.empty else 0
                    ebitda = comp_info.get('ebitda', 0)
                    net_income = safe_extract(comp_financials_yf, 'Net Income', comp_financials_yf.columns[0]) if 'Net Income' in comp_financials_yf.index and not comp_financials_yf.empty else 0
                    
                    total_debt = safe_extract(comp_bs, 'Long Term Debt', comp_bs.columns[0]) if 'Long Term Debt' in comp_bs.index and not comp_bs.empty else 0
                    cash = safe_extract(comp_bs, 'Cash And Cash Equivalents', comp_bs.columns[0]) if 'Cash And Cash Equivalents' in comp_bs.index and not comp_bs.empty else 0
                    
                    book_value = comp_info.get('bookValue', 0)
                    eps = net_income / shares if shares > 0 else 0
                    
                    # Calculate multiples
                    pe = price / eps if eps > 0 else 0
                    pb = price / book_value if book_value > 0 else 0
                    ps = market_cap / revenue if revenue > 0 else 0
                    
                    enterprise_value = market_cap + total_debt - cash
                    ev_ebitda = enterprise_value / ebitda if ebitda > 0 else 0
                    ev_sales = enterprise_value / revenue if revenue > 0 else 0
                    
                    comp_data.append({
                        'ticker': ticker,
                        'name': comp_info.get('longName', ticker),
                        'price': price,
                        'market_cap': market_cap,
                        'revenue': revenue,
                        'ebitda': ebitda,
                        'net_income': net_income,
                        'eps': eps,
                        'book_value': book_value,
                        'pe': pe,
                        'pb': pb,
                        'ps': ps,
                        'ev_ebitda': ev_ebitda,
                        'ev_sales': ev_sales,
                        'enterprise_value': enterprise_value,
                        'shares': shares
                    })
                    
                except Exception as e:
                    st.warning(f"Could not fetch data for {ticker}: {str(e)}")
                    continue
        
        results['comparables'] = comp_data
        
        if not comp_data:
            st.error("No comparable company data could be fetched")
            return None
        
        # Calculate statistics for each multiple
        multiples = ['pe', 'pb', 'ps', 'ev_ebitda', 'ev_sales']
        
        for multiple in multiples:
            valid_values = [c[multiple] for c in comp_data if c.get(multiple, 0) > 0]
            
            if not valid_values:
                continue
            
            results['multiples_stats'][multiple] = {
                'average': np.mean(valid_values),
                'median': np.median(valid_values),
                'min': np.min(valid_values),
                'max': np.max(valid_values),
                'std': np.std(valid_values),
                'values': valid_values
            }
        
        # Calculate implied valuations
        target = results['target']
        valuations_summary = {}
        _csym = results.get('_currency_symbol', '₹')  # ensure _csym is always defined
        
        # P/E Method
        if 'pe' in results['multiples_stats'] and target['eps'] > 0:
            stats = results['multiples_stats']['pe']
            
            fair_value_avg = target['eps'] * stats['average']
            fair_value_median = target['eps'] * stats['median']
            
            valuations_summary['pe'] = {
                'method': 'Price-to-Earnings (P/E)',
                'target_metric': target['eps'],
                'metric_name': 'EPS',
                'avg_multiple': stats['average'],
                'median_multiple': stats['median'],
                'fair_value_avg': fair_value_avg,
                'fair_value_median': fair_value_median,
                'current_price': target['current_price'],
                'upside_avg': ((fair_value_avg - target['current_price']) / target['current_price'] * 100) if target['current_price'] else 0,
                'upside_median': ((fair_value_median - target['current_price']) / target['current_price'] * 100) if target['current_price'] else 0,
                'formula_avg': f"EPS × Avg P/E = {_csym}{target['eps']:.2f} × {stats['average']:.2f} = {_csym}{fair_value_avg:.2f}",
                'formula_median': f"EPS × Median P/E = {_csym}{target['eps']:.2f} × {stats['median']:.2f} = {_csym}{fair_value_median:.2f}"
            }
        
        # P/B Method
        if 'pb' in results['multiples_stats'] and target['book_value_per_share'] > 0:
            stats = results['multiples_stats']['pb']
            
            fair_value_avg = target['book_value_per_share'] * stats['average']
            fair_value_median = target['book_value_per_share'] * stats['median']
            
            valuations_summary['pb'] = {
                'method': 'Price-to-Book (P/B)',
                'target_metric': target['book_value_per_share'],
                'metric_name': 'Book Value per Share',
                'avg_multiple': stats['average'],
                'median_multiple': stats['median'],
                'fair_value_avg': fair_value_avg,
                'fair_value_median': fair_value_median,
                'current_price': target['current_price'],
                'upside_avg': ((fair_value_avg - target['current_price']) / target['current_price'] * 100) if target['current_price'] else 0,
                'upside_median': ((fair_value_median - target['current_price']) / target['current_price'] * 100) if target['current_price'] else 0,
                'formula_avg': f"BVPS × Avg P/B = {_csym}{target['book_value_per_share']:.2f} × {stats['average']:.2f} = {_csym}{fair_value_avg:.2f}",
                'formula_median': f"BVPS × Median P/B = {_csym}{target['book_value_per_share']:.2f} × {stats['median']:.2f} = {_csym}{fair_value_median:.2f}"
            }
        
        # P/S Method
        if 'ps' in results['multiples_stats'] and target['revenue'] > 0 and target['shares'] > 0:
            stats = results['multiples_stats']['ps']
            
            revenue_per_share = target['revenue'] / target['shares']
            fair_value_avg = revenue_per_share * stats['average']
            fair_value_median = revenue_per_share * stats['median']
            
            valuations_summary['ps'] = {
                'method': 'Price-to-Sales (P/S)',
                'target_metric': revenue_per_share,
                'metric_name': 'Revenue per Share',
                'avg_multiple': stats['average'],
                'median_multiple': stats['median'],
                'fair_value_avg': fair_value_avg,
                'fair_value_median': fair_value_median,
                'current_price': target['current_price'],
                'upside_avg': ((fair_value_avg - target['current_price']) / target['current_price'] * 100) if target['current_price'] else 0,
                'upside_median': ((fair_value_median - target['current_price']) / target['current_price'] * 100) if target['current_price'] else 0,
                'formula_avg': f"Revenue/Share × Avg P/S = {_csym}{revenue_per_share:.2f} × {stats['average']:.2f} = {_csym}{fair_value_avg:.2f}",
                'formula_median': f"Revenue/Share × Median P/S = {_csym}{revenue_per_share:.2f} × {stats['median']:.2f} = {_csym}{fair_value_median:.2f}"
            }
        
        # EV/EBITDA Method
        if 'ev_ebitda' in results['multiples_stats'] and target['ebitda'] > 0 and target['shares'] > 0:
            stats = results['multiples_stats']['ev_ebitda']
            
            implied_ev_avg = target['ebitda'] * stats['average']
            implied_ev_median = target['ebitda'] * stats['median']
            
            net_debt = target['total_debt'] - target['cash']
            
            equity_value_avg = implied_ev_avg - net_debt
            equity_value_median = implied_ev_median - net_debt
            
            fair_value_avg = equity_value_avg / target['shares']
            fair_value_median = equity_value_median / target['shares']
            
            valuations_summary['ev_ebitda'] = {
                'method': 'EV/EBITDA',
                'target_metric': target['ebitda'],
                'metric_name': 'EBITDA',
                'avg_multiple': stats['average'],
                'median_multiple': stats['median'],
                'implied_ev_avg': implied_ev_avg,
                'implied_ev_median': implied_ev_median,
                'total_debt': total_debt,
        'cash': cash,
        'net_debt': net_debt,
                'fair_value_avg': fair_value_avg,
                'fair_value_median': fair_value_median,
                'current_price': target['current_price'],
                'upside_avg': ((fair_value_avg - target['current_price']) / target['current_price'] * 100) if target['current_price'] else 0,
                'upside_median': ((fair_value_median - target['current_price']) / target['current_price'] * 100) if target['current_price'] else 0,
                'formula_avg': f"(EBITDA × Avg EV/EBITDA - Net Debt) / Shares = ({_csym}{target['ebitda']/1e7:.2f}{'Cr' if _csym=='₹' else 'M'} × {stats['average']:.2f} - {_csym}{net_debt/1e7:.2f}{'Cr' if _csym=='₹' else 'M'}) / {target['shares']/1e7:.2f}{'Cr' if _csym=='₹' else 'M'}",
                'formula_median': f"(EBITDA × Median EV/EBITDA - Net Debt) / Shares = ({_csym}{target['ebitda']/1e7:.2f}{'Cr' if _csym=='₹' else 'M'} × {stats['median']:.2f} - {_csym}{net_debt/1e7:.2f}{'Cr' if _csym=='₹' else 'M'}) / {target['shares']/1e7:.2f}{'Cr' if _csym=='₹' else 'M'}"
            }
        
        # EV/Sales Method
        if 'ev_sales' in results['multiples_stats'] and target['revenue'] > 0 and target['shares'] > 0:
            stats = results['multiples_stats']['ev_sales']
            
            implied_ev_avg = target['revenue'] * stats['average']
            implied_ev_median = target['revenue'] * stats['median']
            
            net_debt = target['total_debt'] - target['cash']
            
            equity_value_avg = implied_ev_avg - net_debt
            equity_value_median = implied_ev_median - net_debt
            
            fair_value_avg = equity_value_avg / target['shares']
            fair_value_median = equity_value_median / target['shares']
            
            valuations_summary['ev_sales'] = {
                'method': 'EV/Sales',
                'target_metric': target['revenue'],
                'metric_name': 'Revenue',
                'avg_multiple': stats['average'],
                'median_multiple': stats['median'],
                'implied_ev_avg': implied_ev_avg,
                'implied_ev_median': implied_ev_median,
                'net_debt': net_debt,
                'fair_value_avg': fair_value_avg,
                'fair_value_median': fair_value_median,
                'current_price': target['current_price'],
                'upside_avg': ((fair_value_avg - target['current_price']) / target['current_price'] * 100) if target['current_price'] else 0,
                'upside_median': ((fair_value_median - target['current_price']) / target['current_price'] * 100) if target['current_price'] else 0,
                'formula_avg': f"(Revenue × Avg EV/Sales - Net Debt) / Shares = ({_csym}{target['revenue']/1e7:.2f}{'Cr' if _csym=='₹' else 'M'} × {stats['average']:.2f} - {_csym}{net_debt/1e7:.2f}{'Cr' if _csym=='₹' else 'M'}) / {target['shares']/1e7:.2f}{'Cr' if _csym=='₹' else 'M'}",
                'formula_median': f"(Revenue × Median EV/Sales - Net Debt) / Shares = ({_csym}{target['revenue']/1e7:.2f}{'Cr' if _csym=='₹' else 'M'} × {stats['median']:.2f} - {_csym}{net_debt/1e7:.2f}{'Cr' if _csym=='₹' else 'M'}) / {target['shares']/1e7:.2f}{'Cr' if _csym=='₹' else 'M'}"
            }
        
        results['valuations'] = valuations_summary
        
        # Calculate 12-Month Forward P/E using EXISTING PROJECTED NOPAT (NO DUPLICATION!)
        # Forward P/E = Current Price / Future EPS
        # Future EPS = Projected Year 1 NOPAT / Current Outstanding Shares
        
        # Get current EPS for comparison
        current_eps = 0
        if target_financials and 'nopat' in target_financials:
            current_nopat = target_financials['nopat'][0] * 100000  # Most recent historical year
            current_eps = current_nopat / target['shares'] if target['shares'] > 0 else 0
        
        # Use EXISTING projections if available, otherwise calculate growth
        if projections and 'nopat' in projections and len(projections['nopat']) > 0:
            # ✅ USE EXISTING PROJECTED NOPAT - NO DUPLICATION!
            projected_nopat_year1 = projections['nopat'][0] * 100000  # Year 1 projection (already calculated in DCF!)
            future_eps = projected_nopat_year1 / target['shares'] if target['shares'] > 0 else 0
            
            # Calculate growth rate for display purposes only
            if current_eps > 0 and future_eps > 0:
                growth_rate = ((future_eps / current_eps) - 1) * 100
            else:
                growth_rate = 0.0
            
            calculation_method = "Using DCF Year 1 Projected NOPAT"
            
        elif target_financials and 'nopat' in target_financials and len(target_financials['nopat']) >= 2:
            # Fallback: Calculate growth if projections not available
            recent_nopat = target_financials['nopat'][:min(3, len(target_financials['nopat']))]
            if len(recent_nopat) >= 2 and recent_nopat[-1] > 0:
                num_years = len(recent_nopat) - 1
                growth_rate = ((recent_nopat[0] / recent_nopat[-1]) ** (1/num_years) - 1) * 100
                growth_rate = max(-5, min(growth_rate, 25))
            else:
                growth_rate = 10.0
            
            future_eps = current_eps * (1 + growth_rate / 100)
            calculation_method = f"Using historical CAGR ({growth_rate:.1f}%)"
        else:
            future_eps = current_eps * 1.10  # Default 10% growth
            growth_rate = 10.0
            calculation_method = "Using default 10% growth"
        
        if 'pe' in results['multiples_stats'] and future_eps > 0:
            stats = results['multiples_stats']['pe']
            forward_fair_value_avg = future_eps * stats['average']
            forward_fair_value_median = future_eps * stats['median']
            
            results['forward_pe'] = {
                'current_eps': current_eps,
                'forward_eps': future_eps,
                'earnings_growth_rate': growth_rate,
                'fair_value_avg': forward_fair_value_avg,
                'fair_value_median': forward_fair_value_median,
                'formula_avg': f"Forward EPS × Avg P/E = {_csym}{future_eps:.2f} × {stats['average']:.2f} = {_csym}{forward_fair_value_avg:.2f}",
                'formula_median': f"Forward EPS × Median P/E = {_csym}{future_eps:.2f} × {stats['median']:.2f} = {_csym}{forward_fair_value_median:.2f}",
                'calculation_method': calculation_method,
                'calculation_note': f"12-Month Forward EPS: {calculation_method}",
                'using_dcf_projections': bool(projections)
            }
        
        return results
        
    except Exception as e:
        st.error(f"Comparative valuation error: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return None

def calculate_working_capital_metrics(financials):
    """
    Calculate working capital days with ROBUST None/zero handling
    
    CRITICAL FIX: If inventory, receivables, or payables are None/zero for ALL years,
    exclude them from working capital calculations to prevent NaN cascade
    """
    wc_metrics = {
        'inventory_days': [],
        'debtor_days': [],
        'creditor_days': []
    }
    
    # ROBUST: Check if we have valid data for each WC component across ALL years
    has_valid_inventory = any(ensure_valid_number(financials['inventory'][i], 0) > 0 for i in range(len(financials['years'])))
    has_valid_receivables = any(ensure_valid_number(financials['receivables'][i], 0) > 0 for i in range(len(financials['years'])))
    has_valid_payables = any(ensure_valid_number(financials['payables'][i], 0) > 0 for i in range(len(financials['years'])))
    
    for i in range(len(financials['years'])):
        # ROBUST: Ensure all values are valid numbers
        revenue = ensure_valid_number(financials['revenue'][i], 0)
        cogs = ensure_valid_number(financials['cogs'][i], 0)
        inventory = ensure_valid_number(financials['inventory'][i], 0)
        receivables = ensure_valid_number(financials['receivables'][i], 0)
        payables = ensure_valid_number(financials['payables'][i], 0)

        # For trading companies (e.g. Zepto) COGS may be 0 because Cost of Materials = 0.
        # In that case fall back to revenue as the denominator so inventory days and
        # creditor days are still meaningful (same base as debtors days).
        cogs_or_rev = cogs if cogs > 0 else revenue

        # Calculate days only if we have valid denominators
        inv_days = safe_divide(inventory * 365, cogs_or_rev, default=0) if has_valid_inventory and cogs_or_rev > 0 else 0
        deb_days = safe_divide(receivables * 365, revenue, default=0) if has_valid_receivables and revenue > 0 else 0
        cred_days = safe_divide(payables * 365, cogs_or_rev, default=0) if has_valid_payables and cogs_or_rev > 0 else 0
        
        wc_metrics['inventory_days'].append(ensure_valid_number(inv_days, 0))
        wc_metrics['debtor_days'].append(ensure_valid_number(deb_days, 0))
        wc_metrics['creditor_days'].append(ensure_valid_number(cred_days, 0))
    
    # Average days - ROBUST: Only calculate if we have valid data
    if has_valid_inventory and wc_metrics['inventory_days']:
        valid_inv_days = [d for d in wc_metrics['inventory_days'] if d > 0]
        wc_metrics['avg_inv_days'] = np.mean(valid_inv_days) if valid_inv_days else 0
    else:
        wc_metrics['avg_inv_days'] = 0  # No inventory data available
    
    if has_valid_receivables and wc_metrics['debtor_days']:
        valid_deb_days = [d for d in wc_metrics['debtor_days'] if d > 0]
        wc_metrics['avg_deb_days'] = np.mean(valid_deb_days) if valid_deb_days else 0
    else:
        wc_metrics['avg_deb_days'] = 0  # No receivables data available
    
    if has_valid_payables and wc_metrics['creditor_days']:
        valid_cred_days = [d for d in wc_metrics['creditor_days'] if d > 0]
        wc_metrics['avg_cred_days'] = np.mean(valid_cred_days) if valid_cred_days else 0
    else:
        wc_metrics['avg_cred_days'] = 0  # No payables data available
    
    # Add flags to indicate which components are available
    wc_metrics['has_inventory'] = has_valid_inventory
    wc_metrics['has_receivables'] = has_valid_receivables
    wc_metrics['has_payables'] = has_valid_payables
    
    # Ensure all values are valid numbers (not NaN or inf)
    wc_metrics['avg_inv_days'] = ensure_valid_number(wc_metrics['avg_inv_days'], 0)
    wc_metrics['avg_deb_days'] = ensure_valid_number(wc_metrics['avg_deb_days'], 0)
    wc_metrics['avg_cred_days'] = ensure_valid_number(wc_metrics['avg_cred_days'], 0)
    
    return wc_metrics

def calculate_historical_capex_ratio(financials):
    """
    Calculate historical CapEx as % of Revenue for each year and return average
    This provides a more realistic CapEx projection method
    
    Returns:
        dict: {
            'capex_ratios': list of ratios for each year,
            'avg_capex_ratio': average ratio to use for projections
        }
    """
    revenues = financials['revenue']
    fixed_assets = financials['fixed_assets']
    
    capex_ratios = []
    
    # Calculate CapEx for each historical year
    # CapEx = Change in Fixed Assets + Depreciation
    for i in range(len(revenues) - 1):
        # Yahoo data is newest to oldest, so:
        # i=0 is newest year, i=1 is previous year
        newer_fa = fixed_assets[i]
        older_fa = fixed_assets[i + 1]
        revenue = revenues[i]
        
        if revenue > 0:
            # Estimate depreciation as ~5% of older FA (conservative estimate)
            estimated_dep = older_fa * 0.05
            capex = (newer_fa - older_fa) + estimated_dep
            
            # Calculate as % of revenue
            capex_ratio = (capex / revenue) * 100
            
            # Sanity check: Flag unusually high CapEx ratios but allow them
            if capex_ratio > 150.0:
                capex_ratio = 150.0  # Maximum cap at 150%
            elif capex_ratio > 50.0:
                # Just log high CapEx, don't cap it
                pass
            
            capex_ratios.append(capex_ratio)
    
    # Calculate average
    avg_capex_ratio = np.mean(capex_ratios) if capex_ratios else 5.0  # Default 5% if no data
    
    return {
        'capex_ratios': capex_ratios,
        'avg_capex_ratio': avg_capex_ratio
    }

def calculate_bank_fcfe_valuation(projections, ke, terminal_growth, num_shares):
    """
    Bank Valuation using FCFE (Free Cash Flow to Equity)
    
    CRITICAL DIFFERENCES FROM NORMAL DCF:
    - Uses Ke (Cost of Equity), NOT WACC
    - Discounts FCFE, NOT FCFF
    - Values EQUITY directly, NOT Enterprise Value
    - No debt adjustment (debt is raw material for banks)
    
    Formula:
    Equity Value = Σ PV(FCFE) + Terminal Value
    Value per Share = Equity Value / Shares
    
    Args:
        projections: Bank projections with 'fcfe' key
        ke: Cost of Equity % (NOT WACC!)
        terminal_growth: Terminal growth rate %
        num_shares: Outstanding shares
    """
    
    if 'fcfe' not in projections:
        return None, "❌ Bank projections must have 'fcfe' (Free Cash Flow to Equity)"
    
    fcfe_list = projections['fcfe']
    g = terminal_growth
    
    # Validation: Terminal growth must be < Ke
    if g >= ke:
        return None, f"❌ ERROR: Terminal growth ({g:.1f}%) must be less than Ke ({ke:.1f}%)"
    
    # =====================================================
    # STEP 1: Discount FCFE at Ke
    # =====================================================
    pv_fcfe = []
    for year, fcfe in enumerate(fcfe_list, start=1):
        fcfe_rupees = fcfe * 100000  # Convert from Lacs to Rupees
        pv = fcfe_rupees / ((1 + ke / 100) ** year)
        pv_fcfe.append(pv)
    
    sum_pv_fcfe = sum(pv_fcfe)
    
    # =====================================================
    # STEP 2: Terminal Value using Gordon Growth
    # =====================================================
    last_fcfe = fcfe_list[-1] * 100000  # Rupees
    fcfe_terminal = last_fcfe * (1 + g / 100)
    
    terminal_value = fcfe_terminal / ((ke / 100) - (g / 100))
    
    n = len(fcfe_list)
    pv_terminal = terminal_value / ((1 + ke / 100) ** n)
    
    # =====================================================
    # STEP 3: EQUITY VALUE (NOT Enterprise Value!)
    # =====================================================
    equity_value = sum_pv_fcfe + pv_terminal  # In Rupees
    
    # Convert to per share
    value_per_share = equity_value / num_shares if num_shares > 0 else 0
    
    # For banks, sustainable growth rate
    if 'roe' in projections:
        roe = projections.get('roe', 15)
        # Retention ratio = (PAT - FCFE) / PAT
        avg_pat = np.mean([projections['pat'][i] for i in range(len(projections['pat']))])
        avg_fcfe = np.mean(fcfe_list)
        retention_ratio = (avg_pat - avg_fcfe) / avg_pat if avg_pat > 0 else 0.5
        sustainable_growth = roe * retention_ratio
    else:
        sustainable_growth = g
    
    return {
        'valuation_method': 'Bank FCFE (Equity DCF)',
        'fair_value_per_share': value_per_share,
        'equity_value': equity_value / 100000,  # In Lacs
        'sum_pv_fcfe': sum_pv_fcfe / 100000,
        'terminal_value_pv': pv_terminal / 100000,
        'cost_of_equity': ke,
        'terminal_growth': g,
        'sustainable_growth': sustainable_growth,
        'projections': projections,
        'pv_fcfe_by_year': [pv / 100000 for pv in pv_fcfe]
    }, None

def project_financials_bank(financials, years, tax_rate, car_ratio=14.0, rwa_percentage=75.0):
    """
    Bank-Specific Financial Projection using FCFE (Free Cash Flow to Equity) Methodology
    
    CRITICAL: Banks CANNOT use FCFF/WACC. Must use FCFE/Ke.
    
    Why FCFE for banks:
    - Debt is raw material (not financing)
    - Interest expense is operating cost (not financing cost)
    - Capital Adequacy Ratio (CAR) constrains growth
    - Only equity capital matters
    
    FCFE Formula for Banks:
    FCFE = PAT - (Growth in Advances × RWA% × CAR)
    
    Where:
    - PAT = Net Profit After Tax
    - Growth in Advances = Loan book growth
    - RWA = Risk Weighted Assets ≈ 70-80% of Advances
    - CAR = Capital Adequacy Ratio (13-15% in India)
    
    Args:
        financials: Historical financial data
        years: Projection period
        tax_rate: Tax rate %
        car_ratio: Capital Adequacy Ratio % (default 14%)
        rwa_percentage: Risk Weight % (default 75%)
    """
    
    st.info("🏦 **Using Bank FCFE Methodology** (Not FCFF - that's wrong for banks!)")
    
    # =====================================================
    # STEP 1: Get Historical Data
    # =====================================================
    
    # Revenue = Total Revenue (Interest Income + Non-Interest Income)
    revenue_history = financials['revenue'] if 'revenue' in financials else []
    
    # Net Profit After Tax
    nopat_history = financials['nopat'] if 'nopat' in financials else []
    
    # Equity (Book Value)
    equity_history = financials['equity'] if 'equity' in financials else []
    
    if not revenue_history or not nopat_history or not equity_history:
        st.error("❌ Insufficient bank data for FCFE projection")
        return None, None
    
    # =====================================================
    # STEP 2: Calculate Historical Growth Rates
    # =====================================================
    
    # Revenue growth (proxy for advances growth in absence of loan book data)
    if len(revenue_history) >= 2 and revenue_history[-1] > 0 and revenue_history[0] > 0:
        num_years_hist = len(revenue_history) - 1
        revenue_growth = ((revenue_history[0] / revenue_history[-1]) ** (1/num_years_hist) - 1) * 100
        revenue_growth = max(5, min(revenue_growth, 150))  # Cap between 5-150% for banks
    else:
        revenue_growth = 12.0  # Default Indian bank growth
    
    # Historical ROE
    latest_equity = equity_history[0] * 100000  # Convert from Lacs to Rupees
    latest_pat = nopat_history[0] * 100000
    current_roe = (latest_pat / latest_equity * 100) if latest_equity > 0 else 15.0
    
    st.info(f"""
    📊 **Bank Metrics Calculated:**
    - Revenue Growth (Advances proxy): {revenue_growth:.2f}%
    - Current ROE: {current_roe:.2f}%
    - CAR Target: {car_ratio:.1f}%
    - RWA Weight: {rwa_percentage:.1f}%
    """)
    
    # =====================================================
    # STEP 3: Project PAT (Net Profit)
    # =====================================================
    
    # Use ROE × Book Value approach for PAT projection
    projected_pat = []
    projected_equity = []
    projected_revenue = []
    projected_fcfe = []
    
    current_revenue = revenue_history[0]
    current_equity_val = latest_equity
    
    for year in range(1, years + 1):
        # Project revenue (advances)
        current_revenue = current_revenue * (1 + revenue_growth / 100)
        projected_revenue.append(current_revenue / 100000)  # Back to Lacs
        
        # Project equity (retained earnings accumulate)
        # Equity grows with retained PAT
        projected_equity.append(current_equity_val / 100000)
        
        # Project PAT using ROE
        pat = current_equity_val * (current_roe / 100)
        projected_pat.append(pat / 100000)
        
        # =====================================================
        # STEP 4: Calculate FCFE (KEY FORMULA)
        # =====================================================
        # FCFE = PAT - Equity Required for Growth
        # Equity Required = Growth in Advances × RWA% × CAR%
        
        advances_growth_amount = current_revenue * (revenue_growth / 100)  # Rupees
        equity_required = advances_growth_amount * (rwa_percentage / 100) * (car_ratio / 100)
        
        fcfe = pat - equity_required
        projected_fcfe.append(fcfe / 100000)  # Back to Lacs
        
        # Update equity for next year (add retained earnings)
        # Retained = PAT - Dividends, approximate as PAT - FCFE
        retained = pat - fcfe
        current_equity_val += retained
    
    projections = {
        'year': list(range(1, years + 1)),
        'revenue': projected_revenue,  # Total revenue
        'pat': projected_pat,  # Net Profit After Tax
        'equity': projected_equity,  # Book Value
        'fcfe': projected_fcfe  # Free Cash Flow to Equity (THIS IS WHAT WE DISCOUNT!)
    }
    
    drivers = {
        'revenue_growth': revenue_growth,
        'roe': current_roe,
        'car_ratio': car_ratio,
        'rwa_percentage': rwa_percentage,
        'tax_rate': tax_rate
    }
    
    st.success(f"✅ **Bank FCFE Projections Complete:** {years} years projected")
    st.info(f"💡 **FCFE** (not FCFF!) will be discounted at **Ke** (not WACC!) to get equity value directly")
    
    return projections, drivers

def project_financials(financials, wc_metrics, years, tax_rate, 
                      rev_growth_override, opex_margin_override, capex_ratio_override=None,
                      # PER-YEAR overrides (lists of length == years, index 0 = Year 1)
                      rev_growth_per_year=None,   # list[float] | None
                      ebitda_margin_per_year=None, # list[float] | None
                      # NEW PARAMETERS - Complete user control
                      ebitda_margin_override=None,
                      depreciation_rate_override=None,
                      depreciation_method="Auto",
                      inventory_days_override=None,
                      debtor_days_override=None,
                      creditor_days_override=None,
                      interest_rate_override=None,
                      working_capital_pct_override=None):
    """
    INDUSTRY-GRADE Financial Projection Engine with FULL USER CONTROL
    ==================================================================
    
    Uses multiple validation layers and industry best practices:
    1. Revenue: CAGR with economic floor (user can override)
    2. Margins: Normalized with trend analysis (user can override)
    3. CapEx: % of Revenue (user can override)
    4. Working Capital: Days-based methodology (user can override each component)
    5. Depreciation: Multiple methods (user can select)
    6. Interest: Auto or user override
    7. Sanity checks at every step
    
    ALL parameters can be overridden by the user for complete control.
    """
    
    # ============================================
    # STEP 1: CALCULATE HISTORICAL CAPEX RATIO
    # ============================================
    capex_info = calculate_historical_capex_ratio(financials)
    avg_capex_ratio = capex_info['avg_capex_ratio']
    
    # Apply override if provided
    if capex_ratio_override:
        try:
            avg_capex_ratio = float(capex_ratio_override)
        except:
            pass  # Keep calculated value if override is invalid
    
    # ============================================
    # STEP 2: REVENUE GROWTH WITH INTELLIGENT FLOORS
    # ============================================
    revenues = financials['revenue']
    num_years = len(revenues) - 1
    
    if num_years > 0 and revenues[0] > 0 and revenues[-1] > 0:
        # CAGR: Start = OLDEST (last element), End = NEWEST (first element)
        start_revenue = revenues[-1]  # Oldest year
        end_revenue = revenues[0]     # Newest year
        historical_cagr = ((end_revenue / start_revenue) ** (1 / num_years) - 1) * 100
        
        # INDUSTRY PRACTICE: Apply GDP floor for low-growth companies
        # But also cap unrealistic high growth
        if historical_cagr < 4.0:
            # Blend historical with GDP floor (7% for India)
            avg_growth = (historical_cagr * 0.6) + (7.0 * 0.4)
        elif historical_cagr > 150.0:
            # Cap extremely excessive growth - maximum 150%
            avg_growth = 150.0
            try:
                st.warning(f"⚠️ Historical Revenue CAGR ({historical_cagr:.1f}%) capped at 150%. Original: {historical_cagr:.1f}%")
            except:
                pass
        else:
            avg_growth = historical_cagr
            if historical_cagr > 50.0:
                try:
                    st.info(f"📊 High Growth Detected: Revenue CAGR = {historical_cagr:.1f}% (using actual historical rate)")
                except:
                    pass
    else:
        avg_growth = 8.0  # Reasonable default for Indian economy
    
    if rev_growth_override:
        avg_growth = float(rev_growth_override)
    
    # ============================================
    # CRITICAL CAPEX NORMALIZATION RULE
    # ============================================
    # RULE: If CapEx/Revenue ratio > Revenue Growth rate,
    # then CapEx is consuming too much cash relative to growth
    # SOLUTION: Cap CapEx at 1/4 of revenue growth rate
    
    if avg_capex_ratio > avg_growth:
        original_capex_ratio = avg_capex_ratio
        avg_capex_ratio = avg_growth / 4.0
        
        # Log the adjustment for transparency
        st.warning(f"⚠️ **CapEx Normalization Applied**")
        st.info(f"""
        📊 **Original CapEx/Revenue:** {original_capex_ratio:.2f}%
        📈 **Revenue Growth Rate:** {avg_growth:.2f}%
        
        **Issue Detected:** CapEx ratio ({original_capex_ratio:.2f}%) exceeds revenue growth ({avg_growth:.2f}%)
        
        **Action Taken:** CapEx ratio normalized to **{avg_capex_ratio:.2f}%** (1/4 of revenue growth)
        
        **Rationale:** Sustainable companies cannot indefinitely spend more on CapEx (as % of revenue) 
        than their revenue growth rate. This normalization ensures long-term financial viability.
        """)
    
    # ============================================
    # STEP 3: MARGIN ANALYSIS WITH NORMALIZATION
    # ============================================
    
    # COGS Margin - Use median to avoid outliers
    cogs_margins = []
    for i in range(len(revenues)):
        if financials['revenue'][i] > 0:
            margin = (financials['cogs'][i] / financials['revenue'][i]) * 100
            # Sanity check: COGS should be 20-85% of revenue
            if 20 <= margin <= 85:
                cogs_margins.append(margin)
    
    avg_cogs_margin = np.median(cogs_margins) if cogs_margins else 55.0
    
    # OpEx Margin - Use median and exclude outliers
    opex_margins = []
    for i in range(len(revenues)):
        if financials['revenue'][i] > 0:
            margin = (financials['opex'][i] / financials['revenue'][i]) * 100
            # Sanity check: OpEx should be 5-50% of revenue
            if 5 <= margin <= 50:
                opex_margins.append(margin)
    
    avg_opex_margin = np.median(opex_margins) if opex_margins else 15.0
    
    if opex_margin_override:
        avg_opex_margin = float(opex_margin_override)
    
    # ============================================
    # STEP 4: DEPRECIATION RATE - NORMALIZED
    # ============================================
    dep_rates = []
    for i in range(len(revenues)):
        if financials['fixed_assets'][i] > 0:
            rate = (financials['depreciation'][i] / financials['fixed_assets'][i]) * 100
            # Sanity: Depreciation typically 3-15% of FA
            if 3 <= rate <= 15:
                dep_rates.append(rate)
    
    avg_dep_rate = np.median(dep_rates) if dep_rates else 6.0
    
    # User override for depreciation rate
    if depreciation_rate_override:
        avg_dep_rate = float(depreciation_rate_override)
    
    # ============================================
    # STEP 5: INTEREST RATE ON DEBT
    # ============================================
    total_debts = [financials['st_debt'][i] + financials['lt_debt'][i] for i in range(len(revenues))]
    fin_cost_rates = []
    
    for i in range(len(revenues)):
        if total_debts[i] > 0 and financials['interest'][i] > 0:
            rate = (financials['interest'][i] / total_debts[i]) * 100
            # Sanity: Interest rate should be 4-18%
            if 4 <= rate <= 18:
                fin_cost_rates.append(rate)
    
    avg_fin_cost_rate = np.median(fin_cost_rates) if fin_cost_rates else 8.0
    
    # User override for interest rate
    if interest_rate_override:
        avg_fin_cost_rate = float(interest_rate_override)
    
    # ============================================
    # STEP 6: BALANCE SHEET GROWTH RATES
    # ============================================
    
    # Equity growth (for completeness)
    equity_values = financials['equity']
    if len(equity_values) > 1 and equity_values[-1] > 0 and equity_values[0] > 0:
        avg_equity_growth = ((equity_values[0] / equity_values[-1]) ** (1 / (len(equity_values) - 1)) - 1) * 100
        # Cap equity growth at revenue growth + 5%
        avg_equity_growth = min(avg_equity_growth, avg_growth + 5)
    else:
        avg_equity_growth = avg_growth
    
    # Debt growth - conservative assumption
    if len(total_debts) > 1 and total_debts[-1] > 0 and total_debts[0] > 0:
        historical_debt_growth = ((total_debts[0] / total_debts[-1]) ** (1 / (len(total_debts) - 1)) - 1) * 100
        # INDUSTRY PRACTICE: Debt shouldn't grow faster than revenue
        avg_debt_growth = min(historical_debt_growth, avg_growth * 0.8)
    else:
        avg_debt_growth = 0.0  # Conservative: assume no debt growth
    
    # ============================================
    # STEP 7: PROJECTIONS WITH ROBUST VALIDATION
    # ============================================
    projections = {
        'year': [],
        'revenue': [],
        'cogs': [],
        'opex': [],
        'ebitda': [],
        'depreciation': [],
        'ebit': [],
        'interest': [],
        'nopat': [],
        'fixed_assets': [],
        'equity': [],
        'debt': [],
        'wc': [],
        'delta_wc': [],
        'capex': [],
        'fcff': []
    }
    
    # Starting point - USE NEWEST YEAR DATA (index 0)
    last_revenue = revenues[0]
    last_fa = financials['fixed_assets'][0]
    last_equity = financials['equity'][0]
    last_debt = total_debts[0] if total_debts[0] > 0 else 0
    
    # CRITICAL FIX: Calculate initial working capital from most recent historical year
    # This ensures delta_wc calculations are based on actual historical WC, not zero
    last_inventory = ensure_valid_number(financials['inventory'][0], 0)
    last_receivables = ensure_valid_number(financials['receivables'][0], 0)
    last_payables = ensure_valid_number(financials['payables'][0], 0)
    last_wc = last_inventory + last_receivables - last_payables
    last_wc = ensure_valid_number(last_wc, 0)
    
    for year in range(1, years + 1):
        # ============================================
        # REVENUE PROJECTION
        # ============================================
        # Per-year growth takes priority → single override → auto CAGR
        year_idx = year - 1  # 0-based index
        if rev_growth_per_year and year_idx < len(rev_growth_per_year) and rev_growth_per_year[year_idx] > 0:
            year_growth = rev_growth_per_year[year_idx]
        else:
            year_growth = avg_growth
        projected_revenue = last_revenue * (1 + year_growth / 100)
        
        # ============================================
        # P&L PROJECTIONS
        # ============================================
        projected_cogs = projected_revenue * (avg_cogs_margin / 100)
        projected_opex = projected_revenue * (avg_opex_margin / 100)
        projected_ebitda = projected_revenue - projected_cogs - projected_opex
        
        # Per-year EBITDA margin takes priority → single override → derived
        if ebitda_margin_per_year and year_idx < len(ebitda_margin_per_year) and ebitda_margin_per_year[year_idx] > 0:
            projected_ebitda = projected_revenue * (ebitda_margin_per_year[year_idx] / 100)
        elif ebitda_margin_override:
            # USER OVERRIDE: EBITDA margin directly overrides the derived EBITDA
            projected_ebitda = projected_revenue * (float(ebitda_margin_override) / 100)
        
        # Sanity check: EBITDA should be positive for healthy companies
        # (skip auto-correction if user explicitly set the EBITDA margin)
        active_ebitda_override = (
            (ebitda_margin_per_year and year_idx < len(ebitda_margin_per_year) and ebitda_margin_per_year[year_idx] > 0)
            or ebitda_margin_override
        )
        if projected_ebitda < 0 and not active_ebitda_override:
            # Adjust opex to maintain 5% EBITDA margin
            projected_opex = projected_revenue * 0.85 - projected_cogs
            projected_ebitda = projected_revenue * 0.15
        
        # ============================================
        # CAPEX PROJECTION (INDUSTRY METHOD)
        # ============================================
        # CapEx as % of Revenue (most reliable method)
        capex = projected_revenue * (avg_capex_ratio / 100)
        
        # Depreciation: Apply to growing FA base
        # FA will grow based on net CapEx
        projected_fa = last_fa + capex  # Will subtract depreciation next
        
        # USER OVERRIDE: Depreciation method selector
        if depreciation_method == "% of Revenue":
            projected_dep = projected_revenue * (avg_dep_rate / 100)
        elif depreciation_method == "Absolute Value":
            # depreciation_rate_override (if provided) is treated as an absolute ₹ Lacs value
            projected_dep = float(depreciation_rate_override) if depreciation_rate_override else avg_dep_rate
        else:
            # "Auto" or "% of Fixed Assets" (default)
            projected_dep = projected_fa * (avg_dep_rate / 100)
        
        # Adjust FA after depreciation
        projected_fa = projected_fa - projected_dep
        
        # ============================================
        # EBIT & NOPAT
        # ============================================
        projected_ebit = projected_ebitda - projected_dep
        projected_nopat = projected_ebit * (1 - tax_rate / 100)
        
        # ============================================
        # DEBT & INTEREST
        # ============================================
        projected_debt = last_debt * (1 + avg_debt_growth / 100) if last_debt > 0 else 0
        projected_interest = projected_debt * (avg_fin_cost_rate / 100) if projected_debt > 0 else 0
        
        # ============================================
        # WORKING CAPITAL (INDUSTRY STANDARD METHOD)
        # ROBUST: Handle cases where inventory/receivables/payables data is None
        # CRITICAL FIX: User overrides take priority over historical data
        # ============================================
        
        # Initialize WC components
        projected_inventory = 0
        projected_receivables = 0
        projected_payables = 0
        
        # Determine inventory days: USER OVERRIDE > Historical Data > 0
        if inventory_days_override and inventory_days_override > 0:
            inv_days_to_use = inventory_days_override
        elif wc_metrics.get('has_inventory', False) and wc_metrics['avg_inv_days'] > 0:
            inv_days_to_use = wc_metrics['avg_inv_days']
        else:
            inv_days_to_use = 0
        
        # Determine debtor days: USER OVERRIDE > Historical Data > 0
        if debtor_days_override and debtor_days_override > 0:
            deb_days_to_use = debtor_days_override
        elif wc_metrics.get('has_receivables', False) and wc_metrics['avg_deb_days'] > 0:
            deb_days_to_use = wc_metrics['avg_deb_days']
        else:
            deb_days_to_use = 0
        
        # Determine creditor days: USER OVERRIDE > Historical Data > 0
        if creditor_days_override and creditor_days_override > 0:
            cred_days_to_use = creditor_days_override
        elif wc_metrics.get('has_payables', False) and wc_metrics['avg_cred_days'] > 0:
            cred_days_to_use = wc_metrics['avg_cred_days']
        else:
            cred_days_to_use = 0
        
        # Calculate WC components using determined days
        # For trading companies cogs may be 0; fall back to revenue so that
        # inventory and creditor projections use the same base as debtor days.
        projected_cogs_or_rev = projected_cogs if projected_cogs > 0 else projected_revenue

        if inv_days_to_use > 0:
            projected_inventory = safe_divide(projected_cogs_or_rev * inv_days_to_use, 365, default=0)
        
        if deb_days_to_use > 0:
            projected_receivables = safe_divide(projected_revenue * deb_days_to_use, 365, default=0)
        
        if cred_days_to_use > 0:
            projected_payables = safe_divide(projected_cogs_or_rev * cred_days_to_use, 365, default=0)
        
        # ROBUST: Ensure all WC components are valid numbers
        projected_inventory = ensure_valid_number(projected_inventory, 0)
        projected_receivables = ensure_valid_number(projected_receivables, 0)
        projected_payables = ensure_valid_number(projected_payables, 0)
        
        # Calculate projected WC
        projected_wc = projected_inventory + projected_receivables - projected_payables
        projected_wc = ensure_valid_number(projected_wc, 0)
        
        # USER OVERRIDE: Working Capital as % of Revenue takes priority over
        # the days-based build-up above
        if working_capital_pct_override:
            projected_wc = projected_revenue * (float(working_capital_pct_override) / 100)
            projected_wc = ensure_valid_number(projected_wc, 0)
        
        # Calculate change in WC
        delta_wc = projected_wc - last_wc
        delta_wc = ensure_valid_number(delta_wc, 0)
        
        # CRITICAL: Cap WC changes to prevent unrealistic swings
        # Industry practice: ΔWC shouldn't exceed 20% of revenue
        max_delta_wc = projected_revenue * 0.20
        if abs(delta_wc) > max_delta_wc:
            delta_wc = max_delta_wc if delta_wc > 0 else -max_delta_wc
            projected_wc = last_wc + delta_wc
            projected_wc = ensure_valid_number(projected_wc, 0)
            delta_wc = ensure_valid_number(delta_wc, 0)
        
        # ============================================
        # FCFF CALCULATION
        # ROBUST: Ensure all components are valid numbers before calculation
        # ============================================
        projected_nopat = ensure_valid_number(projected_nopat, 0)
        projected_dep = ensure_valid_number(projected_dep, 0)
        delta_wc = ensure_valid_number(delta_wc, 0)
        capex = ensure_valid_number(capex, 0)
        
        fcff = projected_nopat + projected_dep - delta_wc - capex
        fcff = ensure_valid_number(fcff, 0)  # Ensure FCFF is never NaN
        
        # SANITY CHECK: Only intervene if FCFF is extremely negative AND components are likely invalid
        # Removed aggressive normalization that was incorrectly zeroing out legitimate working capital changes
        # Negative FCFF is acceptable for high-growth companies with working capital needs
        
        # ============================================
        # STORE PROJECTIONS
        # ============================================
        projections['year'].append(year)
        projections['revenue'].append(projected_revenue)
        projections['cogs'].append(projected_cogs)
        projections['opex'].append(projected_opex)
        projections['ebitda'].append(projected_ebitda)
        projections['depreciation'].append(projected_dep)
        projections['ebit'].append(projected_ebit)
        projections['interest'].append(projected_interest)
        projections['nopat'].append(projected_nopat)
        projections['fixed_assets'].append(projected_fa)
        projections['equity'].append(last_equity * (1 + avg_equity_growth / 100))
        projections['debt'].append(projected_debt)
        projections['wc'].append(projected_wc)
        projections['delta_wc'].append(delta_wc)
        projections['capex'].append(capex)
        projections['fcff'].append(fcff)
        
        # Update for next iteration
        last_revenue = projected_revenue
        last_fa = projected_fa
        last_equity = projections['equity'][-1]
        last_debt = projected_debt
        last_wc = projected_wc
    
    return projections, {
        'avg_growth': avg_growth,
        'avg_cogs_margin': avg_cogs_margin,
        'avg_opex_margin': avg_opex_margin,
        'avg_dep_rate': avg_dep_rate,
        'avg_fin_cost_rate': avg_fin_cost_rate,
        'avg_capex_ratio': avg_capex_ratio
    }

def calculate_peer_unlevered_beta(peer_tickers, target_financials, tax_rate, period_years=3,
                                   beta_start_date=None, beta_end_date=None):
    """
    Hamada-equation beta pipeline:
      1. Fetch 3-year raw (levered) beta for every comp ticker.
      2. Unlever each beta using the peer's own D/E ratio.
      3. Average the unlevered betas.
      4. Relever the average using the TARGET company's D/E ratio.

    Hamada formula:
        β_L  = β_U × [1 + (1 − t) × D/E]
        β_U  = β_L  / [1 + (1 − t) × D/E]

    Args:
        peer_tickers  : comma-separated ticker strings (may include .NS/.BO).
        target_financials : financials dict of the company being valued.
        tax_rate      : effective tax rate % (e.g. 25.0).
        period_years  : lookback for beta regression (default 3).

    Returns:
        dict with keys:
            relevered_beta, avg_unlevered_beta, peer_details,
            target_de_ratio, n_peers_used
    """
    import time, random

    ticker_list = [t.strip() for t in peer_tickers.split(',') if t.strip()]
    t = tax_rate / 100.0

    # ── Target D/E from the TARGET company's own balance sheet ──────────
    tgt_eq   = ensure_valid_number(target_financials['equity'][0], 1)   # Lacs
    tgt_std  = ensure_valid_number(target_financials['st_debt'][0], 0)
    tgt_ltd  = ensure_valid_number(target_financials['lt_debt'][0], 0)
    tgt_debt = tgt_std + tgt_ltd
    target_de = tgt_debt / tgt_eq if tgt_eq > 0 else 0.0

    peer_details    = []
    unlevered_betas = []

    for ticker in ticker_list:
        try:
            # Small polite delay between API calls
            if peer_details:
                time.sleep(random.uniform(0.5, 1.0))

            # ── Step 1: raw (levered) beta via regression ─────────────────
            raw_beta = get_stock_beta(ticker, period_years=period_years,
                                       beta_start_date=beta_start_date,
                                       beta_end_date=beta_end_date)
            if raw_beta <= 0:
                st.caption(f"   ↳ {ticker}: skipped (invalid beta {raw_beta:.3f})")
                continue

            # ── Step 2: peer D/E from yfinance ───────────────────────────
            peer_de = 0.0
            try:
                peer_stock = get_cached_ticker(ticker)

                # .info can legitimately return None – guard every access
                raw_info = peer_stock.info
                info = raw_info if isinstance(raw_info, dict) else {}

                peer_equity = ensure_valid_number(info.get('bookValue', 0), 0)
                peer_price  = ensure_valid_number(
                    info.get('currentPrice') or info.get('regularMarketPrice') or 0, 0)
                peer_shares = ensure_valid_number(info.get('sharesOutstanding', 0), 0)
                peer_mktcap = peer_price * peer_shares if peer_price > 0 and peer_shares > 0 else 0

                # Try balance-sheet debt (balance_sheet may be empty / have no columns)
                peer_bs = peer_stock.balance_sheet
                if peer_bs is not None and not peer_bs.empty and len(peer_bs.columns) > 0:
                    bs_col = peer_bs.columns[0]
                    peer_ltd = safe_extract(peer_bs, 'Long Term Debt', bs_col)                         if 'Long Term Debt' in peer_bs.index else 0
                    peer_std = safe_extract(peer_bs, 'Current Debt', bs_col)                         if 'Current Debt' in peer_bs.index else 0
                else:
                    peer_ltd = peer_std = 0
                peer_total_debt = peer_ltd + peer_std

                # Equity denominator: book value × shares → market cap → 0
                peer_eq_value = (peer_equity * peer_shares
                                 if peer_equity > 0 and peer_shares > 0
                                 else peer_mktcap)
                peer_de = peer_total_debt / peer_eq_value if peer_eq_value > 0 else 0.0
                peer_de = max(0.0, peer_de)
            except Exception:
                peer_de = 0.0   # assume all-equity if we can't fetch

            # ── Step 3: unlever ───────────────────────────────────────────
            # β_U = β_L / [1 + (1-t) × D/E]
            unlevered_beta = raw_beta / (1 + (1 - t) * peer_de)
            unlevered_beta = max(0.1, min(unlevered_beta, 3.0))

            unlevered_betas.append(unlevered_beta)
            peer_details.append({
                'ticker'        : ticker,
                'raw_beta'      : raw_beta,
                'peer_de_ratio' : peer_de,
                'unlevered_beta': unlevered_beta,
            })

            st.caption(
                f"   {ticker} → βL={raw_beta:.3f}, D/E={peer_de:.2f}, "
                f"βU={unlevered_beta:.3f}"
            )

        except Exception as e:
            st.warning(f"⚠️ Beta unlever failed for {ticker}: {str(e)[:80]}")
            continue

    if not unlevered_betas:
        # Hard fallback: return levered beta of 1.0
        return {
            'relevered_beta'    : 1.0,
            'avg_unlevered_beta': 1.0,
            'peer_details'      : [],
            'target_de_ratio'   : target_de,
            'n_peers_used'      : 0,
            'fallback'          : True,
        }

    # ── Step 4: average unlevered betas ──────────────────────────────────
    avg_bu = float(np.mean(unlevered_betas))

    # ── Step 5: relever using target company's D/E ───────────────────────
    # β_L = β_U × [1 + (1-t) × D/E_target]
    relevered_beta = avg_bu * (1 + (1 - t) * target_de)
    relevered_beta = max(0.1, min(relevered_beta, 3.0))

    return {
        'relevered_beta'    : relevered_beta,
        'avg_unlevered_beta': avg_bu,
        'peer_details'      : peer_details,
        'target_de_ratio'   : target_de,
        'n_peers_used'      : len(unlevered_betas),
        'fallback'          : False,
    }


def calculate_wacc(financials, tax_rate, peer_tickers=None, manual_rf_rate=None, manual_rm_rate=None,
                   beta_start_date=None, beta_end_date=None):
    """Calculate WACC with proper beta calculation from peers"""
    # Cost of Equity (Ke)
    # ALWAYS use manual rates (passed from session state), never fetch
    rf = manual_rf_rate if manual_rf_rate is not None else 6.83
    rm = manual_rm_rate if manual_rm_rate is not None else 12.0
    
    # ── Beta: unlever peer betas → average → relever for target ──────────
    beta = 1.0
    beta_details = {}
    if peer_tickers and peer_tickers.strip():
        st.markdown("#### 🔢 Beta Calculation (Hamada Unlevering / Relevering)")
        if beta_start_date and beta_end_date:
            _bd_label = f"{pd.Timestamp(beta_start_date).strftime('%d-%b-%Y')} → {pd.Timestamp(beta_end_date).strftime('%d-%b-%Y')}"
        else:
            _bd_label = "3-year rolling window (default)"
        st.caption(
            f"Beta window: {_bd_label} | Daily returns | "
            "Unlever each peer β (Hamada) → average → relever to target D/E."
        )
        beta_result = calculate_peer_unlevered_beta(
            peer_tickers, financials, tax_rate, period_years=3,
            beta_start_date=beta_start_date, beta_end_date=beta_end_date
        )
        beta         = beta_result['relevered_beta']
        beta_details = beta_result

        if beta_result.get('fallback'):
            st.warning("⚠️ Could not compute unlevered beta from peers — using default β=1.0")
        else:
            st.success(
                f"✅ Avg Unlevered β = {beta_result['avg_unlevered_beta']:.3f} | "
                f"Target D/E = {beta_result['target_de_ratio']:.2f} | "
                f"**Relevered β = {beta:.3f}** "
                f"(from {beta_result['n_peers_used']} peers)"
            )
            with st.expander("📋 Beta Breakdown by Peer"):
                for pd_row in beta_result['peer_details']:
                    st.write(
                        f"• **{pd_row['ticker']}** | "
                        f"Levered β = {pd_row['raw_beta']:.3f} | "
                        f"Peer D/E = {pd_row['peer_de_ratio']:.2f} | "
                        f"Unlevered β = {pd_row['unlevered_beta']:.3f}"
                    )
    else:
        st.warning("⚠️ No peer tickers provided, using default β=1.0")

    ke = rf + (beta * (rm - rf))
    
    # Cost of Debt (Kd) - USE NEWEST values (index 0)
    # Handle debt properly - could be 0 or NaN
    st_debt = financials['st_debt'][0] if financials['st_debt'][0] > 0 else 0
    lt_debt = financials['lt_debt'][0] if financials['lt_debt'][0] > 0 else 0
    total_debt = st_debt + lt_debt
    interest = financials['interest'][0]
    
    # Cost of Debt - handle zero/NaN debt
    if total_debt > 0 and interest > 0:
        kd = (interest / total_debt * 100)
    else:
        kd = 0.0  # Debt-free company has no cost of debt
    kd_after_tax = kd * (1 - tax_rate / 100)
    
    # WACC - USE NEWEST equity (index 0)
    equity = financials['equity'][0]
    total_capital = equity + total_debt
    
    # Handle weights - CRITICAL: Support negative equity scenarios
    # When equity is negative, weights can be >100% or negative
    if total_capital != 0:
        we = equity / total_capital
        wd = total_debt / total_capital
    else:
        # Edge case: total capital = 0 (equity = -debt)
        we = 1.0
        wd = 0.0
    
    wacc = (we * ke) + (wd * kd_after_tax)
    
    return {
        'wacc': wacc,
        'ke': ke,
        'kd': kd,
        'kd_after_tax': kd_after_tax,
        'rf': rf,
        'rm': rm,
        'beta': beta,
        'we': we * 100,
        'wd': wd * 100,
        'equity': equity,
        'debt': total_debt,
        'beta_details': beta_details,
    }

def calculate_wacc_bank(financials, tax_rate, peer_tickers=None, manual_rf_rate=None, manual_rm_rate=None,
                        beta_start_date=None, beta_end_date=None):
    """
    Calculate WACC for BANKS/NBFCs with proper Cost of Funds methodology
    
    For banks:
    - Kd = Cost of Funds (WACF) = Interest Expended / Average Interest-Bearing Liabilities
    - Interest-bearing liabilities include: Deposits, Borrowings, Bonds, Subordinated debt
    - NOT just simple Interest/Debt ratio (that's wrong for banks!)
    """
    
    # Cost of Equity (Ke) - Same as normal companies
    # ALWAYS use manual rates (passed from session state), never fetch
    rf = manual_rf_rate if manual_rf_rate is not None else 6.83
    rm = manual_rm_rate if manual_rm_rate is not None else 12.0
    
    # ── Beta: unlever peer betas → average → relever for target (Bank) ────
    beta = 1.0
    beta_details = {}
    if peer_tickers and peer_tickers.strip():
        st.markdown("#### 🔢 Beta Calculation (Hamada Unlevering / Relevering) — Bank Mode")
        if beta_start_date and beta_end_date:
            _bd_label = f"{pd.Timestamp(beta_start_date).strftime('%d-%b-%Y')} → {pd.Timestamp(beta_end_date).strftime('%d-%b-%Y')}"
        else:
            _bd_label = "3-year rolling window (default)"
        st.caption(
            f"Beta window: {_bd_label} | Daily returns | "
            "Unlevering peer betas then relevering to target bank's own D/E."
        )
        beta_result = calculate_peer_unlevered_beta(
            peer_tickers, financials, tax_rate, period_years=3,
            beta_start_date=beta_start_date, beta_end_date=beta_end_date
        )
        beta         = beta_result['relevered_beta']
        beta_details = beta_result

        if beta_result.get('fallback'):
            st.warning("⚠️ Could not compute unlevered beta — using default β=1.0")
        else:
            st.success(
                f"✅ Avg Unlevered β = {beta_result['avg_unlevered_beta']:.3f} | "
                f"Target D/E = {beta_result['target_de_ratio']:.2f} | "
                f"**Relevered β = {beta:.3f}** "
                f"(from {beta_result['n_peers_used']} bank peers)"
            )
            with st.expander("📋 Bank Beta Breakdown by Peer"):
                for pd_row in beta_result['peer_details']:
                    st.write(
                        f"• **{pd_row['ticker']}** | "
                        f"Levered β = {pd_row['raw_beta']:.3f} | "
                        f"Peer D/E = {pd_row['peer_de_ratio']:.2f} | "
                        f"Unlevered β = {pd_row['unlevered_beta']:.3f}"
                    )
    
    ke = rf + (beta * (rm - rf))
    
    # Cost of Debt (Kd) - BANK METHODOLOGY
    # Kd = WACF (Weighted Average Cost of Funds)
    # Formula: Interest Expended / Average Interest-Bearing Liabilities
    
    interest_expense = financials['interest'][0]  # Total interest paid
    
    # Interest-bearing liabilities (need to calculate from balance sheet)
    # For banks: Deposits + Borrowings = primary interest-bearing liabilities
    # We approximate: Total Liabilities - Equity - Other non-interest liabilities
    
    equity_current = financials['equity'][0]
    equity_previous = financials['equity'][1] if len(financials['equity']) > 1 else equity_current
    
    # For banks, we need total assets - equity = total liabilities (most are interest-bearing)
    # Rough approximation: Use debt as proxy for interest-bearing liabilities
    st_debt_current = financials['st_debt'][0] if financials['st_debt'][0] > 0 else 0
    lt_debt_current = financials['lt_debt'][0] if financials['lt_debt'][0] > 0 else 0
    total_liabilities_current = st_debt_current + lt_debt_current
    
    st_debt_previous = financials['st_debt'][1] if len(financials['st_debt']) > 1 and financials['st_debt'][1] > 0 else st_debt_current
    lt_debt_previous = financials['lt_debt'][1] if len(financials['lt_debt']) > 1 and financials['lt_debt'][1] > 0 else lt_debt_current
    total_liabilities_previous = st_debt_previous + lt_debt_previous
    
    # Average interest-bearing liabilities
    avg_interest_bearing_liabilities = (total_liabilities_current + total_liabilities_previous) / 2
    
    # Cost of Funds (Kd for banks)
    if avg_interest_bearing_liabilities > 0 and interest_expense > 0:
        kd = (interest_expense / avg_interest_bearing_liabilities) * 100
        st.info(f"💡 **Bank Cost of Funds (Kd):** {kd:.2f}% = Interest Expended ₹{interest_expense:,.0f} / Avg Liabilities ₹{avg_interest_bearing_liabilities:,.0f}")
    else:
        kd = 5.0  # Default reasonable cost of funds for banks
        st.warning("⚠️ Using default bank cost of funds: 5%")
    
    # For banks, tax shield on interest is different (interest is operating expense, not financing)
    # But for WACC calculation, we still apply tax shield
    kd_after_tax = kd * (1 - tax_rate / 100)
    
    # Capital structure weights
    total_capital = equity_current + total_liabilities_current
    
    # Handle weights - CRITICAL: Support negative equity scenarios
    if total_capital != 0:
        we = equity_current / total_capital
        wd = total_liabilities_current / total_capital
    else:
        # Edge case: total capital = 0 (equity = -debt)
        we = 0.20  # Banks typically have low equity weight
        wd = 0.80
    
    wacc = (we * ke) + (wd * kd_after_tax)
    
    st.success(f"✅ **Bank WACC Calculated:** {wacc:.2f}% | Equity Weight: {we*100:.1f}% | Debt Weight: {wd*100:.1f}%")
    
    return {
        'wacc': wacc,
        'ke': ke,
        'kd': kd,
        'kd_after_tax': kd_after_tax,
        'rf': rf,
        'rm': rm,
        'beta': beta,
        'we': we * 100,
        'wd': wd * 100,
        'equity': equity_current,
        'debt': total_liabilities_current,
        'calculation_method': 'Bank Methodology (Cost of Funds)',
        'interest_expense': interest_expense,
        'avg_liabilities': avg_interest_bearing_liabilities,
        'beta_details': beta_details,
    }

def calculate_dcf_valuation(projections, wacc_details, terminal_growth, num_shares, cash_balance=0, manual_discount_rate=None):
    """
    Calculate DCF valuation with Rulebook-compliant validations and intelligent FCFF recovery
    
    Args:
        manual_discount_rate: Optional manual override for discount rate (instead of WACC)
    """
    # Use manual discount rate if provided, otherwise use WACC
    if manual_discount_rate and manual_discount_rate > 0:
        wacc = manual_discount_rate
        discount_rate_source = f"Manual Override ({manual_discount_rate:.2f}%)"
    else:
        wacc = wacc_details['wacc']
        discount_rate_source = f"WACC ({wacc:.2f}%)"
    
    g = terminal_growth
    
    # RULEBOOK SECTION 8.2: Terminal growth must be < discount rate
    if g >= wacc:
        return None, f"❌ HARD ERROR: Terminal growth rate must be less than discount rate (Rulebook 8.2). Current: TG={g:.1f}%, Discount={wacc:.1f}%"
    
    # CRITICAL FIX: Terminal growth should generally be lower than long-term revenue growth
    # Extract revenue growth from projections
    if len(projections['revenue']) >= 2:
        first_rev = projections['revenue'][0]
        last_rev = projections['revenue'][-1]
        num_years = len(projections['revenue']) - 1
        
        # BUGFIX: Protect against zero/negative revenues to prevent ZeroDivisionError
        if first_rev > 0 and last_rev > 0:
            implied_revenue_cagr = ((last_rev / first_rev) ** (1 / num_years) - 1) * 100
        else:
            implied_revenue_cagr = 0  # Default to 0 if revenue data is invalid
            st.warning("⚠️ Revenue data contains zero or negative values. Cannot calculate revenue CAGR.")
        
        # Warning if terminal growth is too close to revenue growth
        if g > implied_revenue_cagr * 0.9 and implied_revenue_cagr > 0:
            st.warning(f"⚠️ Terminal Growth Rate ({g:.1f}%) is very close to projected revenue CAGR ({implied_revenue_cagr:.1f}%)")
            st.info("💡 **Recommendation:** Terminal growth should typically be 40-60% of revenue growth for conservative valuations")
    
    # RULEBOOK SECTION 8.2: Check terminal year FCFF
    last_fcff = projections['fcff'][-1]
    fcff_adjusted = False
    adjustment_details = {}
    
    if last_fcff <= 0:
        # =====================================================
        # INTELLIGENT FCFF RECOVERY MECHANISM
        # =====================================================
        st.warning(f"⚠️ Terminal year FCFF is {last_fcff:.2f} Lacs (negative or zero)")
        st.info("🔧 **Activating Intelligent FCFF Recovery Mechanism**")
        
        # Analyze all projected FCFFs to understand the issue
        all_fcffs = projections['fcff']
        positive_fcffs = [f for f in all_fcffs if f > 0]
        
        # Even if NO positive FCFFs, we can still recover using ULTRA-AGGRESSIVE strategies
        if len(positive_fcffs) == 0:
            st.error("⚠️ **SEVERE CASE:** All projected FCFFs are negative or zero")
            st.warning("🔧 **Activating ULTRA-AGGRESSIVE Recovery Mechanisms**")
            st.caption("Using fundamental value drivers to construct viable terminal FCFF")
        
        # Calculate intelligent adjustments
        avg_positive_fcff = np.mean(positive_fcffs) if positive_fcffs else 0
        median_positive_fcff = np.median(positive_fcffs) if positive_fcffs else 0
        max_fcff = max(all_fcffs) if all_fcffs else 0
        
        # Analyze components to find best recovery path
        last_nopat = projections['nopat'][-1]
        last_dep = projections['depreciation'][-1]
        last_dwc = projections['delta_wc'][-1]
        last_capex = projections['capex'][-1]
        
        # Calculate component ratios
        revenue = projections['revenue'][-1]
        ebitda = projections['ebitda'][-1]
        
        # INTELLIGENT RECOVERY STRATEGIES
        recovery_options = []
        
        # =====================================================
        # ULTRA-AGGRESSIVE STRATEGIES (For severe cases with all negative FCFFs)
        # =====================================================
        
        # Ultra Strategy 1: Revenue-Based Proxy with Industry Margins
        if revenue > 0:
            # Assume industry-standard metrics:
            # - Operating Margin: 10-15% (conservative for mature company)
            # - Tax Rate: from WACC details or default 25%
            # - FCFF/Revenue: 5-8% for mature companies
            tax_rate = wacc_details.get('tax_rate', 25)
            
            # Conservative approach: 6% FCFF/Revenue ratio
            fcff_from_revenue = revenue * 0.06
            
            if fcff_from_revenue > 0:
                recovery_options.append({
                    'strategy': 'Revenue-Based Proxy (Ultra-Aggressive)',
                    'fcff': fcff_from_revenue,
                    'adjustments': {
                        'revenue': f'₹{revenue:.2f} Lacs',
                        'fcff_margin': '6% of Revenue (conservative industry standard)',
                        'rationale': 'Assumes normalized mature company cash conversion',
                        'calculated_fcff': f'{fcff_from_revenue:.2f} Lacs'
                    }
                })
        
        # Ultra Strategy 2: Reverse-Engineered from Growth Rate
        # If we know terminal growth rate, work backwards from sustainable metrics
        if terminal_growth > 0 and revenue > 0:
            # Sustainable FCFF = Revenue × Terminal Growth × FCFF/Growth ratio
            # Typical FCFF/Growth ratio: 2-4 (i.e., if growing at 5%, FCFF ~10-20% of revenue)
            sustainable_fcff = revenue * (terminal_growth / 100) * 2.5
            
            if sustainable_fcff > 0:
                recovery_options.append({
                    'strategy': 'Growth-Reverse-Engineered (Ultra-Aggressive)',
                    'fcff': sustainable_fcff,
                    'adjustments': {
                        'terminal_growth': f'{terminal_growth}%',
                        'revenue': f'₹{revenue:.2f} Lacs',
                        'fcff_growth_ratio': '2.5x (industry standard)',
                        'logic': f'Sustainable FCFF = Revenue × {terminal_growth}% × 2.5',
                        'calculated_fcff': f'{sustainable_fcff:.2f} Lacs'
                    }
                })
        
        # Ultra Strategy 3: NOPAT-Based with Zero CapEx/WC (Absolute Floor)
        # Assumes company transitions to asset-light model
        if last_nopat > 0:
            fcff_nopat_only = last_nopat + last_dep  # Just operating cash
            
            if fcff_nopat_only > 0:
                recovery_options.append({
                    'strategy': 'NOPAT-Based Floor (Ultra-Aggressive)',
                    'fcff': fcff_nopat_only,
                    'adjustments': {
                        'nopat': f'₹{last_nopat:.2f} Lacs',
                        'depreciation': f'₹{last_dep:.2f} Lacs',
                        'capex': 'Assumed ZERO (asset-light transition)',
                        'working_capital': 'Assumed ZERO (normalized)',
                        'calculated_fcff': f'{fcff_nopat_only:.2f} Lacs'
                    }
                })
        
        # Ultra Strategy 4: Operating Cash Flow Proxy
        # EBITDA - Tax (ignoring all capital requirements)
        if ebitda > 0:
            tax_rate = wacc_details.get('tax_rate', 25)
            operating_cash = ebitda * (1 - tax_rate / 100)
            
            if operating_cash > 0:
                recovery_options.append({
                    'strategy': 'Operating Cash Proxy (Ultra-Aggressive)',
                    'fcff': operating_cash,
                    'adjustments': {
                        'ebitda': f'₹{ebitda:.2f} Lacs',
                        'tax_rate': f'{tax_rate}%',
                        'assumption': 'Pure operating cash, no capital requirements',
                        'calculated_fcff': f'{operating_cash:.2f} Lacs'
                    }
                })
        
        # Ultra Strategy 5: Minimum Viable FCFF (Absolute Last Resort)
        # Use 3% of revenue as bare minimum sustainable cash generation
        if revenue > 0:
            min_viable_fcff = revenue * 0.03
            
            recovery_options.append({
                'strategy': 'Minimum Viable FCFF (Last Resort)',
                'fcff': min_viable_fcff,
                'adjustments': {
                    'revenue': f'₹{revenue:.2f} Lacs',
                    'fcff_margin': '3% of Revenue (bare minimum)',
                    'rationale': 'Absolute floor for sustainable operations',
                    'note': 'This is the MOST aggressive assumption',
                    'calculated_fcff': f'{min_viable_fcff:.2f} Lacs'
                }
            })
        
        # =====================================================
        # STANDARD RECOVERY STRATEGIES
        # =====================================================
        
        # Strategy 1: Reduce CapEx to sustainable level (typically 80% of depreciation)
        sustainable_capex = last_dep * 0.8
        capex_savings = last_capex - sustainable_capex if last_capex > sustainable_capex else 0
        fcff_with_capex_adj = last_nopat + last_dep - last_dwc - sustainable_capex
        if fcff_with_capex_adj > 0:
            recovery_options.append({
                'strategy': 'Reduced CapEx to Sustainable Level',
                'fcff': fcff_with_capex_adj,
                'adjustments': {
                    'capex': f'Reduced from {last_capex:.2f} to {sustainable_capex:.2f} Lacs (80% of Depreciation)',
                    'savings': f'CapEx savings: {capex_savings:.2f} Lacs'
                }
            })
        
        # Strategy 2: Normalize Working Capital (assume zero working capital change in terminal year)
        fcff_with_wc_normalization = last_nopat + last_dep - last_capex
        if fcff_with_wc_normalization > 0:
            recovery_options.append({
                'strategy': 'Normalized Working Capital',
                'fcff': fcff_with_wc_normalization,
                'adjustments': {
                    'working_capital': f'Set ΔWC to 0 (from {last_dwc:.2f} Lacs)',
                    'assumption': 'Working capital stabilizes at terminal year'
                }
            })
        
        # Strategy 3: Combined approach (sustainable capex + normalized WC)
        fcff_combined = last_nopat + last_dep - sustainable_capex
        if fcff_combined > 0:
            recovery_options.append({
                'strategy': 'Combined: Sustainable CapEx + Normalized WC',
                'fcff': fcff_combined,
                'adjustments': {
                    'capex': f'CapEx at 80% depreciation: {sustainable_capex:.2f} Lacs',
                    'working_capital': 'ΔWC = 0 (normalized)',
                    'combined_impact': f'Total improvement: {fcff_combined - last_fcff:.2f} Lacs'
                }
            })
        
        # Strategy 4: Use average of positive FCFFs (conservative)
        if avg_positive_fcff > 0:
            recovery_options.append({
                'strategy': 'Average of Positive Historical FCFFs',
                'fcff': avg_positive_fcff,
                'adjustments': {
                    'basis': f'Average of {len(positive_fcffs)} positive FCFF years',
                    'value': f'{avg_positive_fcff:.2f} Lacs',
                    'rationale': 'Uses historical positive cash generation as sustainable baseline'
                }
            })
        
        # Strategy 5: EBITDA-based proxy (if operations are profitable)
        if ebitda > 0:
            # Typical FCFF = ~40-60% of EBITDA for mature companies
            fcff_from_ebitda = ebitda * 0.5 * (1 - wacc_details.get('tax_rate', 25) / 100)
            if fcff_from_ebitda > 0:
                recovery_options.append({
                    'strategy': 'EBITDA-Based Proxy',
                    'fcff': fcff_from_ebitda,
                    'adjustments': {
                        'ebitda': f'{ebitda:.2f} Lacs',
                        'conversion': '50% FCFF/EBITDA ratio (industry standard)',
                        'tax_adjusted': 'Applied tax rate',
                        'calculated_fcff': f'{fcff_from_ebitda:.2f} Lacs'
                    }
                })
        
        # Select BEST recovery option
        # With ultra-aggressive strategies, we ALWAYS have at least one option
        if not recovery_options:
            # Absolute fallback - should never reach here
            # Create emergency FCFF based on revenue if available
            if revenue > 0:
                emergency_fcff = revenue * 0.02  # 2% of revenue
                recovery_options.append({
                    'strategy': 'Emergency Fallback (2% of Revenue)',
                    'fcff': emergency_fcff,
                    'adjustments': {
                        'note': 'Emergency fallback - uses minimal assumptions',
                        'revenue': f'₹{revenue:.2f} Lacs',
                        'calculated_fcff': f'{emergency_fcff:.2f} Lacs'
                    }
                })
            elif ebitda > 0:
                emergency_fcff = ebitda * 0.3  # 30% of EBITDA
                recovery_options.append({
                    'strategy': 'Emergency Fallback (30% of EBITDA)',
                    'fcff': emergency_fcff,
                    'adjustments': {
                        'note': 'Emergency fallback - uses minimal assumptions',
                        'ebitda': f'₹{ebitda:.2f} Lacs',
                        'calculated_fcff': f'{emergency_fcff:.2f} Lacs'
                    }
                })
            else:
                # Truly desperate - use 1 Lac as minimum
                recovery_options.append({
                    'strategy': 'Absolute Minimum (₹1 Lac)',
                    'fcff': 1.0,
                    'adjustments': {
                        'note': '⚠️ No viable metrics available - using symbolic minimum',
                        'warning': 'Valuation highly uncertain - use with extreme caution'
                    }
                })
        
        # Rank by FCFF value (higher is better, but prefer more conservative approaches)
        # Preference order: Standard strategies > Ultra-aggressive strategies
        strategy_preference = {
            # Standard strategies (highest priority)
            'Combined: Sustainable CapEx + Normalized WC': 10,
            'Reduced CapEx to Sustainable Level': 9,
            'Normalized Working Capital': 8,
            'Average of Positive Historical FCFFs': 7,
            'EBITDA-Based Proxy': 6,
            # Ultra-aggressive strategies (medium priority)
            'Revenue-Based Proxy (Ultra-Aggressive)': 5,
            'Growth-Reverse-Engineered (Ultra-Aggressive)': 4,
            'NOPAT-Based Floor (Ultra-Aggressive)': 3,
            'Operating Cash Proxy (Ultra-Aggressive)': 2,
            'Minimum Viable FCFF (Last Resort)': 1,
            # Emergency fallbacks (lowest priority)
            'Emergency Fallback (2% of Revenue)': 0.5,
            'Emergency Fallback (30% of EBITDA)': 0.4,
            'Absolute Minimum (₹1 Lac)': 0.1
        }
        
        # Sort by preference, then by FCFF value
        best_option = max(recovery_options, 
                         key=lambda x: (strategy_preference.get(x['strategy'], 0), x['fcff']))
        
        # Apply the best recovery strategy
        last_fcff = best_option['fcff']
        fcff_adjusted = True
        adjustment_details = best_option
        
        # Display the recovery strategy
        st.success(f"✅ **Selected Recovery Strategy:** {best_option['strategy']}")
        st.write(f"**Adjusted Terminal FCFF:** ₹{last_fcff:.2f} Lacs (Original: ₹{projections['fcff'][-1]:.2f} Lacs)")
        
        # Add extra warning for ultra-aggressive strategies
        if 'Ultra-Aggressive' in best_option['strategy'] or 'Last Resort' in best_option['strategy'] or 'Emergency' in best_option['strategy'] or 'Absolute' in best_option['strategy']:
            st.warning("⚠️ **CAUTION:** This strategy uses aggressive assumptions due to severe cash flow issues")
            st.caption("💡 Recommendation: Cross-validate with alternative valuation methods (P/E, P/B, EV/EBITDA)")
        
        with st.expander("📋 View All Recovery Options Considered"):
            for i, opt in enumerate(recovery_options, 1):
                st.markdown(f"### Option {i}: {opt['strategy']}")
                st.write(f"**Resulting FCFF:** ₹{opt['fcff']:.2f} Lacs")
                st.write("**Adjustments:**")
                for key, value in opt['adjustments'].items():
                    st.write(f"  - {key.replace('_', ' ').title()}: {value}")
                if opt == best_option:
                    st.success("✅ **SELECTED** (Best balance of conservatism and cash flow)")
                st.markdown("---")
        
        st.info("💡 **Note:** These adjustments reflect sustainable long-term assumptions required for terminal value calculation.")
        
        # CRITICAL: Update projections with adjusted terminal FCFF
        # This ensures all downstream calculations use the recovered value
        projections['fcff'][-1] = last_fcff
        st.caption(f"📌 Terminal year FCFF in projections updated to ₹{last_fcff:.2f} Lacs")
    
    # Present Value of FCFFs
    pv_fcffs = []
    for i, fcff in enumerate(projections['fcff']):
        year = i + 1
        pv = fcff / ((1 + wacc / 100) ** year)
        pv_fcffs.append(pv)
    
    sum_pv_fcff = sum(pv_fcffs)
    
    # CRITICAL CHECK: If sum of PV(FCFF) is negative, we need additional recovery
    # This happens when ALL or most FCFFs are negative (high growth/investment phase)
    growth_phase_adjusted = False
    original_sum_pv_fcff = sum_pv_fcff
    
    if sum_pv_fcff < 0:
        st.warning(f"⚠️ **Additional Issue Detected:** Sum of PV(FCFF) is negative (₹{sum_pv_fcff:.2f} Lacs)")
        st.info("🔧 **Applying Growth-Phase Adjustment**: Treating as high-growth company transitioning to maturity")
        
        # For high-growth companies, we should focus entirely on terminal value
        # Set sum_pv_fcff to zero (ignore negative cash flows during growth phase)
        sum_pv_fcff = 0
        growth_phase_adjusted = True
        
        st.success(f"✅ **Growth-Phase Adjustment Applied:**")
        st.write(f"   - Original Sum PV(FCFF): ₹{original_sum_pv_fcff:.2f} Lacs (negative due to growth)")
        st.write(f"   - Adjusted Sum PV(FCFF): ₹{sum_pv_fcff:.2f} Lacs (set to zero)")
        st.write(f"   - **Rationale:** Company in high-growth phase; value comes from mature cash flows")
        st.caption("💡 This is common for high-growth companies that invest heavily before generating positive cash flows")
    
    # Terminal Value (Rulebook Section 8.1)
    fcff_n_plus_1 = last_fcff * (1 + g / 100)
    terminal_value = fcff_n_plus_1 / ((wacc / 100) - (g / 100))
    
    n = len(projections['fcff'])
    pv_terminal_value = terminal_value / ((1 + wacc / 100) ** n)
    
    # Enterprise Value (in Lacs)
    enterprise_value = sum_pv_fcff + pv_terminal_value
    
    # RULEBOOK SECTION 13.1: Terminal Value sanity checks
    tv_percentage = (pv_terminal_value / enterprise_value * 100) if enterprise_value > 0 else 0
    
    if tv_percentage > 100:
        return None, f"❌ ERROR: Terminal Value ({tv_percentage:.1f}%) exceeds 100% of Enterprise Value (Rulebook 13.1)"
    
    # Equity Value Calculation: EV - Net Debt
    # Handle debt properly (could be 0, None, or NaN for debt-free companies)
    total_debt = wacc_details.get('debt', 0)
    if total_debt is None or (isinstance(total_debt, float) and np.isnan(total_debt)):
        total_debt = 0
    total_debt = float(total_debt) if total_debt > 0 else 0
    
    # Handle cash properly (extract from parameter, could be 0)
    cash = float(cash_balance) if cash_balance and cash_balance > 0 else 0
    
    # Net Debt = Total Debt - Cash
    # Can be negative (net cash position) if cash > debt
    net_debt = total_debt - cash
    
    # Equity Value = Enterprise Value - Net Debt
    # For debt-free companies: EV - (-cash) = EV + cash
    equity_value = enterprise_value - net_debt
    
    # Convert Equity Value from Lacs to absolute Rupees, then divide by shares
    # Equity Value is in Lacs, so multiply by 100,000 to get Rupees
    equity_value_rupees = equity_value * 100000
    fair_value_per_share = equity_value_rupees / num_shares if num_shares > 0 else 0
    
    # CRITICAL VALIDATION: Check if fair value is negative
    negative_fair_value_warning = None
    if fair_value_per_share < 0:
        negative_fair_value_warning = {
            'enterprise_value': enterprise_value,
            'total_debt': total_debt,
            'cash': cash,
            'net_debt': net_debt,
            'equity_value': equity_value,
            'num_shares': num_shares,
            'reason': []
        }
        
        # Diagnose the problem
        if enterprise_value < net_debt:
            negative_fair_value_warning['reason'].append(
                f"Enterprise Value (₹{enterprise_value:.2f} Lacs) is less than Net Debt (₹{net_debt:.2f} Lacs)"
            )
        if enterprise_value <= 0:
            negative_fair_value_warning['reason'].append(
                f"Enterprise Value is zero or negative (₹{enterprise_value:.2f} Lacs)"
            )
        if net_debt > enterprise_value * 2:
            negative_fair_value_warning['reason'].append(
                f"Net Debt (₹{net_debt:.2f} Lacs) is more than 2x Enterprise Value"
            )
    
    return {
        'pv_fcffs': pv_fcffs,
        'sum_pv_fcff': sum_pv_fcff,
        'original_sum_pv_fcff': original_sum_pv_fcff if growth_phase_adjusted else sum_pv_fcff,
        'growth_phase_adjusted': growth_phase_adjusted,
        'terminal_value': terminal_value,
        'pv_terminal_value': pv_terminal_value,
        'enterprise_value': enterprise_value,
        'total_debt': total_debt,
        'cash': cash,
        'net_debt': net_debt,
        'equity_value': equity_value,
        'equity_value_rupees': equity_value_rupees,
        'fair_value_per_share': fair_value_per_share,
        'tv_percentage': tv_percentage,
        'tv_warning': tv_percentage > 90,  # Flag for warning
        'fcff_adjusted': fcff_adjusted,
        'adjustment_details': adjustment_details if fcff_adjusted else None,
        'adjusted_terminal_fcff': last_fcff if fcff_adjusted else projections['fcff'][-1],
        'negative_fair_value_warning': negative_fair_value_warning,
        'wacc': wacc,
        'discount_rate_source': discount_rate_source
    }, None
# ================================
# MAIN UI FUNCTION
# ================================
