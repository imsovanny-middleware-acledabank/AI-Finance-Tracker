# navigation.py
# Navigation stack helpers for Telegram bot

def push_state(context, state, data=None):
    stack = context.user_data.get("nav_stack", [])
    stack.append({"state": state, "data": data or {}})
    context.user_data["nav_stack"] = stack

def pop_state(context):
    stack = context.user_data.get("nav_stack", [])
    if stack:
        stack.pop()
        context.user_data["nav_stack"] = stack
    return stack[-1] if stack else None

def current_state(context):
    stack = context.user_data.get("nav_stack", [])
    return stack[-1] if stack else None

async def handle_navigation(update, context, send_main_menu, send_quick_entry_help):
    nav = current_state(context)
    if not nav:
        # Initialize to main menu
        push_state(context, "main")
        nav = current_state(context)
    state = nav["state"]
    if state == "main":
        await send_main_menu(update.message if hasattr(update, "message") else update.callback_query.message, "User", update.effective_user.id, context.user_data.get("lang", "en"))
    elif state == "add_expense":
        await send_quick_entry_help(update.message if hasattr(update, "message") else update.callback_query.message, "expense", context.user_data.get("lang", "en"))
    elif state == "add_income":
        await send_quick_entry_help(update.message if hasattr(update, "message") else update.callback_query.message, "income", context.user_data.get("lang", "en"))
    # ... add more states as needed

async def on_next(update, context, next_state, data=None, handle_navigation_func=None):
    push_state(context, next_state, data)
    if handle_navigation_func:
        await handle_navigation_func(update, context)

async def on_back(update, context, handle_navigation_func=None):
    pop_state(context)
    if handle_navigation_func:
        await handle_navigation_func(update, context)
