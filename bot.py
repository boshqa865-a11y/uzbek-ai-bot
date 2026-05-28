import os
import tempfile
import edge_tts
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import BadRequest
from groq import Groq

# --- SOZLAMALAR ---
TELEGRAM_TOKEN = "TOKEN_BU_YERDA"
GROQ_API_KEY = "GROQ_KEY_BU_YERDA"

groq_client = Groq(api_key=GROQ_API_KEY)

# Foydalanuvchi ma'lumotlari
user_data = {}

SYSTEM_PROMPT = """Siz o'zbek tilida gaplashadigan do'stona AI yordamchisiz.
FAQAT lotin alifbosida yozing. Kirill harflaridan foydalanmang.
Qisqa, aniq va tabiiy javob bering.
Agar foydalanuvchi haqida muhim ma'lumot bilsangiz (ismi, yoshi, kasbi va h.k.), undan foydalaning."""

# --- YORDAMCHI FUNKSIYALAR ---
def get_user(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            "history": [],
            "memory": {}  # muhim ma'lumotlar: ism, yosh, kasb va h.k.
        }
    return user_data[user_id]

def extract_memory(user_text, ai_text, current_memory):
    try:
        prompt = f"""Foydalanuvchi gapidan FAQAT quyidagi ma'lumotlarni ajrat:
- ism (faqat ism bo'lsa)
- yosh (faqat son bo'lsa)
- kasb (faqat kasb bo'lsa)
- shahar (faqat shahar bo'lsa)
- qiziqishlar (faqat aniq qiziqish bo'lsa)

QOIDALAR:
- Salomlashish, savol, javob kabi narsalarni SAQLAМА
- Agar aniq ma'lumot yo'q bo'lsa, null qo'y
- Mavjud ma'lumotni o'chirma, yangilab qo'y
- FAQAT JSON qaytар, izoh yozma

Mavjud: {current_memory}
Foydalanuvchi: {user_text}

JSON format: {{"ism": null, "yosh": null, "kasb": null, "shahar": null, "qiziqishlar": null}}"""

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )
        import json
        result = response.choices[0].message.content.strip()
        result = result.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(result)
        # Faqat null bo'lmagan qiymatlarni saqlash
        merged = {k: v for k, v in current_memory.items() if v}
        for k, v in parsed.items():
            if v and v != "null":
                merged[k] = v
        return merged
    except Exception:
        return current_memory

        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )
        import json
        result = response.choices[0].message.content.strip()
        result = result.replace("```json", "").replace("```", "").strip()
        return json.loads(result)
    except:
        return current_memory

def build_system_prompt(memory):
    prompt = SYSTEM_PROMPT
    if memory:
        facts = ", ".join([f"{k}: {v}" for k, v in memory.items() if v])
        if facts:
            prompt += f"\n\nFoydalanuvchi haqida ma'lumotlar: {facts}"
    return prompt

