
# Complete Setup Guide: WhatsApp Farming Assistant

This guide will walk you through setting up the multilingual farming assistant on your local machine, from creating a WhatsApp sandbox to running the full application.

## Prerequisites

Before starting, make sure you have:
- Python 3.8 or higher installed
- A Meta Developer account
- FFmpeg installed on your system
- Basic command line knowledge

## Step 1: Set Up WhatsApp Business API (Sandbox)

### 1.1 Create Meta Developer Account
1. Go to [developers.facebook.com](https://developers.facebook.com)
2. Click "Get Started" and log in with your Facebook account
3. Complete the developer account setup process

### 1.2 Create a New App
1. Click "Create App" in the developer dashboard
2. Select "Business" as the app type
3. Fill in your app details:
   - **App Name**: `Farming Assistant` (or your preferred name)
   - **App Contact Email**: Your email address
4. Click "Create App"

### 1.3 Add WhatsApp Product
1. In your app dashboard, scroll down to "Add Products to Your App"
2. Find "WhatsApp" and click "Set Up"
3. You'll be taken to the WhatsApp setup page

### 1.4 Configure WhatsApp Sandbox
1. In the WhatsApp setup page, you'll see:
   - **Phone Number ID**: Copy this value
   - **WhatsApp Business Account ID**: Note this down
   - **Test Phone Number**: This is the sandbox number farmers will message

2. **Generate Access Token**:
   - Click "Generate Token" next to "Temporary Access Token"
   - Copy the token (starts with `EAA...`)
   - ⚠️ **Important**: This expires in 24 hours for testing

3. **Add Test Numbers**:
   - Scroll to "Step 1: Add recipient phone number"
   - Add your phone number (include country code, e.g., +919876543210)
   - Send the verification code to your WhatsApp
   - Enter the code to verify

## Step 2: Set Up Webhook URL

You'll need a public URL for WhatsApp to send messages to your local server. We'll use ngrok for this.

### 2.1 Install ngrok
```bash
# Download from https://ngrok.com/download
# Or install via package manager:

# macOS
brew install ngrok

# Ubuntu/Debian
sudo apt install ngrok

# Windows: Download and extract from website
```

### 2.2 Get Your Webhook URL
```bash
# Start ngrok tunnel (run this in a separate terminal)
ngrok http 5001
```

You'll see output like:
```
Forwarding    https://abc123.ngrok.io -> http://localhost:5001
```

Copy the `https://abc123.ngrok.io` URL - this is your webhook URL.

### 2.3 Configure Webhook in Meta Dashboard
1. Go back to your WhatsApp setup page
2. Scroll to "Step 2: Configure Webhooks"
3. **Callback URL**: Enter `https://your-ngrok-url.ngrok.io/webhook`
4. **Verify Token**: Create a random string (e.g., `myverifytoken123`)
5. **Webhook Fields**: Select these options:
   - ✅ messages
   - ✅ message_deliveries
   - ✅ message_reads
   - ✅ message_echoes
6. Click "Verify and Save"

## Step 3: Get API Keys

### 3.1 OpenWeather API
1. Go to [openweathermap.org](https://openweathermap.org/api)
2. Sign up for a free account
3. Go to "API Keys" section
4. Copy your API key

### 3.2 Google Gemini API
1. Go to [ai.google.dev](https://ai.google.dev)
2. Click "Get API Key"
3. Create a new project or select existing one
4. Generate API key and copy it

## Step 4: Set Up Local Environment

### 4.1 Clone/Create Project Directory
```bash
mkdir whatsapp-farming-assistant
cd whatsapp-farming-assistant
```

### 4.2 Create Python Virtual Environment
```bash
# Create virtual environment
python -m venv farming_env

# Activate it
# On macOS/Linux:
source farming_env/bin/activate
# On Windows:
farming_env\Scripts\activate
```

### 4.3 Install Required Packages
```bash
pip install flask python-dotenv requests
pip install google-generativeai
pip install langchain langchain-community
pip install chromadb sentence-transformers
pip install googletrans==3.1.0a0
pip install gtts
pip install openai-whisper
pip install torch torchvision torchaudio
pip install beautifulsoup4
```

### 4.4 Install FFmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows:**
1. Download from [ffmpeg.org](https://ffmpeg.org/download.html)
2. Extract to a folder (e.g., `C:\ffmpeg`)
3. Add `C:\ffmpeg\bin` to your system PATH

## Step 5: Configure Environment Variables

### 5.1 Create .env File
Create a file named `.env` in your project directory:

```env
# WhatsApp API Configuration
VERIFY_TOKEN=myverifytoken123
ACCESS_TOKEN=your_temporary_access_token_here
PHONE_NUMBER_ID=your_phone_number_id_here
API_VERSION=v17.0

# API Keys
OPENWEATHER_API_KEY=your_openweather_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### 5.2 Fill in Your Values
Replace the placeholder values with:
- `VERIFY_TOKEN`: The verify token you created in Step 2.3
- `ACCESS_TOKEN`: The temporary access token from Meta
- `PHONE_NUMBER_ID`: From your WhatsApp setup page
- `OPENWEATHER_API_KEY`: From Step 3.1
- `GEMINI_API_KEY`: From Step 3.2

## Step 6: Set Up Knowledge Base

### 6.1 Create Knowledge Base Setup File
Create `rag_setup.py` with the provided code for building the vector database.

### 6.2 Create Documents Folder
```bash
mkdir docs
```

### 6.3 Add Sample Documents
Add some farming-related PDF files or text documents to the `docs` folder:
- Government agricultural schemes
- Pest management guides
- Soil health information
- Market price data

### 6.4 Build Vector Database
```bash
python rag_setup.py
```

This will create a `chroma` folder with your searchable knowledge base.

## Step 7: Create and Run the Main Application

### 7.1 Create Main Application File
Save the provided main application code as `app.py` in your project directory.

### 7.2 Create Required Folders
```bash
mkdir downloads
```

### 7.3 Run the Application
```bash
python app.py
```

You should see:
```
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5001
 * Running on http://[your-ip]:5001
```

## Step 8: Test the Setup

### 8.1 Verify Webhook Connection
1. Check your ngrok terminal - you should see webhook verification requests
2. In Meta dashboard, the webhook status should show as "Connected"

### 8.2 Test with WhatsApp
1. Open WhatsApp on your phone
2. Send a message to the test number provided in Meta dashboard
3. Start with: "Hi, I need farming advice"
4. Send your location when prompted
5. Try sending:
   - Text questions about farming
   - Voice messages
   - Photos of crops/plants

### 8.3 Check Logs
Monitor your terminal running the Flask app for:
- Incoming message logs
- Translation processes
- RAG search results
- Any error messages

## Troubleshooting Common Issues

### Webhook Not Receiving Messages
- **Check ngrok**: Make sure ngrok is still running and URL hasn't changed
- **Verify token**: Ensure VERIFY_TOKEN in .env matches what you set in Meta dashboard
- **Check Meta settings**: Verify webhook fields are selected correctly

### Translation Errors
- **Network issues**: Google Translate requires internet connection
- **Rate limiting**: Free tier has limits; add delays between requests if needed

### Voice Processing Slow
- **Model size**: Consider using `whisper.load_model("small")` for faster processing
- **Threading**: Voice processing runs in background threads to avoid blocking

### Image Analysis Failing
- **File format**: Code assumes JPG; ensure images are clear and well-lit
- **Base64 encoding**: Check if image file was downloaded successfully

### Weather API Not Working
- **API key**: Verify your OpenWeather API key is active
- **Rate limits**: Free tier allows 1000 calls per day

## File Structure

Your final project structure should look like:
```
whatsapp-farming-assistant/
├── farming_env/              # Virtual environment
├── app.py                    # Main application
├── rag_setup.py             # Knowledge base builder
├── .env                     # Configuration file
├── docs/                    # Knowledge base documents
│   ├── farming_guide.pdf
│   └── pest_management.txt
├── chroma/                  # Vector database (created by rag_setup.py)
├── downloads/               # Temporary media files
└── requirements.txt         # Package dependencies (optional)
```
