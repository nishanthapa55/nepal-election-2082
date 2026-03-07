from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
from functools import wraps
from config import Config
from models import db, Province, District, Constituency, Party, Candidate, Result, ScraperLog
from seed_data import seed_database
from sqlalchemy import func
from datetime import datetime, timezone
import logging
import time
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────── Simple In-Memory Cache ───────────────────────────

_cache = {}
_CACHE_TTL = 5  # seconds — serves cached data for 5s, then refreshes

def cached(key, ttl=None):
    """Decorator to cache JSON API responses in memory.
    On election day with thousands of users, this means the DB
    is only queried once every few seconds, not on every request."""
    if ttl is None:
        ttl = _CACHE_TTL
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            now = time.time()
            cache_key = key() if callable(key) else key
            entry = _cache.get(cache_key)
            if entry and (now - entry["ts"]) < ttl:
                resp = jsonify(entry["data"])
                resp.headers["X-Cache"] = "HIT"
                resp.headers["X-Cache-Age"] = f"{now - entry['ts']:.1f}s"
                return resp
            result = f(*args, **kwargs)
            # Store the raw data before jsonify
            _cache[cache_key] = {"data": result, "ts": now}
            resp = jsonify(result)
            resp.headers["X-Cache"] = "MISS"
            return resp
        return wrapper
    return decorator

def invalidate_cache(pattern=None):
    """Clear cache entries. Called after admin updates."""
    if pattern is None:
        _cache.clear()
    else:
        keys_to_del = [k for k in _cache if pattern in k]
        for k in keys_to_del:
            del _cache[k]


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        # Seed data if empty
        if Province.query.count() == 0:
            seed_database()

    return app


app = create_app()


# ─────────────────────────── Auth Helpers ───────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────── Performance Middleware ───────────────────────────

@app.before_request
def before_request():
    request._start_time = time.time()

@app.after_request
def after_request(response):
    if hasattr(request, '_start_time'):
        elapsed = (time.time() - request._start_time) * 1000
        response.headers['X-Response-Time'] = f'{elapsed:.1f}ms'
    return response


# ─────────────────────────── Frontend Routes ───────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/constituency/<int:constituency_id>")
def constituency_detail(constituency_id):
    # Constituency details are shown via modal on the main page
    return redirect(url_for("index"))


# ─────────────────────────── API Routes ───────────────────────────

