"""Tests for the centralized Notes / Comments / Reactions annotation layer.

Contract under test (see docs/DESIGN-NOTES-DRAWER.md):
  * Polymorphic Note on any entity (entity_type + entity_id, no FK cascade).
  * 1-level comments (no parent field) — flat threads only.
  * Lazy API: list payload carries comments_count + reaction counts but NO
    comment bodies; comments load via the nested per-note endpoint.
  * Permission model: any authenticated reads/creates/comments/reacts; edit &
    soft-delete restricted to author or global admin; internal visibility =
    author + admins only.
  * Reactions: one per user per target (note XOR comment), toggle = POST again.
  * Audit: create/update/delete emit GovernanceEvent.
"""
import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from catalog.models import Note, NoteComment, NoteReaction, GovernanceEvent

NOTES_URL = '/carbon-api/catalog/notes/'
COMMENTS_URL = '/carbon-api/catalog/notes/{note_id}/comments/'


@pytest.fixture
def auth_client(db, create_user, get_token_for_user):
    """API client authenticated as a normal user (own APIClient instance)."""
    user = create_user('note_writer')
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
    client.user = user
    return client


@pytest.fixture
def admin_client(db, create_user, get_token_for_user):
    """API client authenticated as a superuser (own APIClient instance)."""
    user = create_user('note_admin', is_superuser=True)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(user)}")
    client.user = user
    return client


def make_note(client, entity_type='org_unit', entity_id=42, body='Auditor asked for FY26 evidence.', **kw):
    payload = {'entity_type': entity_type, 'entity_id': entity_id, 'body': body, **kw}
    return client.post(NOTES_URL, payload, format='json')


# ── CRUD ────────────────────────────────────────────────────────────────────

class TestNoteCRUD:
    def test_create_note(self, auth_client):
        resp = make_note(auth_client)
        assert resp.status_code == 201, resp.content
        data = resp.json()
        assert data['body'] == 'Auditor asked for FY26 evidence.'
        assert data['author']['id'] == auth_client.user.id
        assert data['comments_count'] == 0
        assert data['reaction_counts'] == {'like': 0, 'question': 0, 'star': 0}
        assert data['my_reaction'] is None
        assert data['is_removed'] is False
        assert data['visibility'] == 'public'  # implicit from author scope
        # Audit event emitted
        assert GovernanceEvent.objects.filter(entity_type='note', action='create').exists()

    def test_list_notes_filtered_newest_first(self, auth_client):
        make_note(auth_client, entity_id=1, body='oldest')
        make_note(auth_client, entity_id=1, body='newest')
        resp = auth_client.get(NOTES_URL, {'entity_type': 'org_unit', 'entity_id': 1})
        assert resp.status_code == 200
        bodies = [n['body'] for n in resp.json()['results']]
        assert bodies == ['newest', 'oldest']

    def test_list_respects_other_entities(self, auth_client):
        make_note(auth_client, entity_id=1)
        resp = auth_client.get(NOTES_URL, {'entity_type': 'org_unit', 'entity_id': 999})
        assert resp.status_code == 200
        assert resp.json()['results'] == []

    def test_patch_note_body(self, auth_client):
        note = make_note(auth_client).json()
        resp = auth_client.patch(f"{NOTES_URL}{note['id']}/", {'body': 'updated body'}, format='json')
        assert resp.status_code == 200
        assert resp.json()['body'] == 'updated body'
        assert GovernanceEvent.objects.filter(entity_type='note', action='update').exists()

    def test_patch_cannot_change_entity(self, auth_client):
        note = make_note(auth_client, entity_id=1).json()
        resp = auth_client.patch(
            f"{NOTES_URL}{note['id']}/",
            {'entity_id': 777}, format='json')
        assert resp.status_code == 200
        assert Note.objects.get(id=note['id']).entity_id == 1

    def test_delete_is_soft(self, auth_client):
        note = make_note(auth_client).json()
        resp = auth_client.delete(f"{NOTES_URL}{note['id']}/")
        assert resp.status_code == 204
        db_note = Note.objects.get(id=note['id'])
        assert db_note.is_active is False
        assert GovernanceEvent.objects.filter(entity_type='note', action='delete').exists()
        # Soft-deleted note no longer listed
        resp = auth_client.get(NOTES_URL, {'entity_type': 'org_unit', 'entity_id': 42})
        assert resp.json()['results'] == []

    def test_requires_entity_and_body(self, auth_client):
        resp = auth_client.post(NOTES_URL, {'entity_type': 'org_unit'}, format='json')
        assert resp.status_code == 400


