from rest_framework import serializers
from .models import Conversation, Message, Document

class DocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ['id', 'title', 'file', 'file_url', 'uploaded_at', 'is_processed']
        read_only_fields = ['uploaded_at', 'is_processed']

    def get_file_url(self, obj):
        """Return the full URL for the file (works with both S3 and local storage)."""
        if obj.file:
            try:
                return obj.file.url
            except Exception:
                return None
        return None

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

class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username')
    email = serializers.CharField(source='user.email')

    class Meta:
        from .models import UserProfile
        model = UserProfile
        fields = ['credits', 'username', 'email']
