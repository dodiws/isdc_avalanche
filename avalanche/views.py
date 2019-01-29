from django.shortcuts import render
from .models import (
	AfgAvsa,
	AfgSnowaAverageExtent,
)
from geodb.models import (
	AfgAdmbndaAdm1,
	AfgAdmbndaAdm2,
	AfgAirdrmp,
	# AfgAvsa,
	AfgCapaGsmcvr,
	AfgCaptAdm1ItsProvcImmap,
	AfgCaptAdm1NearestProvcImmap,
	AfgCaptAdm2NearestDistrictcImmap,
	AfgCaptAirdrmImmap,
	AfgCaptHltfacTier1Immap,
	AfgCaptHltfacTier2Immap,
	AfgCaptHltfacTier3Immap,
	AfgCaptHltfacTierallImmap,
	AfgHltfac,
	# AfgIncidentOasis,
	AfgLndcrva,
	AfgPplp,
	AfgRdsl,
	districtsummary,
	# earthquake_events,
	# earthquake_shakemap,
	forecastedLastUpdate,
	LandcoverDescription,
	provincesummary,
	provincesummary,
	tempCurrentSC,
	# villagesummaryEQ,
	)
from geodb.geo_calc import (
	getBaseline,
	getCommonUse,
	# getFloodForecastBySource,
	# getFloodForecastMatrix,
	getGeoJson,
	getProvinceSummary_glofas,
	getProvinceSummary,
	getRawBaseLine,
	# getRawFloodRisk,
	# getSettlementAtFloodRisk,
	getShortCutData,
	getTotalArea,
	getTotalBuildings,
	getTotalPop,
	getTotalSettlement,
	getRiskNumber,
	)
from geodb.views import (
	getCommonVillageData,
	)
from django.db import connection, connections
from django.db.models import Count, Sum
from geonode.maps.views import _resolve_map, _PERMISSION_MSG_VIEW
from geonode.utils import include_section, none_to_zero, query_to_dicts, RawSQL_nogroupby, ComboChart, merge_dict, div_by_zero_is_zero, dict_ext, linenum
from matrix.models import matrix
from pprint import pprint
from pytz import timezone, all_timezones
from tastypie.cache import SimpleCache
from tastypie.resources import ModelResource, Resource
from urlparse import urlparse
from graphos.renderers import flot, gchart
from graphos.sources.simple import SimpleDataSource
from django.utils.translation import ugettext as _
from django.shortcuts import render_to_response
from django.template import RequestContext

import json
import time, datetime
import timeago

# from geodb.views
from django.conf import settings
from django.contrib.gis.utils import LayerMapping
from ftplib import FTP
from geodb.views import GS_TMP_DIR, initial_data_path, gdal_path, cleantmpfile
import gzip
import os
import subprocess
from geodb.enumerations import HEALTHFAC_TYPES, LANDCOVER_TYPES, AVA_LIKELIHOOD_INDEX, AVA_LIKELIHOOD_TYPES, AVA_LIKELIHOOD_INVERSE, AVA_LIKELIHOOD_INDEX
from django.conf.urls import url
from tastypie.utils import trailing_slash
from tastypie.authentication import BasicAuthentication, SessionAuthentication, OAuthAuthentication

def get_dashboard_meta(*args,**kwargs):
	# if page_name in ['avalancheforecast', 'avalcheforecast']:
	#     return {'function':dashboard_avalancheforecast, 'template':'dash_aforecast.html'}
	# elif page_name == 'avalancherisk':
	#     return {'function':dashboard_avalancherisk, 'template':'dash_arisk.html'}
	response = {
		'pages': [
			{
				'name': 'avalancheforecast',
				'function': dashboard_avalancheforecast, 
				'template': 'dash_aforecast.html',
				'menutitle': 'Avalanche Forecast',
			},
			{
				'name': 'avalancherisk',
				'function': dashboard_avalancherisk, 
				'template': 'dash_arisk.html',
				'menutitle': 'Avalanche Risk',
			},
		],
		'menutitle': 'Avalanche',
	}
	
	return response

# from geodb.geo_calc

def getAvalancheForecast(request, filterLock, flag, code, includes=[], excludes=[], date='', response=dict_ext()):
	# response = dict_ext()
	targetBase = AfgLndcrva.objects.all()
	
	# FIXME: use values from provincesummary but only after building data present
	response['baseline'] = response.pathget('cache','getBaseline','baseline') or getBaseline(request, filterLock, flag, code, includes=['pop_lc','building_lc'])
	response['avalancherisk'] = response.pathget('cache','getBaseline','avalancherisk') or getRawAvalancheRisk(filterLock, flag, code)

	# because building data not in provincesummary yet
	# response['avalancheforecast'] = response.pathget('cache','getBaseline','avalancheforecast') or getRawAvalancheForecast(request, filterLock, flag, code, date)
	response['avalancheforecast'] = getRawAvalancheForecast(request, filterLock, flag, code, date)

	response.path('avalancheforecast')['pop_forecast_percent'] = {k:round(div_by_zero_is_zero(v, response['baseline']['pop_total'])*100, 0) for k,v in response['avalancheforecast']['pop_likelihood'].items()}
	response.path('avalancheforecast')['pop_forecast_percent_total'] = sum(response['avalancheforecast']['pop_forecast_percent'].values())

	if include_section('adm_likelihood', includes, excludes):
		if 'date' not in request.GET:
			response.path('avalancheforecast')['adm_likelihood'] = getProvinceSummary(filterLock, flag, code)

			for i in response.path('avalancheforecast')['adm_likelihood']:
				i['total_pop_forecast_percent'] = int(round(i['total_ava_forecast_pop']/i['Population']*100,0))
				i['high_pop_forecast_percent'] = int(round(i['ava_forecast_high_pop']/i['Population']*100,0))
				i['med_pop_forecast_percent'] = int(round(i['ava_forecast_med_pop']/i['Population']*100,0))
				i['low_pop_forecast_percent'] = int(round(i['ava_forecast_low_pop']/i['Population']*100,0))

	if include_section('GeoJson', includes, excludes):
		response['GeoJson'] = getGeoJson(request, flag, code)

	return response

def getAvalancheForecast_ORIG(request, filterLock, flag, code, includes=[], excludes=[]):
	targetBase = AfgLndcrva.objects.all()
	response = getCommonUse(request, flag, code)

	if flag not in ['entireAfg','currentProvince']:
		response['Population']=getTotalPop(filterLock, flag, code, targetBase)
		response['Buildings']=getTotalBuildings(filterLock, flag, code, targetBase)
	else :
		tempData = getShortCutData(flag,code)
		response['Population']= tempData['Population']
		response['Buildings']= tempData['total_buildings']

	rawAvalancheRisk = getRawAvalancheRisk(filterLock, flag, code)
	for i in rawAvalancheRisk:
		response[i]=rawAvalancheRisk[i]

	rawAvalancheForecast = getRawAvalancheForecast(request, filterLock, flag, code)

	for i in rawAvalancheForecast:
		response[i]=rawAvalancheForecast[i]

	response['total_pop_forecast_percent'] = int(round(((response['total_ava_forecast_pop'] or 0)/(response['Population'] or 0))*100,0))
	response['high_pop_forecast_percent'] = int(round(((response['ava_forecast_high_pop'] or 0)/(response['Population'] or 0))*100,0))
	response['med_pop_forecast_percent'] = int(round(((response['ava_forecast_med_pop'] or 0)/(response['Population'] or 0))*100,0))
	response['low_pop_forecast_percent'] = int(round(((response['ava_forecast_low_pop'] or 0)/(response['Population'] or 0))*100,0))

	data1 = []
	data1.append(['agg_simplified_description','area_population'])
	data1.append(['',response['total_ava_forecast_pop']])
	data1.append(['',response['Population']-response['total_ava_forecast_pop']])
	response['total_pop_forecast_chart'] = gchart.PieChart(SimpleDataSource(data=data1), html_id="pie_chart1", options={'title':'', 'width': 135,'height': 135, 'pieSliceText': 'number', 'pieSliceTextStyle': 'black','legend': 'none', 'pieHole': 0.75, 'slices':{0:{'color':'red'},1:{'color':'grey'}}, 'pieStartAngle': 270, 'tooltip': { 'trigger': 'none' }, })

	data2 = []
	data2.append(['agg_simplified_description','area_population'])
	data2.append(['',response['ava_forecast_high_pop']])
	data2.append(['',response['Population']-response['ava_forecast_high_pop']])
	response['high_pop_forecast_chart'] = gchart.PieChart(SimpleDataSource(data=data2), html_id="pie_chart2", options={'title':'', 'width': 135,'height': 135, 'pieSliceText': 'number', 'pieSliceTextStyle': 'black','legend': 'none', 'pieHole': 0.75, 'slices':{0:{'color':'red'},1:{'color':'grey'}}, 'pieStartAngle': 270, 'tooltip': { 'trigger': 'none' }, })

	data3 = []
	data3.append(['agg_simplified_description','area_population'])
	data3.append(['',response['ava_forecast_med_pop']])
	data3.append(['',response['Population']-response['ava_forecast_med_pop']])
	response['med_pop_forecast_chart'] = gchart.PieChart(SimpleDataSource(data=data3), html_id="pie_chart3", options={'title':'', 'width': 135,'height': 135, 'pieSliceText': 'number', 'pieSliceTextStyle': 'black','legend': 'none', 'pieHole': 0.75, 'slices':{0:{'color':'red'},1:{'color':'grey'}}, 'pieStartAngle': 270, 'tooltip': { 'trigger': 'none' }, })

	data4 = []
	data4.append(['agg_simplified_description','area_population'])
	data4.append(['',response['ava_forecast_low_pop']])
	data4.append(['',response['Population']-response['ava_forecast_low_pop']])
	response['low_pop_forecast_chart'] = gchart.PieChart(SimpleDataSource(data=data4), html_id="pie_chart4", options={'title':'', 'width': 135,'height': 135, 'pieSliceText': 'number', 'pieSliceTextStyle': 'black','legend': 'none', 'pieHole': 0.75, 'slices':{0:{'color':'red'},1:{'color':'grey'}}, 'pieStartAngle': 270, 'tooltip': { 'trigger': 'none' }, })

	if 'date' not in request.GET:
		data = getProvinceSummary(filterLock, flag, code)

		for i in data:
			i['total_pop_forecast_percent'] = int(round(i['total_ava_forecast_pop']/i['Population']*100,0))
			i['high_pop_forecast_percent'] = int(round(i['ava_forecast_high_pop']/i['Population']*100,0))
			i['med_pop_forecast_percent'] = int(round(i['ava_forecast_med_pop']/i['Population']*100,0))
			i['low_pop_forecast_percent'] = int(round(i['ava_forecast_low_pop']/i['Population']*100,0))

		response['lc_child']=data

	#if include_section('GeoJson', includes, excludes):
	response['GeoJson'] = json.dumps(getGeoJson(request, flag, code))

	return response

def getRawAvalancheForecast(request, filterLock, flag, code, date=''):

	# includeDetailState = True
	# if 'date' in request.GET:
	# 	curdate = datetime.datetime(int(request.GET['date'].split('-')[0]), int(request.GET['date'].split('-')[1]), int(request.GET['date'].split('-')[2]), 00, 00)
	# 	includeDetailState = False
	# else:
	# 	curdate = datetime.datetime.utcnow()

	# YEAR = curdate.strftime("%Y")
	# MONTH = curdate.strftime("%m")
	# DAY = curdate.strftime("%d")

	try:
		YEAR, MONTH, DAY = date.split('-')
	except Exception as e:
		YEAR, MONTH, DAY = datetime.datetime.utcnow().strftime("%Y %m %d").split()

	# Avalanche Forecasted
	if flag=='entireAfg':
		# cursor = connections['geodb'].cursor()
		sql = "select forcastedvalue.riskstate, \
			sum(afg_avsa.avalanche_pop) as pop, \
			sum(afg_avsa.area_buildings) as buildings \
			FROM afg_avsa \
			INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
			INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
			INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
			WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
			AND forcastedvalue.datadate = '%s-%s-%s' \
			AND forcastedvalue.forecasttype = 'snowwater' ) \
			GROUP BY forcastedvalue.riskstate" %(YEAR,MONTH,DAY)
		# row = cursor.fetchall()
		# cursor.close()
	elif flag=='currentProvince':
		# cursor = connections['geodb'].cursor()
		if len(str(code)) > 2:
			ff0001 =  "dist_code  = '"+str(code)+"'"
		else :
			ff0001 =  "prov_code  = '"+str(code)+"'"
		sql = "select forcastedvalue.riskstate, \
			sum(afg_avsa.avalanche_pop) as pop, \
			sum(afg_avsa.area_buildings) as buildings \
			FROM afg_avsa \
			INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
			INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
			INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
			WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
			AND forcastedvalue.datadate = '%s-%s-%s' \
			AND forcastedvalue.forecasttype = 'snowwater' ) \
			and afg_avsa.%s \
			GROUP BY forcastedvalue.riskstate" %(YEAR,MONTH,DAY,ff0001)
		# row = cursor.fetchall()
		# cursor.close()
	elif flag=='drawArea':
		# cursor = connections['geodb'].cursor()
		sql = "select forcastedvalue.riskstate, \
			sum(case \
				when ST_CoveredBy(afg_avsa.wkb_geometry , %s) then afg_avsa.avalanche_pop \
				else st_area(st_intersection(afg_avsa.wkb_geometry, %s)) / st_area(afg_avsa.wkb_geometry)* avalanche_pop end \
			) as pop, \
			sum(afg_avsa.area_buildings) as buildings \
			FROM afg_avsa \
			INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
			INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
			INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
			WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
			AND forcastedvalue.datadate = '%s-%s-%s' \
			AND forcastedvalue.forecasttype = 'snowwater' ) \
			GROUP BY forcastedvalue.riskstate" %(filterLock,filterLock,YEAR,MONTH,DAY)
		# row = cursor.fetchall()
		# cursor.close()
	else:
		# cursor = connections['geodb'].cursor()
		sql = "select forcastedvalue.riskstate, \
			sum(afg_avsa.avalanche_pop) as pop, \
			sum(afg_avsa.area_buildings) as buildings \
			FROM afg_avsa \
			INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
			INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
			INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
			WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
			AND forcastedvalue.datadate = '%s-%s-%s' \
			AND forcastedvalue.forecasttype = 'snowwater' ) \
			AND ST_Within(afg_avsa.wkb_geometry, %s) \
			GROUP BY forcastedvalue.riskstate" %(YEAR,MONTH,DAY,filterLock)
		# row = cursor.fetchall()
		# cursor.close()

	# cursor = connections['geodb'].cursor()
	# row = query_to_dicts(cursor, sql)
	# counts = []
	# for i in row:
	# 	counts.append(i)
	# cursor.close()

	with connections['geodb'].cursor() as cursor:
		counts = list(query_to_dicts(cursor, sql))

	response = {}
	for i,j in {'pop':'pop','building':'buildings'}.items():
		temp = dict([(c['riskstate'], c[j]) for c in counts])
		response[i+'_likelihood'] = {v:temp.get(int(k)) or 0 for k,v in AVA_LIKELIHOOD_INDEX.items()}
		response[i+'_likelihood_total'] = sum(response[i+'_likelihood'].values())

	# dict_pop = dict([(c['riskstate'], c['pop']) for c in counts])
	# response['ava_forecast_low_pop']=round(dict_pop.get(1, 0) or 0,0)
	# response['ava_forecast_med_pop']=round(dict_pop.get(2, 0) or 0,0)
	# response['ava_forecast_high_pop']=round(dict_pop.get(3, 0) or 0,0)
	# response['total_ava_forecast_pop']=response['ava_forecast_low_pop'] + response['ava_forecast_med_pop'] + response['ava_forecast_high_pop']

	# dict_buildings = dict([(c['riskstate'], c['buildings']) for c in counts])
	# response['ava_forecast_low_buildings']=round(dict_buildings.get(1, 0) or 0,0)
	# response['ava_forecast_med_buildings']=round(dict_buildings.get(2, 0) or 0,0)
	# response['ava_forecast_high_buildings']=round(dict_buildings.get(3, 0) or 0,0)
	# response['total_ava_forecast_buildings']=response['ava_forecast_low_buildings'] + response['ava_forecast_med_buildings'] + response['ava_forecast_high_buildings']

	return response

