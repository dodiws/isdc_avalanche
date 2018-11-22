from django.conf.urls import include, patterns, url
from tastypie.api import Api
from .views import AvalancheRiskStatisticResource, AvalancheForecastStatisticResource, AvalancheStatisticResource

api = Api(api_name='geoapi')

api.register(AvalancheRiskStatisticResource())
api.register(AvalancheForecastStatisticResource())
api.register(AvalancheStatisticResource())

urlpatterns = [
    url(r'', include(api.urls)),
    url(r'^getOverviewMaps/snowinfo$', 'avalanche.views.getSnowVillage', name='getSnowVillage'),   
]
