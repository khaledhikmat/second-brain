import os
import tempfile
import shutil
from google import genai

def generate_generic_long_summary(pdf_path: str):
    """
    Uploads an Arabic PDF document to the Gemini API and generates a detailed,
    long-form structural summary in professional Arabic.
    """
    # 1. Initialize the client.
    # Expects the GEMINI_API_KEY environment variable to be set.
    client = genai.Client()

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"The file at {pdf_path} could not be found.")

    # 2. Upload the file using the File API.
    # This natively handles massive files up to 2GB.
    # To handle Unicode filenames (e.g., Arabic), we create a temporary copy with ASCII-safe name
    original_name = os.path.basename(pdf_path)
    print(f"Uploading '{original_name}' to Gemini File API...")

    # Create temporary file with ASCII-safe name
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', prefix='gemini_upload_') as tmp_file:
        temp_path = tmp_file.name

    try:
        # Copy the original file to temp location
        shutil.copy2(pdf_path, temp_path)

        # Upload using the temp file (ASCII-safe path)
        uploaded_file = client.files.upload(file=temp_path)
        print(f"Upload complete. Remote File Name: {uploaded_file.name}")

        # 3. Generic, highly-structured prompt for comprehensive document synthesis.
        # It instructs the model to translate complex book architectures into
        # an exhaustive, long-form summary in Arabic.
        prompt = """
        You are an expert academic research analyst fluent in classical and professional Arabic text synthesis.
        Please read the attached Arabic PDF document meticulously and generate an exhaustive,
        long-form structural summary written entirely in formal, professional Arabic.

        Your output must strictly follow this detailed structure:

        1. **Context & Methodological Framework (مقدمة وسياق النص)**:
           Detail the background of the text, its foundational scope, the central thesis,
           and the main objectives or research questions the author sets out to investigate.

        2. **Core Pillars & Primary Themes (المحاور والأركان الرئيسية)**:
           Provide a high-level breakdown of the primary theoretical concepts, arguments,
           or structural divisions established by the author.

        3. **Exhaustive Chapter/Chronological Breakdown (التفكيك التحليلي المفصل)**:
           Go through the text dynamically (either chapter-by-chapter, phase-by-phase, or section-by-section).
           Summarize the progression of arguments, explicit data points, interactions,
           and logical sub-conclusions. Avoid high-level generalities; capture the specific sub-arguments
           and detailed evidence presented within the text.

        4. **Analytical Synthesis & Strategic Verdicts (خلاصات ورؤى نقدية)**:
           Synthesize the overarching insights, paradoxes, rules, or core patterns that emerge
           when connecting the different sections of the document together.

        5. **Final Prescriptions & Conclusion (النتائج والتوصيات الختامية)**:
           Summarize the author's final conclusions, ultimate prescriptions, or future recommendations
           as explicitly detailed in the closing portions of the document.

        Ensure your analysis is deeply rooted in the text without inserting external commentary or outside assumptions.
        """

        # 4. Invoke the model.
        # We use 'gemini-3.5-flash' (June 2026) for its deep context reasoning
        # and superior cross-referencing capabilities over long texts.
        print("Analyzing document and generating long-form summary (this may take a moment)...")

        try:
            response = client.models.generate_content(
                model='gemini-3.5-flash',
                contents=[uploaded_file, prompt]
            )

            # 5. Output the result
            print("\n" + "="*40 + "\n GENERATED ARABIC SUMMARY \n" + "="*40 + "\n")
            print(response.text)

            # 6. Write summary to output.md in the same folder as the PDF
            output_folder = os.path.dirname(pdf_path) or '.'
            output_path = os.path.join(output_folder, 'output.md')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"\n✓ Summary written to: {output_path}")

        except Exception as e:
            print(f"An error occurred during generation: {e}")

        finally:
            # 7. Cleanup remote storage.
            # Deleting the file from the API server after processing frees up your project storage quota.
            print("\nCleaning up remote file asset...")
            client.files.delete(name=uploaded_file.name)
            print("Remote cleanup successful.")

    finally:
        # 8. Cleanup temporary local file
        if os.path.exists(temp_path):
            os.unlink(temp_path)
            print("Temporary file cleanup successful.")

if __name__ == "__main__":
    # Path to the Arabic PDF file to summarize
    target_pdf = "./book2.pdf"

    generate_generic_long_summary(target_pdf)