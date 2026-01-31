import streamlit as st
import requests
from datetime import datetime, timedelta
from dateutil import parser

# Page config
st.set_page_config(
    page_title="Concert Finder",
    page_icon="🎸",
    layout="wide"
)

# Constants
VENUE_SIZE_THRESHOLD = 10000  # Exclude venues larger than this capacity
LASTFM_API_URL = "http://ws.audioscrobbler.com/2.0/"


def get_similar_artists_lastfm(artist_name, limit=3):
    """Get similar artists using Last.fm API."""
    api_key = st.secrets.get("LASTFM_API_KEY", "")

    if not api_key:
        return []

    response = requests.get(
        LASTFM_API_URL,
        params={
            "method": "artist.getsimilar",
            "artist": artist_name,
            "api_key": api_key,
            "format": "json",
            "limit": limit
        }
    )

    if response.status_code == 200:
        data = response.json()
        similar = data.get("similarartists", {}).get("artist", [])
        return [a["name"] for a in similar]
    return []


@st.cache_data(ttl=3600)
def get_artist_popularity(artist_name):
    """Get artist popularity (listener count) from Last.fm."""
    api_key = st.secrets.get("LASTFM_API_KEY", "")

    if not api_key:
        return 0

    response = requests.get(
        LASTFM_API_URL,
        params={
            "method": "artist.getinfo",
            "artist": artist_name,
            "api_key": api_key,
            "format": "json"
        }
    )

    if response.status_code == 200:
        data = response.json()
        artist_info = data.get("artist", {})
        stats = artist_info.get("stats", {})
        listeners = stats.get("listeners", "0")
        try:
            return int(listeners)
        except (ValueError, TypeError):
            return 0
    return 0


def extract_artist_from_event(event):
    """Extract the main artist name from an event."""
    # Try to get from attractions first (most reliable)
    attractions = event.get("_embedded", {}).get("attractions", [])
    if attractions:
        return attractions[0].get("name", "")

    # Fall back to event name, removing common suffixes
    name = event.get("name", "")
    # Remove common tour/show suffixes
    for suffix in [" Tour", " Live", " Concert", " Show", " Presents", " World Tour"]:
        if suffix in name:
            name = name.split(suffix)[0]
    return name.strip()


def search_ticketmaster_events(artists, genres, postal_code, radius, start_date, end_date, exclude_large_venues):
    """Search Ticketmaster for events matching criteria."""
    api_key = st.secrets.get("TICKETMASTER_API_KEY", "")
    if not api_key:
        st.error("Ticketmaster API key not configured")
        return []

    all_events = []
    seen_event_ids = set()

    # Search by artist keywords
    search_terms = artists + genres

    for term in search_terms:
        if not term.strip():
            continue

        params = {
            "apikey": api_key,
            "keyword": term,
            "postalCode": postal_code,
            "radius": radius,
            "unit": "miles",
            "classificationName": "Music",
            "startDateTime": start_date.strftime("%Y-%m-%dT00:00:00Z"),
            "endDateTime": end_date.strftime("%Y-%m-%dT23:59:59Z"),
            "size": 50,
            "sort": "date,asc"
        }

        try:
            response = requests.get(
                "https://app.ticketmaster.com/discovery/v2/events.json",
                params=params
            )

            if response.status_code == 200:
                data = response.json()
                events = data.get("_embedded", {}).get("events", [])

                for event in events:
                    event_id = event.get("id")
                    if event_id in seen_event_ids:
                        continue

                    # Check venue size if excluding large venues
                    if exclude_large_venues:
                        venues = event.get("_embedded", {}).get("venues", [])
                        if venues:
                            venue = venues[0]
                            # Check multiple places where capacity might be stored
                            capacity = None
                            if venue.get("generalInfo", {}).get("capacity"):
                                capacity = venue.get("generalInfo", {}).get("capacity")
                            elif venue.get("upcomingEvents", {}).get("_total"):
                                # Some venues store capacity differently
                                pass
                            # Also check boxOfficeInfo
                            if not capacity and venue.get("boxOfficeInfo", {}).get("capacity"):
                                capacity = venue.get("boxOfficeInfo", {}).get("capacity")

                            if capacity:
                                try:
                                    if int(capacity) > VENUE_SIZE_THRESHOLD:
                                        continue
                                except (ValueError, TypeError):
                                    pass

                    seen_event_ids.add(event_id)
                    all_events.append(event)

        except requests.RequestException as e:
            st.warning(f"Error searching for '{term}': {e}")

    # Sort by date
    all_events.sort(key=lambda e: e.get("dates", {}).get("start", {}).get("dateTime", ""))

    return all_events


