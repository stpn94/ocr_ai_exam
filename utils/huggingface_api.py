import os
import streamlit as st
from dotenv import load_dotenv
import base64
from typing import List, Dict, Any # 타입 힌팅용
import json # 테스트용
import requests # API 호출용
import time # 재시도 로직용
import io # BytesIO 사용 위함
import logging # 로깅 추가
import re # re 모듈 import 추가

# 로거 설정 (app.py와 동일한 로거 사용 또는 별도 설정)
logger = logging.getLogger("ocr-extraction-app") # app.py와 동일한 로거 이름 사용

# .env 파일이 있다면 로드 (로컬 개발 시 유용)
load_dotenv()

# freeimage.host API 정보
FREEIMAGE_API_KEY = "6d207e02198a847aa98d0a2a901485a5" # 문서 제공 키, 실제 사용시 환경변수화 권장
FREEIMAGE_UPLOAD_URL = "https://freeimage.host/api/1/upload"

HUGGINGFACE_API_ENDPOINT_URL = "YOUR_HUGGINGFACE_INFERENCE_ENDPOINT_URL_HERE" # 사용자가 생성한 엔드포인트 URL로 대체 필요
# 예시: "https://xyz.eu-west-1.aws.endpoints.huggingface.cloud"
# 또는 특정 모델 경로: "https://api-inference.huggingface.co/models/prithivMLmods/Qwen2-VL-OCR2-2B-Instruct"

def get_freeimage_api_key() -> str:
    """
    Freeimage.host API 키를 환경 변수 또는 기본값에서 가져옵니다.
    실제 운영 시에는 st.secrets 또는 환경 변수를 통해 안전하게 관리하는 것이 좋습니다.
    """
    # 여기서는 문서에 제공된 키를 사용하지만, 실제로는 환경 변수에서 읽도록 수정하는 것이 좋습니다.
    # return os.environ.get("FREEIMAGE_API_KEY", FREEIMAGE_API_KEY)
    return FREEIMAGE_API_KEY # 임시로 하드코딩된 키 사용