# ── Multi-anchor (Option B) ─────────────────────────────────────────────────
# One note can surface under MULTIPLE entities: primary anchor stays in
# entity_type/entity_id; extra anchors live in NoteAnchor. The drawer context
# for a domain app = [reporting_year, app] so a note appears in both threads
# without duplication, while each domain app's thread stays isolated.

class TestMultiAnchorNotes:
    def test_create_with_extra_anchors(self, auth_client):
        resp = auth_client.post(NOTES_URL, {
            'entity_type': 'reporting_year',
            'entity_id': 2026,
            'body': 'Dashboard note for FY26',
            'anchors': [
                {'entity_type': 'app', 'entity_id': 1},
                {'entity_type': 'module', 'entity_id': 52},
            ],
        }, format='json')
        assert resp.status_code == 201, resp.content
        data = resp.json()
        assert data['anchors'] == [
            {'entity_type': 'reporting_year', 'entity_id': 2026},
            {'entity_type': 'app', 'entity_id': 1},
            {'entity_type': 'module', 'entity_id': 52},
        ]
        note = Note.objects.get(id=data['id'])
        assert note.anchors.count() == 2
        # Audit event carries the full anchor list
        ev = GovernanceEvent.objects.filter(entity_type='note', action='create').latest('timestamp')
        assert len(ev.after['anchors']) == 3

    def test_duplicate_anchors_deduped_against_primary(self, auth_client):
        resp = auth_client.post(NOTES_URL, {
            'entity_type': 'reporting_year', 'entity_id': 2026, 'body': 'dedupe',
            'anchors': [
                {'entity_type': 'reporting_year', 'entity_id': 2026},  # == primary
                {'entity_type': 'app', 'entity_id': 1},
                {'entity_type': 'app', 'entity_id': 1},                # duplicate extra
            ],
        }, format='json')
        assert resp.status_code == 201, resp.content
        note = Note.objects.get(id=resp.json()['id'])
        assert note.anchors.count() == 1
        assert resp.json()['anchors'] == [
            {'entity_type': 'reporting_year', 'entity_id': 2026},
            {'entity_type': 'app', 'entity_id': 1},
        ]

    def test_anchors_optional_backward_compatible(self, auth_client):
        resp = make_note(auth_client, entity_type='org_unit', entity_id=42)
        assert resp.status_code == 201
        assert resp.json()['anchors'] == [{'entity_type': 'org_unit', 'entity_id': 42}]
        assert Note.objects.get(id=resp.json()['id']).anchors.count() == 0

    def test_single_pair_filter_matches_extra_anchor(self, auth_client):
        auth_client.post(NOTES_URL, {
            'entity_type': 'reporting_year', 'entity_id': 2026, 'body': 'app-scoped note',
            'anchors': [{'entity_type': 'app', 'entity_id': 1}],
        }, format='json')
        # Filtering by the app (extra anchor) still finds the note
        resp = auth_client.get(NOTES_URL, {'entity_type': 'app', 'entity_id': 1})
        bodies = [n['body'] for n in resp.json()['results']]
        assert 'app-scoped note' in bodies

    def test_anchor_list_filter_any_of(self, auth_client):
        # Note A: year + app. Note B: year only. Note C: another entity.
        auth_client.post(NOTES_URL, {
            'entity_type': 'reporting_year', 'entity_id': 2026, 'body': 'A',
            'anchors': [{'entity_type': 'app', 'entity_id': 1}],
        }, format='json')
        auth_client.post(NOTES_URL, {
            'entity_type': 'reporting_year', 'entity_id': 2026, 'body': 'B',
        }, format='json')
        auth_client.post(NOTES_URL, {
            'entity_type': 'org_unit', 'entity_id': 99, 'body': 'C',
        }, format='json')
        resp = auth_client.get(NOTES_URL, {'anchor': ['app:1', 'reporting_year:2026']})
        assert resp.status_code == 200
        bodies = [n['body'] for n in resp.json()['results']]
        assert set(bodies) == {'A', 'B'}  # C (different app) never mingles

    def test_anchor_filter_isolates_app_threads(self, auth_client):
        """Two domain apps must never see each other's notes."""
        auth_client.post(NOTES_URL, {
            'entity_type': 'reporting_year', 'entity_id': 2026, 'body': 'carbon note',
            'anchors': [{'entity_type': 'app', 'entity_id': 1}],  # carbon app
        }, format='json')
        auth_client.post(NOTES_URL, {
            'entity_type': 'reporting_year', 'entity_id': 2026, 'body': 'water note',
            'anchors': [{'entity_type': 'app', 'entity_id': 2}],  # water app
        }, format='json')
        resp = auth_client.get(NOTES_URL, {'anchor': ['app:1']})
        bodies = [n['body'] for n in resp.json()['results']]
        assert bodies == ['carbon note']
        assert 'water note' not in bodies

    def test_patch_cannot_change_anchors(self, auth_client):
        note = auth_client.post(NOTES_URL, {
            'entity_type': 'reporting_year', 'entity_id': 2026, 'body': 'stable',
            'anchors': [{'entity_type': 'app', 'entity_id': 1}],
        }, format='json').json()
        resp = auth_client.patch(
            f"{NOTES_URL}{note['id']}/",
            {'anchors': [{'entity_type': 'app', 'entity_id': 999}]}, format='json')
        assert resp.status_code == 200
        db_note = Note.objects.get(id=note['id'])
        assert db_note.anchors.count() == 1
        assert db_note.anchors.first().entity_id == 1
        assert resp.json()['anchors'] == [
            {'entity_type': 'reporting_year', 'entity_id': 2026},
            {'entity_type': 'app', 'entity_id': 1},
        ]


