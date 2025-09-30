#!/usr/bin/env python
# coding: utf-8

# In[7]:


import os
from pathlib import Path


def _load_env() -> None:
    """Load environment variables from a local .env file if available."""
    if os.getenv("BITGET_API_KEY"):
        return
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv  # type: ignore

            load_dotenv(env_path)
        except ImportError:
            pass


_load_env()

API_KEY = os.getenv("BITGET_API_KEY")
SECRET_KEY = os.getenv("BITGET_SECRET")
PASSPHRASE = os.getenv("BITGET_PASSPHRASE")

if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
    raise RuntimeError(
        "Missing Bitget API credentials. Set BITGET_API_KEY, BITGET_SECRET, and "
        "BITGET_PASSPHRASE as environment variables (optionally via a .env file not "
        "checked into version control)."
    )


# In[10]:


import requests
import json
import time
import hmac
import hashlib
import base64
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN


class SimpleBitgetOrderTest:
    def __init__(self, api_key, secret_key, passphrase):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.base_url = "https://api.bitget.com"
        self.symbol_rules = {}  # cache for symbol metadata

    def _generate_signature(self, timestamp, method, request_path, body=''):
        message = timestamp + method.upper() + request_path + body
        signature = base64.b64encode(
            hmac.new(
                self.secret_key.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        return signature

    def _make_request(self, method, endpoint, params=None, data=None, auth=False):
        timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')

        request_path = endpoint
        if params and method.upper() == 'GET':
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            request_path += f"?{query_string}"

        body = json.dumps(data, separators=(',', ':')) if data else ''
        headers = {'Content-Type': 'application/json', 'locale': 'en-US'}

        if auth:
            signature = self._generate_signature(timestamp, method, request_path, body)
            headers.update({
                'ACCESS-KEY': self.api_key,
                'ACCESS-SIGN': signature,
                'ACCESS-TIMESTAMP': timestamp,
                'ACCESS-PASSPHRASE': self.passphrase,
            })

        url = self.base_url + request_path
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                data=body if method.upper() == 'POST' else None,
                timeout=10
            )
            print(f"API Request: {method} {url}")
            print(f"Request Body: {body}")
            print(f"Response Status: {response.status_code}")
            result = response.json()
            print(f"Response: {result}")
            return result
        except Exception as e:
            print(f"API request failed: {e}")
            return None

    def list_symbols(self):
        print("\n=== FETCHING AVAILABLE SYMBOLS ===")
        result = self._make_request('GET', '/api/v2/spot/public/symbols')
        if result and result.get('code') == '00000':
            self.symbol_rules = {}
            for sym in result['data']:
                self.symbol_rules[sym['symbol']] = sym
                if sym['symbol'] in ['BTCUSDT', 'ETHUSDT']:
                    print(
                        f"{sym['symbol']} | minQty={sym['minTradeAmount']} "
                        f"| minNotional={sym['minTradeUSDT']} "
                        f"| pricePrecision={sym['pricePrecision']} "
                        f"| quantityPrecision={sym['quantityPrecision']}"
                    )
            return self.symbol_rules
        else:
            print("Failed to fetch symbols")
            return None

    def get_current_price(self, symbol="BTCUSDT"):
        params = {'symbol': symbol}
        result = self._make_request('GET', '/api/v2/spot/market/tickers', params)
        if result and result.get('code') == '00000' and result.get('data'):
            try:
                price = float(result['data'][0]['lastPr'])
                print(f"Current {symbol} price: ${price:.2f}")
                return price
            except Exception as e:
                print(f"Error parsing ticker: {e}")
        print("Failed to get price")
        return None

    def get_balance(self):
        result = self._make_request('GET', '/api/v2/spot/account/assets', auth=True)
        if result and result.get('code') == '00000':
            for asset in result['data']:
                if asset.get('coin') == 'USDT':
                    balance = float(asset.get('available', 0))
                    print(f"USDT Balance: ${balance:.2f}")
                    return balance
        print("Failed to get balance")
        return 0.0

    def _format_quantity(self, quantity, precision):
        """Format quantity to exact precision without rounding up"""
        decimal_qty = Decimal(str(quantity))
        factor = Decimal(10) ** precision
        return float(decimal_qty.quantize(Decimal(1) / factor, rounding=ROUND_DOWN))

    def test_market_order(self, usd_amount=10.0, symbol="BTCUSDT"):
        print(f"\n=== TESTING MARKET ORDER - ${usd_amount} on {symbol} ===")
        rule = self.symbol_rules.get(symbol)
        if not rule:
            print("No rules cached for symbol, call list_symbols() first")
            return False

        min_notional = float(rule['minTradeUSDT'])
        if usd_amount < min_notional:
            print(f"Amount ${usd_amount} is below minNotional {min_notional}")
            return False

        # Format the size properly
        data = {
            "symbol": symbol,
            "side": "buy",
            "orderType": "market",
            "force": "gtc",
            "size": f"{usd_amount:.2f}",  # For market orders, use "size" for quote quantity (USDT amount)
            "clientOid": f"test_market_{int(time.time() * 1000)}"
        }

        print(f"Market Order Data: {data}")
        result = self._make_request('POST', '/api/v2/spot/trade/place-order', data=data, auth=True)

        if result and result.get('code') == '00000':
            print(f"SUCCESS! Order ID: {result['data']['orderId']}")
            return True
        else:
            print(f"FAILED: {result}")
            return False

    def test_limit_order(self, usd_amount=10.0, symbol="BTCUSDT"):
        print(f"\n=== TESTING LIMIT ORDER on {symbol} ===")
        rule = self.symbol_rules.get(symbol)
        if not rule:
            print("No rules cached for symbol, call list_symbols() first")
            return False

        price_precision = int(rule['pricePrecision'])
        qty_precision = int(rule['quantityPrecision'])
        min_qty = float(rule['minTradeAmount'])
        min_notional = float(rule['minTradeUSDT'])

        current_price = self.get_current_price(symbol)
        if not current_price:
            return False

        # Set limit price slightly below current price for buy order
        limit_price = current_price * 0.999  # 0.1% below current price

        # Calculate quantity based on USD amount
        position_size = usd_amount / limit_price

        # Format price and quantity with proper precision
        formatted_price = f"{limit_price:.{price_precision}f}"
        formatted_qty = self._format_quantity(position_size, qty_precision)

        # Verify minimums
        actual_notional = formatted_qty * limit_price
        if formatted_qty < min_qty or actual_notional < min_notional:
            print(f"Order too small. qty={formatted_qty}, minQty={min_qty}, "
                  f"notional={actual_notional:.2f}, minNotional={min_notional}")
            return False

        # Use correct Bitget v2 API parameter names - "size" not "quantity"!
        data = {
            "symbol": symbol,
            "side": "buy",
            "orderType": "limit",
            "force": "gtc",
            "price": formatted_price,
            "size": f"{formatted_qty:.{qty_precision}f}",  # CRITICAL: Use "size" not "quantity"
            "clientOid": f"test_limit_{int(time.time() * 1000)}"
        }

        print(f"Limit order data: {data}")
        print(f"Calculated: price={limit_price:.{price_precision}f}, qty={formatted_qty:.{qty_precision}f}, notional={actual_notional:.2f}")

        result = self._make_request('POST', '/api/v2/spot/trade/place-order', data=data, auth=True)

        if result and result.get('code') == '00000':
            print("SUCCESS with limit order!")
            return True
        else:
            print("FAILED with limit order")
            return False

    def test_limit_order_v1(self, usd_amount=10.0, symbol="BTCUSDT"):
        """Try V1 API as fallback when V2 permissions fail"""
        print(f"\n=== TESTING V1 LIMIT ORDER on {symbol} ===")
        rule = self.symbol_rules.get(symbol)
        if not rule:
            print("No rules cached for symbol")
            return False

        current_price = self.get_current_price(symbol)
        if not current_price:
            return False

        # V1 API uses different symbol format - add _SPBL suffix
        v1_symbol = symbol + "_SPBL"
        limit_price = current_price * 0.999
        position_size = usd_amount / limit_price

        # Ensure minimum order size for V1 API (needs to be > 1 USDT)
        if usd_amount < 2.0:
            usd_amount = 2.0
            position_size = usd_amount / limit_price
            print(f"Increased order size to ${usd_amount} to meet V1 minimum requirements")

        # V1 API parameters - fixed based on error message
        data = {
            "symbol": v1_symbol.lower(),  # V1 uses lowercase
            "side": "buy",
            "orderType": "limit",
            "price": f"{limit_price:.2f}",
            "quantity": f"{position_size:.6f}",
            "force": "normal",  # Add the missing force parameter
            "clientOrderId": f"test_v1_limit_{int(time.time())}"
        }

        print(f"V1 API data: {data}")
        print(f"Order value: ${position_size * limit_price:.2f}")

        # Use V1 endpoint
        result = self._make_request('POST', '/api/spot/v1/trade/orders', data=data, auth=True)

        if result and result.get('code') == '00000':
            print("SUCCESS with V1 limit order!")
            print("BREAKTHROUGH: V1 API works! You can use V1 endpoints for trading.")
            return True
        else:
            print("FAILED with V1 limit order")
            print(f"Error details: {result}")
            return False

    def test_market_order_v1(self, usd_amount=10.0, symbol="BTCUSDT"):
        """Test V1 market order"""
        print(f"\n=== TESTING V1 MARKET ORDER - ${usd_amount} on {symbol} ===")

        # V1 API uses different symbol format
        v1_symbol = symbol + "_SPBL"

        # Ensure minimum for V1
        if usd_amount < 2.0:
            usd_amount = 2.0
            print(f"Increased order size to ${usd_amount} to meet V1 minimum requirements")

        # V1 market order parameters
        data = {
            "symbol": v1_symbol.lower(),
            "side": "buy",
            "orderType": "market",
            "quantity": f"{usd_amount:.2f}",  # For market orders, quantity is the USDT amount
            "force": "normal",
            "clientOrderId": f"test_v1_market_{int(time.time())}"
        }

        print(f"V1 Market Order Data: {data}")
        result = self._make_request('POST', '/api/spot/v1/trade/orders', data=data, auth=True)

        if result and result.get('code') == '00000':
            print(f"SUCCESS! V1 Market Order ID: {result['data'].get('orderId', 'N/A')}")
            return True
        else:
            print(f"FAILED: V1 Market Order - {result}")
            return False

    def check_account_permissions(self):
        print("\n=== CHECKING ACCOUNT PERMISSIONS ===")
        result = self._make_request('GET', '/api/v2/spot/account/info', auth=True)
        print(f"Account info: {result}")

        # Also check if spot trading is enabled
        if result and result.get('code') == '00000':
            data = result.get('data', {})
            authorities = data.get('authorities', [])
            print(f"Account authorities: {authorities}")

            # Check for spot trading permission
            has_spot = any(auth.lower() in ['spot', 'spow'] for auth in authorities)
            if not has_spot:
                print("CRITICAL: Spot trading is NOT enabled on this account!")
                print("   You need to enable spot trading in your Bitget account settings.")
                print("   Without spot trading enabled, all order placement will fail.")
                return False
            else:
                print("Spot trading appears to be enabled")

        return result

    def get_open_orders(self, symbol="BTCUSDT"):
        """Check for any open orders"""
        print(f"\n=== CHECKING OPEN ORDERS for {symbol} ===")
        params = {'symbol': symbol}
        result = self._make_request('GET', '/api/v2/spot/trade/unfilled-orders', params, auth=True)

        if result and result.get('code') == '00000':
            orders = result.get('data', [])
            print(f"Open orders count: {len(orders)}")
            for order in orders[:3]:  # Show first 3 orders
                print(f"  Order: {order.get('orderId')} - {order.get('side')} {order.get('quantity')} at {order.get('price')}")
            return orders
        else:
            print("Failed to get open orders")
            return []


def main():
    # UNCOMMENT AND ADD YOUR CREDENTIALS
    #API_KEY = "YOUR_API_KEY_HERE"
    #SECRET_KEY = "YOUR_SECRET_KEY_HERE"
    #PASSPHRASE = "YOUR_PASSPHRASE_HERE"

    if API_KEY == "YOUR_API_KEY_HERE":
        print("Please update your API credentials in the script")
        return

    tester = SimpleBitgetOrderTest(API_KEY, SECRET_KEY, PASSPHRASE)

    print("Simple Bitget Order Test - Complete Testing")
    print("=" * 50)

    # Step 1: Get symbol rules
    symbols = tester.list_symbols()
    if not symbols:
        print("Failed to get symbol rules, exiting")
        return

    # Step 2: Check balance
    balance = tester.get_balance()
    if balance < 5:
        print("Need at least $5 balance for comprehensive testing")
        return

    print(f"\nAvailable balance: ${balance:.2f}")

    # Step 3: Test with appropriate amount
    test_amount = max(2.0, min(5.0, balance * 0.05))
    print(f"\nTesting with ${test_amount:.2f} per order")

    # Test all order types with both APIs
    print("\n" + "="*50)
    print("COMPREHENSIVE ORDER TESTING")
    print("="*50)

    print("\n1. Testing V2 Limit Order...")
    v2_limit_success = tester.test_limit_order(usd_amount=test_amount, symbol="BTCUSDT")

    print("\n2. Testing V2 Market Order...")
    v2_market_success = tester.test_market_order(usd_amount=test_amount, symbol="BTCUSDT")

    print("\n3. Testing V1 Limit Order...")
    v1_limit_success = tester.test_limit_order_v1(usd_amount=test_amount, symbol="BTCUSDT")

    print("\n4. Testing V1 Market Order...")
    v1_market_success = tester.test_market_order_v1(usd_amount=test_amount, symbol="BTCUSDT")

    # Summary
    print("\n" + "="*50)
    print("TESTING SUMMARY")
    print("="*50)
    print(f"V2 Limit Orders:  {'Working' if v2_limit_success else 'Failed'}")
    print(f"V2 Market Orders: {'Working' if v2_market_success else 'Failed'}")
    print(f"V1 Limit Orders:  {'Working' if v1_limit_success else 'Failed'}")
    print(f"V1 Market Orders: {'Working' if v1_market_success else 'Failed'}")

    if v2_limit_success and v2_market_success:
        print("\nV2 API fully functional - use this for your trading bot")
    elif v1_limit_success and v1_market_success:
        print("\nV1 API fully functional - reliable fallback option")
    else:
        print("\nPartial functionality - check individual test results above")

    print("\nTesting complete!")


if __name__ == "__main__":
    main()