def format_event(event):
    """Format an event for display."""
    name = event.get("name", "Unknown Event")

    # Date
    dates = event.get("dates", {}).get("start", {})
    date_str = dates.get("localDate", "TBD")
    time_str = dates.get("localTime", "")
    if date_str != "TBD":
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            date_str = dt.strftime("%a, %b %d, %Y")
        except ValueError:
            pass
    if time_str:
        try:
            t = datetime.strptime(time_str, "%H:%M:%S")
            time_str = t.strftime("%I:%M %p")
        except ValueError:
            pass

    # Venue
    venues = event.get("_embedded", {}).get("venues", [])
    venue_name = venues[0].get("name", "Unknown Venue") if venues else "Unknown Venue"
    venue_city = venues[0].get("city", {}).get("name", "") if venues else ""

    # Ticket URL
    url = event.get("url", "")

    # Price range
    price_ranges = event.get("priceRanges", [])
    price_str = ""
    if price_ranges:
        min_price = price_ranges[0].get("min", 0)
        max_price = price_ranges[0].get("max", 0)
        if min_price and max_price:
            price_str = f"${min_price:.0f} - ${max_price:.0f}"
        elif min_price:
            price_str = f"From ${min_price:.0f}"

    # Images
    images = event.get("images", [])
    image_url = ""
    if images:
        # Find a reasonably sized image
        for img in images:
            if img.get("width", 0) >= 200:
                image_url = img.get("url", "")
                break
        if not image_url:
            image_url = images[0].get("url", "")

    # Get artist name
    attractions = event.get("_embedded", {}).get("attractions", [])
    artist_name = attractions[0].get("name", "") if attractions else ""

    return {
        "name": name,
        "date": date_str,
        "time": time_str,
        "venue": venue_name,
        "city": venue_city,
        "url": url,
        "price": price_str,
        "image": image_url,
        "artist": artist_name,
        "popularity": event.get("_popularity", 0)
    }


# Main app
st.title("Concert Finder")
st.markdown("Find upcoming concerts near you based on your music taste.")

# Sidebar for inputs
with st.sidebar:
    st.header("Your Preferences")

    # Location
    zip_code = st.text_input("Your Zip Code", value="02101", max_chars=5)

    # Distance radius
    radius = st.select_slider(
        "Search Radius",
        options=[10, 25, 50, 75, 100],
        value=25,
        format_func=lambda x: f"{x} miles"
    )

    # Date range
    st.subheader("Date Range")
    date_options = {
        "Next 2 weeks": 14,
        "Next month": 30,
        "Next 3 months": 90,
        "Next 6 months": 180
    }
    date_range = st.selectbox("Show concerts in", options=list(date_options.keys()), index=1)

    # Venue size
    exclude_large = st.checkbox("Exclude large venues/arenas", value=True)

    # Similar artists toggle
    include_similar = st.checkbox(
        "Include similar artists to broaden discovery",
        value=True,
        help="Uses Last.fm to find artists similar to your favorites"
    )

    # Sort option
    sort_by = st.selectbox(
        "Sort results by",
        options=["Popularity (most popular first)", "Date (soonest first)"],
        index=0
    )

    st.divider()

    # Artists input
    st.subheader("Your Favorite Artists")
    st.caption("Enter up to 10 artists (one per line)")
    artists_input = st.text_area(
        "Artists",
        placeholder="Radiohead\nThe National\nPhoebe Bridgers",
        height=200,
        label_visibility="collapsed"
    )

    # Genres input
    st.subheader("Genres You Like")
    st.caption("Enter up to 3 genres")
    genres_input = st.text_area(
        "Genres",
        placeholder="indie rock\njazz\nfolk",
        height=100,
        label_visibility="collapsed"
    )

    search_button = st.button("Find Concerts", type="primary", use_container_width=True)