def upload_image_to_freeimage(image_bytes: bytes, filename: str = "uploaded_image.png") -> str | None:
    """
    이미지 바이트 데이터를 freeimage.host에 업로드하고 이미지 URL을 반환합니다.
    성공 시 이미지 URL (str), 실패 시 None을 반환합니다.
    filename 파라미터는 freeimage.host API에서 파일명을 지정하기 위해 사용될 수 있습니다.
    """
    logger.info(f"upload_image_to_freeimage 함수 시작. 파일명: {filename}, 이미지 크기: {len(image_bytes)} 바이트")
    api_key = get_freeimage_api_key()
    payload = {
        'key': api_key,
        'format': 'json' 
    }
    files = {
        'source': (filename, image_bytes, 'image/png') # MIME 타입은 실제 이미지에 맞게 조정 필요
    }
    
    try:
        st.info(f"freeimage.host에 '{filename}' 업로드 중...") # 사용자 피드백은 유지
        logger.info(f"freeimage.host API 요청 시작. URL: {FREEIMAGE_UPLOAD_URL}, 페이로드 키: {list(payload.keys())}, 파일명: {filename}")
        response = requests.post(FREEIMAGE_UPLOAD_URL, data=payload, files=files, timeout=(10, 30)) # 연결 10초, 읽기 30초
        logger.info(f"freeimage.host API 응답 받음. 상태 코드: {response.status_code}")
        response.raise_for_status() # HTTP 오류 발생 시 예외 발생
        
        result = response.json()
        logger.debug(f"Freeimage.host JSON 응답: {json.dumps(result, indent=2)}")
        
        if result.get("status_code") == 200 and result.get("image") and result["image"].get("url"):
            image_url = result["image"]["url"]
            st.success(f"이미지 업로드 성공: {image_url}")
            logger.info(f"Freeimage.host 업로드 성공. URL: {image_url}")
            return image_url
        else:
            error_message = result.get("error", {}).get("message", "알 수 없는 오류") if isinstance(result.get("error"), dict) else result.get("status_txt", "알 수 없는 오류")
            st.error(f"freeimage.host 이미지 업로드 실패: {error_message} (상태 코드: {result.get('status_code')})")
            logger.error(f"Freeimage.host 업로드 실패. 메시지: {error_message}, 상태 코드: {result.get('status_code')}, 전체 응답: {result}")
            # st.json(result) # 전체 응답 보여주기 - 필요시 주석 해제
            return None
            
    except requests.exceptions.Timeout as e:
        st.error("freeimage.host 이미지 업로드 시간 초과.")
        logger.error(f"freeimage.host 이미지 업로드 시간 초과: {e}", exc_info=True)
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"freeimage.host 이미지 업로드 HTTP 오류: {e.response.status_code} - {e.response.text[:200]}")
        logger.error(f"freeimage.host 이미지 업로드 HTTP 오류: {e.response.status_code} - {e.response.text}", exc_info=True)
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"freeimage.host 이미지 업로드 요청 오류: {e}")
        logger.error(f"freeimage.host 이미지 업로드 요청 오류: {e}", exc_info=True)
        return None
    except Exception as e:
        st.error(f"freeimage.host 이미지 업로드 중 예상치 못한 오류 발생: {e}")
        logger.error(f"freeimage.host 이미지 업로드 중 예상치 못한 오류: {e}", exc_info=True)
        return None
    finally:
        logger.info("upload_image_to_freeimage 함수 종료.")

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
        "inputs": image_base64, # image_base64 문자열을 직접 할당
        "parameters": {         # schema를 parameters 객체 안으로 이동
            "schema": processed_schema
            # 모델에 따라 여기에 추가적인 파라미터가 필요할 수 있습니다.
            # 예: "task": "document-question-answering" 또는 특정 OCR 작업 관련 파라미터
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

def suggest_schema_from_document(image_input: str, max_retries: int = 3, timeout: int = 60) -> list:
    """
    OpenAI API 호환 형식으로 이미지(base64 데이터 URI 또는 외부 URL)와 프롬프트를 사용하여 
    Hugging Face TGI Endpoint에 스키마 제안 요청을 보낸다.
    모델이 생성한 텍스트에서 JSON 형식의 스키마를 추출하여 반환한다.
    반환값: 제안된 스키마 리스트 (예: [{"key_name": "...", "description": "...", "data_type": "...", "is_array": false}, ...])
    """
    logger.info(f"suggest_schema_from_document 함수 시작. 이미지 입력 타입: {'URL' if image_input.startswith('http') else 'Base64'}")
    api_key = get_huggingface_api_key()
    base_endpoint_url = get_huggingface_endpoint_url().rstrip('/')
    if not base_endpoint_url.endswith('/v1'):
        if not "/v1" in base_endpoint_url.split("/")[-2:]:
             base_endpoint_url += "/v1" 
    
    chat_completions_url = f"{base_endpoint_url}/chat/completions"
    logger.info(f"Hugging Face 스키마 제안 엔드포인트 URL: {chat_completions_url}")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # 스키마 제안을 위한 프롬프트 (apiDocumentExam.md 참조)
    prompt_template = """Please analyze the provided document image and suggest a detailed schema for information extraction. 
Your response should be a valid JSON list of objects. Each object should represent a field to be extracted and must include the following keys: 
'key_name' (string, snake_case, unique identifier for the field, e.g., 'invoice_number'), 
'description' (string, a clear description of what this field represents, e.g., 'The unique identifier for the invoice'), 
'data_type' (string, one of ['String', 'Number', 'Date', 'Boolean'], e.g., 'String'), and 
'is_array' (boolean, true if multiple values can be extracted for this key, false otherwise, e.g., false).

Example for an invoice:
[
  {{"key_name": "invoice_id", "description": "Invoice unique identifier", "data_type": "String", "is_array": false}},
  {{"key_name": "issue_date", "description": "Date the invoice was issued (YYYY-MM-DD)", "data_type": "Date", "is_array": false}},
  {{"key_name": "line_items", "description": "List of items in the invoice", "data_type": "Array", "is_array": true, "sub_schema": [
    {{"key_name": "item_description", "description": "Description of the item", "data_type": "String", "is_array": false}},
    {{"key_name": "quantity", "description": "Quantity of the item", "data_type": "Number", "is_array": false}}
  ]}}
]

Based on the image, provide the schema. Ensure the output is ONLY the JSON list, with no other text before or after it."""

    image_url_content = {"type": "image_url", "image_url": {"url": image_input}}
    
    # OpenAI API 호환 페이로드
    openai_payload = {
        # "model": "tgi", # 엔드포인트가 이미 모델을 특정하므로 제거됨 (이전 수정 사항)
        "messages": [
            {
                "role": "user",
                "content": [
                    image_url_content,
                    {"type": "text", "text": prompt_template}
                ]
            }
        ],
        "max_tokens": 256, # 스키마 제안이므로 이전 2048에서 대폭 줄임 (이전 수정 사항)
        "stream": False # 스트리밍 사용 안 함
        # "temperature": 0.5, # 필요시 추가
    }
    logger.debug(f"Hugging Face API 요청 페이로드 (일부): messages.user.content[1].text 길이: {len(openai_payload['messages'][0]['content'][1]['text'])}, max_tokens: {openai_payload['max_tokens']}")

    for attempt in range(max_retries):
        try:
            st.info(f"스키마 제안 API 호출 중... (시도 {attempt + 1}/{max_retries})")
            logger.info(f"Hugging Face 스키마 제안 API 요청 시작 (시도 {attempt + 1}/{max_retries}). URL: {chat_completions_url}")
            response = requests.post(chat_completions_url, headers=headers, json=openai_payload, timeout=(10, 60)) # 연결 10초, 읽기 60초
            logger.info(f"Hugging Face 스키마 제안 API 응답 받음 (시도 {attempt + 1}/{max_retries}). 상태 코드: {response.status_code}")
            response.raise_for_status()
            
            response_json = response.json()
            logger.debug(f"Hugging Face API JSON 응답 (시도 {attempt + 1}/{max_retries}): {str(response_json)[:500]}...") # 너무 길 수 있어 일부만 로깅

            if "choices" in response_json and response_json["choices"]:
                message_content = response_json["choices"][0].get("message", {}).get("content", "")
                logger.info(f"API 응답에서 추출된 메시지 내용 (길이: {len(message_content)}). 내용 (일부): {message_content[:200]}...")
                
                # 모델이 생성한 텍스트 앞뒤 공백 제거
                message_content = message_content.strip()

                # 중복 중괄호 치환 시도
                # 예: {{key: "value"}} -> {key: "value"}
                # 주의: 이 방식이 모든 경우에 안전하지 않을 수 있으나, 현재 로그 패턴에 기반한 시도입니다.
                if message_content.startswith("[") and message_content.endswith("]"):
                    # 리스트 내부의 객체들에 대해 {{...}} -> {...} 변환 시도
                    # 좀 더 정교한 방법이 필요할 수 있음. 예: 정규식 사용
                    # 단순 문자열 치환은 의도치 않은 결과를 낳을 수 있으므로,
                    # 모델이 일관되게 {{ 와 }} 를 사용한다고 가정하고, 가장 바깥쪽 []는 유지.
                    # 내부의 {{ 를 { 로, }} 를 } 로 변경
                    
                    # 먼저, JSON 마크다운 블록이 있다면 제거
                    if message_content.strip().startswith("```json"):
                        message_content = message_content.strip()[7:-3].strip()
                        logger.info("JSON 마크다운 블록 제거됨 (치환 전).")
                    elif message_content.strip().startswith("```"):
                         message_content = message_content.strip()[3:-3].strip()
                         logger.info("일반 마크다운 블록 제거됨 (치환 전).")

                    # 이중 중괄호 치환
                    # 이 치환은 문자열 전체에 적용되므로, JSON 구조 내 문자열 값에 {{ 또는 }}가 있다면 문제 발생 가능.
                    # 하지만 현재 오류는 키-값 쌍을 정의하는 부분에서의 구조 문제로 보이므로 시도.
                    original_content_for_log = message_content[:200] # 로그용 원본 일부
                    message_content = message_content.replace("{{", "{").replace("}}", "}")
                    if message_content[:200] != original_content_for_log:
                        logger.info(f"이중 중괄호 치환 적용됨. 변경 후 (일부): {message_content[:200]}...")
                    else:
                        logger.info("이중 중괄호 치환이 적용되지 않았거나, 변경 사항 없음.")

                # 모델이 JSON 마크다운 블록으로 응답하는 경우 대비 (```json ... ```)
                if message_content.strip().startswith("```json"):
                    message_content = message_content.strip()[7:-3].strip()
                    logger.info("JSON 마크다운 블록 제거됨.")
                elif message_content.strip().startswith("```"):
                     message_content = message_content.strip()[3:-3].strip()
                     logger.info("일반 마크다운 블록 제거됨.")

                try:
                    # 응답이 순수 JSON 문자열이라고 가정
                    suggested_schema = json.loads(message_content)
                    if isinstance(suggested_schema, list):
                        logger.info(f"성공적으로 스키마 JSON 파싱 완료. {len(suggested_schema)}개의 필드 제안됨.")
                        return suggested_schema
                    else:
                        logger.warning(f"파싱된 스키마가 리스트가 아님: {type(suggested_schema)}. 원본 내용: {message_content[:200]}...")
                        st.warning(f"AI가 반환한 스키마가 예상한 리스트 형태가 아닙니다. (타입: {type(suggested_schema)}) AI 응답을 확인해주세요.")
                        # 모델이 때때로 텍스트 설명을 포함하여 JSON을 반환할 수 있음
                        # 이런 경우, 실제 JSON 부분을 찾아내려는 시도 (매우 기본적인 방법)
                        try:
                            # 가장 큰 JSON 배열 또는 객체를 찾아보려는 시도
                            # 이것은 매우 실험적이며, 모델의 응답 형식에 따라 실패할 가능성이 높음
                            json_like_parts = []
                            # 대괄호로 시작하는 가장 긴 부분
                            match_array = re.search(r'\[\s*\{.*\}\s*\]', message_content, re.DOTALL)
                            if match_array:
                                json_like_parts.append(match_array.group(0))
                            # 중괄호로 시작하는 가장 긴 부분 (단일 객체이고 리스트가 아닌 경우)
                            match_object = re.search(r'\{\s*".*"\s*:\s*".*"\s*\}', message_content, re.DOTALL)
                            if match_object:
                                json_like_parts.append(match_object.group(0))
                            
                            if json_like_parts:
                                longest_part = max(json_like_parts, key=len)
                                logger.info(f"텍스트에서 JSON과 유사한 부분을 찾음 (길이: {len(longest_part)}): {longest_part[:100]}...")
                                re_parsed_schema = json.loads(longest_part)
                                if isinstance(re_parsed_schema, list):
                                    logger.info("재파싱 성공! 스키마 반환.")
                                    return re_parsed_schema
                                elif isinstance(re_parsed_schema, dict) and len(re_parsed_schema) > 0 : # 단일 객체지만 내용이 있다면 리스트로 감싸서 반환
                                     logger.info("단일 객체 재파싱 성공! 리스트로 감싸서 스키마 반환.")
                                     return [re_parsed_schema]
                        except Exception as sub_e:
                            logger.warning(f"메시지 내용에서 JSON 재파싱 시도 중 오류: {sub_e}")
                            pass # 재파싱 실패 시 다음 로직으로 넘어감
                        
                        return [{"error": "Failed to parse schema from AI response", "details": message_content[:500]}]
                except json.JSONDecodeError as json_e:
                    logger.error(f"API 응답 JSON 파싱 실패: {json_e}. 원본 내용: {message_content[:500]}...", exc_info=True)
                    st.error(f"AI 응답을 JSON으로 파싱하는 데 실패했습니다: {json_e}")
                    return [{"error": "JSONDecodeError", "details": message_content[:500]}]
            else:
                logger.warning(f"API 응답에 'choices'가 없거나 비어 있음. 응답: {str(response_json)[:500]}...")
                st.warning("AI로부터 유효한 스키마 제안을 받지 못했습니다. (응답에 'choices' 없음)")
                return [{"error": "No choices in AI response", "details": str(response_json)[:500]}]

        except requests.exceptions.Timeout as e:
            logger.warning(f"Hugging Face API 호출 시간 초과 (시도 {attempt + 1}/{max_retries}): {e}", exc_info=True)
            if attempt == max_retries - 1:
                st.error("스키마 제안 API 호출 시간 초과. 여러 번 시도했지만 응답을 받지 못했습니다.")
                return [{"error": "Timeout", "details": str(e)}]
            time.sleep(2 ** attempt)
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"Hugging Face API HTTP 오류 (시도 {attempt + 1}/{max_retries}): {e.response.status_code} - {e.response.text}", exc_info=True)
            if attempt == max_retries - 1:
                st.error(f"스키마 제안 API HTTP 오류. 여러 번 시도했지만 실패했습니다: {e.response.status_code}")
                return [{"error": f"HTTPError: {e.response.status_code}", "details": e.response.text[:500]}]
            time.sleep(2 ** attempt)

        except requests.exceptions.RequestException as e:
            logger.warning(f"Hugging Face API 요청 오류 (시도 {attempt + 1}/{max_retries}): {e}", exc_info=True)
            if attempt == max_retries - 1:
                st.error("스키마 제안 API 요청 오류. 여러 번 시도했지만 실패했습니다.")
                return [{"error": "RequestException", "details": str(e)}]
            time.sleep(2 ** attempt)
            
        except Exception as e:
            logger.error(f"Hugging Face API 호출 중 예상치 못한 오류 (시도 {attempt + 1}/{max_retries}): {e}", exc_info=True)
            if attempt == max_retries - 1:
                st.error(f"스키마 제안 API 호출 중 예상치 못한 오류 발생: {e}")
                return [{"error": "UnexpectedException", "details": str(e)}]
            time.sleep(2 ** attempt)

    logger.error("스키마 제안 API 호출에 실패했습니다. 모든 재시도가 실패했습니다.")
    st.error("스키마 제안 API 호출에 실패했습니다. 모든 재시도가 실패했습니다.")
    return [{"error": "All retries failed"}]

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