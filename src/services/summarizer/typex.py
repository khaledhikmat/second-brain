import json
from datetime import datetime
from typing import Dict, List, Protocol, Optional, Any
from pydantic import BaseModel

class SummarizerResult(BaseModel):
    """
    Represents the result of a summarization process.
    """
    category: str
    channel: str
    language: str
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    concepts: Optional[List[str]] = None
    entities: Optional[Dict[str, List[str]]] = None
    summary: Optional[str] = None
    wikilinks: Optional[List[str]] = None
    content: Optional[str] = None
    translations: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None
    processedAt: Optional[str] = None

class ISummarizerService(Protocol):
    """Protocol defining the summarizer service interface."""

    async def summarize(
            self,
            channel: str,
            message: str,
            category: str,
            language: str = None,
            specified_title: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None
        ) -> Optional [SummarizerResult]:        
        """
        Process an incoming message and create a summary.

        Args:
            channel: The channel to which the summary belongs
            message: The message content
            category: The category of the note
            language: The language of the message
            specified_title: The title of the summary (if specified)
            metadata: Optional dictionary containing additional metadata for the note
        """
        ...

##############################################
## common functions used by all summarizers ##
##############################################

def produce_summarization_prompt(category: str, language: str, message: str, skip_summarization: bool = False):
    prompt = f"""You are an expert knowledge curator. Analyze the following {language} text and extract structured information.

Text to analyze:
{message}

{"User specified category: " + category if category else ""}

Please provide a JSON response with the following structure:"""

    # Build JSON structure based on category
    json_structure = {
        "title": "A concise, descriptive title for this note",
        "tags": ["max", "5", "relevant", "tags"],
        "concepts": ["max", "5", "key", "concepts"],
        "entities": {
            "people": ["max 5 people mentioned"],
            "places": ["max 5 places mentioned"],
            "terms": ["max 5 important terms"]
        },
        "summary": "A detailed summary",
        "wikilinks": ["Terms that should be wikilinked (max 10)"],
        "content": "The original text formatted in Obsidian markdown with appropriate headers, wikilinks, and structure"
    }

    # Only include category field if user specified it
    if category:
        json_structure["category"] = category
    else:
        # Don't include category in JSON - we'll force it to "Jots" later
        pass

    # Add translations for Arabic notes
    if language == "ar":
        json_structure["translations"] = {"term in Arabic": "English translation - Only for Arabic notes, translate max 5 key terms to English"}

    # Add key_terms and comparison_table for non-Sayings/Poetry categories
    if not skip_summarization:
        translation_lang = "English" if language == "ar" else "Arabic"
        json_structure["key_terms"] = [
            {
                "term": f"Technical term in {language}",
                "translation": f"Translation in {translation_lang}",
                "explanation": f"Brief explanation in {language}"
            }
        ]
        json_structure["comparison_table"] = {
            "present": "true/false",
            "caption": f"Descriptive caption for the table in {language}",
            "headers": ["Column1", "Column2", "Column3"],
            "rows": [
                ["Item1_Col1", "Item1_Col2", "Item1_Col3"],
                ["Item2_Col1", "Item2_Col2", "Item2_Col3"]
            ]
        }

    # Convert to formatted JSON string
    import json as json_module
    json_example = json_module.dumps(json_structure, indent=4, ensure_ascii=False)

    prompt += f"\n{json_example}\n\nCRITICAL RULES:\n"

    if category:
        prompt += f"1. Category: User explicitly specified '{category}' - include this in the JSON response\n"
        prompt += f"2. Do NOT change the category from '{category}'\n"
    else:
        prompt += f"1. Category: The user did NOT specify a category\n"
        prompt += f"2. Do NOT include a 'category' field in your JSON response\n"
        prompt += f"   - The system will automatically assign this to 'Jots'\n"
        prompt += f"   - Do NOT try to guess or infer the category\n"

    prompt += "3. Maximum 5 items for: tags, concepts, and each entity type\n"
    prompt += "4. For wikilinks: identify key terms that could link to other notes\n"
    prompt += "5. Preserve the original language of the text\n"

    rule_num = 6

    # Language preservation for Arabic content
    if language == "ar":
        prompt += f"{rule_num}. CRITICAL - Language Preservation for Arabic Content:\n"
        prompt += f"   - Keep the title in ARABIC (do NOT translate to English)\n"
        prompt += f"   - Keep all entity names (people, places, terms) in ARABIC (do NOT translate to English)\n"
        prompt += f"   - All metadata should preserve the original Arabic language\n"
        rule_num += 1

    # Special handling for Poetry and Sayings categories
    if category and category.lower() in ["poetry", "sayings"]:
        prompt += f"{rule_num}. ADDITIONAL RULE for {category} category:\n"
        prompt += f"   - The title should be a short excerpt or the first line of the text in its original language\n"
        rule_num += 1

    if language == "ar":
        prompt += f"{rule_num}. For Arabic text: provide 'translations' object with Arabic terms and their English translations (max 5 terms)\n"
        rule_num += 1

    if not skip_summarization:
        translation_lang = "English" if language == "ar" else "Arabic"
        prompt += f"{rule_num}. For key_terms: Extract ALL important technical, domain-specific, or specialized terms (not limited to 5)\n"
        prompt += f"   - term: The term in the note's language ({language})\n"
        prompt += f"   - translation: Translation to {translation_lang}\n"
        prompt += f"   - explanation: Brief explanation in the note's language ({language})\n"
        rule_num += 1
        prompt += f"{rule_num}. For comparison_table:\n"
        prompt += f"   - Set 'present' to true ONLY if the text contains side-by-side comparisons of concepts, products, methods, or approaches\n"
        prompt += f"   - If present=true, extract the comparison into a structured table format\n"
        prompt += f"   - Include a descriptive caption in {language}\n"
        prompt += f"   - If no comparison exists, set 'present' to false and omit headers/rows\n"
    else:
        prompt += f"NOTE: This is a {category} category - skip key_terms and comparison_table extraction\n"

    prompt += "\nReturn ONLY the JSON object, no other text."
    
    return prompt

