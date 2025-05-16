import streamlit as st
from PIL import Image
import PyPDF2 # PyPDF2 주석 해제
from pdf2image import convert_from_bytes # pdf2image import
import io

MAX_FILE_SIZE_MB = 5 # 최대 파일 크기 5MB
ALLOWED_IMAGE_TYPES = ["png", "jpg", "jpeg"]
ALLOWED_PDF_TYPES = ["pdf"]
ALLOWED_TYPES = ALLOWED_IMAGE_TYPES + ALLOWED_PDF_TYPES

def render_schema_input_area():
    st.header("스키마 설정")

    # 세션 상태에 스키마 필드가 없으면 초기화
    if 'schema_fields' not in st.session_state:
        st.session_state.schema_fields = [
            {'key_name': '', 'description': '', 'data_type': 'String', 'is_array': False, 'id': 0, 'error': None} # 'error' 필드 추가
        ]
    
    # 각 스키마 필드 렌더링
    # 필드 삭제 기능을 위해 각 필드에 고유 ID 부여 및 역순 순회 (삭제 시 인덱스 문제 방지)
    for i in reversed(range(len(st.session_state.schema_fields))):
        field = st.session_state.schema_fields[i]
        field_id = field['id'] # 고유 ID 사용

        cols = st.columns([3, 4, 2, 1, 1]) # Key, Description, Type, Array, Delete
        
        field['key_name'] = cols[0].text_input(
            "Key name*", # 필수 필드 표시
            field['key_name'], 
            key=f"key_{field_id}",
            placeholder="예: Shipper"
        )
        # Key name 유효성 검사
        if not field['key_name'].strip(): # 앞뒤 공백 제거 후 비어있는지 확인
            field['error'] = "Key name은 필수 항목입니다."
        else:
            field['error'] = None # 오류 없는 경우 None으로 설정

        field['description'] = cols[1].text_input(
            "Description", 
            field['description'], 
            key=f"desc_{field_id}",
            placeholder="예: 수출자 상호 및 주소"
        )
        field['data_type'] = cols[2].selectbox(
            "Type", 
            options=['String', 'Number', 'Date', 'Boolean'], 
            index=['String', 'Number', 'Date', 'Boolean'].index(field['data_type']), 
            key=f"type_{field_id}"
        )
        field['is_array'] = cols[3].checkbox(
            "Array", 
            field['is_array'], 
            key=f"array_{field_id}",
            help="이 키에 여러 값이 추출될 수 있습니까?"
        )
        
        # 필드 삭제 버튼
        if cols[4].button("➖", key=f"del_{field_id}", help="이 필드를 삭제합니다."):
            st.session_state.schema_fields.pop(i)
            st.rerun() # 삭제 후 UI 즉시 업데이트

        # 필드 아래에 오류 메시지 표시
        if field.get('error'): # field 딕셔너리에 'error' 키가 없을 수도 있으므로 .get() 사용
            cols[0].error(field['error']) # Key name 입력란 아래에 오류 표시

    st.markdown("---") # 구분선

    # 버튼들을 한 줄에 배치하기 위해 컬럼 사용
    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("➕ 필드 추가 (Add Field)"):
            new_id = 0
            if st.session_state.schema_fields: # 기존 필드가 있으면 ID 계산
                new_id = max(f['id'] for f in st.session_state.schema_fields) + 1
            
            st.session_state.schema_fields.append(
                {'key_name': '', 'description': '', 'data_type': 'String', 'is_array': False, 'id': new_id, 'error': None} # 'error' 필드 추가
            )
            st.rerun() # 추가 후 UI 즉시 업데이트
    
    with col_btn2:
        if st.button("🔄 스키마 초기화 (Reset Schema)"):
            st.session_state.schema_fields = [
                {'key_name': '', 'description': '', 'data_type': 'String', 'is_array': False, 'id': 0, 'error': None}
            ]
            st.rerun() # 초기화 후 UI 즉시 업데이트
    
    # (참고) 현재 스키마 데이터 보기 (디버깅용)
    # st.subheader("Current Schema Data (for debugging):")
    # st.json(st.session_state.schema_fields)