def getAvalancheRisk(request, filterLock, flag, code, includes=[], excludes=[], response=dict_ext()):
	# response = dict_ext()

	targetBase = AfgLndcrva.objects.all()

	# TODO: add avalanche risk building data to provincesummary
	response['baseline'] = response.pathget('cache','getBaseline','baseline') or getBaseline(request, filterLock, flag, code, includes=['pop_lc','building_lc'])
	# if flag not in ['entireAfg','currentProvince']:
	#     response['Population']=getTotalPop(filterLock, flag, code, targetBase)
	#     response['Area']=getTotalArea(filterLock, flag, code, targetBase)
	#     response['Buildings']=getTotalBuildings(filterLock, flag, code, targetBase)
	#     response['settlement']=getTotalSettlement(filterLock, flag, code, targetBase)
	# else :
	#     tempData = getShortCutData(flag,code)
	#     response['Population']= tempData['Population']
	#     response['Area']= tempData['Area']
	#     response['Buildings']= tempData['total_buildings']
	#     response['settlement']= tempData['settlements']

	response['avalancherisk'] = response.pathget('cache','getBaseline','avalancherisk') or getRawAvalancheRisk(filterLock, flag, code)
	# rawAvalancheRisk = getRawAvalancheRisk(filterLock, flag, code)
	# for i in rawAvalancheRisk:
	#     response[i]=rawAvalancheRisk[i]

	response.path('avalancherisk')['pop_likelihood_percent'] = {k:round(div_by_zero_is_zero(v, response['baseline']['pop_total'])*100, 0) for k,v in response['avalancherisk']['pop_likelihood'].items()}
	response.path('avalancherisk')['pop_likelihood_total_percent'] = sum(response.path('avalancherisk')['pop_likelihood_percent'].values())

	response.path('avalancherisk')['area_likelihood_percent'] = {k:round(div_by_zero_is_zero(v, response['baseline']['area_total'])*100, 0) for k,v in response['avalancherisk']['area_likelihood'].items()}
	response.path('avalancherisk')['area_likelihood_total_percent'] = sum(response.path('avalancherisk')['area_likelihood_percent'].values())

	response.path('avalancherisk')['building_likelihood_percent'] = {k:round(div_by_zero_is_zero(v, response['baseline']['building_total'])*100, 0) for k,v in response['avalancherisk']['building_likelihood'].items()}
	response.path('avalancherisk')['building_likelihood_total_percent'] = sum(response.path('avalancherisk')['building_likelihood_percent'].values())

	# response['total_pop_atrisk_percent'] = int(round(((response['total_ava_population'] or 0)/(response['Population'] or 1))*100,0))
	# response['total_area_atrisk_percent'] = int(round(((response['total_ava_area'] or 0)/(response['Area'] or 1))*100,0))

	# response['total_pop_high_atrisk_percent'] = int(round(((response['high_ava_population'] or 0)/(response['Population'] or 1))*100,0))
	# response['total_area_high_atrisk_percent'] = int(round(((response['high_ava_area'] or 0)/(response['Area'] or 1))*100,0))

	# response['total_pop_med_atrisk_percent'] = int(round(((response['med_ava_population'] or 0)/(response['Population'] or 1))*100,0))
	# response['total_area_med_atrisk_percent'] = int(round(((response['med_ava_area'] or 0)/(response['Area'] or 1))*100,0))

	# data1 = []
	# data1.append(['agg_simplified_description','area_population'])
	# data1.append(['',response['total_ava_population']])
	# data1.append(['',response['Population']-response['total_ava_population']])
	# response['total_pop_atrisk_chart'] = gchart.PieChart(SimpleDataSource(data=data1), html_id="pie_chart1", options={'title':'', 'width': 135,'height': 135, 'pieSliceText': 'number', 'pieSliceTextStyle': 'black','legend': 'none', 'pieHole': 0.75, 'slices':{0:{'color':'red'},1:{'color':'grey'}}, 'pieStartAngle': 270, 'tooltip': { 'trigger': 'none' }, })

	# data2 = []
	# data2.append(['agg_simplified_description','area_population'])
	# data2.append(['',response['total_ava_area']])
	# data2.append(['',response['Area']-response['total_ava_area']])
	# response['total_area_atrisk_chart'] = gchart.PieChart(SimpleDataSource(data=data2), html_id="pie_chart2", options={'title':'', 'width': 135,'height': 135, 'pieSliceText': 'number', 'pieSliceTextStyle': 'black','legend': 'none', 'pieHole': 0.75, 'slices':{0:{'color':'red'},1:{'color':'grey'}}, 'pieStartAngle': 270, 'tooltip': { 'trigger': 'none' }, })

	# data3 = []
	# data3.append(['agg_simplified_description','area_population'])
	# data3.append(['',response['high_ava_population']])
	# data3.append(['',response['Population']-response['high_ava_population']])
	# response['high_pop_atrisk_chart'] = gchart.PieChart(SimpleDataSource(data=data3), html_id="pie_chart3", options={'title':'', 'width': 135,'height': 135, 'pieSliceText': 'number', 'pieSliceTextStyle': 'black','legend': 'none', 'pieHole': 0.75, 'slices':{0:{'color':'red'},1:{'color':'grey'}}, 'pieStartAngle': 270, 'tooltip': { 'trigger': 'none' }, })

	# data4 = []
	# data4.append(['agg_simplified_description','area_population'])
	# data4.append(['',response['med_ava_population']])
	# data4.append(['',response['Population']-response['med_ava_population']])
	# response['med_pop_atrisk_chart'] = gchart.PieChart(SimpleDataSource(data=data4), html_id="pie_chart4", options={'title':'', 'width': 135,'height': 135, 'pieSliceText': 'number', 'pieSliceTextStyle': 'black','legend': 'none', 'pieHole': 0.75, 'slices':{0:{'color':'red'},1:{'color':'grey'}}, 'pieStartAngle': 270, 'tooltip': { 'trigger': 'none' }, })

	data = getProvinceSummary(filterLock, flag, code)

	for i in data:
		i['total_pop_atrisk_percent'] = int(round((i['total_ava_population'] or 0)/(i['Population'] or 1)*100,0))
		i['total_area_atrisk_percent'] = int(round((i['total_ava_area'] or 0)/(i['Area'] or 1)*100,0))
		i['total_pop_high_atrisk_percent'] = int(round((i['high_ava_population'] or 0)/(i['Population'] or 1)*100,0))
		i['total_area_high_atrisk_percent'] = int(round((i['high_ava_area'] or 0)/(i['Area'] or 1)*100,0))
		i['total_pop_med_atrisk_percent'] = int(round((i['med_ava_population'] or 0)/(i['Population'] or 1)*100,0))
		i['total_area_med_atrisk_percent'] = int(round((i['med_ava_area'] or 0)/(i['Area'] or 1)*100,0))

	response['adm_lc']=data

	if include_section('GeoJson', includes, excludes):
		response['GeoJson'] = getGeoJson(request, flag, code)

	return response

def getRawAvalancheRisk(filterLock, flag, code):
	response = dict_ext()
	targetAvalanche = AfgAvsa.objects.all()
	counts =  getRiskNumber(targetAvalanche, filterLock, 'avalanche_cat', 'avalanche_pop', 'sum_area_sqm', 'area_buildings', flag, code, None)
	# pprint.pprint(counts)
	# pop at risk level
	for i,j in {'pop':'count','area':'areaatrisk','building':'houseatrisk'}.items():
		temp = dict([(c['avalanche_cat'], c[j]) for c in counts])
		response[i+'_likelihood'] = {k:temp.get(v) or 0 for k,v in AVA_LIKELIHOOD_TYPES.items()}
		response[i+'_likelihood']['low'] = 0
		response[i+'_likelihood_total'] = sum(response[i+'_likelihood'].values())

	response['area_likelihood'] = {k:round(v/1000000,1) for k,v in response['area_likelihood'].items()}
	response['area_likelihood_total'] = sum(response['area_likelihood'].values())

	# response['high_ava_population']=round(temp.get('High', 0) or 0,0)
	# response['med_ava_population']=round(temp.get('Moderate', 0) or 0, 0)
	# response['low_ava_population']=0
	# response['total_ava_population']=response['high_ava_population']+response['med_ava_population']+response['low_ava_population']

	# # area at risk level
	# temp = dict([(c['avalanche_cat'], c['areaatrisk']) for c in counts])
	# response['high_ava_area']=round((temp.get('High', 0) or 0)/1000000,1)
	# response['med_ava_area']=round((temp.get('Moderate', 0) or 0)/1000000,1)
	# response['low_ava_area']=0
	# response['total_ava_area']=round(response['high_ava_area']+response['med_ava_area']+response['low_ava_area'],2)

	# # buildings at risk level
	# temp = dict([(c['avalanche_cat'], c['houseatrisk']) for c in counts])
	# response['high_ava_buildings']=round(temp.get('High', 0) or 0,0)
	# response['med_ava_buildings']=round(temp.get('Moderate', 0) or 0, 0)
	# response['low_ava_buildings']=0
	# response['total_ava_buildings']=response['high_ava_buildings']+response['med_ava_buildings']+response['low_ava_buildings']

	return response

# from geodb.geoapi

