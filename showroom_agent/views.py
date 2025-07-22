from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404, render
from django.core.cache import cache
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
import logging
from .models import UserSession, ChatInteraction
from .services import ShowroomAIService
import uuid

logger = logging.getLogger(__name__)

def index(request):
    return render(request, 'showroom/index.html')

class StartSessionView(APIView):
    def post(self, request):
        """Start a new user session - simplified"""
        try:
            # Simple rate limiting by IP
            user_ip = self._get_client_ip(request)
            recent_session_key = f'recent_session_{user_ip}'
            recent_session = cache.get(recent_session_key)
            
            if recent_session:
                logger.info(f"Returning existing session: {recent_session['session_id']}")
                return Response(recent_session)
            
            # Create new session
            session = UserSession.objects.create()
            
            session_data = {
                'session_id': session.id,
                'session_key': session.session_key,
                'message': 'Welcome! I specialize in bathroom and kitchen design. Which space are you working on, and what\'s your budget?'
            }
            
            # Cache session for 5 minutes
            cache.set(recent_session_key, session_data, 300)
            
            logger.info(f"New session created: {session.id}")
            return Response(session_data)
            
        except Exception as e:
            logger.error(f"Error creating session: {str(e)}")
            return Response(
                {'error': 'Failed to create session'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_client_ip(self, request):
        """Get client IP for rate limiting"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

class ChatView(APIView):
    def post(self, request):
        """Handle chat messages with budget awareness"""
        session_id = request.data.get('session_id')
        message = request.data.get('message', '').strip()

        # Validation
        if not session_id:
            return Response(
                {'error': 'session_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not message or len(message) < 2:
            return Response(
                {'error': 'Please provide a valid message (at least 2 characters)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(message) > 500:
            return Response(
                {'error': 'Message too long (max 500 characters)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Rate limiting per session
        rate_limit_key = f'chat_rate_limit_{session_id}'
        request_count = cache.get(rate_limit_key, 0)
        
        if request_count >= 10:  # Max 10 messages per minute
            return Response(
                {'error': 'Too many messages. Please wait a moment.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        cache.set(rate_limit_key, request_count + 1, 60)

        try:
            # Get session
            session = get_object_or_404(
                UserSession.objects,
                id=int(session_id),
                is_active=True
            )
            
            # Check if session expired
            if session.is_expired():
                session.is_active = False
                session.save()
                return Response(
                    {'error': 'Session expired. Please start a new session.'},
                    status=status.HTTP_410_GONE
                )

            # Get AI service
            ai_service = self._get_ai_service()
            
            # Process message
            result = ai_service.process_user_message(message, session.id)
            
            # Add session info
            result.update({
                'session_id': session.id,
                'timestamp': session.updated_at.isoformat()
            })
            
            logger.info(f"Processed message for session {session.id}")
            return Response(result)

        except ValueError:
            return Response(
                {'error': 'Invalid session_id format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Chat error: {str(e)}")
            return Response(
                {
                    'error': 'I encountered an issue. Please try again.',
                    'response': 'Something went wrong. Could you repeat your question?'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_ai_service(self):
        """Get AI service instance with caching"""
        cache_key = 'ai_service_instance'
        service = cache.get(cache_key)
        
        if not service:
            service = ShowroomAIService()
            cache.set(cache_key, service, 3600)
        
        return service

class SessionStatusView(APIView):
    @method_decorator(cache_page(60))
    def get(self, request, session_id):
        """Get current session status with budget info"""
        try:
            session = get_object_or_404(
                UserSession.objects,
                id=session_id,
                is_active=True
            )
            
            # Get recent interactions
            interactions = ChatInteraction.objects.filter(
                session=session
            ).order_by('-timestamp')[:3].values(
                'user_message', 'ai_response', 'timestamp'
            )
            
            # Format budget info
            budget_info = {}
            if session.budget_amount:
                budget_info = {
                    'amount': float(session.budget_amount),
                    'range': session.budget_range,
                    'formatted': f"${session.budget_amount:,.0f} ({session.budget_range} range)"
                }
            
            response_data = {
                'session_id': session.id,
                'preferences': session.preferences or {},
                'room_type': session.room_type,
                'style_preference': session.style_preference,
                'budget_info': budget_info,
                'room_size': session.room_size,
                'recent_interactions': list(interactions),
                'is_active': session.is_active,
                'created_at': session.created_at.isoformat(),
                'total_messages': session.total_interactions,
                'completion_percentage': session.completion_percentage,
                'session_phase': self._get_session_phase(session)
            }
            
            return Response(response_data)

        except Exception as e:
            logger.error(f"Session status error: {str(e)}")
            return Response(
                {'error': 'Failed to retrieve session status'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_session_phase(self, session):
        """Determine current phase based on completion"""
        if not session.room_type:
            return 'room_identification'
        elif session.room_type not in ['bathroom', 'kitchen']:
            return 'out_of_scope'
        elif session.completion_percentage < 60:
            return 'info_gathering'
        elif session.completion_percentage < 90:
            return 'final_details'
        else:
            return 'design_ready'

class SessionCleanupView(APIView):
    """Clean up old sessions"""
    
    def post(self, request):
        """Clean up expired sessions"""
        try:
            from datetime import timedelta
            from django.utils import timezone
            
            # Delete sessions older than 7 days
            cutoff_date = timezone.now() - timedelta(days=7)
            old_sessions = UserSession.objects.filter(created_at__lt=cutoff_date)
            
            # Delete inactive sessions older than 1 day
            inactive_cutoff = timezone.now() - timedelta(days=1)
            inactive_sessions = UserSession.objects.filter(
                is_active=False,
                created_at__lt=inactive_cutoff
            )
            
            old_count = old_sessions.count()
            inactive_count = inactive_sessions.count()
            
            old_sessions.delete()
            inactive_sessions.delete()
            
            cache.clear()
            
            logger.info(f"Cleaned up {old_count + inactive_count} sessions")
            
            return Response({
                'message': 'Cleanup completed',
                'sessions_cleaned': old_count + inactive_count
            })
            
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")
            return Response(
                {'error': 'Cleanup failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class QuickRecommendationView(APIView):
    """Fast endpoint for quick product recommendations"""
    
    def post(self, request):
        """Get quick recommendations without full conversation"""
        room_type = request.data.get('room_type')
        style = request.data.get('style')
        budget = request.data.get('budget', 'medium')
        
        if room_type not in ['bathroom', 'kitchen']:
            return Response(
                {'error': 'room_type must be "bathroom" or "kitchen"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Create temporary preferences
            temp_preferences = {
                'room_type': room_type,
                'style': style,
                'budget_range': budget
            }
            
            # Get recommendations
            ai_service = ShowroomAIService()
            products = ai_service._get_budget_aware_products(
                f"{room_type} {style}", 
                temp_preferences
            )
            
            return Response({
                'recommendations': products,
                'room_type': room_type,
                'style': style,
                'budget': budget
            })
            
        except Exception as e:
            logger.error(f"Quick recommendation error: {str(e)}")
            return Response(
                {'error': 'Failed to get recommendations'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )