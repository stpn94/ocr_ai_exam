import pytest
import base64
import os
from unittest.mock import MagicMock, patch

# 테스트 대상 모듈 임포트 (경로 설정 필요 가능성)
# 프로젝트 루트에서 pytest를 실행한다고 가정하고, utils 폴더가 PYTHONPATH에 있다고 가정
# 또는 상대 경로 임포트: from ....utils import huggingface_api (pytest 실행 위치에 따라 조정)
# 여기서는 utils.huggingface_api 로 직접 참조 (PYTHONPATH에 프로젝트 루트 추가 필요)
from utils import huggingface_api 

# Streamlit 모듈 모킹 (테스트 환경에서는 st 객체가 없음)
# huggingface_api 모듈이 로드될 때 st 객체를 사용하므로, 모듈 레벨에서 모킹이 필요할 수 있음.
# 여기서는 함수 내에서 st.secrets를 사용하므로, 해당 부분만 선택적으로 모킹하거나,
# 테스트 시 st 객체가 없어도 os.environ을 통해 동작하도록 함수가 설계되어야 함.
# huggingface_api.st = MagicMock() # 간단한 전역 모킹 (필요시)

class MockUploadedFile:
    def __init__(self, file_content_bytes):
        self.content_bytes = file_content_bytes

    def getvalue(self):
        return self.content_bytes

# --- get_huggingface_api_key 테스트 ---
def test_get_huggingface_api_key_from_env(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "test_env_api_key")
    # st.secrets 모킹 (존재하지 않도록)
    with patch.object(huggingface_api, 'st', MagicMock(secrets=None), create=True):
        assert huggingface_api.get_huggingface_api_key() == "test_env_api_key"

def test_get_huggingface_api_key_from_streamlit_secrets(monkeypatch):
    # 환경 변수 삭제 또는 다른 값으로 설정
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    mock_st_secrets = {"huggingface": {"api_key": "test_streamlit_api_key"}}
    
    with patch.object(huggingface_api, 'st', MagicMock(secrets=mock_st_secrets), create=True):
        assert huggingface_api.get_huggingface_api_key() == "test_streamlit_api_key"

def test_get_huggingface_api_key_not_found(monkeypatch):
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    with patch.object(huggingface_api, 'st', MagicMock(secrets=None, error=MagicMock()), create=True):
        with pytest.raises(ValueError, match="Hugging Face API 키를 찾을 수 없습니다."):
            huggingface_api.get_huggingface_api_key()

# --- get_huggingface_endpoint_url 테스트 ---
def test_get_huggingface_endpoint_url_from_env(monkeypatch):
    test_url = "https://env.example.com/api"
    monkeypatch.setenv("HUGGINGFACE_API_ENDPOINT_URL", test_url)
    assert huggingface_api.get_huggingface_endpoint_url() == test_url

def test_get_huggingface_endpoint_url_from_default(monkeypatch):
    monkeypatch.delenv("HUGGINGFACE_API_ENDPOINT_URL", raising=False)
    # huggingface_api.HUGGINGFACE_API_ENDPOINT_URL을 임시로 변경하여 테스트
    original_default_url = huggingface_api.HUGGINGFACE_API_ENDPOINT_URL
    huggingface_api.HUGGINGFACE_API_ENDPOINT_URL = "https://default.example.com/api"
    assert huggingface_api.get_huggingface_endpoint_url() == "https://default.example.com/api"
    huggingface_api.HUGGINGFACE_API_ENDPOINT_URL = original_default_url # 원상 복구

def test_get_huggingface_endpoint_url_not_configured(monkeypatch):
    monkeypatch.delenv("HUGGINGFACE_API_ENDPOINT_URL", raising=False)
    original_default_url = huggingface_api.HUGGINGFACE_API_ENDPOINT_URL
    huggingface_api.HUGGINGFACE_API_ENDPOINT_URL = "YOUR_HUGGINGFACE_INFERENCE_ENDPOINT_URL_HERE"
    with patch.object(huggingface_api.st, 'error', MagicMock()): # st.error 호출 모킹
        with pytest.raises(ValueError, match="Hugging Face Inference Endpoint URL이 설정되지 않았습니다."):
            huggingface_api.get_huggingface_endpoint_url()
    huggingface_api.HUGGINGFACE_API_ENDPOINT_URL = original_default_url


# --- encode_image_to_base64 테스트 ---
def test_encode_image_to_base64():
    # 1x1 픽셀 투명 PNG 이미지의 바이트 및 base64 표현
    png_bytes = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
    expected_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    mock_file = MockUploadedFile(png_bytes)
    assert huggingface_api.encode_image_to_base64(mock_file) == expected_base64

