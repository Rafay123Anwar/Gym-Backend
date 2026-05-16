from django.contrib import admin
from django.urls import path
from strawberry.django.views import GraphQLView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from graphql_api.schema import schema
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('graphql/', csrf_exempt(GraphQLView.as_view(schema=schema))),
]
