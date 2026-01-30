from django.contrib import admin
from .models import Conversation, Message, Document

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


