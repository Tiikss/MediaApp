import os
import tempfile
from typing import List, Any
from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from langchain_core.documents import Document


class DocumentProcessor:

    def __init__(self):
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.generate_picture_images = True
        pipeline_options.images_scale = 2.0 

        self.converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
        )

    def process_uploaded_files(self, uploaded_files) -> tuple[List[Document], List[Any]]:
        documents = []
        docling_docs = []
        temp_dir = tempfile.mkdtemp()

        try:
            for uploaded_file in uploaded_files:
                print(f"Obrađuje se {uploaded_file.name}...")

                temp_file_path = os.path.join(temp_dir, uploaded_file.name)
                with open(temp_file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                try:
                    result = self.converter.convert(temp_file_path)

                    markdown_content = result.document.export_to_markdown()

                    doc = Document(
                        page_content=markdown_content,
                        metadata={
                            "filename": uploaded_file.name,
                            "file_type": uploaded_file.type,
                            "source": uploaded_file.name,
                        },
                    )
                    documents.append(doc)

                    print(f"Uspješno obrađen fajl: {uploaded_file.name}.")

                except Exception as e:
                    print(f"Greška prilikom obrade fajla {uploaded_file.name}: {str(e)}.")
                    continue

        finally:
            try:
                import shutil

                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"Upozorenje: Nije moguće obrisati privremeni folder: {str(e)}.")

        print(f"{len(documents)} fajl(ova) je uspješno obrađen(o).")
        return documents, docling_docs
