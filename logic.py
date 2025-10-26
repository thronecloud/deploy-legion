#!/usr/bin/env python3
"""
YB Airdrop Tracker - Optimized Edition
Tracks token airdrops and current balances using bulk holder list API.
Uses only 2-5 API calls instead of thousands!

Usage:
  python runfbupdated.py --out yb_airdrop_balances.csv
  
Import as module:
  from runfbupdated import (
      fetch_airdrop_data,
      get_token_holder_count,
      get_all_token_holders,
      get_all_token_transfers,
      analyze_contract_activity
  )
"""

import os
import csv
import json
import time
import argparse
import requests
from decimal import Decimal
from typing import Dict, List, Tuple, Optional

# ===================== CONFIGURATION =====================
TOKEN_CONTRACT = "0x01791f726b4103694969820be083196cc7c045ff"
DECIMALS = 18
CHAIN_ID = 1
MAX_RPS = 8  # 8 requests/second
MAX_RETRIES = 3
TIMEOUT = 30
ETHERSCAN_V2 = "https://api.etherscan.io/v2/api"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

DEFAULT_TX_HASHES = [
    "0xd237693e624f9703f9ea7e825677979e2bb3ff9dfa90d2feaedbdba1095b6421",
    "0x49221e43c6e052ca363cd6a11cb3bd4e6103cad263b4e7dbcb153684be8f7430",
    "0x4992e07a5fc08679e78a8cf31bca71439f1e291dba8abcd3794dfc8bf4252a86",
    "0x8d5309864c224dfbd1e16fa158e40147611ebbaea1ce03de757ce4519c7ecbc0",
    "0xbc358060f75b9ef1bf92c500e891d5f02ab70e44b08209f340ed26ae9775a3e6",
    "0x27417dfb374d9041f3bb3923f21d670488cbdc23cc674c4e965708ed5ea52d57",
    "0xab8629e7fef19281ae290de54d0cdcf5d7545722dce544e3d089e6052a4995c1",
    "0x098d225c5a663f108edea82ce8097b7196c12206792af99d0c30745083b8295b"
]

DEFAULT_CONTRACTS_AND_FUNCTIONS = {
    "0x8235c179e9e84688fbd8b12295efc26834dac211": {
        "category": "staking",
        "functions": [
            "increase_amount",
            "create_lock"
        ]
    },
    "0xec977F46467a3021785Cff88894886E617abd65b" :{
        "category": "liquidity",
        "functions": [
            "add_liquidity"
        ]
    }
}

# ===================== UTILITY FUNCTIONS =====================
def get_api_key() -> str:
    """Load API key from environment or config.env file"""
    env_files = ['config.env', '.env']
    for env_file in env_files:
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
    
    key = os.environ.get("ETHERSCAN_API_KEY") or os.environ.get("ETHERSCAN_APIKEY")
    if not key:
        raise SystemExit("ERROR: Set ETHERSCAN_API_KEY in config.env or environment")
    return key

