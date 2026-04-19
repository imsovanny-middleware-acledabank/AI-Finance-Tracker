# 💰 AI Finance Bot - Complete Project

A Telegram-based financial tracking application with AI-powered transaction parsing, REST API backend, and interactive web dashboard.

## 🚀 Features

### Core Features
- ✅ **Telegram Bot** with text/voice message support
- ✅ **AI-Powered Parsing** using Google Gemini API
- ✅ **Transaction Tracking** with categories, amounts, dates
- ✅ **REST API** with statistics and analytics endpoints
- ✅ **Web Dashboard** with real-time charts and visualizations
- ✅ **Multi-Category Support** with emoji icons
- ✅ **Budget Management** with frequency-based tracking
- ✅ **Monthly Trends** and spending analysis

### Dashboard Features
- 📊 Statistics cards (Income, Expenses, Net Balance)
- 📉 Doughnut chart for category breakdown
- 📈 Line chart for monthly income/expense trends
- 📝 Recent transactions list
- 🔄 Auto-refresh every 30 seconds

## 🛠️ Setup Instructions

### 1. Prerequisites
```bash
python 3.8+
Django 6.0.4
PostgreSQL or SQLite (included)
```

### 2. Install Dependencies
```bash
cd ai_finance_bot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment
Create `.env` file in project root:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
GEMINI_API_KEY=your_google_gemini_api_key_here
DEBUG=True
```

### 4. Initialize Database
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. (Optional) Populate Test Data
```bash
python populate_test_data.py
```

## 📱 Running the Application

### Start Web Server & Dashboard
```bash
python manage.py runserver 8000
# Access dashboard at http://localhost:8000/
```

### Start Telegram Bot
```bash
python manage.py run_bot
# Or in a separate terminal:
# python tracker/management/commands/run_bot.py
```

## 📡 Telegram Bot Usage

### Available Commands
- `/start` - Show welcome message
- `/total` - Display income, expenses, and net balance
- `/expenses` - Show total expenses
- `/income` - Show total income
- `/list` - List recent transactions

### Recording Transactions

**Text Format:**
```
spent $50 on food
earned $1000 salary
```

**Voice Messages:**
- Just send a voice message saying: "spent $25 on taxi"
- Bot automatically transcribes and processes

**Supported Categories:**
- 🍔 Food
- 🚗 Transport
- 🎬 Entertainment
- 🛍️ Shopping
- 💡 Bills
- 💊 Health
- 💰 Salary
- (Plus any custom category)

## 🔌 REST API Endpoints

Base URL: `http://localhost:8000/api/`

### Get Statistics
```bash
GET /api/transactions/statistics/?telegram_id=123
```
Response:
```json
{
  "total_income": "5000.00",
  "total_expenses": "740.50",
  "net": "4259.50",
  "transaction_count": 13,
  "monthly_average": "740.50"
}
```

### Get Spending by Category
```bash
GET /api/transactions/by_category/?telegram_id=123
```
Response:
```json
[
  {
    "category": "🍔 Food",
    "total_amount": 115.5,
    "count": 4
  },
  ...
]
```

### Get Monthly Trends
```bash
GET /api/transactions/monthly_trend/?telegram_id=123
```
Response:
```json
[
  {
    "month": "2024-04",
    "income": 5000.0,
    "expenses": 740.5
  }
]
```

### Get Recent Transactions
```bash
GET /api/transactions/recent/?telegram_id=123&limit=10
```
Response:
```json
[
  {
    "id": 2,
    "amount": 25.5,
    "type": "expense",
    "category": "🍔 Food",
    "description": "Lunch",
    "date": "2026-04-18",
    "created_at": "2026-04-19T03:58:58.661903+00:00"
  },
  ...
]
```

## 📊 Dashboard Access

Open your browser and navigate to:
```
http://localhost:8000/
```

The dashboard automatically displays:
- Real-time statistics for all users
- Spending breakdown by category with pie chart
- Monthly income/expense trends with line chart
- Recent transactions list

**Note:** The dashboard uses `telegram_id=123` by default for demo. To view your own data, modify the `TELEGRAM_ID` variable in the JavaScript or update it based on your user ID.

## 🗄️ Database Schema

