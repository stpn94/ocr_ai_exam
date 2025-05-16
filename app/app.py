import streamlit as st
from PIL import Image
import PyPDF2 # PyPDF2 주석 해제
from pdf2image import convert_from_bytes # pdf2image import
import io
import json # 스키마 export/import용
import datetime # 파일명에 타임스탬프 추가용
import time
import pandas as pd  # 결과 테이블 표시용
# --- 에러 핸들링/로깅 관련 추가 import ---
import logging
import traceback
from functools import wraps
import utils.huggingface_api as hf_api  # 자동 스키마 제안 함수 사용
import os
import base64
import requests
import uuid # For unique keys for schema fields

from dotenv import load_dotenv # .env 파일 로드용

# .env 파일에서 환경 변수 로드
load_dotenv()

# --- 페이지 설정 (스크립트 최상단으로 이동) ---
st.set_page_config(layout="wide", page_title="OCR 문서 정보 추출")

# --- 로깅 설정 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ocr-extraction-app")

# --- 중앙 집중 에러 핸들러 데코레이터 ---
def handle_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_id = int(time.time())
            error_details = traceback.format_exc()
            logger.error(f"Error ID: {error_id}")
            logger.error(f"Function: {func.__name__}")
            logger.error(f"Error: {str(e)}")
            logger.error(f"Details: {error_details}")
            # 세션 상태에 에러 로그 저장
            if 'errors' not in st.session_state:
                st.session_state.errors = []
            st.session_state.errors.append({
                "id": error_id,
                "function": func.__name__,
                "error": str(e),
                "details": error_details,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            # 사용자 친화적 에러 메시지
            error_message = get_user_friendly_error_message(e)
            st.error(f"Error: {error_message} (ID: {error_id})")
            # 디버그 모드일 때만 상세 정보
            if 'debug_mode' in st.session_state and st.session_state.debug_mode:
                with st.expander("Technical Details"):
                    st.code(error_details)
            else:
                st.info("상세 에러 정보는 사이드바 Debug Mode에서 확인할 수 있습니다.")
    return wrapper

# --- 사용자 친화적 에러 메시지 변환 ---
def get_user_friendly_error_message(error):
    error_str = str(error).lower()
    if "api key" in error_str:
        return "API 인증에 실패했습니다. API 키를 확인하세요."
    if "timeout" in error_str or "connection" in error_str:
        return "OCR 서비스 연결에 실패했습니다. 잠시 후 다시 시도하세요."
    if "rate limit" in error_str or "too many requests" in error_str:
        return "OCR 서비스가 혼잡합니다. 잠시 후 다시 시도하세요."
    if "file" in error_str and ("not found" in error_str or "invalid" in error_str):
        return "업로드된 파일에 문제가 있습니다. 다른 파일로 시도해보세요."
    if "pdf" in error_str and "corrupt" in error_str:
        return "PDF 파일이 손상된 것 같습니다. 다른 파일로 시도해보세요."
    if "schema" in error_str and "invalid" in error_str:
        return "추출 스키마가 올바르지 않습니다. 스키마 정의를 확인하세요."
    return "예상치 못한 오류가 발생했습니다. 다시 시도하거나 관리자에게 문의하세요."

# --- Debug 모드/에러 로그 사이드바 UI ---
def debug_mode_section():
    st.sidebar.header("Developer Options")
    if 'debug_mode' not in st.session_state:
        st.session_state.debug_mode = False
    st.session_state.debug_mode = st.sidebar.checkbox("Debug Mode", st.session_state.debug_mode)
    if st.session_state.debug_mode:
        st.sidebar.subheader("Error Log")
        if 'errors' in st.session_state and st.session_state.errors:
            for error in reversed(st.session_state.errors):
                with st.sidebar.expander(f"Error ID: {error['id']} - {error['timestamp']}"):
                    st.write(f"Function: {error['function']}")
                    st.write(f"Error: {error['error']}")
                    st.code(error['details'])
        else:
            st.sidebar.info("No errors logged.")
        # 에러 로그 초기화 버튼
        if st.sidebar.button("Clear Error Log") and 'errors' in st.session_state:
            st.session_state.errors = []
            st.sidebar.success("Error log cleared.")
        # 로그 레벨 선택
        log_level = st.sidebar.selectbox(
            "Log Level",
            ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            index=1
        )
        current_level = logging.getLevelName(logger.level)
        if log_level != current_level:
            logger.setLevel(getattr(logging, log_level))
            st.sidebar.success(f"Log level changed to {log_level}")

# --- 도움말/문서화 섹션 --- (신규 추가)
@handle_error
def render_help_section():
    st.sidebar.title("💡 도움말 및 정보")
    with st.sidebar.expander("자주 묻는 질문 (FAQ)", expanded=False):
        st.markdown(
            """
            **Q: 어떤 파일 형식을 지원하나요?**
            A: PNG, JPG, JPEG 이미지 파일과 PDF 문서를 지원합니다.

            **Q: 추출 정확도는 어느 정도인가요?**
            A: 문서 품질과 내용의 명확성에 따라 다릅니다. 고품질 스캔 문서에서 더 좋은 결과를 얻을 수 있습니다.

            **Q: 데이터는 안전하게 처리되나요?**
            A: 문서는 추출을 위해 일시적으로 처리되며, 영구적으로 저장되지 않습니다. (실제 API 연동 시 개인정보보호 정책 확인 필요)

            **Q: 여러 문서를 한 번에 처리할 수 있나요?**
            A: 네, '배치 문서 업로드' 기능을 통해 여러 문서를 큐에 추가하고 순차적으로 처리할 수 있습니다.

            **Q: 스키마는 어떻게 작성해야 하나요?**
            A: 추출하려는 정보의 `Key name`(필드명), `Description`(AI에게 전달할 설명), `Type`(데이터 타입)을 명확히 정의해야 합니다. '스키마 자동 생성' 기능을 사용하면 AI가 문서 내용을 기반으로 스키마를 제안해줍니다.
            """
        )
    with st.sidebar.expander("예제 스키마 (송장)", expanded=False):
        st.json([
            {"key_name": "invoice_number", "description": "송장 번호", "data_type": "String", "is_array": False, "id": 0, "error": None},
            {"key_name": "issue_date", "description": "발행일 (YYYY-MM-DD 형식)", "data_type": "Date", "is_array": False, "id": 1, "error": None},
            {"key_name": "total_amount", "description": "총액 (숫자만)", "data_type": "Number", "is_array": False, "id": 2, "error": None}
        ])
    with st.sidebar.expander("Poppler 설치 안내 (PDF 미리보기)", expanded=False):
        st.markdown(
            """
            PDF 미리보기 기능을 사용하려면 Poppler 유틸리티가 필요합니다.
            - **Windows:** [여기에서 다운로드](https://github.com/oschwartz10612/poppler-windows/releases/) 후, 압축 해제한 폴더의 `bin` 디렉토리를 시스템 PATH 환경 변수에 추가하세요.
            - **macOS (Homebrew 사용):** `brew install poppler`
            - **Linux (apt 사용):** `sudo apt-get install poppler-utils`
            """
        )

MAX_FILE_SIZE_MB = 5 # 최대 파일 크기 5MB
ALLOWED_IMAGE_TYPES = ["png", "jpg", "jpeg"]
ALLOWED_PDF_TYPES = ["pdf"]
ALLOWED_TYPES = ALLOWED_IMAGE_TYPES + ALLOWED_PDF_TYPES

# --- Constants ---
MAX_IMAGE_RESIZE_DIMENSION = 1024 # 이미지 리사이징 시 최대 크기 (픽셀)

def render_schema_input_area():
    # "스키마 설정" 제목, (선택적) 전체 오류 메시지, "필드 추가" 버튼을 한 줄에 배치
    col_title_error, col_add_button = st.columns([3, 1]) # 비율 조정 가능

    with col_title_error:
        st.header("스키마 설정")

    with col_add_button:
        if st.button("➕ 필드 추가", key="add_field_top_button", help="새로운 스키마 필드를 추가합니다."):
            new_id = 0
            if 'schema_fields' in st.session_state and st.session_state.schema_fields: 
                new_id = max(f['id'] for f in st.session_state.schema_fields) + 1
            else:
                st.session_state.schema_fields = [] # schema_fields가 없을 경우 초기화
            st.session_state.schema_fields.append(
                {'key_name': '', 'description': '', 'data_type': 'String', 'is_array': False, 'id': new_id, 'error': None}
            )
            st.rerun()

    if 'schema_fields' not in st.session_state:
        st.session_state.schema_fields = [
            {'key_name': '', 'description': '', 'data_type': 'String', 'is_array': False, 'id': 0, 'error': None}
        ]
    
    for i in reversed(range(len(st.session_state.schema_fields))):
        field = st.session_state.schema_fields[i]
        field_id = field['id']

        key_name_is_empty = not field['key_name'].strip()
        if key_name_is_empty:
            field['error'] = "Key name은 필수 항목입니다." # 오류 상태는 유지 (다른 로직에서 사용될 수 있음)
        elif field.get('error') == "Key name은 필수 항목입니다.": # Key name이 채워졌으면 해당 오류는 제거
            field['error'] = None

        # 아이콘을 위한 열 추가: Icon, KeyName, Description, Type, Array, Delete
        icon_col, key_col, desc_col, type_col, array_col, del_col = st.columns(
            [0.7, 3, 4, 2, 1.5, 1.5], 
            vertical_alignment="center"
        ) 
        
        with icon_col:
            if key_name_is_empty:
                # 아이콘과 툴팁 표시 (수직 정렬을 위해 padding-top 또는 div style 조정 -> vertical_alignment로 대체)
                st.markdown(
                    "<div style='text-align: center;'>"  # padding-top 제거
                    "<span title='Key name은 필수 항목입니다.' style='color:red; font-size:20px;'>❗️</span>"
                    "</div>", 
                    unsafe_allow_html=True
                )
        
        with key_col:
            field['key_name'] = st.text_input(
                "Key name*", 
                field['key_name'], 
                key=f"key_{field_id}",
                placeholder="예: Shipper"
            )
            # Key name 필드 바로 아래에 "Key name은 필수 항목입니다." 이외의 오류만 표시
            if field.get('error') and field['error'] != "Key name은 필수 항목입니다.":
                 st.error(field['error'])

        with desc_col:
            field['description'] = st.text_input(
                "Description", 
                field['description'], 
                key=f"desc_{field_id}",
                placeholder="예: 수출자 상호 및 주소"
            )
        
        with type_col:
            field['data_type'] = st.selectbox(
                "Type", 
                options=['String', 'Number', 'Date', 'Boolean'], 
                index=['String', 'Number', 'Date', 'Boolean'].index(field['data_type']), 
                key=f"type_{field_id}"
            )

        with array_col:
            field['is_array'] = st.checkbox(
                "Array", 
                field['is_array'], 
                key=f"array_{field_id}",
                help="이 키에 여러 값이 추출될 수 있습니까?"
            )
        
        with del_col:
            if st.button("➖", key=f"del_{field_id}", help="이 필드를 삭제합니다."):
                st.session_state.schema_fields.pop(i)
                st.rerun()

    st.markdown("---")

    col_btn2, col_btn3, col_btn4, col_btn5 = st.columns(4)
    
    with col_btn2:
        if st.button("🔄 스키마 초기화 (Reset Schema)"):
            st.session_state.schema_fields = [
                {'key_name': '', 'description': '', 'data_type': 'String', 'is_array': False, 'id': 0, 'error': None}
            ]
            st.rerun() 
    
    with col_btn3:
        if 'schema_fields' in st.session_state and st.session_state.schema_fields:
            try:
                schema_to_export = st.session_state.schema_fields
                schema_json = json.dumps(schema_to_export, indent=2, ensure_ascii=False)
                
                now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                file_name = f"extraction_schema_{now}.json"

                st.download_button(
                    label="💾 스키마 내보내기",
                    data=schema_json,
                    file_name=file_name,
                    mime="application/json",
                    help="현재 정의된 스키마를 JSON 파일로 다운로드합니다."
                )
            except Exception as e:
                st.error(f"스키마 내보내기 준비 중 오류: {e}")
        else:
            st.button("💾 스키마 내보내기", disabled=True, help="내보낼 스키마가 없습니다.")

    with col_btn4:
        st.write(" ") 
        st.write(" ") 
        st.markdown("###### JSON 가져오기:")
        
    with col_btn5:
        uploaded_schema_file = st.file_uploader("스키마 JSON 업로드", type=["json"], key="schema_import_uploader")
        if uploaded_schema_file is not None:
            try:
                imported_schema = json.load(uploaded_schema_file)
                def validate_imported_schema(schema):
                    if not isinstance(schema, list):
                        return False, "스키마는 리스트(JSON 배열)여야 합니다."
                    for idx, field in enumerate(schema):
                        if not isinstance(field, dict):
                            return False, f"{idx+1}번째 항목이 객체가 아닙니다."
                        for k in ["key_name", "description", "data_type", "is_array"]:
                            if k not in field:
                                return False, f"{idx+1}번째 항목에 '{k}' 필드가 없습니다."
                        if not isinstance(field["key_name"], str) or not field["key_name"].strip(): # 공백 허용 안 함
                            return False, f"{idx+1}번째 항목의 key_name이 올바르지 않습니다."
                        if not isinstance(field["description"], str):
                            return False, f"{idx+1}번째 항목의 description이 문자열이 아닙니다."
                        if field["data_type"] not in ["String", "Number", "Date", "Boolean"]:
                            return False, f"{idx+1}번째 항목의 data_type이 올바르지 않습니다."
                        if not isinstance(field["is_array"], bool):
                            return False, f"{idx+1}번째 항목의 is_array가 bool 타입이 아닙니다."
                    return True, None
                is_valid, err_msg = validate_imported_schema(imported_schema)
                if is_valid:
                    for i_field, field_data in enumerate(imported_schema):
                        field_data.setdefault("id", i_field)
                        field_data["error"] = None
                    st.session_state.schema_fields = imported_schema
                    st.success("스키마가 성공적으로 적용되었습니다!")
                    st.rerun()
                else:
                    st.error(f"스키마 파일 형식 오류: {err_msg}")
            except json.JSONDecodeError:
                st.error("유효하지 않은 JSON 파일입니다. 올바른 스키마 파일을 업로드하세요.")
            except Exception as e:
                st.error(f"스키마 import 중 오류: {e}")

def validate_uploaded_file(uploaded_file):
    if uploaded_file is None:
        return False, "문서를 먼저 업로드하세요."
    file_size_bytes = uploaded_file.size
    file_size_mb = file_size_bytes / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        return False, f"파일 크기 초과: 업로드된 파일({file_size_mb:.2f}MB)이 최대 허용 크기({MAX_FILE_SIZE_MB}MB)를 초과합니다."
    file_type_simple = uploaded_file.type.split('/')[-1].lower()
    if file_type_simple not in ALLOWED_TYPES:
        return False, f"지원하지 않는 파일 형식입니다: {file_type_simple}"
    return True, None

def validate_schema(schema_fields):
    if not schema_fields or len(schema_fields) == 0:
        return False, "스키마에 최소 1개 이상의 필드가 필요합니다."
    for idx, field in enumerate(schema_fields):
        if not field.get('key_name') or not str(field['key_name']).strip():
            return False, f"{idx+1}번째 필드의 Key name이 비어 있습니다."
        if field.get('data_type') not in ['String', 'Number', 'Date', 'Boolean']:
            return False, f"{idx+1}번째 필드의 Type이 올바르지 않습니다."
    return True, None

def display_json_view(results):
    """Display results in JSON format with syntax highlighting"""
    if results is None:
        st.warning("표시할 JSON 데이터가 없습니다.")
        return

    try:
        json_str = json.dumps(results, indent=2, ensure_ascii=False)
        st.code(json_str, language="json")

        # Copy button for JSON
        if st.button("JSON 복사", key=f"copy_json_{uuid.uuid4()}"):
            # Use JavaScript to copy to clipboard (Streamlit's recommended way for complex data)
            st.components.v1.html(
                f"<script>navigator.clipboard.writeText({json.dumps(json_str)});</script>",
                height=0,
            )
            st.success("JSON이 클립보드에 복사되었습니다!")

        # Download button
        st.download_button(
            label="JSON 다운로드",
            data=json_str,
            file_name="extraction_results.json",
            mime="application/json",
            key=f"download_json_{uuid.uuid4()}"
        )
    except TypeError as e:
        st.error(f"JSON 직렬화 중 오류 발생: {e}")
        st.write("원본 데이터:")
        st.write(results)
    except Exception as e:
        st.error(f"JSON 표시 중 예기치 않은 오류 발생: {e}")

def display_preview_table(results):
    """Display results in a table format"""
    if results is None:
        st.warning("표시할 미리보기 데이터가 없습니다.")
        return

    try:
        if isinstance(results, dict):
            df = pd.DataFrame(list(results.items()), columns=['필드', '값'])
            st.dataframe(df, use_container_width=True)
            csv_data = df.to_csv(index=False).encode('utf-8')
            file_label = "테이블 데이터"
        elif isinstance(results, list) and results and all(isinstance(item, dict) for item in results):
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)
            csv_data = df.to_csv(index=False).encode('utf-8')
            file_label = "테이블 데이터"
        elif isinstance(results, list):
            st.write(results)
            csv_data = pd.Series(results).to_csv(index=False).encode('utf-8') # Convert list to CSV
            file_label = "리스트 데이터"
        else:
            st.write(str(results))
            csv_data = str(results).encode('utf-8') # Convert simple types to CSV
            file_label = "데이터"
        
        # Copy button for table data (copies as CSV)
        if st.button(f"{file_label} CSV로 복사", key=f"copy_csv_{uuid.uuid4()}"):
            st.components.v1.html(
                f"<script>navigator.clipboard.writeText({json.dumps(csv_data.decode('utf-8'))});</script>",
                height=0,
            )
            st.success(f"{file_label}이(가) CSV 형식으로 클립보드에 복사되었습니다!")

        # Download button for table data (downloads as CSV)
        st.download_button(
            label=f"{file_label} 다운로드 (.csv)",
            data=csv_data,
            file_name="extraction_results.csv",
            mime="text/csv",
            key=f"download_csv_{uuid.uuid4()}"
        )
    except Exception as e:
        st.error(f"미리보기 테이블 표시 중 오류 발생: {e}")
        st.write("원본 데이터:")
        st.write(results)

def display_results():
    """추출 결과를 Preview(테이블)와 JSON 탭으로 표시 + 복사/다운로드 기능"""
    if 'extraction_results' not in st.session_state or not st.session_state['extraction_results']:
        st.info("아직 추출 결과가 없거나, 추출에 실패했습니다.")
        return
    results = st.session_state['extraction_results']
    st.header("추출 결과")
    preview_tab, json_tab = st.tabs(["Preview", "JSON"])
    with preview_tab:
        display_preview_table(results)
    with json_tab:
        display_json_view(results)

@handle_error
def display_image_preview(uploaded_file):
    try:
        image = Image.open(uploaded_file)
        # 원본 이미지 표시 (use_column_width=True로 컬럼 너비에 맞춤)
        st.image(image, caption=f"미리보기: {uploaded_file.name}", use_container_width=True)
        # (선택적) 썸네일 표시 예시 (예: 너비 200px)
        # st.image(image, caption=f"썸네일: {uploaded_file.name}", width=200)
        # (참고) 라이트박스/모달, 확대/축소/회전은 Streamlit 기본 기능으로 어렵습니다.
        # 필요시 HTML/JS 컴포넌트 연동 또는 외부 라이브러리 고려 (MVP 이후)
    except Exception as e:
        st.error(f"이미지 미리보기를 표시하는 중 오류가 발생했습니다: {e}")

@handle_error
def display_pdf_preview(uploaded_file):
    try:
        pdf_bytes = uploaded_file.getvalue()
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        num_pages = len(pdf_reader.pages)
        st.write(f"PDF 미리보기 ({num_pages} 페이지)")
        # --- 멀티페이지 썸네일/슬라이더/선택 ---
        if 'current_page' not in st.session_state:
            st.session_state.current_page = 1
        if 'selected_pages' not in st.session_state:
            st.session_state.selected_pages = [1]
        if 'pdf_thumbnails' not in st.session_state:
            st.session_state.pdf_thumbnails = {}
        
        # 페이지 네비게이션 UI
        if num_pages > 1:
            col_prev, col_slider, col_next = st.columns([1, 6, 1])
            with col_prev:
                if st.button("◀", key=f"pdf_prev_{uploaded_file.name}") and st.session_state.current_page > 1:
                    st.session_state.current_page -= 1
            with col_slider:
                st.session_state.current_page = st.slider(
                    "페이지 이동",
                    min_value=1,
                    max_value=num_pages, # num_pages가 1일 경우 min과 max가 같아 오류 발생
                    value=st.session_state.current_page,
                    key=f"pdf_page_slider_{uploaded_file.name}"
                )
            with col_next:
                if st.button("▶", key=f"pdf_next_{uploaded_file.name}") and st.session_state.current_page < num_pages:
                    st.session_state.current_page += 1
        elif num_pages == 1:
            st.session_state.current_page = 1 # 페이지가 1개일 경우 현재 페이지는 항상 1
            # 슬라이더를 표시하지 않거나, st.write 등으로 페이지 정보만 표시
            st.write("단일 페이지 PDF입니다.")

        # 썸네일 생성 및 캐싱
        cur_page = st.session_state.current_page
        if cur_page not in st.session_state.pdf_thumbnails:
            with st.spinner(f"페이지 {cur_page} 썸네일 생성 중..."):
                images = convert_from_bytes(pdf_bytes, first_page=cur_page, last_page=cur_page, dpi=100)
                if images:
                    st.session_state.pdf_thumbnails[cur_page] = images[0]
                    # 생성된 PIL 이미지를 세션 상태에 저장
                    if uploaded_file.name in st.session_state.pdf_preview_states:
                        st.session_state.pdf_preview_states[uploaded_file.name]['current_page_pil'] = images[0]
                        st.session_state.pdf_preview_states[uploaded_file.name]['current_page_for_display'] = cur_page # 현재 페이지 번호(1-indexed)도 저장
                        logger.info(f"PDF 페이지 {cur_page}의 PIL 이미지를 세션 상태(pdf_preview_states['{uploaded_file.name}']['current_page_pil'])에 저장했습니다.")
                    else:
                        logger.warning(f"세션 상태에 pdf_preview_states['{uploaded_file.name}'] 키가 없어 PIL 이미지를 저장하지 못했습니다.")
        
        # 저장된 PIL 이미지 사용 (썸네일 표시와 별개로, 스키마 제안 등 다른 곳에서 사용 위함)
        # current_page_pil_for_later_use = None
        # if uploaded_file.name in st.session_state.pdf_preview_states and \\
        #    st.session_state.pdf_preview_states[uploaded_file.name].get('current_page_pil'):
        #     current_page_pil_for_later_use = st.session_state.pdf_preview_states[uploaded_file.name]['current_page_pil']
        #     # logger.debug(f"세션에서 '{uploaded_file.name}'의 current_page_pil 가져옴: {current_page_pil_for_later_use is not None}")


        if cur_page in st.session_state.pdf_thumbnails:
            if st.session_state.pdf_thumbnails[cur_page]:
                st.image(st.session_state.pdf_thumbnails[cur_page], caption=f"페이지 {cur_page} / {num_pages}", use_container_width=True) # 페이지 번호 0-indexed에서 1-indexed로 변경된 것 반영
            else:
                st.warning("PDF 페이지 썸네일을 생성하지 못했습니다.")
        # 멀티페이지 선택 옵션
        st.markdown("---")
        st.subheader(":bookmark_tabs: 추출 대상 페이지 선택")
        extraction_option = st.radio(
            "추출 대상",
            ["현재 페이지만", "여러 페이지 선택", "전체 페이지"],
            index=0,
            key=f"pdf_extract_option_{uploaded_file.name}"
        )
        if extraction_option == "현재 페이지만":
            st.session_state.selected_pages = [cur_page]
        elif extraction_option == "여러 페이지 선택":
            st.session_state.selected_pages = st.multiselect(
                "추출할 페이지를 선택하세요",
                options=list(range(1, num_pages+1)),
                default=[cur_page],
                key=f"pdf_page_multiselect_{uploaded_file.name}"
            )
        elif extraction_option == "전체 페이지":
            st.session_state.selected_pages = list(range(1, num_pages+1))
        st.info(f"선택된 추출 대상 페이지: {st.session_state.selected_pages}")
    except PyPDF2.errors.PdfReadError:
        st.error("PDF 파일을 읽는 중 오류가 발생했습니다. 파일이 암호화되었거나 손상되었을 수 있습니다.")
    except Exception as e:
        st.error(f"PDF 미리보기 중 예상치 못한 오류 발생: {e}")

@handle_error
def render_auto_schema_section(current_selected_doc=None):
    logger.info("render_auto_schema_section 시작")
    st.subheader("📜 스키마 자동 생성 (AI 제안)")

    if not current_selected_doc:
        st.info("문서 큐에서 스키마를 제안받을 문서를 먼저 선택해주세요.")
        logger.info("선택된 현재 문서 없음, 함수 종료.")
        return

    doc_name = current_selected_doc.name
    session_key_inprogress = f'auto_schema_in_progress_{doc_name}'
    session_key_suggested_schema = f'suggested_schema_{doc_name}' # 새 세션 키

    logger.debug(f"문서명: {doc_name}, 진행 키: {session_key_inprogress}, 제안 키: {session_key_suggested_schema}")

    if session_key_inprogress not in st.session_state:
        st.session_state[session_key_inprogress] = False
        logger.info(f"{session_key_inprogress} 세션 상태 초기화: False")
    if session_key_suggested_schema not in st.session_state:
        st.session_state[session_key_suggested_schema] = None # 제안된 스키마 저장용
        logger.info(f"{session_key_suggested_schema} 세션 상태 초기화: None")

    # 1. 이전에 제안된 스키마가 있고, 아직 처리되지 않았다면 먼저 보여주고 선택 옵션 제공
    if st.session_state[session_key_suggested_schema] is not None:
        logger.info(f"'{doc_name}'에 대해 이전에 제안된 스키마가 존재합니다. 사용자 선택 대기 중.")
        
        # 제안된 스키마가 빈 리스트인 경우 (AI가 제안할 것을 찾지 못한 경우)
        if not st.session_state[session_key_suggested_schema]: # 빈 리스트 체크
            st.info("AI가 문서에서 제안할 스키마를 찾지 못했습니다.")
            if st.button("확인", key=f"confirm_no_suggestion_{doc_name}"):
                st.session_state[session_key_suggested_schema] = None # 확인 후 초기화
                st.session_state[session_key_inprogress] = False
                logger.info(f"'{doc_name}' 빈 스키마 제안 확인됨. {session_key_suggested_schema} 초기화.")
                st.rerun()
            return

        # 제안된 스키마가 있는 경우 (오류 객체가 아닌 실제 스키마)
        st.success(f"AI가 '{doc_name}' 문서를 기반으로 스키마를 제안했습니다. 아래 옵션 중 하나를 선택하세요.")
        suggested_schema_to_display = st.session_state[session_key_suggested_schema]

        col1, col2, col3_spacer = st.columns([2,2,4]) 
        with col1:
            if st.button("덮어쓰기", key=f"overwrite_schema_{doc_name}_final", help="현재 스키마를 AI 제안으로 완전히 대체합니다."):
                st.session_state.schema_fields = [] 
                for i, field_suggestion in enumerate(suggested_schema_to_display):
                    # 오류 객체가 아닌 경우에만 필드 추가
                    if isinstance(field_suggestion, dict) and "error" not in field_suggestion:
                        st.session_state.schema_fields.append({
                            'key_name': field_suggestion.get('key_name', f'field_{i}'),
                            'description': field_suggestion.get('description', ''),
                            'data_type': field_suggestion.get('data_type', 'String'),
                            'is_array': field_suggestion.get('is_array', False),
                            'id': get_new_schema_field_id(),
                            'error': None
                        })
                st.toast("AI 제안 스키마로 덮어썼습니다.")
                st.session_state[session_key_suggested_schema] = None 
                st.session_state[session_key_inprogress] = False 
                logger.info(f"'{doc_name}' 스키마 덮어쓰기 완료. {session_key_suggested_schema} 초기화됨.")
                st.rerun() 
        with col2:
            if st.button("병합하기", key=f"merge_schema_{doc_name}_final", help="현재 스키마에 AI 제안 중 새로운 필드만 추가합니다."):
                existing_key_names = {f['key_name'] for f in st.session_state.get('schema_fields', []) if f['key_name']}
                merged_count = 0
                for field_suggestion in suggested_schema_to_display:
                     # 오류 객체가 아니고, 유효한 key_name이 있으며, 기존에 없는 key_name인 경우
                    if isinstance(field_suggestion, dict) and "error" not in field_suggestion:
                        suggested_key = field_suggestion.get('key_name')
                        if suggested_key and suggested_key not in existing_key_names:
                            st.session_state.schema_fields.append({
                                'key_name': suggested_key,
                                'description': field_suggestion.get('description', ''),
                                'data_type': field_suggestion.get('data_type', 'String'),
                                'is_array': field_suggestion.get('is_array', False),
                                'id': get_new_schema_field_id(),
                                'error': None
                            })
                            existing_key_names.add(suggested_key)
                            merged_count += 1
                st.toast(f"{merged_count}개의 새 필드를 병합했습니다.")
                st.session_state[session_key_suggested_schema] = None 
                st.session_state[session_key_inprogress] = False 
                logger.info(f"'{doc_name}' 스키마 병합 완료. {merged_count}개 추가. {session_key_suggested_schema} 초기화됨.")
                st.rerun() 

        st.subheader("AI 제안 스키마 미리보기:")
        st.json(suggested_schema_to_display)
        return 

    # 2. 스키마 자동 제안 버튼 및 진행 로직
    logger.debug(f"현재 {session_key_inprogress} 상태: {st.session_state[session_key_inprogress]}")
    button_clicked = st.button(f"\'{doc_name}\'에서 스키마 자동 제안", 
                               key=f"auto_schema_btn_{doc_name}", 
                               disabled=st.session_state[session_key_inprogress],
                               help="선택된 문서(PDF의 경우 현재 페이지만 해당)를 기반으로 AI가 스키마를 제안합니다.")

    if button_clicked:
        logger.info(f"\'{doc_name}\' 스키마 자동 제안 버튼 클릭됨.")
        st.session_state[session_key_inprogress] = True
        logger.info(f"{session_key_inprogress} 상태 변경: True")
        st.session_state[session_key_suggested_schema] = None 
        logger.info(f"{session_key_suggested_schema} 초기화됨 (새 제안 시작).")
        st.rerun() 

    if st.session_state[session_key_inprogress]:
        logger.info(f"{session_key_inprogress}가 True이므로 스키마 자동 생성 로직 실행 시작.")
        st.info(f"\'{doc_name}\'에 대한 스키마 자동 생성 작업을 시작합니다...")
        
        action_completed_or_error = False 
        suggested_data_from_api = None

        with st.spinner(f"\'{doc_name}\' 처리 중... (이미지 준비, 업로드 및 AI 분석)"):
            try:
                image_bytes_to_upload = None
                upload_filename = doc_name
                logger.info("이미지 바이트 및 파일명 초기화 완료.")

                if current_selected_doc.type.startswith("image/"):
                    logger.info(f"선택된 문서 타입: 이미지 ({current_selected_doc.type})")
                    image_bytes_to_upload = current_selected_doc.getvalue()
                    logger.info(f"이미지 바이트 가져오기 완료 (크기: {len(image_bytes_to_upload)} 바이트).")
                elif current_selected_doc.type == "application/pdf":
                    logger.info(f"선택된 문서 타입: PDF ({current_selected_doc.type})")
                    if doc_name in st.session_state.pdf_preview_states and \
                       st.session_state.pdf_preview_states[doc_name].get('current_page_pil'):
                        pil_img_pdf = st.session_state.pdf_preview_states[doc_name]['current_page_pil']
                        current_page_display = st.session_state.pdf_preview_states[doc_name].get('current_page_for_display', 'current')
                        logger.info(f"PDF 현재 페이지 PIL 이미지 가져옴 (페이지: {current_page_display}).")
                        img_byte_arr = io.BytesIO()
                        pil_img_pdf.save(img_byte_arr, format='PNG') # PDF 페이지는 PNG로 변환
                        image_bytes_to_upload = img_byte_arr.getvalue()
                        upload_filename = f"{os.path.splitext(doc_name)[0]}_page_{current_page_display}.png"
                        logger.info(f"PDF 페이지를 PNG 바이트로 변환 완료 (크기: {len(image_bytes_to_upload)} 바이트, 파일명: {upload_filename}).")
                    else:
                        st.error("PDF 미리보기에서 현재 페이지 이미지를 찾을 수 없습니다.")
                        logger.warning("PDF 미리보기에서 current_page_pil을 찾을 수 없음.")
                        action_completed_or_error = True # 오류로 간주
                        st.session_state[session_key_suggested_schema] = [{"error": "PDF page image not found"}] # 오류 정보 저장
                        # 여기서 바로 rerun하지 않고 finally에서 처리하도록 함
                
                if not image_bytes_to_upload and not action_completed_or_error: # action_completed_or_error가 True면 이미 오류 처리중
                    st.error("스키마 제안을 위한 이미지 데이터를 준비할 수 없습니다.")
                    action_completed_or_error = True
                    st.session_state[session_key_suggested_schema] = [{"error": "Image data preparation failed"}]


                if image_bytes_to_upload and not action_completed_or_error:
                    pil_image_for_resize = Image.open(io.BytesIO(image_bytes_to_upload))
                    pil_image_for_resize.thumbnail((MAX_IMAGE_RESIZE_DIMENSION, MAX_IMAGE_RESIZE_DIMENSION), Image.Resampling.LANCZOS)
                    resized_image_io = io.BytesIO()
                    
                    # 원본 파일명의 확장자를 유지하거나, PNG로 통일
                    original_extension = os.path.splitext(upload_filename)[1].lower()
                    save_format = 'PNG' # 기본은 PNG
                    if original_extension in ['.jpg', '.jpeg']:
                        save_format = 'JPEG'
                    
                    try:
                        pil_image_for_resize.save(resized_image_io, format=save_format)
                    except Exception as save_err: # JPEG 저장 실패 등 예외 처리
                        logger.warning(f"이미지 저장 형식 {save_format} 실패 ({save_err}), PNG로 재시도.")
                        save_format = 'PNG'
                        # 파일명 확장자도 PNG로 변경
                        base_name, _ = os.path.splitext(upload_filename)
                        upload_filename = base_name + ".png"
                        resized_image_io = io.BytesIO() # clear previous buffer
                        pil_image_for_resize.save(resized_image_io, format=save_format)

                    resized_image_bytes = resized_image_io.getvalue()
                    st.info(f"이미지 리사이징 완료. 새 크기: {pil_image_for_resize.width}x{pil_image_for_resize.height}, 저장 형식: {save_format}")

                    image_url_for_suggestion = hf_api.upload_image_to_freeimage(resized_image_bytes, filename=upload_filename)

                    if not image_url_for_suggestion:
                        st.error("이미지 업로드 실패. 스키마 제안을 진행할 수 없습니다.")
                        action_completed_or_error = True
                        st.session_state[session_key_suggested_schema] = [{"error": "Image upload failed"}]
                    else:
                        suggested_data_from_api = hf_api.suggest_schema_from_document(image_url_for_suggestion)
                        action_completed_or_error = True 
                    
                        if isinstance(suggested_data_from_api, list) and suggested_data_from_api and not any(isinstance(item, dict) and "error" in item for item in suggested_data_from_api):
                            logger.info(f"API로부터 스키마 제안 받음: {len(suggested_data_from_api)}개 필드")
                            st.session_state[session_key_suggested_schema] = suggested_data_from_api
                        elif isinstance(suggested_data_from_api, list) and not suggested_data_from_api: # 빈 리스트도 정상 응답으로 간주
                            logger.info("API가 빈 스키마 리스트를 제안했습니다 (제안할 항목 없음).")
                            st.session_state[session_key_suggested_schema] = [] 
                        else: # 오류 객체 리스트 또는 예상치 못한 형식
                            error_detail = str(suggested_data_from_api)
                            st.error(f"스키마 자동 제안에 실패했습니다. AI 응답: {error_detail[:200]}...")
                            logger.error(f"스키마 자동 제안 실패. API 응답: {error_detail}")
                            # 오류 정보를 포함한 객체를 저장하여 사용자에게 보여줄 수 있도록 함
                            if isinstance(suggested_data_from_api, list) and suggested_data_from_api and isinstance(suggested_data_from_api[0], dict) and "error" in suggested_data_from_api[0]:
                                st.session_state[session_key_suggested_schema] = suggested_data_from_api 
                            else:
                                st.session_state[session_key_suggested_schema] = [{"error": "AI schema suggestion failed", "details": error_detail[:200]}]


            except Exception as e:
                logger.error(f"Error during auto schema suggestion for {doc_name}: {traceback.format_exc()}")
                st.error(f"\'{doc_name}\'에서 스키마를 자동으로 제안하는 중 오류가 발생했습니다: {e}")
                action_completed_or_error = True 
                st.session_state[session_key_suggested_schema] = [{"error": "Unexpected exception during schema suggestion", "details": str(e)[:200]}]
            finally:
                if action_completed_or_error and st.session_state[session_key_inprogress]:
                    st.session_state[session_key_inprogress] = False
                    logger.info(f"{session_key_inprogress} False로 변경됨 (finally 블록). 제안된 스키마 상태: {st.session_state.get(session_key_suggested_schema)}")
                    st.rerun() 

def get_new_schema_field_id():
    # Ensure schema_fields list exists in session_state
    if 'schema_fields' not in st.session_state:
        st.session_state.schema_fields = []
    
    if not st.session_state.schema_fields:  # If the list is empty
        return 0  # Start IDs from 0
    else:
        # If the list has items, find the max ID and add 1
        return max(field['id'] for field in st.session_state.schema_fields) + 1

@handle_error
def main():
    debug_mode_section()  # 사이드바 Debug/에러 로그 항상 표시
    render_help_section() # 사이드바 도움말 섹션 표시
    st.title("OCR 문서 정보 추출 시스템")
    
    # 1. 문서 업로드 및 미리보기 섹션 (기존 col1 내용)
    st.header("문서 업로드 및 미리보기")
    st.subheader("배치 문서 업로드")
    # 세션 상태 초기화
    if 'document_queue' not in st.session_state:
        st.session_state.document_queue = []
    if 'current_document_index' not in st.session_state:
        st.session_state.current_document_index = 0
    if 'batch_results' not in st.session_state:
        st.session_state.batch_results = []
    
    uploaded_files = st.file_uploader(
        "여기에 여러 문서를 드래그 앤 드롭하거나 클릭하여 업로드하세요.",
        type=ALLOWED_TYPES,
        accept_multiple_files=True,
        key="batch_uploader",
        help=f"지원 파일 형식: {', '.join(ALLOWED_TYPES)}. 최대 파일 크기: {MAX_FILE_SIZE_MB}MB. PDF의 경우 Poppler 설치가 필요할 수 있습니다."
    )

    if uploaded_files:
        valid_files_for_queue = []
        for up_file in uploaded_files:
            is_valid, msg = validate_uploaded_file(up_file)
            if is_valid:
                valid_files_for_queue.append(up_file)
            else:
                st.error(f"{up_file.name}: {msg}")
        
        if valid_files_for_queue:
            st.session_state.document_queue = valid_files_for_queue
            st.session_state.current_document_index = 0
            st.session_state.batch_results = [] 
            st.success(f"{len(st.session_state.document_queue)}개 문서가 큐에 추가되었습니다.")
        else:
            st.warning("유효한 파일이 없어 큐에 추가되지 않았습니다.")

    if st.session_state.document_queue:
        st.write(f"**문서 큐:** 총 {len(st.session_state.document_queue)}개")
        for i, doc in enumerate(st.session_state.document_queue):
            status_icon = "✅" if i < len(st.session_state.batch_results) and not st.session_state.batch_results[i].get("error") else \
                            "❌" if i < len(st.session_state.batch_results) and st.session_state.batch_results[i].get("error") else "⌛"
            st.write(f"{i+1}. {doc.name} {status_icon}")

        doc_names = [doc.name for doc in st.session_state.document_queue]
        
        if not (0 <= st.session_state.current_document_index < len(doc_names)):
            st.session_state.current_document_index = 0

        selected_idx = st.selectbox(
            "미리볼 문서 선택",
            options=list(range(len(doc_names))),
            format_func=lambda i: f"{i+1}. {doc_names[i]}",
            index=st.session_state.current_document_index,
            key="doc_nav_selectbox"
        )
        st.session_state.current_document_index = selected_idx
        
        if st.session_state.document_queue and 0 <= selected_idx < len(st.session_state.document_queue):
            selected_doc_for_preview = st.session_state.document_queue[selected_idx]
            file_type_simple = selected_doc_for_preview.type.split('/')[-1].lower()
            st.markdown(f"**선택 문서 미리보기:** {selected_doc_for_preview.name}")
            
            if file_type_simple in ALLOWED_PDF_TYPES:
                if 'pdf_preview_states' not in st.session_state:
                    st.session_state.pdf_preview_states = {}
                if selected_doc_for_preview.name not in st.session_state.pdf_preview_states:
                    st.session_state.pdf_preview_states[selected_doc_for_preview.name] = {
                        'current_page': 1,
                        'selected_pages': [1],
                        'pdf_thumbnails': {}
                    }
                st.session_state.current_page = st.session_state.pdf_preview_states[selected_doc_for_preview.name]['current_page']
                st.session_state.selected_pages = st.session_state.pdf_preview_states[selected_doc_for_preview.name]['selected_pages']
                st.session_state.pdf_thumbnails = st.session_state.pdf_preview_states[selected_doc_for_preview.name]['pdf_thumbnails']

            if file_type_simple in ALLOWED_IMAGE_TYPES:
                display_image_preview(selected_doc_for_preview)
            elif file_type_simple in ALLOWED_PDF_TYPES:
                display_pdf_preview(selected_doc_for_preview) 
                if selected_doc_for_preview.name in st.session_state.pdf_preview_states:
                    st.session_state.pdf_preview_states[selected_doc_for_preview.name]['current_page'] = st.session_state.current_page
                    st.session_state.pdf_preview_states[selected_doc_for_preview.name]['selected_pages'] = st.session_state.selected_pages
                    st.session_state.pdf_preview_states[selected_doc_for_preview.name]['pdf_thumbnails'] = st.session_state.pdf_thumbnails
            else:
                st.warning("지원하지 않는 파일 형식입니다.")

        if st.button("다음 문서 처리", key="process_next_doc_btn"):
            idx_to_process = len(st.session_state.batch_results)
            if idx_to_process < len(st.session_state.document_queue):
                doc_to_process = st.session_state.document_queue[idx_to_process]
                with st.spinner(f"'{doc_to_process.name}' 처리 중... ({idx_to_process + 1}/{len(st.session_state.document_queue)})"):
                    time.sleep(2) 
                    
                    if doc_to_process.name.lower().startswith('fail'):
                        st.session_state.batch_results.append({"filename": doc_to_process.name, "error": "모의 추출 실패"})
                        st.error(f"'{doc_to_process.name}' 처리 실패!")
                    else:
                        mock_result = {"mock_data": f"'{doc_to_process.name}'의 추출 결과"}
                        st.session_state.batch_results.append({"filename": doc_to_process.name, "data": mock_result})
                        st.success(f"'{doc_to_process.name}' 처리 완료!")
                    st.rerun() 
            
            if len(st.session_state.batch_results) == len(st.session_state.document_queue):
                st.info("모든 문서가 처리되었습니다!")
        
        if st.session_state.document_queue and 0 <= st.session_state.current_document_index < len(st.session_state.document_queue):
            current_doc_for_single_extraction = st.session_state.document_queue[st.session_state.current_document_index]
            schema_fields_for_single_extraction = st.session_state.get('schema_fields', [])
            
            file_valid_single, file_msg_single = validate_uploaded_file(current_doc_for_single_extraction)
            schema_valid_single, schema_msg_single = validate_schema(schema_fields_for_single_extraction)

            extract_single_btn_disabled = not (file_valid_single and schema_valid_single)
            extract_single_help_msg = "현재 선택된 문서와 스키마가 모두 유효해야 추출이 가능합니다."
            if not file_valid_single:
                extract_single_help_msg += f" 파일 문제: {file_msg_single}"
            if not schema_valid_single:
                extract_single_help_msg += f" 스키마 문제: {schema_msg_single}"

            if st.button(f"'{current_doc_for_single_extraction.name}' 정보 추출 시작", 
                         disabled=extract_single_btn_disabled, 
                         help=extract_single_help_msg,
                         key="extract_current_doc_btn"):
                try:
                    with st.spinner(f"'{current_doc_for_single_extraction.name}'에서 정보 추출 중..."):
                        # API 키 유효성 검사는 utils/huggingface_api.py 내부에서 수행됨
                        # schema_fields_for_single_extraction는 이미 상단에서 정의됨
                        
                        # 스키마 유효성 재확인 (버튼 활성화 로직과 별개로 실제 실행 직전 확인)
                        schema_is_valid, schema_err_msg = validate_schema(schema_fields_for_single_extraction)
                        if not schema_is_valid:
                            st.error(f"스키마 오류: {schema_err_msg}")
                            st.stop()

                        file_bytes = current_doc_for_single_extraction.getvalue()
                        file_type = current_doc_for_single_extraction.type
                        doc_name_for_extraction = current_doc_for_single_extraction.name
                        
                        extraction_result = {}

                        if "pdf" in file_type.lower():
                            logger.info(f"PDF 파일 '{doc_name_for_extraction}' 추출 시작.")
                            # PDF 페이지 선택 정보 가져오기
                            pages_to_process = [1] # 기본값: 첫 페이지
                            if 'pdf_preview_states' in st.session_state and doc_name_for_extraction in st.session_state.pdf_preview_states:
                                pages_to_process = st.session_state.pdf_preview_states[doc_name_for_extraction].get('selected_pages', [1])
                            
                            if not pages_to_process:
                                st.warning("추출할 PDF 페이지가 선택되지 않았습니다. 첫 페이지만 처리합니다.")
                                pages_to_process = [1]
                            
                            logger.info(f"추출 대상 PDF 페이지: {pages_to_process}")
                            
                            pdf_page_results = {}
                            total_pages_to_process = len(pages_to_process)
                            for i, page_num in enumerate(pages_to_process):
                                st.info(f"PDF '{doc_name_for_extraction}'의 {page_num} 페이지 처리 중... ({i+1}/{total_pages_to_process})")
                                try:
                                    page_images = convert_from_bytes(file_bytes, first_page=page_num, last_page=page_num, dpi=200) # DPI는 필요에 따라 조정
                                    if page_images:
                                        pil_image = page_images[0]
                                        img_byte_arr = io.BytesIO()
                                        pil_image.save(img_byte_arr, format='PNG') # API가 PNG를 선호한다고 가정
                                        image_base64_for_api = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
                                        
                                        payload = hf_api.prepare_ocr_payload(image_base64_for_api, schema_fields_for_single_extraction)
                                        logger.debug(f"페이지 {page_num} API 요청 페이로드 준비 완료.")
                                        api_response = hf_api.call_huggingface_ocr_endpoint(payload)
                                        logger.debug(f"페이지 {page_num} API 응답 받음.")
                                        page_result = hf_api.parse_ocr_response(api_response)
                                        pdf_page_results[f"page_{page_num}"] = page_result
                                        logger.info(f"'{doc_name_for_extraction}' {page_num} 페이지 처리 완료.")
                                    else:
                                        logger.error(f"'{doc_name_for_extraction}' {page_num} 페이지 이미지 변환 실패.")
                                        pdf_page_results[f"page_{page_num}"] = {"error": f"Page {page_num} image conversion failed"}
                                except Exception as page_e:
                                    logger.error(f"'{doc_name_for_extraction}' {page_num} 페이지 처리 중 오류: {page_e}")
                                    pdf_page_results[f"page_{page_num}"] = {"error": f"Error processing page {page_num}: {str(page_e)}"}
                            
                            if total_pages_to_process == 1 and pages_to_process: # 단일 페이지만 추출한 경우
                                extraction_result = pdf_page_results.get(f"page_{pages_to_process[0]}", {"error": "Result not found for single page PDF extraction"})
                            else: # 여러 페이지 결과
                                extraction_result = pdf_page_results

                        elif file_type.startswith("image/"):
                            logger.info(f"이미지 파일 '{doc_name_for_extraction}' 추출 시작.")
                            image_base64_for_api = base64.b64encode(file_bytes).decode('utf-8')
                            payload = hf_api.prepare_ocr_payload(image_base64_for_api, schema_fields_for_single_extraction)
                            logger.debug("이미지 API 요청 페이로드 준비 완료.")
                            api_response = hf_api.call_huggingface_ocr_endpoint(payload)
                            logger.debug("이미지 API 응답 받음.")
                            extraction_result = hf_api.parse_ocr_response(api_response)
                            logger.info(f"이미지 파일 '{doc_name_for_extraction}' 처리 완료.")
                        else:
                            st.error(f"지원하지 않는 파일 형식입니다: {file_type}")
                            st.session_state.extraction_results = {"error": f"Unsupported file type: {file_type}"}
                            st.stop()

                        st.session_state.extraction_results = extraction_result 
                        st.success(f"'{doc_name_for_extraction}' 정보 추출이 완료되었습니다!")
                        st.rerun() 
                except Exception as e:
                    st.session_state.extraction_results = None 
                    error_id = int(time.time()) 
                    logger.error(f"Single extraction error ID {error_id}: {e}\\n{traceback.format_exc()}")
                    st.error(f"'{current_doc_for_single_extraction.name}' 추출 중 오류 발생: {get_user_friendly_error_message(e)} (ID: {error_id})")

    st.markdown("---") # 구분선

    # 2. 스키마 설정 (기존 col2 내용 일부)
    render_schema_input_area() 
    st.markdown("---") # 구분선
    
    # 3. 스키마 자동 생성 (기존 col2 내용 일부)
    current_selected_doc_for_auto_schema = None
    if st.session_state.document_queue and 0 <= st.session_state.current_document_index < len(st.session_state.document_queue):
        current_selected_doc_for_auto_schema = st.session_state.document_queue[st.session_state.current_document_index]
    render_auto_schema_section(current_selected_doc_for_auto_schema)
    st.markdown("---") # 구분선

    # 4. 개별 추출 결과 표시 (기존 col2 내용 일부)
    display_results()
    st.markdown("---") # 구분선

    # 5. 배치 결과 집계/다운로드/개별 확인 UI (기존 col2 내용 일부)
    if st.session_state.get('batch_results'):
        st.markdown("---")
        st.subheader(":inbox_tray: 배치 처리 결과 요약")
        doc_names = [r.get("filename", f"문서{i+1}") for i, r in enumerate(st.session_state.batch_results)]
        selected_idx = st.selectbox(
            "결과를 확인할 문서 선택",
            options=list(range(len(doc_names))),
            format_func=lambda i: f"{i+1}. {doc_names[i]}",
            key="batch_result_selectbox"
        )
        result = st.session_state.batch_results[selected_idx]
        st.markdown(f"**문서명:** {result.get('filename','-')}")
        if 'error' in result:
            st.error(f"처리 실패: {result['error']}")
        else:
            # Preview/JSON 탭으로 결과 표시 (display_results() 활용 불가 시 직접 구현)
            preview_tab, json_tab = st.tabs(["Preview", "JSON"])
            with preview_tab:
                data = result.get('data', {})
                if isinstance(data, dict):
                    df = pd.DataFrame(list(data.items()), columns=["필드", "값"])
                    st.dataframe(df, use_container_width=True)
                elif isinstance(data, list) and data and isinstance(data[0], dict):
                    df = pd.DataFrame(data)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.write(data)
            with json_tab:
                import json
                json_str = json.dumps(data, ensure_ascii=False, indent=2)
                st.json(data, expanded=True)
                st.download_button(
                    label="이 문서 결과 JSON 다운로드",
                    data=json_str,
                    file_name=f"{result.get('filename','result')}_result.json",
                    mime="application/json"
                )
        # 전체 결과 다운로드
        all_results_json = json.dumps(st.session_state.batch_results, ensure_ascii=False, indent=2)
        st.download_button(
            label=":package: 전체 배치 결과 JSON 다운로드",
            data=all_results_json,
            file_name="batch_extraction_results.json",
            mime="application/json"
        )

if __name__ == "__main__":
    main() 