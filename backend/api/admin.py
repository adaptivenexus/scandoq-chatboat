from django.contrib import admin
from .models import Conversation, Message, Document, DocumentChunk

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'user', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('title',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'role', 'created_at')
    list_filter = ('role', 'created_at')
    search_fields = ('content',)

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'user', 'uploaded_at')
    list_filter = ('uploaded_at', 'user')
    search_fields = ('title',)

@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ('id', 'document', 'chunk_index', 'content_preview')
    list_filter = ('document',)
    search_fields = ('content',)
    readonly_fields = ('embedding_display',)  # Use a custom method for display
    exclude = ('embedding',) # Exclude the raw field

    def content_preview(self, obj):
        return obj.content[:50] + "..." if obj.content else ""
    
    def embedding_display(self, obj):
        if obj.embedding is None:
            return "No embedding"
        # Convert to list/string to avoid numpy ambiguity error in Django Admin
        # and truncate for readability
        vec = list(obj.embedding)
        preview = str(vec[:5]) + f" ... ({len(vec)} dimensions)"
        return preview
    
    embedding_display.short_description = "Embedding Preview"
