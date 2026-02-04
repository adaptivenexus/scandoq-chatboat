from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_delete
from django.dispatch import receiver
import os
import lancedb

class Conversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title or 'Untitled'} ({self.id})"

class Message(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]

    conversation = models.ForeignKey(Conversation, related_name='messages', on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    documents = models.ManyToManyField('Document', related_name='referenced_in_messages', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."

class Document(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)

    def __str__(self):
        return self.title

# Signal to clean up vectors when a document is deleted
@receiver(post_delete, sender=Document)
def delete_document_vectors(sender, instance, **kwargs):
    """
    Delete vectors from S3 LanceDB when a Document is deleted.
    """
    try:
        bucket_name = os.getenv('AWS_STORAGE_BUCKET_NAME')
        if not bucket_name:
            return

        uri = f"s3://{bucket_name}/vectors"
        # Since we can't easily check if table exists without connection which might be slow,
        # we wrap in try-except. And we import lancedb here to avoid circulars if any.
        
        db = lancedb.connect(uri)
        if "documents" in db.table_names():
            table = db.open_table("documents")
            # LanceDB delete syntax: table.delete("document_id = 123")
            table.delete(f"document_id = {instance.id}")
            print(f"Deleted vectors for document {instance.id} from S3.")
            
    except Exception as e:
        print(f"Error deleting vectors for document {instance.id}: {e}")