@app.route("/api/summary")
@cached("summary")
def api_summary():
    """Overall election summary stats, enhanced with OnlineKhabar API data."""
    total_constituencies = Constituency.query.count()
    declared = Constituency.query.filter_by(status="declared").count()
    counting = Constituency.query.filter_by(status="counting").count()
    pending = Constituency.query.filter_by(status="pending").count()

    # Party-wise seats won
    party_seats = (
        db.session.query(
            Party.id,
            Party.name,
            Party.short_name,
            Party.short_name_np,
            Party.name_np,
            Party.color,
            func.count(Result.id).label("seats_won"),
        )
        .join(Result, Result.party_id == Party.id)
        .filter(Result.is_winner == True)
        .group_by(Party.id)
        .order_by(func.count(Result.id).desc())
        .all()
    )

    # Party-wise total votes
    party_votes = (
        db.session.query(
            Party.id,
            Party.name,
            Party.short_name,
            Party.short_name_np,
            Party.name_np,
            Party.color,
            func.sum(Result.votes).label("total_votes"),
        )
        .join(Result, Result.party_id == Party.id)
        .group_by(Party.id)
        .order_by(func.sum(Result.votes).desc())
        .all()
    )

    # Leading candidates (most votes in each counting constituency)
    total_votes_cast = db.session.query(func.sum(Result.votes)).scalar() or 0

    # Get fast OnlineKhabar API party data if available
    okh_party_summary = None
    try:
        from okh_cache import get_okh_party_cache, get_okh_cache_timestamp
        okh_data = get_okh_party_cache()
        if okh_data:
            okh_party_summary = {
                "parties": okh_data,
                "timestamp": get_okh_cache_timestamp(),
            }
    except Exception as e:
        logger.error(f"Failed to get OKH party cache: {e}")

    return {
        "total_constituencies": total_constituencies,
        "declared": declared,
        "counting": counting,
        "pending": pending,
        "total_votes_cast": total_votes_cast,
        "party_seats": [
            {"id": p.id, "name": p.name, "short_name": p.short_name, "short_name_np": p.short_name_np, "name_np": p.name_np, "color": p.color, "seats": p.seats_won}
            for p in party_seats
        ],
        "party_votes": [
            {"id": p.id, "name": p.name, "short_name": p.short_name, "short_name_np": p.short_name_np, "name_np": p.name_np, "color": p.color, "total_votes": p.total_votes}
            for p in party_votes
        ],
        "okh_party_summary": okh_party_summary,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


@app.route("/api/health")
def api_health():
    """Diagnostic endpoint to check what's running."""
    import sys
    import traceback
    info = {
        "python_version": sys.version,
        "status": "ok",
    }
    try:
        info["constituency_count"] = Constituency.query.count()
        info["result_count"] = Result.query.count()
        info["declared"] = Constituency.query.filter_by(status="declared").count()
        info["counting"] = Constituency.query.filter_by(status="counting").count()
    except Exception as e:
        info["db_error"] = str(e)
    try:
        from okh_cache import get_okh_party_cache, get_okh_cache_timestamp
        cache = get_okh_party_cache()
        info["okh_cache_size"] = len(cache) if cache else 0
        info["okh_timestamp"] = get_okh_cache_timestamp()
    except Exception as e:
        info["okh_error"] = traceback.format_exc()
    return jsonify(info)


@app.route("/api/provinces")
def api_provinces():
    provinces = Province.query.all()
    return jsonify([p.to_dict() for p in provinces])


@app.route("/api/districts")
def api_districts():
    province_id = request.args.get("province_id", type=int)
    query = District.query
    if province_id:
        query = query.filter_by(province_id=province_id)
    districts = query.order_by(District.name).all()
    return jsonify([d.to_dict() for d in districts])


@app.route("/api/constituencies")
def api_constituencies():
    district_id = request.args.get("district_id", type=int)
    province_id = request.args.get("province_id", type=int)
    status = request.args.get("status")
    search = request.args.get("search")

    query = Constituency.query.join(District)

    if district_id:
        query = query.filter(Constituency.district_id == district_id)
    if province_id:
        query = query.filter(District.province_id == province_id)
    if status:
        query = query.filter(Constituency.status == status)
    if search:
        query = query.filter(Constituency.name.ilike(f"%{search}%"))

    constituencies = query.order_by(Constituency.name).all()
    return jsonify([c.to_dict() for c in constituencies])


@app.route("/api/constituency/<int:constituency_id>")
def api_constituency_detail(constituency_id):
    constituency = Constituency.query.get_or_404(constituency_id)
    results = (
        Result.query
        .filter_by(constituency_id=constituency_id)
        .order_by(Result.votes.desc())
        .all()
    )
    return jsonify({
        "constituency": constituency.to_dict(),
        "results": [r.to_dict() for r in results],
    })


@app.route("/api/parties")
def api_parties():
    parties = Party.query.order_by(Party.name).all()
    return jsonify([p.to_dict() for p in parties])


@app.route("/api/party/<int:party_id>/results")
def api_party_results(party_id):
    results = (
        Result.query
        .filter_by(party_id=party_id)
        .order_by(Result.votes.desc())
        .all()
    )
    party = Party.query.get_or_404(party_id)
    return jsonify({
        "party": party.to_dict(),
        "total_votes": sum(r.votes for r in results),
        "seats_won": sum(1 for r in results if r.is_winner),
        "constituencies": len(results),
        "results": [r.to_dict() for r in results],
    })


@app.route("/api/leading")
@cached("leading")
def api_leading():
    """Get the leading candidate in each constituency (one per constituency)."""
    # Subquery to get max votes per constituency
    subq = (
        db.session.query(
            Result.constituency_id,
            func.max(Result.votes).label("max_votes"),
        )
        .group_by(Result.constituency_id)
        .subquery()
    )

    leaders = (
        db.session.query(Result)
        .join(subq, (Result.constituency_id == subq.c.constituency_id) & (Result.votes == subq.c.max_votes))
        .filter(Result.votes > 0)
        .all()
    )

    # Deduplicate: one leader per constituency (pick first if tied)
    seen_constituencies = set()
    data = []
    for r in leaders:
        if r.constituency_id in seen_constituencies:
            continue
        seen_constituencies.add(r.constituency_id)
        c = Constituency.query.get(r.constituency_id)
        data.append({
            "constituency": c.to_dict() if c else {},
            "leading_candidate": r.candidate.name if r.candidate else None,
            "leading_party": r.party.short_name if r.party else "IND",
            "leading_party_color": r.party.color if r.party else "#999",
            "votes": r.votes,
            "is_winner": r.is_winner,
        })

    return data


@app.route("/api/map-data")
def api_map_data():
    """Data optimized for the map view — one entry per district with leading party."""
    districts = District.query.all()
    data = []

    for district in districts:
        constituencies = Constituency.query.filter_by(district_id=district.id).all()
        c_ids = [c.id for c in constituencies]

        if not c_ids:
            continue

        # Get leading party in this district (most seats or most votes)
        party_votes = (
            db.session.query(
                Party.short_name,
                Party.color,
                func.sum(Result.votes).label("total"),
            )
            .join(Result, Result.party_id == Party.id)
            .filter(Result.constituency_id.in_(c_ids))
            .group_by(Party.id)
            .order_by(func.sum(Result.votes).desc())
            .first()
        )

        total_counted = sum(c.votes_counted for c in constituencies)
        total_voters = sum(c.total_voters for c in constituencies)

        data.append({
            "district": district.name,
            "province_id": district.province_id,
            "constituencies": len(constituencies),
            "declared": sum(1 for c in constituencies if c.status == "declared"),
            "counting": sum(1 for c in constituencies if c.status == "counting"),
            "leading_party": party_votes.short_name if party_votes else None,
            "leading_color": party_votes.color if party_votes else "#cccccc",
            "total_votes": party_votes.total if party_votes else 0,
            "total_counted": total_counted,
            "total_voters": total_voters,
        })

    return jsonify(data)


# ─────────────────────────── Admin Routes ───────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == Config.ADMIN_USERNAME and password == Config.ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Invalid credentials", "error")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("index"))


@app.route("/admin")
@login_required
def admin_dashboard():
    return render_template("admin/dashboard.html")


@app.route("/admin/results", methods=["GET"])
@login_required
def admin_results():
    constituencies = Constituency.query.join(District).order_by(Constituency.name).all()
    parties = Party.query.order_by(Party.name).all()
    return render_template("admin/results.html", constituencies=constituencies, parties=parties)


@app.route("/admin/api/update-result", methods=["POST"])
@login_required
def admin_update_result():
    """Admin endpoint to manually update election results."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    constituency_id = data.get("constituency_id")
    candidate_name = data.get("candidate_name")
    party_id = data.get("party_id")
    votes = data.get("votes", 0)

    if not constituency_id or not candidate_name:
        return jsonify({"error": "constituency_id and candidate_name required"}), 400

    constituency = Constituency.query.get(constituency_id)
    if not constituency:
        return jsonify({"error": "Constituency not found"}), 404

    # Find or create candidate
    candidate = Candidate.query.filter_by(name=candidate_name).first()
    if not candidate:
        candidate = Candidate(
            name=candidate_name,
            party_id=party_id,
        )
        db.session.add(candidate)
        db.session.flush()

    # Update or create result
    result = Result.query.filter_by(
        constituency_id=constituency_id,
        candidate_id=candidate.id,
    ).first()

    if result:
        result.votes = votes
        result.party_id = party_id
        result.updated_at = datetime.now(timezone.utc)
    else:
        result = Result(
            constituency_id=constituency_id,
            candidate_id=candidate.id,
            party_id=party_id,
            votes=votes,
        )
        db.session.add(result)

    db.session.commit()
    invalidate_cache()  # Clear cache after result update
    return jsonify({"success": True, "result": result.to_dict()})


@app.route("/admin/api/update-constituency-status", methods=["POST"])
@login_required
def admin_update_constituency_status():
    data = request.get_json()
    constituency_id = data.get("constituency_id")
    status = data.get("status")

    if status not in ("pending", "counting", "declared"):
        return jsonify({"error": "Invalid status"}), 400

    constituency = Constituency.query.get_or_404(constituency_id)
    constituency.status = status

    # If declared, mark the top vote-getter as winner
    if status == "declared":
        results = Result.query.filter_by(constituency_id=constituency_id).order_by(Result.votes.desc()).all()
        for i, r in enumerate(results):
            r.is_winner = (i == 0 and r.votes > 0)

    db.session.commit()
    invalidate_cache()  # Clear cache after status change
    return jsonify({"success": True})


@app.route("/admin/api/bulk-update", methods=["POST"])
@login_required
def admin_bulk_update():
    """Bulk update results for a constituency."""
    data = request.get_json()
    constituency_id = data.get("constituency_id")
    results_data = data.get("results", [])

    constituency = Constituency.query.get_or_404(constituency_id)
    updated = 0

    for r_data in results_data:
        candidate_name = r_data.get("candidate_name")
        party_id = r_data.get("party_id")
        votes = r_data.get("votes", 0)

        if not candidate_name:
            continue

        candidate = Candidate.query.filter_by(name=candidate_name).first()
        if not candidate:
            candidate = Candidate(name=candidate_name, party_id=party_id)
            db.session.add(candidate)
            db.session.flush()

        result = Result.query.filter_by(
            constituency_id=constituency_id,
            candidate_id=candidate.id,
        ).first()

        if result:
            result.votes = votes
            result.party_id = party_id
            result.updated_at = datetime.now(timezone.utc)
        else:
            result = Result(
                constituency_id=constituency_id,
                candidate_id=candidate.id,
                party_id=party_id,
                votes=votes,
            )
            db.session.add(result)
        updated += 1

    # Update total votes counted
    total = db.session.query(func.sum(Result.votes)).filter_by(constituency_id=constituency_id).scalar() or 0
    constituency.votes_counted = total

    db.session.commit()
    invalidate_cache()  # Clear cache after bulk update
    return jsonify({"success": True, "updated": updated})


@app.route("/admin/api/scraper-logs")
@login_required
def admin_scraper_logs():
    logs = ScraperLog.query.order_by(ScraperLog.timestamp.desc()).limit(50).all()
    return jsonify([{
        "id": l.id,
        "timestamp": l.timestamp.isoformat() if l.timestamp else None,
        "source": l.source,
        "status": l.status,
        "message": l.message,
        "records_updated": l.records_updated,
    } for l in logs])


# ─────────────────────────── Scraper Status & Control  ───────────────────────────

@app.route("/api/scraper-status")
def api_scraper_status():
    """Public endpoint showing scraper health and source status."""
    from scraper import get_coordinator
    coord = get_coordinator(app)
    status = coord.get_status()
    # Add recent log entries
    recent_logs = ScraperLog.query.order_by(ScraperLog.timestamp.desc()).limit(5).all()
    status["recent_logs"] = [{
        "timestamp": l.timestamp.isoformat() if l.timestamp else None,
        "status": l.status,
        "message": l.message,
        "records_updated": l.records_updated,
    } for l in recent_logs]
    return jsonify(status)


@app.route("/admin/api/trigger-scrape", methods=["POST"])
@login_required
def admin_trigger_scrape():
    """Manually trigger a scrape cycle."""
    from scraper import get_coordinator
    coord = get_coordinator(app)
    updated = coord.run_all()
    invalidate_cache()
    return jsonify({"success": True, "records_updated": updated, "status": coord.get_status()})


# ─────────────────────────── Scheduler ───────────────────────────

_scheduler = None

def start_scheduler(app):
    """Start background scrapers on a schedule."""
    global _scheduler
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        _scheduler = BackgroundScheduler(daemon=True)

        def scrape_job():
            with app.app_context():
                from scraper import run_scraper
                run_scraper()

        def fast_scrape_job():
            with app.app_context():
                from scraper import run_fast_scraper
                run_fast_scraper()

        # Full scrape (Ekantipur + OnlineKhabar HTML) every 15s
        _scheduler.add_job(
            scrape_job,
            "interval",
            seconds=Config.SCRAPE_INTERVAL_SECONDS,
            id="multi_source_scraper",
            max_instances=1,
            next_run_time=datetime.now(timezone.utc),  # run immediately on start
        )

        # Fast scrape (OnlineKhabar API — party summary) every 5s
        _scheduler.add_job(
            fast_scrape_job,
            "interval",
            seconds=5,
            id="fast_party_scraper",
            max_instances=1,
            next_run_time=datetime.now(timezone.utc),
        )

        _scheduler.start()
        logger.info(f"Full scraper scheduled every {Config.SCRAPE_INTERVAL_SECONDS}s")
        logger.info(f"Fast party scraper scheduled every 5s (OnlineKhabar API)")
    except Exception as e:
        logger.warning(f"Scheduler not started: {e}")


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")


# ─────────────────────────── Start Scheduler ───────────────────────────
# Start scraper for BOTH gunicorn (production) and direct python (dev)
# Gunicorn never runs __main__, so we start it here at module level.

if Config.SCRAPE_ENABLED:
    start_scheduler(app)


# ─────────────────────────── Main ───────────────────────────

if __name__ == "__main__":
    is_production = os.environ.get("RENDER") or os.environ.get("PRODUCTION")

    print("\n" + "=" * 60)
    print("  Nepal Election Live Results 2026")
    print("  Dashboard:  http://127.0.0.1:5000")
    print("  Admin:      http://127.0.0.1:5000/admin")
    print("  Scraper:    " + ("ACTIVE (full: {}s, fast: 5s)".format(Config.SCRAPE_INTERVAL_SECONDS) if Config.SCRAPE_ENABLED else "DISABLED"))
    print("  Sources:    OnlineKhabar API, Ekantipur, OnlineKhabar HTML")
    print("=" * 60 + "\n")

    app.run(
        debug=not is_production,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        use_reloader=False,
    )