def getRiskExecuteExternal(filterLock, flag, code, yy=None, mm=None, dd=None, rf_type=None, bring=None, init_response=dict_ext()):
		date_params = False
		response_tree = init_response

		if yy and mm and dd:
			date_params = True
			YEAR = yy
			MONTH = mm
			DAY = dd
		else:    
			YEAR = datetime.datetime.utcnow().strftime("%Y")
			MONTH = datetime.datetime.utcnow().strftime("%m")
			DAY = datetime.datetime.utcnow().strftime("%d")
		
		# targetRiskIncludeWater = AfgFldzonea100KRiskLandcoverPop.objects.all()
		# targetRisk = targetRiskIncludeWater.exclude(agg_simplified_description='Water body and Marshland')
		# targetBase = AfgLndcrva.objects.all()
		targetAvalanche = AfgAvsa.objects.all()
		# print targetAvalanche.query
		# response = response_base

		if flag not in ['entireAfg','currentProvince'] or date_params:

			#Avalanche Risk
			counts =  getRiskNumber(targetAvalanche, filterLock, 'avalanche_cat', 'avalanche_pop', 'sum_area_sqm', 'area_buildings', flag, code, None)
			# pop at risk level
			temp = dict([(c['avalanche_cat'], c['count']) for c in counts])
			response_tree.path('avalancherisk')['pop_likelihood'] = {t:round(temp.get(v) or 0) for t,v in AVA_LIKELIHOOD_TYPES.items()}
			response_tree.path('avalancherisk')['pop_likelihood']['low'] = 0
			response_tree.path('avalancherisk')['pop_likelihood_total'] = sum(response_tree.path('avalancherisk')['pop_likelihood'].values())
			# response = response_tree.path('avalancherisk','population','table')
			# response['high_ava_population']=round(temp.get('High', 0) or 0,0)
			# response['med_ava_population']=round(temp.get('Moderate', 0) or 0,0)
			# response['low_ava_population']=0
			# response['total_ava_population']=response['high_ava_population']+response['med_ava_population']+response['low_ava_population']

			# area at risk level
			temp = dict([(c['avalanche_cat'], c['areaatrisk']) for c in counts])
			response_tree.path('avalancherisk')['area_likelihood'] = {t:round(temp.get(v) or 0) for t,v in AVA_LIKELIHOOD_TYPES.items()}
			response_tree.path('avalancherisk')['area_likelihood']['low'] = 0
			response_tree.path('avalancherisk')['area_likelihood_total'] = sum(response_tree.path('avalancherisk')['area_likelihood'].values())
			# response = response_tree['avalancherisk']['area']['table']
			# response['high_ava_area']=round((temp.get('High', 0) or 0)/1000000,1)
			# response['med_ava_area']=round((temp.get('Moderate', 0) or 0)/1000000,1)
			# response['low_ava_area']=0    
			# response['total_ava_area']=round(response['high_ava_area']+response['med_ava_area']+response['low_ava_area'],2) 

			# Number of Building on Avalanche Risk
			temp = dict([(c['avalanche_cat'], c['houseatrisk']) for c in counts])
			response_tree.path('avalancherisk')['building_likelihood'] = {t:round(temp.get(v) or 0) for t,v in AVA_LIKELIHOOD_TYPES.items()}
			response_tree.path('avalancherisk')['building_likelihood']['low'] = 0
			response_tree.path('avalancherisk')['building_likelihood_total'] = sum(response_tree.path('avalancherisk')['building_likelihood'].values())
			# response = response_tree['avalancherisk']['buildings']['table']
			# response['high_ava_buildings']=temp.get('High', 0) or 0
			# response['med_ava_buildings']=temp.get('Moderate', 0) or 0
			# response['total_ava_buildings'] = response['high_ava_buildings']+response['med_ava_buildings']

			# # Flood Risk
			# counts =  getRiskNumber(targetRisk.exclude(mitigated_pop__gt=0), filterLock, 'deeperthan', 'fldarea_population', 'fldarea_sqm', 'area_buildings', flag, code, None)
			
			# # pop at risk level
			# temp = dict([(c['deeperthan'], c['count']) for c in counts])
			# response['high_risk_population']=round((temp.get('271 cm', 0) or 0),0)
			# response['med_risk_population']=round((temp.get('121 cm', 0) or 0), 0)
			# response['low_risk_population']=round((temp.get('029 cm', 0) or 0),0)
			# response['total_risk_population']=response['high_risk_population']+response['med_risk_population']+response['low_risk_population']

			# # area at risk level
			# temp = dict([(c['deeperthan'], c['areaatrisk']) for c in counts])
			# response['high_risk_area']=round((temp.get('271 cm', 0) or 0)/1000000,1)
			# response['med_risk_area']=round((temp.get('121 cm', 0) or 0)/1000000,1)
			# response['low_risk_area']=round((temp.get('029 cm', 0) or 0)/1000000,1)    
			# response['total_risk_area']=round(response['high_risk_area']+response['med_risk_area']+response['low_risk_area'],2) 

			# # buildings at flood risk
			# temp = dict([(c['deeperthan'], c['houseatrisk']) for c in counts])
			# response['total_risk_buildings'] = 0
			# response['total_risk_buildings']+=temp.get('271 cm', 0) or 0
			# response['total_risk_buildings']+=temp.get('121 cm', 0) or 0
			# response['total_risk_buildings']+=temp.get('029 cm', 0) or 0

			# counts =  getRiskNumber(targetRiskIncludeWater.exclude(mitigated_pop__gt=0), filterLock, 'agg_simplified_description', 'fldarea_population', 'fldarea_sqm', 'area_buildings', flag, code, None)

			# # landcover/pop/atrisk
			# temp = dict([(c['agg_simplified_description'], c['count']) for c in counts])
			# response['water_body_pop_risk']=round(temp.get('Water body and Marshland', 0) or 0,0)
			# response['barren_land_pop_risk']=round(temp.get('Barren land', 0) or 0,0)
			# response['built_up_pop_risk']=round(temp.get('Build Up', 0) or 0,0)
			# response['fruit_trees_pop_risk']=round(temp.get('Fruit Trees', 0) or 0,0)
			# response['irrigated_agricultural_land_pop_risk']=round(temp.get('Irrigated Agricultural Land', 0) or 0,0)
			# response['permanent_snow_pop_risk']=round(temp.get('Snow', 0) or 0,0)
			# response['rainfed_agricultural_land_pop_risk']=round(temp.get('Rainfed', 0) or 0,0)
			# response['rangeland_pop_risk']=round(temp.get('Rangeland', 0) or 0,0)
			# response['sandcover_pop_risk']=round(temp.get('Sand Covered Areas', 0) or 0,0)
			# response['vineyards_pop_risk']=round(temp.get('Vineyards', 0) or 0,0)
			# response['forest_pop_risk']=round(temp.get('Forest & Shrub', 0) or 0,0)
			# response['sand_dunes_pop_risk']=round(temp.get('Sand Dunes', 0) or 0,0)

			# temp = dict([(c['agg_simplified_description'], c['areaatrisk']) for c in counts])
			# response['water_body_area_risk']=round((temp.get('Water body and Marshland', 0) or 0)/1000000,1)
			# response['barren_land_area_risk']=round((temp.get('Barren land', 0) or 0)/1000000,1)
			# response['built_up_area_risk']=round((temp.get('Build Up', 0) or 0)/1000000,1)
			# response['fruit_trees_area_risk']=round((temp.get('Fruit Trees', 0) or 0)/1000000,1)
			# response['irrigated_agricultural_land_area_risk']=round((temp.get('Irrigated Agricultural Land', 0) or 0)/1000000,1)
			# response['permanent_snow_area_risk']=round((temp.get('Snow', 0) or 0)/1000000,1)
			# response['rainfed_agricultural_land_area_risk']=round((temp.get('Rainfed', 0) or 0)/1000000,1)
			# response['rangeland_area_risk']=round((temp.get('Rangeland', 0) or 0)/1000000,1)
			# response['sandcover_area_risk']=round((temp.get('Sand Covered Areas', 0) or 0)/1000000,1)
			# response['vineyards_area_risk']=round((temp.get('Vineyards', 0) or 0)/1000000,1)
			# response['forest_area_risk']=round((temp.get('Forest & Shrub', 0) or 0)/1000000,1)
			# response['sand_dunes_area_risk']=round((temp.get('Sand Dunes', 0) or 0)/1000000,1)

			


			# # landcover all
			# counts =  getRiskNumber(targetBase, filterLock, 'agg_simplified_description', 'area_population', 'area_sqm', 'area_buildings', flag, code, None)
			# temp = dict([(c['agg_simplified_description'], c['count']) for c in counts])
			# response['water_body_pop']=round(temp.get('Water body and Marshland', 0),0)
			# response['barren_land_pop']=round(temp.get('Barren land', 0),0)
			# response['built_up_pop']=round(temp.get('Build Up', 0),0)
			# response['fruit_trees_pop']=round(temp.get('Fruit Trees', 0),0)
			# response['irrigated_agricultural_land_pop']=round(temp.get('Irrigated Agricultural Land', 0),0)
			# response['permanent_snow_pop']=round(temp.get('Snow', 0),0)
			# response['rainfed_agricultural_land_pop']=round(temp.get('Rainfed', 0),0)
			# response['rangeland_pop']=round(temp.get('Rangeland', 0),0)
			# response['sandcover_pop']=round(temp.get('Sand Covered Areas', 0),0)
			# response['vineyards_pop']=round(temp.get('Vineyards', 0),0)
			# response['forest_pop']=round(temp.get('Forest & Shrub', 0),0)
			# response['sand_dunes_pop']=round(temp.get('Sand Dunes', 0),0)

			# temp = dict([(c['agg_simplified_description'], c['areaatrisk']) for c in counts])
			# response['water_body_area']=round(temp.get('Water body and Marshland', 0)/1000000,1)
			# response['barren_land_area']=round(temp.get('Barren land', 0)/1000000,1)
			# response['built_up_area']=round(temp.get('Build Up', 0)/1000000,1)
			# response['fruit_trees_area']=round(temp.get('Fruit Trees', 0)/1000000,1)
			# response['irrigated_agricultural_land_area']=round(temp.get('Irrigated Agricultural Land', 0)/1000000,1)
			# response['permanent_snow_area']=round(temp.get('Snow', 0)/1000000,1)
			# response['rainfed_agricultural_land_area']=round(temp.get('Rainfed', 0)/1000000,1)
			# response['rangeland_area']=round(temp.get('Rangeland', 0)/1000000,1)
			# response['sandcover_area']=round(temp.get('Sand Covered Areas', 0)/1000000,1)
			# response['vineyards_area']=round(temp.get('Vineyards', 0)/1000000,1)
			# response['forest_area']=round(temp.get('Forest & Shrub', 0)/1000000,1)
			# response['sand_dunes_area']=round(temp.get('Sand Dunes', 0)/1000000,1)

			# # total buildings
			# temp = dict([(c['agg_simplified_description'], c['houseatrisk']) for c in counts])
			# response['total_buildings'] = 0
			# response['total_buildings']+=temp.get('Water body and Marshland', 0) or 0
			# response['total_buildings']+=temp.get('Barren land', 0) or 0
			# response['total_buildings']+=temp.get('Build Up', 0) or 0
			# response['total_buildings']+=temp.get('Fruit Trees', 0) or 0
			# response['total_buildings']+=temp.get('Irrigated Agricultural Land', 0) or 0
			# response['total_buildings']+=temp.get('Snow', 0) or 0
			# response['total_buildings']+=temp.get('Rainfed', 0) or 0
			# response['total_buildings']+=temp.get('Rangeland', 0) or 0
			# response['total_buildings']+=temp.get('Sand Covered Areas', 0) or 0
			# response['total_buildings']+=temp.get('Vineyards', 0) or 0
			# response['total_buildings']+=temp.get('Forest & Shrub', 0) or 0
			# response['total_buildings']+=temp.get('Sand Dunes', 0) or 0

			# # Number settlement at risk of flood
			# if flag=='drawArea':
			#     countsBase = targetRisk.exclude(mitigated_pop__gt=0).filter(agg_simplified_description='Build Up').extra(
			#         select={
			#             'numbersettlementsatrisk': 'count(distinct vuid)'}, 
			#         where = {'st_area(st_intersection(wkb_geometry,'+filterLock+')) / st_area(wkb_geometry)*fldarea_sqm > 1 and ST_Intersects(wkb_geometry, '+filterLock+')'}).values('numbersettlementsatrisk')
			# elif flag=='entireAfg':
			#     countsBase = targetRisk.exclude(mitigated_pop__gt=0).filter(agg_simplified_description='Build Up').extra(
			#         select={
			#             'numbersettlementsatrisk': 'count(distinct vuid)'}).values('numbersettlementsatrisk')
			# elif flag=='currentProvince':
			#     if len(str(code)) > 2:
			#         ff0001 =  "dist_code  = '"+str(code)+"'"
			#     else :
			#         ff0001 =  "prov_code  = '"+str(code)+"'"
			#     countsBase = targetRisk.exclude(mitigated_pop__gt=0).filter(agg_simplified_description='Build Up').extra(
			#         select={
			#             'numbersettlementsatrisk': 'count(distinct vuid)'}, 
			#         where = {ff0001}).values('numbersettlementsatrisk')
			# elif flag=='currentBasin':
			#     countsBase = targetRisk.exclude(mitigated_pop__gt=0).filter(agg_simplified_description='Build Up').extra(
			#         select={
			#             'numbersettlementsatrisk': 'count(distinct vuid)'}, 
			#         where = {"vuid = '"+str(code)+"'"}).values('numbersettlementsatrisk')    
			# else:
			#     countsBase = targetRisk.exclude(mitigated_pop__gt=0).filter(agg_simplified_description='Build Up').extra(
			#         select={
			#             'numbersettlementsatrisk': 'count(distinct vuid)'}, 
			#         where = {'ST_Within(wkb_geometry, '+filterLock+')'}).values('numbersettlementsatrisk')

			# response['settlements_at_risk'] = round(countsBase[0]['numbersettlementsatrisk'],0)

		#     # number all settlements
		#     if flag=='drawArea':
		#         countsBase = targetBase.exclude(agg_simplified_description='Water body and Marshland').extra(
		#             select={
		#                 'numbersettlements': 'count(distinct vuid)'}, 
		#             where = {'st_area(st_intersection(wkb_geometry,'+filterLock+')) / st_area(wkb_geometry)*area_sqm > 1 and ST_Intersects(wkb_geometry, '+filterLock+')'}).values('numbersettlements')
		#     elif flag=='entireAfg':
		#         countsBase = targetBase.exclude(agg_simplified_description='Water body and Marshland').extra(
		#             select={
		#                 'numbersettlements': 'count(distinct vuid)'}).values('numbersettlements')
		#     elif flag=='currentProvince':
		#         if len(str(code)) > 2:
		#             ff0001 =  "dist_code  = '"+str(code)+"'"
		#         else :
		#             ff0001 =  "prov_code  = '"+str(code)+"'"
		#         countsBase = targetBase.exclude(agg_simplified_description='Water body and Marshland').extra(
		#             select={
		#                 'numbersettlements': 'count(distinct vuid)'}, 
		#             where = {ff0001}).values('numbersettlements')
		#     elif flag=='currentBasin':
		#         countsBase = targetBase.exclude(agg_simplified_description='Water body and Marshland').extra(
		#             select={
		#                 'numbersettlements': 'count(distinct vuid)'}, 
		#             where = {"vuid = '"+str(code)+"'"}).values('numbersettlements')   
		#     else:
		#         countsBase = targetBase.exclude(agg_simplified_description='Water body and Marshland').extra(
		#             select={
		#                 'numbersettlements': 'count(distinct vuid)'}, 
		#             where = {'ST_Within(wkb_geometry, '+filterLock+')'}).values('numbersettlements')
			
		#     response['settlements'] = round(countsBase[0]['numbersettlements'],0)

		#     # All population number
		#     if flag=='drawArea':
		#         countsBase = targetBase.extra(
		#             select={
		#                 'countbase' : 'SUM(  \
		#                         case \
		#                             when ST_CoveredBy(wkb_geometry,'+filterLock+') then area_population \
		#                             else st_area(st_intersection(wkb_geometry,'+filterLock+')) / st_area(wkb_geometry)*area_population end \
		#                     )'
		#             },
		#             where = {
		#                 'ST_Intersects(wkb_geometry, '+filterLock+')'
		#             }).values('countbase')
		#     elif flag=='entireAfg':
		#         countsBase = targetBase.extra(
		#             select={
		#                 'countbase' : 'SUM(area_population)'
		#             }).values('countbase')
		#     elif flag=='currentProvince':
		#         if len(str(code)) > 2:
		#             ff0001 =  "dist_code  = '"+str(code)+"'"
		#         else :
		#             ff0001 =  "prov_code  = '"+str(code)+"'"
		#         countsBase = targetBase.extra(
		#             select={
		#                 'countbase' : 'SUM(area_population)'
		#             },
		#             where = {
		#                 ff0001
		#             }).values('countbase')
		#     elif flag=='currentBasin':
		#         countsBase = targetBase.extra(
		#             select={
		#                 'countbase' : 'SUM(area_population)'
		#             }, 
		#             where = {"vuid = '"+str(code)+"'"}).values('countbase')     
		#     else:
		#         countsBase = targetBase.extra(
		#             select={
		#                 'countbase' : 'SUM(area_population)'
		#             },
		#             where = {
		#                 'ST_Within(wkb_geometry, '+filterLock+')'
		#             }).values('countbase')
						
		#     response['Population']=round(none_to_zero(countsBase)[0]['countbase'],0)

		#     if flag=='drawArea':
		#         countsBase = targetBase.extra(
		#             select={
		#                 'areabase' : 'SUM(  \
		#                         case \
		#                             when ST_CoveredBy(wkb_geometry,'+filterLock+') then area_sqm \
		#                             else st_area(st_intersection(wkb_geometry,'+filterLock+')) / st_area(wkb_geometry)*area_sqm end \
		#                     )'
		#             },
		#             where = {
		#                 'ST_Intersects(wkb_geometry, '+filterLock+')'
		#             }).values('areabase')
		#     elif flag=='entireAfg':
		#         countsBase = targetBase.extra(
		#             select={
		#                 'areabase' : 'SUM(area_sqm)'
		#             }).values('areabase')
		#     elif flag=='currentProvince':
		#         if len(str(code)) > 2:
		#             ff0001 =  "dist_code  = '"+str(code)+"'"
		#         else :
		#             ff0001 =  "prov_code  = '"+str(code)+"'"
		#         countsBase = targetBase.extra(
		#             select={
		#                 'areabase' : 'SUM(area_sqm)'
		#             },
		#             where = {
		#                 ff0001
		#             }).values('areabase')
		#     elif flag=='currentBasin':
		#         countsBase = targetBase.extra(
		#             select={
		#                 'areabase' : 'SUM(area_sqm)'
		#             },
		#             where = {"vuid = '"+str(code)+"'"}).values('areabase')      

		#     else:
		#         countsBase = targetBase.extra(
		#             select={
		#                 'areabase' : 'SUM(area_sqm)'
		#             },
		#             where = {
		#                 'ST_Within(wkb_geometry, '+filterLock+')'
		#             }).values('areabase')

		#     response['Area']=round(none_to_zero(countsBase)[0]['areabase']/1000000,0)

		# else:
		#     if flag=='entireAfg':
		#         px = provincesummary.objects.aggregate(Sum('high_ava_population'),Sum('med_ava_population'),Sum('low_ava_population'),Sum('total_ava_population'),Sum('high_ava_area'),Sum('med_ava_area'),Sum('low_ava_area'),Sum('total_ava_area'), \
		#             Sum('high_risk_population'),Sum('med_risk_population'),Sum('low_risk_population'),Sum('total_risk_population'), Sum('high_risk_area'),Sum('med_risk_area'),Sum('low_risk_area'),Sum('total_risk_area'),  \
		#             Sum('water_body_pop_risk'),Sum('barren_land_pop_risk'),Sum('built_up_pop_risk'),Sum('fruit_trees_pop_risk'),Sum('irrigated_agricultural_land_pop_risk'),Sum('permanent_snow_pop_risk'),Sum('rainfed_agricultural_land_pop_risk'),Sum('rangeland_pop_risk'),Sum('sandcover_pop_risk'),Sum('vineyards_pop_risk'),Sum('forest_pop_risk'), Sum('sand_dunes_pop_risk'), \
		#             Sum('water_body_area_risk'),Sum('barren_land_area_risk'),Sum('built_up_area_risk'),Sum('fruit_trees_area_risk'),Sum('irrigated_agricultural_land_area_risk'),Sum('permanent_snow_area_risk'),Sum('rainfed_agricultural_land_area_risk'),Sum('rangeland_area_risk'),Sum('sandcover_area_risk'),Sum('vineyards_area_risk'),Sum('forest_area_risk'), Sum('sand_dunes_area_risk'), \
		#             Sum('water_body_pop'),Sum('barren_land_pop'),Sum('built_up_pop'),Sum('fruit_trees_pop'),Sum('irrigated_agricultural_land_pop'),Sum('permanent_snow_pop'),Sum('rainfed_agricultural_land_pop'),Sum('rangeland_pop'),Sum('sandcover_pop'),Sum('vineyards_pop'),Sum('forest_pop'), Sum('sand_dunes_pop'), \
		#             Sum('water_body_area'),Sum('barren_land_area'),Sum('built_up_area'),Sum('fruit_trees_area'),Sum('irrigated_agricultural_land_area'),Sum('permanent_snow_area'),Sum('rainfed_agricultural_land_area'),Sum('rangeland_area'),Sum('sandcover_area'),Sum('vineyards_area'),Sum('forest_area'), Sum('sand_dunes_area'), \
		#             Sum('settlements_at_risk'), Sum('settlements'), Sum('Population'), Sum('Area'), Sum('ava_forecast_low_pop'), Sum('ava_forecast_med_pop'), Sum('ava_forecast_high_pop'), Sum('total_ava_forecast_pop'),
		#             Sum('total_buildings'), Sum('total_risk_buildings'), Sum('high_ava_buildings'), Sum('med_ava_buildings'), Sum('total_ava_buildings') )
		#     else:    
		#         if len(str(code)) > 2:
		#             px = districtsummary.objects.filter(district=code).aggregate(Sum('high_ava_population'),Sum('med_ava_population'),Sum('low_ava_population'),Sum('total_ava_population'),Sum('high_ava_area'),Sum('med_ava_area'),Sum('low_ava_area'),Sum('total_ava_area'), \
		#                 Sum('high_risk_population'),Sum('med_risk_population'),Sum('low_risk_population'),Sum('total_risk_population'), Sum('high_risk_area'),Sum('med_risk_area'),Sum('low_risk_area'),Sum('total_risk_area'),  \
		#                 Sum('water_body_pop_risk'),Sum('barren_land_pop_risk'),Sum('built_up_pop_risk'),Sum('fruit_trees_pop_risk'),Sum('irrigated_agricultural_land_pop_risk'),Sum('permanent_snow_pop_risk'),Sum('rainfed_agricultural_land_pop_risk'),Sum('rangeland_pop_risk'),Sum('sandcover_pop_risk'),Sum('vineyards_pop_risk'),Sum('forest_pop_risk'), Sum('sand_dunes_pop_risk'), \
		#                 Sum('water_body_area_risk'),Sum('barren_land_area_risk'),Sum('built_up_area_risk'),Sum('fruit_trees_area_risk'),Sum('irrigated_agricultural_land_area_risk'),Sum('permanent_snow_area_risk'),Sum('rainfed_agricultural_land_area_risk'),Sum('rangeland_area_risk'),Sum('sandcover_area_risk'),Sum('vineyards_area_risk'),Sum('forest_area_risk'), Sum('sand_dunes_area_risk'), \
		#                 Sum('water_body_pop'),Sum('barren_land_pop'),Sum('built_up_pop'),Sum('fruit_trees_pop'),Sum('irrigated_agricultural_land_pop'),Sum('permanent_snow_pop'),Sum('rainfed_agricultural_land_pop'),Sum('rangeland_pop'),Sum('sandcover_pop'),Sum('vineyards_pop'),Sum('forest_pop'), Sum('sand_dunes_pop'), \
		#                 Sum('water_body_area'),Sum('barren_land_area'),Sum('built_up_area'),Sum('fruit_trees_area'),Sum('irrigated_agricultural_land_area'),Sum('permanent_snow_area'),Sum('rainfed_agricultural_land_area'),Sum('rangeland_area'),Sum('sandcover_area'),Sum('vineyards_area'),Sum('forest_area'), Sum('sand_dunes_area'), \
		#                 Sum('settlements_at_risk'), Sum('settlements'), Sum('Population'), Sum('Area'), Sum('ava_forecast_low_pop'), Sum('ava_forecast_med_pop'), Sum('ava_forecast_high_pop'), Sum('total_ava_forecast_pop'),
		#                 Sum('total_buildings'), Sum('total_risk_buildings'), Sum('high_ava_buildings'), Sum('med_ava_buildings'), Sum('total_ava_buildings') )
		#         else :
		#             px = provincesummary.objects.filter(province=code).aggregate(Sum('high_ava_population'),Sum('med_ava_population'),Sum('low_ava_population'),Sum('total_ava_population'),Sum('high_ava_area'),Sum('med_ava_area'),Sum('low_ava_area'),Sum('total_ava_area'), \
		#                 Sum('high_risk_population'),Sum('med_risk_population'),Sum('low_risk_population'),Sum('total_risk_population'), Sum('high_risk_area'),Sum('med_risk_area'),Sum('low_risk_area'),Sum('total_risk_area'),  \
		#                 Sum('water_body_pop_risk'),Sum('barren_land_pop_risk'),Sum('built_up_pop_risk'),Sum('fruit_trees_pop_risk'),Sum('irrigated_agricultural_land_pop_risk'),Sum('permanent_snow_pop_risk'),Sum('rainfed_agricultural_land_pop_risk'),Sum('rangeland_pop_risk'),Sum('sandcover_pop_risk'),Sum('vineyards_pop_risk'),Sum('forest_pop_risk'), Sum('sand_dunes_pop_risk'), \
		#                 Sum('water_body_area_risk'),Sum('barren_land_area_risk'),Sum('built_up_area_risk'),Sum('fruit_trees_area_risk'),Sum('irrigated_agricultural_land_area_risk'),Sum('permanent_snow_area_risk'),Sum('rainfed_agricultural_land_area_risk'),Sum('rangeland_area_risk'),Sum('sandcover_area_risk'),Sum('vineyards_area_risk'),Sum('forest_area_risk'), Sum('sand_dunes_area_risk'), \
		#                 Sum('water_body_pop'),Sum('barren_land_pop'),Sum('built_up_pop'),Sum('fruit_trees_pop'),Sum('irrigated_agricultural_land_pop'),Sum('permanent_snow_pop'),Sum('rainfed_agricultural_land_pop'),Sum('rangeland_pop'),Sum('sandcover_pop'),Sum('vineyards_pop'),Sum('forest_pop'), Sum('sand_dunes_pop'), \
		#                 Sum('water_body_area'),Sum('barren_land_area'),Sum('built_up_area'),Sum('fruit_trees_area'),Sum('irrigated_agricultural_land_area'),Sum('permanent_snow_area'),Sum('rainfed_agricultural_land_area'),Sum('rangeland_area'),Sum('sandcover_area'),Sum('vineyards_area'),Sum('forest_area'), Sum('sand_dunes_area'), \
		#                 Sum('settlements_at_risk'), Sum('settlements'), Sum('Population'), Sum('Area'), Sum('ava_forecast_low_pop'), Sum('ava_forecast_med_pop'), Sum('ava_forecast_high_pop'), Sum('total_ava_forecast_pop'),
		#                 Sum('total_buildings'), Sum('total_risk_buildings'), Sum('high_ava_buildings'), Sum('med_ava_buildings'), Sum('total_ava_buildings') )
			
		#     for p in px:
		#         response[p[:-5]] = px[p]


		# Avalanche Forecasted
		sql = ""
		if flag=='entireAfg':
			# cursor = connections['geodb'].cursor()
			sql = "select forcastedvalue.riskstate, \
				sum(afg_avsa.avalanche_pop) as pop, \
				sum(afg_avsa.area_buildings) as building \
				FROM afg_avsa \
				INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
				INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
				INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
				WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
				AND forcastedvalue.datadate = '%s-%s-%s' \
				AND forcastedvalue.forecasttype = 'snowwater' ) \
				GROUP BY forcastedvalue.riskstate" %(YEAR,MONTH,DAY)
			# cursor.execute("select forcastedvalue.riskstate, \
			#     sum(afg_avsa.avalanche_pop) as pop, \
			#     sum(afg_avsa.area_buildings) as building \
			#     FROM afg_avsa \
			#     INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
			#     INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
			#     INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
			#     WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
			#     AND forcastedvalue.datadate = '%s-%s-%s' \
			#     AND forcastedvalue.forecasttype = 'snowwater' ) \
			#     GROUP BY forcastedvalue.riskstate" %(YEAR,MONTH,DAY))  
			# row = cursor.fetchall()
			# cursor.close()
		elif flag=='currentProvince':
			# cursor = connections['geodb'].cursor()
			if len(str(code)) > 2:
				ff0001 =  "dist_code  = '"+str(code)+"'"
			else :
				ff0001 =  "prov_code  = '"+str(code)+"'"

			sql = "select forcastedvalue.riskstate, \
				sum(afg_avsa.avalanche_pop) as pop, \
				sum(afg_avsa.area_buildings) as building \
				FROM afg_avsa \
				INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
				INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
				INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
				WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
				AND forcastedvalue.datadate = '%s-%s-%s' \
				AND forcastedvalue.forecasttype = 'snowwater' ) \
				and afg_avsa.%s \
				GROUP BY forcastedvalue.riskstate" %(YEAR,MONTH,DAY,ff0001)
			# cursor.execute("select forcastedvalue.riskstate, \
			#     sum(afg_avsa.avalanche_pop) as pop, \
			#     sum(afg_avsa.area_buildings) as building \
			#     FROM afg_avsa \
			#     INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
			#     INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
			#     INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
			#     WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
			#     AND forcastedvalue.datadate = '%s-%s-%s' \
			#     AND forcastedvalue.forecasttype = 'snowwater' ) \
			#     and afg_avsa.%s \
			#     GROUP BY forcastedvalue.riskstate" %(YEAR,MONTH,DAY,ff0001)) 
			# row = cursor.fetchall()
			# cursor.close()
		elif flag=='drawArea':
			# cursor = connections['geodb'].cursor()
			sql = "select forcastedvalue.riskstate, \
				sum(case \
					when ST_CoveredBy(afg_avsa.wkb_geometry , %s) then afg_avsa.avalanche_pop \
					else st_area(st_intersection(afg_avsa.wkb_geometry, %s)) / st_area(afg_avsa.wkb_geometry)* avalanche_pop end \
				) as pop, \
				sum(case \
					when ST_CoveredBy(afg_avsa.wkb_geometry , %s) then afg_avsa.area_buildings \
					else st_area(st_intersection(afg_avsa.wkb_geometry, %s)) / st_area(afg_avsa.wkb_geometry)* area_buildings end \
				) as building \
				FROM afg_avsa \
				INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
				INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
				INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
				WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
				AND forcastedvalue.datadate = '%s-%s-%s' \
				AND forcastedvalue.forecasttype = 'snowwater' ) \
				GROUP BY forcastedvalue.riskstate" %(filterLock,filterLock, filterLock,filterLock,YEAR,MONTH,DAY)
			# cursor.execute("select forcastedvalue.riskstate, \
			#     sum(case \
			#         when ST_CoveredBy(afg_avsa.wkb_geometry , %s) then afg_avsa.avalanche_pop \
			#         else st_area(st_intersection(afg_avsa.wkb_geometry, %s)) / st_area(afg_avsa.wkb_geometry)* avalanche_pop end \
			#     ) as pop, \
			#     sum(case \
			#         when ST_CoveredBy(afg_avsa.wkb_geometry , %s) then afg_avsa.area_buildings \
			#         else st_area(st_intersection(afg_avsa.wkb_geometry, %s)) / st_area(afg_avsa.wkb_geometry)* area_buildings end \
			#     ) as building \
			#     FROM afg_avsa \
			#     INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
			#     INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
			#     INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
			#     WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
			#     AND forcastedvalue.datadate = '%s-%s-%s' \
			#     AND forcastedvalue.forecasttype = 'snowwater' ) \
			#     GROUP BY forcastedvalue.riskstate" %(filterLock,filterLock,YEAR,MONTH,DAY)) 
			# row = cursor.fetchall()
			# cursor.close()
		else:
			# cursor = connections['geodb'].cursor()
			sql = "select forcastedvalue.riskstate, \
				sum(afg_avsa.avalanche_pop) as pop, \
				sum(afg_avsa.area_buildings) as building \
				FROM afg_avsa \
				INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
				INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
				INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
				WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
				AND forcastedvalue.datadate = '%s-%s-%s' \
				AND forcastedvalue.forecasttype = 'snowwater' ) \
				AND ST_Within(afg_avsa.wkb_geometry, %s) \
				GROUP BY forcastedvalue.riskstate" %(YEAR,MONTH,DAY,filterLock)
			# cursor.execute("select forcastedvalue.riskstate, \
			#     sum(afg_avsa.avalanche_pop) as pop, \
			#     sum(afg_avsa.area_buildings) as building \
			#     FROM afg_avsa \
			#     INNER JOIN current_sc_basins ON (ST_WITHIN(ST_Centroid(afg_avsa.wkb_geometry), current_sc_basins.wkb_geometry)) \
			#     INNER JOIN afg_sheda_lvl4 ON ( afg_avsa.basinmember_id = afg_sheda_lvl4.ogc_fid ) \
			#     INNER JOIN forcastedvalue ON ( afg_sheda_lvl4.ogc_fid = forcastedvalue.basin_id ) \
			#     WHERE (NOT (afg_avsa.basinmember_id IN (SELECT U1.ogc_fid FROM afg_sheda_lvl4 U1 LEFT OUTER JOIN forcastedvalue U2 ON ( U1.ogc_fid = U2.basin_id ) WHERE U2.riskstate IS NULL)) \
			#     AND forcastedvalue.datadate = '%s-%s-%s' \
			#     AND forcastedvalue.forecasttype = 'snowwater' ) \
			#     AND ST_Within(afg_avsa.wkb_geometry, %s) \
			#     GROUP BY forcastedvalue.riskstate" %(YEAR,MONTH,DAY,filterLock))  
			# row = cursor.fetchall()
			# cursor.close()    
		cursor = connections['geodb'].cursor()
		row = query_to_dicts(cursor, sql)
		counts = []
		for i in row:
			counts.append(i)
		cursor.close()

		temp = dict([(c['riskstate'], c['pop']) for c in counts])
		response_tree.path('avalancheforecast')['pop_likelihood'] = {v:round(temp.get(k) or 0) for k,v in AVA_LIKELIHOOD_INDEX.items()}
		response_tree.path('avalancheforecast')['pop_likelihood_total'] = sum(response_tree.path('avalancheforecast')['pop_likelihood'].values())
		# response['ava_forecast_low_pop']=round(dict(row).get(1, 0) or 0,0) 
		# response['ava_forecast_med_pop']=round(dict(row).get(2, 0) or 0,0) 
		# response['ava_forecast_high_pop']=round(dict(row).get(3, 0) or 0,0) 
		# response = response_tree['avalancheforecast']['population']['table']
		# response['ava_forecast_low_pop']=round(temp.get(1, 0) or 0,0) 
		# response['ava_forecast_med_pop']=round(temp.get(2, 0) or 0,0) 
		# response['ava_forecast_high_pop']=round(temp.get(3, 0) or 0,0) 
		# response['total_ava_forecast_pop']=response['ava_forecast_low_pop'] + response['ava_forecast_med_pop'] + response['ava_forecast_high_pop']

		# avalanche forecast buildings
		temp = dict([(c['riskstate'], c['building']) for c in counts])
		response_tree.path('avalancheforecast')['building_likelihood'] = {v:round(temp.get(i) or 0,0) for i,v in AVA_LIKELIHOOD_INDEX.items()}
		response_tree.path('avalancheforecast')['building_likelihood_total'] = sum(response_tree.path('avalancheforecast')['building_likelihood'].values())
		# response['ava_forecast_low_buildings']=round(dict(row).get(1, 0) or 0,0) 
		# response['ava_forecast_med_buildings']=round(dict(row).get(2, 0) or 0,0) 
		# response['ava_forecast_high_buildings']=round(dict(row).get(3, 0) or 0,0)
		# response = response_tree['avalancheforecast']['buildings']['table']
		# response['ava_forecast_low_buildings']=round(temp.get(1, 0) or 0,0) 
		# response['ava_forecast_med_buildings']=round(temp.get(2, 0) or 0,0) 
		# response['ava_forecast_high_buildings']=round(temp.get(3, 0) or 0,0) 
		# response['total_ava_forecast_buildings']=response['ava_forecast_low_buildings'] + response['ava_forecast_med_buildings'] + response['ava_forecast_high_buildings']


		# counts =  getRiskNumber(targetRisk.exclude(mitigated_pop=0), filterLock, 'deeperthan', 'mitigated_pop', 'fldarea_sqm', 'area_buildings', flag, code, None)
		# temp = dict([(c['deeperthan'], c['count']) for c in counts])
		# response['high_risk_mitigated_population']=round(temp.get('271 cm', 0) or 0,0)
		# response['med_risk_mitigated_population']=round(temp.get('121 cm', 0) or 0, 0)
		# response['low_risk_mitigated_population']=round(temp.get('029 cm', 0) or 0,0)
		# response['total_risk_mitigated_population']=response['high_risk_mitigated_population']+response['med_risk_mitigated_population']+response['low_risk_mitigated_population']


		# # River Flood Forecasted
		# if rf_type == 'GFMS only':
		#     bring = filterLock    
		# temp_result = getFloodForecastBySource(rf_type, targetRisk, bring, flag, code, YEAR, MONTH, DAY)
		# for item in temp_result:
		#     response[item]=temp_result[item]


		# # Flash Flood Forecasted
		# # AfgFldzonea100KRiskLandcoverPop.objects.all().select_related("basinmembers").values_list("agg_simplified_description","basinmember__basins__riskstate")
		# counts =  getRiskNumber(targetRisk.exclude(mitigated_pop__gt=0).select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='flashflood',basinmember__basins__datadate='%s-%s-%s' %(YEAR,MONTH,DAY)), filterLock, 'basinmember__basins__riskstate', 'fldarea_population', 'fldarea_sqm', 'area_buildings', flag, code, 'afg_fldzonea_100k_risk_landcover_pop')
		
		# temp = dict([(c['basinmember__basins__riskstate'], c['count']) for c in counts])
		# response['flashflood_forecast_verylow_pop']=round(temp.get(1, 0) or 0,0) 
		# response['flashflood_forecast_low_pop']=round(temp.get(2, 0) or 0,0) 
		# response['flashflood_forecast_med_pop']=round(temp.get(3, 0) or 0,0) 
		# response['flashflood_forecast_high_pop']=round(temp.get(4, 0) or 0,0) 
		# response['flashflood_forecast_veryhigh_pop']=round(temp.get(5, 0) or 0,0) 
		# response['flashflood_forecast_extreme_pop']=round(temp.get(6, 0) or 0,0) 
		# response['total_flashflood_forecast_pop']=response['flashflood_forecast_verylow_pop'] + response['flashflood_forecast_low_pop'] + response['flashflood_forecast_med_pop'] + response['flashflood_forecast_high_pop'] + response['flashflood_forecast_veryhigh_pop'] + response['flashflood_forecast_extreme_pop']

		# temp = dict([(c['basinmember__basins__riskstate'], c['areaatrisk']) for c in counts])
		# response['flashflood_forecast_verylow_area']=round((temp.get(1, 0) or 0)/1000000,0) 
		# response['flashflood_forecast_low_area']=round((temp.get(2, 0) or 0)/1000000,0) 
		# response['flashflood_forecast_med_area']=round((temp.get(3, 0) or 0)/1000000,0) 
		# response['flashflood_forecast_high_area']=round((temp.get(4, 0) or 0)/1000000,0) 
		# response['flashflood_forecast_veryhigh_area']=round((temp.get(5, 0) or 0)/1000000,0) 
		# response['flashflood_forecast_extreme_area']=round((temp.get(6, 0) or 0)/1000000,0) 
		# response['total_flashflood_forecast_area']=response['flashflood_forecast_verylow_area'] + response['flashflood_forecast_low_area'] + response['flashflood_forecast_med_area'] + response['flashflood_forecast_high_area'] + response['flashflood_forecast_veryhigh_area'] + response['flashflood_forecast_extreme_area']

		# # number of building on flahsflood forecasted
		# temp = dict([(c['basinmember__basins__riskstate'], c['houseatrisk']) for c in counts])
		# response['flashflood_forecast_verylow_buildings']=round(temp.get(1, 0) or 0,0) 
		# response['flashflood_forecast_low_buildings']=round(temp.get(2, 0) or 0,0) 
		# response['flashflood_forecast_med_buildings']=round(temp.get(3, 0) or 0,0) 
		# response['flashflood_forecast_high_buildings']=round(temp.get(4, 0) or 0,0) 
		# response['flashflood_forecast_veryhigh_buildings']=round(temp.get(5, 0) or 0,0) 
		# response['flashflood_forecast_extreme_buildings']=round(temp.get(6, 0) or 0,0) 
		# response['total_flashflood_forecast_buildings']=response['flashflood_forecast_verylow_buildings'] + response['flashflood_forecast_low_buildings'] + response['flashflood_forecast_med_buildings'] + response['flashflood_forecast_high_buildings'] + response['flashflood_forecast_veryhigh_buildings'] + response['flashflood_forecast_extreme_buildings']


		# response['total_flood_forecast_pop'] = response['total_riverflood_forecast_pop'] + response['total_flashflood_forecast_pop']
		# response['total_flood_forecast_area'] = response['total_riverflood_forecast_area'] + response['total_flashflood_forecast_area']

		response_tree = none_to_zero(response_tree)

		# # flood risk and flashflood forecast matrix
		# px = targetRisk.exclude(mitigated_pop__gt=0).select_related("basinmembers").defer('basinmember__wkb_geometry').exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='flashflood',basinmember__basins__datadate='%s-%s-%s' %(YEAR,MONTH,DAY))
		# # px = px.values('basinmember__basins__riskstate','deeperthan').annotate(counter=Count('ogc_fid')).extra(
		# #     select={
		# #         'pop' : 'SUM(fldarea_population)'
		# #     }).values('basinmember__basins__riskstate','deeperthan', 'pop') 
		# if flag=='entireAfg': 
		#     px = px.\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(pop=Sum('fldarea_population')).\
		#         annotate(building=Sum('area_buildings')).\
		#         values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
		# elif flag=='currentProvince':
		#     if len(str(code)) > 2:
		#         ff0001 =  "dist_code  = '"+str(code)+"'"
		#     else :
		#         if len(str(code))==1:
		#             ff0001 =  "left(cast(dist_code as text),1)  = '"+str(code)+"'"
		#         else:
		#             ff0001 =  "left(cast(dist_code as text),2)  = '"+str(code)+"'"   
		#     px = px.\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(pop=Sum('fldarea_population')).\
		#         annotate(building=Sum('area_buildings')).\
		#         extra(
		#             where={
		#                 ff0001
		#             }).\
		#         values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')
		# elif flag=='drawArea':
		#     px = px.\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(pop=RawSQL_nogroupby('SUM(  \
		#                         case \
		#                             when ST_CoveredBy(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry ,'+filterLock+') then fldarea_population \
		#                             else st_area(st_intersection(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry,'+filterLock+')) / st_area(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry)* fldarea_population end \
		#                     )')).\
		#         annotate(building=RawSQL_nogroupby('SUM(  \
		#                         case \
		#                             when ST_CoveredBy(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry ,'+filterLock+') then area_buildings \
		#                             else st_area(st_intersection(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry,'+filterLock+')) / st_area(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry)* area_buildings end \
		#                     )')).\
		#         extra(
		#             where = {
		#                 'ST_Intersects(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'
		#             }).\
		#         values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')  
		# else:
		#     px = px.\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(pop=Sum('fldarea_population')).\
		#         annotate(building=Sum('area_buildings')).\
		#         extra(
		#             where = {
		#                 'ST_Within(afg_fldzonea_100k_risk_landcover_pop.wkb_geometry, '+filterLock+')'
		#             }).\
		#         values('basinmember__basins__riskstate','deeperthan', 'pop', 'building')     

		# px = none_to_zero(px)

		# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 1 ]
		# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		# response['flashflood_forecast_verylow_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_verylow_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_verylow_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		# response['flashflood_forecast_verylow_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_verylow_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_verylow_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 2 ]
		# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		# response['flashflood_forecast_low_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_low_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0) 
		# response['flashflood_forecast_low_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		# response['flashflood_forecast_low_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_low_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0) 
		# response['flashflood_forecast_low_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 3 ]
		# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		# response['flashflood_forecast_med_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_med_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_med_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0) 
		# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		# response['flashflood_forecast_med_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_med_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_med_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 4 ]
		# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		# response['flashflood_forecast_high_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_high_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_high_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		# response['flashflood_forecast_high_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_high_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_high_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 5 ]
		# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		# response['flashflood_forecast_veryhigh_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_veryhigh_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_veryhigh_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		# response['flashflood_forecast_veryhigh_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_veryhigh_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_veryhigh_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)

		# tempD = [ num for num in px if num['basinmember__basins__riskstate'] == 6 ]
		# temp = dict([(c['deeperthan'], c['pop']) for c in tempD])
		# response['flashflood_forecast_extreme_risk_low_pop']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_extreme_risk_med_pop']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_extreme_risk_high_pop']=round(temp.get('271 cm', 0) or 0,0)
		# temp = dict([(c['deeperthan'], c['building']) for c in tempD])
		# response['flashflood_forecast_extreme_risk_low_buildings']=round(temp.get('029 cm', 0) or 0,0)
		# response['flashflood_forecast_extreme_risk_med_buildings']=round(temp.get('121 cm', 0) or 0, 0)
		# response['flashflood_forecast_extreme_risk_high_buildings']=round(temp.get('271 cm', 0) or 0,0)
		

		# try:
		#     response['percent_total_risk_population'] = round((response['total_risk_population']/response['Population'])*100,0)
		# except ZeroDivisionError:
		#     response['percent_total_risk_population'] = 0
			
		# try:
		#     response['percent_high_risk_population'] = round((response['high_risk_population']/response['Population'])*100,0)
		# except ZeroDivisionError:
		#     response['percent_high_risk_population'] = 0

		# try:
		#     response['percent_med_risk_population'] = round((response['med_risk_population']/response['Population'])*100,0)
		# except ZeroDivisionError:
		#     response['percent_med_risk_population'] = 0

		# try:
		#     response['percent_low_risk_population'] = round((response['low_risk_population']/response['Population'])*100,0)
		# except ZeroDivisionError:
		#     response['percent_low_risk_population'] = 0

		# try:
		#     response['percent_total_risk_area'] = round((response['total_risk_area']/response['Area'])*100,0)
		# except ZeroDivisionError:
		#     response['percent_total_risk_area'] = 0

		# try:
		#     response['percent_high_risk_area'] = round((response['high_risk_area']/response['Area'])*100,0)
		# except ZeroDivisionError:
		#     response['percent_high_risk_area'] = 0

		# try:
		#     response['percent_med_risk_area'] = round((response['med_risk_area']/response['Area'])*100,0)
		# except ZeroDivisionError:
		#     response['percent_med_risk_area'] = 0
		
		# try:
		#     response['percent_low_risk_area'] = round((response['low_risk_area']/response['Area'])*100,0)
		# except ZeroDivisionError:
		#     response['percent_low_risk_area'] = 0

		response_tree.path('avalancherisk')['pop_likelihood_percent'] = {k:round(div_by_zero_is_zero(v, response_tree['baseline']['pop_total'])*100, 0) for k,v in response_tree['avalancherisk']['pop_likelihood'].items()}
		response_tree.path('avalancherisk')['pop_likelihood_percent_total'] = sum(response_tree.path('avalancherisk')['pop_likelihood_percent'].values())

		# avalancherisk = response_tree['avalancherisk']['population']['table']
		# baseline = response_tree['baseline']['population']['table']

		# for level in ['total','high','med','low']:
		#     avalancherisk['percent_%s_ava_population'%(level)] = \
		#         round(div_by_zero_is_zero(avalancherisk['%s_ava_population'%(level)], baseline['Population'])*100, 0)

		# try:
		#     avalancherisk['percent_total_ava_population'] = round((avalancherisk['total_ava_population']/baseline['Population'])*100,0)
		# except ZeroDivisionError:
		#     avalancherisk['percent_total_ava_population'] = 0
		
		# try:
		#     avalancherisk['percent_high_ava_population'] = round((avalancherisk['high_ava_population']/baseline['Population'])*100,0)
		# except ZeroDivisionError:
		#     avalancherisk['percent_high_ava_population'] = 0    
		
		# try:
		#     avalancherisk['percent_med_ava_population'] = round((avalancherisk['med_ava_population']/baseline['Population'])*100,0)
		# except ZeroDivisionError:
		#     avalancherisk['percent_med_ava_population'] = 0

		# try:
		#     avalancherisk['percent_low_ava_population'] = round((avalancherisk['low_ava_population']/baseline['Population'])*100,0)
		# except ZeroDivisionError:
		#     avalancherisk['percent_low_ava_population'] = 0

		response_tree.path('avalancherisk')['area_likelihood_percent'] = {k:round(div_by_zero_is_zero(v, response_tree['baseline']['area_total'])*100, 0) for k,v in response_tree['avalancherisk']['area_likelihood'].items()}
		response_tree.path('avalancherisk')['area_likelihood_percent_total'] = sum(response_tree.path('avalancherisk')['area_likelihood_percent'].values())

		# avalancherisk = response_tree['avalancherisk']['area']['table']
		# baseline = response_tree['baseline']['area']['table']

		# for level in ['total','high','med','low']:
		#     avalancherisk['percent_%s_ava_area'%(level)] = \
		#         round(div_by_zero_is_zero(avalancherisk['%s_ava_area'%(level)], baseline['Area'])*100, 0)

		# try:
		#     avalancherisk['percent_total_ava_area'] = round((avalancherisk['total_ava_area']/baseline['Area'])*100,0)
		# except ZeroDivisionError:
		#     avalancherisk['percent_total_ava_area'] = 0

		# try:
		#     avalancherisk['percent_high_ava_area'] = round((avalancherisk['high_ava_area']/baseline['Area'])*100,0)
		# except ZeroDivisionError:
		#     avalancherisk['percent_high_ava_area'] = 0

		# try:
		#     avalancherisk['percent_med_ava_area'] = round((avalancherisk['med_ava_area']/baseline['Area'])*100,0)
		# except ZeroDivisionError:
		#     avalancherisk['percent_med_ava_area'] = 0
		# try:
		#     avalancherisk['percent_low_ava_area'] = round((avalancherisk['low_ava_area']/baseline['Area'])*100,0)
		# except ZeroDivisionError:
		#     avalancherisk['percent_low_ava_area'] = 0    

		# # Population percentage
		# try:
		#     response['precent_barren_land_pop_risk'] = round((response['barren_land_pop_risk']/response['barren_land_pop'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_barren_land_pop_risk'] = 0
		# try:
		#     response['precent_built_up_pop_risk'] = round((response['built_up_pop_risk']/response['built_up_pop'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_built_up_pop_risk'] = 0       
		# try:
		#     response['precent_fruit_trees_pop_risk'] = round((response['fruit_trees_pop_risk']/response['fruit_trees_pop'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_fruit_trees_pop_risk'] = 0
		# try:
		#     response['precent_irrigated_agricultural_land_pop_risk'] = round((response['irrigated_agricultural_land_pop_risk']/response['irrigated_agricultural_land_pop'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_irrigated_agricultural_land_pop_risk'] = 0     
		# try:
		#     response['precent_permanent_snow_pop_risk'] = round((response['permanent_snow_pop_risk']/response['permanent_snow_pop'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_permanent_snow_pop_risk'] = 0 
		# try:
		#     response['precent_rainfed_agricultural_land_pop_risk'] = round((response['rainfed_agricultural_land_pop_risk']/response['rainfed_agricultural_land_pop'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_rainfed_agricultural_land_pop_risk'] = 0  
		# try:
		#     response['precent_rangeland_pop_risk'] = round((response['rangeland_pop_risk']/response['rangeland_pop'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_rangeland_pop_risk'] = 0  
		# try:
		#     response['precent_sandcover_pop_risk'] = round((response['sandcover_pop_risk']/response['sandcover_pop'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_sandcover_pop_risk'] = 0  
		# try:
		#     response['precent_vineyards_pop_risk'] = round((response['vineyards_pop_risk']/response['vineyards_pop'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_vineyards_pop_risk'] = 0  
		# try:
		#     response['precent_water_body_pop_risk'] = round((response['water_body_pop_risk']/response['water_body_pop'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_water_body_pop_risk'] = 0     
		# try:
		#     response['precent_forest_pop_risk'] = round((response['forest_pop_risk']/response['forest_pop'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_forest_pop_risk'] = 0    
		# try:
		#     response['precent_sand_dunes_pop_risk'] = round((response['sand_dunes_pop_risk']/response['sand_dunes_pop'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_sand_dunes_pop_risk'] = 0                          


		# # Area percentage
		# try:
		#     response['precent_barren_land_area_risk'] = round((response['barren_land_area_risk']/response['barren_land_area'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_barren_land_area_risk'] = 0
		# try:        
		#     response['precent_built_up_area_risk'] = round((response['built_up_area_risk']/response['built_up_area'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_built_up_area_risk'] = 0    
		# try:
		#     response['precent_fruit_trees_area_risk'] = round((response['fruit_trees_area_risk']/response['fruit_trees_area'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_fruit_trees_area_risk'] = 0        
		# try:
		#     response['precent_irrigated_agricultural_land_area_risk'] = round((response['irrigated_agricultural_land_area_risk']/response['irrigated_agricultural_land_area'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_irrigated_agricultural_land_area_risk'] = 0 
		# try:
		#     response['precent_permanent_snow_area_risk'] = round((response['permanent_snow_area_risk']/response['permanent_snow_area'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_permanent_snow_area_risk'] = 0 
		# try:
		#     response['precent_rainfed_agricultural_land_area_risk'] = round((response['rainfed_agricultural_land_area_risk']/response['rainfed_agricultural_land_area'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_rainfed_agricultural_land_area_risk'] = 0  
		# try:
		#     response['precent_rangeland_area_risk'] = round((response['rangeland_area_risk']/response['rangeland_area'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_rangeland_area_risk'] = 0  
		# try:
		#     response['precent_sandcover_area_risk'] = round((response['sandcover_area_risk']/response['sandcover_area'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_sandcover_area_risk'] = 0  
		# try:
		#     response['precent_vineyards_area_risk'] = round((response['vineyards_area_risk']/response['vineyards_area'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_vineyards_area_risk'] = 0  
		# try:
		#     response['precent_water_body_area_risk'] = round((response['water_body_area_risk']/response['water_body_area'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_water_body_area_risk'] = 0     
		# try:
		#     response['precent_forest_area_risk'] = round((response['forest_area_risk']/response['forest_area'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_forest_area_risk'] = 0 
		# try:
		#     response['precent_sand_dunes_area_risk'] = round((response['sand_dunes_area_risk']/response['sand_dunes_area'])*100,0)
		# except ZeroDivisionError:
		#     response['precent_sand_dunes_area_risk'] = 0 

		# # Roads 
		# if flag=='drawArea':
		#     countsRoadBase = AfgRdsl.objects.all().\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(road_length=RawSQL_nogroupby('SUM(  \
		#                     case \
		#                         when ST_CoveredBy(wkb_geometry'+','+filterLock+') then road_length \
		#                         else ST_Length(st_intersection(wkb_geometry::geography'+','+filterLock+')) / road_length end \
		#                 )/1000')).\
		#         extra(
		#         where = {
		#             'ST_Intersects(wkb_geometry'+', '+filterLock+')'
		#         }).\
		#         values('type_update','road_length') 

		#     countsHLTBase = AfgHltfac.objects.all().filter(activestatus='Y').\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(numberhospital=Count('ogc_fid')).\
		#         extra(
		#             where = {
		#                 'ST_Intersects(wkb_geometry'+', '+filterLock+')'
		#             }).\
		#         values('facility_types_description', 'numberhospital')

		# elif flag=='entireAfg':    
		#     # countsRoadBase = AfgRdsl.objects.all().values('type_update').annotate(counter=Count('ogc_fid')).extra(
		#     #         select={
		#     #             'road_length' : 'SUM(road_length)/1000'
		#     #         }).values('type_update', 'road_length')
		#     countsRoadBase = AfgRdsl.objects.all().\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(road_length__sum=Sum('road_length')/1000).\
		#         values('type_update', 'road_length__sum')

		#     # Health Facilities
		#     # countsHLTBase = AfgHltfac.objects.all().filter(activestatus='Y').values('facility_types_description').annotate(counter=Count('ogc_fid')).extra(
		#     #         select={
		#     #             'numberhospital' : 'count(*)'
		#     #         }).values('facility_types_description', 'numberhospital')
		#     countsHLTBase = AfgHltfac.objects.all().filter(activestatus='Y').\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(numberhospital=Count('ogc_fid')).\
		#         values('facility_types_description', 'numberhospital')
			
		# elif flag=='currentProvince':
		#     if len(str(code)) > 2:
		#         ff0001 =  "dist_code  = '"+str(code)+"'"
		#     else :
		#         if len(str(code))==1:
		#             ff0001 =  "left(cast(dist_code as text),1)  = '"+str(code)+"'"
		#         else:
		#             ff0001 =  "left(cast(dist_code as text),2)  = '"+str(code)+"'"    
					
		#     countsRoadBase = AfgRdsl.objects.all().\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(road_length__sum=Sum('road_length')/1000).\
		#         extra(
		#             where = {
		#                 ff0001
		#             }).\
		#         values('type_update','road_length__sum') 

		#     countsHLTBase = AfgHltfac.objects.all().filter(activestatus='Y').\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(numberhospital=Count('ogc_fid')).\
		#         extra(
		#             where = {
		#                 ff0001
		#             }).\
		#         values('facility_types_description', 'numberhospital')

		# elif flag=='currentBasin':
		#     print 'currentBasin'
		# else:
		#     countsRoadBase = AfgRdsl.objects.all().\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(road_length__sum=Sum('road_length')/1000).\
		#         extra(
		#             where = {
		#                 'ST_Within(wkb_geometry'+', '+filterLock+')'
		#             }).\
		#         values('type_update','road_length__sum') 

		#     countsHLTBase = AfgHltfac.objects.all().filter(activestatus='Y').\
		#         annotate(counter=Count('ogc_fid')).\
		#         annotate(numberhospital=Count('ogc_fid')).\
		#         extra(
		#             where = {
		#                 'ST_Within(wkb_geometry'+', '+filterLock+')'
		#             }).\
		#         values('facility_types_description', 'numberhospital')


		# tempRoadBase = dict([(c['type_update'], c['road_length__sum']) for c in countsRoadBase])
		# tempHLTBase = dict([(c['facility_types_description'], c['numberhospital']) for c in countsHLTBase])

		# response["highway_road_base"]=round(tempRoadBase.get("highway", 0),1)
		# response["primary_road_base"]=round(tempRoadBase.get("primary", 0),1)
		# response["secondary_road_base"]=round(tempRoadBase.get("secondary", 0),1)
		# response["tertiary_road_base"]=round(tempRoadBase.get("tertiary", 0),1)
		# response["residential_road_base"]=round(tempRoadBase.get("residential", 0),1)
		# response["track_road_base"]=round(tempRoadBase.get("track", 0),1)
		# response["path_road_base"]=round(tempRoadBase.get("path", 0),1)
		# response["river_crossing_road_base"]=round(tempRoadBase.get("river crossing", 0),1)
		# response["bridge_road_base"]=round(tempRoadBase.get("bridge", 0),1)
		# response["total_road_base"]=response["highway_road_base"]+response["primary_road_base"]+response["secondary_road_base"]+response["tertiary_road_base"]+response["residential_road_base"]+response["track_road_base"]+response["path_road_base"]+response["river_crossing_road_base"]+response["bridge_road_base"]

		# response["h1_health_base"]=round(tempHLTBase.get("Regional / National Hospital (H1)", 0))
		# response["h2_health_base"]=round(tempHLTBase.get("Provincial Hospital (H2)", 0))    
		# response["h3_health_base"]=round(tempHLTBase.get("District Hospital (H3)", 0))
		# response["sh_health_base"]=round(tempHLTBase.get("Special Hospital (SH)", 0))
		# response["rh_health_base"]=round(tempHLTBase.get("Rehabilitation Center (RH)", 0))               
		# response["mh_health_base"]=round(tempHLTBase.get("Maternity Home (MH)", 0))
		# response["datc_health_base"]=round(tempHLTBase.get("Drug Addicted Treatment Center", 0))
		# response["tbc_health_base"]=round(tempHLTBase.get("TB Control Center (TBC)", 0))
		# response["mntc_health_base"]=round(tempHLTBase.get("Mental Clinic / Hospital", 0))
		# response["chc_health_base"]=round(tempHLTBase.get("Comprehensive Health Center (CHC)", 0))
		# response["bhc_health_base"]=round(tempHLTBase.get("Basic Health Center (BHC)", 0))
		# response["dcf_health_base"]=round(tempHLTBase.get("Day Care Feeding", 0))
		# response["mch_health_base"]=round(tempHLTBase.get("MCH Clinic M1 or M2 (MCH)", 0))
		# response["shc_health_base"]=round(tempHLTBase.get("Sub Health Center (SHC)", 0))
		# response["ec_health_base"]=round(tempHLTBase.get("Eye Clinic / Hospital", 0))
		# response["pyc_health_base"]=round(tempHLTBase.get("Physiotherapy Center", 0))
		# response["pic_health_base"]=round(tempHLTBase.get("Private Clinic", 0))        
		# response["mc_health_base"]=round(tempHLTBase.get("Malaria Center (MC)", 0))
		# response["moph_health_base"]=round(tempHLTBase.get("MoPH National", 0))
		# response["epi_health_base"]=round(tempHLTBase.get("EPI Fixed Center (EPI)", 0))
		# response["sfc_health_base"]=round(tempHLTBase.get("Supplementary Feeding Center (SFC)", 0))
		# response["mht_health_base"]=round(tempHLTBase.get("Mobile Health Team (MHT)", 0))
		# response["other_health_base"]=round(tempHLTBase.get("Other", 0))
		# response["total_health_base"] = response["bhc_health_base"]+response["dcf_health_base"]+response["mch_health_base"]+response["rh_health_base"]+response["h3_health_base"]+response["sh_health_base"]+response["mh_health_base"]+response["datc_health_base"]+response["h1_health_base"]+response["shc_health_base"]+response["ec_health_base"]+response["pyc_health_base"]+response["pic_health_base"]+response["tbc_health_base"]+response["mntc_health_base"]+response["chc_health_base"]+response["other_health_base"]+response["h2_health_base"]+response["mc_health_base"]+response["moph_health_base"]+response["epi_health_base"]+response["sfc_health_base"]+response["mht_health_base"]
		
		# response = response_tree['avalancheforecast']['lastupdated']['table']

		try:
			sw = forecastedLastUpdate.objects.filter(forecasttype='snowwater').latest('datadate')
		except forecastedLastUpdate.DoesNotExist:
			response_tree.path('avalancheforecast','lastupdated')["snowwater"] = None
		else:
			response_tree.path('avalancheforecast','lastupdated')["snowwater"] = timeago.format(sw.datadate, datetime.datetime.utcnow())   #tempSW.strftime("%d-%m-%Y %H:%M")
			# tempSW = sw.datadate + datetime.timedelta(hours=4.5)
			# response_tree.path('avalancheforecast','lastupdated')["snowwater"] = timeago.format(tempSW, datetime.datetime.utcnow() + datetime.timedelta(hours=4.5))   #tempSW.strftime("%d-%m-%Y %H:%M")

		# try:
		#     rf = forecastedLastUpdate.objects.filter(forecasttype='riverflood').latest('datadate')
		# except forecastedLastUpdate.DoesNotExist:
		#     response["riverflood_lastupdated"] = None
		# else:
		#     tempRF = rf.datadate + datetime.timedelta(hours=4.5)
		#     response["riverflood_lastupdated"] = timeago.format(tempRF, datetime.datetime.utcnow()+ datetime.timedelta(hours=4.5))  #tempRF.strftime("%d-%m-%Y %H:%M")

		# try:
		#     sw = forecastedLastUpdate.objects.filter(forecasttype='snowwater').latest('datadate')
		# except forecastedLastUpdate.DoesNotExist:
		#     response["snowwater_lastupdated"] = None
		# else:
		#     tempSW = sw.datadate + datetime.timedelta(hours=4.5)
		#     response["snowwater_lastupdated"] =  timeago.format(tempSW, datetime.datetime.utcnow()+ datetime.timedelta(hours=4.5))   #tempSW.strftime("%d-%m-%Y %H:%M")

		# # print rf.datadate
		# tz = timezone('Asia/Kabul')
		# stdSC = datetime.datetime.utcnow()
		# stdSC = stdSC.replace(hour=3, minute=00, second=00)

		# tempSC = datetime.datetime.utcnow()

		# if stdSC > tempSC:
		#     tempSC = tempSC - datetime.timedelta(days=1)
		
		# tempSC = tempSC.replace(hour=3, minute=00, second=00)
		# tempSC = tempSC + datetime.timedelta(hours=4.5)
		# # tempSC = tempSC.replace(tzinfo=tz) 
		# print tempSC
		# response["glofas_lastupdated"] = timeago.format(tempSC, datetime.datetime.utcnow()+ datetime.timedelta(hours=4.5))     #tempSC.strftime("%d-%m-%Y %H:%M")
		
		# # add response from optional modules
		# for modulename in settings.GETRISKEXECUTEEXTERNAL_MODULES:
		#     module = importlib.import_module(modulename+'.views')
		#     response_add = module.getRiskExecuteExternal(filterLock, flag, code, yy, mm, dd, rf_type, bring, response_base=response)
		#     response.update(response_add)

		return response_tree

