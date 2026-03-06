"""Seed data for Nepal's provinces, districts, constituencies, and major parties."""

from models import db, Province, District, Constituency, Party

PROVINCES = [
    {"id": 1, "name": "Koshi", "name_np": "कोशी प्रदेश"},
    {"id": 2, "name": "Madhesh", "name_np": "मधेश प्रदेश"},
    {"id": 3, "name": "Bagmati", "name_np": "बागमती प्रदेश"},
    {"id": 4, "name": "Gandaki", "name_np": "गण्डकी प्रदेश"},
    {"id": 5, "name": "Lumbini", "name_np": "लुम्बिनी प्रदेश"},
    {"id": 6, "name": "Karnali", "name_np": "कर्णाली प्रदेश"},
    {"id": 7, "name": "Sudurpashchim", "name_np": "सुदूरपश्चिम प्रदेश"},
]

# All 77 districts grouped by province
DISTRICTS = {
    1: [  # Koshi
        "Taplejung", "Panchthar", "Ilam", "Jhapa", "Morang",
        "Sunsari", "Dhankuta", "Terhathum", "Sankhuwasabha",
        "Bhojpur", "Solukhumbu", "Okhaldhunga", "Khotang", "Udayapur",
    ],
    2: [  # Madhesh
        "Saptari", "Siraha", "Dhanusha", "Mahottari", "Sarlahi",
        "Rautahat", "Bara", "Parsa",
    ],
    3: [  # Bagmati
        "Dolakha", "Sindhupalchok", "Rasuwa", "Dhading", "Nuwakot",
        "Kathmandu", "Bhaktapur", "Lalitpur", "Kavrepalanchok",
        "Ramechhap", "Sindhuli", "Makwanpur", "Chitwan",
    ],
    4: [  # Gandaki
        "Gorkha", "Lamjung", "Tanahu", "Syangja", "Kaski",
        "Manang", "Mustang", "Myagdi", "Parbat", "Baglung", "Nawalparasi East",
    ],
    5: [  # Lumbini
        "Nawalparasi West", "Rupandehi", "Kapilvastu", "Palpa",
        "Arghakhanchi", "Gulmi", "Pyuthan", "Rolpa", "Eastern Rukum",
        "Dang", "Banke", "Bardiya",
    ],
    6: [  # Karnali
        "Western Rukum", "Salyan", "Dolpa", "Humla", "Jumla",
        "Kalikot", "Mugu", "Surkhet", "Dailekh", "Jajarkot",
    ],
    7: [  # Sudurpashchim
        "Bajura", "Bajhang", "Achham", "Doti", "Kailali",
        "Kanchanpur", "Dadeldhura", "Baitadi", "Darchula",
    ],
}

# Number of federal HoR constituencies per district (165 FPTP seats)
CONSTITUENCY_COUNTS = {
    # Province 1 - Koshi (29 seats)
    "Taplejung": 1, "Panchthar": 2, "Ilam": 2, "Jhapa": 5, "Morang": 6,
    "Sunsari": 3, "Dhankuta": 1, "Terhathum": 1, "Sankhuwasabha": 1,
    "Bhojpur": 1, "Solukhumbu": 1, "Okhaldhunga": 1, "Khotang": 2, "Udayapur": 2,
    # Province 2 - Madhesh (32 seats)
    "Saptari": 3, "Siraha": 4, "Dhanusha": 4, "Mahottari": 4, "Sarlahi": 4,
    "Rautahat": 4, "Bara": 4, "Parsa": 5,
    # Province 3 - Bagmati (34 seats)
    "Dolakha": 1, "Sindhupalchok": 2, "Rasuwa": 1, "Dhading": 2, "Nuwakot": 2,
    "Kathmandu": 10, "Bhaktapur": 2, "Lalitpur": 3, "Kavrepalanchok": 3,
    "Ramechhap": 1, "Sindhuli": 2, "Makwanpur": 2, "Chitwan": 3,
    # Province 4 - Gandaki (18 seats)
    "Gorkha": 2, "Lamjung": 1, "Tanahu": 2, "Syangja": 2, "Kaski": 3,
    "Manang": 0, "Mustang": 1, "Myagdi": 1, "Parbat": 1, "Baglung": 2, "Nawalparasi East": 2,
    # Province 5 - Lumbini (24 seats)
    "Nawalparasi West": 2, "Rupandehi": 5, "Kapilvastu": 3, "Palpa": 1,
    "Arghakhanchi": 1, "Gulmi": 1, "Pyuthan": 1, "Rolpa": 1, "Eastern Rukum": 1,
    "Dang": 3, "Banke": 3, "Bardiya": 2,
    # Province 6 - Karnali (12 seats)
    "Western Rukum": 1, "Salyan": 1, "Dolpa": 1, "Humla": 1, "Jumla": 1,
    "Kalikot": 1, "Mugu": 1, "Surkhet": 2, "Dailekh": 2, "Jajarkot": 1,
    # Province 7 - Sudurpashchim (17 seats)
    "Bajura": 1, "Bajhang": 2, "Achham": 2, "Doti": 2, "Kailali": 5,
    "Kanchanpur": 2, "Dadeldhura": 1, "Baitadi": 1, "Darchula": 1,
}

# Major political parties of Nepal
PARTIES = [
    {"name": "Nepali Congress", "short_name": "NC", "short_name_np": "कांग्रेस", "name_np": "नेपाली काँग्रेस", "color": "#0066CC", "logo_url": "/static/logos/nc.svg"},
    {"name": "CPN (UML)", "short_name": "UML", "short_name_np": "एमाले", "name_np": "नेकपा (एमाले)", "color": "#FF0000", "logo_url": "/static/logos/uml.svg"},
    {"name": "CPN (Maoist Centre)", "short_name": "MC", "short_name_np": "माओवादी", "name_np": "नेकपा (माओवादी केन्द्र)", "color": "#CC0000", "logo_url": "/static/logos/mc.svg"},
    {"name": "Rastriya Swatantra Party", "short_name": "RSP", "short_name_np": "रास्वपा", "name_np": "राष्ट्रिय स्वतन्त्र पार्टी", "color": "#FF6600", "logo_url": "/static/logos/rsp.svg"},
    {"name": "Rastriya Prajatantra Party", "short_name": "RPP", "short_name_np": "राप्रपा", "name_np": "राष्ट्रिय प्रजातन्त्र पार्टी", "color": "#FFD700", "logo_url": "/static/logos/rpp.svg"},
    {"name": "Janata Samajbadi Party", "short_name": "JSP", "short_name_np": "जसपा", "name_np": "जनता समाजवादी पार्टी", "color": "#008000", "logo_url": "/static/logos/jsp.svg"},
    {"name": "CPN (Unified Socialist)", "short_name": "US", "short_name_np": "एकीकृत समाजवादी", "name_np": "नेकपा (एकीकृत समाजवादी)", "color": "#990000", "logo_url": "/static/logos/us.svg"},
    {"name": "Loktantrik Samajbadi Party", "short_name": "LSP", "short_name_np": "लोसपा", "name_np": "लोकतान्त्रिक समाजवादी पार्टी", "color": "#336699", "logo_url": "/static/logos/lsp.svg"},
    {"name": "Janamat Party", "short_name": "JP", "short_name_np": "जनमत", "name_np": "जनमत पार्टी", "color": "#9933FF", "logo_url": "/static/logos/jp.svg"},
    {"name": "Nagarik Unmukti Party", "short_name": "NUP", "short_name_np": "नाउपा", "name_np": "नागरिक उन्मुक्ति पार्टी", "color": "#00CC99", "logo_url": "/static/logos/nup.svg"},
    {"name": "Nepal Workers Peasants Party", "short_name": "NWPP", "short_name_np": "नेमकिपा", "name_np": "नेपाल मजदुर किसान पार्टी", "color": "#663300", "logo_url": "/static/logos/nwpp.svg"},
    {"name": "Ujaylo Nepal Party", "short_name": "UNP", "short_name_np": "उजनेपा", "name_np": "उज्यालो नेपाल पार्टी", "color": "#FFA500", "logo_url": "/static/logos/unp.svg"},
    {"name": "Shram Sanskriti Party", "short_name": "SSP", "short_name_np": "श्रमसंपा", "name_np": "श्रम संस्कृति पार्टी", "color": "#8B4513", "logo_url": "/static/logos/ssp.svg"},
    {"name": "Pragatishil Loktantrik Party", "short_name": "PLP", "short_name_np": "प्रलोपा", "name_np": "प्रगतिशील लोकतान्त्रिक पार्टी", "color": "#4B0082", "logo_url": "/static/logos/plp.svg"},
    {"name": "Nepal Sadbhavana Party", "short_name": "NSP", "short_name_np": "नेसपा", "name_np": "नेपाल सद्भावना पार्टी", "color": "#228B22", "logo_url": "/static/logos/nsp.svg"},
    {"name": "Rastriya Janamorcha", "short_name": "RJM", "short_name_np": "राजमो", "name_np": "राष्ट्रिय जनमोर्चा", "color": "#B22222", "logo_url": "/static/logos/rjm.svg"},
    {"name": "Independent", "short_name": "IND", "short_name_np": "स्वतन्त्र", "name_np": "स्वतन्त्र", "color": "#999999", "logo_url": "/static/logos/ind.svg"},
]


def seed_database():
    """Populate database with Nepal election geography and parties."""
    # Provinces
    for p in PROVINCES:
        province = Province.query.get(p["id"])
        if not province:
            province = Province(**p)
            db.session.add(province)
    db.session.flush()

    # Districts
    district_map = {}
    for province_id, district_names in DISTRICTS.items():
        for d_name in district_names:
            existing = District.query.filter_by(name=d_name, province_id=province_id).first()
            if not existing:
                district = District(name=d_name, province_id=province_id)
                db.session.add(district)
                db.session.flush()
                district_map[d_name] = district.id
            else:
                district_map[d_name] = existing.id

    # Constituencies
    for d_name, count in CONSTITUENCY_COUNTS.items():
        district_id = district_map.get(d_name)
        if not district_id:
            continue
        for num in range(1, count + 1):
            c_name = f"{d_name}-{num}"
            existing = Constituency.query.filter_by(name=c_name, district_id=district_id).first()
            if not existing:
                c = Constituency(
                    name=c_name,
                    number=num,
                    district_id=district_id,
                    total_voters=0,
                    status="pending",
                )
                db.session.add(c)

    # Parties
    for p in PARTIES:
        existing = Party.query.filter_by(name=p["name"]).first()
        if not existing:
            party = Party(**p)
            db.session.add(party)
        else:
            # Update fields that may have changed
            for key, val in p.items():
                if key != "name" and hasattr(existing, key):
                    setattr(existing, key, val)

    db.session.commit()
    print(f"Seeded: {Province.query.count()} provinces, "
          f"{District.query.count()} districts, "
          f"{Constituency.query.count()} constituencies, "
          f"{Party.query.count()} parties")
