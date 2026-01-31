# Concert Finder

Find upcoming concerts near you based on your music taste. Optionally discover shows by similar artists you might not know yet.

## Setup

### 1. Get API Keys (Free)

**Ticketmaster:**
1. Go to https://developer.ticketmaster.com/
2. Create an account and sign in
3. Go to "My Apps" and create a new app
4. Copy your **Consumer Key**

**Last.fm:**
1. Go to https://www.last.fm/api/account/create
2. Create a Last.fm account if you don't have one
3. Fill in the API application form (app name, description can be anything)
4. Copy your **API Key** (you don't need the shared secret)

### 2. Local Development

```bash
# Install dependencies
cd boston-concerts-app
pip install -r requirements.txt

# Create secrets file
cp .streamlit/secrets.toml.example .streamlit/secrets.toml

# Edit .streamlit/secrets.toml with your API keys
```

Run the app:
```bash
streamlit run app.py
```

### 3. Deploy to Streamlit Cloud (Free)

1. Push this folder to a GitHub repo
2. Go to https://share.streamlit.io/
3. Sign in with GitHub
4. Click "New app" and select your repo
5. In "Advanced settings" > "Secrets", add:
   ```
   TICKETMASTER_API_KEY = "your_key_here"
   LASTFM_API_KEY = "your_key_here"
   ```
6. Deploy!

## Features

- **Zip code + radius**: Find shows near you (10-100 miles)
- **Up to 10 favorite artists**: We'll search for their shows
- **Up to 3 genres**: Broader discovery by genre
- **Date range**: Next 2 weeks to 6 months
- **Exclude large venues**: Skip arenas if you prefer intimate shows
- **Similar artists**: Optionally expand your search with Last.fm's related artists

## Project Structure

```
boston-concerts-app/
├── app.py                      # Main Streamlit app
├── requirements.txt            # Python dependencies
├── .gitignore                  # Keeps secrets out of git
├── .streamlit/
│   └── secrets.toml.example    # Template for API keys
└── README.md
```
