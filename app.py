#!/usr/bin/env python3
"""Minimalist Flask app for YB Airdrop Tracker"""
from flask import Flask, request, render_template, send_file, session, redirect
from dotenv import load_dotenv
import json
import os
import tempfile
from logic import fetch_airdrop_data, DEFAULT_TX_HASHES, DEFAULT_CONTRACTS_AND_FUNCTIONS

# Load environment variables from .env file
load_dotenv()

# Verify API key is set
if not os.environ.get('ETHERSCAN_API_KEY'):
    raise ValueError("ETHERSCAN_API_KEY not found in environment variables. Please set it in .env file.")

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())

@app.route('/')
def index():
    session.clear()
    example_txs = '\n'.join(DEFAULT_TX_HASHES)
    example_contracts = json.dumps(DEFAULT_CONTRACTS_AND_FUNCTIONS, indent=2)
    return render_template('index.html', result=None, example_txs=example_txs, example_contracts=example_contracts)

@app.route('/run', methods=['POST'])
def run():
    token = request.form['token'].strip()
    decimals = int(request.form['decimals'])
    txhashes = [line.strip() for line in request.form['txhashes'].strip().split('\n') if line.strip()]
    contracts_json = request.form.get('contracts', '').strip()
    
    # Parse contracts config
    if contracts_json:
        try:
            contracts = json.loads(contracts_json)
        except:
            return "Invalid JSON for contracts", 400
    else:
        contracts = DEFAULT_CONTRACTS_AND_FUNCTIONS
    
    # Configure logic module
    import logic
    old_token = logic.TOKEN_CONTRACT
    old_decimals = logic.DECIMALS
    old_contracts = logic.DEFAULT_CONTRACTS_AND_FUNCTIONS
    
    logic.TOKEN_CONTRACT = token
    logic.DECIMALS = decimals
    logic.DEFAULT_CONTRACTS_AND_FUNCTIONS = contracts
    
    # Create temp CSV file
    tmpfile = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='')
    tmpfile.close()
    
    try:
        # Process synchronously (blocking) - suppress stdout
        import sys
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()  # Suppress all print statements
        
        rows, api_calls = fetch_airdrop_data(tx_hashes=txhashes, output_file=tmpfile.name, token_contract=token)
        
        sys.stdout = old_stdout  # Restore stdout
    finally:
        # Restore config
        logic.TOKEN_CONTRACT = old_token
        logic.DECIMALS = old_decimals
        logic.DEFAULT_CONTRACTS_AND_FUNCTIONS = old_contracts
    
    # Store CSV file path in session
    session['csv_file'] = tmpfile.name
    
    # Read CSV to get headers and preview
    with open(tmpfile.name, 'r') as f:
        import csv
        reader = csv.reader(f)
        headers = next(reader)
        preview = [row for _, row in zip(range(100), reader)]
    
    result = {
        'count': len(rows),
        'api_calls': api_calls,
        'headers': headers,
        'preview': preview
    }
    
    return render_template('index.html', result=result, example_txs='', example_contracts='')

@app.route('/download', methods=['POST'])
def download():
    csv_file = session.get('csv_file')
    if not csv_file or not os.path.exists(csv_file):
        return "No file to download", 404
    return send_file(csv_file, as_attachment=True, download_name='airdrop_data.csv')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, port=port, host='0.0.0.0')
