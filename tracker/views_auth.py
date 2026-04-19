# tracker/views_auth.py
"""
Authentication views for Telegram login.
"""

import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from tracker.auth import TelegramAuthenticator
from tracker.models import Transaction


@require_http_methods(["GET"])
def login_page(request):
    """Render Telegram login page."""
    return render(request, 'login.html')


@require_http_methods(["POST"])
@csrf_exempt
def authenticate_telegram(request):
    """
    Authenticate user with Telegram data.
    Expects POST data with Telegram auth object.
    """
    try:
        data = json.loads(request.body)
        
        # Verify Telegram data
        user_data = TelegramAuthenticator.verify_telegram_data(data)
        
        if not user_data:
            return JsonResponse(
                {'error': 'Invalid Telegram authentication data'},
                status=400
            )
        
        # Create session
        session_token = TelegramAuthenticator.create_session(user_data)
        
        response = JsonResponse({
            'success': True,
            'user_id': user_data['id'],
            'first_name': user_data['first_name'],
            'username': user_data['username'],
            'redirect_url': f'/dashboard/?token={session_token}'
        })
        
        # Set secure session cookie
        response.set_cookie(
            'telegram_session',
            session_token,
            max_age=7 * 24 * 3600,  # 7 days
            secure=False,  # Set to True in production with HTTPS
            httponly=True,  # Prevent JavaScript access
            samesite='Lax'
        )
        
        return response
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def logout(request):
    """Logout user by invalidating session."""
    session_token = request.COOKIES.get('telegram_session')
    
    if session_token:
        TelegramAuthenticator.logout_session(session_token)
    
    response = JsonResponse({'success': True})
    response.delete_cookie('telegram_session')
    
    return response


@require_http_methods(["GET"])
def user_info(request):
    """Get current user info if authenticated."""
    session_token = request.COOKIES.get('telegram_session')
    
    if not session_token:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    user_data = TelegramAuthenticator.get_session_user(session_token)
    
    if not user_data:
        return JsonResponse({'error': 'Session expired'}, status=401)
    
    # Get user statistics
    user_id = user_data['id']
    transactions = Transaction.objects.filter(telegram_id=user_id)
    income = sum(float(t.amount) for t in transactions.filter(transaction_type='income'))
    expense = sum(float(t.amount) for t in transactions.filter(transaction_type='expense'))
    
    return JsonResponse({
        'id': user_data['id'],
        'first_name': user_data['first_name'],
        'last_name': user_data['last_name'],
        'username': user_data['username'],
        'photo_url': user_data['photo_url'],
        'transaction_count': transactions.count(),
        'total_income': income,
        'total_expenses': expense,
    })
