from views import get_users_data, user_data_view
from rest_framework.routers import DefaultRouter
from django.conf.urls import url

app_name = 'zelda'
router = DefaultRouter()

urlpatterns = [
    url(r'^get_users_data', get_users_data, name='get_user_data'),
    url(r'^$', user_data_view, name='user_data_view'),
] + router.urls

