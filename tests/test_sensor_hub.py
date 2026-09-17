import pytest

from app.sensor_hub import U_CODES, normalize_event


def test_normalizes_sensor_reading_into_ugatu_envelope():
    event = normalize_event(
        "field-sensor-01",
        {"temp_c": 22},
        observed_at="2026-09-16T20:00:00+00:00",
        metadata={"transport": "https", "site": "test"},
    )
    assert event["u_code"] == "U-9210"
    assert event["event_type"] == "sensor.reading.received"
    assert event["source_system"] == "UNG-CONSTELLATION"
    assert event["source_function"] == "REMOTE-SENSOR-HUB"
    assert event["sensor_id"] == "field-sensor-01"
    assert event["data"] == {"temp_c": 22}
    assert event["metadata"]["schema_version"] == "1.0"
    assert event["metadata"]["site"] == "test"
    assert event["message_id"]


def test_all_sensor_event_types_have_reserved_u_codes():
    assert U_CODES == {
        "sensor.reading.received": "U-9210",
        "sensor.threshold.alert": "U-9220",
        "sensor.offline": "U-9230",
        "sensor.restored": "U-9240",
        "sensor.data_quality.exception": "U-9250",
        "sensor.calibration.maintenance": "U-9260",
        "sensor.manual_reading": "U-9270",
        "sensor.event.acknowledged": "U-9280",
        "sensor.integration.audit": "U-9290",
    }


def test_rejects_blank_sensor_id():
    with pytest.raises(ValueError, match="sensor_id is required"):
        normalize_event("  ", {"temp_c": 22})


def test_rejects_unknown_event_type():
    with pytest.raises(ValueError, match="unsupported event_type"):
        normalize_event("field-sensor-01", {}, event_type="sensor.unknown")
