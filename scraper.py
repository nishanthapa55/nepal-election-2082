"""
Nepal Election Results Scraper (2082)
=====================================
Scrapes live election results from real sources:
  1. Ekantipur Election Portal (election.ekantipur.com) - candidate-level data
  2. Election Commission Nepal (result.election.gov.np) - official party summary

Architecture:
  - EkantipurScraper: fetches constituency pages in rotating batches,
    parses __NEXT_DATA__ JSON or falls back to HTML text parsing
  - ECNScraper: fetches official ASP.NET results page
  - ScraperCoordinator: runs scrapers, reconciles data, updates database
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from models import db, Constituency, Candidate, Party, Result, ScraperLog, District
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time
import random
import re
import json
import traceback

logger = logging.getLogger(__name__)

# ──────────────────────── Nepali Numeral Conversion ────────────────────────

NEPALI_DIGITS = {'०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
                 '५': '5', '६': '6', '७': '7', '८': '8', '९': '9'}


def nepali_to_int(text):
    """Convert Nepali numeral string (e.g. '१,०४१') to integer. Returns None if invalid."""
    if not text:
        return None
    converted = ''
    for ch in text:
        if ch in NEPALI_DIGITS:
            converted += NEPALI_DIGITS[ch]
        elif ch == ',':
            continue
        elif ch.isdigit():
            converted += ch
        else:
            break  # stop at non-numeric chars like 'अग्रता'
    converted = converted.strip()
    if converted and converted.isdigit():
        return int(converted)
    return None


# ──────────────────────── Constants ────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]

# ──────────────────────── Party Name Mapping ────────────────────────

PARTY_NAME_MAP = {
    # Nepali Congress
    "nepali congress": "NC", "nc": "NC", "congress": "NC",
    "\u0928\u0947\u092a\u093e\u0932\u0940 \u0915\u093e\u0901\u0917\u094d\u0930\u0947\u0938": "NC",
    "\u0928\u0947\u092a\u093e\u0932\u0940 \u0915\u093e\u0902\u0917\u094d\u0930\u0947\u0938": "NC",
    # CPN-UML
    "cpn-uml": "UML", "cpn uml": "UML", "uml": "UML", "cpn (uml)": "UML",
    "\u0928\u0947\u0915\u092a\u093e \u090f\u092e\u093e\u0932\u0947": "UML",
    "\u090f\u092e\u093e\u0932\u0947": "UML",
    # Maoist Centre
    "cpn-mc": "MC", "maoist": "MC", "maoist centre": "MC",
    "cpn (maoist centre)": "MC", "nepali communist party": "MC",
    "nepal communist party (maoist)": "MC", "ncp": "MC",
    "\u0928\u0947\u092a\u093e\u0932\u0940 \u0915\u092e\u094d\u092f\u0941\u0928\u093f\u0938\u094d\u091f \u092a\u093e\u0930\u094d\u091f\u0940": "MC",
    "\u092e\u093e\u0913\u0935\u093e\u0926\u0940 \u0915\u0947\u0928\u094d\u0926\u094d\u0930": "MC",
    # RSP
    "rsp": "RSP", "rastriya swatantra party": "RSP",
    "rastirya swatantra party": "RSP", "swatantra": "RSP",
    "\u0930\u093e\u0937\u094d\u091f\u094d\u0930\u093f\u092f \u0938\u094d\u0935\u0924\u0928\u094d\u0924\u094d\u0930 \u092a\u093e\u0930\u094d\u091f\u0940": "RSP",
    "\u0930\u093e\u0938\u094d\u0935\u092a\u093e": "RSP",
    # RPP
    "rpp": "RPP", "rastriya prajatantra party": "RPP",
    "\u0930\u093e\u0937\u094d\u091f\u094d\u0930\u093f\u092f \u092a\u094d\u0930\u091c\u093e\u0924\u0928\u094d\u0924\u094d\u0930 \u092a\u093e\u0930\u094d\u091f\u0940": "RPP",
    "\u0930\u093e\u092a\u094d\u0930\u092a\u093e": "RPP",
    # JSP
    "jsp": "JSP", "janata samajwadi": "JSP", "janata samajwadi party": "JSP",
    "janata samjbadi party-nepal": "JSP", "janata samajwadi party, nepal": "JSP",
    "\u091c\u0928\u0924\u093e \u0938\u092e\u093e\u091c\u0935\u093e\u0926\u0940 \u092a\u093e\u0930\u094d\u091f\u0940": "JSP",
    "\u091c\u0938\u092a\u093e": "JSP",
    # Janamat
    "janamat": "JP", "janamat party": "JP",
    "\u091c\u0928\u092e\u0924 \u092a\u093e\u0930\u094d\u091f\u0940": "JP",
    # Nagarik Unmukti
    "nup": "NUP", "nagarik unmukti": "NUP", "nagarik unmukti party": "NUP",
    "\u0928\u093e\u0917\u0930\u093f\u0915 \u0909\u0928\u094d\u092e\u0941\u0915\u094d\u0924\u093f \u092a\u093e\u0930\u094d\u091f\u0940": "NUP",
    # NWPP
    "nwpp": "NWPP", "nepal workers peasants party": "NWPP",
    "\u0928\u0947\u092a\u093e\u0932 \u092e\u091c\u0926\u0941\u0930 \u0915\u093f\u0938\u093e\u0928 \u092a\u093e\u0930\u094d\u091f\u0940": "NWPP",
    # LSP
    "lsp": "LSP", "loktantrik samajwadi": "LSP",
    "loktantrik samajwadi party": "LSP",
    "\u0932\u094b\u0915\u0924\u093e\u0928\u094d\u0924\u094d\u0930\u093f\u0915 \u0938\u092e\u093e\u091c\u0935\u093e\u0926\u0940 \u092a\u093e\u0930\u094d\u091f\u0940": "LSP",
    # CPN Unified Socialist
    "cpn-us": "US", "unified socialist": "US",
    "cpn (unified socialist)": "US",
    "\u090f\u0915\u0940\u0915\u0943\u0924 \u0938\u092e\u093e\u091c\u0935\u093e\u0926\u0940": "US",
    # Ujaylo Nepal Party (Kulman Ghising)
    "ujaylo nepal party": "UNP", "ujaylo nepal": "UNP",
    "\u0909\u091c\u094d\u092f\u093e\u0932\u094b \u0928\u0947\u092a\u093e\u0932 \u092a\u093e\u0930\u094d\u091f\u0940": "UNP",
    # Shram Sanskriti Party
    "shram sanskriti party": "SSP",
    "श्रम संस्कृति पार्टी": "SSP",
    # JSP with Nepal suffix (OnlineKhabar style)
    "janata samajwadi party, nepal": "JSP",
    "जनता समाजवादी पार्टी, नेपाल": "JSP",
    # Nepal Communist Party (United) -> US
    "नेपाल कम्युनिष्ट पार्टी (संयुक्त)": "US",
    # Nepal Communist Party (Maoist) alternate
    "नेपाल कम्युनिस्ट पार्टी (माओवादी)": "MC",
    # Rastriya Mukti Party
    "rastriya mukti party nepal": "RMPN",
    "rastriya mukti party nepal (ekal chunab chinha)": "RMPN",
    # Independent
    "independent": "IND", "ind": "IND",
    "\u0938\u094d\u0935\u0924\u0928\u094d\u0924\u094d\u0930": "IND",
}


def resolve_party(name_str):
    """Resolve a party name string to our DB short_name."""
    if not name_str:
        return None
    key = name_str.strip().lower()
    return PARTY_NAME_MAP.get(key)


# ──────────────── District Slug for Ekantipur URLs ─────────────────

DISTRICT_SLUG_OVERRIDES = {
    "Nawalparasi East": "nawalparasi(e)",
    "Nawalparasi West": "nawalparasi(w)",
    "Nawalparasi (East)": "nawalparasi(e)",
    "Nawalparasi (West)": "nawalparasi(w)",
    "Eastern Rukum": "rukumeast",
    "Western Rukum": "rukum(w)",
    "Rukum (East)": "rukumeast",
    "Rukum (West)": "rukum(w)",
    "Kavrepalanchok": "kavreplanchowk",
    "Tanahu": "tanahun",
    "Dadeldhura": "dadeldura",
    "Dolakha": "dolkha",
}


def district_to_slug(name):
    """Convert DB district name to ekantipur URL slug."""
    if name in DISTRICT_SLUG_OVERRIDES:
        return DISTRICT_SLUG_OVERRIDES[name]
    return name.lower().replace(" ", "")


# ──────────── OnlineKhabar URL Slug Mapping ────────────

OKHABAR_SLUG_OVERRIDES = {
    "Ilam": "illam",
    "Dhanusha": "dhanusa",
    "Rupandehi": "rupendehi",
    "Eastern Rukum": "rukum",
    "Western Rukum": "rukumwest",
    "Nawalparasi East": "nawalparasi",
    "Nawalparasi West": "nawalparasiwest",
    "Kavrepalanchok": "kavrepalanchowk",
    "Tanahu": "tanahun",
    "Sindhupalchok": "sindhupalchowk",
    "Dadeldhura": "dadeldhura",
}


def district_to_okhabar_slug(name):
    """Convert DB district name to OnlineKhabar URL slug."""
    if name in OKHABAR_SLUG_OVERRIDES:
        return OKHABAR_SLUG_OVERRIDES[name]
    return name.lower().replace(" ", "")


# ──────────────────────── Base Scraper ────────────────────────

class BaseScraper:
    """Common HTTP + retry logic."""
    name = "base"
    display_name = "Base"
    enabled = True
    timeout = 20

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ne;q=0.8",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        })

    def fetch(self, url, **kwargs):
        """Fetch a URL with retry (2 attempts)."""
        timeout = kwargs.pop("timeout", self.timeout)
        for attempt in range(2):
            try:
                resp = self.session.get(url, timeout=timeout, **kwargs)
                resp.raise_for_status()
                return resp
            except Exception as e:
                if attempt == 0:
                    time.sleep(0.5)
                else:
                    raise

    def run(self):
        raise NotImplementedError


# ──────────────────────── Ekantipur Scraper ────────────────────────

class EkantipurScraper(BaseScraper):
    """
    Scrapes election.ekantipur.com for candidate-level vote counts.

    Strategy:
      1. Build constituency URLs from DB (pradesh-{P}/district-{D}/constituency-{N})
      2. Fetch a rotating batch of constituency pages
      3. Parse __NEXT_DATA__ JSON if present, else parse HTML
    """
    name = "ekantipur"
    display_name = "Ekantipur"
    enabled = True
    timeout = 15

    BASE = "https://election.ekantipur.com"

    def _build_constituency_urls(self):
        """Build list of (constituency_id, name, url) from database."""
        urls = []
        try:
            constituencies = (
                Constituency.query
                .join(District)
                .order_by(Constituency.id)
                .all()
            )
            for c in constituencies:
                district = c.district
                if not district or not district.province:
                    continue
                province_id = district.province_id
                slug = district_to_slug(district.name)
                url = f"{self.BASE}/pradesh-{province_id}/district-{slug}/constituency-{c.number}?lng=eng"
                urls.append((c.id, c.name, url))
        except Exception as e:
            logger.error(f"[Ekantipur] Failed to build URLs: {e}")
        return urls

    def run(self):
        results = []
        errors = []

        try:
            all_urls = self._build_constituency_urls()
        except Exception as e:
            return [], [f"Failed to build URLs: {e}"]

        if not all_urls:
            return [], ["No constituency URLs generated"]

        # Fetch ALL constituencies every cycle for maximum coverage and speed
        batch = all_urls[:]
        logger.info(f"[Ekantipur] Fetching all {len(batch)} constituencies")

        # Fetch pages with thread pool — 25 workers for fast parallel fetching
        def fetch_one(item):
            cid, cname, url = item
            try:
                resp = self.fetch(url, timeout=10)
                page_results = self._parse_constituency_page(resp.text, cname)
                return page_results, None
            except Exception as e:
                return [], f"{cname}: {str(e)[:80]}"

        with ThreadPoolExecutor(max_workers=25) as executor:
            futures = {executor.submit(fetch_one, item): item for item in batch}
            for future in as_completed(futures, timeout=60):
                try:
                    page_results, error = future.result(timeout=15)
                    results.extend(page_results)
                    if error:
                        errors.append(error)
                except Exception as e:
                    item = futures[future]
                    errors.append(f"{item[1]}: timeout/error")

        logger.info(f"[Ekantipur] Got {len(results)} candidate results, {len(errors)} errors")
        return results, errors

    def _parse_constituency_page(self, html, constituency_name):
        """
        Parse an ekantipur constituency page for candidate vote data.
        
        HTML structure (verified):
          <table>
            <tr> <!-- header row -->
              <th>Candidate</th><th>Party</th><th>Total Votes</th>
            </tr>
            <tr> <!-- candidate rows -->
              <td>
                <a class="candidate-name-link">
                  <figure><img .../></figure>
                  <span>Kulman Ghising</span>
                </a>
              </td>
              <td>
                <a>...<span>Ujaylo Nepal Party</span></a>
              </td>
              <td>
                <div class="votecount win|lost d-flex align-items-center">
                  <p>1,041</p>        <!-- vote count -->
                  <span>293</span>    <!-- secondary info (booths/etc) -->
                </div>
              </td>
            </tr>
          </table>
        """
        results = []
        soup = BeautifulSoup(html, "html.parser")

        # Find all table rows with votecount divs (candidate result rows)
        rows = soup.find_all("tr")
        
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            
            try:
                # Column 1: Candidate name
                name_span = cells[0].find("span")
                if not name_span:
                    continue
                candidate_name = name_span.get_text(strip=True)
                if not candidate_name:
                    continue
                
                # Column 2: Party name
                party_span = cells[1].find("span")
                if party_span:
                    party_name = party_span.get_text(strip=True)
                else:
                    party_name = cells[1].get_text(strip=True)
                
                # Column 3: Vote count from <p> inside votecount div
                vote_div = cells[2].find(class_=re.compile(r"votecount"))
                if not vote_div:
                    continue
                vote_p = vote_div.find("p")
                if not vote_p:
                    continue
                vote_text = vote_p.get_text(strip=True).replace(",", "")
                if not vote_text or not vote_text.isdigit():
                    continue
                votes = int(vote_text)
                
                if votes <= 0:
                    continue
                
                # Check if this candidate is leading (has "win" class)
                is_leading = "win" in (vote_div.get("class") or [])
                
                # Check if officially elected (span contains "Elected" text)
                is_elected = False
                if is_leading:
                    vote_span = vote_div.find("span")
                    if vote_span and "elected" in vote_span.get_text().lower():
                        is_elected = True
                
                party_short = resolve_party(party_name)
                
                results.append({
                    "candidate": candidate_name,
                    "votes": votes,
                    "party_short": party_short,
                    "party_name": party_name,
                    "constituency": constituency_name,
                    "source": "ekantipur",
                    "is_leading": is_leading,
                    "is_elected": is_elected,
                })
            except Exception as e:
                logger.debug(f"[Ekantipur] Row parse error in {constituency_name}: {e}")
                continue

        if results:
            logger.debug(f"[Ekantipur] {constituency_name}: {len(results)} candidates, "
                        f"leading: {next((r['candidate'] for r in results if r.get('is_leading')), 'N/A')}")
        
        return results


# ──────────────────────── OnlineKhabar Scraper ────────────────────────

class OnlineKhabarScraper(BaseScraper):
    """
    Scrapes election.onlinekhabar.com for candidate vote counts.
    URL: https://election.onlinekhabar.com/central-chetra/{district_slug}{number}
    
    SAFETY: This scraper runs in UPDATE-ONLY mode.
    It can only update vote counts for candidates already in the DB (from Ekantipur).
    It matches by constituency + party. It NEVER creates new candidates or results.
    """
    name = "onlinekhabar"
    display_name = "OnlineKhabar"
    enabled = True
    timeout = 15

    BASE = "https://election.onlinekhabar.com"

    def _build_constituency_urls(self):
        """Build list of (constituency_id, name, url) from database."""
        urls = []
        try:
            constituencies = (
                Constituency.query
                .join(District)
                .order_by(Constituency.id)
                .all()
            )
            for c in constituencies:
                district = c.district
                if not district:
                    continue
                slug = district_to_okhabar_slug(district.name)
                url = f"{self.BASE}/central-chetra/{slug}{c.number}"
                urls.append((c.id, c.name, url))
        except Exception as e:
            logger.error(f"[OnlineKhabar] Failed to build URLs: {e}")
        return urls

    def run(self):
        results = []
        errors = []

        try:
            all_urls = self._build_constituency_urls()
        except Exception as e:
            return [], [f"Failed to build URLs: {e}"]

        if not all_urls:
            return [], ["No constituency URLs generated"]

        # Fetch counting + declared constituencies (where Ekantipur has already found data)
        try:
            active_ids = set(
                c.id for c in Constituency.query.filter(
                    Constituency.status.in_(["counting", "declared"])
                ).all()
            )
        except Exception:
            active_ids = set()

        if not active_ids:
            # No active constituencies yet — skip entirely, let Ekantipur discover first
            return [], []

        batch = [(cid, name, url) for cid, name, url in all_urls if cid in active_ids]
        logger.info(f"[OnlineKhabar] Fetching {len(batch)} active constituencies")

        def fetch_one(item):
            cid, cname, url = item
            try:
                resp = self.fetch(url, timeout=10)
                page_results = self._parse_page(resp.text, cname)
                return page_results, None
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 404:
                    return [], None
                return [], f"{cname}: {str(e)[:60]}"
            except Exception as e:
                return [], f"{cname}: {str(e)[:60]}"

        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = {executor.submit(fetch_one, item): item for item in batch}
            for future in as_completed(futures, timeout=60):
                try:
                    page_results, error = future.result(timeout=15)
                    results.extend(page_results)
                    if error:
                        errors.append(error)
                except Exception as e:
                    item = futures[future]
                    errors.append(f"{item[1]}: timeout")

        logger.info(f"[OnlineKhabar] Got {len(results)} candidate results, {len(errors)} errors")
        return results, errors

    def _parse_page(self, html, constituency_name):
        """
        Parse OnlineKhabar constituency page — FIRST table only (2082 current results).
        
        The page has tabs: "प्रत्यक्ष" (current), "प्रत्यक्ष २०७९", "समानुपातिक मत-२०७९"
        Only the first <table> contains current 2082 election data.
        
        Table format (Nepali):
          | N. | Name Gender, Age वर्ष | Party | VoteCount |
        """
        results = []
        soup = BeautifulSoup(html, "html.parser")

        # Only parse the FIRST table — this is the current 2082 "प्रत्यक्ष" tab
        table = soup.find("table")
        if not table:
            return results

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            try:
                # Cell 1: candidate name + "पुरुष/महिला, XX वर्ष"
                cell_text = cells[1].get_text(strip=True)
                # Must contain gender marker to be a candidate row
                if "पुरुष" not in cell_text and "महिला" not in cell_text:
                    continue
                name_match = re.match(r'(.+?)\s*(पुरुष|महिला)', cell_text)
                if not name_match:
                    continue
                candidate_name = name_match.group(1).strip()
                if not candidate_name:
                    continue

                # Cell 2: party name (Nepali)
                party_name = cells[2].get_text(strip=True)

                # Cell 3: votes (Nepali numerals) possibly with "अग्रता"
                vote_text = cells[3].get_text(strip=True)
                votes = nepali_to_int(vote_text)

                if not votes or votes <= 0:
                    continue

                party_short = resolve_party(party_name)
                if not party_short:
                    continue  # Skip if we can't identify the party

                results.append({
                    "candidate": candidate_name,
                    "votes": votes,
                    "party_short": party_short,
                    "party_name": party_name,
                    "constituency": constituency_name,
                    "source": "onlinekhabar",
                })
            except Exception as e:
                logger.debug(f"[OnlineKhabar] Row parse error in {constituency_name}: {e}")
                continue

        if results:
            logger.debug(f"[OnlineKhabar] {constituency_name}: {len(results)} candidates")

        return results


# ──────────────────────── ECN Scraper ────────────────────────

class ECNScraper(BaseScraper):
    """
    Scrapes the official Election Commission Nepal results page.
    URL: result.election.gov.np (ASP.NET WebForms, server-rendered)
    """
    name = "ecn"
    display_name = "Election Commission Nepal"
    enabled = False  # Disabled: returns party-level only, no candidate data
    timeout = 30

    URL = "https://result.election.gov.np"

    def run(self):
        results = []
        errors = []

        try:
            resp = self.fetch(self.URL, timeout=30)
            html = resp.text
            logger.info(f"[ECN] Fetched {len(html)} bytes")

            soup = BeautifulSoup(html, "html.parser")

            # The ECN page shows party-level summary (winners/leads)
            # It may also have links to constituency-level detail pages
            # For now we log the party standings
            text = soup.get_text(separator="\n")

            # Try to find any constituency-level result links
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                if "Constituency" in href or "constituency" in href:
                    logger.info(f"[ECN] Found constituency link: {href}")

            # ECN data is party-level only (winners/leads), not candidate vote counts
            # We can't create candidate-level Result rows from it
            # But we log it for monitoring

        except Exception as e:
            error_msg = f"ECN: {str(e)[:100]}"
            errors.append(error_msg)
            logger.error(f"[ECN] {error_msg}")

        return results, errors


# ──────────────────── Scraper Registry ────────────────────

ALL_SCRAPERS = [EkantipurScraper, OnlineKhabarScraper, ECNScraper]


# ──────────────────────── Coordinator ────────────────────────

class ScraperCoordinator:
    """
    Runs all scrapers, reconciles data, updates database.
    Higher vote count = more recent data = wins.
    """

    def __init__(self, app=None):
        self.app = app
        self.scrapers = [cls() for cls in ALL_SCRAPERS if cls.enabled]
        self.last_run = None
        self.last_results_count = 0
        self.last_errors = []
        self.source_status = {}
        self.total_runs = 0
        self.total_updates = 0

    def run_all(self):
        start = time.time()
        all_results = []
        all_errors = []
        self.total_runs += 1

        logger.info(f"[Run #{self.total_runs}] Starting scrape from {len(self.scrapers)} sources in parallel...")

        # Run all scrapers in parallel for maximum speed
        # Each thread needs Flask app context for DB queries
        from flask import current_app
        app = current_app._get_current_object()

        def run_scraper_safe(scraper):
            try:
                with app.app_context():
                    return scraper, scraper.run(), None
            except Exception as e:
                return scraper, ([], []), e

        with ThreadPoolExecutor(max_workers=len(self.scrapers)) as executor:
            futures = {executor.submit(run_scraper_safe, s): s for s in self.scrapers}
            for future in as_completed(futures, timeout=90):
                try:
                    scraper, (scraper_results, scraper_errors), exc = future.result(timeout=60)
                    if exc:
                        raise exc
                    all_results.extend(scraper_results)
                    all_errors.extend(scraper_errors)

                    self.source_status[scraper.name] = {
                        "display_name": scraper.display_name,
                        "results_count": len(scraper_results),
                        "errors": scraper_errors[:3],
                        "status": "ok" if scraper_results else ("error" if scraper_errors else "no_data"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                except Exception as e:
                    scraper = futures[future]
                    error_msg = f"{scraper.display_name}: {str(e)[:100]}"
                    all_errors.append(error_msg)
                    logger.error(f"[Coordinator] {error_msg}")
                    logger.error(traceback.format_exc())
                    self.source_status[scraper.name] = {
                        "display_name": scraper.display_name,
                        "results_count": 0,
                        "errors": [error_msg],
                        "status": "error",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

        elapsed = time.time() - start

        updated = 0
        if all_results:
            updated = self._reconcile_and_update(all_results)

        self._log_run(updated, all_errors, elapsed)

        self.last_run = datetime.now(timezone.utc)
        self.last_results_count = updated
        self.last_errors = all_errors[:10]
        self.total_updates += updated

        logger.info(f"[Run #{self.total_runs}] Done in {elapsed:.1f}s: "
                     f"{len(all_results)} raw, {updated} updated, {len(all_errors)} errors")

        return updated

    def _reconcile_and_update(self, raw_results):
        reconciled = {}
        for r in raw_results:
            candidate = r.get("candidate", "").strip()
            constituency = r.get("constituency", "").strip()
            votes = r.get("votes", 0)

            if not candidate or votes <= 0:
                continue

            key = (candidate.lower(), constituency.lower() if constituency else "")
            if key not in reconciled or votes > reconciled[key]["votes"]:
                reconciled[key] = r

        logger.info(f"Reconciled {len(raw_results)} raw -> {len(reconciled)} unique")

        updated_count = 0
        for result in reconciled.values():
            try:
                count = self._update_db_result(result)
                updated_count += count
            except Exception as e:
                logger.error(f"DB update error for {result.get('candidate')}: {e}")
                db.session.rollback()

        if updated_count > 0:
            try:
                db.session.commit()
                try:
                    from app import invalidate_cache
                    invalidate_cache()
                except ImportError:
                    pass
                logger.info(f"Committed {updated_count} updates, cache invalidated")
            except Exception as e:
                logger.error(f"Commit failed: {e}")
                db.session.rollback()

        return updated_count

    def _update_db_result(self, result):
        candidate_name = result["candidate"].strip()
        votes = result["votes"]
        party_short = result.get("party_short")
        constituency_name = result.get("constituency", "").strip()
        source = result.get("source", "")

        # Find party
        party = None
        if party_short:
            party = Party.query.filter_by(short_name=party_short).first()
        if not party and result.get("party_name"):
            party = Party.query.filter(
                Party.name.ilike(f"%{result['party_name']}%")
            ).first()

        # Find constituency
        constituency = None
        if constituency_name:
            constituency = Constituency.query.filter(
                Constituency.name.ilike(f"%{constituency_name}%")
            ).first()
            if not constituency:
                match = re.match(r'(.+?)\s*[-\u2013]\s*(\d+)', constituency_name)
                if match:
                    district_part = match.group(1).strip()
                    number = int(match.group(2))
                    district = District.query.filter(
                        District.name.ilike(f"%{district_part}%")
                    ).first()
                    if district:
                        constituency = Constituency.query.filter_by(
                            district_id=district.id,
                            number=number,
                        ).first()

        if not constituency:
            return 0

        # Find candidate by name (works for English names from Ekantipur)
        candidate = Candidate.query.filter_by(name=candidate_name).first()
        if not candidate:
            candidate = Candidate.query.filter(
                Candidate.name.ilike(f"%{candidate_name}%")
            ).first()

        # Cross-source matching: if candidate not found by name (e.g. Nepali name
        # from OnlineKhabar), match by constituency + party instead
        if not candidate and party and source == "onlinekhabar":
            existing = Result.query.filter_by(
                constituency_id=constituency.id,
                party_id=party.id,
            ).first()
            if existing:
                if votes > existing.votes:
                    existing.votes = votes
                    existing.updated_at = datetime.now(timezone.utc)
                    return 1
                return 0
            # No existing result for this constituency+party - skip
            # (don't create candidates with Nepali names)
            return 0

        if not candidate:
            candidate = Candidate(
                name=candidate_name,
                party_id=party.id if party else None,
            )
            db.session.add(candidate)
            db.session.flush()

        # Update or create result
        existing_result = Result.query.filter_by(
            constituency_id=constituency.id,
            candidate_id=candidate.id,
        ).first()

        is_elected = result.get("is_elected", False)
        changed = 0

        if existing_result:
            if votes > existing_result.votes:
                existing_result.votes = votes
                existing_result.party_id = party.id if party else existing_result.party_id
                existing_result.updated_at = datetime.now(timezone.utc)
                changed = 1
            # Mark winner if officially elected
            if is_elected and not existing_result.is_winner:
                existing_result.is_winner = True
                existing_result.updated_at = datetime.now(timezone.utc)
                changed = 1
        else:
            new_result = Result(
                constituency_id=constituency.id,
                candidate_id=candidate.id,
                party_id=party.id if party else None,
                votes=votes,
                is_winner=is_elected,
            )
            db.session.add(new_result)
            if constituency.status == "pending":
                constituency.status = "counting"
            changed = 1

        # Update constituency status to declared if a winner exists
        if is_elected and constituency.status != "declared":
            constituency.status = "declared"
            logger.info(f"WINNER DECLARED: {candidate_name} in {constituency_name}")
            # Reset is_winner for other candidates in same constituency
            Result.query.filter(
                Result.constituency_id == constituency.id,
                Result.candidate_id != candidate.id,
            ).update({"is_winner": False})
            changed = 1

        return changed

    def _log_run(self, updated, errors, elapsed):
        try:
            sources = ", ".join(
                f"{s['display_name']}:{s['results_count']}"
                for s in self.source_status.values()
            )
            log = ScraperLog(
                source="multi-source",
                status="success" if updated > 0 else ("partial" if errors else "no_data"),
                message=f"{updated} updates in {elapsed:.1f}s | {sources}",
                records_updated=updated,
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to log scrape run: {e}")
            db.session.rollback()

    def get_status(self):
        return {
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_results_count": self.last_results_count,
            "total_runs": self.total_runs,
            "total_updates": self.total_updates,
            "errors": self.last_errors,
            "sources": self.source_status,
            "scraper_count": len(self.scrapers),
        }


# ──────────────────────── Global Entry Points ────────────────────────

coordinator = None


def get_coordinator(app=None):
    global coordinator
    if coordinator is None:
        coordinator = ScraperCoordinator(app)
    return coordinator


def run_scraper():
    """Main entry point called by the scheduler."""
    c = get_coordinator()
    try:
        return c.run_all()
    except Exception as e:
        logger.error(f"Scraper coordinator failed: {e}")
        logger.error(traceback.format_exc())
        return 0
