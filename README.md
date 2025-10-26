# 🚀 Airdrop Tracker - Web App

Minimalist Flask web interface for tracking token airdrops and analyzing wallet activity on Ethereum.

## Features

- ✅ **Token Analysis** - Input contract address, decimals, transaction hashes
- ✅ **Smart Contract Activity** - Configure staking, liquidity analysis
- ✅ **Live Terminal Output** - Watch processing in real-time
- ✅ **Data Preview** - See first 100 rows instantly
- ✅ **CSV Export** - Download full results

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python3 app.py
```

Visit http://127.0.0.1:5001

## Deploy to Railway 🚂

### Method 1: Deploy from GitHub (Recommended)

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-repo-url>
   git push -u origin main
   ```

2. **Deploy on Railway**
   - Go to [railway.app](https://railway.app)
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository
   - Railway auto-detects Python and deploys! 🎉

3. **Set Environment Variable** (Optional)
   - In Railway dashboard → Variables
   - Add: `ETHERSCAN_API_KEY=your_key_here`

### Method 2: Deploy from CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize and deploy
railway init
railway up
```

### Method 3: Deploy with Railway Button

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/yourusername/yourrepo)

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ETHERSCAN_API_KEY` | Your Etherscan API key | Hardcoded fallback |
| `PORT` | Server port | 5001 |
| `SECRET_KEY` | Flask session secret | Auto-generated |

## Project Structure

```
legiondeploy/
├── app.py                 # Flask application
├── logic.py              # Core airdrop analysis logic
├── templates/
│   └── index.html        # Web interface
├── requirements.txt      # Python dependencies
├── Procfile             # Railway/Heroku deployment config
├── runtime.txt          # Python version
└── README.md            # This file
```

## How It Works

1. **Submit Form** - Enter token details and transaction hashes
2. **Background Processing** - Server processes data using `logic.py`
3. **Live Updates** - Terminal output streams to frontend every 300ms
4. **View Results** - Preview top 100 rows in a table
5. **Download CSV** - Export complete dataset

## Technologies

- **Backend**: Flask, Python 3.9
- **Frontend**: Pure HTML/CSS/JavaScript (no frameworks)
- **Server**: Gunicorn (production)
- **Deployment**: Railway
- **API**: Etherscan API v2

## Free Tier Limits

Railway free tier includes:
- ✅ $5 monthly credit
- ✅ Unlimited projects
- ✅ 500MB RAM per service
- ✅ Background threads supported

Perfect for this app! 🎯

## Support

Questions? Issues? Create a GitHub issue or reach out!

