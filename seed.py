import json
import random

random.seed(2026)

ROLES = [
    "Backend", "Frontend", "Mobile", "Data Scientist", "ML Engineer",
    "DevOps", "QA", "Product Manager", "UX/UI Designer", "Tech Lead",
    "Recruiter", "CTO/Founder", "Data Engineer", "Security"
]

ROLE_STACKS = {
    "Backend": ["Python", "Java", "Go", "Node.js", "PostgreSQL", "Kafka"],
    "Frontend": ["React", "TypeScript", "Vue", "Next.js", "CSS"],
    "Mobile": ["Kotlin", "Swift", "Flutter", "React Native"],
    "Data Scientist": ["Python", "SQL", "PyTorch", "Pandas"],
    "ML Engineer": ["Python", "PyTorch", "LLM", "MLOps", "Docker"],
    "DevOps": ["Docker", "Kubernetes", "AWS", "Terraform", "Linux"],
    "QA": ["Selenium", "Python", "Postman", "Java"],
    "Product Manager": ["SQL", "Jira", "Figma", "Analytics"],
    "UX/UI Designer": ["Figma", "CSS", "Analytics"],
    "Tech Lead": ["Java", "Go", "Kubernetes", "Python", "Kafka"],
    "Recruiter": ["Python", "Java", "React", "Kotlin", "DevOps"],
    "CTO/Founder": ["Python", "Go", "LLM", "AWS", "React"],
    "Data Engineer": ["SQL", "Kafka", "Python", "Spark", "AWS"],
    "Security": ["Linux", "Python", "Pentest", "AWS"]
}

ALL_STACK = list({s for items in ROLE_STACKS.values() for s in items})

INTERESTS = [
    "AgroTech", "Smart City", "Kazakh NLP", "AI", "FinTech", "Web3",
    "GameDev", "Cloud", "Cybersecurity", "EdTech", "Startups",
    "Open Source", "Data", "GovTech", "E-commerce", "IoT"
]

MALE_FIRST = ["Айдос", "Данияр", "Ерлан", "Тимур", "Нурлан", "Расул", "Бауыржан", "Арман", "Максим", "Санжар", "Иван", "Ержан"]
MALE_LAST = ["Сейтказин", "Омаров", "Ким", "Нуртазин", "Петров", "Касымов", "Жумабаев", "Искаков", "Тлеуов", "Абенов", "Волков", "Беков"]

FEMALE_FIRST = ["Мадина", "Аружан", "Алия", "Диана", "Асель", "Карина", "Жанар", "Динара", "Айгерим", "Елена", "Камила", "Томирис"]
FEMALE_LAST = ["Ахметова", "Соколова", "Смагулова", "Нурланова", "Омарова", "Касымова", "Жумабаева", "Искакова", "Бекова", "Ким"]

CITIES = ["Алматы", "Алматы", "Астана", "Астана", "Шымкент", "Қарағанды", "Ақтөбе", "Remote"]
ORGS = ["Astana Hub", "Банк / FinTech", "Продуктовая компания", "Аутсорс", "Стартап", "Университет", "GovTech"]
LANG_SETS = [["kk", "ru", "en"], ["ru", "en"], ["kk", "ru"], ["kk", "en"]]

ABOUT_POOL = [
    "Люблю строить продукты, которые решают реальные задачи в Казахстане.",
    "Interested in scalable systems and clean architecture.",
    "Ищу интересные проекты и сильную команду.",
    "Веду комьюнити, выступаю на митапах.",
    "Хочу делиться опытом и расти вместе с сообществом.",
    "Работаю над стартапом в сфере финтех и ИИ.",
    "Pet-проекты, open source и развитие инженерной культуры."
]

GOALS = ["job", "hire", "mentee", "mentor", "cofounder", "exchange"]


def pick_goal(role: str, years: int) -> str:
    x = random.random()
    if role == "Recruiter":
        return "hire" if x < 0.85 else "exchange"
    if role == "CTO/Founder":
        return "hire" if x < 0.35 else ("cofounder" if x < 0.7 else ("mentor" if x < 0.85 else "exchange"))
    if role == "Tech Lead":
        return "mentor" if x < 0.45 else ("hire" if x < 0.7 else "exchange")
    if years <= 2:
        return "job" if x < 0.55 else ("mentee" if x < 0.85 else "exchange")
    if years >= 7:
        return "mentor" if x < 0.4 else ("hire" if x < 0.6 else ("exchange" if x < 0.8 else "cofounder"))
    return random.choice(GOALS)


def generate_profiles(total: int = 120):
    profiles = []
    used_names = set()

    for idx in range(1, total + 1):
        while True:
            if random.choice([True, False]):
                full_name = f"{random.choice(MALE_FIRST)} {random.choice(MALE_LAST)}"
            else:
                full_name = f"{random.choice(FEMALE_FIRST)} {random.choice(FEMALE_LAST)}"
            if full_name not in used_names:
                used_names.add(full_name)
                break

        role = ROLES[(idx - 1) % len(ROLES)]
        if role == "Recruiter":
            years = random.randint(2, 9)
        elif role in ("Tech Lead", "CTO/Founder"):
            years = random.randint(6, 14)
        else:
            years = random.randint(0, 9)

        base_stack = ROLE_STACKS[role]
        extra = random.sample(ALL_STACK, 2)
        stack = list(dict.fromkeys(random.sample(base_stack, min(3, len(base_stack))) + extra))[:4]
        interests = random.sample(INTERESTS, random.randint(2, 3))
        goal = pick_goal(role, years)

        profiles.append({
            "id": idx,
            "name": full_name,
            "role": role,
            "stack": stack,
            "years": years,
            "experience_years": years,
            "interests": interests,
            "about": random.choice(ABOUT_POOL),
            "goal": goal,
            "city": random.choice(CITIES),
            "langs": random.choice(LANG_SETS),
            "org": random.choice(ORGS),
        })

    with open("profiles.json", "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)
    print(f"Сгенерировано {len(profiles)} анкет в profiles.json")


if __name__ == "__main__":
    generate_profiles(120)