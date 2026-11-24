"""Automated Integration & Final Acceptance Test Suite for PulseIQ.

Verifies:
1. Health telemetry & 52,000+ seeded synthetic dataset integrity (spikes, duplicates, missing fields, multilingual)
2. JWT Authentication & Role-Based Access Control (Admin, Analyst, Viewer restrictions)
3. All 4 modular ingestion adapters (CSV, RSS, Permitted Public API, Synthetic Stream)
4. 10-stage NLP pipeline stages (normalisation, language detection, dedup, topic/sentiment, NER, sarcasm uncertainty)
5. Event Intelligence before/during/after comparison analytics
6. End-to-end Final Acceptance Workflow:
   Create Monitoring Topic -> Ingest Source -> NLP Process -> Identify Cluster/Trend ->
   Review Source Evidence -> Bookmark/Verify -> Correct Classification (Override) ->
   Audit Trail Verification -> Generate Grounded Report -> Export Markdown & CSV
7. Live WebSocket (/ws/live) connection readiness
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.nlp.pipeline import get_nlp_pipeline

client = TestClient(app)


def _login(email: str, password: str = "PulseIQ!2026") -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_and_52k_corpus_seeded():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["database"] == "connected"
    assert body["raw_records"] >= 50000
    assert body["processed_records"] >= 50000

    headers = _login("lead.analyst@pulseiq.gov")
    meth = client.get("/api/v1/methodology", headers=headers)
    assert meth.status_code == 200
    tel = meth.json()["corpus_telemetry"]
    assert tel["total_raw_records"] >= 50000
    assert tel["synthetic_records"] >= 50000
    assert tel["duplicate_records"] >= 500
    assert tel["missing_field_records"] >= 500
    assert tel["needs_review_queue"] >= 100
    langs = {item["language"] for item in tel["language_distribution"]}
    assert {"en", "es", "fr", "de", "pt"}.issubset(langs)


def test_rbac_authentication_and_viewer_restriction():
    # Unauthenticated request blocked
    unauth = client.get("/api/v1/overview")
    assert unauth.status_code == 401

    # Viewer can read overview, but cannot create monitoring topic or override
    viewer_headers = _login("viewer@pulseiq.gov")
    ov = client.get("/api/v1/overview?days=30", headers=viewer_headers)
    assert ov.status_code == 200
    assert ov.json()["kpis"]["total_all_time_records"] >= 50000

    forbidden = client.post(
        "/api/v1/topics",
        headers=viewer_headers,
        json={"name": "Unauthorized Viewer Topic", "keywords": ["test"]},
    )
    assert forbidden.status_code == 403


def test_nlp_pipeline_stages_and_edge_cases():
    pipeline = get_nlp_pipeline()
    samples = [
        "Check https://example.org or email user@city.gov @civicuser about Harbor Bridge delays in Eastside!",
        "Check https://example.org or email user@city.gov @civicuser about Harbor Bridge delays in Eastside!",
        "Los vecinos de Riverview solicitan mejor alumbrado en parques y cruces peatonales seguros.",
        "Great job closing the only Harbor Bridge lane right before the Annual Civic Festival—truly inspiring traffic planning.",
    ]
    res = pipeline.process_batch(samples)

    # Stage 2 privacy normalization
    assert "[URL]" in res.normalized_texts[0]
    assert "[EMAIL]" in res.normalized_texts[0]
    assert "[HANDLE]" in res.normalized_texts[0]

    # Stage 3 multilingual detection
    assert res.languages[0] == "en"
    assert res.languages[2] == "es"

    # Stage 4 duplicate detection
    assert res.is_duplicates[0] is False
    assert res.is_duplicates[1] is True
    assert res.similarity_scores[1] == 1.0

    # Stage 7 civic NER
    entity_names = {e["text"] for e in res.entities_list[0]}
    assert "Harbor Bridge" in entity_names

    # Sarcasm confidence dampening
    assert res.sentiment_confidences[3] < 0.75


def test_modular_ingestion_adapters_csv_rss_api_stream():
    headers = _login("analyst@pulseiq.gov")
    sources = client.get("/api/v1/sources", headers=headers).json()
    by_type = {}
    for s in sources:
        by_type.setdefault(s["provider_type"], s)

    for ptype in ("csv", "rss", "public_api", "synthetic_stream"):
        assert ptype in by_type, f"Missing configured source for provider_type={ptype}"
        src = by_type[ptype]
        run_resp = client.post(
            f"/api/v1/sources/{src['id']}/run",
            headers=headers,
            json={"batch_size": 5, "use_celery": False},
        )
        assert run_resp.status_code == 200, f"Adapter {ptype} failed: {run_resp.text}"
        body = run_resp.json()
        assert body["status"] in ("completed", "partial")
        assert body["records_inserted"] >= 1


def test_event_intelligence_before_during_after():
    headers = _login("senior.analyst@pulseiq.gov")
    events = client.get("/api/v1/events", headers=headers).json()
    assert len(events) >= 3

    analysis = client.get(f"/api/v1/events/{events[0]['id']}/analysis", headers=headers)
    assert analysis.status_code == 200
    data = analysis.json()
    assert data["comparison"]["during"]["count"] > 0
    assert len(data["timeline"]) > 0
    assert len(data["representative_evidence"]) > 0

    # Create a new custom event window
    now = datetime.now(timezone.utc)
    create_resp = client.post(
        "/api/v1/events",
        headers=headers,
        json={
            "title": f"Transit Corridor Public Hearing {uuid.uuid4().hex[:6]}",
            "description": "Automated acceptance verification event window.",
            "event_type": "Policy Hearing",
            "location": "Eastside Transit Hub",
            "start_time": (now - timedelta(days=3)).isoformat(),
            "end_time": now.isoformat(),
            "baseline_days": 5,
            "keywords": ["transit", "fare", "late-night bus"],
        },
    )
    assert create_resp.status_code == 201
    ev_id = create_resp.json()["id"]
    custom_analysis = client.get(f"/api/v1/events/{ev_id}/analysis", headers=headers)
    assert custom_analysis.status_code == 200
    assert custom_analysis.json()["comparison"]["during"]["count"] > 0

    # Clean up test event
    del_resp = client.delete(f"/api/v1/events/{ev_id}", headers=headers)
    assert del_resp.status_code == 204


def test_end_to_end_analyst_acceptance_workflow():
    """Demonstrates the exact Final Acceptance Test end-to-end:
    Create topic -> Ingest -> NLP Process -> Identify Trend/Cluster ->
    Review Evidence -> Correct Classification -> Audit Trail -> Generate Report & Export.
    """
    headers = _login("analyst@pulseiq.gov")
    suffix = uuid.uuid4().hex[:6]

    # 1. Analyst creates a monitoring topic
    topic_name = f"Stormwater & Corridor Resilience {suffix}"
    create_topic = client.post(
        "/api/v1/topics",
        headers=headers,
        json={
            "name": topic_name,
            "description": "Monitoring urban stormwater drainage, culvert flooding, and transit underpass resilience.",
            "category": "Infrastructure",
            "keywords": ["stormwater", "flooding", "culvert", "drain", "underpass"],
            "excluded_keywords": ["commercial plumbing ad"],
            "time_range_days": 30,
            "language": "all",
            "status": "active",
        },
    )
    assert create_topic.status_code == 201, create_topic.text
    topic_id = create_topic.json()["id"]

    # 2 & 3. System ingests records from a configured source and processes through NLP pipeline + clustering
    ingest_resp = client.post(
        f"/api/v1/topics/{topic_id}/ingest",
        headers=headers,
        json={"batch_size": 20, "use_celery": False},
    )
    assert ingest_resp.status_code == 200, ingest_resp.text
    ingest_body = ingest_resp.json()
    assert ingest_body["records_inserted"] == 20
    assert ingest_body["records_duplicated"] >= 1  # Near-duplicate detection verified

    # 4. System identifies topic clusters & trend metrics
    explorer_resp = client.get(f"/api/v1/explorer/overview?topic_id={topic_id}&days=30", headers=headers)
    assert explorer_resp.status_code == 200
    explorer_data = explorer_resp.json()
    assert len(explorer_data["clusters"]) >= 1
    assert len(explorer_data["volume_trends"]) >= 1

    # 5. Analyst reviews primary source evidence (verifying raw & processed stored separately)
    records_resp = client.get(f"/api/v1/records?topic_id={topic_id}&page=1&page_size=10", headers=headers)
    assert records_resp.status_code == 200
    items = records_resp.json()["items"]
    assert len(items) >= 1
    target_record_id = items[0]["id"]

    detail_resp = client.get(f"/api/v1/records/{target_record_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["raw"]["original_text"]
    assert detail["processed"]["normalized_text"]
    assert detail["raw"]["is_synthetic"] is True  # Synthetic provenance clearly labelled

    # Bookmark & verify insight with report section tag
    ann_resp = client.put(
        f"/api/v1/records/{target_record_id}/annotation",
        headers=headers,
        json={
            "is_bookmarked": True,
            "is_verified": True,
            "note": "Verified firsthand report of stormwater underpass disruption.",
            "report_section_tag": "Emerging Risk",
        },
    )
    assert ann_resp.status_code == 200
    assert ann_resp.json()["is_verified"] is True

    # 6. Analyst corrects an inaccurate classification (override)
    original_sent = detail["sentiment_classification"]["predicted_sentiment"]
    corrected_sent = "negative" if original_sent != "negative" else "mixed"
    ovr_resp = client.post(
        f"/api/v1/records/{target_record_id}/override",
        headers=headers,
        json={
            "overridden_sentiment": corrected_sent,
            "override_reason": "Acceptance test: sarcastic civic phrasing misclassified by baseline linear model.",
        },
    )
    assert ovr_resp.status_code == 200
    assert ovr_resp.json()["effective_sentiment"] == corrected_sent
    assert ovr_resp.json()["sentiment_overridden"] is True

    # Confirm original model prediction is preserved while effective label reflects override
    detail_after = client.get(f"/api/v1/records/{target_record_id}", headers=headers).json()
    assert detail_after["sentiment_classification"]["predicted_sentiment"] == original_sent
    assert detail_after["sentiment_classification"]["effective_sentiment"] == corrected_sent

    # Confirm audit log recorded the override
    audit_resp = client.get("/api/v1/audit-logs?action=classification.overridden", headers=headers)
    assert audit_resp.status_code == 200
    assert any(a["resource_id"] == str(target_record_id) for a in audit_resp.json()["items"])

    # 7. Analyst generates a grounded Insight Report & exports Markdown + CSV
    report_resp = client.post(
        "/api/v1/reports/generate",
        headers=headers,
        json={
            "title": f"Acceptance Intelligence Brief: {topic_name}",
            "subtitle": "End-to-End Evidence-Backed Verification Report",
            "monitoring_topic_id": topic_id,
            "days": 30,
        },
    )
    assert report_resp.status_code == 201, report_resp.text
    report_id = report_resp.json()["id"]

    report_detail = client.get(f"/api/v1/reports/{report_id}", headers=headers).json()
    assert "[REC-" in report_detail["executive_summary"]
    assert "PROVENANCE DISCLOSURE" in report_detail["provenance_disclosure"]
    assert len(report_detail["evidence"]) >= 1
    assert "Non-Representative Sampling" in report_detail["data_limitations"]

    md_export = client.get(f"/api/v1/reports/{report_id}/export?format=markdown", headers=headers)
    assert md_export.status_code == 200
    assert "# Acceptance Intelligence Brief" in md_export.text

    csv_export = client.get(f"/api/v1/records/export.csv?topic_id={topic_id}", headers=headers)
    assert csv_export.status_code == 200
    assert "record_id,external_id" in csv_export.text

    # Archive temporary test topic to keep workspace spotless
    arch = client.patch(f"/api/v1/topics/{topic_id}", headers=headers, json={"status": "archived"})
    assert arch.status_code == 200


def test_websocket_live_stream_connection():
    token = _login("analyst@pulseiq.gov")["Authorization"].replace("Bearer ", "")
    with client.websocket_connect(f"/ws/live?token={token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "connection.ready"
        assert "channel" in msg
