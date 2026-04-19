# 🎯 Using Real Telegram Data - Quick Guide

## How to Link Your Telegram Bot to the Dashboard

### Step 1: Find Your Telegram User ID

**Option A: Quick Method**
1. Send `/start` command to your bot on Telegram
2. The bot will reply with your Telegram ID
3. Click the dashboard link in the reply

**Option B: Run the ID Finder**
```bash
cd ai_finance_bot
source venv/bin/activate
python find_telegram_id.py
```
Then send any message to your bot and your ID will appear in the terminal.

### Step 2: Access Your Personal Dashboard

Once you have your Telegram ID, visit:
```
http://localhost:8000/?telegram_id=YOUR_ID
```

Replace `YOUR_ID` with your actual Telegram user ID.

**Example:**
```
http://localhost:8000/?telegram_id=987654321
```

### Step 3: Start Recording Transactions

Send messages to your bot on Telegram:

**Text Messages:**
- "spent $50 on food"
- "earned $1000 salary"
- "spent $25 on transport yesterday"

**Voice Messages:**
- Record yourself saying: "spent $30 on coffee"
- Send the voice message

**Watch the Dashboard:**
- Your dashboard automatically updates
- Charts refresh every 30 seconds
- All data is in real-time!

---

## Dashboard Features with Real Data

### Input Your ID (Top of Page)
- Enter your Telegram ID in the input field
- Press Enter or click "Load Data"
- Dashboard instantly shows YOUR data

### Automatic Sync
When you send a transaction on Telegram:
1. Bot receives message
2. AI parses the transaction
3. Data saves to database
4. Dashboard updates automatically (max 30 seconds)

### Persistent Storage
- Your dashboard ID is saved in browser
- Reload the page and it remembers your ID
- Switch IDs anytime by entering a different one

---

## API Access with Your ID

All API endpoints work with your real data:

```bash
# Replace YOUR_ID with your actual Telegram ID

# Get your statistics
curl http://localhost:8000/api/transactions/statistics/?telegram_id=YOUR_ID

# Get your spending by category
curl http://localhost:8000/api/transactions/by_category/?telegram_id=YOUR_ID

# Get monthly trends
curl http://localhost:8000/api/transactions/monthly_trend/?telegram_id=YOUR_ID

# Get recent transactions
curl http://localhost:8000/api/transactions/recent/?telegram_id=YOUR_ID
```

---

## Complete Workflow

```
1. Start Bot
   ↓
   python manage.py run_bot

2. Start Dashboard Server
   ↓
   python manage.py runserver 8000

3. Send /start to Bot
   ↓
   Bot replies with your Telegram ID and dashboard link

4. Click Dashboard Link or Enter ID
   ↓
   http://localhost:8000/?telegram_id=YOUR_ID

5. Send Transactions on Telegram
   ↓
   "spent $50 on food"
   Voice message: "earned $1000"

6. Watch Dashboard Update
   ↓
   Charts and statistics sync automatically!

7. View API Data
   ↓
   curl http://localhost:8000/api/transactions/statistics/?telegram_id=YOUR_ID
```

---

## Troubleshooting

### Dashboard shows "No data"
- Make sure you entered the correct Telegram ID
- Check that transactions exist: send a test message to the bot
- Wait a few seconds for the dashboard to refresh

### Don't know your Telegram ID
- Run: `python find_telegram_id.py`
- Send any message to your bot
- Your ID will display immediately

### Multiple Users
- Each person gets their own dashboard ID
- Share the dashboard URL with your ID: `http://localhost:8000/?telegram_id=YOUR_ID`
- Each ID shows only that person's data

### Data not syncing
- Check Django server is running: `http://localhost:8000/` should load
- Check bot is running in another terminal
- Check for errors in bot terminal output

---

## Tips & Tricks

✅ **Save Your ID**
- The dashboard remembers your ID in browser storage
- You can access your data from any browser by adding the URL parameter

✅ **Test with Sample Data**
- Default test user: `?telegram_id=123`
- Contains 13 sample transactions for testing

✅ **Share Your Dashboard**
- Send the dashboard link to friends
- Format: `http://localhost:8000/?telegram_id=YOUR_ID`
- Each person can access their own financial data

✅ **Automate API Access**
- Use the REST API endpoints in your own apps
- Build custom reports using the API data
- Integrate with other services

---

**Your AI Finance Bot is now tracking your real expenses!** 💰📊
