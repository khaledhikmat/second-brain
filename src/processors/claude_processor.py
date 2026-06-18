"""Claude AI processor for analyzing and structuring notes."""

import json
import logging
from typing import Dict, List, Any, Optional
from anthropic import Anthropic
from datetime import datetime

logger = logging.getLogger(__name__)


class ClaudeProcessor:
    """Processes messages using Claude API to extract insights and structure."""

    def __init__(self, api_key: str, predefined_categories: List[str]):
        """
        Initialize the Claude processor.

        Args:
            api_key: Anthropic API key
            predefined_categories: List of predefined categories
        """
        self.client = Anthropic(api_key=api_key)
        self.predefined_categories = predefined_categories

    def process_message(
        self,
        message_text: str,
        language: str,
        specified_title: Optional[str] = None,
        specified_category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a message and extract structured information.

        Args:
            message_text: The message content
            language: Language code ('ar' or 'en')
            specified_title: Optional explicit title (e.g., from YouTube video title)
            specified_category: Optional explicit category (e.g., from API request)

        Returns:
            Dictionary containing:
                - title: Suggested note title
                - category: Primary category
                - tags: List of tags (max 5)
                - concepts: Extracted key concepts (max 5)
                - entities: Named entities (max 5 each)
                - summary: Brief summary
                - wikilinks: Suggested [[wikilinks]]
                - content: Structured note content
                - translations: Arabic to English term translations (if applicable)
        """
        # Check for category prefix (e.g., "Poetry -> message content") only if not explicitly provided
        # Supports both single-line and multi-line formats:
        # "Poetry -> message" or "Poetry ->\nmessage"
        actual_message = message_text

        # Only check for prefix if category not explicitly provided
        if not specified_category and (" -> " in message_text or " → " in message_text):
            separator = " -> " if " -> " in message_text else " → "
            parts = message_text.split(separator, 1)
            if len(parts) == 2:
                potential_category = parts[0].strip()
                # Check if it matches one of the predefined categories (case-insensitive)
                for cat in self.predefined_categories:
                    if potential_category.lower() == cat.lower():
                        specified_category = cat
                        # Strip the message part (handles multi-line)
                        actual_message = parts[1].strip()
                        break

        language_name = "Arabic" if language == "ar" else "English"

        # Determine if we should extract key terms and comparison tables
        # Skip for Sayings and Poetry as they are typically short quotes/verses
        skip_advanced_extraction = specified_category and specified_category.lower() in ["sayings", "poetry"]

        prompt = f"""You are an expert knowledge curator. Analyze the following {language_name} text and extract structured information.

Text to analyze:
{actual_message}

{"User specified category: " + specified_category if specified_category else ""}

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
            "summary": "A brief 1-2 sentence summary",
            "wikilinks": ["Terms that should be wikilinked (max 10)"],
            "content": "The original text formatted in Obsidian markdown with appropriate headers, wikilinks, and structure"
        }

        # Only include category field if user specified it
        if specified_category:
            json_structure["category"] = specified_category
        else:
            # Don't include category in JSON - we'll force it to "Jots" later
            pass

        # Add translations for Arabic notes
        if language == "ar":
            json_structure["translations"] = {"term in Arabic": "English translation - Only for Arabic notes, translate max 5 key terms to English"}

        # Add key_terms and comparison_table for non-Sayings/Poetry categories
        if not skip_advanced_extraction:
            translation_lang = "English" if language == "ar" else "Arabic"
            json_structure["key_terms"] = [
                {
                    "term": f"Technical term in {language_name}",
                    "translation": f"Translation in {translation_lang}",
                    "explanation": f"Brief explanation in {language_name}"
                }
            ]
            json_structure["comparison_table"] = {
                "present": "true/false",
                "caption": f"Descriptive caption for the table in {language_name}",
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

        if specified_category:
            prompt += f"1. Category: User explicitly specified '{specified_category}' - include this in the JSON response\n"
            prompt += f"2. Do NOT change the category from '{specified_category}'\n"
        else:
            prompt += f"1. Category: The user did NOT specify a category\n"
            prompt += f"2. Do NOT include a 'category' field in your JSON response\n"
            prompt += f"   - The system will automatically assign this to 'Jots'\n"
            prompt += f"   - Do NOT try to guess or infer the category\n"

        prompt += "3. Maximum 5 items for: tags, concepts, and each entity type\n"
        prompt += "4. For wikilinks: identify key terms that could link to other notes\n"
        prompt += "5. Preserve the original language of the text\n"

        rule_num = 6

        # Special handling for Poetry and Sayings categories
        if specified_category and specified_category.lower() in ["poetry", "sayings"]:
            prompt += f"{rule_num}. IMPORTANT for {specified_category} category:\n"
            prompt += f"   - Keep the title in the ORIGINAL language (do NOT translate to English)\n"
            prompt += f"   - Keep all entity names (people, places) in the ORIGINAL language (do NOT translate to English)\n"
            prompt += f"   - The title should be a short excerpt or the first line of the text in its original language\n"
            rule_num += 1

        if language == "ar":
            prompt += f"{rule_num}. For Arabic text: provide 'translations' object with Arabic terms and their English translations (max 5 terms)\n"
            rule_num += 1

        if not skip_advanced_extraction:
            translation_lang = "English" if language == "ar" else "Arabic"
            prompt += f"{rule_num}. For key_terms: Extract ALL important technical, domain-specific, or specialized terms (not limited to 5)\n"
            prompt += f"   - term: The term in the note's language ({language_name})\n"
            prompt += f"   - translation: Translation to {translation_lang}\n"
            prompt += f"   - explanation: Brief explanation in the note's language ({language_name})\n"
            rule_num += 1
            prompt += f"{rule_num}. For comparison_table:\n"
            prompt += f"   - Set 'present' to true ONLY if the text contains side-by-side comparisons of concepts, products, methods, or approaches\n"
            prompt += f"   - If present=true, extract the comparison into a structured table format\n"
            prompt += f"   - Include a descriptive caption in {language_name}\n"
            prompt += f"   - If no comparison exists, set 'present' to false and omit headers/rows\n"
        else:
            prompt += f"NOTE: This is a {specified_category} category - skip key_terms and comparison_table extraction\n"

        prompt += "\nReturn ONLY the JSON object, no other text."

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract the text content
            response_text = message.content[0].text

            # Claude sometimes wraps JSON in markdown code blocks, remove them
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
                logger.warning("Initial JSON parse failed, attempting repair...")
                repaired_text = self._attempt_json_repair(response_text)
                result = json.loads(repaired_text)
                logger.info("Successfully parsed repaired JSON")

            # Enforce limits and validation
            result = self._enforce_limits_and_validate(result, specified_category)

            # Override title if explicitly provided (e.g., from YouTube video title)
            if specified_title:
                result["title"] = specified_title
                logger.info(f"Using explicit title: {specified_title}")

            # Add metadata
            result["processed_at"] = datetime.now().isoformat()
            result["language"] = language
            result["original_text"] = actual_message  # Store original message text

            logger.info(f"Successfully processed message with title: {result.get('title')}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            logger.error(f"Error at line {e.lineno}, column {e.colno}, position {e.pos}")
            # Log more of the response around the error position
            start = max(0, e.pos - 200)
            end = min(len(response_text), e.pos + 300)
            logger.error(f"Context around error:\n...{response_text[start:end]}...")
            logger.error(f"Full response length: {len(response_text)} characters")
            # Return a fallback structure with explicit metadata if provided
            return self._create_fallback_structure(message_text, language, specified_title, specified_category)

        except Exception as e:
            logger.error(f"Error processing message with Claude: {e}")
            return self._create_fallback_structure(message_text, language, specified_title, specified_category)

    def _enforce_limits_and_validate(self, result: Dict[str, Any], specified_category: str = None) -> Dict[str, Any]:
        """
        Enforce limits on arrays and validate category.

        Args:
            result: The parsed result from Claude
            specified_category: User-specified category (if any)

        Returns:
            Validated and limited result
        """
        # Enforce category - must be in predefined list
        # If user specified category, use it
        if specified_category:
            result["category"] = specified_category
        else:
            # User did NOT specify a category - ALWAYS default to Jots
            # Ignore any category that Claude may have returned
            if "category" in result:
                logger.warning(f"Claude returned category '{result.get('category')}' but user did not specify one, forcing to 'Jots'")
            result["category"] = "Jots"

        # Limit arrays to max 5 items
        if "tags" in result and isinstance(result["tags"], list):
            result["tags"] = result["tags"][:5]

        if "concepts" in result and isinstance(result["concepts"], list):
            result["concepts"] = result["concepts"][:5]

        if "wikilinks" in result and isinstance(result["wikilinks"], list):
            result["wikilinks"] = result["wikilinks"][:10]

        # Limit entities
        if "entities" in result and isinstance(result["entities"], dict):
            for key in result["entities"]:
                if isinstance(result["entities"][key], list):
                    result["entities"][key] = result["entities"][key][:5]

        # Limit translations if present
        if "translations" in result and isinstance(result["translations"], dict):
            # Keep only first 5 translations
            result["translations"] = dict(list(result["translations"].items())[:5])

        return result

    def _attempt_json_repair(self, json_text: str) -> str:
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
            logger.debug(f"Added {open_brackets - close_brackets} closing brackets")

        # Check for unterminated string at the end
        # If the last non-whitespace character is not a closing brace/bracket, we likely have truncation
        stripped = json_text.rstrip()
        if stripped and stripped[-1] not in ['}', ']', '"']:
            # Try to close the current string
            if stripped.count('"') % 2 != 0:
                json_text = stripped + '"'
                logger.debug("Added closing quote for unterminated string")
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
                logger.debug(f"Truncated to position {last_comma_or_brace}")

        # Add missing closing braces
        if open_braces > close_braces:
            json_text += '}' * (open_braces - close_braces)
            logger.debug(f"Added {open_braces - close_braces} closing braces")

        return json_text

    def _create_fallback_structure(
        self,
        message_text: str,
        language: str,
        specified_title: Optional[str] = None,
        specified_category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a basic structure when Claude processing fails."""
        return {
            "title": specified_title or f"Note - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "category": specified_category or "Jots",
            "tags": ["unprocessed"],
            "concepts": [],
            "entities": {"people": [], "places": [], "terms": []},
            "summary": message_text[:200] + ("..." if len(message_text) > 200 else ""),
            "wikilinks": [],
            "content": message_text,
            "processed_at": datetime.now().isoformat(),
            "language": language,
            "fallback": True
        }
