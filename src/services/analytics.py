"""
Analytics service for message statistics and insights.

Provides aggregated statistics about messages, processing, and categories.
"""

import logging
from typing import Dict, Any
from datetime import datetime

from src.db.database import get_db_manager
from src.db.repository import AnalyticsRepository

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for analytics and statistics."""

    async def get_summary(self) -> Dict[str, Any]:
        """
        Get summary analytics.

        Returns:
            Dict with overall statistics including:
            - Total messages
            - Messages by status
            - Messages by category
            - Messages by language
            - Success rate
        """
        db_manager = get_db_manager()
        if not db_manager or not db_manager.is_available:
            logger.error("Database not available for analytics")
            return {
                "error": "Database not available",
                "timestamp": datetime.utcnow().isoformat()
            }

        try:
            async with db_manager.get_session() as session:
                # Get all analytics data in parallel queries
                total_messages = await AnalyticsRepository.get_total_messages(session)
                status_counts = await AnalyticsRepository.get_message_counts_by_status(session)
                category_counts = await AnalyticsRepository.get_message_counts_by_category(session)
                language_counts = await AnalyticsRepository.get_message_counts_by_language(session)
                success_rate = await AnalyticsRepository.get_success_rate(session)

                return {
                    "total_messages": total_messages,
                    "by_status": status_counts,
                    "by_category": category_counts,
                    "by_language": language_counts,
                    "success_rate_percent": round(success_rate, 2),
                    "timestamp": datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to get analytics summary: {e}", exc_info=True)
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def get_category_stats(self) -> Dict[str, Any]:
        """
        Get detailed category statistics.

        Returns:
            Dict with category breakdown
        """
        db_manager = get_db_manager()
        if not db_manager or not db_manager.is_available:
            logger.error("Database not available for analytics")
            return {
                "error": "Database not available",
                "timestamp": datetime.utcnow().isoformat()
            }

        try:
            async with db_manager.get_session() as session:
                category_counts = await AnalyticsRepository.get_message_counts_by_category(session)
                total = sum(category_counts.values())

                # Calculate percentages
                category_stats = {
                    category: {
                        "count": count,
                        "percentage": round((count / total * 100), 2) if total > 0 else 0
                    }
                    for category, count in category_counts.items()
                }

                return {
                    "categories": category_stats,
                    "total": total,
                    "timestamp": datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to get category stats: {e}", exc_info=True)
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def get_language_stats(self) -> Dict[str, Any]:
        """
        Get detailed language statistics.

        Returns:
            Dict with language breakdown
        """
        db_manager = get_db_manager()
        if not db_manager or not db_manager.is_available:
            logger.error("Database not available for analytics")
            return {
                "error": "Database not available",
                "timestamp": datetime.utcnow().isoformat()
            }

        try:
            async with db_manager.get_session() as session:
                language_counts = await AnalyticsRepository.get_message_counts_by_language(session)
                total = sum(language_counts.values())

                # Calculate percentages
                language_stats = {
                    language: {
                        "count": count,
                        "percentage": round((count / total * 100), 2) if total > 0 else 0
                    }
                    for language, count in language_counts.items()
                }

                return {
                    "languages": language_stats,
                    "total": total,
                    "timestamp": datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to get language stats: {e}", exc_info=True)
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def get_processing_stats(self) -> Dict[str, Any]:
        """
        Get processing statistics.

        Returns:
            Dict with processing status breakdown
        """
        db_manager = get_db_manager()
        if not db_manager or not db_manager.is_available:
            logger.error("Database not available for analytics")
            return {
                "error": "Database not available",
                "timestamp": datetime.utcnow().isoformat()
            }

        try:
            async with db_manager.get_session() as session:
                status_counts = await AnalyticsRepository.get_message_counts_by_status(session)
                total = sum(status_counts.values())
                success_rate = await AnalyticsRepository.get_success_rate(session)

                # Calculate percentages for each status
                status_stats = {
                    status: {
                        "count": count,
                        "percentage": round((count / total * 100), 2) if total > 0 else 0
                    }
                    for status, count in status_counts.items()
                }

                return {
                    "by_status": status_stats,
                    "total": total,
                    "success_rate_percent": round(success_rate, 2),
                    "timestamp": datetime.utcnow().isoformat()
                }

        except Exception as e:
            logger.error(f"Failed to get processing stats: {e}", exc_info=True)
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