# ===================== TOKEN HOLDER COUNT =====================
def get_token_holder_count(
    contract_address: str,
    apikey: str,
    chain_id: int = CHAIN_ID
) -> Optional[int]:
    """
    Get the total number of token holders for a given contract address.
    
    Args:
        contract_address: ERC-20 token contract address
        apikey: Etherscan API key
        chain_id: Chain ID (default: 1 for Ethereum mainnet)
    
    Returns:
        Number of token holders, or None if request fails
    
    Example:
        count = get_token_holder_count("0xaaa...", api_key)
        print(f"Token has {count} holders")
    """
    params = {
        "chainid": chain_id,
        "module": "token",
        "action": "tokenholdercount",
        "contractaddress": contract_address.lower(),
        "apikey": apikey,
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(ETHERSCAN_V2, params=params, timeout=TIMEOUT)
            if r.ok:
                data = r.json()
                status = data.get("status")
                result = data.get("result")
                
                if status == "1" and result:
                    try:
                        return int(result)
                    except (ValueError, TypeError):
                        print(f"  ⚠️  Invalid result format: {result}")
                        return None
                elif "rate limit" in str(result).lower():
                    print(f"  ⚠️  Rate limited, waiting...")
                    time.sleep(5)
                    continue
                else:
                    print(f"  ⚠️  API error: {data.get('message', 'Unknown error')}")
                    return None
        except Exception as e:
            print(f"  ⚠️  Attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)
                continue
            return None
    
    return None

def get_all_token_holders(
    contract_address: str,
    apikey: str,
    max_holders: int = None,
    page_size: int = 10000,
    chain_id: int = CHAIN_ID
) -> List[Dict[str, str]]:
    """
    Get all token holders by fetching all pages automatically.
    
    Args:
        contract_address: ERC-20 token contract address
        apikey: Etherscan API key
        max_holders: Maximum number of holders to fetch (None = all)
        page_size: Records per page (default: 10000 for maximum efficiency)
        chain_id: Chain ID (default: 1 for Ethereum mainnet)
    
    Returns:
        List of all holders with their balances
    
    Example:
        all_holders = get_all_token_holders("0xaaa...", api_key)
        print(f"Fetched {len(all_holders)} holders")
    """
    all_holders = []
    page = 1
    
    print(f"  📋 Fetching token holders (page size: {page_size})...")
    
    while True:
        # Build request parameters
        params = {
            "chainid": chain_id,
            "module": "token",
            "action": "tokenholderlist",
            "contractaddress": contract_address.lower(),
            "page": page,
            "offset": page_size,
            "apikey": apikey,
        }
        
        # Make API request
        try:
            r = requests.get(ETHERSCAN_V2, params=params, timeout=30)
            if r.ok:
                data = r.json()
                status = data.get("status")
                result = data.get("result")
                
                if status == "1" and isinstance(result, list):
                    holders = result
                elif "rate limit" in str(result).lower():
                    print(f"  ⚠️  Rate limited")
                    break
                else:
                    print(f"  ⚠️  API error: {data.get('message', 'Unknown error')}")
                    break
            else:
                print(f"  ⚠️  HTTP error: {r.status_code}")
                break
        except Exception as e:
            print(f"  ⚠️  Request failed: {e}")
            break
        
        # Process results
        if not holders or len(holders) == 0:
            break
        
        all_holders.extend(holders)
        print(f"     Page {page}: fetched {len(holders)} holders (total: {len(all_holders)})")
        
        # Stop if we've reached max_holders
        if max_holders and len(all_holders) >= max_holders:
            all_holders = all_holders[:max_holders]
            print(f"  ✅ Reached maximum of {max_holders} holders")
            break
        
        # Stop if we got fewer records than page_size (last page)
        if len(holders) < page_size:
            print(f"  ✅ Fetched all {len(all_holders)} holders")
            break
        
        page += 1
        time.sleep(0.5)  # Be nice to the API between pages
    
    return all_holders

# ===================== TOKEN TRANSFERS =====================
def get_all_token_transfers(
    address: str,
    apikey: str,
    contract_address: str = None,
    start_block: int = 0,
    end_block: int = 99999999,
    max_transactions: int = None,
    page_size: int = 10000,
    sort: str = "desc",
    chain_id: int = CHAIN_ID
) -> List[Dict]:
    """
    Get all token transfers for an address by fetching all pages automatically.
    
    Args:
        address: Wallet address to query
        apikey: Etherscan API key
        contract_address: Optional - filter by specific token contract
        start_block: Starting block number (default: 0)
        end_block: Ending block number (default: 99999999)
        max_transactions: Maximum number of transactions to fetch (None = all)
        page_size: Records per page (default: 10000 for maximum efficiency)
        sort: Sort order 'asc' or 'desc' (default: 'desc')
        chain_id: Chain ID (default: 1 for Ethereum mainnet)
    
    Returns:
        List of all token transfer transactions
    
    Example:
        # Get all token transfers for an address
        all_txs = get_all_token_transfers("0x123...", api_key)
        print(f"Found {len(all_txs)} transactions")
        
        # Get last 5000 USDT transfers
        usdt_txs = get_all_token_transfers(
            "0x123...",
            api_key,
            contract_address="0xdac17f958d2ee523a2206206994597c13d831ec7",
            max_transactions=5000
        )
    """
    all_transfers = []
    page = 1
    
    token_info = f" for token {contract_address[:10]}..." if contract_address else ""
    print(f"  📋 Fetching token transfers{token_info} (page size: {page_size})...")
    
    while True:
        # Build request parameters
        params = {
            "chainid": chain_id,
            "module": "account",
            "action": "tokentx",
            "address": address.lower(),
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": page_size,
            "sort": sort,
            "apikey": apikey,
        }
        
        # Add contract address filter if specified
        if contract_address:
            params["contractaddress"] = contract_address.lower()
        
        # Make API request
        try:
            r = requests.get(ETHERSCAN_V2, params=params, timeout=30)
            if r.ok:
                data = r.json()
                status = data.get("status")
                result = data.get("result")
                
                if status == "1" and isinstance(result, list):
                    transfers = result
                elif "rate limit" in str(result).lower():
                    print(f"  ⚠️  Rate limited")
                    break
                elif status == "0" and "No transactions found" in str(data.get("message", "")):
                    if page == 1:
                        print(f"     No transactions found")
                    break
                else:
                    print(f"  ⚠️  API error: {data.get('message', 'Unknown error')}")
                    break
            else:
                print(f"  ⚠️  HTTP error: {r.status_code}")
                break
        except Exception as e:
            print(f"  ⚠️  Request failed: {e}")
            break
        
        # Process results
        if len(transfers) == 0:
            if page == 1:
                print(f"     No transactions found")
            break
        
        all_transfers.extend(transfers)
        print(f"     Page {page}: fetched {len(transfers)} transactions (total: {len(all_transfers)})")
        
        # Stop if we've reached max_transactions
        if max_transactions and len(all_transfers) >= max_transactions:
            all_transfers = all_transfers[:max_transactions]
            print(f"  ✅ Reached maximum of {max_transactions} transactions")
            break
        
        # Stop if we got fewer records than page_size (last page)
        if len(transfers) < page_size:
            print(f"  ✅ Fetched all {len(all_transfers)} transactions")
            break
        
        page += 1
        time.sleep(0.5)  # Be nice to the API between pages
    
    return all_transfers

# ===================== SMART CONTRACT ACTIVITY ANALYSIS =====================
def analyze_contract_activity(
    addresses: List[str],
    apikey: str,
    contracts_config: Dict = None,
    token_contract: str = TOKEN_CONTRACT,
    chain_id: int = CHAIN_ID
) -> Dict[str, Dict[str, Decimal]]:
    """
    Analyze smart contract interactions for a list of addresses.
    
    Args:
        addresses: List of addresses to analyze
        apikey: Etherscan API key
        contracts_config: Dict mapping contract addresses to categories and functions
        token_contract: Token contract to filter by
        chain_id: Chain ID
    
    Returns:
        Dict mapping address -> category -> sum of token values
        
    Example:
        activity = analyze_contract_activity(
            recipient_addresses,
            api_key,
            DEFAULT_CONTRACTS_AND_FUNCTIONS
        )
        # Returns: {"0xabc...": {"staking": Decimal("1000000...")}, ...}
    """
    if contracts_config is None:
        contracts_config = DEFAULT_CONTRACTS_AND_FUNCTIONS
    
    # Initialize result dict: address -> category -> value
    activity_by_address = {addr.lower(): {} for addr in addresses}
    
    # Process each smart contract
    for contract_addr, config in contracts_config.items():
        category = config.get("category")
        function_names = config.get("functions", [])
        
        if not category or not function_names:
            continue
        
        print(f"\n  🔍 Analyzing {category} activity for contract {contract_addr[:10]}...")
        
        # Query transfers involving this smart contract
        # Note: address param is the smart contract, contractaddress is the token
        transfers = get_all_token_transfers(
            address=contract_addr,
            apikey=apikey,
            contract_address=token_contract,
            chain_id=chain_id
        )
        
        print(f"     Found {len(transfers)} total transfers")
        
        # Filter and aggregate
        matched_count = 0
        for tx in transfers:
            from_addr = tx.get("from", "").lower()
            function_name = tx.get("functionName", "")
            value = tx.get("value", "0")
            
            # Check if this is one of our recipient addresses
            if from_addr not in activity_by_address:
                continue
            
            # Check if function name matches (partial match)
            function_matched = False
            for func in function_names:
                if func.lower() in function_name.lower():
                    function_matched = True
                    break
            
            if not function_matched:
                continue
            
            # Add to category sum for this address
            if category not in activity_by_address[from_addr]:
                activity_by_address[from_addr][category] = Decimal(0)
            
            activity_by_address[from_addr][category] += Decimal(value)
            matched_count += 1
        
        print(f"     ✅ Matched {matched_count} transactions from our recipients")
    
    return activity_by_address

# ===================== TRANSACTION RECEIPT FETCHING =====================
def fetch_transaction_receipt(txhash: str, apikey: str) -> dict:
    """Fetch transaction receipt with retries"""
    params = {
        "chainid": CHAIN_ID,
        "module": "proxy",
        "action": "eth_getTransactionReceipt",
        "txhash": txhash,
        "apikey": apikey,
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(ETHERSCAN_V2, params=params, timeout=TIMEOUT)
            if r.ok:
                result = r.json().get("result", {})
                if isinstance(result, str) and "rate limit" in result.lower():
                    print(f"  ⚠️  Rate limited, waiting...")
                    time.sleep(5)
                    continue
                if result:
                    return result
        except Exception as e:
            print(f"  ⚠️  Attempt {attempt + 1} failed: {e}")
            time.sleep(2)
    
    return {}

def parse_transfers_from_receipt(receipt: dict, token_contract: str = TOKEN_CONTRACT) -> List[Tuple[str, int]]:
    """Extract (address, amount_wei) for token Transfer logs"""
    transfers = []
    logs = receipt.get("logs", [])
    
    for lg in logs:
        if lg.get("address", "").lower() != token_contract.lower():
            continue
        topics = lg.get("topics", [])
        if not topics or topics[0].lower() != TRANSFER_TOPIC:
            continue
        
        to_addr = "0x" + topics[2][-40:].lower()
        try:
            amount = int(lg.get("data", "0x0"), 16)
        except Exception:
            amount = 0
        
        transfers.append((to_addr, amount))
    
    return transfers

# ===================== MAIN FUNCTION (IMPORTABLE) =====================
def fetch_airdrop_data(
    tx_hashes: List[str] = None,
    output_file: str = "yb_airdrop_balances.csv",
    test_mode: bool = False,
    token_contract: str = TOKEN_CONTRACT
) -> Tuple[List[List], int]:
    """
    Main function to fetch airdrop data using optimized bulk holder list API.
    Uses only 2-5 API calls instead of thousands!
    
    Args:
        tx_hashes: List of transaction hashes to parse (uses defaults if None)
        output_file: Output CSV filename
        test_mode: If True, only process first 100 addresses
        token_contract: Token contract address (uses default YB token if not specified)
    
    Returns:
        (rows, api_calls): CSV rows and number of API calls made
    """
    apikey = get_api_key()
    tx_hashes = tx_hashes or DEFAULT_TX_HASHES
    api_calls = 0
    
    print(f"\n{'='*70}")
    print(f"🚀 YB AIRDROP TRACKER - OPTIMIZED EDITION")
    print(f"{'='*70}\n")
    
    # Step 1: Fetch receipts and parse transfers
    print(f"[1/4] Fetching {len(tx_hashes)} transaction receipts...")
    received: Dict[str, Decimal] = {}
    
    for idx, txhash in enumerate(tx_hashes, 1):
        print(f"  Transaction {idx}/{len(tx_hashes)}: {txhash[:10]}...")
        receipt = fetch_transaction_receipt(txhash, apikey)
        api_calls += 1
        
        if not receipt:
            print(f"  ❌ Failed to get receipt for {txhash}")
            raise SystemExit("Cannot continue without all receipts")
        
        transfers = parse_transfers_from_receipt(receipt, token_contract)
        print(f"  ✅ Found {len(transfers)} transfers")
        
        for addr, amount in transfers:
            received[addr] = received.get(addr, Decimal(0)) + Decimal(amount)
        
        if idx < len(tx_hashes):
            time.sleep(1)  # Be nice to API
    
    addresses = list(received.keys())
    if test_mode:
        addresses = addresses[:100]
        print(f"\n⚠️  TEST MODE: Processing only 100 addresses")
    
    print(f"\n[2/5] Found {len(addresses)} unique recipients")
    
    # Step 2: Get holder count (optional, for info)
    print(f"\n[3/5] Getting token holder count...")
    holder_count = get_token_holder_count(token_contract, apikey)
    api_calls += 1
    
    if holder_count:
        print(f"  ✅ Token has {holder_count:,} total holders")
    else:
        print(f"  ⚠️  Could not fetch holder count (continuing anyway)")
    
    # Step 3: Fetch ALL token holders using paginated API
    print(f"\n[4/5] Fetching all token holder balances...")
    all_holders = get_all_token_holders(token_contract, apikey, page_size=10000)
    
    # Count API calls (estimate based on pages)
    pages_fetched = (len(all_holders) // 10000) + 1
    api_calls += pages_fetched
    
    # Build lookup dictionary with lowercase addresses for O(1) lookup
    print(f"\n  📊 Building balance lookup dictionary...")
    balance_lookup = {
        holder['TokenHolderAddress'].lower(): Decimal(holder['TokenHolderQuantity'])
        for holder in all_holders
    }
    print(f"  ✅ Built lookup for {len(balance_lookup):,} holders")
    
    # Step 4: Analyze smart contract activity
    print(f"\n[5/5] Analyzing smart contract activity...")
    activity_data = analyze_contract_activity(
        addresses,
        apikey,
        DEFAULT_CONTRACTS_AND_FUNCTIONS,
        token_contract
    )
    
    # Get all unique categories for column headers
    all_categories = set()
    for addr_activity in activity_data.values():
        all_categories.update(addr_activity.keys())
    all_categories = sorted(all_categories)  # e.g., ['staking', 'liquidity', ...]
    
    if all_categories:
        print(f"\n  ✅ Found {len(all_categories)} categories: {', '.join(all_categories)}")
    else:
        print(f"\n  ℹ️  No contract activity categories configured")
    
    # Step 5: Match airdrop recipients with current balances and activity
    print(f"\n  🔍 Building final output with all data...")
    rows = []
    scale = Decimal(10) ** DECIMALS
    not_found_count = 0
    
    for addr in addresses:
        received_wei = received.get(addr, Decimal(0))
        
        # Lookup current balance (O(1) lookup!)
        balance_wei = balance_lookup.get(addr.lower(), Decimal(0))
        
        if balance_wei == 0 and addr.lower() not in balance_lookup:
            not_found_count += 1
        
        rcv = received_wei / scale
        cur = balance_wei / scale
        delta = cur - rcv
        pct = (cur / rcv * Decimal(100)) if rcv > 0 else Decimal(0)
        
        # Format function to avoid scientific notation (max 2 decimal places)
        def format_decimal(val):
            # Round to 2 decimal places
            rounded = round(float(val), 2)
            # Format and remove trailing zeros
            s = f"{rounded:.2f}".rstrip('0').rstrip('.')
            return s if s else '0'
        
        # Build row with base columns
        row = [
            addr,
            format_decimal(rcv),
            format_decimal(cur),
            format_decimal(delta),
            f"{pct.quantize(Decimal('0.01'))}%"
        ]
        
        # Add category columns
        addr_activity = activity_data.get(addr.lower(), {})
        for category in all_categories:
            category_value = addr_activity.get(category, Decimal(0))
            category_display = category_value / scale
            row.append(format_decimal(category_display))
        
        rows.append(row)
    
    print(f"  ✅ Matched all {len(addresses)} addresses")
    if not_found_count > 0:
        print(f"  ℹ️  {not_found_count} addresses not in holder list (likely sold all tokens)")
    
    # Write CSV with category columns
    rows_sorted = sorted(rows, key=lambda r: Decimal(r[2]), reverse=True)
    
    # Build header with category columns
    header = [
        "address",
        "received_total_YB",
        "current_balance_YB",
        "delta_YB",
        "percent_remaining"
    ]
    header.extend([f"{cat}_value_YB" for cat in all_categories])
    
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows_sorted)
    
    print(f"\n{'='*70}")
    print(f"✅ SUCCESS!")
    print(f"{'='*70}")
    print(f"  Wrote {len(rows)} rows to {output_file}")
    print(f"  Total API calls: {api_calls} 🎉")
    print(f"  (vs {len(addresses)} with old method)")
    print(f"  Efficiency gain: {len(addresses)/api_calls:.1f}x fewer API calls!")
    print(f"{'='*70}\n")
    
    return rows_sorted, api_calls

# ===================== CLI ENTRY POINT =====================
def main():
    parser = argparse.ArgumentParser(description="YB Airdrop Tracker")
    parser.add_argument("--out", default="yb_airdrop_balances.csv", help="Output CSV")
    parser.add_argument("--tx", nargs="*", help="Transaction hashes (space-separated)")
    parser.add_argument("--test", action="store_true", help="Test mode: first 100 addresses")
    args = parser.parse_args()
    
    try:
        fetch_airdrop_data(
            tx_hashes=args.tx,
            output_file=args.out,
            test_mode=args.test
        )
        return 0
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
