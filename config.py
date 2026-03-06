import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "nepal-election-2026-secret")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "election.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Admin credentials (change in production!)
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "election2026")

    # Scraper settings — aggressive for election day live counting
    SCRAPE_INTERVAL_SECONDS = 30   # scrape every 30 seconds
    SCRAPE_ENABLED = True          # auto-start scraper on launch
    EC_BASE_URL = "https://election.gov.np"
