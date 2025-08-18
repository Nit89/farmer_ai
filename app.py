import os
import requests
from flask import Flask, request
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
import re
from googletrans import Translator
from gtts import gTTS
import whisper
import subprocess
import torch
import threading
import base64
translator = Translator()
load_dotenv()
app = Flask(__name__)
asr_model = whisper.load_model("medium")  
torch.set_num_threads(1)

# ---------------- CONFIG ----------------
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
API_VERSION = os.getenv("API_VERSION", "v17.0")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectordb = Chroma(persist_directory="chroma", embedding_function=embeddings)

SESSIONS = {}   # Track user state
os.makedirs("downloads", exist_ok=True)

# ---------------- WEBHOOK VERIFY ----------------
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

# ---------------- MAIN WEBHOOK ----------------
@app.route("/webhook", methods=["POST"])
def receive_message():
    data = request.get_json()
    print("Incoming:", data)

    if data.get("object"):
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                
                # ✅ Handle status updates (delivery/read receipts)
                if "statuses" in value:
                    print("Status update:", value["statuses"])
                    return "EVENT_RECEIVED", 200  

                # ✅ Handle actual user messages
                messages = value.get("messages", [])
                for message in messages:
                    from_number = message.get("from")
                    msg_type = message.get("type", "")

                    if msg_type == "text":
                        text = message["text"]["body"].strip()
                        handle_text(from_number, text)

                    elif msg_type == "audio":
                        media_id = message["audio"]["id"]
                        audio_file = download_whatsapp_media(media_id)
                        if audio_file:
                            threading.Thread(
                                target=handle_voice, args=(from_number, audio_file), daemon=True
                            ).start()

                    elif msg_type == "location":
                        lat = message["location"]["latitude"]
                        lon = message["location"]["longitude"]
                        weather_info = get_weather(lat, lon)
                        SESSIONS[from_number] = {"step": "after_weather", "location": (lat, lon)}
                        send_message(from_number, weather_info)
                        send_message(
                            from_number,
                            "What would you like next?\n1. Soil condition\n2. Market prices\n3. Pest diagnosis (send image)\n4. Finance & schemes"
                        )

                    elif msg_type == "image":
                        media_id = message["image"]["id"]
                        image_path = download_whatsapp_media(media_id, file_type="image")
                        if image_path:
                            detected_lang = SESSIONS.get(from_number, {}).get("lang", "hi")
                            diagnosis = analyze_crop_image(image_path, detected_lang)
                            send_message(from_number, f"🔍 Pest Diagnosis:\n{diagnosis}")
                            audio_reply = text_to_speech(diagnosis, lang_code=detected_lang)
                            send_voice_message(from_number, audio_reply)

    # ✅ Always return a valid response
    return "EVENT_RECEIVED", 200


# ---------------- TRANSLATION ----------------
def translate_to_english(user_input: str):
    try:
        detected = translator.detect(user_input).lang
        translated = translator.translate(user_input, src=detected, dest="en").text
        return translated, detected
    except Exception as e:
        print("Translation error:", e)
        return user_input, "en"

def translate_from_english(response_text: str, target_lang: str):
    try:
        if target_lang == "en":
            return response_text
        return translator.translate(response_text, src="en", dest=target_lang).text
    except Exception as e:
        print("Back-translation error:", e)
        return response_text

# ---------------- RAG SEARCH ----------------
def rag_search(query: str, k: int = 3):
    try:
        docs = vectordb.similarity_search(query, k=k)
        if not docs:
            return None
        context = "\n\n".join([d.page_content for d in docs])
        return context
    except Exception as e:
        print("RAG search error:", e)
        return None