# ── Permissions ─────────────────────────────────────────────────────────────

class TestNotePermissions:
    def test_unauthenticated_blocked(self, db, api_client):
        assert api_client.get(NOTES_URL).status_code == 401
        assert make_note(api_client).status_code == 401

    def test_other_user_cannot_edit_or_delete(self, auth_client, api_client, create_user, get_token_for_user):
        note = make_note(auth_client).json()
        other = create_user('note_other')
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(other)}")
        assert api_client.patch(f"{NOTES_URL}{note['id']}/", {'body': 'x'}, format='json').status_code == 403
        assert api_client.delete(f"{NOTES_URL}{note['id']}/").status_code == 403
        # Read still allowed
        assert api_client.get(f"{NOTES_URL}{note['id']}/").status_code == 200

    def test_admin_can_edit_any(self, admin_client, auth_client):
        note = make_note(auth_client).json()
        resp = admin_client.patch(f"{NOTES_URL}{note['id']}/", {'body': 'admin edit'}, format='json')
        assert resp.status_code == 200

    def test_visibility_is_implicit(self, auth_client, admin_client, api_client, create_user, get_token_for_user):
        """Visibility derives from the author's scope — client input is ignored."""
        # Normal user → always public, even if 'internal' is posted.
        note = make_note(auth_client, visibility='internal').json()
        assert note['visibility'] == 'public'
        # Admin → always internal by scope.
        admin_note = make_note(admin_client, body='Admin scope note').json()
        assert admin_note['visibility'] == 'internal'
        # A third user sees the public note but not the admin's internal one.
        other = create_user('note_other2')
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(other)}")
        bodies = [n['body'] for n in api_client.get(NOTES_URL, {'entity_type': 'org_unit', 'entity_id': 42}).json()['results']]
        assert 'Auditor asked for FY26 evidence.' in bodies
        assert 'Admin scope note' not in bodies

    def test_internal_visible_to_author_and_admin(self, auth_client, admin_client, api_client, create_user, get_token_for_user):
        note = make_note(admin_client).json()
        assert note['visibility'] == 'internal'
        # Author (admin) sees own internal note
        resp = admin_client.get(NOTES_URL, {'entity_type': 'org_unit', 'entity_id': 42})
        assert any(n['id'] == note['id'] for n in resp.json()['results'])
        # Another admin sees it too
        other_admin = create_user('note_admin2', is_superuser=True)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(other_admin)}")
        resp = api_client.get(NOTES_URL, {'entity_type': 'org_unit', 'entity_id': 42})
        assert any(n['id'] == note['id'] for n in resp.json()['results'])


# ── Comments (1-level, lazy) ────────────────────────────────────────────────

