#!/usr/bin/env python3
"""Minimalist Flask app for YB Airdrop Tracker"""
from flask import Flask, request, render_template, send_file, session, jsonify, redirect
import json
import os
import sys
import tempfile
import threading
from logic import fetch_airdrop_data, DEFAULT_TX_HASHES, DEFAULT_CONTRACTS_AND_FUNCTIONS

# Set API key (can be overridden by environment variable)
if 'ETHERSCAN_API_KEY' not in os.environ:
    os.environ['ETHERSCAN_API_KEY'] = 'AIUURKNADGEDNUU1VT9C5YN4B72CZCQGVS'

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())

LOGS_DIR = '/tmp/airdrop_logs'
os.makedirs(LOGS_DIR, exist_ok=True)

@app.route('/')
def index():
    session.clear()
    example_txs = '\n'.join(DEFAULT_TX_HASHES)
    example_contracts = json.dumps(DEFAULT_CONTRACTS_AND_FUNCTIONS, indent=2)
    return render_template('index.html', mode=None, result=None, example_txs=example_txs, example_contracts=example_contracts)

@app.route('/run', methods=['POST'])
def run():
    token = request.form['token'].strip()
    decimals = int(request.form['decimals'])
    txhashes = [line.strip() for line in request.form['txhashes'].strip().split('\n') if line.strip()]
    contracts_json = request.form.get('contracts', '').strip()
    
    if contracts_json:
        try:
            contracts = json.loads(contracts_json)
        except:
            return "Invalid JSON for contracts", 400
    else:
        contracts = DEFAULT_CONTRACTS_AND_FUNCTIONS
    
    # Create unique job ID and log file
    job_id = os.urandom(8).hex()
    session['job_id'] = job_id
    log_file = os.path.join(LOGS_DIR, f'{job_id}.log')
    result_file = os.path.join(LOGS_DIR, f'{job_id}.result')
    
    def process():
        # Redirect stdout to log file
        with open(log_file, 'w') as log:
            old_stdout = sys.stdout
            sys.stdout = log
            
            try:
                import logic
                old_token = logic.TOKEN_CONTRACT
                old_decimals = logic.DECIMALS
                old_contracts = logic.DEFAULT_CONTRACTS_AND_FUNCTIONS
                
                logic.TOKEN_CONTRACT = token
                logic.DECIMALS = decimals
                logic.DEFAULT_CONTRACTS_AND_FUNCTIONS = contracts
                
                tmpfile = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='')
                tmpfile.close()
                
                rows, api_calls = fetch_airdrop_data(tx_hashes=txhashes, output_file=tmpfile.name, token_contract=token)
                
                logic.TOKEN_CONTRACT = old_token
                logic.DECIMALS = old_decimals
                logic.DEFAULT_CONTRACTS_AND_FUNCTIONS = old_contracts
                
                # Read CSV
                with open(tmpfile.name, 'r') as f:
                    import csv
                    reader = csv.reader(f)
                    headers = next(reader)
                    preview = [row for _, row in zip(range(100), reader)]
                
                # Save result
                result = {
                    'csv_file': tmpfile.name,
                    'count': len(rows),
                    'api_calls': api_calls,
                    'headers': headers,
                    'preview': preview
                }
                with open(result_file, 'w') as rf:
                    json.dump(result, rf)
                    
            except Exception as e:
                log.write(f"\nERROR: {str(e)}\n")
            finally:
                sys.stdout = old_stdout
                log.write("\n[DONE]\n")
    
    threading.Thread(target=process, daemon=True).start()
    return render_template('index.html', mode='processing', result=None, example_txs='', example_contracts='')

@app.route('/poll')
def poll():
    job_id = session.get('job_id')
    if not job_id:
        return jsonify({'lines': ['ERROR: No job found'], 'done': True})
    
    log_file = os.path.join(LOGS_DIR, f'{job_id}.log')
    
    if not os.path.exists(log_file):
        return jsonify({'lines': ['Initializing...'], 'done': False})
    
    with open(log_file, 'r') as f:
        content = f.read()
        lines = content.split('\n')
        done = '[DONE]' in content
    
    return jsonify({'lines': lines, 'done': done})

@app.route('/result')
def result():
    job_id = session.get('job_id')
    if not job_id:
        return redirect('/')
    
    result_file = os.path.join(LOGS_DIR, f'{job_id}.result')
    if not os.path.exists(result_file):
        return "Processing not complete", 400
    
    with open(result_file, 'r') as f:
        result_data = json.load(f)
    
    session['csv_file'] = result_data['csv_file']
    
    result = {
        'count': result_data['count'],
        'api_calls': result_data['api_calls'],
        'headers': result_data['headers'],
        'preview': result_data['preview']
    }
    
    return render_template('index.html', mode=None, result=result, example_txs='', example_contracts='')

@app.route('/download', methods=['POST'])
def download():
    csv_file = session.get('csv_file')
    if not csv_file or not os.path.exists(csv_file):
        return "No file to download", 404
    return send_file(csv_file, as_attachment=True, download_name='airdrop_data.csv')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, port=port, host='0.0.0.0')