# from geodb.views

def getSnowCover():
	today  = datetime.datetime.now()
	year = today.strftime("%Y")

	base_url = 'sidads.colorado.edu'
	filelist=[]

	ftp = FTP(base_url)
	ftp.login()
	ftp.cwd("pub/DATASETS/NOAA/G02156/GIS/1km/"+ "{year}/".format(year=year))

	ftp.retrlines('LIST',filelist.append)

	ftp.retrbinary("RETR " + filelist[-1].split()[8], open(os.path.join(GS_TMP_DIR,filelist[-1].split()[8]),"wb").write)


	decompressedFile = gzip.GzipFile(os.path.join(GS_TMP_DIR,filelist[-1].split()[8]), 'rb')
	s=decompressedFile.read()
	decompressedFile.close()
	outF = file(os.path.join(GS_TMP_DIR,filelist[-1].split()[8,:-3]), 'wb')
	outF.write(s)
	outF.close()

	ftp.quit()

	subprocess.call('%s -te 2438000 4432000 4429000 6301000 %s %s' %(os.path.join(gdal_path,'gdalwarp'), os.path.join(GS_TMP_DIR,filelist[-1].split()[8][:-3]), os.path.join(GS_TMP_DIR,filelist[-1].split()[8][:-7])+'_cropped.tif'),shell=True)
	subprocess.call('%s -t_srs EPSG:4326 %s %s' %(os.path.join(gdal_path,'gdalwarp'), os.path.join(GS_TMP_DIR,filelist[-1].split()[8][:-7])+'_cropped.tif', os.path.join(GS_TMP_DIR,filelist[-1].split()[8][:-7])+'_reproj.tif'),shell=True)

	subprocess.call('%s -cutline %s -crop_to_cutline %s %s' %(os.path.join(gdal_path,'gdalwarp'), os.path.join(initial_data_path,'afg_admbnda_int.shp'), os.path.join(GS_TMP_DIR,filelist[-1].split()[8][:-7])+'_reproj.tif', os.path.join(GS_TMP_DIR,filelist[-1].split()[8][:-7])+'_cropped_afg.tif'),shell=True)

	subprocess.call('%s %s -f "ESRI Shapefile" %s' %(os.path.join(gdal_path,'gdal_polygonize.py'), os.path.join(GS_TMP_DIR,filelist[-1].split()[8][:-7])+'_cropped_afg.tif', os.path.join(GS_TMP_DIR,filelist[-1].split()[8][:-7])+'_poly_temp.shp'),shell=True)
	subprocess.call('%s %s %s -where "DN=4"' %(os.path.join(gdal_path,'ogr2ogr'), os.path.join(GS_TMP_DIR,filelist[-1].split()[8][:-7])+'_poly.shp', os.path.join(GS_TMP_DIR,filelist[-1].split()[8][:-7])+'_poly_temp.shp'),shell=True)
	mapping = {
		'wkb_geometry' : 'POLYGON',
	} # The mapping is a dictionary

	# update snow cover in geodb
	tempCurrentSC.objects.all().delete()
	lm = LayerMapping(tempCurrentSC, os.path.join(GS_TMP_DIR,filelist[-1].split()[8][:-7])+'_poly.shp', mapping)
	lm.save(verbose=True)

	# create intersects layer of basin with SC
	cursor = connections['geodb'].cursor()
	cursor.execute("delete from current_sc_basins")
	cursor.execute("insert into current_sc_basins(basin,wkb_geometry) select a.value, ST_Multi(ST_Intersection(a.wkb_geometry, b.wkb_geometry)) as wkb_geometry from afg_sheda_lvl4 as a, temp_current_sc as b where st_intersects(a.wkb_geometry, b.wkb_geometry)")

	cursor.close()
	# clean temporary files
	cleantmpfile('ims')
	print 'snowCover done'

def getSnowVillage(request):
	template = './snowInfo.html'
	village = request.GET["v"]
	context_dict = getCommonVillageData(village)
	currentdate = datetime.datetime.utcnow()
	year = currentdate.strftime("%Y")
	month = currentdate.strftime("%m")
	day = currentdate.strftime("%d")

	# print context_dict

	snowCal = AfgSnowaAverageExtent.objects.all().filter(dist_code=context_dict['dist_code'])
	snowCal = snowCal.filter(wkb_geometry__contains=context_dict['position'])


	cursor = connections['geodb'].cursor()
	cursor.execute("\
		select b.ogc_fid, b.value, c.riskstate, a.wkb_geometry \
		from current_sc_basins a \
		inner join afg_sheda_lvl4 b on a.basin=b.value \
		left outer join forcastedvalue c on b.ogc_fid=c.basin_id and c.forecasttype = 'snowwaterreal' and c.datadate = NOW()::date \
		where st_intersects(ST_GeomFromText('"+context_dict['position'].wkt+"', 4326), a.wkb_geometry)\
	")
	currSnow = cursor.fetchall()
	cursor.close()

	# currSnow = AfgShedaLvl4.objects.all().filter(wkb_geometry__contains=context_dict['position']).select_related("basins").filter(basins__datadate=year+'-'+month+'-'+day,basins__forecasttype='snowwaterreal').values('basins__riskstate')
	tempDepth = None
	for i in currSnow:
		tempDepth = i[2]
		if tempDepth == None :
			tempDepth = 1

	if tempDepth > 0 and tempDepth <=10:
		context_dict['current_snow_depth'] = 'Snow cover, no info on depth'
	elif tempDepth > 10 and tempDepth <=25:
		context_dict['current_snow_depth'] = '5cm - 25cm'
	elif tempDepth > 25 and tempDepth <=50:
		context_dict['current_snow_depth'] = '15cm - 50cm'
	elif tempDepth > 50 and tempDepth <=100:
		context_dict['current_snow_depth'] = '25cm - 1m'
	elif tempDepth > 100 and tempDepth <=150:
		context_dict['current_snow_depth'] = '50cm - 1.5m'
	elif tempDepth > 150 and tempDepth <=200:
		context_dict['current_snow_depth'] = '75cm - 2m'
	elif tempDepth > 200:
		context_dict['current_snow_depth'] = '> 1m - 2m'
	else:
		context_dict['current_snow_depth'] = 'not covered by snow'
	# Forcastedvalue.objects.all().filter(datadate=year+'-'+month+'-'+day,forecasttype='flashflood',basin=basin)
	# targetAvalanche.select_related("basinmembersava").exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='snowwater',basinmember__basins__datadate='%s-%s-%s' %(YEAR,MONTH,DAY))
	data1 = []
	data1.append([_('Month'),'Snow_Cover'])
	for i in snowCal:
		data1.append([_('Jan'),getSnowCoverClassNumber(i.cov_01_jan)])
		data1.append([_('Feb'),getSnowCoverClassNumber(i.cov_02_feb)])
		data1.append([_('Mar'),getSnowCoverClassNumber(i.cov_03_mar)])
		data1.append([_('Apr'),getSnowCoverClassNumber(i.cov_04_apr)])
		data1.append([_('May'),getSnowCoverClassNumber(i.cov_05_may)])
		data1.append([_('Jun'),getSnowCoverClassNumber(i.cov_06_jun)])
		data1.append([_('Jul'),getSnowCoverClassNumber(i.cov_07_jul)])
		data1.append([_('Aug'),getSnowCoverClassNumber(i.cov_08_aug)])
		data1.append([_('Sep'),getSnowCoverClassNumber(i.cov_09_sep)])
		data1.append([_('Oct'),getSnowCoverClassNumber(i.cov_10_oct)])
		data1.append([_('Nov'),getSnowCoverClassNumber(i.cov_11_nov)])
		data1.append([_('Dec'),getSnowCoverClassNumber(i.cov_12_dec)])

	context_dict['snowcover_line_chart'] = gchart.LineChart(SimpleDataSource(data=data1), html_id="line_chart1", options={'title': _("Snow Cover Calendar"), 'width': 500,'height': 250, 'legend': 'none', 'curveType': 'function', 'vAxis': { 'ticks': [{ 'v': 0, 'f': _('No Snow')}, {'v': 1, 'f': _('Very low')}, {'v': 2, 'f': _('Low')}, {'v': 3, 'f': _('Average')}, {'v': 4, 'f': _('High')}, {'v': 5, 'f': _('Very high')}]}})
	context_dict.pop('position')
	return render_to_response(template,
								  RequestContext(request, context_dict))