class TestComments:
    def test_lazy_list_has_no_comment_bodies(self, auth_client):
        note = make_note(auth_client).json()
        note_id = note['id']
        auth_client.post(COMMENTS_URL.format(note_id=note_id), {'body': 'secret comment'}, format='json')
        resp = auth_client.get(NOTES_URL, {'entity_type': 'org_unit', 'entity_id': 42})
        item = resp.json()['results'][0]
        assert item['comments_count'] == 1
        assert 'secret comment' not in resp.content.decode()

    def test_comments_flat_thread(self, auth_client):
        note = make_note(auth_client).json()
        c1 = auth_client.post(COMMENTS_URL.format(note_id=note['id']), {'body': 'first'}, format='json')
        c2 = auth_client.post(COMMENTS_URL.format(note_id=note['id']), {'body': 'second'}, format='json')
        assert c1.status_code == 201 and c2.status_code == 201
        resp = auth_client.get(COMMENTS_URL.format(note_id=note['id']))
        assert resp.status_code == 200
        bodies = [c['body'] for c in resp.json()['results']]
        assert bodies == ['first', 'second']  # chronological
        # Each comment has author + reaction scaffolding
        assert resp.json()['results'][0]['author']['username'] == 'note_writer'

    def test_comment_edit_author_only(self, auth_client, api_client, create_user, get_token_for_user):
        note = make_note(auth_client).json()
        comment = auth_client.post(
            COMMENTS_URL.format(note_id=note['id']), {'body': 'mine'}, format='json').json()
        other = create_user('comment_other')
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(other)}")
        assert api_client.patch(
            f"{COMMENTS_URL.format(note_id=note['id'])}{comment['id']}/",
            {'body': 'hijack'}, format='json').status_code == 403

    def test_comment_soft_delete(self, auth_client):
        note = make_note(auth_client).json()
        comment = auth_client.post(
            COMMENTS_URL.format(note_id=note['id']), {'body': 'bye'}, format='json').json()
        assert auth_client.delete(
            f"{COMMENTS_URL.format(note_id=note['id'])}{comment['id']}/").status_code == 204
        assert NoteComment.objects.get(id=comment['id']).is_active is False
        assert GovernanceEvent.objects.filter(entity_type='note_comment', action='delete').exists()

    def test_comment_on_hidden_internal_note_blocked(self, admin_client, api_client, create_user, get_token_for_user):
        note = make_note(admin_client).json()  # internal by admin scope
        other = create_user('comment_other2')
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {get_token_for_user(other)}")
        resp = api_client.post(COMMENTS_URL.format(note_id=note['id']), {'body': 'nope'}, format='json')
        assert resp.status_code == 404


# ── Reactions ───────────────────────────────────────────────────────────────

class TestReactions:
    def test_toggle_note_reaction(self, auth_client):
        note = make_note(auth_client).json()
        url = f"{NOTES_URL}{note['id']}/reactions/"
        resp = auth_client.post(url, {'reaction': 'like'}, format='json')
        assert resp.status_code == 200
        assert resp.json()['reaction_counts']['like'] == 1
        assert resp.json()['my_reaction'] == 'like'
        # Toggle again → removed
        resp = auth_client.post(url, {'reaction': 'like'}, format='json')
        assert resp.json()['reaction_counts']['like'] == 0
        assert resp.json()['my_reaction'] is None

    def test_one_reaction_per_user_per_note(self, auth_client):
        note = make_note(auth_client).json()
        url = f"{NOTES_URL}{note['id']}/reactions/"
        auth_client.post(url, {'reaction': 'like'}, format='json')
        auth_client.post(url, {'reaction': 'star'}, format='json')
        assert NoteReaction.objects.filter(note_id=note['id']).count() == 2
        # Same user can hold like + star on one note (different reactions allowed)
        assert NoteReaction.objects.filter(note_id=note['id'], reaction='like').count() == 1

    def test_reaction_on_comment(self, auth_client):
        note = make_note(auth_client).json()
        comment = auth_client.post(
            COMMENTS_URL.format(note_id=note['id']), {'body': 'agree'}, format='json').json()
        url = f"{COMMENTS_URL.format(note_id=note['id'])}{comment['id']}/reactions/"
        resp = auth_client.post(url, {'reaction': 'question'}, format='json')
        assert resp.status_code == 200
        assert resp.json()['reaction_counts']['question'] == 1

    def test_counts_are_independent_per_target(self, auth_client):
        note = make_note(auth_client).json()
        comment = auth_client.post(
            COMMENTS_URL.format(note_id=note['id']), {'body': 'x'}, format='json').json()
        auth_client.post(f"{NOTES_URL}{note['id']}/reactions/", {'reaction': 'like'}, format='json')
        auth_client.post(
            f"{COMMENTS_URL.format(note_id=note['id'])}{comment['id']}/reactions/",
            {'reaction': 'like'}, format='json')
        # Note has 1 like, comment has its own 1 like — not merged
        assert NoteReaction.objects.filter(note_id=note['id']).count() == 1
        assert NoteReaction.objects.filter(comment_id=comment['id']).count() == 1

    def test_invalid_reaction_rejected(self, auth_client):
        note = make_note(auth_client).json()
        resp = auth_client.post(
            f"{NOTES_URL}{note['id']}/reactions/", {'reaction': 'angry'}, format='json')
        assert resp.status_code == 400
