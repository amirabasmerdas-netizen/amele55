import threading
import telebot
from telebot import types
import database as db
import config
import datetime

_bot = None
BOT_USERNAME = None
OWNER_TG_ID = 8296865861

def get_bot():
    return _bot

def start_token_bot():
    global _bot, BOT_USERNAME

    if not config.BOT_TOKEN:
        print("⚠️ BOT_TOKEN تنظیم نشده — ربات الماس غیرفعال است")
        return

    _bot = telebot.TeleBot(config.BOT_TOKEN, parse_mode="HTML", threaded=False)

    try:
        me = _bot.get_me()
        BOT_USERNAME = me.username
        print(f"🤖 ربات الماس: @{BOT_USERNAME}")
    except Exception as e:
        print(f"❌ خطا در اتصال ربات الماس: {e}")
        _bot = None
        return

    import time as _time
    for attempt in range(3):
        try:
            _bot.delete_webhook(drop_pending_updates=True)
            _time.sleep(3)
            break
        except:
            _time.sleep(3)

    def send_forced_channels_menu(message, missing_channels):
        markup = types.InlineKeyboardMarkup(row_width=1)
        for ch in missing_channels:
            ch_clean = ch.lstrip("@")
            markup.add(types.InlineKeyboardButton(f"📢 عضویت در {ch}", url=f"https://t.me/{ch_clean}"))
        markup.add(types.InlineKeyboardButton("✅ بررسی عضویت من", callback_data="check_join"))
        
        channels_list = "\n".join([f"🔸 {ch}" for ch in missing_channels])
        _bot.reply_to(
            message,
            "⛔️ <b>ورود به ربات منوط به عضویت در کانال‌های زیر است:</b>\n\n"
            f"{channels_list}\n\n"
            "👇 روی هر کانال کلیک کنید و Join بزنید، سپس دکمه «بررسی عضویت من» را بزنید:",
            reply_markup=markup
        )

    @_bot.message_handler(commands=["start"])
    def cmd_start(message):
        try:
            tg_id = message.from_user.id
            parts = message.text.strip().split()
            ref_code = parts[1] if len(parts) > 1 else None
            
            if ref_code and ref_code.startswith("ref_"):
                try:
                    referrer_id = int(ref_code[4:])
                    if db.process_referral(referrer_id, tg_id):
                        referrer_tg = db.get_telegram_id_by_owner(referrer_id)
                        if referrer_tg:
                            try:
                                _bot.send_message(referrer_tg, 
                                    f"🎉 یک نفر با لینک شما عضو شد!\n"
                                    f"<b>+{config.REFERRAL_TOKENS} الماس</b> دریافت کردید 💎")
                            except: pass
                except: pass

            is_member, missing = db.check_user_membership(_bot, tg_id)
            if not is_member:
                send_forced_channels_menu(message, missing)
                return

            site_url = getattr(config, "SITE_URL", "")
            account = db.get_account_by_tg_id(tg_id)

            if not account:
                markup = types.InlineKeyboardMarkup()
                if site_url:
                    markup.add(types.InlineKeyboardButton("🌐 ورود به پنل وب", url=site_url))
                _bot.reply_to(message, 
                    "👋 <b>سلام!</b>\n\n"
                    "برای استفاده از ربات:\n"
                    "1️⃣ در پنل وب ثبت‌نام کنید\n"
                    "2️⃣ حساب تلگرام را وصل کنید\n"
                    "3️⃣ دوباره /start بزنید", 
                    reply_markup=markup if site_url else None)
                return

            stats = db.get_token_stats(account["id"])
            
            if message.chat.type == 'private':
                if tg_id == OWNER_TG_ID:
                    markup = _owner_keyboard()
                else:
                    markup = _user_keyboard()
            else:
                markup = None

            token_price = getattr(config, 'TOKEN_PRICE_TOMAN', 200)
            
            _bot.reply_to(
                message,
                f"👋 سلام <b>{account['username']}</b>!\n\n"
                f"💎 موجودی: <b>{stats['balance']}</b>\n"
                f"📊 کل دریافتی: <b>{stats['total_earned']}</b>\n\n"
                f"⚡ هر <b>۲ الماس</b> = <b>۲ ساعت</b> سلف‌بات\n"
                f"💰 قیمت هر الماس: <b>{token_price} تومان</b>",
                reply_markup=markup
            )

            if message.chat.type == 'private':
                sponsors = getattr(config, 'SPONSORS', [])
                if sponsors:
                    sponsors_text = "🤝 <b>اسپانسرهای رسمی پروژه:</b>\n"
                    for sp in sponsors:
                        sponsors_text += f"🔸 @{sp['username']}\n"
                    sponsors_text += f"\n👑 <b>مالک و پشتیبانی:</b> @{config.OWNER_USERNAME}"
                    _bot.send_message(message.chat.id, sponsors_text)
        except Exception as e:
            print(f"❌ خطا در cmd_start: {e}")

    @_bot.callback_query_handler(func=lambda call: call.data == "check_join")
    def callback_check_join(call):
        try:
            is_member, missing = db.check_user_membership(_bot, call.from_user.id)
            if is_member:
                _bot.answer_callback_query(call.id, "عضویت تأیید شد! ✅")
                try: _bot.delete_message(call.message.chat.id, call.message.message_id)
                except: pass
                cmd_start(call.message)
            else:
                _bot.answer_callback_query(call.id, f"هنوز در {len(missing)} کانال عضو نشده‌اید! ❌", show_alert=True)
        except Exception as e:
            print(f"❌ خطا در callback_check_join: {e}")

    def require_membership(message):
        is_member, missing = db.check_user_membership(_bot, message.from_user.id)
        if not is_member:
            send_forced_channels_menu(message, missing)
            return False
        return True

    @_bot.message_handler(func=lambda m: m.text == "💎 موجودی", chat_types=['private'])
    def cmd_balance(message):
        try:
            if not require_membership(message): return
            account = db.get_account_by_tg_id(message.from_user.id)
            if not account: return _bot.reply_to(message, "⚠️ ابتدا در پنل وب ثبت‌نام کنید.")
            stats = db.get_token_stats(account["id"])
            ref_count = db.get_referral_count(account["id"])
            token_price = getattr(config, 'TOKEN_PRICE_TOMAN', 200)
            _bot.reply_to(message,
                f"💎 <b>موجودی الماس</b>\n\n"
                f"💰 فعلی: <b>{stats['balance']}</b>\n"
                f"📊 کل: <b>{stats['total_earned']}</b>\n"
                f"👥 رفرال: <b>{ref_count}</b> نفر\n"
                f"💵 قیمت هر الماس: <b>{token_price} تومان</b>",
                reply_markup=_user_keyboard())
        except Exception as e:
            print(f"❌ خطا در cmd_balance: {e}")

    @_bot.message_handler(func=lambda m: m.text == "🎁 هدیه روزانه", chat_types=['private'])
    def cmd_daily(message):
        try:
            if not require_membership(message): return
            account = db.get_account_by_tg_id(message.from_user.id)
            if not account: return _bot.reply_to(message, "⚠️ ابتدا در پنل وب ثبت‌نام کنید.", reply_markup=_user_keyboard())
            success, msg = db.claim_daily_token(account["id"])
            if success:
                stats = db.get_token_stats(account["id"])
                _bot.reply_to(message, f"{msg}\n\n💎 موجودی جدید: <b>{stats['balance']}</b>", reply_markup=_user_keyboard())
            else:
                _bot.reply_to(message, msg, reply_markup=_user_keyboard())
        except Exception as e:
            print(f"❌ خطا در cmd_daily: {e}")

    @_bot.message_handler(func=lambda m: m.text == "🔗 رفرال", chat_types=['private'])
    def cmd_referral(message):
        try:
            if not require_membership(message): return
            account = db.get_account_by_tg_id(message.from_user.id)
            if not account: return _bot.reply_to(message, "⚠️ ابتدا در پنل وب ثبت‌نام کنید.", reply_markup=_user_keyboard())
            link = f"https://t.me/{BOT_USERNAME}?start=ref_{account['id']}"
            ref_count = db.get_referral_count(account["id"])
            token_price = getattr(config, 'TOKEN_PRICE_TOMAN', 200)
            referral_value = config.REFERRAL_TOKENS * token_price
            _bot.reply_to(message,
                f"🔗 <b>لینک رفرال شما:</b>\n<code>{link}</code>\n\n"
                f"👥 تعداد: <b>{ref_count}</b>\n"
                f"🎁 پاداش: <b>{config.REFERRAL_TOKENS} الماس</b> (معادل {referral_value} تومان)",
                reply_markup=_user_keyboard())
        except Exception as e:
            print(f"❌ خطا در cmd_referral: {e}")

    @_bot.message_handler(func=lambda m: m.text == "🛒 خرید الماس", chat_types=['private'])
    def cmd_buy(message):
        try:
            if not require_membership(message): return
            account = db.get_account_by_tg_id(message.from_user.id)
            username_txt = account["username"] if account else str(message.from_user.id)
            
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(types.InlineKeyboardButton("📩 خرید از مالک (@Amele55)", url="https://t.me/Amele55"))
            sponsors = getattr(config, 'SPONSORS', [])
            for sp in sponsors:
                markup.add(types.InlineKeyboardButton(f"🤝 {sp['name']}: @{sp['username']}", url=f"https://t.me/{sp['username']}"))

            token_price = getattr(config, 'TOKEN_PRICE_TOMAN', 200)
            _bot.reply_to(message,
                f"🛒 <b>خرید الماس</b>\n\n"
                f"💰 قیمت هر الماس: <b>{token_price} تومان</b>\n"
                f"👤 یوزرنیم پنل شما: <b>{username_txt}</b>\n\n"
                f"برای خرید، روی دکمه «خرید از مالک» کلیک کنید و یوزرنیم پنل خود را ارسال نمایید.",
                reply_markup=markup)
        except Exception as e:
            print(f"❌ خطا در cmd_buy: {e}")

    # --- انتقال الماس ---
    @_bot.message_handler(commands=["transfer"])
    def cmd_transfer(message):
        try:
            if message.chat.type != 'private':
                return _bot.reply_to(message, "❌ این دستور فقط در پیوی قابل استفاده است.")
            if not require_membership(message): return
            
            parts = message.text.strip().split()
            if len(parts) != 3:
                return _bot.reply_to(message, "❌ فرمت اشتباه.\nدرست: <code>/transfer @username amount</code>\nمثال: <code>/transfer @ali 10</code>")
            
            target_username = parts[1].lstrip("@")
            try:
                amount = int(parts[2])
            except:
                return _bot.reply_to(message, "❌ مقدار الماس باید عدد باشد.")
            
            from_account = db.get_account_by_tg_id(message.from_user.id)
            to_account = db.get_account_by_username(target_username)
            
            if not to_account:
                return _bot.reply_to(message, f"❌ کاربری با یوزرنیم {target_username} یافت نشد.")
            
            success, msg = db.transfer_diamonds(from_account["id"], to_account["id"], amount)
            
            if success:
                _bot.reply_to(message, f"✅ {msg}")
                to_tg_id = db.get_telegram_id_by_owner(to_account["id"])
                if to_tg_id:
                    try:
                        _bot.send_message(to_tg_id, f"🎁 <b>{amount} الماس</b> از طرف <b>{from_account['username']}</b> دریافت کردید!\n💎 موجودی جدید: <b>{db.get_token_balance(to_account['id'])}</b>")
                    except: pass
            else:
                _bot.reply_to(message, msg)
        except Exception as e:
            print(f"❌ خطا در cmd_transfer: {e}")

    # --- قرعه کشی گروهی ---
    @_bot.message_handler(commands=["lottery"])
    def cmd_lottery(message):
        try:
            if message.chat.type not in ['group', 'supergroup']:
                return _bot.reply_to(message, "❌ قرعه‌کشی فقط در گروه‌ها قابل ایجاد است.")
            if message.from_user.id != OWNER_TG_ID:
                return _bot.reply_to(message, "❌ فقط مالک می‌تواند قرعه‌کشی ایجاد کند.")
            
            parts = message.text.strip().split()
            if len(parts) != 2:
                return _bot.reply_to(message, "❌ فرمت اشتباه.\nدرست: <code>/lottery amount</code>\nمثال: <code>/lottery 100</code>")
            
            try:
                prize_amount = int(parts[1])
            except:
                return _bot.reply_to(message, "❌ مبلغ جایزه باید عدد باشد.")
            
            duration = getattr(config, 'LOTTERY_DURATION_MINUTES', 5)
            lottery_id = db.create_lottery(message.chat.id, message.from_user.id, prize_amount, duration)
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🎲 شرکت در قرعه‌کشی (۱ الماس)", callback_data=f"join_lottery_{lottery_id}"))
            
            end_time = datetime.datetime.now() + datetime.timedelta(minutes=duration)
            end_time_str = end_time.strftime("%H:%M")
            
            msg = _bot.send_message(message.chat.id,
                f"🎉 <b>قرعه‌کشی ویژه!</b>\n\n"
                f"💎 مبلغ جایزه: <b>{prize_amount} الماس</b>\n"
                f"⏰ زمان پایان: <b>{end_time_str}</b>\n\n"
                f"برای شرکت، روی دکمه زیر کلیک کنید!\n"
                f"(هزینه شرکت: ۱ الماس از موجودی شما)",
                reply_markup=markup)
            
            db.update_lottery_message(lottery_id, msg.message_id)
        except Exception as e:
            print(f"❌ خطا در cmd_lottery: {e}")

    @_bot.callback_query_handler(func=lambda call: call.data.startswith("join_lottery_"))
    def callback_join_lottery(call):
        try:
            lottery_id = int(call.data.split("_")[2])
            lottery = db.get_lottery(lottery_id)
            
            if not lottery or lottery["status"] != "active":
                return _bot.answer_callback_query(call.id, "❌ این قرعه‌کشی فعال نیست یا به پایان رسیده.", show_alert=True)
            
            account = db.get_account_by_tg_id(call.from_user.id)
            if not account:
                return _bot.answer_callback_query(call.id, "❌ ابتدا در پنل وب ثبت‌نام کنید.", show_alert=True)
            
            bet_amount = 1  # هزینه شرکت در قرعه‌کشی
            
            success, msg = db.join_lottery(lottery_id, call.from_user.id, account["id"], bet_amount)
            if success:
                _bot.answer_callback_query(call.id, "✅ با موفقیت شرکت کردید!", show_alert=True)
            else:
                _bot.answer_callback_query(call.id, msg, show_alert=True)
        except Exception as e:
            print(f"❌ خطا در callback_join_lottery: {e}")

    # --- جام جهانی ---
    @_bot.message_handler(commands=["wc_create"])
    def cmd_wc_create(message):
        try:
            if message.from_user.id != OWNER_TG_ID:
                return
            parts = message.text.strip().split(" | ")
            if len(parts) != 4:
                return _bot.reply_to(message, "❌ فرمت: <code>/wc_create Team1 | Team2 | Time | Amount</code>\nمثال: <code>/wc_create Iran | USA | 18:00 | 10</code>")
            
            team1, team2, match_time, bet_amount = parts
            try:
                bet_amount = int(bet_amount)
            except:
                return _bot.reply_to(message, "❌ مبلغ شرط باید عدد باشد.")
            
            challenge_id = db.create_world_cup_challenge(team1.strip(), team2.strip(), match_time.strip(), bet_amount)
            
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(types.InlineKeyboardButton(f"🔵 {team1}", callback_data=f"bet_wc_{challenge_id}_{team1}"))
            markup.add(types.InlineKeyboardButton(f"🔴 {team2}", callback_data=f"bet_wc_{challenge_id}_{team2}"))
            
            group = getattr(config, 'WORLD_CUP_GROUP', '@amelselfgap')
            try:
                msg = _bot.send_message(group,
                    f"⚽️ <b>چالش جام جهانی!</b>\n\n"
                    f"🆚 <b>{team1}</b> در برابر <b>{team2}</b>\n"
                    f"⏰ ساعت: <b>{match_time}</b>\n"
                    f"💎 مبلغ شرط: <b>{bet_amount} الماس</b>\n\n"
                    f"کدام تیم برنده می‌شود؟ شرط ببندید!",
                    reply_markup=markup)
                db.update_challenge_message(challenge_id, msg.message_id, msg.chat.id)
                _bot.reply_to(message, "✅ چالش با موفقیت در گروه ارسال شد.")
            except Exception as e:
                _bot.reply_to(message, f"❌ خطا در ارسال به گروه: {e}\nمطمئن شوید ربات در گروه {group} ادمین است.")
        except Exception as e:
            print(f"❌ خطا در cmd_wc_create: {e}")

    @_bot.callback_query_handler(func=lambda call: call.data.startswith("bet_wc_"))
    def callback_bet_wc(call):
        try:
            parts = call.data.split("_")
            challenge_id = int(parts[2])
            team_choice = "_".join(parts[3:])
            
            challenge = db.get_challenge(challenge_id)
            if not challenge or challenge["status"] != "active":
                return _bot.answer_callback_query(call.id, "❌ این چالش فعال نیست.", show_alert=True)
            
            account = db.get_account_by_tg_id(call.from_user.id)
            if not account:
                return _bot.answer_callback_query(call.id, "❌ ابتدا در پنل وب ثبت‌نام کنید.", show_alert=True)
            
            success, msg = db.place_bet(challenge_id, call.from_user.id, account["id"], team_choice, challenge["bet_amount"])
            if success:
                _bot.answer_callback_query(call.id, f"✅ شرط شما روی {team_choice} ثبت شد!", show_alert=True)
            else:
                _bot.answer_callback_query(call.id, msg, show_alert=True)
        except Exception as e:
            print(f"❌ خطا در callback_bet_wc: {e}")

    @_bot.message_handler(commands=["wc_winner"])
    def cmd_wc_winner(message):
        try:
            if message.from_user.id != OWNER_TG_ID:
                return
            parts = message.text.strip().split()
            if len(parts) != 3:
                return _bot.reply_to(message, "❌ فرمت: <code>/wc_winner [challenge_id] [winning_team]</code>")
            
            challenge_id = int(parts[1])
            winning_team = parts[2]
            
            db.set_challenge_winner(challenge_id, winning_team)
            success, results = db.settle_challenge_bets(challenge_id)
            
            if success:
                won_count = sum(1 for r in results if r["result"] == "won")
                lost_count = sum(1 for r in results if r["result"] == "lost")
                
                for r in results:
                    if r["result"] == "won":
                        try:
                            _bot.send_message(r["user_tg_id"], f"🎉 تبریک! شرط شما درست بود.\n💎 <b>{r['amount']} الماس</b> به حساب شما واریز شد.")
                        except: pass
                
                _bot.reply_to(message, f"✅ نتیجه چالش ثبت شد.\n🏆 برنده: <b>{winning_team}</b>\n✅ برندگان: {won_count} نفر\n❌ بازندگان: {lost_count} نفر")
            else:
                _bot.reply_to(message, f"❌ خطا: {results}")
        except Exception as e:
            print(f"❌ خطا در cmd_wc_winner: {e}")

    # --- دستورات اختصاصی مالک ---
    @_bot.message_handler(func=lambda m: m.text == "📢 مدیریت چنل‌ها", chat_types=['private'])
    def cmd_admin_channels(message):
        try:
            if message.from_user.id != OWNER_TG_ID: return
            channels = db.get_forced_channels()
            if not channels:
                text = "📋 لیست چنل‌ها خالی است.\n\nبرای افزودن:\n<code>/addchannel @ChannelID</code>"
            else:
                text = "📋 <b>چنل‌های اجباری فعلی:</b>\n" + "\n".join([f"🔸 {ch}" for ch in channels])
                text += "\n\nبرای حذف:\n<code>/removechannel @ChannelID</code>"
            _bot.reply_to(message, text, reply_markup=_owner_keyboard())
        except Exception as e:
            print(f"❌ خطا در cmd_admin_channels: {e}")

    @_bot.message_handler(commands=["addchannel"])
    def cmd_add_channel(message):
        try:
            if message.from_user.id != OWNER_TG_ID: return
            parts = message.text.strip().split()
            if len(parts) < 2: return _bot.reply_to(message, "فرمت: <code>/addchannel @ChannelID</code>")
            if db.add_forced_channel(parts[1]):
                _bot.reply_to(message, f"✅ چنل <b>{parts[1]}</b> اضافه شد.", reply_markup=_owner_keyboard())
            else:
                _bot.reply_to(message, "⚠️ خطا یا تکراری است.", reply_markup=_owner_keyboard())
        except Exception as e:
            print(f"❌ خطا در cmd_add_channel: {e}")

    @_bot.message_handler(commands=["removechannel"])
    def cmd_remove_channel(message):
        try:
            if message.from_user.id != OWNER_TG_ID: return
            parts = message.text.strip().split()
            if len(parts) < 2: return _bot.reply_to(message, "فرمت: <code>/removechannel @ChannelID</code>")
            if db.remove_forced_channel(parts[1]):
                _bot.reply_to(message, f"✅ چنل <b>{parts[1]}</b> حذف شد.", reply_markup=_owner_keyboard())
            else:
                _bot.reply_to(message, "⚠️ چنل در لیست نبود.", reply_markup=_owner_keyboard())
        except Exception as e:
            print(f"❌ خطا در cmd_remove_channel: {e}")

    @_bot.message_handler(commands=["give"])
    def cmd_give(message):
        try:
            if message.from_user.id != OWNER_TG_ID: return
            parts = message.text.strip().split()
            if len(parts) < 3: return _bot.reply_to(message, "فرمت: <code>/give username amount</code>")
            target = parts[1].lstrip("@")
            try:
                amount = int(parts[2])
            except:
                return _bot.reply_to(message, "❌ مقدار باید عدد باشد.")
            
            account = db.get_account_by_username(target)
            if not account: return _bot.reply_to(message, f"❌ کاربر '{target}' یافت نشد.")
            
            db.add_tokens(account["id"], amount)
            new_balance = db.get_token_balance(account["id"])
            token_price = getattr(config, 'TOKEN_PRICE_TOMAN', 200)
            _bot.reply_to(message,
                f"✅ <b>{amount}</b> الماس به <b>{account['username']}</b> داده شد.\n"
                f"💎 موجودی جدید: <b>{new_balance}</b> (معادل {new_balance * token_price} تومان)",
                reply_markup=_owner_keyboard())
            
            tg_id = db.get_telegram_id_by_owner(account["id"])
            if tg_id:
                try:
                    _bot.send_message(tg_id, f"🎁 <b>{amount}</b> الماس از طرف مالک دریافت کردید!\n💎 موجودی جدید: <b>{new_balance}</b>")
                except: pass
        except Exception as e:
            print(f"❌ خطا در cmd_give: {e}")

    @_bot.message_handler(commands=["users"])
    def cmd_users(message):
        try:
            if message.from_user.id != OWNER_TG_ID: return
            accounts = db.get_all_accounts()
            if not accounts: return _bot.reply_to(message, "هیچ کاربری ثبت نشده.")
            lines = [f"👥 <b>کاربران ({len(accounts)} نفر):</b>\n"]
            for acc in accounts[:20]:
                bal = db.get_token_balance(acc["id"])
                lines.append(f"• <b>{acc['username']}</b> — ID:{acc['id']} — 💎{bal}")
            _bot.reply_to(message, "\n".join(lines))
        except Exception as e:
            print(f"❌ خطا در cmd_users: {e}")

    @_bot.message_handler(func=lambda m: True, chat_types=['private'])
    def cmd_unknown(message):
        try:
            account = db.get_account_by_tg_id(message.from_user.id)
            if not account: return
            if not require_membership(message): return
            if message.from_user.id == OWNER_TG_ID:
                _bot.reply_to(message, "لطفاً از دکمه‌های زیر استفاده کنید:", reply_markup=_owner_keyboard())
            else:
                _bot.reply_to(message, "لطفاً از دکمه‌های زیر استفاده کنید:", reply_markup=_user_keyboard())
        except Exception as e:
            print(f"❌ خطا در cmd_unknown: {e}")

    def _polling_loop():
        import time as _t
        while True:
            try:
                _bot.infinity_polling(timeout=30, long_polling_timeout=25, restart_on_change=False, skip_pending=True)
            except Exception as e:
                if "409" in str(e):
                    _t.sleep(10)
                    try: _bot.delete_webhook(drop_pending_updates=True)
                    except: pass
                else:
                    _t.sleep(5)

    t = threading.Thread(target=_polling_loop, daemon=True)
    t.start()
    print(f"✅ ربات الماس @{BOT_USERNAME} استارت شد.")

def _user_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💎 موجودی", "🎁 هدیه روزانه")
    markup.add("🔗 رفرال", "🛒 خرید الماس")
    return markup

def _owner_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("💎 موجودی", "🎁 هدیه روزانه")
    markup.add("🔗 رفرال", "🛒 خرید الماس")
    markup.add("📢 مدیریت چنل‌ها")
    return markup
