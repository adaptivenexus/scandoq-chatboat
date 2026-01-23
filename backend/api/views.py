from django.http import JsonResponse
from django.db import connection
from rest_framework import viewsets, status, permissions, parsers
from rest_framework.decorators import action, permission_classes
from rest_framework.response import Response
from .models import Conversation, Message, Document
from .serializers import ConversationSerializer, MessageSerializer, DocumentSerializer
from .services import process_document, search_documents, generate_chat_response

@permission_classes([permissions.AllowAny])
def health_check(request):
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return JsonResponse({
        "status": "ok",
        "database": db_status
    })

class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(user=self.request.user).order_by('-updated_at')

    def perform_create(self, serializer):
        doc = serializer.save(user=self.request.user)
        # Process document (split, embed, store)
        # Note: For production, this should be a background task (e.g. Celery)
        # For now, we run it synchronously to ensure immediate availability for testing
        process_document(doc.id)

    @action(detail=False, methods=['get'])
    def suggestions(self, request):
        from collections import Counter
        
        # Get user's past messages
        user_messages = Message.objects.filter(
            conversation__user=request.user, 
            role='user'
        ).values_list('content', flat=True)
        
        # Normalize and count
        # Filter out short messages to avoid "hi", "test"
        clean_messages = [
            m.strip() for m in user_messages 
            if len(m.strip()) > 10
        ]
        
        counts = Counter(clean_messages)
        top_user_prompts = [item[0] for item in counts.most_common(3)]
        
        # Default prompts
        default_prompts = [
            "Summarize the uploaded document",
            "What are the key takeaways?",
            "Explain the main concepts"
        ]
        
        # Merge: Unique user prompts + defaults, limit to 4-5 total
        suggestions = []
        seen = set()
        
        for p in top_user_prompts:
            if p not in seen:
                suggestions.append(p)
                seen.add(p)
                
        for p in default_prompts:
            if p not in seen and len(suggestions) < 5:
                suggestions.append(p)
                seen.add(p)
                
        return Response(suggestions)

    @action(detail=True, methods=['post'])
    def message(self, request, pk=None):
        conversation = self.get_object()
        content = request.data.get('content')
        
        if not content:
            return Response({'error': 'Content is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Save user message
        user_message = Message.objects.create(
            conversation=conversation,
            role='user',
            content=content
        )

        # Get conversation history (excluding the latest message we just saved to avoid duplication in history formatting)
        # We want the LATEST messages for context, so we order by -created_at, slice, then reverse.
        # Limit to last 10 messages for context window
        recent_msgs = Message.objects.filter(conversation=conversation).order_by('-created_at')[:11] # Fetch 11 to include current + 10 previous
        # Reverse to get chronological order
        history_msgs = reversed(recent_msgs)
        
        history = [{'role': m.role, 'content': m.content} for m in history_msgs]
        
        # Filter out the current message from history to avoid double counting if we pass it as query
        # The current message was just saved, so it is likely in recent_msgs.
        previous_history = [h for h in history if not (h['content'] == content and h['role'] == 'user')]
        
        # Ensure we only keep the last 10 of previous history if we fetched more
        if len(previous_history) > 10:
            previous_history = previous_history[-10:]
        
        # Call RAG service
        ai_response_content = generate_chat_response(previous_history, content, request.user)
        
        ai_message = Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=ai_response_content
        )

        # Update conversation timestamp
        conversation.save()

        serializer = MessageSerializer(ai_message)
        return Response(serializer.data)

class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        return Document.objects.filter(user=self.request.user).order_by('-uploaded_at')

    def perform_create(self, serializer):
        doc = serializer.save(user=self.request.user)
        # Process document (split, embed, store)
        # Note: For production, this should be a background task (e.g. Celery)
        # For now, we run it synchronously to ensure immediate availability for testing
        process_document(doc.id)

    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        """
        Manually trigger processing for a document.
        """
        document = self.get_object()
        success, message = process_document(document.id)
        
        if success:
            return Response({'status': 'processed', 'chunks_count': message})
        else:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
