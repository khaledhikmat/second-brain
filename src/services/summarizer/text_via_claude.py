from typing import Any, Dict, Optional, List
import json
from datetime import datetime

from src.services.setting.typex import ISettingService
from src.services.logger.typex import ILoggerService
from src.services.typex import SummarizerResult

class TextSummarizerService:
    def __init__(self, setting: ISettingService, logger: ILoggerService):
        self._setting = setting
        self._logger = logger

    async def summarize(
            self,
            channel: str,
            message: str,
            category: str,
            language: str = None,
            specified_title: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None
        ) -> SummarizerResult:        
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
        skip_summarization = False
        if category and category.lower() in ["sayings", "poetry"]:
            skip_summarization = True

        # determine if message needs to be chunked based on length and model limits
        if len(message) > self._setting.summarize_threshold():
            self._logger.info(f"Messafe exceeds threshold ({len(message)} > {self._setting.summarize_threshold()}), summarizing...")
            message = self._summarize_message(message)

        self._logger.info("Processing message length via Claude: %d", len(message))

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
            "summary": "A brief 1-2 sentence summary",
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

        # Special handling for Poetry and Sayings categories
        if category and category.lower() in ["poetry", "sayings"]:
            prompt += f"{rule_num}. IMPORTANT for {category} category:\n"
            prompt += f"   - Keep the title in the ORIGINAL language (do NOT translate to English)\n"
            prompt += f"   - Keep all entity names (people, places) in the ORIGINAL language (do NOT translate to English)\n"
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

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-6",
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
                self._logger.warning("Initial JSON parse failed, attempting repair...")
                repaired_text = self._attempt_json_repair(response_text)
                result = json.loads(repaired_text)
                self._loggerlogger.info("Successfully parsed repaired JSON")

            # Uisng Pydantic, parse into a SummarizerResult object for validation and type safety

            summarizer_result = SummarizerResult(**result)
            # Enforce limits and validation
            summarizer_result = self._enforce_limits_and_validate(summarizer_result, category)

            # Override title if explicitly provided (e.g., from YouTube video title)
            if specified_title:
                result["title"] = specified_title
                self._logger.info(f"Using explicit title: {specified_title}")

            # Add metadata
            result["processed_at"] = datetime.now().isoformat()
            result["language"] = language
            result["original_text"] = message  # Store original message text

            self._logger.info(f"Successfully processed message with title: {result.get('title')}")
            return result

        except json.JSONDecodeError as e:
            self._logger.error(f"Failed to parse Claude response as JSON: {e}")
            self._logger.error(f"Error at line {e.lineno}, column {e.colno}, position {e.pos}")
            # Log more of the response around the error position
            start = max(0, e.pos - 200)
            end = min(len(response_text), e.pos + 300)
            self._logger.error(f"Context around error:\n...{response_text[start:end]}...")
            self._logger.error(f"Full response length: {len(response_text)} characters")
            # Return a fallback structure with explicit metadata if provided
            return self._create_fallback_structure(message, language, specified_title, category)

        except Exception as e:
            self._logger.error(f"Error processing message with Claude: {e}")
            return self._create_fallback_structure(message, language, specified_title, category)

    def _enforce_limits_and_validate(self, result: SummarizerResult, specified_category: str = None) -> SummarizerResult:
        """
        Enforce limits on arrays and validate category.

        Args:
            result: SummarizerResult object to validate
            specified_category: User-specified category (if any)

        Returns:
            Validated SummarizerResult object
        """
        # Enforce category - must be in predefined list
        # If user specified category, use it
        if specified_category:
            result["category"] = specified_category
        else:
            # User did NOT specify a category - ALWAYS default to Jots
            # Ignore any category that Claude may have returned
            if "category" in result:
                self._logger.warning(f"Claude returned category '{result.get('category')}' but user did not specify one, forcing to 'Jots'")
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

    def _summarize_messagge(self, message: str, language: str) -> str:
        """
        Summarize a long message using Claude.

        Uses different strategies based on message length:
        - < 150k chars: Direct summarization (fits in Claude's context window)
        - >= 150k chars: Chunked summarization with map-reduce approach

        Args:
            message: Full message text

        Returns:
            Summarized text suitable for note creation
        """
        self._logger.info(f"Summarizing message (length: {len(message)} chars, ~{len(message)//4} tokens) using language: {language}")

        try:
            # Strategy 1: For messages < 150k chars, summarize directly
            # (Claude Sonnet 4 has 200k token context = ~600k-800k chars)
            if len(message) < 150000:
                self._logger.info("Using direct summarization (message fits in context window)")
                return self._summarize_single_chunk(message, language)

            # Strategy 2: For very long messages, use map-reduce chunking
            self._logger.info("Using chunked summarization for very long message")
            chunks = self._split_message_into_chunks(message, chunk_size=40000)
            self._logger.info(f"Split message into {len(chunks)} chunks")

            # Summarize each chunk
            chunk_summaries = []
            for i, chunk in enumerate(chunks, 1):
                chunk_summary = self._summarize_single_chunk(chunk, language, i, len(chunks))
                chunk_summaries.append(chunk_summary)

            # If we have multiple chunk summaries, combine them into final summary
            if len(chunk_summaries) > 1:
                self._logger.info(f"Combining {len(chunk_summaries)} chunk summaries into final summary")

                combined_text = "\n\n".join([
                    f"Section {i}:\n{summary}"
                    for i, summary in enumerate(chunk_summaries, 1)
                ])

                # Create final combined summary
                final_prompt = f"""Please create a comprehensive final summary by combining these section summaries from a long video.

IMPORTANT: The content is in {language}. Your final summary MUST be in {language} as well.

Combine and organize:
1. Main topics and themes across all sections
2. Key points and takeaways
3. Important facts, quotes, or insights
4. Any actionable items or recommendations

Remove redundancy and create a cohesive, well-structured summary.
Write your entire response in {language}.

Section Summaries:
{combined_text}
"""

                from anthropic import Anthropic
                client = Anthropic(api_key=self.claude_processor.client.api_key)

                message = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=8192,  # Larger output for combined summary
                    messages=[
                        {"role": "user", "content": final_prompt}
                    ]
                )

                final_summary = message.content[0].text.strip()
                self._logger.info(f"Final combined summary created (length: {len(final_summary)} chars)")
                return final_summary
            else:
                # Only one chunk, return its summary directly
                return chunk_summaries[0]

        except Exception as e:
            self._logger.error(f"Failed to summarize message: {e}", exc_info=True)
            # If summarization fails, return truncated message
            self._logger.warning("Using truncated message instead of summary")
            return message[:self._setting.summarize_threshold()]

    def _split_message_into_chunks(self, message: str, chunk_size: int = 40000) -> List[str]:
        """
        Split a long message into manageable chunks.

        Args:
            message: Full message text
            chunk_size: Maximum characters per chunk (default: 40k chars ~10k tokens)

        Returns:
            List of message chunks
        """
        if len(message) <= chunk_size:
            return [message]

        chunks = []
        words = message.split()
        current_chunk = []
        current_length = 0

        for word in words:
            word_length = len(word) + 1  # +1 for space

            if current_length + word_length > chunk_size and current_chunk:
                # Save current chunk and start new one
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_length = word_length
            else:
                current_chunk.append(word)
                current_length += word_length

        # Add final chunk
        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    def _summarize_single_chunk(self, chunk: str, lang_name: str, chunk_num: int = None, total_chunks: int = None) -> str:
        """
        Summarize a single chunk of message.

        Args:
            chunk: Message chunk to summarize
            lang_name: Language name for the summary
            chunk_num: Current chunk number (for logging)
            total_chunks: Total number of chunks (for logging)

        Returns:
            Summarized text
        """
        chunk_info = f" (chunk {chunk_num}/{total_chunks})" if chunk_num and total_chunks else ""
        self._logger.info(f"Summarizing message chunk{chunk_info} (length: {len(chunk)} chars)")

        prompt = f"""Please create a comprehensive summary of this video message{' section' if chunk_num else ''}.

IMPORTANT: The message is in {lang_name}. Your summary MUST be in {lang_name} as well.

Extract and organize:
1. Main topics and themes
2. Key points and takeaways
3. Important facts, quotes, or insights
4. Any actionable items or recommendations

Present the summary in a structured format that would work well as a note.
Write your entire response in {lang_name}.

Message:
{chunk}
"""

        from anthropic import Anthropic
        client = Anthropic(api_key=self.claude_processor.client.api_key)

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return message.content[0].text.strip()

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
            self._logger.debug(f"Added {open_brackets - close_brackets} closing brackets")

        # Check for unterminated string at the end
        # If the last non-whitespace character is not a closing brace/bracket, we likely have truncation
        stripped = json_text.rstrip()
        if stripped and stripped[-1] not in ['}', ']', '"']:
            # Try to close the current string
            if stripped.count('"') % 2 != 0:
                json_text = stripped + '"'
                self._logger.debug("Added closing quote for unterminated string")
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
                self._logger.debug(f"Truncated to position {last_comma_or_brace}")

        # Add missing closing braces
        if open_braces > close_braces:
            json_text += '}' * (open_braces - close_braces)
            self._logger.debug(f"Added {open_braces - close_braces} closing braces")

        return json_text

    def _create_fallback_structure(
        self,
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
            processed_at=datetime.now().isoformat(),
            language=language,
            fallback=True
        )