# Process search
if search_button:
    # Parse inputs
    artists = [a.strip() for a in artists_input.strip().split("\n") if a.strip()][:10]
    genres = [g.strip() for g in genres_input.strip().split("\n") if g.strip()][:3]

    if not artists and not genres:
        st.warning("Please enter at least one artist or genre.")
    else:
        # Calculate dates
        start_date = datetime.now()
        end_date = start_date + timedelta(days=date_options[date_range])

        # Expand artists with similar artists if enabled
        all_artists = artists.copy()
        similar_artist_map = {}

        if include_similar and artists:
            with st.spinner("Finding similar artists..."):
                api_key = st.secrets.get("LASTFM_API_KEY", "")
                if api_key:
                    for artist in artists:
                        related = get_similar_artists_lastfm(artist, limit=5)
                        for related_name in related:
                            if related_name.lower() not in [a.lower() for a in all_artists]:
                                all_artists.append(related_name)
                                if artist not in similar_artist_map:
                                    similar_artist_map[artist] = []
                                similar_artist_map[artist].append(related_name)
                else:
                    st.warning("Last.fm API key not configured. Searching for your listed artists only.")

        # Show similar artists found
        if similar_artist_map:
            with st.expander("Similar artists we're also searching for", expanded=False):
                for original, similar in similar_artist_map.items():
                    st.markdown(f"**{original}** → {', '.join(similar)}")

        # Search for events
        with st.spinner("Searching for concerts..."):
            events = search_ticketmaster_events(
                all_artists,
                genres,
                zip_code,
                radius,
                start_date,
                end_date,
                exclude_large
            )

        # Display results
        if events:
            # Fetch popularity scores and sort
            if sort_by.startswith("Popularity"):
                with st.spinner("Ranking by artist popularity..."):
                    for event in events:
                        artist_name = extract_artist_from_event(event)
                        event["_popularity"] = get_artist_popularity(artist_name) if artist_name else 0
                    events.sort(key=lambda e: e.get("_popularity", 0), reverse=True)
            else:
                events.sort(key=lambda e: e.get("dates", {}).get("start", {}).get("dateTime", ""))

            st.success(f"Found {len(events)} concerts!")

            for event in events:
                formatted = format_event(event)

                col1, col2 = st.columns([1, 3])

                with col1:
                    if formatted["image"]:
                        st.image(formatted["image"], use_container_width=True)

                with col2:
                    st.markdown(f"### {formatted['name']}")
                    st.markdown(f"**{formatted['date']}** {formatted['time']}")
                    st.markdown(f"📍 {formatted['venue']}" + (f", {formatted['city']}" if formatted['city'] else ""))

                    # Show popularity if available
                    if formatted["popularity"] > 0:
                        listeners = formatted["popularity"]
                        if listeners >= 1_000_000:
                            pop_str = f"{listeners / 1_000_000:.1f}M listeners"
                        elif listeners >= 1_000:
                            pop_str = f"{listeners / 1_000:.0f}K listeners"
                        else:
                            pop_str = f"{listeners} listeners"
                        st.caption(f"🎧 {pop_str} on Last.fm")

                    if formatted["price"]:
                        st.markdown(f"💰 {formatted['price']}")
                    if formatted["url"]:
                        st.markdown(f"[🎟️ Get Tickets]({formatted['url']})")

                st.divider()
        else:
            st.info("No concerts found matching your criteria. Try expanding your date range or adding more artists/genres.")

# Footer
st.markdown("---")
st.caption("Data provided by Ticketmaster and Last.fm. Built with Streamlit.")
