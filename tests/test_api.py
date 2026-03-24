from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    res = client.get('/api/v1/health')
    assert res.status_code == 200
    assert res.json()['status'] == 'ok'


def test_period_options():
    res = client.get('/api/v1/period-options/1d')
    assert res.status_code == 200
    assert 'periods' in res.json()
