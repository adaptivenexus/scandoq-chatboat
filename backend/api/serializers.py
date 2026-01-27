from rest_framework import serializers
from .models import Conversation, Message, Document

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'title', 'file', 'uploaded_at', 'is_processed']
        read_only_fields = ['uploaded_at', 'is_processed']

class MessageSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'role', 'content', 'created_at', 'documents']

class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = ['id', 'title', 'created_at', 'updated_at', 'messages']