### Transaction Model
- `id` - Primary key
- `telegram_id` - Telegram user ID
- `amount` - Transaction amount
- `category` - Foreign key to Category
- `category_name` - Fallback category name
- `transaction_type` - 'income' or 'expense'
- `note` - Transaction description
- `transaction_date` - Date of transaction
- `is_recurring` - Boolean flag
- `tags` - Comma-separated tags
- `created_at` - Creation timestamp

### Category Model
- `id` - Primary key
- `name` - Category name (unique)
- `icon` - Emoji icon
- `description` - Optional description
- `created_at` - Creation timestamp

### Budget Model
- `id` - Primary key
- `telegram_id` - Telegram user ID
- `category` - Foreign key to Category
- `limit_amount` - Budget limit
- `frequency` - 'daily', 'weekly', 'monthly', 'yearly'
- `alert_threshold` - Alert percentage
- `is_active` - Boolean flag
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp

## 🔐 Security Notes

1. **Environment Variables**: Never commit `.env` file with real credentials
2. **API Key**: Keep GEMINI_API_KEY and TELEGRAM_BOT_TOKEN private
3. **Database**: Use strong passwords for production databases
4. **HTTPS**: Use HTTPS in production (not just HTTP)

## 📚 Technology Stack

- **Backend**: Django 6.0.4, Django REST Framework 3.17.1
- **Database**: SQLite (development), PostgreSQL (production-ready)
- **Bot Framework**: python-telegram-bot 20.7
- **AI/ML**: Google Generative AI (Gemini 2.5-flash)
- **Frontend**: Vanilla JavaScript + Chart.js
- **Audio**: SpeechRecognition 3.10.0 + pydub 0.25.1

## 🔄 Integration Flow

```
Telegram User
    ↓
  Bot receives message (text/voice/photo)
    ↓
  AI Analysis (Gemini API) parses transaction
    ↓
  Save to Database
    ↓
  Dashboard & API endpoints fetch data
    ↓
  Web Dashboard displays real-time charts
```

## 📝 File Structure

```
ai_finance_bot/
├── db.sqlite3                           # Database
├── manage.py                            # Django management
├── populate_test_data.py                # Test data script
├── requirements.txt                     # Dependencies
├── .env                                 # Environment config (not in repo)
├── core/                                # Project settings
│   ├── settings.py                      # Django settings
│   ├── urls.py                          # Main URLs
│   ├── asgi.py
│   └── wsgi.py
└── tracker/                             # Main app
    ├── models.py                        # Database models
    ├── services.py                      # AI/Gemini integration
    ├── views_api.py                     # REST API endpoints
    ├── serializers.py                   # DRF serializers
    ├── urls.py                          # API URLs
    ├── admin.py                         # Django admin
    ├── management/
    │   └── commands/
    │       └── run_bot.py               # Telegram bot entry point
    ├── migrations/                      # Database migrations
    └── templates/
        └── dashboard.html               # Web dashboard
```

## 🐛 Troubleshooting

### Bot doesn't respond
- Check TELEGRAM_BOT_TOKEN in `.env`
- Verify internet connection
- Check bot logs for errors

### "Gemini API not found" error
- Ensure GEMINI_API_KEY is valid
- Check available models using: `python manage.py shell`

### Dashboard shows no data
- Verify transactions exist: `python manage.py shell` → `Transaction.objects.all()`
- Check browser console for JavaScript errors
- Ensure `telegram_id` matches your user ID

### Voice transcription fails
- Install ffmpeg: `brew install ffmpeg` (macOS) or `apt install ffmpeg` (Linux)
- Check microphone permissions on your device

## 📈 Future Enhancements

- [ ] Budget alerts and notifications
- [ ] Multi-language support (Khmer, English, Chinese)
- [ ] Expense forecasting using ML
- [ ] Photo receipt scanning with OCR
- [ ] Monthly budget reports
- [ ] Custom category management
- [ ] User authentication and multi-user support
- [ ] Mobile app (React Native)

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Django logs: `tail -f /tmp/django_server.log`
3. Check bot logs: Console output where `run_bot` was started

## 📄 License

This project is open source and available under the MIT License.

---

**Happy tracking! 💰📊**
