import feedparser

# A few Nigerian news RSS feeds — we'll start with these and can add more later
RSS_FEEDS = {
    "Punch": "https://punchng.com/feed/",
    "Vanguard": "https://www.vanguardngr.com/feed/",
    "Premium Times": "https://www.premiumtimesng.com/feed",
}

CRIME_KEYWORDS = [
    "robbery", "robbers", "robbed", "kidnap", "kidnapping", "kidnapped",
    "abduct", "abducted", "gunmen", "bandits", "armed", "hostage",
    "ransom", "rustled", "rustling"
]


def fetch_all_headlines():
    all_headlines = []

    for source_name, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            all_headlines.append({
                "title": entry.title,
                "source": source_name,
                "link": entry.link
            })

    return all_headlines


def filter_crime_related(headlines):
    filtered = []
    for h in headlines:
        title_lower = h["title"].lower()
        if any(keyword in title_lower for keyword in CRIME_KEYWORDS):
            filtered.append(h)
    return filtered


if __name__ == "__main__":
    headlines = fetch_all_headlines()
    print(f"Fetched {len(headlines)} headlines total.\n")

    crime_headlines = filter_crime_related(headlines)
    print(f"Filtered down to {len(crime_headlines)} crime-related headlines:\n")
    for h in crime_headlines:
        print(f"[{h['source']}] {h['title']}")