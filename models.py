from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()


class Province(db.Model):
    """7 provinces of Nepal"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    name_np = db.Column(db.String(200))  # Nepali name
    districts = db.relationship("District", backref="province", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "name_np": self.name_np,
        }


class District(db.Model):
    """77 districts of Nepal"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_np = db.Column(db.String(200))
    province_id = db.Column(db.Integer, db.ForeignKey("province.id"), nullable=False)
    constituencies = db.relationship("Constituency", backref="district", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "name_np": self.name_np,
            "province_id": self.province_id,
            "province_name": self.province.name if self.province else None,
        }


class Constituency(db.Model):
    """Federal constituencies (275 HoR seats)"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    number = db.Column(db.Integer, nullable=False)  # e.g., constituency 1, 2...
    district_id = db.Column(db.Integer, db.ForeignKey("district.id"), nullable=False)
    total_voters = db.Column(db.Integer, default=0)
    votes_counted = db.Column(db.Integer, default=0)
    status = db.Column(db.String(30), default="pending")  # pending, counting, declared
    results = db.relationship("Result", backref="constituency", lazy=True)

    def to_dict(self):
        # Compute votes_counted dynamically from actual results
        computed_votes = sum(r.votes for r in self.results) if self.results else self.votes_counted
        return {
            "id": self.id,
            "name": self.name,
            "number": self.number,
            "district_id": self.district_id,
            "district_name": self.district.name if self.district else None,
            "province_name": self.district.province.name if self.district and self.district.province else None,
            "total_voters": self.total_voters,
            "votes_counted": computed_votes,
            "status": self.status,
        }


class Party(db.Model):
    """Political parties"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    short_name = db.Column(db.String(30))
    short_name_np = db.Column(db.String(50))
    name_np = db.Column(db.String(300))
    color = db.Column(db.String(7), default="#666666")  # hex color for charts
    logo_url = db.Column(db.String(500))
    results = db.relationship("Result", backref="party", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "short_name_np": self.short_name_np,
            "name_np": self.name_np,
            "color": self.color,
            "logo_url": self.logo_url,
        }


class Candidate(db.Model):
    """Individual candidates"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_np = db.Column(db.String(300))
    party_id = db.Column(db.Integer, db.ForeignKey("party.id"), nullable=True)
    photo_url = db.Column(db.String(500))
    party = db.relationship("Party", backref="candidates")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "name_np": self.name_np,
            "party_id": self.party_id,
            "party_name": self.party.name if self.party else "Independent",
            "party_short": self.party.short_name if self.party else "IND",
            "photo_url": self.photo_url,
        }


class Result(db.Model):
    """Vote counts per candidate per constituency"""
    id = db.Column(db.Integer, primary_key=True)
    constituency_id = db.Column(db.Integer, db.ForeignKey("constituency.id"), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidate.id"), nullable=False)
    party_id = db.Column(db.Integer, db.ForeignKey("party.id"), nullable=True)
    votes = db.Column(db.Integer, default=0)
    is_winner = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))
    candidate = db.relationship("Candidate", backref="results")

    __table_args__ = (
        db.UniqueConstraint("constituency_id", "candidate_id", name="uq_constituency_candidate"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "constituency_id": self.constituency_id,
            "constituency_name": self.constituency.name if self.constituency else None,
            "candidate_id": self.candidate_id,
            "candidate_name": self.candidate.name if self.candidate else None,
            "party_id": self.party_id,
            "party_name": self.party.name if self.party else "Independent",
            "party_short": self.party.short_name if self.party else "IND",
            "party_color": self.party.color if self.party else "#666666",
            "votes": self.votes,
            "is_winner": self.is_winner,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ScraperLog(db.Model):
    """Track scraping activity"""
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    source = db.Column(db.String(200))
    status = db.Column(db.String(20))  # success, error
    message = db.Column(db.Text)
    records_updated = db.Column(db.Integer, default=0)