# --- TUGMALAR ---
def main_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📜 Tarix", callback_data="show_history"),
            InlineKeyboardButton("🧠 Xotira", callback_data="show_memory"),
        ],
        [
            InlineKeyboardButton("🗑 Tarixni tozala", callback_data="clear_history"),
            InlineKeyboardButton("📊 Statistika", callback_data="stats"),
        ],
        [
            InlineKeyboardButton("ℹ️ Yordam", callback_data="help"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    get_user(user_id)
    await update.message.reply_text(
        "👋 Salom! Men AI yordamchiman!\n\n"
        "🎤 Ovozli xabar — javob beraman\n"
        "💬 Matn yozing — javob beraman\n"
        "🧠 Sizni eslab qolaman!\n\n"
        "Quyidagi tugmalardan foydalaning 👇",
        reply_markup=main_keyboard()
    )

# --- CALLBACK HANDLER ---
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = get_user(user_id)

    try:
        if query.data == "show_history":
            history = data["history"]
            if not history:
                text = "📜 Tarix bo'sh!\n\nHali hech qanday suhbat yo'q."
            else:
                text = "📜 *Oxirgi suhbatlar:*\n\n"
                for msg in history[-6:]:
                    if msg["role"] == "user":
                        text += f"👤 *Siz:* {msg['content'][:100]}\n\n"
                    else:
                        text += f"🤖 *AI:* {msg['content'][:100]}\n\n"
            await query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=main_keyboard()
            )

        elif query.data == "show_memory":
            memory = data["memory"]
            if not memory:
                text = "🧠 Xotira bo'sh!\n\nHali sizning ma'lumotlaringiz saqlanmagan."
            else:
                text = "🧠 *Siz haqingizda bilganlarim:*\n\n"
                icons = {
                    "ism": "👤", "yosh": "🎂", "kasb": "💼",
                    "shahar": "🏙", "qiziqishlar": "⭐"
                }
                for k, v in memory.items():
                    if v:
                        icon = icons.get(k, "📌")
                        text += f"{icon} *{k.capitalize()}:* {v}\n"
            await query.edit_message_text(
                text, parse_mode="Markdown", reply_markup=main_keyboard()
            )

        elif query.data == "clear_history":
            keyboard = [
                [
                    InlineKeyboardButton("✅ Ha, tozala", callback_data="confirm_clear"),
                    InlineKeyboardButton("❌ Yo'q", callback_data="cancel_clear"),
                ]
            ]
            await query.edit_message_text(
                "⚠️ Tarixni tozalaylikmi?\n(Xotira saqlanib qoladi)",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif query.data == "confirm_clear":
            data["history"] = []
            await query.edit_message_text(
                "✅ Tarix tozalandi!\n🧠 Xotira saqlanib qoldi.",
                reply_markup=main_keyboard()
            )

        elif query.data == "cancel_clear":
            await query.edit_message_text(
                "❌ Bekor qilindi.",
                reply_markup=main_keyboard()
            )

        elif query.data == "stats":
            history = data["history"]
            memory = data["memory"]
            user_msgs = len([m for m in history if m["role"] == "user"])
            await query.edit_message_text(
                f"📊 *Statistika:*\n\n"
                f"💬 Xabarlar: {user_msgs}\n"
                f"🧠 Saqlangan faktlar: {len(memory)}\n"
                f"📝 Tarixdagi xabarlar: {len(history)}",
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )

        elif query.data == "help":
            await query.edit_message_text(
                "ℹ️ *Yordam:*\n\n"
                "🎤 Ovozli xabar — AI ovozli javob beradi\n"
                "💬 Matn — AI matn bilan javob beradi\n"
                "📜 Tarix — oxirgi suhbatlar\n"
                "🧠 Xotira — siz haqida saqlangan ma'lumotlar\n"
                "🗑 Tarixni tozalash — yangi suhbat boshlash\n"
                "📊 Statistika — xabarlar soni",
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )

    except BadRequest as e:
        if "Message is not modified" in str(e):
            pass  # Tugma ikki marta bosildi — e'tibor berma
        else:
            raise e

# --- OVOZLI XABAR ---
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = get_user(user_id)

    await update.message.reply_text("🎤 Eshitildi, javob tayyorlanmoqda...")

    try:
        file = await context.bot.get_file(update.message.voice.file_id)
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            voice_path = tmp.name

        with open(voice_path, 'rb') as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=("audio.ogg", audio_file),
                model="whisper-large-v3-turbo",
                language="uz",
                prompt="O'zbek tilida gap. Lotin alifbosida yoz."
            )
        user_text = transcription.text

        data["history"].append({"role": "user", "content": user_text})
        if len(data["history"]) > 20:
            data["history"] = data["history"][-20:]

        messages = [{"role": "system", "content": build_system_prompt(data["memory"])}] + data["history"]
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )
        ai_text = response.choices[0].message.content
        data["history"].append({"role": "assistant", "content": ai_text})

        # Xotiraga muhim ma'lumotlarni saqlash
        data["memory"] = extract_memory(user_text, ai_text, data["memory"])

        audio_path = tempfile.mktemp(suffix='.mp3')
        communicate = edge_tts.Communicate(ai_text, voice="uz-UZ-SardorNeural")
        await communicate.save(audio_path)

        await update.message.reply_text(
            f"📝 Siz: {user_text}\n\n🤖 AI: {ai_text}",
            reply_markup=main_keyboard()
        )
        with open(audio_path, 'rb') as audio:
            await update.message.reply_voice(voice=audio)

        os.unlink(voice_path)
        os.unlink(audio_path)

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")

# --- MATNLI XABAR ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = get_user(user_id)
    user_text = update.message.text

    try:
        data["history"].append({"role": "user", "content": user_text})
        if len(data["history"]) > 20:
            data["history"] = data["history"][-20:]

        messages = [{"role": "system", "content": build_system_prompt(data["memory"])}] + data["history"]
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )
        ai_text = response.choices[0].message.content
        data["history"].append({"role": "assistant", "content": ai_text})

        # Xotiraga muhim ma'lumotlarni saqlash
        data["memory"] = extract_memory(user_text, ai_text, data["memory"])

        await update.message.reply_text(
            f"🤖 {ai_text}",
            reply_markup=main_keyboard()
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik: {str(e)}")

# --- MAIN ---
def main():
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(read_timeout=60, write_timeout=60, connect_timeout=60)
    app = Application.builder().token(TELEGRAM_TOKEN).request(request).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("✅ Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()