def getSnowVillageCommon(village):
	# template = './snowInfo.html'
	# village = request.GET["v"]
	context_dict = getCommonVillageData(village)
	currentdate = datetime.datetime.utcnow()
	year = currentdate.strftime("%Y")
	month = currentdate.strftime("%m")
	day = currentdate.strftime("%d")

	# print context_dict

	snowCal = AfgSnowaAverageExtent.objects.all().filter(dist_code=context_dict['dist_code'])
	snowCal = snowCal.filter(wkb_geometry__contains=context_dict['position'])


	cursor = connections['geodb'].cursor()
	sql = "\
		select b.ogc_fid, b.value, c.riskstate, a.wkb_geometry \
		from current_sc_basins a \
		inner join afg_sheda_lvl4 b on a.basin=b.value \
		left outer join forcastedvalue c on b.ogc_fid=c.basin_id and c.forecasttype = 'snowwaterreal' and c.datadate = NOW()::date \
		where st_intersects(ST_GeomFromText('"+context_dict['position'].wkt+"', 4326), a.wkb_geometry)\
	"
	print linenum() ,sql
	cursor.execute(sql)
	currSnow = cursor.fetchall()
	cursor.close()

	# currSnow = AfgShedaLvl4.objects.all().filter(wkb_geometry__contains=context_dict['position']).select_related("basins").filter(basins__datadate=year+'-'+month+'-'+day,basins__forecasttype='snowwaterreal').values('basins__riskstate')
	tempDepth = None
	for i in currSnow:
		tempDepth = i[2]
		if tempDepth == None :
			tempDepth = 1

	if tempDepth > 0 and tempDepth <=10:
		context_dict['current_snow_depth'] = 'Snow cover, no info on depth'
	elif tempDepth > 10 and tempDepth <=25:
		context_dict['current_snow_depth'] = '5cm - 25cm'
	elif tempDepth > 25 and tempDepth <=50:
		context_dict['current_snow_depth'] = '15cm - 50cm'
	elif tempDepth > 50 and tempDepth <=100:
		context_dict['current_snow_depth'] = '25cm - 1m'
	elif tempDepth > 100 and tempDepth <=150:
		context_dict['current_snow_depth'] = '50cm - 1.5m'
	elif tempDepth > 150 and tempDepth <=200:
		context_dict['current_snow_depth'] = '75cm - 2m'
	elif tempDepth > 200:
		context_dict['current_snow_depth'] = '> 1m - 2m'
	else:
		context_dict['current_snow_depth'] = 'not covered by snow'
	# Forcastedvalue.objects.all().filter(datadate=year+'-'+month+'-'+day,forecasttype='flashflood',basin=basin)
	# targetAvalanche.select_related("basinmembersava").exclude(basinmember__basins__riskstate=None).filter(basinmember__basins__forecasttype='snowwater',basinmember__basins__datadate='%s-%s-%s' %(YEAR,MONTH,DAY))
	data1 = []
	data1.append([_('Month'),'Snow_Cover'])
	i = next(iter(snowCal or []), None) # get first item or None
	data1.append([_('Jan'),getSnowCoverClassNumber(getattr(i, 'cov_01_jan', None))])
	data1.append([_('Feb'),getSnowCoverClassNumber(getattr(i, 'cov_02_feb', None))])
	data1.append([_('Mar'),getSnowCoverClassNumber(getattr(i, 'cov_03_mar', None))])
	data1.append([_('Apr'),getSnowCoverClassNumber(getattr(i, 'cov_04_apr', None))])
	data1.append([_('May'),getSnowCoverClassNumber(getattr(i, 'cov_05_may', None))])
	data1.append([_('Jun'),getSnowCoverClassNumber(getattr(i, 'cov_06_jun', None))])
	data1.append([_('Jul'),getSnowCoverClassNumber(getattr(i, 'cov_07_jul', None))])
	data1.append([_('Aug'),getSnowCoverClassNumber(getattr(i, 'cov_08_aug', None))])
	data1.append([_('Sep'),getSnowCoverClassNumber(getattr(i, 'cov_09_sep', None))])
	data1.append([_('Oct'),getSnowCoverClassNumber(getattr(i, 'cov_10_oct', None))])
	data1.append([_('Nov'),getSnowCoverClassNumber(getattr(i, 'cov_11_nov', None))])
	data1.append([_('Dec'),getSnowCoverClassNumber(getattr(i, 'cov_12_dec', None))])
	# for i in snowCal:
	# 	data1.append([_('Jan'),getSnowCoverClassNumber(i.cov_01_jan)])
	# 	data1.append([_('Feb'),getSnowCoverClassNumber(i.cov_02_feb)])
	# 	data1.append([_('Mar'),getSnowCoverClassNumber(i.cov_03_mar)])
	# 	data1.append([_('Apr'),getSnowCoverClassNumber(i.cov_04_apr)])
	# 	data1.append([_('May'),getSnowCoverClassNumber(i.cov_05_may)])
	# 	data1.append([_('Jun'),getSnowCoverClassNumber(i.cov_06_jun)])
	# 	data1.append([_('Jul'),getSnowCoverClassNumber(i.cov_07_jul)])
	# 	data1.append([_('Aug'),getSnowCoverClassNumber(i.cov_08_aug)])
	# 	data1.append([_('Sep'),getSnowCoverClassNumber(i.cov_09_sep)])
	# 	data1.append([_('Oct'),getSnowCoverClassNumber(i.cov_10_oct)])
	# 	data1.append([_('Nov'),getSnowCoverClassNumber(i.cov_11_nov)])
	# 	data1.append([_('Dec'),getSnowCoverClassNumber(i.cov_12_dec)])

	ticks = [{ 'v': 0, 'f': _('No Snow')}, {'v': 1, 'f': _('Very low')}, {'v': 2, 'f': _('Low')}, {'v': 3, 'f': _('Average')}, {'v': 4, 'f': _('High')}, {'v': 5, 'f': _('Very high')}]
	context_dict['ticks'] = ticks
	context_dict['snowcover_month_depth'] = data1
	context_dict['snowcover_line_chart'] = gchart.LineChart(SimpleDataSource(data=data1), html_id="line_chart1", options={'title': _("Snow Cover Calendar"), 'width': 500,'height': 250, 'legend': 'none', 'curveType': 'function', 'vAxis': { 'ticks': ticks}})
	context_dict.pop('position')
	return context_dict

