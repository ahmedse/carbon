"""
integrations/turnkey/models.py — TurnKey Bridge data model.

Contract: docs/DESIGN-PLATFORM.md §6.3.

* ``TurnKeyConfig``     — connection config; the TurnKey API key is stored
  Fernet-encrypted at rest (``FERNET_KEY`` setting), never in plaintext.
* ``TurnKeyModelLink``  — provenance record: Carbon DatasetVersion → TurnKey
  registered model + version (purpose training/inference).
* ``PredictionRecord``  — a prediction received back from TurnKey (with
  optional trace-back to the source DataRow + feedback loop for accuracy).
* ``DriftAlert``        — a drift alert received from TurnKey; triggers a DQ
  re-evaluation on the linked dataset version.

Dependency direction: this app imports datahub/dataschema/dq (all core apps).
Core apps never import this app.
"""
import hashlib
import json
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from cryptography.fernet import Fernet

User = get_user_model()


def canonical_json(value) -> str:
    """Stable JSON serialization used for input_hash computation.

    Keys are sorted and values are str()-normalized so the same logical input
    always hashes identically regardless of dict ordering.
    """
    return json.dumps(value, sort_keys=True, default=str)


def input_hash_of(value) -> str:
    """64-char hex SHA-256 of canonicalized input data (the input_hash key)."""
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


class TurnKeyConfig(models.Model):
    """Connection config for a TurnKey deployment. One per platform (usually).

    api_key_encrypted: Fernet-encrypted TurnKey API key.
    Never store the plaintext key. Provide .get_api_key()/.set_api_key() helpers.
    """
    name = models.CharField(max_length=120, unique=True)
    base_url = models.CharField(max_length=500)
    api_key_encrypted = models.TextField(blank=True)  # Fernet b64 ciphertext
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='turnkey_configs',
    )

    class Meta:
        ordering = ['name']

    def _fernet(self) -> Fernet:
        return Fernet(settings.FERNET_KEY.encode())

    def get_api_key(self) -> str:
        """Decrypt and return the TurnKey API key (plaintext, in-memory only)."""
        if not self.api_key_encrypted:
            return ''
        return self._fernet().decrypt(self.api_key_encrypted.encode()).decode()

    def set_api_key(self, plaintext: str):
        """Encrypt and store the TurnKey API key (never persists plaintext)."""
        if plaintext:
            self.api_key_encrypted = self._fernet().encrypt(
                plaintext.encode()
            ).decode()
        else:
            self.api_key_encrypted = ''

    def __str__(self):
        return self.name


class TurnKeyModelLink(models.Model):
    """Links a Carbon DatasetVersion to a TurnKey registered model+version.

    This is the provenance record: model X in TurnKey was trained on
    DatasetVersion Y in Carbon (approved, health_score Z).

    purpose='training': the version was the training dataset for this model.
    purpose='inference': the version is the reference schema for live predictions.
    """
    PURPOSE_CHOICES = [
        ('training',   'Training dataset'),
        ('inference',  'Inference input schema'),
    ]
    STATUS_CHOICES = [
        ('pending',    'Pending'),
        ('registered', 'Registered in TurnKey'),
        ('promoted',   'Promoted to production'),
        ('failed',     'Failed'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset_version = models.ForeignKey(
        'datahub.DatasetVersion', on_delete=models.PROTECT,
        related_name='turnkey_links',
    )
    turnkey_config = models.ForeignKey(TurnKeyConfig, on_delete=models.PROTECT)
    turnkey_model_id = models.CharField(max_length=200)
    turnkey_model_name = models.CharField(max_length=200, blank=True)
    turnkey_version_id = models.CharField(max_length=200, blank=True)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending',
    )
    error_detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    linked_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='turnkey_links',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        try:
            return (
                f"{self.dataset_version.dataset.name} "
                f"v{self.dataset_version.version_number}"
                f" → TurnKey:{self.turnkey_model_name or self.turnkey_model_id}"
            )
        except Exception:
            return f"TurnKeyModelLink({self.id})"


class PredictionRecord(models.Model):
    """A prediction received back from TurnKey, stored for provenance and DQ feedback.

    input_ref: reference to the DataRow that was the prediction input (if traceable).
    actual: the real outcome when known (feedback loop — enables accuracy monitoring).
    When actual is set, the health of the linked DatasetVersion can be re-evaluated.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model_link = models.ForeignKey(
        TurnKeyModelLink, on_delete=models.CASCADE, related_name='predictions',
    )
    # Source data row (optional — not always traceable)
    input_data_row = models.ForeignKey(
        'dataschema.DataRow', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='predictions',
    )
    input_hash = models.CharField(max_length=64, blank=True)  # SHA-256 of input JSON
    prediction = models.JSONField()
    actual = models.JSONField(null=True, blank=True)
    feedback_submitted_at = models.DateTimeField(null=True, blank=True)
    feedback_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='submitted_feedback',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Prediction {self.id} on {self.model_link}"


class DriftAlert(models.Model):
    """Drift alert received from TurnKey. Triggers a DQ re-evaluation."""
    SEVERITY_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]
    model_link = models.ForeignKey(
        TurnKeyModelLink, on_delete=models.CASCADE, related_name='drift_alerts',
    )
    turnkey_alert_id = models.CharField(max_length=200, unique=True)
    metric = models.CharField(max_length=50)   # e.g. "mape", "rmse"
    value = models.FloatField()
    threshold = models.FloatField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    # After receiving a drift alert: mark linked dataset version health as degraded
    dq_job_triggered = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='acknowledged_drift_alerts',
    )

    class Meta:
        ordering = ['-received_at']

    def __str__(self):
        return f"Drift {self.metric}={self.value} ({self.severity})"
