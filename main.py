import json
import os
import re
import sqlite3
import time
from contextlib import asynccontextmanager
from typing import List, Optional, Union

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AliasChoices, BaseModel, Field

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "networking.db")
PROFILES_PATH = os.getenv("PROFILES_PATH", "profiles.json")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

GOAL_RECIPROCITY = {
    "job": ["hire"],
    "hire": ["job"],
    "mentee": ["mentor"],
    "mentor": ["mentee"],
    "cofounder": ["cofounder"],
    "exchange": ["exchange"],
}

GOAL_ALIASES = {
    "job": "job",
    "найти работу": "job",
    "ищу работу": "job",
    "жұмыс табу": "job",
    "hire": "hire",
    "нанять": "hire",
    "нанять специалиста": "hire",
    "маман жалдау": "hire",
    "mentee": "mentee",
    "найти ментора": "mentee",
    "ментор табу": "mentee",
    "mentor": "mentor",
    "стать ментором": "mentor",
    "ментор болу": "mentor",
    "cofounder": "cofounder",
    "найти кофаундера": "cofounder",
    "кофаундер табу": "cofounder",
    "exchange": "exchange",
    "обмен опытом": "exchange",
    "тәжірибе алмасу": "exchange",
}

GOAL_LABELS_RU = {
    "job": "Найти работу",
    "hire": "Нанять",
    "mentee": "Найти ментора",
    "mentor": "Стать ментором",
    "cofounder": "Найти кофаундера",
    "exchange": "Обмен опытом",
}

CITY_ALIASES = {
    "алматы": "almaty",
    "almaty": "almaty",
    "астана": "astana",
    "astana": "astana",
    "шымкент": "shymkent",
    "shymkent": "shymkent",
    "караганда": "karaganda",
    "қарағанды": "karaganda",
    "karaganda": "karaganda",
    "актобе": "aktobe",
    "ақтөбе": "aktobe",
    "aktobe": "aktobe",
}

TECH_ROLES = {
    "Backend", "Frontend", "Mobile", "Data Scientist", "ML Engineer",
    "DevOps", "QA", "Tech Lead", "Data Engineer", "Security"
}


def normalize_goal(raw_goal: str) -> str:
    cleaned = raw_goal.strip().lower()
    return GOAL_ALIASES.get(cleaned, "exchange")


