from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import health_check, ConversationViewSet, DocumentViewSet, user_profile
from .auth_views import signup, login

router = DefaultRouter()
router.register(r'conversations', ConversationViewSet, basename='conversation')
router.register(r'documents', DocumentViewSet, basename='document')

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('signup/', signup, name='signup'),
    path('login/', login, name='login'),
    path('profile/', user_profile, name='user_profile'),
    path('', include(router.urls)),
]
