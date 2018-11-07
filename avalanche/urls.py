from django.conf.urls import patterns, url

urlpatterns = [
    url(r'^getOverviewMaps/snowinfo$', 'avalanche.views.getSnowVillage', name='getSnowVillage'),   
]