def normalize_city(raw_city: str) -> str:
    cleaned = (raw_city or "").strip().lower()
    return CITY_ALIASES.get(cleaned, cleaned)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            stack TEXT NOT NULL,
            years INTEGER NOT NULL,
            interests TEXT NOT NULL,
            about TEXT NOT NULL,
            goal TEXT NOT NULL,
            city TEXT NOT NULL,
            langs TEXT NOT NULL,
            org TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("SELECT COUNT(*) FROM profiles")
    if cur.fetchone()[0] == 0 and os.path.exists(PROFILES_PATH):
        with open(PROFILES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for p in data:
            yrs = p.get("years", p.get("experience_years", 1))
            cur.execute(
                """
                INSERT INTO profiles (id, name, role, stack, years, interests, about, goal, city, langs, org)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    p["id"],
                    p["name"],
                    p["role"],
                    json.dumps(p["stack"], ensure_ascii=False),
                    yrs,
                    json.dumps(p["interests"], ensure_ascii=False),
                    p.get("about", ""),
                    normalize_goal(p["goal"]),
                    p.get("city", "Almaty"),
                    json.dumps(p.get("langs", ["ru", "en"]), ensure_ascii=False),
                    p.get("org", "IT-компания"),
                ),
            )
    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Qazaq IT Smart Networking API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserProfileInput(BaseModel):
    name: str = Field(default="Участник")
    role: str = Field(default="Backend")
    stack: Union[List[str], str] = Field(default_factory=list)
    years: int = Field(
        default=2,
        ge=0,
        le=50,
        validation_alias=AliasChoices("years", "experience_years", "experience"),
    )
    interests: Union[List[str], str] = Field(default_factory=list)
    about: str = Field(default="")
    goal: str = Field(default="exchange")
    city: str = Field(default="")
    langs: List[str] = Field(default_factory=lambda: ["ru"])
    language: str = Field(default="ru", validation_alias=AliasChoices("language", "lang"))
    limit: int = Field(default=5, ge=1, le=30)
    exclude_ids: Optional[List[int]] = Field(default_factory=list)


class FeedbackInput(BaseModel):
    candidate_id: int = Field(validation_alias=AliasChoices("candidate_id", "id"))
    status: str = Field(default="no")


def normalize_tags(raw: Union[List[str], str]) -> List[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return [x.strip() for x in str(raw).split(",") if x.strip()]


def tokenize(text: str) -> set:
    return set(re.findall(r"[a-zа-яёәіңғүұқөһ0-9+#.-]{3,}", text.lower()))


def compute_score(user: dict, cand: dict) -> tuple[int, dict]:
    u_stack = {s.lower() for s in user["stack"]}
    c_stack = {s.lower() for s in cand["stack"]}
    stack_overlap = u_stack & c_stack

    u_int = {i.lower() for i in user["interests"]}
    c_int = {i.lower() for i in cand["interests"]}
    int_overlap = u_int & c_int

    u_tokens = tokenize(f"{user['role']} {user['about']}")
    c_tokens = tokenize(f"{cand['role']} {cand['about']}")
    text_overlap = u_tokens & c_tokens

    score = 52
    score += min(24, len(stack_overlap) * 8)
    score += min(14, len(int_overlap) * 6)
    score += min(8, len(text_overlap) * 2)

    goal = user["goal"]
    if goal == "mentee" and cand["years"] > user["years"]:
        score += 8
    elif goal == "mentor" and user["years"] > cand["years"]:
        score += 8
    elif goal == "cofounder":
        if (user["role"] in TECH_ROLES) != (cand["role"] in TECH_ROLES):
            score += 9
        elif user["role"] != cand["role"]:
            score += 5

    u_city = normalize_city(user.get("city", ""))
    c_city = normalize_city(cand.get("city", ""))
    if u_city and u_city == c_city:
        score += 3

    if set(user.get("langs", [])) & set(cand.get("langs", [])):
        score += 2

    return min(99, score), {
        "shared_stack": list(stack_overlap),
        "shared_interests": list(int_overlap),
    }


def fallback_copy(user: dict, cand: dict, meta: dict, lang: str) -> tuple[str, str]:
    shared_list = meta["shared_stack"] or meta["shared_interests"] or cand["stack"][:2]
    shared = ", ".join(shared_list) if shared_list else cand["role"]
    first_name = cand["name"].split()[0]

    if lang in ("kk", "kz"):
        exp = (
            f"Мақсаттарыңыз өзара сәйкес, ортақ бағыттар: {shared}. "
            f"{cand['role']} ретінде тәжірибесі ({cand['years']} ж., {cand['org']}) сізге пайдалы болады."
        )
        ice = f"Сәлем, {first_name}! {shared} бойынша тәжірибе алмасып, танысуға қалай қарайсыз?"
    elif lang == "en":
        exp = (
            f"Mutual goal match with shared focus on {shared}. "
            f"Their background as {cand['role']} ({cand['years']} yrs, {cand['org']}) fits your request."
        )
        ice = f"Hi {first_name}! Noticed we both work with {shared} — would love to connect for 5 minutes."
    else:
        exp = (
            f"Взаимное совпадение по целям и пересечение по темам: {shared}. "
            f"Опыт кандидата на роли {cand['role']} ({cand['years']} л., {cand['org']}) закрывает ваш запрос."
        )
        ice = f"Привет, {first_name}! Увидел пересечение по {shared} — давай познакомимся и обсудим задачи?"
    return exp, ice


def clean_json_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def enrich_with_gemini(user: dict, top_items: list, lang: str) -> list:
    if not GEMINI_API_KEY or not top_items:
        for item in top_items:
            exp, ice = fallback_copy(user, item["profile"], item["meta"], lang)
            item["explanation"] = exp
            item["icebreaker"] = ice
        return top_items

    lang_label = {"ru": "русском", "kk": "казахском", "kz": "казахском", "en": "английском"}.get(lang, "русском")
    llm_batch = top_items[:5]
    compact_candidates = [
        {
            "id": item["profile"]["id"],
            "name": item["profile"]["name"],
            "role": item["profile"]["role"],
            "stack": item["profile"]["stack"],
            "years": item["profile"]["years"],
            "interests": item["profile"]["interests"],
            "goal": GOAL_LABELS_RU.get(item["profile"]["goal"], item["profile"]["goal"]),
            "org": item["profile"]["org"],
            "about": item["profile"]["about"],
        }
        for item in llm_batch
    ]

    user_for_llm = {
        **user,
        "goal": GOAL_LABELS_RU.get(user["goal"], user["goal"]),
    }

    prompt = (
        f"Ты AI-ассистент умного нетворкинга на IT-конференции в Казахстане. Отвечай строго на {lang_label} языке.\n"
        f"Анкета участника: {json.dumps(user_for_llm, ensure_ascii=False)}\n"
        f"Кандидаты: {json.dumps(compact_candidates, ensure_ascii=False)}\n\n"
        f"Верни JSON-массив из {len(llm_batch)} объектов строго в формате:\n"
        '[{"id": <int>, "explanation": "<1-2 емких предложения, почему им выгодно познакомиться>", '
        '"icebreaker": "<короткая живая первая фраза для начала диалога>"}]'
    )

    url = f"[https://generativelanguage.googleapis.com/v1beta/models/](https://generativelanguage.googleapis.com/v1beta/models/){GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(clean_json_text(raw_text))
            by_id = {int(row["id"]): row for row in parsed}

            for item in top_items:
                cid = item["profile"]["id"]
                if cid in by_id and by_id[cid].get("explanation"):
                    item["explanation"] = by_id[cid]["explanation"]
                    item["icebreaker"] = by_id[cid].get("icebreaker", "")
                else:
                    exp, ice = fallback_copy(user, item["profile"], item["meta"], lang)
                    item["explanation"] = exp
                    item["icebreaker"] = ice
            return top_items
    except Exception:
        for item in top_items:
            exp, ice = fallback_copy(user, item["profile"], item["meta"], lang)
            item["explanation"] = exp
            item["icebreaker"] = ice
        return top_items


def row_to_dict(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "role": r["role"],
        "stack": json.loads(r["stack"]),
        "years": r["years"],
        "experience_years": r["years"],
        "interests": json.loads(r["interests"]),
        "about": r["about"],
        "goal": r["goal"],
        "city": r["city"],
        "langs": json.loads(r["langs"]),
        "org": r["org"],
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "gemini_configured": bool(GEMINI_API_KEY)}


@app.get("/api/profiles")
def list_profiles():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM profiles ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]


@app.post("/api/recommend")
async def recommend(payload: UserProfileInput):
    t0 = time.perf_counter()
    lang = payload.language.lower() if payload.language.lower() in ("ru", "kk", "kz", "en") else "ru"
    canonical_goal = normalize_goal(payload.goal)

    user_data = {
        "name": payload.name.strip() or "Участник",
        "role": payload.role.strip(),
        "stack": normalize_tags(payload.stack),
        "years": payload.years,
        "interests": normalize_tags(payload.interests),
        "about": payload.about.strip(),
        "goal": canonical_goal,
        "city": payload.city.strip(),
        "langs": payload.langs,
    }

    target_goals = GOAL_RECIPROCITY.get(canonical_goal, [canonical_goal])
    excluded = set(payload.exclude_ids or [])

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM profiles")
    total_profiles = cur.fetchone()[0]

    placeholders = ",".join("?" for _ in target_goals)
    cur.execute(f"SELECT * FROM profiles WHERE goal IN ({placeholders})", target_goals)
    rows = cur.fetchall()

    scored = []
    for r in rows:
        if r["id"] in excluded:
            continue
        cand = row_to_dict(r)
        score, meta = compute_score(user_data, cand)
        scored.append({"profile": cand, "match_score": score, "meta": meta})

    if len(scored) < payload.limit:
        cur.execute("SELECT * FROM profiles")
        extra_rows = cur.fetchall()
        seen_ids = {item["profile"]["id"] for item in scored} | excluded
        for r in extra_rows:
            if r["id"] in seen_ids:
                continue
            cand = row_to_dict(r)
            score, meta = compute_score(user_data, cand)
            scored.append({"profile": cand, "match_score": max(42, score - 15), "meta": meta})

    conn.close()

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    selected = scored[: payload.limit]
    selected = await enrich_with_gemini(user_data, selected, lang)

    def format_card(item: dict) -> dict:
        return {
            **item["profile"],
            "match_score": item["match_score"],
            "explanation": item["explanation"],
            "icebreaker": item["icebreaker"],
        }

    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    return {
        "elapsed_ms": elapsed_ms,
        "total_profiles": total_profiles,
        "recommendations": [format_card(x) for x in selected],
    }


@app.post("/api/feedback")
def save_feedback(payload: FeedbackInput):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO feedback (candidate_id, status) VALUES (?, ?)",
        (payload.candidate_id, payload.status),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    idx_file = os.path.join("static", "index.html")
    if os.path.exists(idx_file):
        return FileResponse(idx_file)
    return {"status": "ok", "message": "Backend is running. Place index.html into static/"}