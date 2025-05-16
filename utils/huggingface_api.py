import os
import streamlit as st
from dotenv import load_dotenv
import base64
from typing import List, Dict, Any # 타입 힌팅용
import json # 테스트용
import requests # API 호출용
import time # 재시도 로직용

# .env 파일이 있다면 로드 (로컬 개발 시 유용)
load_dotenv()

HUGGINGFACE_API_ENDPOINT_URL = "YOUR_HUGGINGFACE_INFERENCE_ENDPOINT_URL_HERE" # 사용자가 생성한 엔드포인트 URL로 대체 필요
# 예시: "https://xyz.eu-west-1.aws.endpoints.huggingface.cloud"
# 또는 특정 모델 경로: "https://api-inference.huggingface.co/models/prithivMLmods/Qwen2-VL-OCR2-2B-Instruct"

def get_huggingface_api_key() -> str:
    """
    Hugging Face API 키를 Streamlit secrets 또는 환경 변수에서 안전하게 가져옵니다.
    Streamlit Cloud 배포 시에는 st.secrets를 사용하고,
    로컬 개발 시에는 .env 파일 또는 직접 설정된 환경 변수를 사용합니다.
    """
    api_key = None
    # 1. Streamlit secrets에서 시도 (배포 환경용)
    try:
        if hasattr(st, 'secrets') and "huggingface" in st.secrets and "api_key" in st.secrets.huggingface:
            api_key = st.secrets.huggingface.api_key
            if api_key:
                # st.info("Using API key from Streamlit secrets.") # 디버깅용
                return api_key
    except Exception as e:
        # st.warning(f"Could not read Streamlit secrets (this is normal in local dev): {e}")
        pass

    # 2. 환경 변수에서 시도 (로컬 개발 환경용)
    api_key = os.environ.get("HUGGINGFACE_API_KEY")
    if api_key:
        # st.info("Using API key from environment variable.") # 디버깅용
        return api_key

    # 3. API 키를 찾을 수 없는 경우
    error_message = (
        "Hugging Face API 키를 찾을 수 없습니다. "
        "Streamlit Cloud에 배포하는 경우 'secrets.toml'에 [huggingface] api_key = 'YOUR_HF_TOKEN' 형식으로 설정해주세요. "
        "로컬에서 실행하는 경우, '.env' 파일에 HUGGINGFACE_API_KEY='YOUR_HF_TOKEN' 형식으로 설정하거나, "
        "직접 환경 변수로 설정해주세요."
    )
    st.error(error_message)
    raise ValueError(error_message)

def get_huggingface_endpoint_url() -> str:
    """
    Hugging Face Inference Endpoint URL을 환경 변수 또는 기본값에서 가져옵니다.
    """
    url = os.environ.get("HUGGINGFACE_API_ENDPOINT_URL", HUGGINGFACE_API_ENDPOINT_URL)
    if url == "YOUR_HUGGINGFACE_INFERENCE_ENDPOINT_URL_HERE" or not url:
        error_message = (
            "Hugging Face Inference Endpoint URL이 설정되지 않았습니다. "
            "'.env' 파일에 HUGGINGFACE_API_ENDPOINT_URL='YOUR_ENDPOINT_URL' 형식으로 설정하거나, "
            "코드 내 HUGGINGFACE_API_ENDPOINT_URL 변수를 실제 엔드포인트 주소로 수정해주세요."
        )
        st.error(error_message)
        raise ValueError(error_message)
    return url

def encode_image_to_base64(image_file) -> str:
    """
    Streamlit UploadedFile 객체 (이미지)를 base64 문자열로 인코딩합니다.
    """
    try:
        # UploadedFile에서 바이트 데이터를 가져옵니다.
        img_bytes = image_file.getvalue()
        base64_encoded_str = base64.b64encode(img_bytes).decode('utf-8')
        return base64_encoded_str
    except Exception as e:
        st.error(f"이미지 인코딩 중 오류 발생: {e}")
        raise

