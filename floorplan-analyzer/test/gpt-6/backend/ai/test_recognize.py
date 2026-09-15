"""AI transport is mocked: these tests do not measure recognition accuracy."""
import base64
import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import ai
from app.main import app

client = TestClient(app)


def picture():
    buf = io.BytesIO()
    Image.new('RGB', (200, 100), 'white').save(buf, format='PNG')
    return buf.getvalue()


def output():
    return {'rooms': [{'name': 'Room', 'vertices': [{'x': 0, 'y': 0}, {'x': 1, 'y': 0}, {'x': 1, 'y': 1}, {'x': 0, 'y': 1}]}], 'walls': [{'start': {'x': 0, 'y': 0}, 'end': {'x': 1, 'y': 0}}], 'doors': [], 'warnings': []}


@pytest.fixture
def configured(monkeypatch):
    for key, value in [('OPENAI_API_KEY', 'secret-api'), ('OPENAI_MODEL', 'test-model'), ('AI_ACCESS_TOKEN', 'test-token')]:
        monkeypatch.setenv(key, value)


def upload(data=None, token='test-token'):
    return client.post('/api/recognize', files={'file': ('plan.png', picture() if data is None else data, 'image/png')}, headers={'X-AI-Token': token})


def test_disabled(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    assert client.get('/api/ai/status').json() == {'enabled': False}
    assert upload().status_code == 503


def test_auth_before_provider(configured, monkeypatch):
    async def fail(*args):
        pytest.fail('must not call provider')
    monkeypatch.setattr(ai, 'request_recognition', fail)
    assert upload(token='wrong').status_code == 401
    assert upload(token=b'\xff').status_code == 401
    assert client.get('/api/ai/status').json() == {'enabled': True}


def test_conversion_and_analyze(configured, monkeypatch):
    async def fake(*args):
        return output()
    monkeypatch.setattr(ai, 'request_recognition', fake)
    response = upload()
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['model'] == 'test-model'
    assert body['warnings']
    mask = body['mask']
    assert mask['image_width'] == 200 and mask['image_height'] == 100
    assert mask['contours'][0]['vertices'][2] == {'x': 200., 'y': 100.}
    assert [x['id'] for x in mask['contours']] == [1, 2]
    assert mask['contours'][1]['label_id'] == 2
    assert Image.open(io.BytesIO(base64.b64decode(mask['image_data']['base64']))).size == (200, 100)
    analysis = client.post('/api/analyze/json?scale_px=100&scale_m=1', json=mask)
    assert analysis.status_code == 200
    assert analysis.json()['summary']['total_floor_area_m2'] == 2
    assert any(w['code'] == 'ai_generated' for w in analysis.json()['warnings'])


@pytest.mark.parametrize('bad', [b'not an image', b'', b'<svg></svg>'])
def test_bad_images(configured, bad):
    assert upload(bad).status_code == 422


def test_too_large(configured, monkeypatch):
    monkeypatch.setattr(ai, 'MAX_IMAGE_BYTES', 10)
    assert upload().status_code == 413


@pytest.mark.parametrize('change', [
    lambda d: d['rooms'][0]['vertices'][0].update(x=float('nan')),
    lambda d: d['rooms'][0]['vertices'][0].update(x=1.1),
    lambda d: d.update(rooms=d['rooms'] * 101),
    lambda d: d['rooms'][0].update(vertices=[{'x': 0, 'y': 0}]),
    lambda d: d.update(extra='unexpected'),
])
def test_invalid_model_output(configured, monkeypatch, change):
    async def fake(*args):
        data = output()
        change(data)
        return data
    monkeypatch.setattr(ai, 'request_recognition', fake)
    response = upload()
    assert response.status_code == 502
    assert 'nan' not in response.text.lower()


def test_image_dimension_limit(configured, monkeypatch):
    monkeypatch.setattr(ai, 'MAX_IMAGE_PIXELS', 10)
    assert upload().status_code == 413


def test_provider_schema_and_refusal(monkeypatch):
    seen = []
    async def handler(request):
        data = json.loads(request.content)
        seen.append(data)
        return httpx.Response(200, json={'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'secret-api'}]}]})
    original = httpx.AsyncClient
    monkeypatch.setattr(ai.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    import asyncio
    with pytest.raises(ai.HTTPException) as error:
        asyncio.run(ai.request_recognition('secret-api', 'test-model', 'data:image/png;base64,abc'))
    assert error.value.status_code == 422
    assert 'secret-api' not in error.value.detail
    assert seen[0]['text']['format']['strict'] is True
    assert seen[0]['store'] is False
    assert seen[0]['input'][0]['content'][1]['type'] == 'input_image'


@pytest.mark.parametrize('kind,status', [('success', 200), ('timeout', 504), ('http', 502), ('invalid', 502), ('incomplete', 502), ('large', 502)])
def test_transport_errors_and_success(configured, monkeypatch, kind, status):
    async def handler(request):
        if kind == 'timeout':
            raise httpx.ReadTimeout('secret-api')
        if kind == 'http':
            return httpx.Response(401, text='secret-api')
        if kind == 'invalid':
            return httpx.Response(200, text='secret-api')
        if kind == 'large':
            return httpx.Response(200, content=b'x' * (ai.MAX_RESPONSE_BYTES + 1))
        return httpx.Response(200, json={'status': 'incomplete' if kind == 'incomplete' else 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(output())}]}]})
    original = httpx.AsyncClient
    monkeypatch.setattr(ai.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    response = upload()
    assert response.status_code == status, response.text
    assert 'secret-api' not in response.text


def test_jpeg_exif_orientation(configured, monkeypatch):
    async def fake(*args):
        return output()
    monkeypatch.setattr(ai, 'request_recognition', fake)
    buf = io.BytesIO()
    im = Image.new('RGB', (200, 100), 'white')
    exif = im.getexif()
    exif[274] = 6
    im.save(buf, format='JPEG', exif=exif)
    response = upload(buf.getvalue())
    assert response.status_code == 200
    mask = response.json()['mask']
    assert (mask['image_width'], mask['image_height']) == (100, 200)
    assert mask['contours'][0]['vertices'][2] == {'x': 100., 'y': 200.}
