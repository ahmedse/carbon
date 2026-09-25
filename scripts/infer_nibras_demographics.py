"""Test-only fill of blank Employee.gender and Employee.nationality on nibras_dev.

Infers from the English name. Never overwrites a value already stored.
Rows with no given name are left blank. Nationality stays blank when the
name does not match a pattern. Restore with scripts/restore-nibras-dev-snapshot.sh.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from mdm.models import ReferenceValue
from people.models import Employee

FEMALE = {
    "maria", "reena", "manal", "maryam", "hayat", "manatalla", "christine",
    "fatemeh", "nicole", "nelyn", "fatima", "aisha", "sarah", "sara", "noor",
    "nour", "huda", "layla", "lina", "dina", "rania", "amira", "hala", "mona",
    "nada", "salma", "yasmin", "zainab", "khadija", "amina", "hanan", "samira",
}

# Whole-name tokens. First matching nationality wins.
PATTERNS: list[tuple[str, set[str]]] = [
    ("PHL", {
        "racela", "suerte", "castillo", "matugas", "salva", "mendoza", "padilla",
        "zamora", "gonzales", "brananola", "lanuzo", "delima", "roque", "millones",
        "angway", "opsima", "junio", "costanilla", "estrada", "saguid", "pineda",
        "suizo", "alcantara", "vanguardia", "orteg", "saldivar", "colobong",
        "beligen", "datulayta", "paragatos", "gamutan", "sasil", "arevalo",
        "virgillio", "virgilio", "teodoro", "charlito", "reymundo", "jefrey",
        "aldrine", "geronimo", "diony", "rolly", "anecito", "olever", "romeo",
        "benedict", "mclawry", "bilagot", "nelyn", "nicole",
    }),
    ("LKA", {"mudiyanselage", "chandrasiri", "gedara", "padmakumara", "tharaka", "niroshana"}),
    ("NPL", {
        "tamang", "bahadur", "ghising", "rasali", "thapa", "thapachhettri",
        "muktan", "baniya", "khimding", "bisundev", "lama",
    }),
    ("BGD", {
        "hossain", "pramanik", "miah", "sikder", "mondal", "sarker", "uddin",
        "kashem", "azizurrahman", "haque", "swapon", "shohidul", "firozul",
        "abul", "hashem",
    }),
    ("PAK", {
        "khan", "iqbal", "bhatti", "shehzad", "mujawar", "mehmood", "qadeer",
        "siddique", "peeran", "pasha", "shaikh", "sheikh", "gul", "aslam",
        "kakar", "mushtaq", "ansari", "shafique", "irfan", "farook", "azeemullah",
    }),
    ("IND", {
        "singh", "kumar", "sharma", "reddy", "nair", "pillai", "gupta", "rao",
        "patel", "krishnan", "gopalakrishnan", "vellayan", "kunapareddy",
        "suthar", "tiwari", "sankla", "nirmal", "jaisankar", "ganta", "gadiraju",
        "fernandez", "varkey", "pappachan", "viswambaran", "radhakrishnan",
        "subramanium", "madrasi", "elango", "sasikumar", "naduparambil",
        "lonappan", "macwan", "mecwan", "lobo", "souza", "naidu", "negi",
        "pathania", "sisodiya", "panchal", "bhuvanendran", "shetty", "kurme",
        "jeganathan", "madasamy", "devadass", "karuver", "karnaver", "nalluri",
        "yerabapu", "gajendra", "lalitkumar", "maniyath", "koringayan",
        "chillayimadathil", "kuzhumbil", "kunnumpurath", "panikkassery",
        "puthoor", "kottappuram", "kokkot", "kalathodika", "saidalavi",
        "ayyappakutty", "purakkal", "kanjirathingal", "vaniyapurackal",
        "parambil", "sasthamkudam", "peddabuddi", "rajadurai", "densingh",
        "shivgovind", "hitesh", "pramod", "pradeep", "sajan", "suresh",
        "rajesh", "rajendra", "surendra", "anand", "arun", "mano", "manoj",
        "dipak", "dipakkumar", "nitheesh", "bestin", "jebin", "bala",
        "chandru", "partha", "harsh", "leon", "shery", "shidin", "baneesh",
        "bajan", "mitesHkumar", "aman", "joyston", "aboobacker", "saji",
        "dileep", "georgekutty", "jayakrishnan", "jayaprakash", "akash",
        "rathi", "vishal", "sridhar", "deep", "balwinder", "hardial",
        "avtar", "gurnam", "ranjit", "harkamal", "vikash", "jitendra",
        "ravindar", "srinivas", "jagadish", "mahesh", "gangaram", "vipin",
        "arjun", "velumadhavan", "shanmugam", "gaurav", "pachin", "sreedharan",
        "kattil", "hinosh", "subodh", "hari", "rabindra", "mahato", "baidhar",
        "das", "amarjinder", "santokh", "pardeep", "kehar", "mithlesh",
        "kolkkattil", "neelala", "kuzhikkanam", "kurishingal", "balasubramaniam",
        "marimuthu", "anoop", "animon", "chandy", "rahiman", "malique",
    }),
    ("SYR", {"zakout", "alkhawam", "khawam"}),
    ("SAU", {"alyami", "alabdaljabar"}),
    ("EGY", {
        "elsayed", "soliman", "ramadan", "mostafa", "abdelhalim", "abdelreda",
        "younes", "gayed", "mikhaeil", "shenouda", "elsabea", "farrag",
        "korkar", "mobarak", "moursy", "belal", "zorkany", "elbasha",
        "hamada", "selim", "tawfik", "gadelsaeed", "koko", "rezk", "abdelnasser",
        "bahloul", "ismaiel", "abdelrehim",         "shaaban", "miloudi", "abdelbari", "abdelrahman", "houga", "moustafa",
        "ismail", "baraka", "oshi", "diko", "jafarian", "adbelrady", "wahbi",
    }),
    ("KWT", {
        "alhajri", "alajmi", "alfares", "alfarhan", "aljarba", "aljassim",
        "alsafran", "alanezi", "albuloushi", "alshoshan", "alissa", "aloudah",
        "alsallal", "alkhammash", "almahmoud", "alfrih", "alzaid", "alhazaaa",
        "alali", "alabd", "aljabbar", "alnajem", "aljassem", "bahman",
        "alkhadhari", "alnaser", "alqallaf", "alabdul",
    }),
    ("OTH", {
        "oppong", "boateng", "adjei", "agyei", "quaye", "sarpong", "anokye",
        "danso", "ayiku", "akpablie", "nwaichi", "ihemekwala", "onyenania",
        "ewulonu", "igwe", "nwachukwu", "iroanya", "ogunsiji", "adegoke",
        "dogosira", "ngwobia", "manauba", "mashamba", "goren", "njuguna",
        "ngethe", "waithaka", "kinuthia", "moracha", "mwau", "kamara", "dogo",
        "adanmado", "jima", "melese", "habetamu", "tavana", "abyat", "babiker",
        "dotse", "freifer", "tristram", "rusel", "kayvan", "chigozie",
        "friday", "kalu", "jonah", "enock", "novwe", "godwin", "emmanuel",
        "isaac", "henry", "obed", "andy", "ogadinma", "udak", "uduak",
        "awedeou", "samuel", "john", "patrick", "kwame", "ernest", "oscar",
        "leku", "loguya", "andrews", "rodrigue", "abu", "evans", "musa",
        "hillary", "oluwatosin", "eric", "justice", "anderson", "francis",
        "julius", "dennis", "david", "bismark", "kofi", "fred", "chisom",
        "philip", "aloysius", "kibwana", "jacob", "redouane", "amine",
    }),
]


def tokens(emp: Employee) -> set[str]:
    raw = f"{emp.name_en_given} {emp.name_en_family} {emp.full_name}".lower()
    raw = raw.replace("-", " ").replace(".", " ").replace("'", "")
    return {t for t in raw.split() if t}


def nationality_code(emp: Employee) -> str:
    words = tokens(emp)
    for code, markers in PATTERNS:
        if words & markers:
            return code
    return ""


def main() -> None:
    gender = {
        rv.code: rv
        for rv in ReferenceValue.objects.filter(reference_set__name="gender")
    }
    nationality = {
        rv.code: rv
        for rv in ReferenceValue.objects.filter(reference_set__name="nationality")
    }
    male = gender["male"]
    female = gender["female"]

    gender_n = 0
    nation_n = 0
    for emp in Employee.objects.all().iterator():
        fields = []
        given = (emp.name_en_given or "").strip().lower()
        if emp.gender_id is None and given:
            emp.gender = female if given in FEMALE else male
            fields.append("gender")
            gender_n += 1
        if emp.nationality_id is None:
            code = nationality_code(emp)
            if code and code in nationality:
                emp.nationality = nationality[code]
                fields.append("nationality")
                nation_n += 1
        if fields:
            emp.save(update_fields=fields)

    blank_g = Employee.objects.filter(gender__isnull=True).count()
    blank_n = Employee.objects.filter(nationality__isnull=True).count()
    print(f"gender set {gender_n}, still blank {blank_g}")
    print(f"nationality set {nation_n}, still blank {blank_n}")


if __name__ == "__main__":
    main()