def prepare_ocr_payload(image_base64: str, schema_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    OCR 추출을 위한 Hugging Face Inference Endpoint 요청 페이로드를 준비합니다.
    모델(prithivMLmods/Qwen2-VL-OCR2-2B-Instruct)이 기대하는 형식에 맞춰야 합니다.
    일반적으로 이미지와 추출할 스키마 정보를 포함합니다.
    """
    processed_schema = []
    for field in schema_fields:
        if not field.get('key_name') or not str(field['key_name']).strip():
            pass

        processed_schema.append({
            "key": str(field.get('key_name', '')).strip(),
            "description": str(field.get('description', '')),
            "type": str(field.get('data_type', 'String')),
            "is_array": bool(field.get('is_array', False))
        })

    payload = {
        "inputs": {
            "image": image_base64, 
            "schema": processed_schema
        }
    }
    return payload

def call_huggingface_ocr_endpoint(payload: Dict[str, Any], max_retries: int = 3, timeout: int = 30) -> Dict[str, Any]:
    """
    준비된 페이로드로 Hugging Face OCR Inference Endpoint를 호출하고 응답을 반환합니다.
    재시도 로직과 타임아웃을 포함합니다.
    """
    api_key = get_huggingface_api_key() # 정의된 함수 사용
    endpoint_url = get_huggingface_endpoint_url() # 정의된 함수 사용
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    for attempt in range(max_retries):
        try:
            st.info(f"OCR API 호출 중... (시도 {attempt + 1}/{max_retries})") # 사용자 피드백
            response = requests.post(endpoint_url, headers=headers, json=payload, timeout=timeout)
            response.raise_for_status() # 200 OK가 아니면 HTTPError 발생
            
            return response.json() # JSON 응답 반환
            
        except requests.exceptions.Timeout as e:
            st.warning(f"API 호출 시간 초과 (시도 {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                st.error("API 호출 시간 초과. 여러 번 시도했지만 응답을 받지 못했습니다.")
                raise Exception(f"API call timed out after {max_retries} attempts: {e}")
            time.sleep(2 ** attempt) # Exponential backoff: 1, 2, 4초...
            
        except requests.exceptions.HTTPError as e:
            st.error(f"API HTTP 오류 (시도 {attempt + 1}/{max_retries}): {e.response.status_code} - {e.response.text}")
            if e.response.status_code == 401:
                st.error("API 인증 실패 (401): API 키를 확인해주세요.")
                raise Exception(f"API Authentication Error (401): {e.response.text}") from e
            
            if attempt == max_retries - 1:
                st.error(f"API HTTP 오류. 여러 번 시도했지만 실패했습니다: {e.response.status_code}")
                raise Exception(f"API HTTP Error after {max_retries} attempts: {e.response.status_code} - {e.response.text}") from e
            time.sleep(2 ** attempt)

        except requests.exceptions.RequestException as e: # 다른 네트워크 관련 예외
            st.warning(f"API 요청 오류 (시도 {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                st.error("API 요청 오류. 여러 번 시도했지만 실패했습니다.")
                raise Exception(f"API Request Error after {max_retries} attempts: {e}")
            time.sleep(2 ** attempt)
            
        except Exception as e: # 그 외 예외 (예: JSON 디코딩 실패 등 response.json()에서 발생 가능)
            st.error(f"API 호출 중 예상치 못한 오류 발생 (시도 {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                raise Exception(f"Unexpected error during API call after {max_retries} attempts: {e}")
            time.sleep(2 ** attempt)

    st.error("API 호출에 실패했습니다. 모든 재시도가 실패했습니다.")
    raise Exception("API call failed after all retries.")

def parse_ocr_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Hugging Face OCR Inference Endpoint로부터 받은 JSON 응답을 파싱합니다.
    성공적인 응답에서 추출된 데이터를 반환하거나, 오류가 있다면 예외를 발생시킵니다.
    모델(prithivMLmods/Qwen2-VL-OCR2-2B-Instruct)의 실제 응답 구조에 맞춰야 합니다.
    """
    try:
        if isinstance(response, list) and response and "error" in response[0]:
             error_detail = response[0].get("error")
             estimated_time = response[0].get("estimated_time", "N/A")
             st.error(f"API 응답 오류: {error_detail} (예상 처리 시간: {estimated_time}초)")
             raise Exception(f"API Error in response list: {error_detail}")
        
        if "error" in response:
            error_detail = response.get("error")
            warnings = response.get("warnings")
            if warnings:
                st.warning(f"API 응답 경고: {warnings}")
            st.error(f"API 응답 오류: {error_detail}")
            raise Exception(f"API Error: {error_detail}")

        if isinstance(response, list) and response:
            extracted_data = response[0] 
            if isinstance(extracted_data, dict):
                st.success("OCR 결과 파싱 성공!")
                return extracted_data
            else:
                 st.warning(f"API 응답이 예상한 딕셔너리 형태가 아닙니다 (리스트 내 요소): {type(extracted_data)}")
                 if isinstance(extracted_data, str) and "generated_text" in extracted_data:
                     st.info("응답이 'generated_text'를 포함합니다. 추가 파싱이 필요할 수 있습니다.")
                     return {"raw_text_output": extracted_data}

        elif isinstance(response, dict):
            possible_keys = ["extracted_data", "outputs", "predictions", "results"]
            for key in possible_keys:
                if key in response:
                    data = response[key]
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        st.success(f"OCR 결과 파싱 성공 (키: {key})!")
                        return data[0]
                    elif isinstance(data, dict):
                        st.success(f"OCR 결과 파싱 성공 (키: {key})!")
                        return data
            
            if response:
                st.success("OCR 결과 파싱 성공 (응답 전체 사용)!")
                return response 

        st.warning(f"API 응답에서 추출된 데이터를 찾을 수 없거나 예상치 못한 형식입니다. 응답 전체: {response}")
        raise Exception("Failed to find or parse extracted data from API response.")

    except Exception as e:
        st.error(f"OCR 응답 파싱 중 오류 발생: {e}")
        raise Exception(f"Failed to parse OCR response: {e}")

# 함수 테스트용 (직접 실행 시)
if __name__ == "__main__":
    try:
        key = get_huggingface_api_key()
        print(f"API Key: {key}")
        endpoint = get_huggingface_endpoint_url()
        print(f"Endpoint URL: {endpoint}")
    except ValueError as e:
        print(f"Error: {e}")

    class MockUploadedFile:
        def getvalue(self):
            dummy_png_bytes = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
            return dummy_png_bytes

    mock_file = MockUploadedFile()
    try:
        encoded_img = encode_image_to_base64(mock_file)
        print(f"\nEncoded Image (dummy): {encoded_img[:50]}...")

        sample_schema = [
            {'key_name': 'InvoiceNumber', 'description': 'The invoice number', 'data_type': 'String', 'is_array': False, 'id': 0, 'error': None},
            {'key_name': 'TotalAmount', 'description': 'The total amount due', 'data_type': 'Number', 'is_array': False, 'id': 1, 'error': None}
        ]
        payload_data = prepare_ocr_payload(encoded_img, sample_schema)
        print(f"Prepared Payload: {json.dumps(payload_data, indent=2)}")

    except Exception as e:
        print(f"Error in additional tests: {e}")
    
    print("\nSkipping call_huggingface_ocr_endpoint test in direct execution.")

    print("\n--- Testing parse_ocr_response ---")
    
    mock_response_success1 = [{"InvoiceNumber": "INV123", "Total": 100.50}]
    try:
        parsed1 = parse_ocr_response(mock_response_success1)
        print(f"Parsed (Success 1): {parsed1}")
    except Exception as e:
        print(f"Error (Success 1): {e}")

    mock_response_success2 = {"extracted_data": {"Item": "Widget", "Quantity": 5}}
    try:
        parsed2 = parse_ocr_response(mock_response_success2)
        print(f"Parsed (Success 2): {parsed2}")
    except Exception as e:
        print(f"Error (Success 2): {e}")
        
    mock_response_success3 = {"Name": "John Doe", "Email": "john.doe@example.com"}
    try:
        parsed3 = parse_ocr_response(mock_response_success3)
        print(f"Parsed (Success 3): {parsed3}")
    except Exception as e:
        print(f"Error (Success 3): {e}")

    mock_response_error1 = {"error": "Model loading failed", "warnings": ["Deprecated field used"]}
    try:
        parse_ocr_response(mock_response_error1)
    except Exception as e:
        print(f"Caught Error (Error 1): {e}")
        
    mock_response_error2 = [{"error": "Input too long", "estimated_time": 10.5}]
    try:
        parse_ocr_response(mock_response_error2)
    except Exception as e:
        print(f"Caught Error (Error 2): {e}")

    mock_response_unexpected = {"some_other_key": "some_value"}
    try:
        parse_ocr_response(mock_response_unexpected)
    except Exception as e:
        print(f"Caught Error (Unexpected): {e}")
        
    mock_response_empty_list = []
    try:
        parse_ocr_response(mock_response_empty_list)
    except Exception as e:
        print(f"Caught Error (Empty List): {e}") 