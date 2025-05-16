import streamlit as st
from PIL import Image
import PyPDF2 # PyPDF2 주석 해제
from pdf2image import convert_from_bytes # pdf2image import
import io

MAX_FILE_SIZE_MB = 5 # 최대 파일 크기 5MB
ALLOWED_IMAGE_TYPES = ["png", "jpg", "jpeg"]
ALLOWED_PDF_TYPES = ["pdf"]
ALLOWED_TYPES = ALLOWED_IMAGE_TYPES + ALLOWED_PDF_TYPES

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
        st.header("스키마 설정 및 추출 결과")
        # 스키마 입력 및 결과 표시는 다른 작업에서 구현
        st.markdown("_(스키마 설정 및 추출 결과는 여기에 표시됩니다.)_")

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