def getSnowCoverClassNumber(x):
	if x == 'Very low':
		return 1
	elif x == 'Low':
		return 2
	elif x == 'Average':
		return 3
	elif x == 'High':
		return 4
	elif x == 'Very high':
		return 5
	else:
		return 0

def dashboard_avalancherisk(request, filterLock, flag, code, includes=[], excludes=[], response=dict_ext()):

	# response = dict_ext()

	AVA_LIKELIHOOD_INDEX_EXC_LOW = {k:v for k,v in AVA_LIKELIHOOD_INDEX.items() if v is not 'low'}
	# AVA_LIKELIHOOD_TYPES_EXC_LOW = {k:v for k,v in AVA_LIKELIHOOD_TYPES.items() if k is not 'low'}
	AVA_LIKELIHOOD_TYPES_EXC_LOW = {'high':_('High Risk'),'med':_('Medium Risk')}

	if include_section('getCommonUse', includes, excludes):
		response.update(getCommonUse(request, flag, code))

	response['source'] = response.pathget('cache','getAvalancheRisk') or getAvalancheRisk(request, filterLock, flag, code, response=response.within('cache'))
	response['panels'] = panels = dict_ext()
	baseline = response['source']['baseline']
	avalancherisk = response['source']['avalancherisk']
	titles = {'pop':'Avalanche Risk Population','building':'Avalanche Risk Building','area':'Avalanche Risk Area'}

	for p in ['pop','building','area']:
		panels.path(p+'_likelihood')['title'] = titles[p]
		panels.path(p+'_likelihood')['value'] = [avalancherisk[p+'_likelihood'].get(d) or 0 for d in AVA_LIKELIHOOD_INDEX_EXC_LOW.values()]
		panels.path(p+'_likelihood')['total_atrisk'] = total_atrisk = sum(panels.path(p+'_likelihood')['value'])
		panels.path(p+'_likelihood')['total'] = total = baseline[p+'_total']
		panels.path(p+'_likelihood')['value'].append(total-total_atrisk) # value not at risk
		panels.path(p+'_likelihood')['label'] = [AVA_LIKELIHOOD_TYPES_EXC_LOW[d] for d in AVA_LIKELIHOOD_INDEX_EXC_LOW.values()] + [_('Not at risk')]
		panels.path(p+'_likelihood')['percent'] = [avalancherisk[p+'_likelihood_percent'].get(d) or 0 for d in AVA_LIKELIHOOD_INDEX_EXC_LOW.values()]
		panels.path(p+'_likelihood')['percent'].append(100-sum(panels.path(p+'_likelihood')['percent'])) # percent not at risk
		panels.path(p+'_likelihood')['child'] = [[AVA_LIKELIHOOD_TYPES_EXC_LOW[d], avalancherisk[p+'_likelihood'].get(d)] for d in AVA_LIKELIHOOD_INDEX_EXC_LOW.values()]
		panels.path(p+'_likelihood')['child'].append([_('Not at risk'),total-total_atrisk]) # percent not at risk

	if include_section('adm_lc', includes, excludes):
		# response['adm_lc'] = baseline['adm_lc']
		panels['adm_likelihood_pop_building_area'] = {
			'title':_('Population, Building and Area of Avalanche Risk'),
			'parentdata':[
				response['parent_label'],
				avalancherisk['pop_likelihood']['high'],
				avalancherisk['building_likelihood']['high'],
				avalancherisk['area_likelihood']['high'],
				avalancherisk['pop_likelihood']['med'],
				avalancherisk['building_likelihood']['med'],
				avalancherisk['area_likelihood']['med'],
				avalancherisk['pop_likelihood_total'],
				avalancherisk['building_likelihood_total'],
				avalancherisk['area_likelihood_total'],
			],
			'child':[{
				'value':[
					v['na_en'],
					v['high_ava_population'],
					v['high_ava_buildings'],
					v['high_ava_area'],
					v['med_ava_population'],
					v['med_ava_buildings'],
					v['med_ava_area'],
					v['total_ava_population'],
					v['total_ava_buildings'],
					v['total_ava_area'],
				],
				'code':v['code'],
			} for v in response['source']['adm_lc']],
		}

	if include_section('GeoJson', includes, excludes):
		response['GeoJson'] = geojsonadd_avalancherisk(response)

	return response

