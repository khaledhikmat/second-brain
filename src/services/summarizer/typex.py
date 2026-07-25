from datetime import datetime
from typing import Dict, Protocol, Optional, Any
from pydantic import BaseModel

class SummarizerResult(BaseModel):
    """
    Represents the result of a summarization process.
    """
    category: str
    channel: str
    language: str
    title: str
    message: str
    metadata: Optional[Dict[str, Any]] = None
    processedAt: Optional[str] = None

class ISummarizerService(Protocol):
    """Protocol defining the summarizer service interface."""

    async def summarize(
            self,
            channel: str,
            category: str,
            language: str,
            message: str,
            metadata: Optional[Dict[str, Any]] = None
        ) -> Optional [SummarizerResult]:        
        """
        Process an incoming message and create a summary.

        Args:
            channel: The channel to which the summary belongs
            category: The category of the note
            language: The language of the message
            message: The message content
            metadata: Optional dictionary containing additional metadata for the note
        """
        ...

##############################################
## common functions used by all summarizers ##
##############################################

def produce_title_prompt(language: str, message: str) -> str:
    prompt = f"""You are an expert knowledge curator. Your job is to produce a concise, descriptive title for the message using the message language.

Message Text:
{message}

Message Language:
{language}
"""

    return prompt

def produce_summarization_prompt(language: str) -> str:
    prompt = f"""
    You are an expert knowledge curator for classical and professional {language} text synthesis.
    Please read the attached {language} PDF document meticulously and generate an exhaustive, 
    long-form structural summary written entirely in formal, professional {language}.
    
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

    return prompt

def process_response(message: str,
    title: str,
    language: str,
    channel: str,     
    category: str,
    metadata: Optional [Dict[str, Any]] = None) -> SummarizerResult:

    result = {}
    result["title"] = title
    result["category"] = category
    result["channel"] = channel
    result["language"] = language
    result["message"] = message  # Store original message text

    # Add metadata
    result["processedAt"] = datetime.now().isoformat()
    result["metadata"] = metadata

    # Using Pydantic, parse into a SummarizerResult object for validation and type safety
    summarizer_result = SummarizerResult(**result)
    return summarizer_result

def create_fallback_structure(
    message: str,
    language: str,
    channel: str,
    category: str
) -> SummarizerResult:
    result = {}
    result["title"] = f"not_processsed_{datetime.now().isoformat()}"
    result["category"] = category
    result["channel"] = channel
    result["language"] = language
    result["message"] = message  # Store original message text

    # Add metadata
    result["processedAt"] = datetime.now().isoformat()

    # Using Pydantic, parse into a SummarizerResult object for validation and type safety
    summarizer_result = SummarizerResult(**result)
    return summarizer_result