def attempt_json_repair(self, json_text: str) -> str:
    """
    Attempt to repair common JSON errors.

    Handles:
    - Incomplete JSON (missing closing braces)
    - Unterminated strings
    - Truncated responses

    Args:
        json_text: The malformed JSON text

    Returns:
        Repaired JSON text

    Raises:
        json.JSONDecodeError: If repair fails
    """
    import re

    # Count opening and closing braces
    open_braces = json_text.count('{')
    close_braces = json_text.count('}')
    open_brackets = json_text.count('[')
    close_brackets = json_text.count(']')

    # Add missing closing brackets for arrays
    if open_brackets > close_brackets:
        json_text += ']' * (open_brackets - close_brackets)
        print(f"Added {open_brackets - close_brackets} closing brackets")

    # Check for unterminated string at the end
    # If the last non-whitespace character is not a closing brace/bracket, we likely have truncation
    stripped = json_text.rstrip()
    if stripped and stripped[-1] not in ['}', ']', '"']:
        # Try to close the current string
        if stripped.count('"') % 2 != 0:
            json_text = stripped + '"'
            print("Added closing quote for unterminated string")
            stripped = json_text

        # Close any open arrays or objects up to the truncation point
        # Find the last complete structure
        last_comma_or_brace = max(
            stripped.rfind(','),
            stripped.rfind('{'),
            stripped.rfind('[')
        )
        if last_comma_or_brace > 0:
            # Truncate to last complete structure
            json_text = stripped[:last_comma_or_brace]
            print(f"Truncated to position {last_comma_or_brace}")

    # Add missing closing braces
    if open_braces > close_braces:
        json_text += '}' * (open_braces - close_braces)
        print(f"Added {open_braces - close_braces} closing braces")

    return json_text

def process_response(message: str,
    response_text: str,
    channel: str,     
    language: str,
    category: str,
    specified_title: Optional[str] = None,
    metadata: Optional [Dict[str, Any]] = None):

    try:
        # Gemini sometimes wraps JSON in markdown code blocks, remove them
        if response_text.strip().startswith("```"):
            # Remove markdown code block markers
            lines = response_text.strip().split('\n')
            # Remove first line (```json or ```) and last line (```)
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response_text = '\n'.join(lines)

        # Parse JSON response
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to repair common JSON issues before giving up
            print("Initial JSON parse failed, attempting repair...")
            repaired_text = attempt_json_repair(response_text)
            result = json.loads(repaired_text)
            print("Successfully parsed repaired JSON")

        # Override title if explicitly provided (e.g., from YouTube video title)
        if specified_title:
            result["title"] = specified_title

        result["category"] = category
        result["channel"] = channel
        result["language"] = language
        result["content"] = message  # Store original message text

        # Add metadata
        result["processedAt"] = datetime.now().isoformat()
        result["metadata"] = metadata

        # Using Pydantic, parse into a SummarizerResult object for validation and type safety
        summarizer_result = SummarizerResult(**result)
        # Enforce limits and validation
        summarizer_result = enforce_limits(summarizer_result)
        return summarizer_result

    except json.JSONDecodeError as e:
        # Return a fallback structure with explicit metadata if provided
        return create_fallback_structure(message, language, specified_title, category)

def enforce_limits(result: SummarizerResult) -> SummarizerResult:
    """
    Enforce limits on arrays and validate category.

    Args:
        result: SummarizerResult object to validate
        specified_category: User-specified category (if any)

    Returns:
        Validated SummarizerResult object
    """
    if result.tags and len(result.tags) > 5:
        result.tags = result.tags[:5]

    if result.concepts and len(result.concepts) > 5:
        result.concepts = result.concepts[:5]

    if result.wikilinks and len(result.wikilinks) > 5:
        result.wikilinks = result.wikilinks[:5]

    if result.wikilinks and len(result.wikilinks) > 5:
        result.wikilinks = result.wikilinks[:5]

    if result.translations and len(result.translations) > 5:
        result.translations = result.translations[:5]

    if result.entities and len(result.entities) > 5:
        for key in result.entities:
            if isinstance(result.entities[key], list):
                result.entities[key] = result.entities[key][:5]

    return result


def create_fallback_structure(
    message_text: str,
    language: str,
    specified_title: Optional[str] = None,
    specified_category: Optional[str] = None
) -> SummarizerResult:
    """Create a basic structure when Claude processing fails."""
    return SummarizerResult(
        title=specified_title or f"Note - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        category=specified_category or "Jots",
        tags=["unprocessed"],
        concepts=[],
        entities={"people": [], "places": [], "terms": []},
        summary=message_text[:200] + ("..." if len(message_text) > 200 else ""),
        wikilinks=[],
        content=message_text,
        processedAt=datetime.now().isoformat(),
        language=language,
        fallback=True
    )

