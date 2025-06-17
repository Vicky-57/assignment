from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404, render
import logging
from .models import UserSession, ChatInteraction
from .services import ShowroomAIService
import uuid

logger = logging.getLogger(__name__)

def index(request):
    return render(request, 'showroom/index.html')

class StartSessionView(APIView):
    def post(self, request):
        """Start a new user session"""
        try:
            session = UserSession.objects.create(
                session_key=str(uuid.uuid4()),
                preferences={}
            )
            logger.info(f"New session created: {session.id}")
            return Response({
                'session_id': session.id,  # ✅ now an integer
                'session_key': session.session_key,
                'message': 'Session started successfully'
            })
        except Exception as e:
            logger.error(f"Error creating session: {str(e)}")
            return Response(
                {'error': 'Failed to create session'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ChatView(APIView):
    def post(self, request):
        """Handle chat messages"""
        session_id = request.data.get('session_id')
        message = request.data.get('message')

        logger.info(f"Chat request - session_id: {session_id}, message: {message}")

        if not session_id or not message:
            return Response(
                {'error': 'session_id and message are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # ✅ Treat session_id as integer directly
            session = get_object_or_404(UserSession, id=int(session_id))

            ai_service = ShowroomAIService()
            result = ai_service.process_user_message(message, session.id)

            logger.info(f"Message processed successfully for session: {session.id}")
            return Response(result)

        except Exception as e:
            logger.error(f"Unexpected error in ChatView: {str(e)}")
            return Response(
                {'error': f'Processing failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class SessionStatusView(APIView):
    def get(self, request, session_id):
        """Get current session status and preferences"""
        try:
            session = get_object_or_404(UserSession, id=session_id)
            interactions = ChatInteraction.objects.filter(session=session).order_by('-timestamp')[:5]

            return Response({
                'session_id': session.id,
                'preferences': session.preferences,
                'room_type': session.room_type,
                'style_preference': session.style_preference,
                'budget_range': session.budget_range,
                'recent_interactions': [
                    {
                        'user_message': interaction.user_message,
                        'ai_response': interaction.ai_response,
                        'timestamp': interaction.timestamp
                    } for interaction in interactions
                ],
                'is_active': session.is_active
            })

        except UserSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
