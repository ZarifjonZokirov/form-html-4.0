import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_from_directory


BASE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = Path("/tmp") if os.getenv("VERCEL") else BASE_DIR
DATABASE_PATH = RUNTIME_DIR / "candidates.db"
JSON_PATH = RUNTIME_DIR / "candidates.json"
FIRESTORE_URL = os.getenv(
    "FIRESTORE_URL",
    "",
)

app = Flask(__name__, static_folder=str(BASE_DIR))


def init_database():
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                job_position TEXT NOT NULL,
                region TEXT NOT NULL,
                exact_address TEXT NOT NULL,
                phone1 TEXT NOT NULL,
                phone2 TEXT,
                gender TEXT,
                dob TEXT,
                past_experience TEXT,
                father_name TEXT,
                education_level TEXT,
                graduation_year TEXT,
                target_branch TEXT,
                status TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                branch TEXT,
                education TEXT,
                grad_year TEXT,
                experience_years TEXT,
                marital_status TEXT
            )
            """
        )
        existing_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(candidates)")
        }
        for column in ("father_name", "education_level", "graduation_year", "target_branch"):
            if column not in existing_columns:
                connection.execute(f"ALTER TABLE candidates ADD COLUMN {column} TEXT")


def save_candidate(candidate):
    columns = (
        "full_name", "job_position", "region", "exact_address", "phone1",
        "phone2", "gender", "dob", "past_experience", "father_name",
        "education_level", "graduation_year", "target_branch", "status",
        "submitted_at", "branch", "education", "grad_year", "experience_years",
        "marital_status",
    )
    values = tuple(candidate.get(column, "") for column in columns)
    placeholders = ", ".join("?" for _ in columns)

    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.execute(
            f"INSERT INTO candidates ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )

    candidates = []
    if JSON_PATH.exists():
        try:
            candidates = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            candidates = []
    candidates.append(candidate)
    JSON_PATH.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def firestore_payload(candidate):
    fields = {
        "fullName": candidate.get("full_name", ""),
        "fatherName": candidate.get("father_name", ""),
        "gender": candidate.get("gender", ""),
        "dob": candidate.get("dob", ""),
        "maritalStatus": candidate.get("marital_status", ""),
        "educationLevel": candidate.get("education_level", ""),
        "graduationYear": candidate.get("graduation_year", ""),
        "region": candidate.get("region", ""),
        "exactAddress": candidate.get("exact_address", ""),
        "targetBranch": candidate.get("target_branch", ""),
        "jobPosition": candidate.get("job_position", ""),
        "phone1": candidate.get("phone1", ""),
        "phone2": candidate.get("phone2", ""),
        "gender": candidate.get("gender", ""),
        "dob": candidate.get("dob", ""),
        "pastExperience": candidate.get("past_experience", ""),
        "status": candidate.get("status", "Yangi nomzod"),
        "submittedAt": candidate.get("submitted_at", ""),
    }
    return {"fields": {key: {"stringValue": value} for key, value in fields.items()}}


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.post("/api/candidates")
def create_candidate():
    if not FIRESTORE_URL:
        return jsonify({"error": "FIRESTORE_URL sozlanmagan"}), 500

    data = request.get_json(silent=True) or {}
    required_fields = (
        "full_name", "father_name", "gender", "dob", "marital_status",
        "education_level", "graduation_year", "region", "exact_address",
        "target_branch", "job_position", "phone1",
    )
    missing_fields = [field for field in required_fields if not str(data.get(field, "")).strip()]
    if missing_fields:
        return jsonify({"error": "Majburiy maydonlar to'ldirilmagan", "fields": missing_fields}), 400

    candidate = {
        "full_name": str(data.get("full_name", "")).strip(),
        "job_position": str(data.get("job_position", "")).strip(),
        "region": str(data.get("region", "")).strip(),
        "exact_address": str(data.get("exact_address", "")).strip(),
        "phone1": str(data.get("phone1", "")).strip(),
        "phone2": str(data.get("phone2", "")).strip(),
        "gender": str(data.get("gender", "")).strip(),
        "dob": str(data.get("dob", "")).strip(),
        "father_name": str(data.get("father_name", "")).strip(),
        "education_level": str(data.get("education_level", "")).strip(),
        "graduation_year": str(data.get("graduation_year", "")).strip(),
        "target_branch": str(data.get("target_branch", "")).strip(),
        "past_experience": str(data.get("past_experience", "")).strip(),
        "status": "Yangi nomzod",
        "submitted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "branch": str(data.get("branch", "")).strip(),
        "education": str(data.get("education", "")).strip(),
        "grad_year": str(data.get("grad_year", "")).strip(),
        "experience_years": str(data.get("experience_years", "")).strip(),
        "marital_status": str(data.get("marital_status", "")).strip(),
    }

    try:
        response = requests.post(
            FIRESTORE_URL,
            json=firestore_payload(candidate),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        save_candidate(candidate)
    except requests.RequestException as error:
        app.logger.exception("Firestore yuborish xatosi: %s", error)
        return jsonify({"error": "HRMS tizimiga yuborib bo'lmadi"}), 502
    except (OSError, sqlite3.Error) as error:
        app.logger.exception("Lokal saqlash xatosi: %s", error)
        app.logger.warning("Firestore saqlandi, lokal nusxa yozilmadi: %s", error)

    return jsonify({"message": "Nomzod muvaffaqiyatli qabul qilindi"}), 201


init_database()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)