def main():
    st.set_page_config(layout="wide") # 넓은 레이아웃 사용
    st.title("OCR 문서 정보 추출 시스템")
    
    # PRD에 명시된 좌우 2단 레이아웃
    col1, col2 = st.columns([2, 3]) # 좌측(업로드/미리보기)을 조금 더 좁게
    
    with col1:
        st.header("문서 업로드 및 미리보기")
        
        uploaded_file = st.file_uploader(
            "여기에 문서를 드래그 앤 드롭하거나 클릭하여 업로드하세요.",
            type=ALLOWED_TYPES,
            accept_multiple_files=False, # MVP에서는 단일 파일만 처리
            help=f"지원 파일 형식: {', '.join(ALLOWED_TYPES)}. 최대 파일 크기: {MAX_FILE_SIZE_MB}MB"
        )
        
        if uploaded_file is not None:
            # 파일 크기 검증
            file_size_bytes = uploaded_file.size
            file_size_mb = file_size_bytes / (1024 * 1024)

            if file_size_mb > MAX_FILE_SIZE_MB:
                st.error(f"파일 크기 초과: 업로드된 파일({file_size_mb:.2f}MB)이 최대 허용 크기({MAX_FILE_SIZE_MB}MB)를 초과합니다.")
            else:
                st.success(f"파일 업로드 성공: {uploaded_file.name} ({file_size_mb:.2f}MB)")
                
                # 파일 유형에 따른 처리 (다음 하위 작업에서 구체화)
                file_type_simple = uploaded_file.type.split('/')[-1].lower()

                if file_type_simple in ALLOWED_IMAGE_TYPES:
                    display_image_preview(uploaded_file)
                elif file_type_simple in ALLOWED_PDF_TYPES:
                    display_pdf_preview(uploaded_file)
                else:
                    # 이 경우는 file_uploader의 type 매개변수로 인해 발생하지 않아야 함
                    st.warning("지원하지 않는 파일 형식입니다.")

    with col2:
        render_schema_input_area() # 스키마 입력 UI 렌더링
        
        st.header("추출 결과") # 추출 결과 헤더 추가
        st.markdown("_(추출 결과는 여기에 표시됩니다.)_") # 임시 텍스트 유지

# 이미지 미리보기 함수 (Subtask 2.2에서 구체화)
def display_image_preview(uploaded_file):
    try:
        image = Image.open(uploaded_file)
        
        # 원본 이미지 표시 (use_column_width=True로 컬럼 너비에 맞춤)
        st.image(image, caption=f"미리보기: {uploaded_file.name}", use_column_width=True)
        
        # (선택적) 썸네일 표시 예시 (예: 너비 200px)
        # st.image(image, caption=f"썸네일: {uploaded_file.name}", width=200)

        # (참고) 라이트박스/모달, 확대/축소/회전은 Streamlit 기본 기능으로 어렵습니다.
        # 필요시 HTML/JS 컴포넌트 연동 또는 외부 라이브러리 고려 (MVP 이후)

    except Exception as e:
        st.error(f"이미지 미리보기를 표시하는 중 오류가 발생했습니다: {e}")

# PDF 미리보기 함수 (Subtask 2.3에서 구체화)
def display_pdf_preview(uploaded_file):
    try:
        pdf_bytes = uploaded_file.getvalue()
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        num_pages = len(pdf_reader.pages)

        st.write(f"PDF 미리보기 ({num_pages} 페이지)")

        if num_pages > 0:
            page_number_to_display = st.number_input(
                "페이지 선택하여 미리보기", 
                min_value=1, 
                max_value=num_pages, 
                value=1, 
                key=f"pdf_page_nav_{uploaded_file.name}" 
            )
            
            with st.spinner(f"{page_number_to_display} 페이지를 로드하는 중..."): # 로딩 스피너 추가
                try:
                    images_from_page = convert_from_bytes(
                        pdf_bytes,
                        dpi=200,
                        first_page=page_number_to_display,
                        last_page=page_number_to_display,
                    )
                    
                    if images_from_page:
                        st.image(images_from_page[0], caption=f"{uploaded_file.name} - 페이지 {page_number_to_display}", use_column_width=True)
                    else:
                        st.warning("선택한 페이지를 미리보기 이미지로 변환할 수 없습니다. 파일이 손상되었거나 지원하지 않는 형식일 수 있습니다.")

                except Exception as conversion_error:
                    st.error(f"PDF 페이지 변환 오류: {conversion_error}")
                    st.info("Poppler 유틸리티 설치 및 PATH 설정을 확인해주세요. (자세한 내용은 앱 설명서 또는 FAQ 참고 - 추후 추가)")
        else:
            st.warning("PDF 파일에 내용(페이지)이 없습니다.")
            
    except PyPDF2.errors.PdfReadError: # 구체적인 PDF 읽기 오류 처리
        st.error("PDF 파일을 읽는 중 오류가 발생했습니다. 파일이 암호화되었거나 손상되었을 수 있습니다.")
    except Exception as e:
        st.error(f"PDF 미리보기 중 예상치 못한 오류 발생: {e}")

if __name__ == "__main__":
    main() 