# --- prepare_ocr_payload 테스트 ---
def test_prepare_ocr_payload():
    image_b64 = "dummy_image_base64_string"
    schema = [
        {'key_name': 'InvoiceID', 'description': 'Invoice identifier', 'data_type': 'String', 'is_array': False},
        {'key_name': 'Amount', 'description': 'Total amount', 'data_type': 'Number', 'is_array': False},
        {'key_name': 'Items', 'description': 'List of items', 'data_type': 'String', 'is_array': True},
    ]
    expected_payload = {
        "inputs": {
            "image": image_b64,
            "schema": [
                {"key": "InvoiceID", "description": "Invoice identifier", "type": "String", "is_array": False},
                {"key": "Amount", "description": "Total amount", "type": "Number", "is_array": False},
                {"key": "Items", "description": "List of items", "type": "String", "is_array": True},
            ]
        }
    }
    assert huggingface_api.prepare_ocr_payload(image_b64, schema) == expected_payload

def test_prepare_ocr_payload_empty_schema():
    image_b64 = "dummy_image_base64_string"
    schema = []
    expected_payload = {"inputs": {"image": image_b64, "schema": []}}
    assert huggingface_api.prepare_ocr_payload(image_b64, schema) == expected_payload

# --- call_huggingface_ocr_endpoint 테스트 (requests_mock 사용) ---
MOCK_ENDPOINT_URL = "http://mock.hf.endpoint/ocr"

@pytest.fixture
def mock_hf_env(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "fake_api_key")
    monkeypatch.setenv("HUGGINGFACE_API_ENDPOINT_URL", MOCK_ENDPOINT_URL)
    # st.info, st.warning, st.error 모킹
    with patch.object(huggingface_api.st, 'info', MagicMock()), \
         patch.object(huggingface_api.st, 'warning', MagicMock()), \
         patch.object(huggingface_api.st, 'error', MagicMock()):
        yield

def test_call_huggingface_ocr_endpoint_success(requests_mock, mock_hf_env):
    requests_mock.post(MOCK_ENDPOINT_URL, json={"data": "success"}, status_code=200)
    payload = {"inputs": "test"}
    response = huggingface_api.call_huggingface_ocr_endpoint(payload)
    assert response == {"data": "success"}
    assert huggingface_api.st.info.call_count > 0 # st.info 호출되었는지 확인

def test_call_huggingface_ocr_endpoint_http_error_401(requests_mock, mock_hf_env):
    requests_mock.post(MOCK_ENDPOINT_URL, status_code=401, text="Unauthorized")
    payload = {"inputs": "test"}
    with pytest.raises(Exception, match="API Authentication Error (401)"):
        huggingface_api.call_huggingface_ocr_endpoint(payload)
    assert huggingface_api.st.error.call_count > 0 

def test_call_huggingface_ocr_endpoint_http_error_500_retry_fail(requests_mock, mock_hf_env):
    requests_mock.post(MOCK_ENDPOINT_URL, status_code=500, text="Server Error")
    payload = {"inputs": "test"}
    with pytest.raises(Exception, match="API HTTP Error after 3 attempts: 500 - Server Error"):
        huggingface_api.call_huggingface_ocr_endpoint(payload, max_retries=3)
    assert requests_mock.call_count == 3 # 3번 재시도 했는지 확인

def test_call_huggingface_ocr_endpoint_timeout_retry_fail(requests_mock, mock_hf_env):
    requests_mock.post(MOCK_ENDPOINT_URL, exc=huggingface_api.requests.exceptions.Timeout)
    payload = {"inputs": "test"}
    with pytest.raises(Exception, match="API call timed out after 3 attempts"):
        huggingface_api.call_huggingface_ocr_endpoint(payload, max_retries=3)
    assert requests_mock.call_count == 3

# --- parse_ocr_response 테스트 ---
# (기존 if __name__ == "__main__" 블록의 테스트 케이스들을 pytest 형식으로 변환)
PARSE_TEST_CASES = [
    # (input_response, expected_output / expected_exception_type, expected_exception_match)
    ([{"InvoiceNumber": "INV123"}], {"InvoiceNumber": "INV123"}, None, None),
    ({"extracted_data": {"Item": "Widget"}}, {"Item": "Widget"}, None, None),
    ({"Name": "John Doe"}, {"Name": "John Doe"}, None, None),
    ({"error": "Model failed"}, None, Exception, "API Error: Model failed"),
    ([{"error": "Input too long"}], None, Exception, "API Error in response list: Input too long"),
    ({"raw_text_output": "Some text"}, {"raw_text_output": "Some text"}, None, None), # generate_text 시나리오
    ([], None, Exception, "Failed to find or parse extracted data"), # 빈 리스트
    ({"other_key": "value"}, {"other_key": "value"}, None, None) # 전체 응답 사용 케이스
]

@pytest.mark.parametrize("response, expected_output, exc_type, exc_match", PARSE_TEST_CASES)
def test_parse_ocr_response(response, expected_output, exc_type, exc_match):
    with patch.object(huggingface_api.st, 'success', MagicMock()), \
         patch.object(huggingface_api.st, 'info', MagicMock()), \
         patch.object(huggingface_api.st, 'warning', MagicMock()), \
         patch.object(huggingface_api.st, 'error', MagicMock()):
        if exc_type:
            with pytest.raises(exc_type, match=exc_match if exc_match else ""):
                huggingface_api.parse_ocr_response(response)
        else:
            assert huggingface_api.parse_ocr_response(response) == expected_output 