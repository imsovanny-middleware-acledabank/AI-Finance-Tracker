#!/bin/bash
# Quick Start Script for AI Finance Bot

set -e

echo "🚀 AI Finance Bot - Quick Start"
echo "================================"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo "🔌 Activating virtual environment..."
source venv/bin/activate

echo "📚 Installing dependencies..."
pip install -q --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -q -r requirements.txt
else
    echo "⚠️  requirements.txt not found!"
    echo "Installing core dependencies..."
    pip install -q \
        Django==6.0.4 \
        djangorestframework==3.17.1 \
        python-telegram-bot==20.7 \
        google-generativeai==0.3.0 \
        python-dotenv==1.0.0 \
        SpeechRecognition==3.10.0 \
        pydub==0.25.1
fi

echo "🗄️  Setting up database..."
python manage.py makemigrations --noinput 2>/dev/null || true
python manage.py migrate --noinput

echo "📊 Populating test data..."
python populate_test_data.py 2>/dev/null || echo "⚠️  Test data population skipped"

echo ""
echo "✅ Setup complete!"
echo ""
echo "📱 Next steps:"
echo "1. Create .env file with:"
echo "   TELEGRAM_BOT_TOKEN=your_token_here"
echo "   GEMINI_API_KEY=your_api_key_here"
echo ""
echo "2. Start web server:"
echo "   python manage.py runserver 8000"
echo ""
echo "3. In another terminal, start the bot:"
echo "   python manage.py run_bot"
echo ""
echo "4. Open dashboard: http://localhost:8000/"
echo ""
echo "📖 For more info, see README.md"
