import hashlib
import json
import logging
import time
import uuid
from datetime import datetime
from typing import AsyncGenerator, Optional

from app.models.agent_outputs import InvestmentResponse
from app.models.domain import ConversationMessage, ConversationSession, UserProfile
from app.models.schemas import ChatRequest, ChatResponse
from app.repositories.cache_repository import get_cache_repository

logger = logging.getLogger(__name__)

RESPONSE_CACHE_TTL = 3600  # 1 hour for response caching


class ChatService:
    """Service layer for chat operations and conversation management."""
    
    def __init__(self):
        self._cache = get_cache_repository()
        self._sessions: dict[str, ConversationSession] = {}
        self._response_cache_enabled = True
    
    def _get_response_cache_key(self, message: str, profile: Optional[UserProfile] = None) -> str:
        """Generate a cache key for a chat response based on message and profile."""
        normalized_message = message.lower().strip()
        profile_key = ""
        if profile:
            profile_key = f"_{profile.risk_tolerance.value}_{profile.investment_horizon.value}"
        
        hash_input = f"{normalized_message}{profile_key}"
        return f"response_{hashlib.md5(hash_input.encode()).hexdigest()}"
    
    def _get_cached_response(self, message: str, profile: Optional[UserProfile] = None) -> Optional[InvestmentResponse]:
        """Check if a cached response exists for this query."""
        if not self._response_cache_enabled:
            return None
        
        cache_key = self._get_response_cache_key(message, profile)
        cached = self._cache.get(cache_key)
        
        if cached:
            logger.info(f"Cache hit for query: {message[:50]}...")
            try:
                return InvestmentResponse(**cached)
            except Exception as e:
                logger.error(f"Error deserializing cached response: {e}")
                return None
        
        return None
    
    def _cache_response(self, message: str, response: InvestmentResponse, profile: Optional[UserProfile] = None):
        """Cache a response for future identical queries. Skip caching error responses."""
        if not self._response_cache_enabled:
            return
        
        # Don't cache error responses or low-confidence responses
        if response.confidence_score and response.confidence_score < 0.5:
            logger.info(f"Skipping cache for low-confidence response: {response.confidence_score}")
            return
        
        # Don't cache responses that contain error messages
        error_indicators = ["apologize", "error processing", "encountered an error", "try rephrasing"]
        explanation_lower = (response.explanation or "").lower()
        if any(indicator in explanation_lower for indicator in error_indicators):
            logger.info("Skipping cache for error response")
            return
        
        cache_key = self._get_response_cache_key(message, profile)
        try:
            self._cache.set(cache_key, response.model_dump(mode="json"), ttl_seconds=RESPONSE_CACHE_TTL)
            logger.info(f"Cached response for query: {message[:50]}...")
        except Exception as e:
            logger.error(f"Error caching response: {e}")
    
    def _get_or_create_session(self, session_id: Optional[str], user_profile: Optional[UserProfile] = None) -> ConversationSession:
        """Get existing session or create a new one."""
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        
        if session_id:
            cached = self._cache.get(f"session_{session_id}")
            if cached:
                session = ConversationSession(**cached)
                self._sessions[session_id] = session
                return session
        
        new_id = session_id or str(uuid.uuid4())
        session = ConversationSession(session_id=new_id, user_profile=user_profile)
        self._sessions[new_id] = session
        return session
    
    def _save_session(self, session: ConversationSession):
        """Persist session to cache."""
        session.updated_at = datetime.utcnow()
        self._cache.set(
            f"session_{session.session_id}",
            session.model_dump(mode="json"),
            ttl_seconds=86400 * 7
        )
    
    def _add_message(self, session: ConversationSession, role: str, content: str):
        """Add a message to the session."""
        message = ConversationMessage(role=role, content=content)
        session.messages.append(message)
        if len(session.messages) > 50:
            session.messages = session.messages[-50:]
    
    def get_conversation_history(self, session_id: str) -> list[dict]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            List of messages in the conversation
        """
        session = self._get_or_create_session(session_id)
        return [
            {"role": msg.role, "content": msg.content}
            for msg in session.messages
        ]
    
    async def process_message(
        self,
        request: ChatRequest,
        agent_runner,
        user_profile: Optional[UserProfile] = None
    ) -> ChatResponse:
        """
        Process a chat message and return a response.
        
        Args:
            request: Chat request with message and optional session_id
            agent_runner: Function to run the agent
            user_profile: Optional user profile for personalized advice
        
        Returns:
            Chat response with structured investment advice
        """
        start_time = time.time()
        
        cached_response = self._get_cached_response(request.message, user_profile)
        if cached_response:
            session = self._get_or_create_session(request.session_id, user_profile)
            self._add_message(session, "user", request.message)
            self._add_message(session, "assistant", cached_response.explanation)
            self._save_session(session)
            
            processing_time = int((time.time() - start_time) * 1000)
            return ChatResponse(
                session_id=session.session_id,
                response=cached_response,
                processing_time_ms=processing_time,
                cached=True,
            )
        
        session = self._get_or_create_session(request.session_id, user_profile)
        self._add_message(session, "user", request.message)
        
        history = self.get_conversation_history(session.session_id)
        
        try:
            response = await agent_runner(request.message, history, user_profile)
            
            self._add_message(session, "assistant", response.explanation)
            self._save_session(session)
            
            self._cache_response(request.message, response, user_profile)
            
            processing_time = int((time.time() - start_time) * 1000)
            
            return ChatResponse(
                session_id=session.session_id,
                response=response,
                processing_time_ms=processing_time,
                cached=False,
            )
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            raise
    
    async def process_message_stream(
        self,
        request: ChatRequest,
        agent_stream_runner
    ) -> AsyncGenerator[str, None]:
        """
        Process a chat message and stream the response.
        
        Args:
            request: Chat request
            agent_stream_runner: Async generator function for streaming
        
        Yields:
            SSE formatted strings
        """
        session = self._get_or_create_session(request.session_id)
        self._add_message(session, "user", request.message)
        
        history = self.get_conversation_history(session.session_id)
        
        full_response = ""
        
        try:
            async for chunk in agent_stream_runner(request.message, history):
                if isinstance(chunk, str):
                    full_response += chunk
                    yield f"event: token\ndata: {json.dumps({'token': chunk})}\n\n"
                elif isinstance(chunk, InvestmentResponse):
                    self._add_message(session, "assistant", chunk.explanation)
                    self._save_session(session)
                    yield f"event: complete\ndata: {json.dumps({'response': chunk.model_dump(mode='json'), 'session_id': session.session_id})}\n\n"
        except Exception as e:
            logger.error(f"Error in stream processing: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear a conversation session.
        
        Args:
            session_id: Session to clear
        
        Returns:
            True if successful
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
        self._cache.delete(f"session_{session_id}")
        return True


_chat_service_instance: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """Get singleton chat service instance."""
    global _chat_service_instance
    if _chat_service_instance is None:
        _chat_service_instance = ChatService()
    return _chat_service_instance