# ---------------- LOCATION EXTRACTION ----------------
def extract_city_from_text(text: str):
    match = re.search(r"in\s+([A-Za-z\s]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

def get_lat_lon_from_city(city: str):
    try:
        url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={OPENWEATHER_API_KEY}"
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return data[0]["lat"], data[0]["lon"]
    except Exception as e:
        print("Geo API error:", e)
    return None, None

# ---------------- TEXT HANDLER ----------------
def handle_text(user, text):
    translated_text, detected_lang = translate_to_english(text)
    print(f"🌐 Detected language: {detected_lang}, Query in English: {translated_text}")

    # ✅ Store user language if not already set
    if user not in SESSIONS:
        SESSIONS[user] = {}
    if "lang" not in SESSIONS[user]:
        SESSIONS[user]["lang"] = detected_lang

    # Always use stored language preference
    user_lang = SESSIONS[user]["lang"]

    state = SESSIONS.get(user, {})
    city = extract_city_from_text(text)
    if city:
        lat, lon = get_lat_lon_from_city(city)
        if lat and lon:
            weather_info = get_weather(lat, lon)
            SESSIONS[user]["step"] = "after_weather"
            SESSIONS[user]["location"] = (lat, lon)
            send_message(user, f"📍 Detected your location as {city}.")
            send_message(user, translate_from_english(weather_info, user_lang))
            send_message(
                user,
                translate_from_english(
                    "What would you like next?\n1. Soil condition\n2. Market prices\n3. Pest diagnosis (send image)\n4. Finance & schemes",
                    user_lang
                )
            )
            return

    if "step" not in state:
        send_message(user, translate_from_english("👋 Hi! Please share your location to get started.", user_lang))
        return

    if state.get("step") == "after_weather":
        intent = classify_intent(text)
        llm_answer = ask_llm(translated_text, user)
        final_answer = translate_from_english(llm_answer, user_lang)
        send_message(user, final_answer)
    else:
        send_message(user, translate_from_english("Please share your location first.", user_lang))


# ---------------- INTENT CLASSIFIER ----------------
def classify_intent(user_text: str) -> str:
    prompt = f"""
    Classify the farmer's request into one of these categories:
    - soil
    - market
    - pest
    - finance
    If it doesn’t match, return 'unknown'.
    Farmer's query: "{user_text}"
    """
    try:
        response = model.generate_content(prompt)
        answer = response.text.lower().strip()
        if "soil" in answer: return "soil"
        if "market" in answer: return "market"
        if "pest" in answer: return "pest"
        if "finance" in answer or "scheme" in answer: return "finance"
        return "unknown"
    except Exception as e:
        print("LLM intent error:", e)
        return "unknown"

# ---------------- ASK LLM ----------------
def ask_llm(query: str, user=None) -> str:
    try:
        context = rag_search(query)
        weather_info = None
        if user in SESSIONS and "location" in SESSIONS[user]:
            lat, lon = SESSIONS[user]["location"]
            weather_info = get_weather(lat, lon)

        kb_text = f"Relevant knowledge base:\n{context}" if context else "No relevant knowledge base found."
        weather_text = f"Weather & location info: {weather_info}" if weather_info else ""

        prompt = f"""
        You are an intelligent agriculture assistant.

        Farmer's query: {query}

        {kb_text}

        {weather_text}

        Task:
        - Use retrieved knowledge (if any).
        - Consider weather/location context if available.
        - Add your own expertise.
        - Answer concisely, in farmer-friendly language.
        """

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        print("LLM error:", e)
        return "I couldn’t process your request right now."

# ---------------- UTILITIES ----------------
def send_message(to, body):
    url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    MAX_LENGTH = 4096
    chunks = [body[i:i+MAX_LENGTH] for i in range(0, len(body), MAX_LENGTH)]
    for chunk in chunks:
        payload = {"messaging_product": "whatsapp", "to": to, "type": "text", "text": {"body": chunk}}
        resp = requests.post(url, headers=headers, json=payload)
        print("Send status:", resp.status_code, resp.json())

def get_weather(lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        city = data.get("name", "your area")
        temp = data["main"]["temp"]
        condition = data["weather"][0]["description"]
        return f"🌤️ Weather in {city}: {temp}°C, {condition}"
    return "Unable to fetch weather right now."

def download_whatsapp_media(media_id, file_type="audio"):
    try:
        url = f"https://graph.facebook.com/{API_VERSION}/{media_id}"
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return None

        media_url = resp.json().get("url")
        media_resp = requests.get(media_url, headers=headers, stream=True)
        if media_resp.status_code != 200:
            return None

        # Choose correct extension
        ext = ".jpg" if file_type == "image" else ".ogg"
        file_path = f"downloads/{media_id}{ext}"

        with open(file_path, "wb") as f:
            for chunk in media_resp.iter_content(chunk_size=8192):
                f.write(chunk)

        return file_path
    except Exception as e:
        print("Error downloading WhatsApp media:", e)
        return None


def speech_to_text(audio_file):
    result = asr_model.transcribe(audio_file, fp16=False)
    return result["text"], result.get("language", "hi")

def text_to_speech(text, lang_code="hi", output_file="downloads/output.mp3"):
    tts = gTTS(text=text, lang=lang_code)
    tts.save(output_file)
    return output_file

def upload_audio(audio_path):
    url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/media"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    ext = os.path.splitext(audio_path)[1].lower()
    mime_type = "audio/mpeg" if ext == ".mp3" else "audio/ogg"
    files = {"file": (os.path.basename(audio_path), open(audio_path, "rb"), mime_type)}
    data = {"messaging_product": "whatsapp"}
    resp = requests.post(url, headers=headers, files=files, data=data)
    resp_json = resp.json()
    if resp.status_code == 200 and "id" in resp_json:
        return resp_json["id"]
    return None

def send_voice_message(to, audio_path):
    media_id = upload_audio(audio_path)
    if not media_id:
        return
    url = f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to, "type": "audio", "audio": {"id": media_id}}
    requests.post(url, headers=headers, json=payload)

def handle_voice(from_number, audio_file_path):
    try:
        wav_file = audio_file_path.replace(".ogg", ".wav")
        subprocess.run(["ffmpeg", "-y", "-i", audio_file_path, "-ar", "16000", "-ac", "1", wav_file], check=True)

        text, detected_lang = speech_to_text(wav_file)
        print("Transcribed text:", text)

        # ✅ Use stored language if available, else set it now
        if from_number not in SESSIONS:
            SESSIONS[from_number] = {}
        if "lang" not in SESSIONS[from_number]:
            SESSIONS[from_number]["lang"] = detected_lang

        user_lang = SESSIONS[from_number]["lang"]

        answer_en = ask_llm(text, from_number)
        answer = translate_from_english(answer_en, user_lang)

        send_message(from_number, answer)

        audio_reply = text_to_speech(answer, lang_code=user_lang)
        send_voice_message(from_number, audio_reply)

    except Exception as e:
        print("Error in handle_voice:", e)
        send_message(from_number, "⚠️ Sorry, I couldn’t process your voice message.")

        
        
        
# ---------------- pest diagonisis----------------


def encode_image_to_base64(image_path):
    """Convert image file to base64 string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# --- Pest Diagnosis (Image) ---

def analyze_crop_image(image_path, lang="en"):
    try:
        base64_image = encode_image_to_base64(image_path)

        prompt = f"""
        You are an agricultural assistant.
        Analyze this crop image and identify if there are any pests or diseases.
        Suggest treatment methods in {lang} language.
        Keep explanation simple and farmer-friendly.
        """

        response = model.generate_content(
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": base64_image
                            }
                        }
                    ]
                }
            ]
        )
        return response.text.strip()

    except Exception as e:
        print("Error in pest diagnosis:", e)
        return "⚠️ Sorry, I couldn’t analyze the crop image right now."


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)