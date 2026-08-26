"""Tests for AIMaturityView — GET /carbon-api/ai/pulse/maturity/."""
import pytest

BASE = "/carbon-api/ai/pulse"
MATURITY_URL = f"{BASE}/maturity/"

EXPECTED_TOP_LEVEL_KEYS = {
    "maturity_score",
    "expertise_level",
    "expertise_description",
    "skills",
    "knowledge",
    "performance",
    "complexity",
    "learning_velocity",
    "domain_expertise",
}
VALID_EXPERTISE_LEVELS = {"Novice", "Developing", "Competent", "Proficient", "Expert"}


@pytest.fixture
def superuser(db):
    from accounts.models import User
    u = User.objects.create_user(username="maturity-admin", password="secret123")
    u.is_superuser = True
    u.is_staff = True
    u.save()
    return u


@pytest.fixture
def regular_user(db):
    from accounts.models import User
    return User.objects.create_user(username="maturity-user", password="secret123")


@pytest.fixture
def admin_client(api_client, get_token_for_user, superuser):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(superuser)}")
    return api_client


@pytest.fixture
def user_client(api_client, get_token_for_user, regular_user):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(regular_user)}")
    return api_client


@pytest.mark.django_db
def test_maturity_requires_auth(api_client):
    """Unauthenticated request must be rejected with 401."""
    assert api_client.get(MATURITY_URL).status_code == 401


@pytest.mark.django_db
def test_maturity_requires_admin(user_client):
    """Authenticated non-admin must be rejected with 403."""
    assert user_client.get(MATURITY_URL).status_code == 403


@pytest.mark.django_db
def test_maturity_superuser_returns_200(admin_client):
    """Superuser must get 200."""
    assert admin_client.get(MATURITY_URL).status_code == 200


@pytest.mark.django_db
def test_maturity_response_has_all_top_level_keys(admin_client):
    """Response body must contain all 9 expected top-level keys."""
    data = admin_client.get(MATURITY_URL).json()
    missing = EXPECTED_TOP_LEVEL_KEYS - data.keys()
    assert not missing, f"Missing keys in response: {missing}"


@pytest.mark.django_db
def test_maturity_empty_db_is_novice_with_zero_score(admin_client):
    """Empty database → maturity_score=0.0, expertise_level='Novice', all counts=0."""
    data = admin_client.get(MATURITY_URL).json()
    assert data["maturity_score"] == 0.0
    assert data["expertise_level"] == "Novice"
    assert data["skills"]["total"] == 0
    assert data["skills"]["promoted"] == 0
    assert data["skills"]["draft"] == 0
    assert data["knowledge"]["entities"] == 0
    assert data["knowledge"]["nodes"] == 0
    assert data["knowledge"]["edges"] == 0
    assert data["performance"]["total_feedback"] == 0
    assert data["complexity"]["total_conversations"] == 0
    assert data["complexity"]["total_plans"] == 0
    assert data["domain_expertise"] == []


@pytest.mark.django_db
def test_maturity_skills_sub_keys_and_types(admin_client):
    """skills dict contains exactly {total, promoted, draft, promotion_rate} with correct types."""
    skills = admin_client.get(MATURITY_URL).json()["skills"]
    assert set(skills.keys()) == {"total", "promoted", "draft", "promotion_rate"}
    assert isinstance(skills["total"], int)
    assert isinstance(skills["promoted"], int)
    assert isinstance(skills["draft"], int)
    assert isinstance(skills["promotion_rate"], (int, float))


@pytest.mark.django_db
def test_maturity_knowledge_sub_keys_and_types(admin_client):
    """knowledge dict contains exactly {entities, nodes, edges, graph_density}."""
    knowledge = admin_client.get(MATURITY_URL).json()["knowledge"]
    assert set(knowledge.keys()) == {"entities", "nodes", "edges", "graph_density"}
    assert isinstance(knowledge["entities"], int)
    assert isinstance(knowledge["graph_density"], (int, float))


@pytest.mark.django_db
def test_maturity_learning_velocity_sub_keys(admin_client):
    """learning_velocity dict contains exactly 4 expected keys."""
    lv = admin_client.get(MATURITY_URL).json()["learning_velocity"]
    assert set(lv.keys()) == {"skills_acquired", "skills_promoted", "entities_added", "nodes_added"}


@pytest.mark.django_db
def test_maturity_expertise_level_is_one_of_five_labels(admin_client):
    """expertise_level is always one of the 5 defined labels."""
    level = admin_client.get(MATURITY_URL).json()["expertise_level"]
    assert level in VALID_EXPERTISE_LEVELS


@pytest.mark.django_db
def test_maturity_score_is_float_in_valid_range(admin_client):
    """maturity_score must be a float between 0.0 and 100.0 (inclusive)."""
    score = admin_client.get(MATURITY_URL).json()["maturity_score"]
    assert isinstance(score, (int, float))
    assert 0.0 <= score <= 100.0


@pytest.mark.django_db
def test_maturity_only_allows_get(admin_client):
    """POST/PUT/DELETE must be rejected with 405 (read-only endpoint)."""
    assert admin_client.post(MATURITY_URL, {}, format="json").status_code == 405
    assert admin_client.put(MATURITY_URL, {}, format="json").status_code == 405
    assert admin_client.delete(MATURITY_URL).status_code == 405
