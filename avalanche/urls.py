from django.conf.urls import include, patterns, url
from tastypie.api import Api
from .views import AvalancheRiskStatisticResource, AvalancheForecastStatisticResource, AvalancheStatisticResource, SnowInfoVillages

api = Api(api_name='geoapi')

api.register(AvalancheRiskStatisticResource())
api.register(AvalancheForecastStatisticResource())
api.register(AvalancheStatisticResource())

# this var will be imported by geonode.urls and registered by getoverviewmaps api
GETOVERVIEWMAPS_APIOBJ = [
    SnowInfoVillages(),
]

urlpatterns = [
    url(r'', include(api.urls)),
    url(r'^getOverviewMaps/snowinfo$', 'avalanche.views.getSnowVillage', name='getSnowVillage'),   
]