def dashboard_avalancheforecast(request, filterLock, flag, code, includes=[], excludes=[], date='', response=dict_ext()):

	# response = dict_ext()

	if include_section('getCommonUse', includes, excludes):
		response.update(getCommonUse(request, flag, code))

	response['source'] = response.pathget('cache','getAvalancheForecast') or getAvalancheForecast(request, filterLock, flag, code, date=date)
	panels = response.path('panels')
	baseline = response['source']['baseline']
	avalancheforecast = response['source']['avalancheforecast']
	titles = {'pop':'Avalanche Prediction Population Graph','building':'Avalanche Prediction Building Graph'}
	AVA_LIKELIHOOD_TYPES = {'high':'High Risk','med':'Medium Risk','low':'Low Risk'}

	for p in ['pop','building']:
		panels.path(p+'_likelihood')['title'] = titles[p]
		panels.path(p+'_likelihood')['value'] = [dict_ext(avalancheforecast).pathget(p+'_likelihood',d) or 0 for d in AVA_LIKELIHOOD_INDEX.values()]
		panels.path(p+'_likelihood')['total_atrisk'] = total_atrisk = sum(panels.pathget(p+'_likelihood','value') or [])
		panels.path(p+'_likelihood')['total'] = total = baseline[p+'_total']
		panels.path(p+'_likelihood')['value'].append(total-total_atrisk) # value not at risk
		panels.path(p+'_likelihood')['label'] = [AVA_LIKELIHOOD_TYPES[d] for d in AVA_LIKELIHOOD_INDEX.values()] + [_('Not at risk')]
		# panels.path(p+'_likelihood')['percent'] = [dict_ext(avalancheforecast).pathget(p+'_likelihood_percent',d) or 0 for d in AVA_LIKELIHOOD_INDEX.values()]
		# panels.path(p+'_likelihood')['percent'].append(100-sum(panels.path(p+'_likelihood')['percent'])) # percent not at risk
		panels.path(p+'_likelihood')['child'] = [[AVA_LIKELIHOOD_TYPES[d], dict_ext(avalancheforecast).pathget(p+'_likelihood',d)] for d in AVA_LIKELIHOOD_INDEX.values()]
		panels.path(p+'_likelihood')['child'].append([_('Not at risk'),total-total_atrisk]) # percent not at risk

	if include_section('adm_likelihood', includes, excludes):
		panels['adm_likelihood'] = {
			'title':_('Population in Predicted Avalanche Risk Area'),
			'parentdata':[
				response['parent_label'],
				avalancheforecast['pop_likelihood']['high'],
				avalancheforecast['pop_likelihood']['med'],
				avalancheforecast['pop_likelihood']['low'],
				avalancheforecast['pop_likelihood_total'],
			],
			'child':[{
				'value':[
					v['na_en'],
					v['ava_forecast_high_pop'],
					v['ava_forecast_med_pop'],
					v['ava_forecast_low_pop'],
					v['total_ava_forecast_pop'],
				],
				'code':v['code'],
			} for v in avalancheforecast['adm_likelihood']],
		}

	if include_section('GeoJson', includes, excludes):
		response['GeoJson'] = geojsonadd_avalancheforecast(response)

	return response

def geojsonadd_avalancherisk(response):

	avalancherisk = response['source']['avalancherisk']
	baseline = response['source']['baseline']
	boundary = response['source']['GeoJson']
	response['source']['adm_lc_dict'] = {v['code']:v for v in response['source']['adm_lc']}

	for k,v in enumerate(boundary.get('features',[])):
		boundary['features'][k]['properties'] = prop = dict_ext(boundary['features'][k]['properties'])

		# Checking if it's in a district
		if response['areatype'] == 'district':
			response['set_jenk_divider'] = 1
			prop['na_en']=response['parent_label']
			prop.update({'%s_ava_%s'%(i,k):avalancherisk[j+'_likelihood'][i] for i in['high','med'] for j,k in {'pop':'population','building':'buildings','area':'area'}.items()})

		else:
			response['set_jenk_divider'] = 7
			if prop['code'] in response['source']['adm_lc_dict']:
				v = response['source']['adm_lc_dict'][prop['code']]
				prop['na_en'] = v['na_en']
				prop.update({'%s_ava_%s'%(i,j):v['%s_ava_%s'%(i,j)] for i in['high','med'] for j in ['population','buildings','area',]})

	return boundary

def geojsonadd_avalancheforecast(response):

	avalancheforecast = response['source']['avalancheforecast']
	baseline = response['source']['baseline']
	boundary = response['source']['GeoJson']
	avalancheforecast['adm_likelihood_dict'] = {v['code']:v for v in avalancheforecast['adm_likelihood']}

	for k,v in enumerate(boundary.get('features',[])):
		boundary['features'][k]['properties'] = prop = dict_ext(boundary['features'][k]['properties'])

		# Checking if it's in a district
		if response['areatype'] == 'district':
			response['set_jenk_divider'] = 1
			prop['na_en']=response['parent_label']
			prop.update({'ava_forecast_%s_pop'%(i):avalancheforecast['pop_likelihood'][i] for i in AVA_LIKELIHOOD_TYPES})

		else:
			response['set_jenk_divider'] = 7
			if (prop['code'] in avalancheforecast['adm_likelihood_dict']):
				j = avalancheforecast['adm_likelihood_dict'][prop['code']]
				prop['na_en'] = j['na_en']
				prop.update({'ava_forecast_%s_pop'%(i):j[i+'_ava_population'] for i in AVA_LIKELIHOOD_TYPES})

	return boundary

class AvalancheRiskStatisticResource(ModelResource):

	class Meta:
		# authorization = DjangoAuthorization()
		resource_name = 'statistic_avalancherisk'
		allowed_methods = ['post']
		detail_allowed_methods = ['post']
		cache = SimpleCache()
		object_class=None
 
	def getRisk(self, request):
		p = urlparse(request.META.get('HTTP_REFERER')).path.split('/')
		mapCode = p[3] if 'v2' in p else p[2]
		map_obj = _resolve_map(request, mapCode, 'base.view_resourcebase', _PERMISSION_MSG_VIEW)

		queryset = matrix(user=request.user,resourceid=map_obj,action='Interactive Calculation')
		queryset.save()

		data = json.loads(request.body)

		wkts = ['ST_GeomFromText(\''+i+'\',4326)' for i in data['spatialfilter']]
		bring = wkts[-1] if len(wkts) else None
		filterLock = 'ST_Union(ARRAY[%s])'%(', '.join(wkts))

		response = getAvalancheriskStatistic(request, filterLock, data.get('flag'), data.get('code'))

		return response

	def post_list(self, request, **kwargs):
		self.method_check(request, allowed=['post'])
		response = self.getRisk(request)
		return self.create_response(request, response)  

def getAvalancheriskStatistic(request,filterLock, flag, code):

	panels = dashboard_avalancherisk(request, filterLock, flag, code)['panels']

	panels_list = dict_ext()
	panels_list['charts'] = [v for k,v in panels.items() if k in ['pop_likelihood','building_likelihood','area_likelihood']]
	panels['adm_likelihood_pop_building_area']['child'] = [panels['adm_likelihood_pop_building_area']['parentdata']] + [v['value'] for v in panels['adm_likelihood_pop_building_area']['child']]
	# panels['adm_likelihood_pop_building_area']['child'] += [v['value'] for v in panels['adm_likelihood_pop_building_area']['child']]
	panels_list['tables'] = [panels['adm_likelihood_pop_building_area'],]

	return panels_list

class AvalancheForecastStatisticResource(ModelResource):

	class Meta:
		# authorization = DjangoAuthorization()
		resource_name = 'statistic_avalancheforecast'
		allowed_methods = ['post']
		detail_allowed_methods = ['post']
		cache = SimpleCache()
		object_class=None
 
	def getRisk(self, request):
		p = urlparse(request.META.get('HTTP_REFERER')).path.split('/')
		mapCode = p[3] if 'v2' in p else p[2]
		map_obj = _resolve_map(request, mapCode, 'base.view_resourcebase', _PERMISSION_MSG_VIEW)

		queryset = matrix(user=request.user,resourceid=map_obj,action='Interactive Calculation')
		queryset.save()

		data = json.loads(request.body)

		wkts = ['ST_GeomFromText(\''+i+'\',4326)' for i in data['spatialfilter']]
		bring = wkts[-1] if len(wkts) else None
		filterLock = 'ST_Union(ARRAY[%s])'%(', '.join(wkts))

		response = getAvalancheforecastStatistic(request, filterLock, data.get('flag'), data.get('code'), data.get('date'))

		return response

	def post_list(self, request, **kwargs):
		self.method_check(request, allowed=['post'])
		response = self.getRisk(request)
		return self.create_response(request, response)  

class AvalancheStatisticResource(ModelResource):

	class Meta:
		# authorization = DjangoAuthorization()
		resource_name = 'statistic_avalanche'
		allowed_methods = ['post']
		detail_allowed_methods = ['post']
		cache = SimpleCache()
		object_class=None
		# always_return_data = True
 
	def getRisk(self, request):

		p = urlparse(request.META.get('HTTP_REFERER')).path.split('/')
		mapCode = p[3] if 'v2' in p else p[2]
		map_obj = _resolve_map(request, mapCode, 'base.view_resourcebase', _PERMISSION_MSG_VIEW)

		queryset = matrix(user=request.user,resourceid=map_obj,action='Interactive Calculation')
		queryset.save()

		boundaryFilter = json.loads(request.body)

		wkts = ['ST_GeomFromText(\'%s\',4326)'%(i) for i in boundaryFilter['spatialfilter']]
		bring = wkts[-1] if len(wkts) else None
		filterLock = 'ST_Union(ARRAY[%s])'%(','.join(wkts))

		response = getAvalancheStatistic(request, filterLock, boundaryFilter.get('flag'), boundaryFilter.get('code'), date=boundaryFilter.get('date'))

		return response

	def post_list(self, request, **kwargs):
		self.method_check(request, allowed=['post'])
		response = self.getRisk(request)
		return self.create_response(request, response)  

def getAvalancheforecastStatistic(request,filterLock, flag, code, date):

	panels = dashboard_avalancheforecast(request, filterLock, flag, code, date=date)['panels']

	panels_list = dict_ext()
	panels_list['charts'] = [v for k,v in panels.items() if k in ['pop_likelihood','building_likelihood']]
	# panels['adm_likelihood_pop_building_area']['child'] = panels['adm_likelihood_pop_building_area']['parentdata'] + [v['value'] for v in panels['adm_likelihood_pop_building_area']['child']]
	panels_list['tables'] = [panels['adm_likelihood'],]

	return panels_list

def getAvalancheStatistic(request,filterLock, flag, code, date=None):

	response = {
		'panels_list':{
			'avalancherisk': getAvalancheriskStatistic(request,filterLock, flag, code),
			'avalancheforecast': getAvalancheforecastStatistic(request,filterLock, flag, code, date=date),
		}
	}

	return response

class SnowInfoVillages(Resource):

	class Meta:
		resource_name = 'snow'
		authentication = SessionAuthentication()

	def prepend_urls(self):
		name = self._meta.resource_name
		return [
			url(r"^%s%s$" % (name, trailing_slash()), self.wrap_view('getdata'), name='get_%s'%(name)),
		]

	def getdata(self, request, **kwargs):
		self.method_check(request, allowed=['get'])
		self.is_authenticated(request)
		self.throttle_check(request)

		data = getSnowVillageCommon(request.GET.get('vuid'))

		response = {
			'panels_list':{
				'tables':[
					{
						'key':'base_info',
						'child':[
							[_('District'),data.get('dist_na_en')],
							[_('Province'),data.get('prov_na_en')],
							[_('Elevation'),'{:,} m above sea level'.format(data.get('elevation'))],
							[_('Approx. Current Snow Depth'),'{}'.format(data.get('current_snow_depth'))],
						],
					},
				],
				'charts':[
					{
						'key':'snow_cover_calendar',
						'title':_('FloodSnow Cover Calendar'),
						'columntitles':data['snowcover_month_depth'][0],
						'child':data['snowcover_month_depth'][1:],
						'y_axis_alias':[[l['v'],l['f']] for l in data['ticks']],
					},
				]
			},
		}

		return self.create_response(request, response)

def getQuickOverview(request, filterLock, flag, code, response=dict_ext()):
	
	response.path('cache')['getAvalancheRisk'] = response.pathget('cache','getAvalancheRisk') or getAvalancheRisk(request, filterLock, flag, code, includes=[''], response=response)
	dashboard_avalancherisk_response = dashboard_avalancherisk(request, filterLock, flag, code, includes=[''], response=response.within('cache'))
	
	if response.pathget('cache','getBaseline','avalancheforecast'):
		response.path('cache')['getAvalancheForecast'] = response.pathget('cache','getBaseline').within('baseline','avalancheforecast')
	else:
		response.path('cache')['getAvalancheForecast'] = getAvalancheForecast(request, filterLock, flag, code, includes=[''], response=response)
	dashboard_avalancheforecast_response = dashboard_avalancheforecast(request, filterLock, flag, code, includes=[''], response=response.within('cache'))
	
	return {
		'templates':{
			'panels':'dash_qoview_avalanche.html',
		},
		'data':{
			'panels':{
				'avalancherisk':dict_ext(dashboard_avalancherisk_response).pathget('panels'),
				'avalancheforecast':dict_ext(dashboard_avalancheforecast_response).pathget('panels'),
			}
		},
	}
	