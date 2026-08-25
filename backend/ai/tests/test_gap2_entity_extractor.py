"""Tests for EntityExtractor (GAP-2).

All assertions are domain-agnostic — entity names are from healthcare,
logistics, and generic domains, not carbon/DQ-specific.
"""
import pytest
from ai.engine.cognition.dialogue.entity_extractor import EntityExtractor, ExtractedEntity


@pytest.fixture
def extractor():
    return EntityExtractor()


def test_extracts_typed_table_entity(extractor):
    entity = extractor.extract("I want to validate the Invoice table")
    assert entity is not None
    assert entity.name == "Invoice"
    assert entity.entity_type == "table"


def test_extracts_dataset_entity(extractor):
    entity = extractor.extract("profile the Lab Results dataset")
    assert entity is not None
    assert entity.name == "Lab Results"
    assert entity.entity_type == "dataset"


def test_extracts_column_entity(extractor):
    entity = extractor.extract("check the Email field")
    assert entity is not None
    assert entity.name == "Email"
    assert entity.entity_type == "field"


def test_extracts_focus_entity_without_type_word(extractor):
    entity = extractor.extract("Focus on Patient Records for now")
    assert entity is not None
    assert "Patient Records" in entity.name


def test_extracts_intent_sentence_entity(extractor):
    entity = extractor.extract("I need to analyze the Shipment Records table")
    assert entity is not None
    assert entity.name == "Shipment Records"
    assert entity.entity_type == "table"


def test_no_entity_returns_none(extractor):
    entity = extractor.extract("What is the meaning of life?")
    assert entity is None


def test_short_text_no_entity(extractor):
    assert extractor.extract("hi") is None


def test_works_for_multi_word_entity(extractor):
    entity = extractor.extract("validate the Customer Order History table")
    assert entity is not None
    assert "Customer Order History" in entity.name


def test_case_insensitive_type_word(extractor):
    entity = extractor.extract("review the Delivery Records TABLE")
    assert entity is not None
    assert entity.entity_type == "table"


def test_no_domain_hardcoding(extractor):
    # The extractor must work for completely new domains
    result = extractor.extract("examine the Medication Batch record")
    assert result is not None
    assert "Medication Batch" in result.name
